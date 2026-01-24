/*
 * NRF905 Transmitter - Arduino Nano 33 BLE
 * Stacja Pomiarowa - wysyła dane z czujników
 * WERSJA Z PEŁNĄ DIAGNOSTYKĄ
 * 
 * Pinout:
 * NRF905 VCC  -> 3.3V (ważne! nie 5V)
 * NRF905 GND  -> GND
 * NRF905 MOSI -> D11
 * NRF905 MISO -> D12
 * NRF905 SCK  -> D13
 * NRF905 CSN  -> D10
 * NRF905 CE   -> D9
 * NRF905 PWR  -> D8
 * NRF905 TX_EN-> D7
 * NRF905 DR   -> D5 (Data Ready - NOWY!)
 * NRF905 CD   -> D6 (Carrier Detect - opcjonalnie)
 */

#include <SPI.h>

// Piny NRF905
#define NRF905_CSN   10
#define NRF905_CE    9
#define NRF905_PWR   8
#define NRF905_TX_EN 7
#define NRF905_CD    6
#define NRF905_DR    5  // Data Ready - WAŻNY PIN!

// Komendy NRF905
#define CMD_W_CONFIG 0x00
#define CMD_R_CONFIG 0x10
#define CMD_W_TX_PAYLOAD 0x20
#define CMD_R_TX_PAYLOAD 0x21
#define CMD_W_TX_ADDRESS 0x22
#define CMD_R_TX_ADDRESS 0x23
#define CMD_R_RX_PAYLOAD 0x24
#define CMD_CHANNEL_CONFIG 0x80

// Ustawienia SPI dla NRF905
SPISettings nrf905_spi(200000, MSBFIRST, SPI_MODE0);  // ZMIENIONE: 200kHz jak w działającym przykładzie

// Struktura danych do wysłania (32 bajty - max payload NRF905)
struct SensorData {
  uint8_t stationID;       // ID stacji (1 bajt)
  float ph;                // pH (4 bajty)
  float tds;               // TDS w ppm (4 bajty)
  float temperature;       // Temperatura w °C (4 bajty)
  float conductivity;      // Przewodność w µS/cm (4 bajty)
  uint32_t timestamp;      // Znacznik czasu (4 bajty)
  uint16_t batteryVoltage; // Napięcie baterii w mV (2 bajty)
  uint8_t errorFlags;      // Flagi błędów (1 bajt)
  uint8_t reserved[7];     // Rezerwa (7 bajtów)
  uint8_t crc;             // Suma kontrolna (1 bajt)
} __attribute__((packed));

SensorData data;
uint32_t lastTransmission = 0;
const uint16_t TRANSMISSION_INTERVAL = 2000; // 2 sekundy

// Statystyki
uint32_t txCount = 0;
uint32_t txSuccessCount = 0;
uint32_t txFailCount = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000); // Czekaj na Serial (max 3s)
  
  Serial.println(F("========================================"));
  Serial.println(F("NRF905 Transmitter - DIAGNOSTYKA"));
  Serial.println(F("========================================"));
  Serial.println();
  
  // Konfiguracja pinów
  pinMode(NRF905_CSN, OUTPUT);
  pinMode(NRF905_CE, OUTPUT);
  pinMode(NRF905_PWR, OUTPUT);
  pinMode(NRF905_TX_EN, OUTPUT);
  pinMode(NRF905_CD, INPUT);
  pinMode(NRF905_DR, INPUT);  // NOWY PIN!
  
  digitalWrite(NRF905_CSN, HIGH);
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_PWR, LOW);  // Start with power off
  digitalWrite(NRF905_TX_EN, LOW);
  
  Serial.println(F("1. Inicjalizacja SPI..."));
  SPI.begin();
  delay(50);
  Serial.println(F("   [OK] SPI zainicjalizowany"));
  
  Serial.println(F("2. Włączanie zasilania NRF905..."));
  digitalWrite(NRF905_PWR, HIGH);  // Power up
  delay(150); // Zwiększone opóźnienie na stabilizację
  Serial.println(F("   [OK] Zasilanie włączone"));
  
  // TEST 1: Sprawdź komunikację SPI
  Serial.println(F("3. Test komunikacji SPI..."));
  if (testSPICommunication()) {
    Serial.println(F("   [OK] Komunikacja SPI działa"));
  } else {
    Serial.println(F("   [BŁĄD] Brak komunikacji SPI!"));
    Serial.println(F("   Sprawdź połączenia: MOSI, MISO, SCK, CSN"));
    while(1); // Stop
  }
  
  // Inicjalizacja NRF905
  Serial.println(F("4. Konfiguracja NRF905..."));
  initNRF905();
  Serial.println(F("   [OK] NRF905 skonfigurowany"));
  
  // TEST 2: Weryfikacja konfiguracji
  Serial.println(F("5. Weryfikacja konfiguracji..."));
  verifyConfiguration();
  
  // TEST 3: Sprawdź piny statusu
  Serial.println(F("6. Test pinów statusu..."));
  testStatusPins();
  
  // Inicjalizacja struktury danych
  data.stationID = 1;
  data.timestamp = 0;
  data.batteryVoltage = 3700; // 3.7V
  data.errorFlags = 0;
  memset(data.reserved, 0, sizeof(data.reserved));
  
  Serial.println();
  Serial.println(F("========================================"));
  Serial.println(F("SYSTEM GOTOWY - Start transmisji"));
  Serial.println(F("Rozmiar pakietu: 32 bajty"));
  Serial.println(F("Interwał: 2 sekundy"));
  Serial.println(F("========================================"));
  Serial.println();
}

