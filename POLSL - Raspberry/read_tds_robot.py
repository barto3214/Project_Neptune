import time
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# I2C bus 1 bezpośrednio
i2c = I2C(1)
ads = ADS1115(i2c)
chan_tds = AnalogIn(ads, 2)  # A2

SENSOR_ID = '28-000010aa60a2'
device_file = f'/sys/bus/w1/devices/{SENSOR_ID}/w1_slave'

def read_temp(retries=5):
    for attempt in range(retries):
        try:
            with open(device_file, 'r') as f:
                lines = f.readlines()
            if len(lines) >= 2 and 'YES' in lines[0]:
                temp_pos = lines[1].find('t=')
                if temp_pos != -1:
                    raw = float(lines[1][temp_pos+2:].strip()) / 1000.0
                    slope = (16.0 - 0.0) / (21.0 - 2.5)
                    offset = 0.0 - slope * 2.5
                    return slope * raw + offset
            if attempt < retries - 1:
                time.sleep(0.2)
        except:
            if attempt < retries - 1:
                time.sleep(0.2)
    return 25.0

def voltage_to_tds(voltage, temperature=25.0):
    compensation_coeff = 1.0 + 0.02 * (temperature - 25.0)
    voltage_comp = voltage / compensation_coeff
    tds = (133.42 * voltage_comp**3
         - 255.86 * voltage_comp**2
         + 857.39 * voltage_comp) * 0.5
    return max(0, tds)

print("=== POMIAR TDS Z KOMPENSACJĄ TEMPERATURY ===")
print("Ctrl+C aby zakończyć\n")

try:
    while True:
        v = chan_tds.voltage
        temp = read_temp()
        tds = voltage_to_tds(v, temp)
        print(f"V: {v:.3f}V | Temp: {temp:.1f}°C | TDS: {tds:.0f} ppm  ", end='\r')
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n\nZakończono pomiar TDS")