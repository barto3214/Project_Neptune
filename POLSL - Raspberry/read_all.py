import time
import glob
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# === I2C ===
i2c = I2C(1)
ads = ADS1115(i2c)

chan_ph  = AnalogIn(ads, 0)  # A0 - czujnik pH
chan_ec  = AnalogIn(ads, 1)  # A1 - czujnik przewodności
chan_tds = AnalogIn(ads, 2)  # A2 - czujnik TDS DFRobot

# === KALIBRACJA pH ===
CAL_PH1         = 4.1
CAL_VOLTAGE_PH1 = 0.88
CAL_PH3         = 9.1
CAL_VOLTAGE_PH3 = 1.43

slope_ph  = (CAL_PH3 - CAL_PH1) / (CAL_VOLTAGE_PH3 - CAL_VOLTAGE_PH1)
offset_ph = CAL_PH1 - slope_ph * CAL_VOLTAGE_PH1

def voltage_to_ph(voltage):
    return slope_ph * voltage + offset_ph

def read_ph_avg(samples=20):
    """Pobierz 20 próbek, odrzuć 20% skrajnych, uśrednij resztę"""
    readings = []
    for _ in range(samples):
        readings.append(voltage_to_ph(chan_ph.voltage))
        time.sleep(0.05)
    readings.sort()
    # Odrzuć skrajne wartości (20% z każdej strony)
    cut = samples // 5
    trimmed = readings[cut:-cut]
    return sum(trimmed) / len(trimmed)

# === KALIBRACJA EC ===
CAL_VOLTAGE_DRY  = 0.003
CAL_VOLTAGE_SALT = 2.3585
CAL_EC_SALT      = 25000  # µS/cm

def voltage_to_ec(voltage):
    if voltage <= CAL_VOLTAGE_DRY:
        return 0
    slope = CAL_EC_SALT / (CAL_VOLTAGE_SALT - CAL_VOLTAGE_DRY)
    return max(0, slope * (voltage - CAL_VOLTAGE_DRY))

def ec_to_tds_ec(ec):
    return ec * 0.5

def read_ec_avg(samples=10):
    readings = []
    for _ in range(samples):
        readings.append(voltage_to_ec(chan_ec.voltage))
        time.sleep(0.02)
    readings.sort()
    trimmed = readings[1:-1]
    return sum(trimmed) / len(trimmed)

# === TEMPERATURA (DS18B20) ===
TEMP_SLOPE  = (16.0 - 0.0) / (21.0 - 2.5)
TEMP_OFFSET = 0.0 - TEMP_SLOPE * 2.5

def find_sensor():
    devices = glob.glob('/sys/bus/w1/devices/28*')
    if devices:
        print(f"Znaleziono czujnik temp: {devices[0].split('/')[-1]}")
        return devices[0] + '/w1_slave'
    print("Temp czujnik: BRAK - sprawdź połączenie GPIO4 i 1-Wire!")
    return None

device_file = find_sensor()

def read_temp(retries=5):
    if device_file is None:
        return None
    for attempt in range(retries):
        try:
            with open(device_file, 'r') as f:
                lines = f.readlines()
            if len(lines) >= 2 and 'YES' in lines[0]:
                temp_pos = lines[1].find('t=')
                if temp_pos != -1:
                    raw = float(lines[1][temp_pos+2:].strip()) / 1000.0
                    return TEMP_SLOPE * raw + TEMP_OFFSET
            if attempt < retries - 1:
                time.sleep(0.2)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.2)
    return None

# === TDS DFRobot ===
def voltage_to_tds(voltage, temperature=25.0):
    compensation_coeff = 1.0 + 0.02 * (temperature - 25.0)
    voltage_comp = voltage / compensation_coeff
    tds = (133.42 * voltage_comp**3
         - 255.86 * voltage_comp**2
         + 857.39 * voltage_comp) * 0.5
    return max(0, tds)

# === START ===
print("\n=== POMIAR WSZYSTKICH CZUJNIKÓW ===")
print("Ctrl+C aby zakończyć\n")

try:
    while True:
        # pH (filtr medianowy z 20 próbek)
        ph = read_ph_avg()

        # EC (uśrednione)
        ec = read_ec_avg()

        # Temperatura
        temp     = read_temp()
        temp_str = f"{temp:.1f}°C" if temp is not None else "BRAK"

        # TDS DFRobot
        v_tds = chan_tds.voltage
        tds   = voltage_to_tds(v_tds, temp if temp is not None else 25.0)

        print(
            f"pH: {ph:.2f} | "
            f"EC: {ec:.0f} µS/cm | "
            f"Temp: {temp_str} | "
            f"TDS: {tds:.0f} ppm  ",
            end='\r'
        )
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n\nZakończono pomiar")