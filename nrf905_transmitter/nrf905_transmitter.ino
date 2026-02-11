/*
 * ARDUINO - STACJA POMIAROWA (Remote Station)
 * Full Duplex: Odbiera komendy z RPi#1, przekazuje do RPi#2 przez Serial
 *              Odbiera dane z RPi#2 przez Serial, transmituje do RPi#1 przez NRF905
 * 
 * Pinout (identyczny jak dotychczas):
 * NRF905 CSN  -> D10
 * NRF905 CE   -> D9
 * NRF905 PWR  -> D8
 * NRF905 TX_EN-> D7
 * NRF905 DR   -> D5
 * 
 * Serial do Raspberry Pi #2:
 * Arduino TX  -> RPi RX (GPIO 15, Pin 10)
 * Arduino RX  -> RPi TX (GPIO 14, Pin 8)
 * GND         -> GND
 */

#include <SPI.h>

// Piny NRF905
#define NRF905_CSN   10
#define NRF905_CE    9
#define NRF905_PWR   8
#define NRF905_TX_EN 7
#define NRF905_DR    5

// Komendy NRF905
#define CMD_W_CONFIG 0x00
#define CMD_R_CONFIG 0x10
#define CMD_W_TX_PAYLOAD 0x20
#define CMD_R_TX_PAYLOAD 0x21
#define CMD_W_TX_ADDRESS 0x22
#define CMD_R_RX_PAYLOAD 0x24

// Command codes (od RPi#1)
#define CMD_MEASURE_START 0x01
#define CMD_MEASURE_STOP 0x02
#define CMD_PUMP_ON 0x03
#define CMD_PUMP_OFF 0x04
#define CMD_STATUS_REQUEST 0x05

// Packet types (do RPi#1)
#define PACKET_DATA 0x10
#define PACKET_STATUS 0x11

// SPI Settings
SPISettings nrf905_spi(200000, MSBFIRST, SPI_MODE0);

// Command packet (32 bajty - odbierane z RPi#1)
struct CommandPacket {
  uint8_t command;
  uint16_t param1;
  uint16_t param2;
  uint32_t timestamp;
  uint8_t reserved[22];
  uint8_t crc;
} __attribute__((packed));

// Data packet (32 bajty - wysyłane do RPi#1)
struct SensorData {
  uint8_t stationID;
  float ph;
  float tds;
  float temperature;
  float conductivity;
  uint32_t timestamp;
  uint16_t batteryVoltage;
  uint8_t errorFlags;
  uint8_t reserved[7];
  uint8_t crc;
} __attribute__((packed));

SensorData sensorData;
CommandPacket cmdPacket;

unsigned long lastRxCheck = 0;
unsigned long lastDataTransmit = 0;
const unsigned long RX_CHECK_INTERVAL = 50;    // Sprawdzaj co 50ms
const unsigned long DATA_TRANSMIT_INTERVAL = 2000;  // Auto-transmit co 2s

uint32_t rxCount = 0;
uint32_t txCount = 0;
bool autoMode = true;  // Auto-transmisja włączona

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);
  
  Serial.println(F("==========================================="));
  Serial.println(F("ARDUINO - STACJA POMIAROWA"));
  Serial.println(F("Full Duplex: RX Commands + TX Data"));
  Serial.println(F("==========================================="));
  Serial.println();
  
  // Konfiguracja pinów
  pinMode(NRF905_CSN, OUTPUT);
  pinMode(NRF905_CE, OUTPUT);
  pinMode(NRF905_PWR, OUTPUT);
  pinMode(NRF905_TX_EN, OUTPUT);
  pinMode(NRF905_DR, INPUT);
  
  digitalWrite(NRF905_CSN, HIGH);
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_PWR, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  
  // Inicjalizacja SPI
  Serial.println(F("1. Inicjalizacja SPI..."));
  SPI.begin();
  delay(50);
  Serial.println(F("   [OK] SPI gotowe"));
  
  // Włącz zasilanie
  Serial.println(F("2. Zasilanie NRF905..."));
  digitalWrite(NRF905_PWR, HIGH);
  delay(150);
  Serial.println(F("   [OK] NRF905 zasilone"));
  
  // Test SPI
  Serial.println(F("3. Test komunikacji SPI..."));
  if (!testSPI()) {
    Serial.println(F("   [BŁĄD] Brak komunikacji SPI!"));
    while(1);
  }
  Serial.println(F("   [OK] Komunikacja działa"));
  
  // Konfiguracja NRF905
  Serial.println(F("4. Konfiguracja NRF905..."));
  initNRF905();
  Serial.println(F("   [OK] Skonfigurowano"));
  
  // Tryb RX domyślnie
  enterRXMode();
  Serial.println(F("   [OK] Tryb RX aktywny"));
  
  // Inicjalizacja danych
  sensorData.stationID = 1;
  sensorData.batteryVoltage = 3700;
  sensorData.errorFlags = 0;
  memset(sensorData.reserved, 0, sizeof(sensorData.reserved));
  
  Serial.println();
  Serial.println(F("==========================================="));
  Serial.println(F("SYSTEM GOTOWY"));
  Serial.println(F("Nasłuchiwanie komend..."));
  Serial.println(F("==========================================="));
  Serial.println();
}