void loop() {
  if (millis() - lastTransmission >= TRANSMISSION_INTERVAL) {
    // Symulacja odczytu czujników
    data.ph = 7.2 + (random(-10, 10) / 100.0);
    data.tds = 350 + random(-50, 50);
    data.temperature = 22.5 + (random(-20, 20) / 10.0);
    data.conductivity = 700 + random(-100, 100);
    data.timestamp = millis() / 1000;
    
    // Oblicz CRC
    data.crc = calculateCRC((uint8_t*)&data, sizeof(data) - 1);
    
    // Wyślij dane z diagnostyką
    bool success = transmitDataWithDiagnostics();
    
    // Debug
    Serial.print(F("TX #"));
    Serial.print(txCount);
    Serial.print(success ? F(" [OK] ") : F(" [FAIL] "));
    Serial.print(F("["));
    Serial.print(data.timestamp);
    Serial.print(F("]  pH:"));
    Serial.print(data.ph, 2);
    Serial.print(F("  TDS:"));
    Serial.print(data.tds, 1);
    Serial.print(F("ppm  Temp:"));
    Serial.print(data.temperature, 1);
    Serial.print(F("°C  Cond:"));
    Serial.print(data.conductivity, 0);
    Serial.print(F("µS/cm  CRC:0x"));
    Serial.print(data.crc, HEX);
    Serial.print(F("  Success rate: "));
    Serial.print(txCount > 0 ? (txSuccessCount * 100 / txCount) : 0);
    Serial.println(F("%"));
    
    lastTransmission = millis();
  }
}

bool testSPICommunication() {
  // Próba odczytu rejestru konfiguracji
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_R_CONFIG);
  uint8_t byte0 = SPI.transfer(0x00);
  uint8_t byte1 = SPI.transfer(0x00);
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  // Sprawdź czy otrzymaliśmy sensowne dane (nie same 0x00 ani 0xFF)
  if ((byte0 == 0x00 && byte1 == 0x00) || (byte0 == 0xFF && byte1 == 0xFF)) {
    Serial.print(F("   Odczytano: 0x"));
    Serial.print(byte0, HEX);
    Serial.print(F(" 0x"));
    Serial.println(byte1, HEX);
    return false;
  }
  
  return true;
}

void initNRF905() {
  // Upewnij się że jesteśmy w standby
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(50);
  
  // Konfiguracja NRF905 - UPROSZCZONA jak w działającym przykładzie
  // Format: [CMD, CH, Mode, Addr_width, RX_PW, TX_PW, RX_ADDR(4), Config]
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_CONFIG);
  SPI.transfer(108);   // Channel 108 (433.2 MHz) - bezpośrednia wartość
  SPI.transfer(0x0C);  // 433MHz, 10dBm
  SPI.transfer(0x44);  // TX_AFW=4, RX_AFW=4
  SPI.transfer(32);    // RX payload width (tylko LOW byte)
  SPI.transfer(32);    // TX payload width (tylko LOW byte)
  SPI.transfer(0xE7);  // RX address byte 0
  SPI.transfer(0xE7);  // RX address byte 1
  SPI.transfer(0xE7);  // RX address byte 2
  SPI.transfer(0xE7);  // RX address byte 3
  SPI.transfer(0xDB);  // CRC enabled, 16-bit CRC
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  delay(50);  // Dłuższe opóźnienie na stabilizację
  
  // Ustaw adres TX
  setTXAddress();
  delay(50);
  
  // WAŻNE: Wyczyść bufor TX przed rozpoczęciem
  Serial.println(F("   Czyszczenie bufora TX..."));
  for (int i = 0; i < 10; i++) {
    SPI.beginTransaction(nrf905_spi);
    digitalWrite(NRF905_CSN, LOW);
    delayMicroseconds(10);
    SPI.transfer(CMD_W_TX_PAYLOAD);
    for (int j = 0; j < 32; j++) {
      SPI.transfer(0x00);
    }
    digitalWrite(NRF905_CSN, HIGH);
    SPI.endTransaction();
    delay(5);
  }
}

