#!/usr/bin/env python3
"""
RASPBERRY PI #2 - STACJA POMIAROWA (Remote Station)
Funkcje:
1. Odbiera komendy z Arduino przez Serial
2. Czyta czujniki (pH, TDS, Temp, Conductivity)
3. Steruje pompą (relay)
4. Wysyła dane do Arduino przez Serial

Komunikacja Serial z Arduino:
- Komendy otrzymywane (z Arduino):
  * MEASURE:120  - rozpocznij pomiar przez 120 sekund
  * STOP         - zatrzymaj pomiar
  * PUMP_ON      - włącz pompę
  * PUMP_OFF     - wyłącz pompę
  * STATUS       - wyślij status
  * SAMPLES_LOADING - wykonaj sekwencję ładowania próbek
  * GET_DATA     - wyślij aktualne dane

- Dane wysyłane (do Arduino):
  * DATA:7.2,350,22.5,700,1\n  (pH,TDS,Temp,Cond,Pump)
  * STATUS:OK,3700,0\n         (Status,BatteryMv,ErrorFlags)
"""

import serial
import time
import threading
from datetime import datetime
import glob
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
PUMP_DURATION = 5.0     # Czas pracy pompy w sekundach do załadunku probówki TODO: USTAWIĆ REALNY
REJECT_POSITION = 0    # Pozycja karuzeli do odrzutu 
REJECT_PUMP_TIME = 8.0  # Czas pracy pompy przy odrzucaniu próbki (dłużej niż normalny załadunek) TODO: USTAWIĆ REALNY
PUMP_1_MAX_TIME = 30.0  # Maksymalny czas pracy pompy 1 (safety cutoff)TODO: USTAWIĆ REALNY

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
STEPS_PER_POSITION = 44  # Liczba kroków do przesunięcia o jedną pozycję TODO: USTAWIĆ REALNY

# Pozycje servo (dostosuj według potrzeb!)
SERVO_UP = 6.0    # Duty cycle % dla pozycji górnej (ok. 90°)TODO: USTAWIĆ REALNY
SERVO_DOWN = 12.5  # Duty cycle % dla pozycji dolnej (ok. 180°)TODO: USTAWIĆ REALNY

# === INICJALIZACJA GPIO ===
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Silnik krokowy
GPIO.setup(STEP_IN1, GPIO.OUT)
GPIO.setup(STEP_IN2, GPIO.OUT)
GPIO.setup(STEP_IN3, GPIO.OUT)
GPIO.setup(STEP_IN4, GPIO.OUT)

# Servo
GPIO.setup(SERVO_PIN, GPIO.OUT)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz
servo_pwm.start(0)

# === SEKWENCJA KROKÓW SILNIKA (Half-step) ===
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

# Stan pompy
pump_state = False

# Serial connection
ser = None

sensor_data = {          
    'ph': 0.0,
    'tds': 0.0,
    'temperature': 0.0,
    'conductivity': 0.0,
}

# === STAN SYSTEMU KARUZELI ===
class CarouselState:
    def __init__(self):
        self.current_position = 0
        self.is_busy = False
        self.lock = threading.Lock()
        self.needle_down = False
    
    def get_status(self):
        return {
            "position": self.current_position,
            "busy": self.is_busy,
            "needle_down": self.needle_down
        }

state = CarouselState()

@dataclass
class SensorData:
    ph: float
    tds: float
    temperature: float
    conductivity: float
    
    
    def voltage_to_ph(voltage):
        return slope_ph * voltage + offset_ph

    def read_ph_avg(samples=20):
        """Pobierz 20 próbek, odrzuć 20% skrajnych, uśrednij resztę"""
        readings = []
        for _ in range(samples):
            readings.append(SensorData.voltage_to_ph(chan_ph.voltage))
            time.sleep(0.05)
        readings.sort()
        # Odrzuć 20% z góry i z dołu (po 4 wartości)
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
            # print(f"Znaleziono czujnik temp: {devices[0].split('/')[-1]}")
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
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.2)
        return None

    # === TDS DFRobot ===
    def voltage_to_tds(voltage, temperature=25.0):
        compensation_coeff = 1.0 + 0.02 * (temperature - 25.0)
        voltage_comp = voltage / compensation_coeff
        tds = (133.42 * voltage_comp**3
             - 255.86 * voltage_comp**2
             + 857.39 * voltage_comp) * 0.5
        return max(0, tds)
    
