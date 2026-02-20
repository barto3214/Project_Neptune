"""
sensors.py - Dataclass + logika odczytu czujników
Importuj do głównego pliku zamiast pisać read_sensors() z globalnym słownikiem.
"""

import time
import glob
from dataclasses import dataclass, field
from datetime import datetime
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn


# ─── I2C / ADC ────────────────────────────────────────────────────────────────
i2c     = I2C(1)
ads     = ADS1115(i2c)
chan_ph  = AnalogIn(ads, 0)   # A0 - pH
chan_ec  = AnalogIn(ads, 1)   # A1 - EC
chan_tds = AnalogIn(ads, 2)   # A2 - TDS DFRobot


# ─── STAŁE KALIBRACYJNE ───────────────────────────────────────────────────────
CAL_PH1          = 4.1
CAL_VOLTAGE_PH1  = 0.88
CAL_PH3          = 9.1
CAL_VOLTAGE_PH3  = 1.43
_slope_ph        = (CAL_PH3 - CAL_PH1) / (CAL_VOLTAGE_PH3 - CAL_VOLTAGE_PH1)
_offset_ph       = CAL_PH1 - _slope_ph * CAL_VOLTAGE_PH1

CAL_VOLTAGE_DRY  = 0.003
CAL_VOLTAGE_SALT = 2.3585
CAL_EC_SALT      = 25000      # µS/cm

TEMP_SLOPE  = (16.0 - 0.0) / (21.0 - 2.5)
TEMP_OFFSET = 0.0 - TEMP_SLOPE * 2.5


# ─── FUNKCJE POMOCNICZE (prywatne) ────────────────────────────────────────────
def _voltage_to_ph(voltage: float) -> float:
    return _slope_ph * voltage + _offset_ph


def _read_ph_avg(samples: int = 20) -> float:
    """Pobierz próbki, odrzuć 20% skrajnych, uśrednij resztę."""
    readings = sorted(
        _voltage_to_ph(chan_ph.voltage)
        for _ in range(samples)
        if not time.sleep(0.05)  # side-effect: sleep między próbkami
    )
    cut = samples // 5
    trimmed = readings[cut:-cut]
    return sum(trimmed) / len(trimmed)


def _voltage_to_ec(voltage: float) -> float:
    if voltage <= CAL_VOLTAGE_DRY:
        return 0.0
    slope = CAL_EC_SALT / (CAL_VOLTAGE_SALT - CAL_VOLTAGE_DRY)
    return max(0.0, slope * (voltage - CAL_VOLTAGE_DRY))


def _read_ec_avg(samples: int = 10) -> float:
    readings = []
    for _ in range(samples):
        readings.append(_voltage_to_ec(chan_ec.voltage))
        time.sleep(0.02)
    readings.sort()
    trimmed = readings[1:-1]
    return sum(trimmed) / len(trimmed)


def _find_sensor() -> str | None:
    devices = glob.glob('/sys/bus/w1/devices/28*')
    if devices:
        print(f"Znaleziono czujnik temp: {devices[0].split('/')[-1]}")
        return devices[0] + '/w1_slave'
    print("Temp czujnik: BRAK - sprawdź połączenie GPIO4 i 1-Wire!")
    return None


_device_file = _find_sensor()


def _read_temp(retries: int = 5) -> float | None:
    if _device_file is None:
        return None
    for attempt in range(retries):
        try:
            with open(_device_file, 'r') as f:
                lines = f.readlines()
            if len(lines) >= 2 and 'YES' in lines[0]:
                temp_pos = lines[1].find('t=')
                if temp_pos != -1:
                    raw = float(lines[1][temp_pos + 2:].strip()) / 1000.0
                    return TEMP_SLOPE * raw + TEMP_OFFSET
            if attempt < retries - 1:
                time.sleep(0.2)
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.2)
    return None


def _voltage_to_tds(voltage: float, temperature: float = 25.0) -> float:
    compensation_coeff = 1.0 + 0.02 * (temperature - 25.0)
    v = voltage / compensation_coeff
    tds = (133.42 * v**3 - 255.86 * v**2 + 857.39 * v) * 0.5
    return max(0.0, tds)


# ─── DATACLASS ────────────────────────────────────────────────────────────────
@dataclass
class SensorData:
    ph:          float
    ec:          float        # µS/cm
    tds:         float        # ppm
    temperature: float | None
    timestamp:   datetime = field(default_factory=datetime.now)

    # ── fabryka: odczytaj wszystkie czujniki i zwróć gotowy obiekt ──
    @classmethod
    def read(cls) -> "SensorData":
        temp = _read_temp()
        return cls(
            ph          = _read_ph_avg(),
            ec          = _read_ec_avg(),
            tds         = _voltage_to_tds(
                            chan_tds.voltage,
                            temp if temp is not None else 25.0
                          ),
            temperature = temp,
        )

    # ── format do wysłania przez Serial do Arduino ──
    def to_serial_string(self, pump_state: bool = False) -> str:
        """DATA:ph,tds,temp,ec,pump  (format oczekiwany przez Arduino)"""
        t = self.temperature if self.temperature is not None else 0.0
        return f"DATA:{self.ph:.2f},{self.tds:.1f},{t:.1f},{self.ec:.1f},{1 if pump_state else 0}"

    # ── czytelny podgląd w terminalu ──
    def display(self) -> str:
        temp_str = f"{self.temperature:.1f}°C" if self.temperature is not None else "BRAK"
        return (
            f"pH: {self.ph:.2f} | "
            f"EC: {self.ec:.0f} µS/cm | "
            f"Temp: {temp_str} | "
            f"TDS: {self.tds:.0f} ppm"
        )

    # ── słownik (np. do JSON / logowania) ──
    def to_dict(self) -> dict:
        return {
            "ph":          round(self.ph, 2),
            "ec":          round(self.ec, 1),
            "tds":         round(self.tds, 1),
            "temperature": round(self.temperature, 1) if self.temperature else None,
            "timestamp":   self.timestamp.isoformat(),
        }