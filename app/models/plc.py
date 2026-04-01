"""
PLC (Programmable Logic Controller) Simulation
Implements ladder-logic style coils, contacts and rungs for an industrial
motor-drive system.  Also provides an alarm-management subsystem.
"""

from datetime import datetime, timezone
from collections import deque

# ---------------------------------------------------------------------------
# PLC coil / contact definitions
# ---------------------------------------------------------------------------
COILS = {
    "motor_run":        {"label": "Motor Run",          "address": "Q0.0", "state": False},
    "pump_run":         {"label": "Coolant Pump Run",   "address": "Q0.1", "state": False},
    "alarm_horn":       {"label": "Alarm Horn",         "address": "Q0.2", "state": False},
    "estop_latch":      {"label": "E-Stop Latch",       "address": "Q0.3", "state": False},
    "pressure_relief":  {"label": "Pressure Relief V.", "address": "Q0.4", "state": False},
    "lube_pump":        {"label": "Lube Pump",          "address": "Q0.5", "state": False},
}

CONTACTS = {
    "start_pb":         {"label": "Start PB",           "address": "I0.0", "state": False},
    "stop_pb":          {"label": "Stop PB",            "address": "I0.1", "state": True},
    "estop_pb":         {"label": "E-Stop PB",          "address": "I0.2", "state": True},
    "temp_sw":          {"label": "Temp OK Switch",     "address": "I0.3", "state": True},
    "pres_sw":          {"label": "Pressure OK Switch", "address": "I0.4", "state": True},
    "oil_level_sw":     {"label": "Oil Level OK Sw.",   "address": "I0.5", "state": True},
    "motor_overload":   {"label": "Motor Overload",     "address": "I0.6", "state": True},
}

ALARM_LOG_SIZE = 100

_PRIORITY = {"critical": 1, "warning": 2, "info": 3}


