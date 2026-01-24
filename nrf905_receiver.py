#!/usr/bin/env python3
"""
NRF905 Receiver - Raspberry Pi (Stacja Bazowa)
WERSJA Z PEŁNĄ DIAGNOSTYKĄ
"""

import spidev
import RPi.GPIO as GPIO
import time
import struct
import socket
import threading
import json
from datetime import datetime

# Konfiguracja GPIO
GPIO_CE = 17      # PIN 11
GPIO_TX_EN = 27   # PIN 13
GPIO_DR = 22      # PIN 15 - Data Ready (NOWY!)
GPIO_PWR = 23     # PIN 16 - Power control (opcjonalnie)

# Konfiguracja TCP
TCP_HOST = '0.0.0.0'
TCP_PORT = 5000

# NRF905 Commands
CMD_W_CONFIG = 0x00
CMD_R_CONFIG = 0x10
CMD_W_TX_PAYLOAD = 0x20
CMD_R_TX_PAYLOAD = 0x21
CMD_W_TX_ADDRESS = 0x22
CMD_R_TX_ADDRESS = 0x23
CMD_R_RX_PAYLOAD = 0x24
CMD_CHANNEL_CONFIG = 0x80

class SensorData:
    """Struktura danych z czujników (zgodna z Arduino)"""
    FORMAT = '<BffffIHB7sB'  # Little-endian, 32 bytes total
    SIZE = 32
    
    def __init__(self, raw_data=None):
        self.station_id = 0
        self.ph = 0.0
        self.tds = 0.0
        self.temperature = 0.0
        self.conductivity = 0.0
        self.timestamp = 0
        self.battery_voltage = 0
        self.error_flags = 0
        self.reserved = b'\x00' * 7
        self.crc = 0
        
        if raw_data and len(raw_data) >= self.SIZE:
            self.parse(raw_data)
    
    def parse(self, data):
        """Parsuj surowe dane z NRF905"""
        try:
            unpacked = struct.unpack(self.FORMAT, data[:self.SIZE])
            self.station_id = unpacked[0]
            self.ph = unpacked[1]
            self.tds = unpacked[2]
            self.temperature = unpacked[3]
            self.conductivity = unpacked[4]
            self.timestamp = unpacked[5]
            self.battery_voltage = unpacked[6]
            self.error_flags = unpacked[7]
            self.reserved = unpacked[8]
            self.crc = unpacked[9]
            return True
        except struct.error as e:
            print(f"Błąd parsowania: {e}")
            print(f"Długość: {len(data)}, Format wymaga: {struct.calcsize(self.FORMAT)}")
            return False
    
    def verify_crc(self, data):
        """Sprawdź sumę kontrolną"""
        if not hasattr(self, 'crc'):
            return False
        calculated_crc = self.calculate_crc(data[:-1])
        is_valid = calculated_crc == self.crc
        if not is_valid:
            print(f"CRC mismatch: calculated=0x{calculated_crc:02X}, received=0x{self.crc:02X}")
        return is_valid
    
    @staticmethod
    def calculate_crc(data):
        """Oblicz CRC (zgodnie z algorytmem Arduino)"""
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x31) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc
    
    def to_dict(self):
        """Konwertuj do słownika JSON"""
        return {
            'station_id': self.station_id,
            'ph': round(self.ph, 2),
            'tds': round(self.tds, 1),
            'temperature': round(self.temperature, 1),
            'conductivity': round(self.conductivity, 0),
            'timestamp': self.timestamp,
            'battery_voltage': self.battery_voltage / 1000.0,
            'error_flags': self.error_flags,
            'received_at': datetime.now().isoformat()
        }
    
    def __str__(self):
        return (f"Station {self.station_id}: pH={self.ph:.2f}, "
                f"TDS={self.tds:.1f}ppm, Temp={self.temperature:.1f}°C, "
                f"Cond={self.conductivity:.0f}µS/cm, Bat={self.battery_voltage/1000:.2f}V, "
                f"CRC=0x{self.crc:02X}")


