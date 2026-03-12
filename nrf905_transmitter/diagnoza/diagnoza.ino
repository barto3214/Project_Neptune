#include <SPI.h>

#define CE_PIN    9
#define PWR_PIN   8
#define TX_EN_PIN 7
#define CSN_PIN   10
#define DR_PIN    5

#define CMD_NOP       0xFF
#define CMD_R_CONFIG  0x10
#define CMD_W_CONFIG  0x00

byte statusByte = 0;

// ── helpers ────────────────────────────────────────────
byte spiTransfer(byte data) {
  digitalWrite(CSN_PIN, LOW);
  delayMicroseconds(5);
  byte r = SPI.transfer(data);
  delayMicroseconds(5);
  digitalWrite(CSN_PIN, HIGH);
  return r;
}

void readConfig(byte* buf, int len) {
  digitalWrite(CSN_PIN, LOW);
  delayMicroseconds(5);
  statusByte = SPI.transfer(CMD_R_CONFIG);
  for (int i = 0; i < len; i++) buf[i] = SPI.transfer(0xFF);
  delayMicroseconds(5);
  digitalWrite(CSN_PIN, HIGH);
}

void writeConfigByte(byte reg, byte val) {
  digitalWrite(CSN_PIN, LOW);
  delayMicroseconds(5);
  SPI.transfer(CMD_W_CONFIG | (reg & 0x0F));
  SPI.transfer(val);
  delayMicroseconds(5);
  digitalWrite(CSN_PIN, HIGH);
}

// ── setup ──────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Serial.println(F("\n===== nRF905 DIAGNOSTYKA ====="));

  pinMode(CSN_PIN,   OUTPUT); digitalWrite(CSN_PIN,   HIGH);
  pinMode(CE_PIN,    OUTPUT); digitalWrite(CE_PIN,    LOW);
  pinMode(TX_EN_PIN, OUTPUT); digitalWrite(TX_EN_PIN, LOW);
  pinMode(PWR_PIN,   OUTPUT);
  pinMode(DR_PIN,    INPUT);

  // --- [1] Zasilanie ---
  Serial.println(F("\n[1] PWR_UP = HIGH ..."));
  digitalWrite(PWR_PIN, HIGH);
  delay(150);

  // --- [2] SPI ---
  SPI.begin();
  SPI.setDataMode(SPI_MODE0);
  SPI.setBitOrder(MSBFIRST);
  SPI.setClockDivider(SPI_CLOCK_DIV16);  // ~1 MHz – bezpieczne
  Serial.println(F("[2] SPI zainicjalizowane (1 MHz, MODE0, MSB)"));
  delay(10);

  // --- [3] Status byte przez NOP ---
  Serial.println(F("\n[TEST 1] Odczyt statusu (NOP):"));
  statusByte = spiTransfer(CMD_NOP);
  Serial.print(F("  Status: 0x")); Serial.println(statusByte, HEX);

  if      (statusByte == 0xFF) Serial.println(F("  !! 0xFF = BRAK ODPOWIEDZI SPI (przewody? 5V na wejsciach?)"));
  else if (statusByte == 0x00) Serial.println(F("  !! 0x00 = problem z GND lub zasilaniem"));
  else                         Serial.println(F("  OK - modul odpowiada na SPI"));

  // --- [4] Odczyt rejestrow konfiguracyjnych ---
  Serial.println(F("\n[TEST 2] Odczyt 10 bajtow konfiguracji:"));
  byte cfg[10];
  readConfig(cfg, 10);
  Serial.print(F("  Config: "));
  for (int i = 0; i < 10; i++) {
    if (cfg[i] < 0x10) Serial.print('0');
    Serial.print(cfg[i], HEX); Serial.print(' ');
  }
  Serial.println();

  // cfg[0] domyslnie = 0x4C (868.2 MHz, -10 dBm, 50 kbps)
  Serial.print(F("  cfg[0] (RF setup): 0x")); Serial.print(cfg[0], HEX);
  if      (cfg[0] == 0x4C) Serial.println(F("  -> domyslna wartosc, OK"));
  else if (cfg[0] == 0xFF) Serial.println(F("  -> BLAD: brak danych z SPI!"));
  else                     Serial.println(F("  -> wartosc niestandardowa (modul byl juz konfigurowany)"));

  // --- [5] Zapis i odczyt z powrotem ---
  Serial.println(F("\n[TEST 3] Zapis 0xAB do cfg[1], odczyt:"));
  writeConfigByte(1, 0xAB);
  delay(5);
  readConfig(cfg, 10);
  Serial.print(F("  Odczytano: 0x")); Serial.println(cfg[1], HEX);
  if (cfg[1] == 0xAB) Serial.println(F("  ZAPIS/ODCZYT OK -> SPI dziala poprawnie!"));
  else                Serial.println(F("  BLAD: zapis nie skutkuje -> SPI nie dziala!"));

  // --- [6] DR pin ---
  Serial.println(F("\n[TEST 4] Pin DR:"));
  Serial.print(F("  DR = ")); Serial.println(digitalRead(DR_PIN) ? "HIGH" : "LOW");
  Serial.println(F("  (oczekiwane LOW w trybie standby/RX bez danych)"));

  // --- Podsumowanie ---
  Serial.println(F("\n===== PODSUMOWANIE ====="));
  Serial.println(F("0xFF wszedzie  -> problem z SPI: sprawdz przewody lub dodaj"));
  Serial.println(F("               level shifter 5V->3.3V na MOSI/SCK/CSN/CE/PWR/TX_EN"));
  Serial.println(F("TEST 3 OK      -> komunikacja SPI sprawna, szukaj bledu w logice"));
  Serial.println(F("DR=HIGH ciagly -> modul utkniety, sprobuj reset przez PWR_PIN"));
}

void loop() {}