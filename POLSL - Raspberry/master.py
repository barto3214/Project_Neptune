#!/usr/bin/env python3
"""
RASPBERRY PI #2 - STACJA POMIAROWA (Remote Station)
Funkcje:
1. Odbiera komendy z Arduino przez Serial
2. Czyta czujniki (pH, TDS, Temp, Conductivity)
3. Steruje pompą (relay)
4. Wysyła dane do Arduino przez Serial
5. Serwuje stream z kamery przez HTTP (MJPEG)

Komunikacja Serial z Arduino:
- Komendy otrzymywane (z Arduino):
  * MEASURE:120  - rozpocznij pomiar przez 120 sekund
  * STOP         - zatrzymaj pomiar
  * PUMP_ON      - włącz pompę
  * PUMP_OFF     - wyłącz pompę
  * STATUS       - wyślij status
  * SAMPLES_LOADING - wykonaj sekwencję ładowania próbek
  * REJECT_SAMPLE   - wykonaj sekwencję odrzutu próbki
  * GET_DATA     - wyślij aktualne dane

- Dane wysyłane (do Arduino):
  * DATA:7.2,350,22.5,700,1\n  (pH,TDS,Temp,Cond,Pump)
  * STATUS:OK,3700,0\n         (Status,BatteryMv,ErrorFlags)

Stream kamery:
  * http://<IP>:8080/stream    - MJPEG stream dla WPF
  * http://<IP>:8080/snapshot  - pojedyncza klatka
  * http://<IP>:8080/          - podgląd w przeglądarce
"""

import serial
import time
import threading
from datetime import datetime
import glob
import subprocess
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn
from dataclasses import dataclass
import db_manager 
import RPi.GPIO as GPIO

# Konfiguracja Serial
SERIAL_PORT = '/dev/ttyUSB0'  # Arduino przez USB

# SERIAL_PORT = '/dev/serial0'  # UART (GPIO 14/15)
SERIAL_BAUD = 115200

# Konfiguracja GPIO (piny)
PUMP_1_RELAY_PIN = 24  # GPIO 24 dla przekaźnika pompy 1
PUMP_2_RELAY_PIN = 25  # GPIO 25 dla przekaźnika pompy 2
PUMP_DURATION = 2    # Czas pracy pompy w sekundach do załadunku probówki 
REJECT_POSITION = 0    # Pozycja karuzeli do odrzutu 
REJECT_PUMP_TIME = 7.0 # Czas pracy pompy przy odrzucaniu próbki (do opróżnienia zbiornika) 
PUMP_1_MAX_TIME = 7.0 # Maksymalny czas pracy pompy 1 (żeby nie rozsadziło) 

# === I2C ===
i2c = I2C(1)
ads = ADS1115(i2c)

chan_ph  = AnalogIn(ads, 0)  # A0 - czujnik pH
chan_ec  = AnalogIn(ads, 1)  # A1 - czujnik przewodności
chan_tds = AnalogIn(ads, 2)  # A2 - czujnik TDS DFRobot

# === KALIBRACJA pH ===
CAL_PH1         = 4.1
CAL_VOLTAGE_PH1 = 0.88
CAL_PH3         = 9.1
CAL_VOLTAGE_PH3 = 1.43

# === KALIBRACJA EC ===
CAL_VOLTAGE_DRY  = 0.003
CAL_VOLTAGE_SALT = 2.3585
CAL_EC_SALT      = 25000  # µS/cm

# === TEMPERATURA (DS18B20) ===
TEMP_SLOPE  = (16.0 - 0.0) / (21.0 - 2.5)
TEMP_OFFSET = 0.0 - TEMP_SLOPE * 2.5

slope_ph  = (CAL_PH3 - CAL_PH1) / (CAL_VOLTAGE_PH3 - CAL_VOLTAGE_PH1)
offset_ph = CAL_PH1 - slope_ph * CAL_VOLTAGE_PH1

# Pomiar
measuring = False
measurement_start_time = 0
measurement_duration = 0
last_measurement = 0
MEASUREMENT_INTERVAL = 2  # Sekund między pomiarami
last_measure_time = 0  


pump_state = False            # obecny stan pompy (True=ON)
ser = None                    # obiekt Serial
sensor_data = {
    'ph': 0.0,
    'tds': 0.0,
    'temperature': 0.0,
    'conductivity': 0.0,
}

