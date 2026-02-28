/*
 * ARDUINO - STACJA POMIAROWA (Remote Station)
 * Full Duplex: Odbiera komendy z RPi#1, przekazuje do RPi#2 przez Serial
 *              Odbiera dane z RPi#2 przez Serial, transmituje do RPi#1 przez NRF905
 * 
 * Pinout:
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
 *
 * Cytron MDD20A (sterowanie łódką):
 * CH1 PWM  -> D3   (lewy silnik, prędkość)
 * CH1 DIR  -> D2   (lewy silnik, kierunek)
 * CH2 PWM  -> D6   (prawy silnik, prędkość)
 * CH2 DIR  -> D4   (prawy silnik, kierunek)
 *
 * Sterowanie WSAD przez NRF905:
 * CMD_BOAT_DRIVE (0x20): param1=lewy, param2=prawy
 * Prędkość: 0=pełny wstecz, 100=stop, 200=pełny przód
 * Watchdog: brak komendy przez 500ms = automatyczny STOP
 */

#include <SPI.h>

// Piny NRF905
#define NRF905_CSN   10
#define NRF905_CE    9
#define NRF905_PWR   8
#define NRF905_TX_EN 7
#define NRF905_DR    5

// Komendy NRF905
#define CMD_W_CONFIG     0x00
#define CMD_R_CONFIG     0x10
#define CMD_W_TX_PAYLOAD 0x20
#define CMD_R_TX_PAYLOAD 0x21
#define CMD_W_TX_ADDRESS 0x22
#define CMD_R_RX_PAYLOAD 0x24

// Command codes (od RPi#1)
#define CMD_MEASURE_START   0x01
#define CMD_MEASURE_STOP    0x02
#define CMD_PUMP_ON         0x03  // Pompa 1 (napełnianie zbiornika)
#define CMD_PUMP_OFF        0x04  // Pompa 1 
#define CMD_STATUS_REQUEST  0x05
#define CMD_SAMPLES_LOADING 0x06  // Sekwencja ładowania próbki (pompa 2)
#define CMD_REJECT_SAMPLE   0x07  // Odrzut próbki - opróżnianie (pompa 2)
#define CMD_BOAT_DRIVE      0x20  // Napęd łódki: param1=lewy(0-200), param2=prawy(0-200), 100=stop (radio nie pozwala wysyłac ujemnych więc przesuwamy zakres do 0-200)

// Packet types (do RPi#1)
#define PACKET_DATA   0x10
#define PACKET_STATUS 0x11

// SPI Settings
SPISettings nrf905_spi(200000, MSBFIRST, SPI_MODE0);

// ─── PINY SILNIKÓW (Cytron MDD20A) ───────────────────────────────────────────
#define MOTOR_LEFT_PWM  3   // D3  - lewy silnik prędkość (PWM)
#define MOTOR_LEFT_DIR  2   // D2  - lewy silnik kierunek
#define MOTOR_RIGHT_PWM 6   // D6  - prawy silnik prędkość (PWM)
#define MOTOR_RIGHT_DIR 4   // D4  - prawy silnik kierunek



// Command packet (32 bajty - odbierane z RPi#1)
struct CommandPacket {
  uint8_t  command;
  uint16_t param1;
  uint16_t param2;
  uint32_t timestamp;
  uint8_t  reserved[22];
  uint8_t  crc;
} __attribute__((packed));

// Data packet (32 bajty - wysyłane do RPi#1)
struct SensorData {
  uint8_t  stationID;
  float    ph;
  float    tds;
  float    temperature;
  float    conductivity;
  uint32_t timestamp;
  uint16_t batteryVoltage;
  uint8_t  errorFlags;
  uint8_t  reserved[7];
  uint8_t  crc;
} __attribute__((packed));

SensorData    sensorData;
CommandPacket cmdPacket;

unsigned long lastRxCheck       = 0;
unsigned long lastDataTransmit  = 0;
const unsigned long RX_CHECK_INTERVAL      = 50;    // co 50ms
const unsigned long DATA_TRANSMIT_INTERVAL = 2000;  // co 2s