class NRF905Receiver:
    """Odbiornik NRF905 dla Raspberry Pi"""
    
    def __init__(self):
        print("=" * 50)
        print("NRF905 RECEIVER - DIAGNOSTYKA")
        print("=" * 50)
        print()
        
        # Inicjalizacja SPI
        print("1. Inicjalizacja SPI...")
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 200000  # ZMIENIONE: 200kHz jak w działającym przykładzie
        self.spi.mode = 0
        print("   [OK] SPI zainicjalizowany (200 kHz)")
        
        # Inicjalizacja GPIO
        print("2. Konfiguracja GPIO...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(GPIO_CE, GPIO.OUT)
        GPIO.setup(GPIO_TX_EN, GPIO.OUT)
        GPIO.setup(GPIO_DR, GPIO.IN)
        
        # Opcjonalnie: kontrola zasilania
        try:
            GPIO.setup(GPIO_PWR, GPIO.OUT)
            GPIO.output(GPIO_PWR, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(GPIO_PWR, GPIO.HIGH)
            print("   [OK] Zasilanie NRF905 włączone")
        except:
            print("   [INFO] Brak kontroli zasilania (pin PWR nie używany)")
        
        GPIO.output(GPIO_CE, GPIO.LOW)
        GPIO.output(GPIO_TX_EN, GPIO.LOW)
        
        time.sleep(0.2)  # Zwiększone opóźnienie
        print("   [OK] GPIO skonfigurowane")
        
        # TEST 1: Komunikacja SPI
        print("3. Test komunikacji SPI...")
        if self.test_spi_communication():
            print("   [OK] Komunikacja SPI działa")
        else:
            print("   [BŁĄD] Brak komunikacji SPI!")
            print("   Sprawdź połączenia: MOSI, MISO, SCK, CE0")
            raise Exception("SPI communication failed")
        
        # Inicjalizacja NRF905
        print("4. Konfiguracja NRF905...")
        self.init_nrf905()
        print("   [OK] NRF905 skonfigurowany")
        
        # TEST 2: Weryfikacja konfiguracji
        print("5. Weryfikacja konfiguracji...")
        self.verify_configuration()
        
        # TEST 3: Status pinów
        print("6. Test pinów statusu...")
        self.test_status_pins()
        
        print()
        print("=" * 50)
        print("SYSTEM GOTOWY - Tryb RX aktywny")
        print(f"Rozmiar pakietu: {SensorData.SIZE} bajtów")
        print("=" * 50)
        print()
        
        # Statystyki
        self.rx_count = 0
        self.rx_success_count = 0
        self.rx_crc_fail_count = 0
        self.rx_empty_count = 0
    
    def test_spi_communication(self):
        """Test komunikacji SPI z NRF905"""
        try:
            # Próba odczytu rejestru konfiguracji
            cmd = [CMD_R_CONFIG, 0x00, 0x00]
            result = self.spi.xfer2(cmd)
            
            # Sprawdź czy otrzymaliśmy sensowne dane
            if (result[1] == 0x00 and result[2] == 0x00) or \
               (result[1] == 0xFF and result[2] == 0xFF):
                print(f"   Odczytano: 0x{result[1]:02X} 0x{result[2]:02X}")
                return False
            
            return True
        except Exception as e:
            print(f"   Błąd SPI: {e}")
            return False
    
    def init_nrf905(self):
        """Konfiguracja NRF905 w trybie odbiornika - ULEPSZONA WERSJA"""
        # Upewnij się że jesteśmy w trybie standby
        GPIO.output(GPIO_CE, GPIO.LOW)
        GPIO.output(GPIO_TX_EN, GPIO.LOW)
        time.sleep(0.05)
        
        # Konfiguracja - UPROSZCZONA jak w działającym przykładzie
        # Format: [CMD, CH, Mode, Addr_width, RX_PW, TX_PW, RX_ADDR(4), Config]
        config = [
            CMD_W_CONFIG,
            108,   # Channel 108 (433.2 MHz) - bezpośrednia wartość
            0x0C,  # 433MHz, 10dBm
            0x44,  # 4-byte addresses (TX i RX)
            32,    # RX payload width (tylko LOW byte)
            32,    # TX payload width (tylko LOW byte)  
            0xE7,  # RX address byte 0
            0xE7,  # RX address byte 1
            0xE7,  # RX address byte 2
            0xE7,  # RX address byte 3
            0xDB   # CRC enabled, 16-bit CRC
        ]
        
        self.spi.xfer2(config)
        time.sleep(0.05)  # Dłuższe opóźnienie
        
        # Ustaw adres TX (taki sam jak RX dla komunikacji dwukierunkowej)
        tx_addr_cmd = [CMD_W_TX_ADDRESS, 0xE7, 0xE7, 0xE7, 0xE7]
        self.spi.xfer2(tx_addr_cmd)
        time.sleep(0.05)
        
        # WAŻNE: Wyczyść bufor odbioru przed rozpoczęciem
        print("   Czyszczenie bufora RX...")
        for _ in range(10):
            self.spi.xfer2([CMD_R_RX_PAYLOAD] + [0x00] * SensorData.SIZE)
            time.sleep(0.01)
        
        # Włącz tryb RX
        GPIO.output(GPIO_TX_EN, GPIO.LOW)  # RX mode (TX_EN = LOW)
        time.sleep(0.02)
        GPIO.output(GPIO_CE, GPIO.HIGH)    # Enable chip
        time.sleep(0.01)
    
    def verify_configuration(self):
        """Weryfikacja konfiguracji NRF905"""
        cmd = [CMD_R_CONFIG] + [0x00] * 11  # Odczytaj 11 bajtów konfiguracji
        result = self.spi.xfer2(cmd)
        config = result[1:12]
        
        print(f"   Odczyt konfiguracji:")
        print(f"   CH: {config[0]} (0x{config[0]:02X})  Mode: 0x{config[1]:02X}  Addr: 0x{config[2]:02X}")
        print(f"   RX_PW: {config[3]}  TX_PW: {config[4]}")
        print(f"   RX_ADDR: " + " ".join([f"0x{b:02X}" for b in config[5:9]]))
        print(f"   Config: 0x{config[9]:02X}")
        
        # Weryfikacja wartości
        config_ok = True
        if config[0] != 108:  # Kanał
            print(f"   [WARN] Nieprawidłowy kanał! Oczekiwano 108, otrzymano {config[0]}")
            config_ok = False
        if config[3] != 32 or config[4] != 32:  # Payload width
            print(f"   [WARN] Nieprawidłowa szerokość payload! RX={config[3]}, TX={config[4]}")
            config_ok = False
        if config[5:9] != [0xE7, 0xE7, 0xE7, 0xE7]:  # RX Address
            print(f"   [WARN] Nieprawidłowy adres RX!")
            config_ok = False
        
        if config_ok:
            print("   [OK] Konfiguracja poprawna")
        
        # Sprawdź TX Address
        tx_addr_cmd = [CMD_R_TX_ADDRESS] + [0x00] * 4
        tx_result = self.spi.xfer2(tx_addr_cmd)
        tx_addr = tx_result[1:5]
        print(f"   TX_ADDR: " + " ".join([f"0x{b:02X}" for b in tx_addr]))
        
        return config_ok
    
    def test_status_pins(self):
        """Test pinów statusu"""
        dr_state = GPIO.input(GPIO_DR)
        print(f"   DR (Data Ready): {'HIGH' if dr_state else 'LOW'}")
        print(f"   [INFO] DR powinien być LOW bez odebranych danych")
    
    def receive_data(self):
        """Odbierz pakiet danych z diagnostyką"""
        try:
            # Sprawdź pin DR (Data Ready)
            dr_state = GPIO.input(GPIO_DR)
            
            # Zawsze próbuj odczytać (dla testów)
            cmd = [CMD_R_RX_PAYLOAD] + [0x00] * SensorData.SIZE
            result = self.spi.xfer2(cmd)
            data = bytes(result[1:SensorData.SIZE + 1])
            
            # Sprawdź czy dane nie są puste (same 0x00 lub 0xFF)
            if all(b == 0x00 for b in data) or all(b == 0xFF for b in data):
                self.rx_empty_count += 1
                if self.rx_empty_count % 100 == 0:  # Log co 100 pustych odczytów
                    print(f"[DEBUG] {self.rx_empty_count} pustych odczytów")
                return None
            
            self.rx_count += 1
            
            # Wyświetl surowe dane (pierwsze 16 bajtów)
            if self.rx_count <= 5:  # Tylko dla pierwszych pakietów
                hex_data = " ".join([f"{b:02X}" for b in data[:16]])
                print(f"[DEBUG] Surowe dane (16B): {hex_data}...")
            
            sensor_data = SensorData(data)
            
            # Weryfikacja CRC
            if sensor_data.verify_crc(data):
                self.rx_success_count += 1
                return sensor_data
            else:
                self.rx_crc_fail_count += 1
                print(f"[WARN] Pakiet #{self.rx_count}: CRC nieprawidłowe")
                return None
                
        except Exception as e:
            print(f"Błąd odbierania: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_statistics(self):
        """Zwróć statystyki odbioru"""
        return {
            'rx_total': self.rx_count,
            'rx_success': self.rx_success_count,
            'rx_crc_fail': self.rx_crc_fail_count,
            'rx_empty': self.rx_empty_count,
            'success_rate': (self.rx_success_count * 100 / self.rx_count) if self.rx_count > 0 else 0
        }
    
    def close(self):
        """Zamknij połączenia"""
        GPIO.output(GPIO_CE, GPIO.LOW)
        self.spi.close()
        GPIO.cleanup()


class TCPServer:
    """Serwer TCP udostępniający dane dla aplikacji WPF"""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = []
        self.latest_data = None
        self.running = False
        self.server_socket = None
    
    def start(self):
        """Uruchom serwer TCP"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Serwer TCP nasłuchuje na {self.host}:{self.port}")
        
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()
    
    def accept_connections(self):
        """Akceptuj nowe połączenia klientów"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"Nowy klient: {address}")
                self.clients.append(client_socket)
                
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Błąd akceptowania połączenia: {e}")
    
    def handle_client(self, client_socket):
        """Obsługa komunikacji z klientem"""
        try:
            while self.running:
                time.sleep(0.1)
        except Exception as e:
            print(f"Błąd komunikacji z klientem: {e}")
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            client_socket.close()
    
    def broadcast_data(self, sensor_data):
        """Wyślij dane do wszystkich klientów"""
        if sensor_data:
            self.latest_data = sensor_data
            json_data = json.dumps(sensor_data.to_dict()) + '\n'
            
            disconnected = []
            for client in self.clients:
                try:
                    client.sendall(json_data.encode('utf-8'))
                except Exception as e:
                    disconnected.append(client)
            
            for client in disconnected:
                if client in self.clients:
                    self.clients.remove(client)
                client.close()
    
    def stop(self):
        """Zatrzymaj serwer"""
        self.running = False
        for client in self.clients:
            client.close()
        if self.server_socket:
            self.server_socket.close()


def main():
    """Główna pętla programu"""
    print()
    print("=" * 50)
    print("NRF905 Receiver - Stacja Bazowa")
    print("Raspberry Pi + NRF905 -> TCP Server")
    print("=" * 50)
    print()
    
    try:
        receiver = NRF905Receiver()
    except Exception as e:
        print(f"\n[BŁĄD] Nie udało się zainicjalizować NRF905: {e}")
        print("Sprawdź połączenia i spróbuj ponownie.")
        return
    
    tcp_server = TCPServer(TCP_HOST, TCP_PORT)
    tcp_server.start()
    
    print()
    print("System gotowy. Oczekiwanie na dane...")
    print("Aby zakończyć, naciśnij Ctrl+C")
    print()
    
    last_stats_time = time.time()
    
    try:
        while True:
            sensor_data = receiver.receive_data()
            
            if sensor_data and sensor_data.station_id > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {sensor_data}")
                tcp_server.broadcast_data(sensor_data)
            
            # Wyświetl statystyki co 10 sekund
            if time.time() - last_stats_time >= 10:
                stats = receiver.get_statistics()
                print(f"\n[STATS] Pakiety: {stats['rx_total']}, "
                      f"OK: {stats['rx_success']}, "
                      f"CRC fail: {stats['rx_crc_fail']}, "
                      f"Puste: {stats['rx_empty']}, "
                      f"Success: {stats['success_rate']:.1f}%\n")
                last_stats_time = time.time()
            
            time.sleep(0.05)  # Zmniejszone opóźnienie dla lepszej responsywności
            
    except KeyboardInterrupt:
        print("\nZatrzymywanie...")
    finally:
        stats = receiver.get_statistics()
        receiver.close()
        tcp_server.stop()
        print(f"\nZamknięto.")
        print(f"Statystyki końcowe:")
        print(f"  Pakiety otrzymane: {stats['rx_total']}")
        print(f"  Poprawne: {stats['rx_success']}")
        print(f"  Błędy CRC: {stats['rx_crc_fail']}")
        print(f"  Puste odczyty: {stats['rx_empty']}")
        print(f"  Sukces: {stats['success_rate']:.1f}%")


if __name__ == '__main__':
    main()