# === KONFIGURACJA GPIO ===

# Silnik krokowy 28BYJ-48
STEP_IN1 = 17
STEP_IN2 = 27
STEP_IN3 = 22
STEP_IN4 = 23

# Servo MG995
SERVO_PIN = 18

# Pozycje karuzeli
TOTAL_POSITIONS = 6  
STEPS_PER_POSITION = 43  # Liczba kroków — używana jako backup gdy enkoder wyłączony

# Pozycje servo
SERVO_UP = 11.7    # Duty cycle % dla pozycji górnej 
SERVO_DOWN = 2.5  # Duty cycle % dla pozycji dolnej 

# === ENKODER HEDL-5540 ===

#              Pin5(GREEN)→GPIO16, Pin7(VIOLET)→GPIO20, Pin9(WHITE)→GPIO21
ENC_A               = 16    # GPIO 16 (PIN 36) - kanał A
ENC_B               = 20    # GPIO 20 (PIN 38) - kanał B
ENC_I               = 21    # GPIO 21 (PIN 40) - index (jeden impuls/obrót)
ENCODER_ENABLED     = True  # False = tryb krokowy bez enkodera
TICKS_PER_POSITION  = 165   # TODO: USTAWIĆ Z KALIBRACJI (kalibracja.py opcja 3)
ENCODER_TOLERANCE   = 2     # Dopuszczalny błąd pozycji w tickach
ENCODER_MAX_RETRIES = 3     # Ile razy próbować korekty zanim się podda
ENCODER_TIMEOUT     = 15.0  # Max sekund na jeden obrót

# Licznik ticków enkodera — aktualizowany przez wątek pollingu
_enc_tick_count = 0
_enc_last_a     = 0  # poprzedni stan kanału A (do detekcji zbocza przez polling)

# ============================================================
# KONFIGURACJA KAMERY
# ============================================================
CAM_ENABLED  = True   # False = wyłącz kamerę jeśli niepodłączona
CAM_PORT     = 8080
CAM_WIDTH    = 1280
CAM_HEIGHT   = 720
CAM_FPS      = 30
CAM_QUALITY  = 70     # 0-100, mniej = mniejszy rozmiar

# Globalny bufor kamery
_frame_lock  = threading.Lock()
_last_frame  = None
_frame_event = threading.Event()

# ============================================================
# INICJALIZACJA GPIO
# ============================================================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(STEP_IN1, GPIO.OUT)
GPIO.setup(STEP_IN2, GPIO.OUT)
GPIO.setup(STEP_IN3, GPIO.OUT)
GPIO.setup(STEP_IN4, GPIO.OUT)

GPIO.setup(SERVO_PIN, GPIO.OUT)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)
servo_pwm.start(0)

HALF_STEP_SEQ = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1]
]

# ============================================================
# STAN KARUZELI
# ============================================================
class CarouselState:
    def __init__(self):
        self.current_position = 0
        self.is_busy          = False
        self.lock             = threading.Lock()
        self.needle_down      = False

    def get_status(self):
        return {
            "position":    self.current_position,
            "busy":        self.is_busy,
            "needle_down": self.needle_down
        }

state = CarouselState()

