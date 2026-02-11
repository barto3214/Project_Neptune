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
  * GET_DATA     - wyślij aktualne dane

- Dane wysyłane (do Arduino):
  * DATA:7.2,350,22.5,700,1\n  (pH,TDS,Temp,Cond,Pump)
  * STATUS:OK,3700,0\n         (Status,BatteryMv,ErrorFlags)

Hardware:
- pH Sensor (I2C lub Analog)
- TDS Sensor (Analog)
- DS18B20 Temperature Sensor (1-Wire)
- Relay Module (GPIO dla pompy)
- Serial do Arduino (UART)
"""

import serial
import time
import threading
import random  # Tymczasowo do symulacji czujników
from datetime import datetime

# Konfiguracja Serial
SERIAL_PORT = '/dev/ttyACM0'  # Arduino przez USB

# SERIAL_PORT = '/dev/serial0'  # UART (GPIO 14/15)
SERIAL_BAUD = 115200

# Konfiguracja GPIO (przykładowe piny)
PUMP_RELAY_PIN = 18  # GPIO 18 dla przekaźnika pompy

# Pomiar
measuring = False
measurement_start_time = 0
measurement_duration = 0
last_measurement = 0
MEASUREMENT_INTERVAL = 2  # Sekund między pomiarami

# Stan pompy
pump_state = False

# Dane czujników
sensor_data = {
    'ph': 7.0,
    'tds': 350.0,
    'temperature': 22.0,
    'conductivity': 700.0
}

# Serial connection
ser = None

def init_gpio():
    """Inicjalizacja GPIO dla pompy"""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PUMP_RELAY_PIN, GPIO.OUT)
        GPIO.output(PUMP_RELAY_PIN, GPIO.LOW)
        print("GPIO zainicjalizowane")
        return GPIO
    except ImportError:
        print("RPi.GPIO nie dostępne (tryb symulacji)")
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
        time.sleep(2)  # Daj Arduino czas na restart
        return True
    except Exception as e:
        print(f"Błąd otwarcia Serial: {e}")
        return False

def read_sensors():
    sensor_data['ph'] = 7.2 + random.uniform(-0.1, 0.1)
    sensor_data['tds'] = 350 + random.uniform(-20, 20)
    sensor_data['temperature'] = 22.5 + random.uniform(-0.5, 0.5)
    sensor_data['conductivity'] = 700 + random.uniform(-50, 50)
    
    # TODO: Prawdziwe czytanie czujników:
    # sensor_data['ph'] = read_ph_sensor()
    # sensor_data['tds'] = read_tds_sensor()
    # sensor_data['temperature'] = read_ds18b20()
    # sensor_data['conductivity'] = sensor_data['tds'] * 2.0

def control_pump(state, GPIO=None):
    """Sterowanie pompą"""
    global pump_state
    pump_state = state
    
    if GPIO:
        GPIO.output(PUMP_RELAY_PIN, GPIO.HIGH if state else GPIO.LOW)
        print(f"Pompa: {'ON' if state else 'OFF'}")
    else:
        print(f"Pompa (symulacja): {'ON' if state else 'OFF'}")

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
    global measuring, measurement_start_time, measurement_duration
    
    command = command.strip().upper()
    
    # DODAJ TE LINIE NA POCZĄTKU:
    # Ignoruj debug logi z Arduino
    if command.startswith("TX DATA") or command.startswith("RX COMMAND") or \
       command.startswith("[DEBUG]") or command.startswith("==="):
        return  # Ignoruj debug output
    
    if command.startswith("MEASURE:"):
        # Format: MEASURE:120 (120 sekund)
        try:
            duration = int(command.split(':')[1])
            measuring = True
            measurement_start_time = time.time()
            measurement_duration = duration
            print(f"START pomiaru przez {duration}s")
        except:
            print(f"Błąd parsowania: {command}")
    
    elif command == "STOP":
        measuring = False
        print("STOP pomiaru")
    
    elif command == "PUMP_ON":
        control_pump(True, GPIO)
    
    elif command == "PUMP_OFF":
        control_pump(False, GPIO)
    
    elif command == "STATUS":
        send_status()
    
    elif command == "GET_DATA":
        if measuring:
            read_sensors()
            send_data()
        # Jesli pomiar nieaktywny - ignoruj GET_DATA
    
    else:
        print(f"Nieznana komenda: {command}")

def send_stop_to_arduino():
    """Wyslij STOP do Arduino - zatrzymaj autoMode"""
    if ser and ser.is_open:
        try:
            ser.write(b"MEASUREMENT_DONE\n")
            ser.flush()
            print("Wyslano MEASUREMENT_DONE do Arduino")
        except Exception as e:
            print(f"Blad wysylania STOP: {e}")
            
            
def measurement_loop(GPIO=None):
    """Pętla pomiaru - wykonuje pomiary gdy measuring=True"""
    global last_measurement,measuring
    
    while True:
        if measuring:
            # Sprawdź czy minął czas pomiaru
            elapsed = time.time() - measurement_start_time
            if elapsed >= measurement_duration:
                print(f"Koniec pomiaru ({measurement_duration}s)")
                measuring = False
                continue
            
            # Wykonaj pomiar co MEASUREMENT_INTERVAL sekund
            if time.time() - last_measurement >= MEASUREMENT_INTERVAL:
                print(f"Pomiar ({elapsed:.0f}/{measurement_duration}s)...")
                read_sensors()
                send_data()
                last_measurement = time.time()
        
        time.sleep(0.1)

def serial_listener(GPIO=None):
    """Nasłuchiwanie komend z Arduino"""
    print("Nasłuchiwanie komend...")
    
    buffer = b''
    
    while True:
        if ser and ser.is_open:
            try:
                # Czytaj dane
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
    
    try:
        # Główna pętla (keep alive)
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nZatrzymywanie...")
    
    finally:
        # Cleanup
        if pump_state and GPIO:
            control_pump(False, GPIO)
        
        if ser and ser.is_open:
            ser.close()
        
        if GPIO:
            GPIO.cleanup()
        
        print("Zamknięto")

if __name__ == '__main__':
    main()