def init_gpio():
    """Inicjalizacja GPIO dla pompy"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.set (PUMP_1_RELAY_PIN, GPIO.OUT)
        GPIO.output(PUMP_1_RELAY_PIN, GPIO.LOW)
        GPIO.setup(PUMP_2_RELAY_PIN, GPIO.OUT)
        GPIO.output(PUMP_2_RELAY_PIN, GPIO.LOW)
        print("GPIO zainicjalizowane")
        return GPIO
    except ImportError:
        print("RPi.GPIO nie dostępne")
        return None

def init_serial():
    """Inicjalizacja połączenia Serial z Arduino"""
    global ser
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUD,
            timeout=0.1,
            write_timeout=1.0
        )
        print(f"Serial otwarty: {SERIAL_PORT} @ {SERIAL_BAUD}")
        time.sleep(2)  
        return True
    except Exception as e:
        print(f"Błąd otwarcia Serial: {e}")
        return False

def read_sensors():
    temp = SensorData.read_temp()
    sensor_data['ph']           = SensorData.read_ph_avg()
    sensor_data['temperature']  = temp
    sensor_data['conductivity'] = SensorData.read_ec_avg()
    sensor_data['tds']          = SensorData.voltage_to_tds(
                                      chan_tds.voltage,
                                      temp if temp is not None else 25.0
                                  )
    db_manager.add_measurement(
    time.time(),
    round(sensor_data['ph'], 2),
    round(sensor_data['tds'], 2),
    round(sensor_data['temperature'], 2),
    round(sensor_data['conductivity'], 2)
    )

def control_pump_1(active, GPIO=None):
    """Sterowanie pompą 1 z zabezpieczeniem czasowym"""
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
    """Wyślij dane do Arduino"""
    if ser and ser.is_open:
        data_str = f"DATA:{sensor_data['ph']:.2f},{sensor_data['tds']:.1f}," \
                   f"{sensor_data['temperature']:.1f},{sensor_data['conductivity']:.1f}," \
                   f"{1 if pump_state else 0}\n"
        
        try:
            ser.write(data_str.encode('utf-8'))
            ser.flush()
            print(f"Wysłano: {data_str.strip()}")
        except Exception as e:
            print(f"Błąd wysyłania: {e}")

def send_status():
    """Wyślij status systemu"""
    if ser and ser.is_open:
        battery_mv = 3700  # TODO: Odczyt napięcia baterii
        error_flags = 0
        status_str = f"STATUS:OK,{battery_mv},{error_flags}\n"
        
        try:
            ser.write(status_str.encode('utf-8'))
            print(f"Status: {status_str.strip()}")
        except Exception as e:
            print(f"Błąd wysyłania statusu: {e}")

def process_command(command, GPIO=None):
    """Przetwórz komendę z Arduino"""
    global measuring, measurement_start_time, measurement_duration, last_measure_time
    
    command = command.strip().upper()
    
    # Ignoruj debug logi i komunikaty startowe z Arduino
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
            
            # DEBOUNCING - ignoruj jeśli ostatnia komenda <3s temu
            if time.time() - last_measure_time < 3:
                return  
            
            last_measure_time = time.time()
            measuring = True
            measurement_start_time = time.time()
            measurement_duration = duration
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
            # print(f"Dane: {sensor_data}")  ← debug
            # print("Czytam czujniki...")   
            send_data()
    #     else:
    #         print("GET_DATA zignorowane - pomiar nieaktywny")  # ← debug
    
    else:
        print(f"Nieznana komenda: {command}")

def send_stop_to_arduino():
    """Wyslij STOP do Arduino - zatrzymaj autoMode"""
    if ser and ser.is_open:
        try:
            ser.write(b"MEASUREMENT_DONE\n")
            ser.flush()
            time.sleep(0.5)  # ← DODAJ - daj Arduino czas na odczyt
            print("Wyslano MEASUREMENT_DONE do Arduino")
        except Exception as e:
            print(f"Blad wysylania STOP: {e}")
            
            
def measurement_loop(GPIO=None):
    """Pętla pomiaru - wykonuje pomiary gdy measuring=True"""
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
    print("Pompa 2   ON")
    time.sleep(duration)
    GPIO.output(PUMP_2_RELAY_PIN, GPIO.LOW)
    print("Pompa 2 OFF")
        
def serial_listener(GPIO=None):
    """Nasłuchiwanie komend z Arduino"""
    print("Nasłuchiwanie komend...")
    
    buffer = b''
    
    while True:
        if ser and ser.is_open:
            try:
                
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    buffer += data
                    
                    # Przetwarzaj kompletne linie
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
                print(f"Błąd odczytu Serial: {e}")
                time.sleep(1)
        
        time.sleep(0.05)
        
# === FUNKCJE KARUZELI ===
def set_step(w1, w2, w3, w4):
    """Ustaw stan pinów silnika krokowego"""
    GPIO.output(STEP_IN1, w1)
    GPIO.output(STEP_IN2, w2)
    GPIO.output(STEP_IN3, w3)
    GPIO.output(STEP_IN4, w4)

def rotate_carousel(steps, direction=1, delay=0.002):
    """
    Obróć karuzelę o określoną liczbę kroków
    direction: 1 = do przodu, -1 = do tyłu
    """
    seq_length = len(HALF_STEP_SEQ)
    for _ in range(steps):
        for step in range(seq_length)[::direction]:
            set_step(*HALF_STEP_SEQ[step])
            time.sleep(delay)
    # Wyłącz cewki po obrocie
    set_step(0, 0, 0, 0)

def move_servo(position):
    """Przesuń servo do pozycji (duty cycle %)"""
    servo_pwm.ChangeDutyCycle(position)
    time.sleep(0.5)  # Poczekaj na ruch servo
    servo_pwm.ChangeDutyCycle(0)  # Zatrzymaj sygnał PWM

def needle_up():
    """Podnieś igłę"""
    print("Podnoszę igłę...")
    move_servo(SERVO_UP)
    state.needle_down = False

def needle_down():
    """Opuść igłę"""
    print("Opuszczam igłę...")
    move_servo(SERVO_DOWN)
    state.needle_down = True

def next_position():
    """Przesuń karuzelę do następnej pozycji"""
    print(f"Przesuwam z pozycji {state.current_position}...")
    rotate_carousel(STEPS_PER_POSITION, direction=1)
    state.current_position = (state.current_position + 1) % TOTAL_POSITIONS
    print(f"Nowa pozycja: {state.current_position}")

def reject_sample():
    """
    Odrzuć próbkę:
    1. Obróć karuzelę do pozycji odrzutu (pozycja 0 = zlew)
    2. Opuść igłę
    3. Włącz pompę na REJECT_PUMP_TIME sekund
    4. Podnieś igłę
    5. Wróć do poprzedniej pozycji
    """
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

        # Wróć do oryginalnej pozycji
        steps_back = (original_position - REJECT_POSITION) % TOTAL_POSITIONS
        if steps_back > 0:
            print(f"Wracam do pozycji {original_position}...")
            rotate_carousel(steps_back * STEPS_PER_POSITION, direction=1)
            state.current_position = original_position

        print("=== ODRZUT ZAKOŃCZONY ===\n")
        return {"success": True, "drained_from": original_position}

    finally:
        state.is_busy = False
        
# === SEKWENCJA ZAŁADUNKU ===
def loading_sequence():
    """
    Główna sekwencja pomiaru: 
    1. Igła w dół
    2. Pompowanie
    3. Igła w górę
    4. Następna pozycja
    """
    with state.lock:
        if state.is_busy:
            return {"error": "System zajęty"}
        state.is_busy = True
    
    try:
        print(f"\n=== START SEKWENCJI - Pozycja {state.current_position} ===")
        
        # 1. Igła w dół
        needle_down()
        
        # 2. Pompowanie 
        pump_2_sequence(PUMP_DURATION)
        
        # 3. Igła w górę
        needle_up()
        
        # 4. Następna pozycja
        next_position()
        
        print("=== KONIEC SEKWENCJI ===\n")
        
        return {
            "success": True,
            "position": state.current_position - 1,  # Pozycja przed przesunięciem
        
        }
    
    finally:
        state.is_busy = False
        
# === GŁÓWNA FUNKCJA ===

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
    
    print()
    print("=" * 60)
    print("SYSTEM GOTOWY")
    print("=" * 60)
    print()
    print("Oczekiwanie na komendy z Arduino...")
    print("Komendy: MEASURE:duration, STOP, PUMP_ON, PUMP_OFF, GET_DATA, STATUS")
    print("Ctrl+C aby zakończyć")
    print()
    
    # Uruchom wątki
    listener_thread = threading.Thread(target=serial_listener, args=(GPIO,))
    listener_thread.daemon = True
    listener_thread.start()
    
    measurement_thread = threading.Thread(target=measurement_loop, args=(GPIO,))
    measurement_thread.daemon = True
    measurement_thread.start()
    
    db_manager.init_database() 
    db_thread = threading.Thread(target=db_manager.database_worker)
    db_thread.daemon = True
    db_thread.start()
    
    try:
        # Główna pętla (keep alive)
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nZatrzymywanie...")
    
    finally:
        # Cleanup
        if pump_state and GPIO:
            control_pump_1(False, GPIO)
        
        if ser and ser.is_open:
            ser.close()
        
        if GPIO:
            GPIO.cleanup()
        
        print("Zamknięto")

if __name__ == '__main__':
    main()