# ============================================================
# CZUJNIKI
# ============================================================
@dataclass
class SensorData:
    ph:            float
    tds:           float
    temperature:   float
    conductivity:  float

    def voltage_to_ph(voltage):
        return slope_ph * voltage + offset_ph

    def read_ph_avg(samples=20):
        readings = []
        for _ in range(samples):
            readings.append(SensorData.voltage_to_ph(chan_ph.voltage))
            time.sleep(0.05)
        readings.sort()
        cut = samples // 5
        trimmed = readings[cut:-cut]
        return sum(trimmed) / len(trimmed)

    def voltage_to_ec(voltage):
        if voltage <= CAL_VOLTAGE_DRY:
            return 0
        slope = CAL_EC_SALT / (CAL_VOLTAGE_SALT - CAL_VOLTAGE_DRY)
        return max(0, slope * (voltage - CAL_VOLTAGE_DRY))

    def ec_to_tds_ec(ec):
        return ec * 0.5

    def read_ec_avg(samples=10):
        readings = []
        for _ in range(samples):
            readings.append(SensorData.voltage_to_ec(chan_ec.voltage))
            time.sleep(0.02)
        readings.sort()
        trimmed = readings[1:-1]
        return sum(trimmed) / len(trimmed)

    def find_sensor():
        devices = glob.glob('/sys/bus/w1/devices/28*')
        if devices:
            return devices[0] + '/w1_slave'
        print("Temp czujnik: BRAK - sprawdź połączenie GPIO4 i 1-Wire!")
        return None

    def read_temp(retries=5):
        device_file = SensorData.find_sensor()
        if device_file is None:
            return None
        for attempt in range(retries):
            try:
                with open(device_file, 'r') as f:
                    lines = f.readlines()
                if len(lines) >= 2 and 'YES' in lines[0]:
                    temp_pos = lines[1].find('t=')
                    if temp_pos != -1:
                        raw = float(lines[1][temp_pos+2:].strip()) / 1000.0
                        return TEMP_SLOPE * raw + TEMP_OFFSET
                if attempt < retries - 1:
                    time.sleep(0.2)
            except Exception:
                if attempt < retries - 1:
                    time.sleep(0.2)
        return None

    def voltage_to_tds(voltage, temperature=25.0):
        compensation_coeff = 1.0 + 0.02 * (temperature - 25.0)
        voltage_comp = voltage / compensation_coeff
        tds = (133.42 * voltage_comp**3
             - 255.86 * voltage_comp**2
             + 857.39 * voltage_comp) * 0.5
        return max(0, tds)

# ============================================================
# ENKODER - POLLING
# Zamiast przerwań (GPIO.add_event_detect) używamy pollingu w osobnym wątku.
# RPi.GPIO ma znany błąd z edge detection na nowszych kernelach/Python 3.13.
# Polling 10kHz jest wystarczający — enkoder 12CPR daje max ~400 ticków/s.
# ============================================================
def _encoder_poll_loop():
    """Wątek pollingu enkodera — wykrywa zbocza kanału A i liczy ticki"""
    global _enc_tick_count, _enc_last_a
    while True:
        a = GPIO.input(ENC_A)
        if a != _enc_last_a:          # wykryto zbocze na kanale A
            b = GPIO.input(ENC_B)
            if a != b:
                _enc_tick_count += 1  # obrót do przodu
            else:
                _enc_tick_count -= 1  # obrót do tyłu
            _enc_last_a = a
        time.sleep(0.0001)            # 10kHz polling

# ============================================================
# KAMERA - WĄTEK PRZECHWYTYWANIA
# ============================================================
def camera_capture_loop():
    """Czyta klatki z rpicam-vid i wrzuca do bufora"""
    global _last_frame

    cmd = [
        "rpicam-vid",
        "--width",     str(CAM_WIDTH),
        "--height",    str(CAM_HEIGHT),
        "--framerate", str(CAM_FPS),
        "--codec",     "mjpeg",
        "--quality",   str(CAM_QUALITY),
        "--timeout",   "0",
        "--nopreview",
        "-o", "-",
    ]

    print(f"[CAM] Start: {CAM_WIDTH}x{CAM_HEIGHT} @ {CAM_FPS}fps")

    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            #print("[CAM] Kamera aktywna") <- debug

            buf = b""
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk

                while True:
                    start = buf.find(b"\xff\xd8")
                    end   = buf.find(b"\xff\xd9", start + 2)
                    if start == -1 or end == -1:
                        break
                    jpeg = buf[start:end + 2]
                    buf  = buf[end + 2:]
                    with _frame_lock:
                        _last_frame = jpeg
                    _frame_event.set()
                    _frame_event.clear()

        except Exception as e:
            print(f"[CAM] Błąd: {e} — restart za 2s")
            time.sleep(2)

