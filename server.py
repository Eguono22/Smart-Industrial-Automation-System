"""
Smart Industrial Automation System
Predictive Maintenance Web Application – Flask app definition for deployment.
"""

import threading
import time
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, render_template, jsonify, request, g
from flask_socketio import SocketIO, emit

from app.models.sensor import SensorSimulator
from app.models.plc_adapter import build_plc_adapter
from app.models.predictor import PredictiveMaintenanceEngine

# ---------------------------------------------------------------------------
# App & SocketIO setup
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "sias-dev-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------------------
# Shared state (protected by a simple lock for the background thread)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
sensor_sim = SensorSimulator()
plc = build_plc_adapter()
predictor = PredictiveMaintenanceEngine()
_started_at = time.time()
_request_metrics = {"total": 0, "errors": 0}
_API_TOKEN = os.environ.get("SIAS_API_TOKEN", "").strip()
_UI_API_TOKEN = os.environ.get("SIAS_UI_API_TOKEN", "").strip()

# Start machine by default for demo
plc.start_machine()
sensor_sim.set_machine_running(True)

# ---------------------------------------------------------------------------
# Background data-refresh thread
# ---------------------------------------------------------------------------
_UPDATE_INTERVAL = 2  # seconds between sensor readings


def _background_update():
    """Reads sensors, runs PLC scan and ML analysis; broadcasts via SocketIO."""
    while True:
        time.sleep(_UPDATE_INTERVAL)
        with _lock:
            sd = sensor_sim.read()
            plc.update(sd)
            prediction = predictor.update(sd)
            plc_status = plc.get_status()

        payload = {
            "sensors": sd,
            "plc": plc_status,
            "prediction": prediction,
        }
        socketio.emit("data_update", payload)


# Serverless platforms do not keep persistent sockets; avoid idle threads there.
if os.environ.get("VERCEL") != "1":
    _bg_thread = threading.Thread(target=_background_update, daemon=True)
    _bg_thread.start()

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.context_processor
def inject_template_globals():
    return {"ui_api_token": _UI_API_TOKEN}


@app.before_request
def before_request():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    _request_metrics["total"] += 1

    # Protect mutating endpoints in production using SIAS_API_TOKEN.
    if _API_TOKEN and request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        presented = request.headers.get("X-API-Key", "")
        if presented != _API_TOKEN:
            _request_metrics["errors"] += 1
            return jsonify({"ok": False, "error": "unauthorized"}), 401


@app.after_request
def after_request(resp):
    resp.headers["X-Request-ID"] = getattr(g, "request_id", "")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/plc-monitor")
def plc_monitor():
    return render_template("plc_monitor.html")


@app.route("/maintenance")
def maintenance():
    return render_template("maintenance.html")


@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "healthy", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


@app.route("/ready")
def ready():
    with _lock:
        status = plc.get_status()
        pred = predictor.get_last_result()
    return jsonify(
        {
            "ok": True,
            "status": "ready",
            "plc_mode": status.get("plc_mode", "sim"),
            "plc_connected": status.get("plc_connected", True),
            "predictor_model_trained": pred.get("model_trained", False),
        }
    )


@app.route("/metrics")
def metrics():
    uptime = int(time.time() - _started_at)
    return jsonify(
        {
            "ok": True,
            "uptime_seconds": uptime,
            "requests_total": _request_metrics["total"],
            "requests_error": _request_metrics["errors"],
        }
    )

# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


@app.route("/api/sensors")
def api_sensors():
    with _lock:
        sd = sensor_sim.read()
    return jsonify(sd)


@app.route("/api/sensors/history")
def api_sensor_history():
    n = int(request.args.get("n", 60))
    with _lock:
        history = sensor_sim.get_all_history(n)
    return jsonify(history)


@app.route("/api/plc/status")
def api_plc_status():
    with _lock:
        status = plc.get_status()
    return jsonify(status)


@app.route("/api/plc/start", methods=["POST"])
def api_plc_start():
    with _lock:
        plc.start_machine()
        sensor_sim.set_machine_running(True)
    return jsonify({"ok": True, "message": "Machine started"})


@app.route("/api/plc/stop", methods=["POST"])
def api_plc_stop():
    with _lock:
        plc.stop_machine()
        sensor_sim.set_machine_running(False)
    return jsonify({"ok": True, "message": "Machine stopped"})


@app.route("/api/plc/estop", methods=["POST"])
def api_plc_estop():
    with _lock:
        plc.emergency_stop()
        sensor_sim.set_machine_running(False)
    return jsonify({"ok": True, "message": "Emergency stop activated"})


@app.route("/api/plc/reset-estop", methods=["POST"])
def api_plc_reset_estop():
    with _lock:
        plc.reset_estop()
    return jsonify({"ok": True, "message": "E-Stop reset"})


@app.route("/api/plc/acknowledge-alarm", methods=["POST"])
def api_acknowledge_alarm():
    data = request.get_json(force=True)
    alarm_id = data.get("alarm_id", "")
    with _lock:
        plc.acknowledge_alarm(alarm_id)
    return jsonify({"ok": True, "alarm_id": alarm_id})


@app.route("/api/prediction")
def api_prediction():
    with _lock:
        result = predictor.update(sensor_sim.read())
    return jsonify(result)


@app.route("/api/prediction/health-history")
def api_health_history():
    n = int(request.args.get("n", 60))
    with _lock:
        data = predictor.get_health_history(n)
    return jsonify(data)


@app.route("/api/prediction/anomaly-history")
def api_anomaly_history():
    n = int(request.args.get("n", 60))
    with _lock:
        data = predictor.get_anomaly_history(n)
    return jsonify(data)


@app.route("/api/fault/inject", methods=["POST"])
def api_inject_fault():
    data = request.get_json(force=True)
    sensor = data.get("sensor", "temperature")
    magnitude = float(data.get("magnitude", 3.0))
    with _lock:
        sensor_sim.inject_fault(sensor, magnitude)
    return jsonify({"ok": True, "sensor": sensor, "magnitude": magnitude})


@app.route("/api/fault/clear", methods=["POST"])
def api_clear_fault():
    with _lock:
        sensor_sim.clear_fault()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# SocketIO events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def on_connect():
    with _lock:
        sd = sensor_sim.read()
        plc_status = plc.get_status()
        prediction = predictor.update(sd)
    emit("data_update", {"sensors": sd, "plc": plc_status, "prediction": prediction})
