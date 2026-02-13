import spidev
import RPi.GPIO as GPIO
import time

CE_PIN = 17
TXEN_PIN = 27
SPI_BUS = 0
SPI_DEVICE = 0

GPIO.setmode(GPIO.BCM)
GPIO.setup(CE_PIN, GPIO.OUT)
GPIO.setup(TXEN_PIN, GPIO.OUT)
GPIO.output(CE_PIN, GPIO.LOW)
GPIO.output(TXEN_PIN, GPIO.LOW)

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = 200000
spi.mode = 0

print("=" * 60)
print("TEST WYKRYWANIA PASMA nRF905")
print("=" * 60)

# Test 1: Próba konfiguracji 433MHz
print("\n[TEST 1] Konfiguracja dla 433MHz...")
GPIO.output(CE_PIN, GPIO.LOW)
time.sleep(0.01)

config_433 = [
    0x00,  # W_CONFIG
    108,   # Kanał dla testu
    0x0C,  # HFREQ_PLL=0 (433MHz), PA_PWR=11
    0x44, 4, 4,
    0xE7, 0xE7, 0xE7, 0xE7,
    0xDB
]

spi.xfer2(config_433)
time.sleep(0.02)

result = spi.xfer2([0x10] + [0x00] * 10)
config = result[1:]

freq_433 = 422.4 + (0.1 * config[0])
bit_hfreq = config[1] & 0x01

print(f"  Bajt Config[1]: 0x{config[1]:02X} (bit HFREQ_PLL={bit_hfreq})")
print(f"  Obliczona częstotliwość: {freq_433:.1f} MHz")

if bit_hfreq == 0:
    print(f"  ✓ Moduł akceptuje pasmo 433MHz")
    band_433_ok = True
else:
    print(f"  ✗ Moduł wymusza pasmo 868/915MHz")
    band_433_ok = False

# Test 2: Próba konfiguracji 868MHz
print("\n[TEST 2] Konfiguracja dla 868MHz...")
GPIO.output(CE_PIN, GPIO.LOW)
time.sleep(0.01)

config_868 = [
    0x00,
    54,    # Kanał dla testu
    0x0D,  # HFREQ_PLL=1 (868/915MHz), PA_PWR=11
    0x44, 4, 4,
    0xE7, 0xE7, 0xE7, 0xE7,
    0xDB
]

spi.xfer2(config_868)
time.sleep(0.02)

result = spi.xfer2([0x10] + [0x00] * 10)
config = result[1:]

freq_868 = 844.8 + (0.2 * config[0])
bit_hfreq = config[1] & 0x01

print(f"  Bajt Config[1]: 0x{config[1]:02X} (bit HFREQ_PLL={bit_hfreq})")
print(f"  Obliczona częstotliwość: {freq_868:.1f} MHz")

if bit_hfreq == 1:
    print(f"  ✓ Moduł akceptuje pasmo 868/915MHz")
    band_868_ok = True
else:
    print(f"  ✗ Moduł wymusza pasmo 433MHz")
    band_868_ok = False

# Wnioski
print("\n" + "=" * 60)
print("WYNIK:")
print("=" * 60)

if band_433_ok and not band_868_ok:
    print("▶ TEN MODUŁ TO: nRF905-433 (433 MHz)")
    print("  Antena powinna mieć ~17 cm")
elif band_868_ok and not band_433_ok:
    print("▶ TEN MODUŁ TO: nRF905-868/915 (868-915 MHz)")
    print("  Antena powinna mieć ~8-9 cm")
elif band_433_ok and band_868_ok:
    print("▶ Moduł akceptuje OBA pasma (nietypowe)")
    print("  Sprawdź fizyczną długość anteny!")
else:
    print("▶ BŁĄD: Moduł nie akceptuje żadnego pasma")

GPIO.cleanup()
spi.close()

print("\n" + "=" * 60)
print("INSTRUKCJA:")
print("=" * 60)
print("1. Uruchom ten test na OBUMODUŁ")
print("2. Zmierz długość anten na obu modułach")
print("3. Porównaj wyniki - muszą być IDENTYCZNE!")
print("=" * 60)