"""
Unit tests for the Smart Industrial Automation System core modules.
Run with:  python -m pytest tests/ -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.sensor import SensorSimulator, SENSORS, _classify
from app.models.plc import PLCController
from app.models.predictor import PredictiveMaintenanceEngine, _rul_label


# ==========================================================================
# SensorSimulator tests
# ==========================================================================

class TestSensorSimulator:

    def test_read_returns_all_sensor_keys(self):
        sim = SensorSimulator()
        data = sim.read()
        assert set(data.keys()) == set(SENSORS.keys())

    def test_sensor_values_have_required_fields(self):
        sim = SensorSimulator()
        data = sim.read()
        for name, info in data.items():
            assert "value" in info, f"{name} missing 'value'"
            assert "unit" in info, f"{name} missing 'unit'"
            assert "status" in info, f"{name} missing 'status'"
            assert "timestamp" in info, f"{name} missing 'timestamp'"
            assert "limits" in info, f"{name} missing 'limits'"

    def test_status_is_valid_classification(self):
        sim = SensorSimulator()
        data = sim.read()
        valid = {"normal", "warning", "critical"}
        for name, info in data.items():
            assert info["status"] in valid, f"{name} has unexpected status: {info['status']}"

    def test_get_history_returns_list(self):
        sim = SensorSimulator()
        history = sim.get_history("temperature", n=10)
        assert isinstance(history, list)
        assert len(history) > 0

    def test_get_history_unknown_sensor_returns_empty(self):
        sim = SensorSimulator()
        result = sim.get_history("nonexistent_sensor")
        assert result == []

    def test_get_all_history_keys_match_sensors(self):
        sim = SensorSimulator()
        all_hist = sim.get_all_history(n=5)
        assert set(all_hist.keys()) == set(SENSORS.keys())

    def test_machine_running_flag(self):
        sim = SensorSimulator()
        sim.set_machine_running(False)
        assert sim.machine_running is False
        sim.set_machine_running(True)
        assert sim.machine_running is True

    def test_inject_fault_raises_sensor_value(self):
        sim = SensorSimulator()
        # Read baseline temperature
        baseline = sim.read()["temperature"]["value"]
        sim.inject_fault("temperature", magnitude=10.0)
        # After several reads the drift should be visible
        for _ in range(5):
            val = sim.read()["temperature"]["value"]
        # With magnitude=10 the drift should push value up noticeably
        assert val != baseline

    def test_clear_fault_resets_drift(self):
        sim = SensorSimulator()
        sim.inject_fault("pressure", magnitude=5.0)
        sim.clear_fault()
        # After clearing all drifts should be zero
        for k in SENSORS:
            assert sim._drift[k] == 0.0


class TestClassify:

    def test_normal_temperature(self):
        assert _classify("temperature", 70.0) == "normal"

    def test_warning_temperature(self):
        assert _classify("temperature", 85.0) == "warning"

    def test_critical_temperature(self):
        assert _classify("temperature", 100.0) == "critical"

    def test_normal_oil_level(self):
        assert _classify("oil_level", 75.0) == "normal"

    def test_warning_oil_level(self):
        assert _classify("oil_level", 45.0) == "warning"

    def test_critical_oil_level(self):
        assert _classify("oil_level", 10.0) == "critical"


# ==========================================================================
# PLCController tests
# ==========================================================================

class TestPLCController:

    def _make_normal_sensor_data(self):
        return {
            s: {"value": 0, "status": "normal"}
            for s in ["temperature", "pressure", "vibration", "current", "rpm", "oil_level"]
        }

    def test_initial_machine_not_running(self):
        plc = PLCController()
        assert plc.get_status()["machine_running"] is False

    def test_start_machine_enables_motor(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        status = plc.get_status()
        assert status["machine_running"] is True
        assert status["coils"]["motor_run"]["state"] is True

    def test_stop_machine_disables_motor(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        plc.stop_machine()
        plc.update(sd)
        status = plc.get_status()
        assert status["coils"]["motor_run"]["state"] is False

    def test_emergency_stop_latches(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        plc.emergency_stop()
        plc.update(sd)
        status = plc.get_status()
        assert status["coils"]["estop_latch"]["state"] is True
        assert status["coils"]["motor_run"]["state"] is False

    def test_reset_estop_clears_latch(self):
        plc = PLCController()
        plc.emergency_stop()
        plc.reset_estop()
        status = plc.get_status()
        assert status["coils"]["estop_latch"]["state"] is False

    def test_coolant_pump_follows_motor(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        status = plc.get_status()
        assert status["coils"]["pump_run"]["state"] is True

    def test_lube_pump_follows_motor(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        status = plc.get_status()
        assert status["coils"]["lube_pump"]["state"] is True

    def test_critical_temperature_trips_interlock(self):
        plc = PLCController()
        plc.start_machine()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        # Now inject critical temperature
        sd["temperature"]["status"] = "critical"
        plc.update(sd)
        status = plc.get_status()
        assert status["contacts"]["temp_sw"]["state"] is False
        assert status["coils"]["motor_run"]["state"] is False

    def test_critical_sensor_raises_alarm(self):
        plc = PLCController()
        sd = self._make_normal_sensor_data()
        sd["vibration"]["status"] = "critical"
        plc.update(sd)
        status = plc.get_status()
        alarm_ids = [a["id"] for a in status["active_alarms"]]
        assert "VIB_HIGH" in alarm_ids

    def test_acknowledge_alarm(self):
        plc = PLCController()
        plc.emergency_stop()
        plc.acknowledge_alarm("ESTOP")
        status = plc.get_status()
        assert status["active_alarms"][0]["acknowledged"] is True

    def test_alarm_log_populated(self):
        plc = PLCController()
        sd = self._make_normal_sensor_data()
        sd["pressure"]["status"] = "warning"
        plc.update(sd)
        status = plc.get_status()
        assert len(status["alarm_log"]) > 0

    def test_get_status_contains_required_keys(self):
        plc = PLCController()
        status = plc.get_status()
        for key in ("machine_running", "coils", "contacts", "active_alarms", "alarm_log", "tick"):
            assert key in status

    def test_tick_increments_on_update(self):
        plc = PLCController()
        sd = self._make_normal_sensor_data()
        plc.update(sd)
        plc.update(sd)
        assert plc.get_status()["tick"] == 2


# ==========================================================================
# PredictiveMaintenanceEngine tests
# ==========================================================================

class TestPredictiveMaintenanceEngine:

    def _make_sensor_data(self, override_status=None):
        sensors = ["temperature", "pressure", "vibration", "current", "rpm", "oil_level"]
        units = {"temperature": "°C", "pressure": "bar", "vibration": "mm/s",
                 "current": "A", "rpm": "RPM", "oil_level": "%"}
        values = {"temperature": 70, "pressure": 3.0, "vibration": 1.2,
                  "current": 10.0, "rpm": 1500, "oil_level": 85}
        data = {}
        for s in sensors:
            data[s] = {
                "value": values[s],
                "unit": units[s],
                "status": override_status.get(s, "normal") if override_status else "normal",
            }
        return data

    def test_update_returns_required_fields(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        result = eng.update(sd)
        for field in ("health_score", "anomaly_score", "is_anomaly",
                       "rul_hours", "rul_label", "recommendations",
                       "model_trained", "samples_collected", "timestamp"):
            assert field in result, f"Missing field: {field}"

    def test_health_score_bounds(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        result = eng.update(sd)
        assert 0.0 <= result["health_score"] <= 100.0

    def test_full_normal_gives_max_health(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        result = eng.update(sd)
        assert result["health_score"] == 100.0

    def test_all_critical_reduces_health(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data(override_status={
            "temperature": "critical", "pressure": "critical",
            "vibration": "critical", "current": "critical",
            "rpm": "critical", "oil_level": "critical",
        })
        result = eng.update(sd)
        assert result["health_score"] < 50.0

    def test_recommendations_not_empty(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        result = eng.update(sd)
        assert len(result["recommendations"]) > 0

    def test_critical_status_generates_recommendation(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data(override_status={"vibration": "critical"})
        result = eng.update(sd)
        combined = " ".join(result["recommendations"])
        assert "Vibration" in combined or "vibration" in combined.lower()

    def test_samples_collected_increments(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        for _ in range(5):
            result = eng.update(sd)
        assert result["samples_collected"] >= 5

    def test_model_trains_after_50_samples(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        for _ in range(52):
            result = eng.update(sd)
        assert result["model_trained"] is True

    def test_get_health_history(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        for _ in range(5):
            eng.update(sd)
        history = eng.get_health_history(n=3)
        assert isinstance(history, list)
        assert len(history) <= 3

    def test_get_anomaly_history(self):
        eng = PredictiveMaintenanceEngine()
        sd = self._make_sensor_data()
        for _ in range(5):
            eng.update(sd)
        history = eng.get_anomaly_history(n=5)
        assert isinstance(history, list)
        for entry in history:
            assert "timestamp" in entry
            assert "score" in entry


class TestRulLabel:
    def test_rul_30_days(self):
        assert _rul_label(720) == "~30 days"

    def test_rul_14_days(self):
        assert _rul_label(400) == "~14 days"

    def test_rul_7_days(self):
        assert _rul_label(200) == "~7 days"

    def test_rul_3_days(self):
        assert _rul_label(80) == "~3 days"

    def test_rul_1_day(self):
        assert _rul_label(30) == "~1 day"

    def test_rul_hours(self):
        assert _rul_label(4) == "~4 hrs"