uint32_t rxCount = 0;
uint32_t txCount = 0;
bool autoMode = true;
unsigned long lastBoatCommand = 0;  // Watchdog: czas ostatniej komendy WSAD
const unsigned long BOAT_WATCHDOG_MS = 500;  // STOP jeśli brak komendy przez 500ms

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000);

  // Konfiguracja pinów
  pinMode(NRF905_CSN,   OUTPUT);
  pinMode(NRF905_CE,    OUTPUT);
  pinMode(NRF905_PWR,   OUTPUT);
  pinMode(NRF905_TX_EN, OUTPUT);
  pinMode(NRF905_DR,    INPUT);
  pinMode(LED_BUILTIN,  OUTPUT);

  // Inicjalizacja silników
  pinMode(MOTOR_LEFT_PWM,  OUTPUT);
  pinMode(MOTOR_LEFT_DIR,  OUTPUT);
  pinMode(MOTOR_RIGHT_PWM, OUTPUT);
  pinMode(MOTOR_RIGHT_DIR, OUTPUT);
  setMotor(MOTOR_LEFT_PWM,  MOTOR_LEFT_DIR,  0);
  setMotor(MOTOR_RIGHT_PWM, MOTOR_RIGHT_DIR, 0);

  digitalWrite(NRF905_CSN,   HIGH);
  digitalWrite(NRF905_CE,    LOW);
  digitalWrite(NRF905_PWR,   LOW);
  digitalWrite(NRF905_TX_EN, LOW);

  SPI.begin();
  delay(50);

  digitalWrite(NRF905_PWR, HIGH);
  delay(150);

  if (!testSPI()) {
    while(1);  // zatrzymaj jeśli SPI nie działa
  }

  initNRF905();
  enterRXMode();

  // Inicjalizacja danych
  sensorData.stationID      = 1;
  sensorData.batteryVoltage = 3700;
  sensorData.errorFlags     = 0;
  memset(sensorData.reserved, 0, sizeof(sensorData.reserved));
  Serial.setTimeout(10);
}

// ─────────────────────────────────────────────────────────────────────────────

void loop() {
  // ODBIERANIE KOMEND z RPi#1
  if (millis() - lastRxCheck >= RX_CHECK_INTERVAL) {
    checkForCommands();
    lastRxCheck = millis();
  }

  // WYSYŁANIE GET_DATA do RPi#2 (auto-mode)
  if (autoMode && (millis() - lastDataTransmit >= DATA_TRANSMIT_INTERVAL)) {
    requestDataFromRPi2();
    lastDataTransmit = millis();
  }

  // ODBIERANIE DANYCH z RPi#2 przez Serial
  if (Serial.available() > 0) {
    processSerialData();
  }

  // WATCHDOG ŁÓDKI — brak komendy przez 500ms = STOP
  if (lastBoatCommand > 0 && millis() - lastBoatCommand >= BOAT_WATCHDOG_MS) {
    setMotor(MOTOR_LEFT_PWM,  MOTOR_LEFT_DIR,  0);
    setMotor(MOTOR_RIGHT_PWM, MOTOR_RIGHT_DIR, 0);
    lastBoatCommand = 0;  // Resetuj żeby nie spamować
  }
}

// ─────────────────────────────────────────────────────────────────────────────

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
  digitalWrite(NRF905_CE,    LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(50);

  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);

  SPI.transfer(CMD_W_CONFIG);
  SPI.transfer(108);    // Channel 108 (433.2 MHz)
  SPI.transfer(0x0C);   // 433MHz, 10dBm
  SPI.transfer(0x44);   // 4-byte addresses
  SPI.transfer(32);     // RX payload width
  SPI.transfer(32);     // TX payload width
  SPI.transfer(0xE7); SPI.transfer(0xE7);
  SPI.transfer(0xE7); SPI.transfer(0xE7);  // RX address
  SPI.transfer(0xDB);   // CRC enabled

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
  digitalWrite(NRF905_CE,    LOW);
  delay(2);
  digitalWrite(NRF905_TX_EN, HIGH);
  delay(1);
}

// ─────────────────────────────────────────────────────────────────────────────

