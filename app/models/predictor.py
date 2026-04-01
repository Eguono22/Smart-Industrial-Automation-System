"""
Predictive Maintenance Engine
Uses an Isolation Forest trained on historical sensor data to produce:
  - Anomaly score for each sensor reading
  - Overall machine health score (0-100)
  - Remaining Useful Life (RUL) estimate in hours
  - Maintenance recommendations
"""

import numpy as np
from datetime import datetime, timezone, timedelta
from collections import deque

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


FEATURE_SENSORS = ["temperature", "pressure", "vibration", "current", "rpm", "oil_level"]
TRAIN_BUFFER_SIZE = 200   # readings needed before model trains
MIN_HEALTH = 0.0
MAX_HEALTH = 100.0

# Weights per sensor for health score calculation
SENSOR_WEIGHTS = {
    "temperature": 0.20,
    "pressure":    0.15,
    "vibration":   0.25,
    "current":     0.15,
    "rpm":         0.10,
    "oil_level":   0.15,
}


class PredictiveMaintenanceEngine:
    """Trains an IsolationForest on-the-fly and scores incoming sensor data."""

    def __init__(self):
        self._model = None
        self._scaler = MinMaxScaler() if SKLEARN_AVAILABLE else None
        self._buffer: deque = deque(maxlen=TRAIN_BUFFER_SIZE)
        self._anomaly_history: deque = deque(maxlen=300)
        self._health_history: deque = deque(maxlen=300)
        self._last_result: dict = _default_result()
        self._trained = False
        self._train_count = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self, sensor_data: dict) -> dict:
        """Ingest one sensor snapshot and return the latest analysis."""
        row = self._extract_features(sensor_data)
        if row is None:
            return self._last_result

        self._buffer.append(row)

        # Retrain every 50 new samples once we have enough data
        if len(self._buffer) >= 50 and (len(self._buffer) % 50 == 0 or not self._trained):
            self._train()

        result = self._analyse(row, sensor_data)
        self._last_result = result

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self._anomaly_history.append({"timestamp": ts, "score": result["anomaly_score"]})
        self._health_history.append({"timestamp": ts, "health": result["health_score"]})

        return result

    def get_health_history(self, n: int = 60) -> list:
        buf = list(self._health_history)
        return buf[-n:]

    def get_anomaly_history(self, n: int = 60) -> list:
        buf = list(self._anomaly_history)
        return buf[-n:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_features(self, sd: dict) -> list | None:
        try:
            return [sd[s]["value"] for s in FEATURE_SENSORS]
        except (KeyError, TypeError):
            return None

    def _train(self):
        if not SKLEARN_AVAILABLE:
            return
        X = np.array(list(self._buffer))
        self._scaler.fit(X)
        X_scaled = self._scaler.transform(X)
        self._model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
        )
        self._model.fit(X_scaled)
        self._trained = True
        self._train_count += 1

    def _analyse(self, row: list, sd: dict) -> dict:
        health = self._compute_health(sd)
        anomaly_score = 0.0
        is_anomaly = False

        if self._trained and SKLEARN_AVAILABLE:
            X = np.array([row])
            X_scaled = self._scaler.transform(X)
            # decision_function returns negative scores; map to 0-1 range
            raw = float(self._model.decision_function(X_scaled)[0])
            # raw is typically in [-0.5, 0.5]; map to [0, 1] where 1 = anomaly
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
            "samples_collected": len(self._buffer),
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
        """Very simple linear degradation model for RUL estimation."""
        if health >= 90:
            return 720    # ~30 days
        if health >= 75:
            return 336    # ~14 days
        if health >= 60:
            return 168    # ~7 days
        if health >= 40:
            return 72     # ~3 days
        if health >= 20:
            return 24     # ~1 day
        return 4          # imminent

    def _recommendations(self, sd: dict, health: float, is_anomaly: bool) -> list:
        recs = []
        if is_anomaly:
            recs.append("⚠️ Anomaly detected – inspect machine immediately")

        for sensor in FEATURE_SENSORS:
            status = sd.get(sensor, {}).get("status", "normal")
            val = sd.get(sensor, {}).get("value", 0)
            unit = sd.get(sensor, {}).get("unit", "")
            if status == "critical":
                recs.append(f"🔴 {sensor.replace('_', ' ').title()}: CRITICAL ({val} {unit}) – shutdown recommended")
            elif status == "warning":
                recs.append(f"🟡 {sensor.replace('_', ' ').title()}: WARNING ({val} {unit}) – schedule inspection")

        if health < 40:
            recs.append("🔴 Overall health critical – immediate maintenance required")
        elif health < 70:
            recs.append("🟡 Schedule preventive maintenance within 72 hours")
        elif health < 90:
            recs.append("🟢 Machine healthy – continue routine monitoring")

        if not recs:
            recs.append("✅ All systems nominal")
        return recs


def _default_result() -> dict:
    return {
        "health_score": 100.0,
        "anomaly_score": 0.0,
        "is_anomaly": False,
        "rul_hours": 720,
        "rul_label": "~30 days",
        "recommendations": ["✅ Initialising predictive model…"],
        "model_trained": False,
        "samples_collected": 0,
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