# ============================================================
# KAMERA - SERWER HTTP
# ============================================================
class MJPEGHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # wycisz logi HTTP

    def do_GET(self):
        if self.path == "/stream":
            self._serve_stream()
        elif self.path == "/snapshot":
            self._serve_snapshot()
        elif self.path == "/":
            self._serve_index()
        else:
            self.send_error(404)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        print(f"[CAM] Klient podłączony: {self.client_address[0]}")
        try:
            while True:
                _frame_event.wait(timeout=1.0)
                with _frame_lock:
                    frame = _last_frame
                if frame is None:
                    continue
                header = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    b"\r\n"
                )
                self.wfile.write(header + frame + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print(f"[CAM] Rozłączono: {self.client_address[0]}")
        except Exception as e:
            print(f"[CAM] Błąd streamu: {e}")

    def _serve_snapshot(self):
        with _frame_lock:
            frame = _last_frame
        if frame is None:
            self.send_error(503, "Brak klatki")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(frame)

    def _serve_index(self):
        html = (
            f"<html><body style='background:#000;color:#fff;text-align:center'>"
            f"<h2>RPi #2 CAM {CAM_WIDTH}x{CAM_HEIGHT}@{CAM_FPS}fps</h2>"
            f"<img src='/stream'>"
            f"</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def camera_server_loop():
    """Uruchamia serwer HTTP kamery — odpala się jako wątek"""
    try:
        server = HTTPServer(("0.0.0.0", CAM_PORT), MJPEGHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "?.?.?.?"
        print(f"[CAM] Serwer HTTP: http://{ip}:{CAM_PORT}/stream")
        server.serve_forever()
    except Exception as e:
        print(f"[CAM] Błąd serwera HTTP: {e}")

# ============================================================
# GPIO / SERIAL
# ============================================================
def init_gpio():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PUMP_1_RELAY_PIN, GPIO.OUT)
        GPIO.output(PUMP_1_RELAY_PIN, GPIO.LOW)
        GPIO.setup(PUMP_2_RELAY_PIN, GPIO.OUT)
        GPIO.output(PUMP_2_RELAY_PIN, GPIO.LOW)

        # Enkoder — setup pinów wejściowych i start wątku pollingu
        if ENCODER_ENABLED:
            GPIO.setup(ENC_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(ENC_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(ENC_I, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            threading.Thread(target=_encoder_poll_loop, daemon=True).start()
            print(f"Enkoder: GPIO{ENC_A}/GPIO{ENC_B}, {TICKS_PER_POSITION} tick/poz")

        print("GPIO zainicjalizowane")
        return GPIO
    except ImportError:
        print("RPi.GPIO nie dostępne")
        return None

def init_serial():
    global ser
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUD,
            timeout=0.1,
            write_timeout=1.0
        )
        ser.setDTR(False)  
        print(f"Serial otwarty: {SERIAL_PORT} @ {SERIAL_BAUD}")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Błąd otwarcia Serial: {e}")
        return False
    
# ============================================================
# CZUJNIKI
# ============================================================
def read_sensors():
    temp = SensorData.read_temp()
    sensor_data['ph']           = SensorData.read_ph_avg()
    sensor_data['temperature']  = temp if temp is not None else 0.0  
    sensor_data['conductivity'] = SensorData.read_ec_avg()
    sensor_data['tds']          = SensorData.voltage_to_tds(
                                      chan_tds.voltage,
                                      sensor_data['temperature']
                                  )
    db_manager.add_measurement(
        time.time(),
        round(sensor_data['ph'], 2),
        round(sensor_data['tds'], 2),
        round(sensor_data['temperature'], 2),   
        round(sensor_data['conductivity'], 2)
    )

def control_pump_1(active, GPIO=None):
    global pump_state
    if active:
        GPIO.output(PUMP_1_RELAY_PIN, GPIO.HIGH)
        pump_state = True
        print(f"Pompa 1: ON (max {PUMP_1_MAX_TIME}s)")

        def auto_shutoff():
            global pump_state
            time.sleep(PUMP_1_MAX_TIME)
            if pump_state:
                GPIO.output(PUMP_1_RELAY_PIN, GPIO.LOW)
                pump_state = False
                print(f"[SAFETY] Pompa 1 wyłączona automatycznie po {PUMP_1_MAX_TIME}s!")

        threading.Thread(target=auto_shutoff, daemon=True).start()
    else:
        GPIO.output(PUMP_1_RELAY_PIN, GPIO.LOW)
        pump_state = False
        print("Pompa 1: OFF")

def send_data():
    if ser and ser.is_open:
        data_str = (f"DATA:{sensor_data['ph']:.2f},{sensor_data['tds']:.1f},"
                    f"{sensor_data['temperature']:.1f},{sensor_data['conductivity']:.1f},"
                    f"{1 if pump_state else 0}\n")
        try:
            ser.write(data_str.encode('utf-8'))
            ser.flush()
            print(f"Wysłano: {data_str.strip()}")
        except Exception as e:
            print(f"Błąd wysyłania: {e}")

def send_status():
    if ser and ser.is_open:
        battery_mv  = 3700  # TODO: Odczyt napięcia baterii
        error_flags = 0
        status_str  = f"STATUS:OK,{battery_mv},{error_flags}\n"
        try:
            ser.write(status_str.encode('utf-8'))
            print(f"Status: {status_str.strip()}")
        except Exception as e:
            print(f"Błąd wysyłania statusu: {e}")

def process_command(command, GPIO=None):
    global measuring, measurement_start_time, measurement_duration, last_measure_time

    command = command.strip().upper()

    IGNORED_PREFIXES = (
        "TX DATA", "RX COMMAND", "[DEBUG]", "===",
        "SYSTEM", "NASŁUCHIWANIE", "STACJA", "ARDUINO",
        "INICJALIZACJA", "GOTOWY", "START",
    )
    if any(command.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return

    if command.startswith("MEASURE:"):
        try:
            duration = int(command.split(':')[1])
            if time.time() - last_measure_time < 3:
                return
            last_measure_time      = time.time()
            measuring              = True
            measurement_start_time = time.time()
            measurement_duration   = duration
            print(f"START pomiaru przez {duration}s")
        except ValueError:
            print(f"Nieprawidłowa komenda MEASURE: {command}")

    elif command == "STOP":
        measuring = False
        print("STOP pomiaru")

    elif command == "PUMP_ON":
        control_pump_1(True, GPIO)

    elif command == "PUMP_OFF":
        control_pump_1(False, GPIO)

    elif command == "STATUS":
        send_status()

    elif command == "SAMPLES_LOADING":
        threading.Thread(target=loading_sequence, daemon=True).start()

    elif command == "REJECT_SAMPLE":
        threading.Thread(target=reject_sample, daemon=True).start()

    elif command == "GET_DATA":
        if measuring:
            read_sensors()
            send_data()

    else:
        print(f"Nieznana komenda: {command}")

def send_stop_to_arduino():
    if ser and ser.is_open:
        try:
            ser.write(b"MEASUREMENT_DONE\n")
            ser.flush()
            time.sleep(0.5)
            print("Wyslano MEASUREMENT_DONE do Arduino")
        except Exception as e:
            print(f"Blad wysylania STOP: {e}")

def measurement_loop(GPIO=None):
    global last_measurement, measuring
    while True:
        if measuring:
            elapsed = time.time() - measurement_start_time
            if elapsed >= measurement_duration:
                print(f"Koniec pomiaru ({measurement_duration}s)")
                measuring = False
                send_stop_to_arduino()
                continue
            if time.time() - last_measurement >= MEASUREMENT_INTERVAL:
                print(f"Pomiar ({elapsed:.0f}/{measurement_duration}s)...")
                try:
                    read_sensors()
                    send_data()
                except Exception as e:
                    print(f"[ERROR] Błąd odczytu czujników: {e}")
                last_measurement = time.time()
        time.sleep(0.1)

def pump_2_sequence(duration):
    GPIO.output(PUMP_2_RELAY_PIN, GPIO.HIGH)
    print("Pompa 2 ON")
    time.sleep(duration)
    GPIO.output(PUMP_2_RELAY_PIN, GPIO.LOW)
    time.sleep(3)
    print("Pompa 2 OFF")

def serial_listener(GPIO=None):
    global ser
    print("Nasłuchiwanie komend...")
    buffer = b''
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    data   = ser.read(ser.in_waiting)
                    buffer += data
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        try:
                            command = line.decode('utf-8').strip()
                            if command:
                                print(f"Komenda: {command}")
                                process_command(command, GPIO)
                        except UnicodeDecodeError:
                            print(f"Błąd dekodowania: {line}")
            except Exception as e:
                print(f"Błąd Serial: {e} — reconnect za 2s...")
                buffer = b''
                try:
                    ser.close()
                except:
                    pass
                time.sleep(2)
                try:
                    ser = serial.Serial(
                        port=SERIAL_PORT,
                        baudrate=SERIAL_BAUD,
                        timeout=0.1,
                        write_timeout=1.0
                    )
                    ser.setDTR(False)  
                    print("Serial reconnected OK")
                except Exception as e2:
                    print(f"Reconnect failed: {e2}")
        else:
            time.sleep(1)
        time.sleep(0.05)

# ============================================================
# KARUZELA
# ============================================================
def set_step(w1, w2, w3, w4):
    GPIO.output(STEP_IN1, w1)
    GPIO.output(STEP_IN2, w2)
    GPIO.output(STEP_IN3, w3)
    GPIO.output(STEP_IN4, w4)

def _rotate_ticks(target_ticks, direction=1, delay=0.002):
    """
    Obraca karuzelę aż enkoder zliczy target_ticks ticków.
    Po zatrzymaniu sprawdza błąd i wykonuje korektę (max ENCODER_MAX_RETRIES razy).
    Zwraca True jeśli pozycja osiągnięta, False jeśli timeout/błąd.
    """
    global _enc_tick_count

    remaining = target_ticks  # ile ticków jeszcze do przejechania

    for attempt in range(ENCODER_MAX_RETRIES):
        _enc_tick_count = 0  # reset licznika przed każdą próbą
        t0 = time.time()

        # Obracaj dopóki enkoder nie zliczy wymaganej liczby ticków
        while True:
            cur = abs(_enc_tick_count)
            if cur >= remaining:
                break
            if time.time() - t0 > ENCODER_TIMEOUT:
                print(f"[ENC] Timeout przy próbie {attempt+1}! {cur}/{remaining} ticków")
                set_step(0, 0, 0, 0)
                return False
            # Wykonaj jeden krok silnika
            for s in range(len(HALF_STEP_SEQ))[::direction]:
                set_step(*HALF_STEP_SEQ[s])
                time.sleep(delay)

        set_step(0, 0, 0, 0)
        time.sleep(0.05)  # poczekaj aż karuzela się ustabilizuje

        # Sprawdź błąd pozycji
        final = abs(_enc_tick_count)
        done_so_far = (target_ticks - remaining) + final
        error = done_so_far - target_ticks
        print(f"[ENC] Próba {attempt+1}: {done_so_far}/{target_ticks} ticków, błąd={error:+d}")

        if abs(error) <= ENCODER_TOLERANCE:
            print(f"[ENC] OK — pozycja osiągnięta")
            return True

        if error < 0:
            # Za mało — dokręć brakujące ticki
            remaining = target_ticks - done_so_far
            print(f"[ENC] Korekta: brakuje {remaining} ticków")
        else:
            # Za dużo — cofnij nadmiar
            print(f"[ENC] Korekta: cofam o {error} ticków")
            _enc_tick_count = 0
            t0 = time.time()
            while True:
                if abs(_enc_tick_count) >= error:
                    break
                if time.time() - t0 > ENCODER_TIMEOUT:
                    break
                for s in range(len(HALF_STEP_SEQ))[::-direction]:
                    set_step(*HALF_STEP_SEQ[s])
                    time.sleep(delay)
            set_step(0, 0, 0, 0)
            return True

    print(f"[ENC] BŁĄD: nie osiągnięto pozycji po {ENCODER_MAX_RETRIES} próbach!")
    return False

def rotate_carousel(steps, direction=1, delay=0.002):
    """
    Główna funkcja obrotu karuzeli.
    ENCODER_ENABLED=True  → obrót przez ticki enkodera (precyzyjny)
    ENCODER_ENABLED=False → obrót przez kroki silnika (stary tryb backup)
    """
    if ENCODER_ENABLED:
        # Przelicz liczbę kroków na mnożnik pozycji, wyznacz cel w tickach
        multiplier = max(1, round(steps / STEPS_PER_POSITION)) if STEPS_PER_POSITION > 0 else 1
        target_ticks = TICKS_PER_POSITION * multiplier
        _rotate_ticks(target_ticks, direction, delay)
    else:
        # Tryb krokowy — stara logika bez enkodera
        seq_length = len(HALF_STEP_SEQ)
        for _ in range(steps):
            for step in range(seq_length)[::direction]:
                set_step(*HALF_STEP_SEQ[step])
                time.sleep(delay)
        set_step(0, 0, 0, 0)

def move_servo(position):
    servo_pwm.ChangeDutyCycle(position)
    time.sleep(0.5)
    servo_pwm.ChangeDutyCycle(0)

def needle_up():
    print("Podnoszę igłę...")
    move_servo(SERVO_UP)
    state.needle_down = False

def needle_down():
    print("Opuszczam igłę...")
    move_servo(SERVO_DOWN)
    state.needle_down = True

def next_position():
    print(f"Przesuwam z pozycji {state.current_position}...")
    rotate_carousel(STEPS_PER_POSITION, direction=1)
    state.current_position = (state.current_position + 1) % TOTAL_POSITIONS
    print(f"Nowa pozycja: {state.current_position}")

def reject_sample():
    with state.lock:
        if state.is_busy:
            print("[REJECT] System zajęty - odrzut niemożliwy")
            return {"error": "System zajęty"}
        state.is_busy = True
    try:
        original_position = state.current_position
        print(f"\n=== ODRZUT PRÓBKI - z pozycji {original_position} ===")
        steps_to_reject = (REJECT_POSITION - state.current_position) % TOTAL_POSITIONS
        if steps_to_reject > 0:
            print(f"Obracam do pozycji odrzutu ({REJECT_POSITION})...")
            rotate_carousel(steps_to_reject * STEPS_PER_POSITION, direction=1)
            state.current_position = REJECT_POSITION
        else:
            print("Już na pozycji odrzutu.")
        needle_down()
        pump_2_sequence(REJECT_PUMP_TIME)
        needle_up()
        steps_back = (original_position - REJECT_POSITION) % TOTAL_POSITIONS
        if steps_back > 0:
            print(f"Wracam do pozycji {original_position}...")
            rotate_carousel(steps_back * STEPS_PER_POSITION, direction=1)
            state.current_position = original_position
        print("=== ODRZUT ZAKOŃCZONY ===\n")
        return {"success": True, "drained_from": original_position}
    finally:
        state.is_busy = False

def loading_sequence():
    with state.lock:
        if state.is_busy:
            return {"error": "System zajęty"}
        state.is_busy = True
    try:
        print(f"\n=== START SEKWENCJI - Pozycja {state.current_position} ===")
        needle_down()
        pump_2_sequence(PUMP_DURATION)
        needle_up()
        next_position()
        print("=== KONIEC SEKWENCJI ===\n")
        return {"success": True, "position": state.current_position - 1}
    finally:
        state.is_busy = False

# ============================================================
# GŁÓWNA FUNKCJA
# ============================================================
def main():
    """Główna funkcja"""
    print()
    print("=" * 60)
    print("RASPBERRY PI #2 - STACJA POMIAROWA")
    print("Czujniki + Pompa + Serial do Arduino")
    print("=" * 60)
    print()
    
    # Inicjalizacja GPIO
    GPIO = init_gpio()
    
    # Inicjalizacja Serial
    if not init_serial():
        print("Nie można otworzyć Serial. Sprawdź połączenie.")
        return

    # Wątki stacji pomiarowej
    listener_thread = threading.Thread(target=serial_listener, args=(GPIO,), daemon=True)
    listener_thread.start()

    measurement_thread = threading.Thread(target=measurement_loop, args=(GPIO,), daemon=True)
    measurement_thread.start()

    db_manager.init_database()
    db_thread = threading.Thread(target=db_manager.database_worker, daemon=True)
    db_thread.start()

    # Wątki kamery
    if CAM_ENABLED:
        cam_capture_thread = threading.Thread(target=camera_capture_loop, daemon=True)
        cam_capture_thread.start()

        cam_server_thread = threading.Thread(target=camera_server_loop, daemon=True)
        cam_server_thread.start()
    else:
        print("[CAM] Kamera wyłączona (CAM_ENABLED = False)")

    print()
    print("=" * 60)
    print("SYSTEM GOTOWY")
    print("=" * 60)
    print()
    print("Oczekiwanie na komendy z Arduino...")
    print("Komendy: MEASURE:duration, STOP, PUMP_ON, PUMP_OFF, GET_DATA, STATUS,LOADING_SAMPLES,REJECT_SAMPLES")
    print("Ctrl+C aby zakończyć")
    print()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nZatrzymywanie...")

    finally:
        if pump_state and GPIO:
            control_pump_1(False, GPIO)
        if ser and ser.is_open:
            ser.close()
        if GPIO:
            GPIO.cleanup()
        print("Zamknięto")


if __name__ == '__main__':
    main()