void setTXAddress() {
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_TX_ADDRESS);
  SPI.transfer(0xE7);
  SPI.transfer(0xE7);
  SPI.transfer(0xE7);
  SPI.transfer(0xE7);
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
}

void verifyConfiguration() {
  Serial.println(F("   Odczyt konfiguracji:"));
  
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_R_CONFIG);
  
  uint8_t config[11];  // ZMIENIONE: 11 bajtów zamiast 12
  for (int i = 0; i < 11; i++) {
    config[i] = SPI.transfer(0x00);
  }
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  // Wyświetl konfigurację
  Serial.print(F("   CH: "));
  Serial.print(config[0]);
  Serial.print(F(" (0x"));
  Serial.print(config[0], HEX);
  Serial.print(F(")  Mode: 0x"));
  Serial.print(config[1], HEX);
  Serial.print(F("  Addr: 0x"));
  Serial.print(config[2], HEX);
  Serial.print(F("  RX_PW: "));
  Serial.print(config[3]);
  Serial.print(F("  TX_PW: "));
  Serial.println(config[4]);
  
  Serial.print(F("   RX_ADDR: "));
  for (int i = 5; i <= 8; i++) {  // ZMIENIONE: bajty 5-8
    Serial.print(F("0x"));
    Serial.print(config[i], HEX);
    if (i < 8) Serial.print(F(" "));
  }
  Serial.println();
  
  Serial.print(F("   Config: 0x"));
  Serial.println(config[9], HEX);
  
  // Sprawdź TX Address
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_R_TX_ADDRESS);
  Serial.print(F("   TX_ADDR: "));
  for (int i = 0; i < 4; i++) {
    uint8_t addr = SPI.transfer(0x00);
    Serial.print(F("0x"));
    Serial.print(addr, HEX);
    if (i < 3) Serial.print(F(" "));
  }
  Serial.println();
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  // Weryfikacja wartości
  bool configOK = true;
  if (config[0] != 108) {
    Serial.print(F("   [WARN] Nieprawidłowy kanał! Oczekiwano 108, otrzymano "));
    Serial.println(config[0]);
    configOK = false;
  }
  if (config[3] != 32 || config[4] != 32) {
    Serial.println(F("   [WARN] Nieprawidłowa szerokość payload!"));
    configOK = false;
  }
  
  if (configOK) {
    Serial.println(F("   [OK] Konfiguracja poprawna"));
  }
}

void testStatusPins() {
  Serial.print(F("   DR (Data Ready): "));
  Serial.println(digitalRead(NRF905_DR) ? "HIGH" : "LOW");
  
  Serial.print(F("   CD (Carrier Detect): "));
  Serial.println(digitalRead(NRF905_CD) ? "HIGH" : "LOW");
  
  Serial.println(F("   [INFO] DR powinien być LOW w stanie spoczynku"));
}

bool transmitDataWithDiagnostics() {
  txCount++;
  
  // 1. Przejdź do standby
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(10);  // Dłuższe opóźnienie
  
  // 2. Zapisz dane do bufora TX
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);
  
  SPI.transfer(CMD_W_TX_PAYLOAD);
  
  uint8_t* dataPtr = (uint8_t*)&data;
  for (int i = 0; i < sizeof(data); i++) {
    SPI.transfer(dataPtr[i]);
  }
  
  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  
  delay(10);  // Opóźnienie po zapisie
  
  // 3. Włącz tryb TX - POPRAWIONA SEKWENCJA
  digitalWrite(NRF905_TX_EN, HIGH);  // Najpierw TX_EN
  delay(5);
  digitalWrite(NRF905_CE, HIGH);     // Potem CE
  
  // 4. Czekaj na zakończenie transmisji (pin DR)
  unsigned long timeout = millis();
  bool drDetected = false;
  
  while (millis() - timeout < 100) { // 100ms timeout
    if (digitalRead(NRF905_DR) == HIGH) {
      drDetected = true;
      break;
    }
    delayMicroseconds(100);
  }
  
  delay(100);  // Czas na pełną transmisję
  
  // 5. Wyłącz TX - powrót do standby
  digitalWrite(NRF905_CE, LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  
  // 6. Sprawdź wynik
  if (drDetected) {
    txSuccessCount++;
    return true;
  } else {
    txFailCount++;
    return false;
  }
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
