"""
Predictive Maintenance Engine
Uses an Isolation Forest trained on engineered rolling-window sensor features.
Provides model persistence and basic data-drift monitoring.
"""

import os
import pickle
from collections import deque
from datetime import datetime, timezone

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


FEATURE_SENSORS = ["temperature", "pressure", "vibration", "current", "rpm", "oil_level"]
TRAIN_BUFFER_SIZE = 400
WINDOW_SIZE = 10
RECENT_DRIFT_WINDOW = 30
MIN_TRAIN_SAMPLES = 50
RETRAIN_INTERVAL = 50
MIN_HEALTH = 0.0
MAX_HEALTH = 100.0

SENSOR_WEIGHTS = {
    "temperature": 0.20,
    "pressure": 0.15,
    "vibration": 0.25,
    "current": 0.15,
    "rpm": 0.10,
    "oil_level": 0.15,
}


class PredictiveMaintenanceEngine:
    """Trains an IsolationForest online and scores incoming sensor data."""

    def __init__(self):
        self._model = None
        self._scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None
        self._train_buffer: deque = deque(maxlen=TRAIN_BUFFER_SIZE)
        self._raw_window: deque = deque(maxlen=WINDOW_SIZE)
        self._recent_engineered: deque = deque(maxlen=RECENT_DRIFT_WINDOW)
        self._anomaly_history: deque = deque(maxlen=300)
        self._health_history: deque = deque(maxlen=300)
        self._last_result: dict = _default_result()
        self._trained = False
        self._train_count = 0
        self._last_train_sample_count = 0
        self._drift_baseline_mean = None
        self._drift_baseline_std = None
        self._drift_score = 0.0
        self._drift_detected = False
        self._model_path = os.environ.get("SIAS_MODEL_PATH", os.path.join("instance", "predictor_model.pkl"))
        self._load_model()

    def update(self, sensor_data: dict) -> dict:
        raw_row = self._extract_raw(sensor_data)
        if raw_row is None:
            return self._last_result

        self._raw_window.append(raw_row)
        engineered = self._engineer_features(raw_row)
        self._train_buffer.append(engineered)
        self._recent_engineered.append(engineered)

        should_train = (
            len(self._train_buffer) >= MIN_TRAIN_SAMPLES
            and (
                not self._trained
                or (len(self._train_buffer) - self._last_train_sample_count) >= RETRAIN_INTERVAL
            )
        )
        if should_train:
            self._train()

        self._update_drift_metrics()

        result = self._analyse(engineered, sensor_data)
        self._last_result = result

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._anomaly_history.append({"timestamp": ts, "score": result["anomaly_score"]})
        self._health_history.append({"timestamp": ts, "health": result["health_score"]})
        return result

    def get_health_history(self, n: int = 60) -> list:
        return list(self._health_history)[-n:]

    def get_anomaly_history(self, n: int = 60) -> list:
        return list(self._anomaly_history)[-n:]

    def get_last_result(self) -> dict:
        return dict(self._last_result)

    def _extract_raw(self, sd: dict) -> list | None:
        try:
            return [float(sd[s]["value"]) for s in FEATURE_SENSORS]
        except (KeyError, TypeError, ValueError):
            return None

    def _engineer_features(self, raw_row: list) -> list:
        window_arr = np.array(list(self._raw_window), dtype=float)
        mean_row = np.mean(window_arr, axis=0)
        std_row = np.std(window_arr, axis=0)
        return list(raw_row) + list(mean_row) + list(std_row)

    def _train(self):
        if not SKLEARN_AVAILABLE:
            return

        X = np.array(list(self._train_buffer), dtype=float)
        self._scaler.fit(X)
        X_scaled = self._scaler.transform(X)
        self._model = IsolationForest(
            n_estimators=150,
            contamination=0.05,
            random_state=42,
        )
        self._model.fit(X_scaled)
        self._trained = True
        self._train_count += 1
        self._last_train_sample_count = len(self._train_buffer)

        self._drift_baseline_mean = np.mean(X, axis=0)
        self._drift_baseline_std = np.std(X, axis=0) + 1e-6
        self._save_model()

    def _update_drift_metrics(self):
        if (
            self._drift_baseline_mean is None
            or self._drift_baseline_std is None
            or len(self._recent_engineered) < 10
        ):
            self._drift_score = 0.0
            self._drift_detected = False
            return

        recent = np.array(list(self._recent_engineered), dtype=float)
        recent_mean = np.mean(recent, axis=0)
        z = np.abs((recent_mean - self._drift_baseline_mean) / self._drift_baseline_std)
        self._drift_score = float(np.mean(z))
        self._drift_detected = self._drift_score >= 2.5

    def _analyse(self, row: list, sd: dict) -> dict:
        health = self._compute_health(sd)
        anomaly_score = 0.0
        is_anomaly = False

        if self._trained and SKLEARN_AVAILABLE and self._model is not None and self._scaler is not None:
            X = np.array([row], dtype=float)
            X_scaled = self._scaler.transform(X)
            raw = float(self._model.decision_function(X_scaled)[0])
            anomaly_score = round(max(0.0, min(1.0, 0.5 - raw)), 3)
            is_anomaly = bool(self._model.predict(X_scaled)[0] == -1)

        rul = self._estimate_rul(health)
        recommendations = self._recommendations(sd, health, is_anomaly)

        return {
            "health_score": round(health, 1),
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "rul_hours": rul,
            "rul_label": _rul_label(rul),
            "recommendations": recommendations,
            "model_trained": self._trained,
            "samples_collected": len(self._train_buffer),
            "drift_score": round(self._drift_score, 3),
            "drift_detected": self._drift_detected,
            "model_train_count": self._train_count,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _compute_health(self, sd: dict) -> float:
        score = 0.0
        for sensor, weight in SENSOR_WEIGHTS.items():
            status = sd.get(sensor, {}).get("status", "normal")
            if status == "normal":
                contribution = weight * 100
            elif status == "warning":
                contribution = weight * 50
            else:
                contribution = weight * 10
            score += contribution
        return max(MIN_HEALTH, min(MAX_HEALTH, score))

    def _estimate_rul(self, health: float) -> int:
        if health >= 90:
            return 720
        if health >= 75:
            return 336
        if health >= 60:
            return 168
        if health >= 40:
            return 72
        if health >= 20:
            return 24
        return 4

    def _recommendations(self, sd: dict, health: float, is_anomaly: bool) -> list:
        recs = []
        if is_anomaly:
            recs.append("⚠️ Anomaly detected - inspect machine immediately")
        if self._drift_detected:
            recs.append("🟡 Data drift detected - recalibration and model review recommended")

        for sensor in FEATURE_SENSORS:
            status = sd.get(sensor, {}).get("status", "normal")
            val = sd.get(sensor, {}).get("value", 0)
            unit = sd.get(sensor, {}).get("unit", "")
            if status == "critical":
                recs.append(
                    f"🔴 {sensor.replace('_', ' ').title()}: CRITICAL ({val} {unit}) - shutdown recommended"
                )
            elif status == "warning":
                recs.append(
                    f"🟡 {sensor.replace('_', ' ').title()}: WARNING ({val} {unit}) - schedule inspection"
                )

        if health < 40:
            recs.append("🔴 Overall health critical - immediate maintenance required")
        elif health < 70:
            recs.append("🟡 Schedule preventive maintenance within 72 hours")
        elif health < 90:
            recs.append("🟢 Machine healthy - continue routine monitoring")

        if not recs:
            recs.append("✅ All systems nominal")
        return recs

    def _save_model(self):
        if not self._trained or self._model is None or self._scaler is None:
            return
        try:
            model_dir = os.path.dirname(self._model_path)
            if model_dir:
                os.makedirs(model_dir, exist_ok=True)
            payload = {
                "model": self._model,
                "scaler": self._scaler,
                "train_count": self._train_count,
                "baseline_mean": self._drift_baseline_mean,
                "baseline_std": self._drift_baseline_std,
            }
            with open(self._model_path, "wb") as fp:
                pickle.dump(payload, fp)
        except OSError:
            pass

    def _load_model(self):
        if not SKLEARN_AVAILABLE:
            return
        if not self._model_path or not os.path.exists(self._model_path):
            return
        try:
            with open(self._model_path, "rb") as fp:
                payload = pickle.load(fp)
            self._model = payload.get("model")
            self._scaler = payload.get("scaler")
            self._train_count = int(payload.get("train_count", 0))
            self._drift_baseline_mean = payload.get("baseline_mean")
            self._drift_baseline_std = payload.get("baseline_std")
            self._trained = self._model is not None and self._scaler is not None
        except (OSError, pickle.UnpicklingError, ValueError, TypeError):
            self._model = None
            self._trained = False


def _default_result() -> dict:
    return {
        "health_score": 100.0,
        "anomaly_score": 0.0,
        "is_anomaly": False,
        "rul_hours": 720,
        "rul_label": "~30 days",
        "recommendations": ["✅ Initialising predictive model..."],
        "model_trained": False,
        "samples_collected": 0,
        "drift_score": 0.0,
        "drift_detected": False,
        "model_train_count": 0,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _rul_label(hours: int) -> str:
    if hours >= 720:
        return "~30 days"
    if hours >= 336:
        return "~14 days"
    if hours >= 168:
        return "~7 days"
    if hours >= 72:
        return "~3 days"
    if hours >= 24:
        return "~1 day"
    return f"~{hours} hrs"
