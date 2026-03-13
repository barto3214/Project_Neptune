# 🌊 Project Neptune — Autonomous Water Sampling Boat

> Autonomous water quality monitoring system with a 6-position sample carousel, real-time telemetry over 433 MHz radio, and live camera feed.

![C#](https://img.shields.io/badge/C%23-.NET%208.0-purple?logo=dotnet)
![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Arduino](https://img.shields.io/badge/Arduino-Nano-teal?logo=arduino)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-red?logo=raspberrypi)
![Radio](https://img.shields.io/badge/Radio-NRF905%20433MHz-orange)

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Hardware Components](#hardware-components)
- [Repository Structure](#repository-structure)
- [Software Modules](#software-modules)
- [Communication Protocol](#communication-protocol)
- [WPF Ground Station](#wpf-ground-station)
- [Getting Started](#getting-started)
- [Calibration](#calibration)
- [Water Quality Algorithm](#water-quality-algorithm)
- [Unit Tests](#unit-tests)

---

## Overview

Project Neptune is a school engineering project developed at **Zespół Szkół nr 10 im. prof. Janusza Groszkowskiego w Zabrzu** in cooperation with **Politechnika Śląska (RAU3)**. The system allows remote collection and real-time analysis of water quality samples from lakes, rivers, and reservoirs.

A remotely controlled boat carries a rotating carousel of 6 test tubes. Sensors (pH, TDS, temperature, conductivity) are immersed in each sample in turn, and the results stream wirelessly to a Windows PC application. The operator controls the boat using WASD keys while watching a live 64 MP camera feed.

**Key features:**
- 6-position sample carousel with quadrature encoder feedback (HEDL-5540-A12)
- Water quality sensors: pH, TDS, temperature (DS18B20), conductivity (EC)
- 433 MHz NRF905 radio link (up to ~150 m open water)
- Live 1280×720 MJPEG video stream over Wi-Fi
- WPF desktop application with dockable panels, live charts (LiveCharts), and data history
- SQLite local logging on the boat
- Battery voltage monitoring (INA219)
- WASD boat control with 500 ms safety watchdog

---

## System Architecture

```
┌─────────────────────────────┐         ┌─────────────────────────┐
│   Windows PC (WPF App)      │         │   RPi #1 — Base Station │
│                             │◄──TCP───│                         │
│  • Live charts (LiveCharts) │  JSON   │   base_station.py       │
│  • Data table (150 records) │  WiFi   │   TCP server :5000      │
│  • Camera stream viewer     │         │   NRF905 transceiver    │
│  • WSAD boat control        │         │   (SPI + GPIO)          │
│  • Command buttons          │         └───────────┬─────────────┘
│                             │                     │  NRF905
│  CameraWindow ──────────────┼──── HTTP ───────────┤  433 MHz
│  (MJPEG :8080)              │     WiFi            │  half-duplex
└─────────────────────────────┘                     │
                                         ┌───────────▼─────────────┐
                                         │   Arduino Nano          │
                                         │   nrf905_transmitter    │
                                         │   Cytron MDD20A driver  │
                                         │   Watchdog 500 ms       │
                                         └───────────┬─────────────┘
                                                     │  Serial 115200
                                         ┌───────────▼─────────────┐
                                         │   RPi #2 — Boat Station │
                                         │   master.py             │
                                         │   Sensors / Carousel    │
                                         │   MJPEG server :8080    │
                                         │   SQLite (pomiary.db)   │
                                         └─────────────────────────┘
```

---

## Hardware Components

| Component | Role |
|---|---|
| Raspberry Pi 4 (#1) | Base station — NRF905 transceiver, TCP server |
| Raspberry Pi 4 (#2) | Boat — sensors, carousel control, camera server |
| Arduino Nano | RF-to-Serial relay, motor driver interface |
| NRF905 (×2) | 433 MHz radio, 32-byte packets, ~150 m range |
| ArduCam 64MP (CSI) | MJPEG camera on RPi #2 |
| TP-Link T3U Plus | USB Wi-Fi adapter on RPi #2 (RTL8822BU) |
| ADS1115 | 16-bit ADC — pH, TDS, EC sensors |
| INA219 | Battery voltage monitor (I2C, shared bus with ADS) |
| DS18B20 | 1-Wire temperature sensor |
| 28BYJ-48 + ULN2003 | Stepper motor for carousel rotation |
| HEDL-5540-A12 | 500 CPR quadrature encoder for carousel |
| MG995 Servo | Needle positioning (sample/retract) |
| IRF520 MOSFET (×2) | Pump control (GPIO 24 & 25, 12 V) |
| Cytron MDD20A | Dual motor driver for boat propulsion |

---

## Repository Structure

```
Project_Neptune/
│
├── POLSL - Raspberry/          # RPi #2 — Boat software
│   ├── master.py               # Main program (sensors, carousel, camera, serial)
│   ├── sensors.py              # Sensor reading module
│   ├── carousele_calibration.py# Interactive calibration tool
│   ├── camera_stream.py        # MJPEG server prototype
│   ├── read_ph.py              # pH diagnostic
│   ├── read_tds_robot.py       # TDS diagnostic
│   ├── read_temp.py            # Temperature diagnostic
│   ├── read_cond.py            # Conductivity diagnostic
│   ├── read_all.py             # All sensors at once
│   ├── test_telemetrii.py      # Telemetry test
│   ├── VCC_measure_test.py     # Voltage test
│   ├── GNSS_calibration.py     # GPS calibration utility
│   └── pomiary.db              # SQLite database (auto-created)
│
├── ja8 - Raspberry/            # RPi #1 — Base station software
│   └── base_station.py         # NRF905 RX/TX + TCP server
│
├── nrf905_transmitter/         # Arduino firmware
│   ├── nrf905_transmitter.ino  # Main sketch
│   └── diagnoza/
│       └── diagnoza.ino        # Diagnostic sketch
│
├── PN_groundStation/           # Windows WPF application (C#)
│   ├── PN_Ground_Station/      # Main project
│   │   ├── MainWindow.xaml/.cs
│   │   ├── TcpDataClient.cs
│   │   ├── SensorData.cs
│   │   ├── EngineController.cs (BoatController)
│   │   └── Dock Windows/
│   │       ├── CameraWindow.xaml/.cs
│   │       ├── ChartsWindow.xaml/.cs
│   │       ├── ControlsWindow.xaml/.cs
│   │       └── DataGridWindow.xaml/.cs
│   ├── PN_Ground_StationTests/ # Unit tests (MSTest)
│   │   └── SensorDataTests.cs
│   └── NetDock/                # Custom docking library
│       ├── DockSurface.cs
│       ├── DockItem.cs
│       └── DockWindow.cs
│
└── pinout.txt                  # GPIO reference
```

---

## Software Modules

### RPi #2 — `master.py`

The main program for the boat. Runs 5 daemon threads simultaneously:

| Thread | Frequency | Function |
|---|---|---|
| `serial_listener()` | continuous | Receives commands from Arduino via Serial |
| `measurement_loop()` | every 2 s | Reads all sensors during active measurement |
| `_encoder_poll_loop()` | 10 kHz | Polls HEDL-5540 GPIO for carousel positioning |
| `camera_capture_loop()` | ~30 fps | Extracts JPEG frames from rpicam-vid |
| `camera_server_loop()` | on demand | HTTP/MJPEG server on port 8080 |

**GPIO pinout (RPi #2):**

| GPIO (BCM) | Physical | Device |
|---|---|---|
| GPIO 4 | Pin 7 | DS18B20 (1-Wire) |
| GPIO 17/27/22/23 | 11/13/15/16 | 28BYJ-48 stepper (IN1–IN4) |
| GPIO 24 | Pin 18 | MOSFET pump 1 |
| GPIO 25 | Pin 22 | MOSFET pump 2 |
| GPIO 18 | Pin 12 | Servo MG995 (PWM 50 Hz) |
| GPIO 16/20/21 | 36/38/40 | HEDL-5540 (A / B / Index) |
| I2C SDA/SCL | Pin 3/5 | ADS1115 + INA219 |
| USB `/dev/ttyUSB0` | USB | Arduino Nano (Serial 115200) |

### RPi #1 — `base_station.py`

TCP server on port 5000. Receives sensor data packets from Arduino via NRF905 and forwards them as JSON to the WPF application. Also receives JSON commands from WPF and transmits them as 32-byte NRF905 packets to Arduino.

**NRF905 GPIO (RPi #1):**
- CE → GPIO 17, TX_EN → GPIO 27, DR → GPIO 22, PWR → GPIO 23, SPI0

### Arduino — `nrf905_transmitter.ino`

Full-duplex relay between NRF905 and RPi #2 via Serial. Also directly drives the Cytron MDD20A motor controller.

- **CMD_BOAT_DRIVE**: immediately sets motor speed without waiting for RPi #2
- **Watchdog**: no `CMD_BOAT_DRIVE` for 500 ms → automatic stop

**Arduino pinout:**
```
NRF905: CSN=D10, CE=D9, PWR=D8, TX_EN=D7, DR=D5
Motors: LEFT_PWM=D3, LEFT_DIR=D2, RIGHT_PWM=D6, RIGHT_DIR=D4
Serial: TX→RPi GPIO15, RX→RPi GPIO14
```

---

## Communication Protocol

### NRF905 packet — Command (32 bytes, PC → boat)

```c
struct CommandPacket {
  uint8_t  command;    // 0x01–0x07, 0x20
  uint16_t param1;     // e.g. measurement duration [s]
  uint16_t param2;     // e.g. right motor speed
  uint32_t timestamp;
  uint8_t  reserved[22];
  uint8_t  crc;
};
```

| Code | Command | Description |
|---|---|---|
| `0x01` | `CMD_MEASURE_START` | Start measurement for `param1` seconds |
| `0x02` | `CMD_MEASURE_STOP` | Stop active measurement |
| `0x03` | `CMD_PUMP_ON` | Turn on pump 1 (fill tank) |
| `0x04` | `CMD_PUMP_OFF` | Turn off pump 1 |
| `0x05` | `CMD_STATUS_REQUEST` | Request status packet |
| `0x06` | `CMD_SAMPLES_LOADING` | Load sample sequence (pump 2 + servo + carousel) |
| `0x07` | `CMD_REJECT_SAMPLE` | Reject sample (pump 2 + reject position) |
| `0x20` | `CMD_BOAT_DRIVE` | Drive: `param1`=left motor, `param2`=right (0–200, 100=stop) |

### TCP JSON — sensor data packet

```json
{
  "station_id": 1,
  "ph": 7.24,
  "tds": 183.5,
  "temperature": 18.3,
  "conductivity": 367.1,
  "timestamp": 3600,
  "battery_voltage": 12.41,
  "error_flags": 0,
  "received_at": "2025-09-15T14:23:01"
}
```

### TCP JSON — command (PC → RPi #1)

```json
{"command": "boat_drive", "param1": 190, "param2": 190, "timestamp": "..."}
```

---

## WPF Ground Station

Built with .NET 8.0 / WPF. Uses **LiveCharts** for real-time plots and a custom **NetDock** library for dockable panels.

### Dockable panels

| Panel | Default position | Contents |
|---|---|---|
| 📷 Camera | Left | Live MJPEG stream from boat camera |
| 📊 Charts | Top-right | Real-time line charts: pH, TDS, temperature, EC |
| ⚙️ Controls | Bottom-left | Sensor readouts, command buttons, WSAD control |
| 📜 Data History | Right | Scrollable table of last 150 measurements |

### WSAD boat control

| Keys | Left motor | Right motor | Motion |
|---|---|---|---|
| W | +90 → 190 | +90 → 190 | Forward |
| S | −90 → 10 | −90 → 10 | Reverse |
| A | −90 → 10 | +90 → 190 | Rotate left |
| D | +90 → 190 | −90 → 10 | Rotate right |
| W+A | 120 | 180 | Arc left forward |
| W+D | 180 | 120 | Arc right forward |
| S+A | 80 | 20 | Arc left reverse |
| S+D | 20 | 80 | Arc right reverse |
| Space | 100 | 100 | Emergency stop |

Click **Activate WSAD Control** in the Controls panel, then click inside the panel to focus it before steering.

### Camera stream

Enter the boat's IP address in the Camera panel and click **Connect**. The URL used is `http://<IP>:8080/stream`.

---

## Getting Started

### Prerequisites

- **RPi #2 (boat):** Raspberry Pi OS (64-bit), Python 3.13+
- **RPi #1 (base):** Raspberry Pi OS (64-bit), Python 3.13+
- **Arduino:** Arduino IDE 2.x
- **PC:** Windows 10/11, .NET 8.0 SDK, Visual Studio 2022

### RPi #2 setup

```bash
# Install Python dependencies
pip install RPi.GPIO adafruit-circuitpython-ads1x15 \
            adafruit-circuitpython-ina219 adafruit-extended-bus \
            --break-system-packages

# Run calibration first
python3 carousele_calibration.py

# Then run the main program
python3 master.py
```

Enable I2C and 1-Wire in `raspi-config` → Interface Options.

### RPi #1 setup

```bash
pip install RPi.GPIO spidev --break-system-packages
python3 base_station.py
```

Enable SPI in `raspi-config` → Interface Options.

### Arduino

Open `nrf905_transmitter/nrf905_transmitter.ino` in Arduino IDE and upload to Arduino Nano (board: *Arduino Nano*, processor: *ATmega328P (Old Bootloader)*).

### WPF Application

```bash
cd PN_groundStation/PN_Ground_Station
dotnet build
dotnet run --project PN_Ground_Station
```

Or open `PN_Ground_Station.sln` in Visual Studio 2022 and press **F5**.

In the app: enter RPi #1's IP address and port **5000**, click **Connect**.

---

## Calibration

Run `carousele_calibration.py` on RPi #2 before first use:

| Option | Mode | What it sets |
|---|---|---|
| 1 | Servo calibration | `SERVO_UP` and `SERVO_DOWN` duty cycle values |
| 2 | Stepper (steps) | `STEPS_PER_POSITION` — fallback mode without encoder |
| 3 | Stepper (ticks) | `TICKS_PER_POSITION` — main encoder-based positioning |
| 4 | Full sequence | End-to-end test of the complete sample loading cycle |

After calibration, update the constants at the top of `master.py`:

```python
TICKS_PER_POSITION = 165  # from option 3
SERVO_UP  = 11.7          # from option 1
SERVO_DOWN = 2.5          # from option 1
```

---

## Water Quality Algorithm

`SensorData.GetWaterQuality()` uses a weighted scoring system:

| Parameter | Weight | Scoring |
|---|---|---|
| pH | 40 pts | pH < 4.0 or > 10.0 → **CRITICAL**; 6.5–8.5 → 40 pts; 6.0–9.0 → 20 pts |
| TDS | 35 pts | TDS > 1000 → **UNACCEPTABLE**; ≤ 150 → 35 pts; ≤ 300 → 30 pts; ≤ 600 → 15 pts |
| EC | 25 pts | EC > 2000 → −20 pts; ≤ 600 → 25 pts; ≤ 1200 → 15 pts |

**Final rating:**

| Score | Result |
|---|---|
| < 0 (critical flag) | CRITICAL |
| < 30 | UNACCEPTABLE |
| < 50 | POOR |
| < 70 | ACCEPTABLE |
| < 90 | GOOD |
| ≥ 90 | EXCELLENT |

---

## Unit Tests

The `PN_Ground_StationTests` project contains **16 MSTest unit tests** for `GetWaterQuality()`:

```bash
cd PN_groundStation/PN_Ground_Station
dotnet test
```

Test coverage includes: CRITICAL (pH out of range), UNACCEPTABLE (high TDS), POOR, ACCEPTABLE, GOOD, EXCELLENT, boundary values (pH=4.0, TDS=50), priority (CRITICAL pH overrides excellent TDS), and all-zeros edge case.

---

## Authors

**Ślusarz Bartłomiej(code), Moj Cyprian(models 3D), Sot Krzysztof(electronics)**  
Klasa IV, Technik Programista  
Zespół Szkół nr 10 im. prof. Janusza Groszkowskiego w Zabrzu  
we współpracy z Politechniką Śląską — Katedra Automatyki i Robotyki (RAU3)
