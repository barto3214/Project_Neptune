#!/usr/bin/env python3
"""
NRF905 TRANSCEIVER - Raspberry Pi #1 (Stacja Bazowa)
HALF DUPLEX: Odbiera dane + Wysyła komendy

Funkcje:
1. TCP Server (port 5000) - komunikacja z WPF
2. NRF905 RX - odbieranie danych z Arduino
3. NRF905 TX - wysyłanie komend do Arduino
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
GPIO_DR = 22      # PIN 15 - Data Ready
GPIO_PWR = 23     # PIN 16 - Power control

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

# Command codes (wysyłane do Arduino)
CMD_MEASURE_START   = 0x01  # Rozpocznij pomiar
CMD_MEASURE_STOP    = 0x02  # Zatrzymaj pomiar
CMD_PUMP_ON         = 0x03  # Włącz pompę 1 (napełnianie zbiornika)
CMD_PUMP_OFF        = 0x04  # Wyłącz pompę 1
CMD_STATUS_REQUEST  = 0x05  # Zapytaj o status
CMD_SAMPLES_LOADING = 0x06  # Sekwencja ładowania próbki (pompa 2)
CMD_REJECT_SAMPLE   = 0x07  # Odrzut próbki (pompa 2)
CMD_BOAT_DRIVE      = 0x20  # Napęd łódki: param1=lewy(0-200), param2=prawy(0-200)

# Packet types (odbierane z Arduino)
PACKET_DATA = 0x10        # Dane z czujników
PACKET_STATUS = 0x11      # Status systemu

class CommandPacket:
    """Pakiet komendy (32 bajty)"""
    SIZE = 32
    
    def __init__(self, command, param1=0, param2=0):
        self.command = command
        self.param1 = param1  # np. duration w sekundach
        self.param2 = param2
        self.timestamp = int(time.time())
    
    def to_bytes(self):
        """Konwertuj do 32 bajtów"""
        data = bytearray(self.SIZE)
        data[0] = self.command
        struct.pack_into('<H', data, 1, self.param1)  # 2 bajty
        struct.pack_into('<H', data, 3, self.param2)  # 2 bajty
        struct.pack_into('<I', data, 5, self.timestamp)  # 4 bajty
        
        # CRC (ostatni bajt(sprawdzający))
        data[31] = self.calculate_crc(data[:31])
        return bytes(data)
    
    @staticmethod
    def calculate_crc(data):
        """CRC zgodne z Arduino"""
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x31) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

class SensorData:
    """Struktura danych z czujników (zgodna z Arduino)"""
    FORMAT = '<BffffIHB7sB'  # 32 bajty
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
        """Parsuj surowe dane"""
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
            return False
    
    def verify_crc(self, data):
        """Sprawdź CRC"""
        calculated_crc = CommandPacket.calculate_crc(data[:-1])
        return calculated_crc == self.crc
    
    def to_dict(self):
        """Konwertuj do JSON"""
        return {
        'station_id':      self.station_id,
        'ph':              round(self.ph, 2),
        'tds':             round(self.tds, 1),
        'temperature':     round(self.temperature, 1),
        'conductivity':    round(self.conductivity, 0),
        'timestamp':       self.timestamp,
        'battery_voltage': self.battery_voltage / 1000.0,
        'pump_state':      bool(self.error_flags & 0x01),
        'packet_type':     'battery' if self.reserved[0] == 0x11 else 'data', 
        'received_at':     datetime.now().isoformat()
        }
    
    def __str__(self):
        return (f"ID{self.station_id}: pH={self.ph:.2f}, TDS={self.tds:.1f}ppm, "
                f"Temp={self.temperature:.1f}°C, Cond={self.conductivity:.0f}µS/cm")


class NRF905Transceiver:
    """Half Duplex NRF905 - RX i TX"""
    
    def __init__(self):
        print("=" * 60)
        print("NRF905 TRANSCEIVER - HALF DUPLEX")
        print("=" * 60)
        print()
        
        # Inicjalizacja SPI
        print("1. Inicjalizacja SPI...")
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 200000  # 200kHz
        self.spi.mode = 0
        print("   [OK] SPI zainicjalizowany")
        
        # Inicjalizacja GPIO
        print("2. Konfiguracja GPIO...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(GPIO_CE, GPIO.OUT)
        GPIO.setup(GPIO_TX_EN, GPIO.OUT)
        GPIO.setup(GPIO_DR, GPIO.IN)
        GPIO.setup(GPIO_PWR, GPIO.OUT)
        
        # Power up NRF905
        GPIO.output(GPIO_PWR, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(GPIO_PWR, GPIO.HIGH)
        time.sleep(0.2)
        print("   [OK] GPIO skonfigurowane, NRF905 zasilone")
        
        # Standby mode
        GPIO.output(GPIO_CE, GPIO.LOW)
        GPIO.output(GPIO_TX_EN, GPIO.LOW)
        time.sleep(0.1)
        
        # Test SPI
        print("3. Test komunikacji SPI...")
        if not self.test_spi():
            raise Exception("Błąd komunikacji SPI!")
        print("   [OK] Komunikacja SPI działa")
        
        # Konfiguracja
        print("4. Konfiguracja NRF905...")
        self.config_nrf905()
        print("   [OK] NRF905 skonfigurowany")
        
        # Tryb RX domyślnie
        self.enter_rx_mode()
        print("   [OK] Tryb RX aktywny")
        
        print()
        print("=" * 60)
        print("SYSTEM GOTOWY")
        print("=" * 60)
        print()
        
        # Statystyki
        self.rx_count = 0
        self.tx_count = 0
    
    def test_spi(self):
        """Test komunikacji SPI"""
        cmd = [CMD_R_CONFIG, 0x00, 0x00]
        result = self.spi.xfer2(cmd)
        return not ((result[1] == 0x00 and result[2] == 0x00) or 
                   (result[1] == 0xFF and result[2] == 0xFF))
    
    def config_nrf905(self):
        """Konfiguracja NRF905 - identyczna jak w Arduino"""
        config = [
            CMD_W_CONFIG,
            108,   # Channel 108 (433.2 MHz)
            0x0C,  # 433MHz, 10dBm
            0x44,  # 4-byte addresses
            32,    # RX payload width
            32,    # TX payload width
            0xE7, 0xE7, 0xE7, 0xE7,  # RX address
            0xDB   # CRC enabled
        ]
        self.spi.xfer2(config)
        time.sleep(0.05)
        
        # TX address (taki sam jak w Arduino)
        tx_addr = [CMD_W_TX_ADDRESS, 0xE7, 0xE7, 0xE7, 0xE7]
        self.spi.xfer2(tx_addr)
        time.sleep(0.05)
        
        # Wyczyść bufory
        for _ in range(5):
            self.spi.xfer2([CMD_R_RX_PAYLOAD] + [0x00] * 32)
            time.sleep(0.01)
    
    def enter_rx_mode(self):
        """Przełącz na tryb RX"""
        GPIO.output(GPIO_TX_EN, GPIO.LOW)
        time.sleep(0.002)
        GPIO.output(GPIO_CE, GPIO.HIGH)
        time.sleep(0.001)
    
    def enter_tx_mode(self):
        """Przełącz na tryb TX"""
        GPIO.output(GPIO_CE, GPIO.LOW)
        time.sleep(0.002)
        GPIO.output(GPIO_TX_EN, GPIO.HIGH)
        time.sleep(0.001)
    
    def transmit_command(self, command, param1=0, param2=0):
        """Wyślij komendę do stacji zdalnej"""
        print(f"📤 TX Command: 0x{command:02X} (param1={param1}, param2={param2})")
        
        # Przygotuj pakiet
        packet = CommandPacket(command, param1, param2)
        data = packet.to_bytes()
        
        # Przejdź do standby
        GPIO.output(GPIO_CE, GPIO.LOW)
        GPIO.output(GPIO_TX_EN, GPIO.LOW)
        time.sleep(0.01)
        
        # Zapisz dane do bufora TX
        cmd = [CMD_W_TX_PAYLOAD] + list(data)
        self.spi.xfer2(cmd)
        time.sleep(0.01)
        
        # Transmisja
        self.enter_tx_mode()
        GPIO.output(GPIO_CE, GPIO.HIGH)
        time.sleep(0.1)  # Czas na transmisję
        GPIO.output(GPIO_CE, GPIO.LOW)
        
        # Powrót do RX
        self.enter_rx_mode()
        
        self.tx_count += 1
        print(f"✅ Komenda wysłana (TX#{self.tx_count})")
        
        return True
    
    def receive_data(self):
        """Odbierz dane z stacji zdalnej"""
        # Sprawdź czy są dane
        cmd = [CMD_R_RX_PAYLOAD] + [0x00] * 32
        result = self.spi.xfer2(cmd)
        data = bytes(result[1:33])
        
        # Sprawdź czy nie puste
        if all(b == 0x00 for b in data) or all(b == 0xFF for b in data):
            return None
        
        self.rx_count += 1
        
        # Parsuj dane
        sensor_data = SensorData(data)
        
        if sensor_data.verify_crc(data):
            return sensor_data
        else:
            print(f"[WARN] RX#{self.rx_count}: CRC fail")
            return None
    
    def close(self):
        """Zamknij połączenia"""
        GPIO.output(GPIO_CE, GPIO.LOW)
        GPIO.output(GPIO_PWR, GPIO.LOW)
        self.spi.close()
        GPIO.cleanup()


class TCPServer:
    """Serwer TCP - komunikacja z WPF"""
    
    def __init__(self, host, port, transceiver):
        self.host = host
        self.port = port
        self.transceiver = transceiver
        self.clients = []
        self.running = False
        self.server_socket = None
    
    def start(self):
        """Uruchom serwer"""
        print("🚀 TCPServer.start() wywołany")
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print("✅ Socket utworzony")
            
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            print("✅ SO_REUSEADDR ustawiony")
            
            self.server_socket.bind((self.host, self.port))
            print(f"✅ Bind na {self.host}:{self.port} zakończony")
            
            self.server_socket.listen(5)
            print("✅ Listen(5) aktywny")
            
            self.running = True
            print("✅ self.running = True")
            
            print(f"🌐 Serwer TCP nasłuchuje na {self.host}:{self.port}")
            print()
            
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            print("✅ Wątek accept_connections utworzony")
            
            accept_thread.start()
            print("✅ Wątek accept_connections uruchomiony")
            
        except Exception as e:
            print(f"❌ BŁĄD w TCPServer.start(): {e}")
            import traceback
            traceback.print_exc()
    
    def accept_connections(self):
        """Akceptuj połączenia"""
        print("👂 accept_connections() uruchomiony - nasłuchuję...")
        
        while self.running:
            try:
                print("⏳ Czekam na połączenie...")
                client_socket, address = self.server_socket.accept()
                print(f"✅ Nowy klient: {address}")
                self.clients.append(client_socket)
                print(f"📊 Liczba klientów po dodaniu: {len(self.clients)}")
                
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
                print(f"🧵 Wątek klienta uruchomiony")
            except Exception as e:
                if self.running:
                    print(f"❌ Błąd akceptowania: {e}")
    
    def handle_client(self, client_socket):
        """Obsługa klienta - odbieranie komend z WPF"""
        print("🔄 handle_client() uruchomiony dla klienta")
        buffer = b''
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    print("❌ Klient rozłączony (brak danych)")
                    break
                
                buffer += data
                
                # Przetwarzaj kompletne wiadomości JSON (zakończone \n)
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    
                    try:
                        message = json.loads(line.decode('utf-8-sig').strip())
                        self.process_command(message, client_socket)
                    except json.JSONDecodeError:
                        print(f"Błąd parsowania JSON: {line}")
                
        except Exception as e:
            print(f"Błąd komunikacji z klientem: {e}")
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            client_socket.close()
            print("❌ Klient rozłączony")
    
    def process_command(self, message, client_socket):
        """Przetwórz komendę z WPF i wyślij do Arduino"""
        command = message.get('command', '').lower()
        param1  = message.get('param1', 0)
        param2  = message.get('param2', 0)

        print(f"📨 Otrzymano komendę z WPF: {command} (p1={param1}, p2={param2})")
        
        if command == 'measure':
            duration = message.get('duration', 120)
            self.transceiver.transmit_command(CMD_MEASURE_START, duration, 0)
            response = {'status': 'ok', 'message': f'Measurement started for {duration}s'}
            
        elif command == 'stop':
            self.transceiver.transmit_command(CMD_MEASURE_STOP)
            response = {'status': 'ok', 'message': 'Measurement stopped'}
            
        elif command == 'pump_on':
            self.transceiver.transmit_command(CMD_PUMP_ON)
            response = {'status': 'ok', 'message': 'Pump 1 ON'}
            
        elif command == 'pump_off':
            self.transceiver.transmit_command(CMD_PUMP_OFF)
            response = {'status': 'ok', 'message': 'Pump 1 OFF'}

        elif command == 'samples_loading':
            self.transceiver.transmit_command(CMD_SAMPLES_LOADING)
            response = {'status': 'ok', 'message': 'Samples loading sequence started'}

        elif command == 'reject_sample':
            self.transceiver.transmit_command(CMD_REJECT_SAMPLE)
            response = {'status': 'ok', 'message': 'Reject sample sequence started'}

        elif command == 'boat_drive':
            # param1 = lewy silnik (0-200, 100=stop)
            # param2 = prawy silnik (0-200, 100=stop)
            left  = max(0, min(200, int(param1)))
            right = max(0, min(200, int(param2)))
            self.transceiver.transmit_command(CMD_BOAT_DRIVE, left, right)
            response = {'status': 'ok', 'message': f'Boat drive: L={left} R={right}'}
            
        else:
            response = {'status': 'error', 'message': f'Unknown command: {command}'}
        
        # Wyślij odpowiedź do WPF
        try:
            client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
        except:
            pass
    
    def broadcast_data(self, sensor_data):
        """Wyślij dane do wszystkich klientów WPF"""
        if sensor_data:
            json_data = json.dumps(sensor_data.to_dict()) + '\n'
            
            print(f"📊 broadcast_data() wywołana - Klientów: {len(self.clients)}")
            
            if len(self.clients) == 0:
                print("⚠️  Brak klientów do wysłania danych")
                return
            
            disconnected = []
            for client in self.clients:
                try:
                    client.sendall(json_data.encode('utf-8'))
                    print(f"✅ Wysłano: {len(json_data)} bajtów")
                except Exception as e:
                    print(f"❌ Błąd: {e}")
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
    print("=" * 60)
    print("STACJA BAZOWA - Half Duplex System")
    print("PC + Raspberry Pi + NRF905 ↔ NRF905 + Arduino + Raspberry Pi")
    print("=" * 60)
    print()
    
    try:
        transceiver = NRF905Transceiver()
    except Exception as e:
        print(f"\n❌ Błąd inicjalizacji: {e}")
        return
    
    tcp_server = TCPServer(TCP_HOST, TCP_PORT, transceiver)
    tcp_server.start()
    
    print("✅ System gotowy")
    print("📡 Odbieranie danych z Arduino...")
    print("🎮 Oczekiwanie na komendy z WPF...")
    print("Ctrl+C aby zakończyć")
    print()
    
    try:
        while True:
            sensor_data = transceiver.receive_data()
            
            if sensor_data and sensor_data.station_id > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 {sensor_data}")
                tcp_server.broadcast_data(sensor_data)
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Zatrzymywanie...")
    finally:
        transceiver.close()
        tcp_server.stop()
        print(f"📊 RX: {transceiver.rx_count}, TX: {transceiver.tx_count}")
        print("✅ Zamknięto")


if __name__ == '__main__':
    main()