void checkForCommands() {
  // Sprawdź pin DR — jeśli LOW, brak danych, nie czytaj
  if (digitalRead(NRF905_DR) == LOW) return;

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

  // Weryfikuj CRC
  memcpy(&cmdPacket, buffer, sizeof(CommandPacket));
  uint8_t calculatedCRC = calculateCRC(buffer, 31);
  if (calculatedCRC != cmdPacket.crc) return;

  rxCount++;
  processCommand(cmdPacket.command, cmdPacket.param1, cmdPacket.param2);
}

void processCommand(uint8_t cmd, uint16_t param1, uint16_t param2) {
  // Tylko komendy dla RPi#2 — żadnych debugowych printów przez Serial
  switch (cmd) {
    case CMD_MEASURE_START:
      Serial.print(F("MEASURE:"));
      Serial.println(param1);
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

    case CMD_SAMPLES_LOADING:           
      Serial.println(F("SAMPLES_LOADING"));
      break;

    case CMD_REJECT_SAMPLE:             
      Serial.println(F("REJECT_SAMPLE"));
      break;

    case CMD_BOAT_DRIVE: {
      // param1=lewy(0-200), param2=prawy(0-200), 100=zatrzymanie
      int leftSpeed  = (int)param1 - 100;  // -100..+100
      int rightSpeed = (int)param2 - 100;  // -100..+100
      setMotor(MOTOR_LEFT_PWM,  MOTOR_LEFT_DIR,  leftSpeed);
      setMotor(MOTOR_RIGHT_PWM, MOTOR_RIGHT_DIR, rightSpeed);
      lastBoatCommand = millis();  // Odśwież watchdog
      break;
    }
  }
}

void requestDataFromRPi2() {
  Serial.println(F("GET_DATA"));
}

// ─────────────────────────────────────────────────────────────────────────────

void processSerialData() {
  String line = Serial.readStringUntil('\n');
  line.trim();
  
  // DEBUG - użyj LED (bo Serial.print idzie do RPi#2)
  if (line.length() > 0) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }

  if (line.startsWith("DATA:")) {
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
      sensorData.errorFlags = line.substring(idx4 + 1).toInt() & 0x01;
      sensorData.timestamp = millis() / 1000;

      transmitData();
    }
  }
  else if (line.startsWith("MEASUREMENT_DONE")) {
    autoMode = false;
    digitalWrite(LED_BUILTIN, HIGH);
    delay(1000);
    digitalWrite(LED_BUILTIN, LOW);
  }

  else if (line.startsWith("STATUS:")) {
    // TODO: parsuj status i przekaż do RPi#1(opcjonalne)
  }
}

void transmitData() {
  sensorData.crc = calculateCRC((uint8_t*)&sensorData, sizeof(sensorData) - 1);

  // Standby
  digitalWrite(NRF905_CE,    LOW);
  digitalWrite(NRF905_TX_EN, LOW);
  delay(10);

  // Zapisz payload
  SPI.beginTransaction(nrf905_spi);
  digitalWrite(NRF905_CSN, LOW);
  delayMicroseconds(10);

  SPI.transfer(CMD_W_TX_PAYLOAD);
  uint8_t* dataPtr = (uint8_t*)&sensorData;
  for (int i = 0; i < (int)sizeof(sensorData); i++) {
    SPI.transfer(dataPtr[i]);
  }

  digitalWrite(NRF905_CSN, HIGH);
  SPI.endTransaction();
  delay(10);

  // Transmisja
  enterTXMode();
  digitalWrite(NRF905_CE, HIGH);
  delay(100);
  digitalWrite(NRF905_CE, LOW);

  // Powrót do RX
  enterRXMode();

  txCount++;
}

// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Ustaw silnik: speed -100..+100 (0=stop, +100=pełny przód, -100=pełny wstecz)
void setMotor(uint8_t pwmPin, uint8_t dirPin, int speed) {
  if (speed > 0) {
    digitalWrite(dirPin, HIGH);
    analogWrite(pwmPin, map(speed, 0, 100, 0, 255));
  } else if (speed < 0) {
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, map(-speed, 0, 100, 0, 255));
  } else {
    analogWrite(pwmPin, 0);
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