void loop() {
  // ODBIERANIE KOMEND z RPi#1
  if (millis() - lastRxCheck >= RX_CHECK_INTERVAL) {
    checkForCommands();
    lastRxCheck = millis();
  }
  
  // WYSYŁANIE DANYCH do RPi#1 (auto-mode)
  if (autoMode && (millis() - lastDataTransmit >= DATA_TRANSMIT_INTERVAL)) {
    requestDataFromRPi2();  // Poproś RPi#2 o dane
    lastDataTransmit = millis();
  }
  
  // ODBIERANIE DANYCH z RPi#2 przez Serial
  if (Serial.available() > 0) {
    processSerialData();
  }
}

bool testSPI() {
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_R_CONFIG);
  uint8_t b1 = SPI.transfer(0x00);
  uint8_t b2 = SPI.transfer(0x00);
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  return !((b1 == 0x00 && b2 == 0x00) || (b1 == 0xFF && b2 == 0xFF));
}

void initNRF905() {
  // Standby
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(50);
  
  // Konfiguracja (identyczna jak RPi#1 i poprzedni kod)
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_CONFIG);
  SPI.transfer(108);   // Channel 108
  SPI.transfer(0x0C);  // 433MHz, 10dBm
  SPI.transfer(0x44);  // 4-byte addresses
  SPI.transfer(32);    // RX payload
  SPI.transfer(32);    // TX payload
  SPI.transfer(0xE7); SPI.transfer(0xE7); 
  SPI.transfer(0xE7); SPI.transfer(0xE7);  // RX address
  SPI.transfer(0xDB);  // CRC enabled
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  delay(50);
  
  // TX address
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_TX_ADDRESS);
  SPI.transfer(0xE7); SPI.transfer(0xE7);
  SPI.transfer(0xE7); SPI.transfer(0xE7);
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  delay(50);
  
  // Wyczyść bufory
  for (int i = 0; i < 5; i++) {
    SPI.beginTransaction(nrf905_spi);
    digitalWrite(NRF905_CSN, LOW);
    SPI.transfer(CMD_R_RX_PAYLOAD);
    for (int j = 0; j < 32; j++) SPI.transfer(0x00);
    digitalWrite(NRF905_CSN, HIGH);
    SPI.endTransaction();
    delay(5);
  }
}

void enterRXMode() {
  digitalWrite(NRF905_TX_EN, LOW);
  delay(2);
  digitalWrite(NRF905_CE, HIGH);
  delay(1);
}

void enterTXMode() {
  digitalWrite(NRF905_CE, LOW);
  delay(2);
  digitalWrite(NRF905_TX_EN, HIGH);
  delay(1);
}

void checkForCommands() {
  // Sprawdź czy są dane (komenda z RPi#1)
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_R_RX_PAYLOAD);
  
  uint8_t buffer[32];
  for (int i = 0; i < 32; i++) {
    buffer[i] = SPI.transfer(0x00);
  }
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  // Sprawdź czy nie puste
  bool isEmpty = true;
  for (int i = 0; i < 32; i++) {
    if (buffer[i] != 0x00 && buffer[i] != 0xFF) {
      isEmpty = false;
      break;
    }
  }
  
  if (isEmpty) return;
  
  // Parsuj komendę
  memcpy(&cmdPacket, buffer, sizeof(CommandPacket));
  
  // Weryfikuj CRC
  uint8_t calculatedCRC = calculateCRC(buffer, 31);
  if (calculatedCRC != cmdPacket.crc) {
    Serial.println(F("[WARN] Komenda: CRC fail"));
    return;
  }
  
  rxCount++;
  
  // Wykonaj komendę
  processCommand(cmdPacket.command, cmdPacket.param1, cmdPacket.param2);
}

