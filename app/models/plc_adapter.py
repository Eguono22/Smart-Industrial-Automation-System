"""
PLC adapter layer.
Provides a simulation adapter and an optional Modbus TCP bridge for
industrial PLC integration.
"""

import os
from abc import ABC, abstractmethod

from app.models.plc import PLCController

try:
    from pymodbus.client import ModbusTcpClient

    PYMODBUS_AVAILABLE = True
except ImportError:
    PYMODBUS_AVAILABLE = False


COIL_ADDR = {
    "motor_run": 0,
    "pump_run": 1,
    "alarm_horn": 2,
    "estop_latch": 3,
    "pressure_relief": 4,
    "lube_pump": 5,
}

COIL_ENV_KEYS = {
    "motor_run": "PLC_COIL_MOTOR_RUN",
    "pump_run": "PLC_COIL_PUMP_RUN",
    "alarm_horn": "PLC_COIL_ALARM_HORN",
    "estop_latch": "PLC_COIL_ESTOP_LATCH",
    "pressure_relief": "PLC_COIL_PRESSURE_RELIEF",
    "lube_pump": "PLC_COIL_LUBE_PUMP",
}


class PLCAdapter(ABC):
    @abstractmethod
    def update(self, sensor_data: dict):
        raise NotImplementedError

    @abstractmethod
    def start_machine(self):
        raise NotImplementedError

    @abstractmethod
    def stop_machine(self):
        raise NotImplementedError

    @abstractmethod
    def emergency_stop(self):
        raise NotImplementedError

    @abstractmethod
    def reset_estop(self):
        raise NotImplementedError

    @abstractmethod
    def acknowledge_alarm(self, alarm_id: str):
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> dict:
        raise NotImplementedError


class SimulatedPLCAdapter(PLCAdapter):
    """Pure software PLC using the existing ladder-logic controller."""

    def __init__(self):
        self._plc = PLCController()

    def update(self, sensor_data: dict):
        self._plc.update(sensor_data)

    def start_machine(self):
        self._plc.start_machine()

    def stop_machine(self):
        self._plc.stop_machine()

    def emergency_stop(self):
        self._plc.emergency_stop()

    def reset_estop(self):
        self._plc.reset_estop()

    def acknowledge_alarm(self, alarm_id: str):
        self._plc.acknowledge_alarm(alarm_id)

    def get_status(self) -> dict:
        status = self._plc.get_status()
        status["plc_mode"] = "sim"
        status["plc_connected"] = True
        return status


class ModbusPLCAdapter(PLCAdapter):
    """
    PLC adapter that keeps ladder logic local and mirrors output coils to a
    real PLC over Modbus TCP when connection is available.
    """

    def __init__(self):
        self._plc = PLCController()
        self._host = os.environ.get("PLC_HOST", "127.0.0.1")
        self._port = int(os.environ.get("PLC_PORT", "502"))
        self._unit_id = int(os.environ.get("PLC_UNIT_ID", "1"))
        self._coil_addr = self._load_coil_addr()
        self._client = None
        self._connected = False

        if PYMODBUS_AVAILABLE:
            self._client = ModbusTcpClient(host=self._host, port=self._port)
            self._connected = bool(self._client.connect())

    def update(self, sensor_data: dict):
        self._plc.update(sensor_data)
        if self._connected:
            self._mirror_coils_to_plc()

    def start_machine(self):
        self._plc.start_machine()
        if self._connected:
            self._mirror_coils_to_plc()

    def stop_machine(self):
        self._plc.stop_machine()
        if self._connected:
            self._mirror_coils_to_plc()

    def emergency_stop(self):
        self._plc.emergency_stop()
        if self._connected:
            self._mirror_coils_to_plc()

    def reset_estop(self):
        self._plc.reset_estop()
        if self._connected:
            self._mirror_coils_to_plc()

    def acknowledge_alarm(self, alarm_id: str):
        self._plc.acknowledge_alarm(alarm_id)

    def get_status(self) -> dict:
        status = self._plc.get_status()
        status["plc_mode"] = "modbus"
        status["plc_connected"] = self._connected
        status["plc_host"] = self._host
        status["plc_port"] = self._port
        status["coil_map"] = dict(self._coil_addr)
        return status

    def _mirror_coils_to_plc(self):
        if not self._client:
            return
        coils = self._plc.get_status()["coils"]
        for name, addr in self._coil_addr.items():
            state = bool(coils.get(name, {}).get("state", False))
            try:
                self._client.write_coil(address=addr, value=state, device_id=self._unit_id)
            except TypeError:
                # Older pymodbus versions use "slave" instead of "device_id".
                self._client.write_coil(address=addr, value=state, slave=self._unit_id)

    def _load_coil_addr(self) -> dict:
        mapping = dict(COIL_ADDR)
        for key, env_name in COIL_ENV_KEYS.items():
            raw = os.environ.get(env_name, "").strip()
            if not raw:
                continue
            try:
                mapping[key] = int(raw)
            except ValueError:
                # Keep default mapping if env value is invalid.
                continue
        return mapping


def build_plc_adapter() -> PLCAdapter:
    mode = os.environ.get("PLC_MODE", "sim").strip().lower()
    if mode == "modbus":
        return ModbusPLCAdapter()
    return SimulatedPLCAdapter()
