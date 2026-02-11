import time
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(3, 2)  # SCL=GPIO3, SDA=GPIO2
ads = ADS1115(i2c)
chan_ec = AnalogIn(ads, 1)  # A1

# === KALIBRACJA EC/TDS ===
CAL_VOLTAGE_DRY = 0.003      # Napięcie na powietrzu
CAL_VOLTAGE_SALT = 2.3585    # Napięcie w roztworze soli
CAL_EC_SALT = 25000          # EC roztworu soli (µS/cm)

def voltage_to_ec(voltage):
    if voltage <= CAL_VOLTAGE_DRY:
        return 0
    # Nachylenie: zmiana EC / zmiana napięcia
    slope = (CAL_EC_SALT - 0) / (CAL_VOLTAGE_SALT - CAL_VOLTAGE_DRY)
    ec = slope * (voltage - CAL_VOLTAGE_DRY)
    return max(0, ec)

def ec_to_tds(ec_us_cm):
    # TDS (ppm) = EC (µS/cm) × 0.5
    return ec_us_cm * 0.5

print("=== POMIAR PRZEWODNOŚCI (EC/TDS) ===")
print(f"Kalibracja: 0 µS/cm @ {CAL_VOLTAGE_DRY}V, {CAL_EC_SALT} µS/cm @ {CAL_VOLTAGE_SALT}V")
print(f"Nachylenie: {CAL_EC_SALT / (CAL_VOLTAGE_SALT - CAL_VOLTAGE_DRY):.0f} µS/cm na Volt\n")
print("Ctrl+C aby zakończyć\n")

try:
    while True:
        ec = voltage_to_ec(v)
        tds = ec_to_tds(ec)
        
        print(f" EC: {ec:.0f} µS/cm | TDS: {tds:.0f} ppm  ", end='\r')
        time.sleep(0.5)
        
except KeyboardInterrupt:
    print("\n\nZakończono pomiar EC/TDS")