void processCommand(uint8_t cmd, uint16_t param1, uint16_t param2) {
  Serial.print(F("RX Command #"));
  Serial.print(rxCount);
  Serial.print(F(": 0x"));
  Serial.print(cmd, HEX);
  Serial.print(F(" ("));
  Serial.print(param1);
  Serial.print(F(", "));
  Serial.print(param2);
  Serial.println(F(")"));
  
  // Przekaż komendę do RPi#2 przez Serial
  switch (cmd) {
    case CMD_MEASURE_START:
      Serial.print(F("MEASURE:"));
      Serial.println(param1);  // duration w sekundach
      autoMode = true;
      break;
      
    case CMD_MEASURE_STOP:
      Serial.println(F("STOP"));
      autoMode = false;
      break;
      
    case CMD_PUMP_ON:
      Serial.println(F("PUMP_ON"));
      break;
      
    case CMD_PUMP_OFF:
      Serial.println(F("PUMP_OFF"));
      break;
      
    case CMD_STATUS_REQUEST:
      Serial.println(F("STATUS"));
      break;
      
    default:
      Serial.print(F("[WARN] Unknown command: 0x"));
      Serial.println(cmd, HEX);
  }
}

void requestDataFromRPi2() {
  // Poproś RPi#2 o dane
  Serial.println(F("GET_DATA"));
}

void processSerialData() {
  // Odbierz dane z RPi#2
  // Format: "DATA:7.2,350,22.5,700,1\n"
  String line = Serial.readStringUntil('\n');
  line.trim();
  
  if (line.startsWith("DATA:")) {
    // Parsuj dane
    line = line.substring(5);  // Usuń "DATA:"
    
    int idx1 = line.indexOf(',');
    int idx2 = line.indexOf(',', idx1 + 1);
    int idx3 = line.indexOf(',', idx2 + 1);
    int idx4 = line.indexOf(',', idx3 + 1);
    
    if (idx1 > 0 && idx2 > 0 && idx3 > 0 && idx4 > 0) {
      sensorData.ph = line.substring(0, idx1).toFloat();
      sensorData.tds = line.substring(idx1 + 1, idx2).toFloat();
      sensorData.temperature = line.substring(idx2 + 1, idx3).toFloat();
      sensorData.conductivity = line.substring(idx3 + 1, idx4).toFloat();
      sensorData.errorFlags = line.substring(idx4 + 1).toInt() & 0x01;  // pump state
      sensorData.timestamp = millis() / 1000;
      
      // Wyślij przez NRF905 do RPi#1
      transmitData();
    }
  }
}

void transmitData() {
  // Oblicz CRC
  sensorData.crc = calculateCRC((uint8_t*)&sensorData, sizeof(sensorData) - 1);
  
  // Standby
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(10);
  
  // Zapisz payload
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_TX_PAYLOAD);
  uint8_t* dataPtr = (uint8_t*)&sensorData;
  for (int i = 0; i < sizeof(sensorData); i++) {
    SPI.transfer(dataPtr[i]);
  }
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  delay(10);
  
  // Transmisja
  enterTXMode();
  digitalWrite(NRF905_CE, HIGH);
  delay(100);  // Czas na TX
  digitalWrite(NRF905_CE, LOW);
  
  // Powrót do RX
  enterRXMode();
  
  txCount++;
  
  Serial.print(F("TX Data #"));
  Serial.print(txCount);
  Serial.print(F(": pH="));
  Serial.print(sensorData.ph, 2);
  Serial.print(F(" TDS="));
  Serial.print(sensorData.tds, 1);
  Serial.print(F("ppm Temp="));
  Serial.print(sensorData.temperature, 1);
  Serial.print(F("°C Pump="));
  Serial.println(sensorData.errorFlags & 0x01 ? "ON" : "OFF");
}

uint8_t calculateCRC(uint8_t* data, uint16_t length) {
  uint8_t crc = 0xFF;
  for (uint16_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (uint8_t j = 0; j < 8; j++) {
      if (crc & 0x80) {
        crc = (crc << 1) ^ 0x31;
      } else {
        crc <<= 1;
      }
    }
  }
  return crc;
}