class PLCController:
    """Simulates a PLC controlling an industrial motor-drive system."""

    def __init__(self):
        self._coils = {k: dict(v) for k, v in COILS.items()}
        self._contacts = {k: dict(v) for k, v in CONTACTS.items()}
        self._alarm_log: deque = deque(maxlen=ALARM_LOG_SIZE)
        self._active_alarms: dict = {}
        self._machine_running = False
        self._tick = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self, sensor_data: dict):
        """Run one PLC scan cycle driven by current sensor data."""
        self._tick += 1
        self._update_contacts_from_sensors(sensor_data)
        self._run_ladder_logic()
        self._update_alarms(sensor_data)

    def start_machine(self):
        self._contacts["start_pb"]["state"] = True
        self._contacts["stop_pb"]["state"] = True
        self._contacts["estop_pb"]["state"] = True
        self._machine_running = True

    def stop_machine(self):
        self._contacts["stop_pb"]["state"] = False
        self._machine_running = False

    def emergency_stop(self):
        self._contacts["estop_pb"]["state"] = False
        self._contacts["stop_pb"]["state"] = False
        self._machine_running = False
        self._coils["estop_latch"]["state"] = True
        self._raise_alarm("ESTOP", "Emergency stop activated", "critical")

    def reset_estop(self):
        self._coils["estop_latch"]["state"] = False
        self._contacts["estop_pb"]["state"] = True
        self._resolve_alarm("ESTOP")

    def acknowledge_alarm(self, alarm_id: str):
        if alarm_id in self._active_alarms:
            self._active_alarms[alarm_id]["acknowledged"] = True

    def get_status(self) -> dict:
        return {
            "machine_running": self._machine_running,
            "coils": {k: {"label": v["label"], "address": v["address"], "state": v["state"]}
                      for k, v in self._coils.items()},
            "contacts": {k: {"label": v["label"], "address": v["address"], "state": v["state"]}
                         for k, v in self._contacts.items()},
            "active_alarms": list(self._active_alarms.values()),
            "alarm_log": list(self._alarm_log),
            "tick": self._tick,
        }

    # ------------------------------------------------------------------
    # Ladder logic rungs
    # ------------------------------------------------------------------

    def _run_ladder_logic(self):
        c = self._contacts
        q = self._coils

        # Rung 1 – Motor Run
        # Energise if: (Start OR Motor already running) AND Stop AND E-Stop
        #              AND Temp OK AND Pressure OK AND Oil OK AND No Overload
        #              AND NOT E-Stop Latch
        motor_can_run = (
            (c["start_pb"]["state"] or q["motor_run"]["state"])
            and c["stop_pb"]["state"]
            and c["estop_pb"]["state"]
            and c["temp_sw"]["state"]
            and c["pres_sw"]["state"]
            and c["oil_level_sw"]["state"]
            and c["motor_overload"]["state"]
            and not q["estop_latch"]["state"]
        )
        prev = q["motor_run"]["state"]
        q["motor_run"]["state"] = motor_can_run
        if motor_can_run and not prev:
            self._raise_alarm("MOTOR_START", "Motor started", "info")
        elif not motor_can_run and prev:
            self._raise_alarm("MOTOR_STOP", "Motor stopped", "info")

        # Rung 2 – Coolant Pump (runs whenever motor runs)
        q["pump_run"]["state"] = q["motor_run"]["state"]

        # Rung 3 – Lube Pump (runs whenever motor runs)
        q["lube_pump"]["state"] = q["motor_run"]["state"]

        # Rung 4 – Pressure Relief Valve (open when pressure switch trips)
        q["pressure_relief"]["state"] = not c["pres_sw"]["state"]

        # Rung 5 – Alarm Horn (any active unacknowledged alarm)
        unack = any(
            not a["acknowledged"] and a["priority"] in (1, 2)
            for a in self._active_alarms.values()
        )
        q["alarm_horn"]["state"] = unack

        # De-latch start pulse after one scan
        if c["start_pb"]["state"] and q["motor_run"]["state"]:
            c["start_pb"]["state"] = False

    # ------------------------------------------------------------------
    # Contact updates from live sensor data
    # ------------------------------------------------------------------

    def _update_contacts_from_sensors(self, sd: dict):
        c = self._contacts

        # Temperature interlock – trip if status is critical
        temp_status = sd.get("temperature", {}).get("status", "normal")
        c["temp_sw"]["state"] = temp_status != "critical"

        # Pressure interlock
        pres_status = sd.get("pressure", {}).get("status", "normal")
        c["pres_sw"]["state"] = pres_status != "critical"

        # Oil level interlock
        oil_status = sd.get("oil_level", {}).get("status", "normal")
        c["oil_level_sw"]["state"] = oil_status != "critical"

        # Motor overload (based on current)
        curr_status = sd.get("current", {}).get("status", "normal")
        c["motor_overload"]["state"] = curr_status != "critical"

    # ------------------------------------------------------------------
    # Alarm management
    # ------------------------------------------------------------------

    def _raise_alarm(self, alarm_id: str, message: str, priority: str):
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        alarm = {
            "id": alarm_id,
            "message": message,
            "priority": _PRIORITY.get(priority, 3),
            "priority_label": priority,
            "timestamp": ts,
            "acknowledged": False,
            "active": True,
        }
        self._active_alarms[alarm_id] = alarm
        self._alarm_log.appendleft(dict(alarm))

    def _resolve_alarm(self, alarm_id: str):
        if alarm_id in self._active_alarms:
            self._active_alarms[alarm_id]["active"] = False
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            self._active_alarms[alarm_id]["resolved_at"] = ts
            del self._active_alarms[alarm_id]

    def _update_alarms(self, sd: dict):
        sensor_alarm_map = {
            "temperature": ("TEMP_HIGH", "High Temperature"),
            "pressure":    ("PRES_HIGH", "High Pressure"),
            "vibration":   ("VIB_HIGH",  "High Vibration"),
            "current":     ("CURR_HIGH", "High Motor Current"),
            "rpm":         ("RPM_HIGH",  "High RPM"),
            "oil_level":   ("OIL_LOW",   "Low Oil Level"),
        }
        for sensor, (aid, msg) in sensor_alarm_map.items():
            status = sd.get(sensor, {}).get("status", "normal")
            if status in ("warning", "critical"):
                self._raise_alarm(aid, f"{msg} [{status.upper()}]", status)
            else:
                self._resolve_alarm(aid)
