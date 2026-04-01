"""
Sensor Data Simulator
Simulates industrial machine sensors: temperature, pressure, vibration,
current draw, RPM, and oil level. Supports normal operation, degradation
drift and injected faults for demo / testing.
"""

import time
import random
import math
from collections import deque
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Sensor configuration
# ---------------------------------------------------------------------------
SENSORS = {
    "temperature": {
        "unit": "°C",
        "normal": (60.0, 80.0),
        "warning": (80.0, 95.0),
        "critical": (95.0, 120.0),
        "baseline": 70.0,
        "noise": 1.5,
    },
    "pressure": {
        "unit": "bar",
        "normal": (2.0, 4.0),
        "warning": (4.0, 5.0),
        "critical": (5.0, 7.0),
        "baseline": 3.0,
        "noise": 0.15,
    },
    "vibration": {
        "unit": "mm/s",
        "normal": (0.0, 2.5),
        "warning": (2.5, 4.0),
        "critical": (4.0, 8.0),
        "baseline": 1.2,
        "noise": 0.2,
    },
    "current": {
        "unit": "A",
        "normal": (8.0, 12.0),
        "warning": (12.0, 15.0),
        "critical": (15.0, 20.0),
        "baseline": 10.0,
        "noise": 0.4,
    },
    "rpm": {
        "unit": "RPM",
        "normal": (1400.0, 1600.0),
        "warning": (1600.0, 1800.0),
        "critical": (1800.0, 2200.0),
        "baseline": 1500.0,
        "noise": 15.0,
    },
    "oil_level": {
        "unit": "%",
        "normal": (60.0, 100.0),
        "warning": (30.0, 60.0),
        "critical": (0.0, 30.0),
        "baseline": 85.0,
        "noise": 0.5,
    },
}

HISTORY_SIZE = 300  # data-points kept in rolling buffer


class SensorSimulator:
    """Simulates all machine sensors and maintains a rolling history."""

    def __init__(self):
        self._values = {k: cfg["baseline"] for k, cfg in SENSORS.items()}
        self._history = {k: deque(maxlen=HISTORY_SIZE) for k in SENSORS}
        self._drift = {k: 0.0 for k in SENSORS}
        self._fault_active = False
        self._fault_sensor = None
        self._machine_running = True
        self._tick = 0
        # Seed the history with a few normal readings so charts render
        # immediately on startup.
        for _ in range(30):
            self._update_values()
            self._record_history()
        self._tick = 0  # reset tick after seeding

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def read(self) -> dict:
        """Return the latest sensor reading snapshot."""
        if self._machine_running:
            self._tick += 1
            self._update_values()
            self._record_history()
        return self._snapshot()

    def get_history(self, sensor: str, n: int = 60) -> list:
        """Return the last *n* history entries for one sensor."""
        if sensor not in self._history:
            return []
        buf = list(self._history[sensor])
        return buf[-n:]

    def get_all_history(self, n: int = 60) -> dict:
        return {k: self.get_history(k, n) for k in SENSORS}

    def inject_fault(self, sensor: str, magnitude: float = 2.0):
        """Inject an artificial fault into a sensor."""
        if sensor in SENSORS:
            self._fault_active = True
            self._fault_sensor = sensor
            self._drift[sensor] += magnitude * (SENSORS[sensor]["noise"] * 10)

    def clear_fault(self):
        self._fault_active = False
        self._fault_sensor = None
        for k in SENSORS:
            self._drift[k] = 0.0

    def set_machine_running(self, running: bool):
        self._machine_running = running

    @property
    def machine_running(self) -> bool:
        return self._machine_running

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_values(self):
        t = self._tick
        for name, cfg in SENSORS.items():
            baseline = cfg["baseline"]
            noise = cfg["noise"]

            # Slow sinusoidal drift to mimic real-world variation
            slow_wave = math.sin(t * 0.05) * noise * 0.8
            fast_noise = random.gauss(0, noise * 0.3)

            # Gradual degradation over time (very slow)
            degradation = self._drift[name]

            new_val = baseline + slow_wave + fast_noise + degradation

            # Oil level decreases very slowly when machine is running
            if name == "oil_level":
                self._drift[name] -= 0.002
                # Refill when critically low
                if self._values[name] < 20:
                    self._drift[name] = 0.0
                    self._values[name] = cfg["baseline"]

            self._values[name] = round(new_val, 2)

    def _record_history(self):
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for name in SENSORS:
            self._history[name].append(
                {"timestamp": ts, "value": self._values[name]}
            )

    def _snapshot(self) -> dict:
        result = {}
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for name, cfg in SENSORS.items():
            val = self._values[name]
            status = _classify(name, val)
            result[name] = {
                "value": val,
                "unit": cfg["unit"],
                "status": status,
                "timestamp": ts,
                "limits": {
                    "normal_min": cfg["normal"][0],
                    "normal_max": cfg["normal"][1],
                    "warning_max": cfg["warning"][1],
                    "critical_max": cfg["critical"][1],
                },
            }
        return result


def _classify(sensor: str, value: float) -> str:
    cfg = SENSORS[sensor]
    # For oil_level lower is worse; for all others higher is worse.
    if sensor == "oil_level":
        # warning range upper bound marks transition to normal
        if value < cfg["critical"][1]:   # below top of critical band
            return "critical"
        if value < cfg["warning"][1]:    # below top of warning band
            return "warning"
        return "normal"
    else:
        # warning range lower bound marks start of warning zone
        if value >= cfg["critical"][0]:  # at or above bottom of critical band
            return "critical"
        if value >= cfg["warning"][0]:   # at or above bottom of warning band
            return "warning"
        return "normal"
