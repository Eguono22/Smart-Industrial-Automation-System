"""Original SIAS application, isolated simulation sessions for serverless hosting."""
import math
import copy
import os
import secrets
import threading
import time
from datetime import datetime, timezone

from flask import Flask, g, jsonify, render_template, request, session
from app.models.sensor import SensorSimulator, SENSORS
from app.models.plc_adapter import SimulatedPLCAdapter
from app.models.predictor import PredictiveMaintenanceEngine


class DemoMachine:
    def __init__(self):
        self.lock = threading.Lock()
        self.sensor = SensorSimulator()
        # Never call build_plc_adapter(): this public deployment cannot use real PLCs.
        self.plc = SimulatedPLCAdapter()
        self.predictor = PredictiveMaintenanceEngine(persist=False)
        self.plc.start_machine()
        self.sensor.set_machine_running(True)
        self.last_tick = 0
        self.last_seen = time.monotonic()
        self.payload = None
        self.revision = 0

    def refresh(self, force=False):
        now = time.monotonic()
        if force or self.payload is None or now - self.last_tick >= 2:
            sensors = self.sensor.read()
            self.plc.update(sensors)
            self.payload = dict(sensors=sensors, plc=self.plc.get_status(),
                                prediction=self.predictor.update(sensors), demo=self.sensor.get_demo_status())
            self.last_tick = now
            self.revision = time.time_ns()
        return self.payload


    def snapshot(self):
        """Small, JSON-only control state; never serialize models or executable objects."""
        controller = self.plc._plc
        return copy.deepcopy(dict(revision=self.revision,
            sensor={key: getattr(self.sensor, key) for key in (
                '_values', '_drift', '_fault_active', '_fault_sensor', '_machine_running',
                '_tick', '_demo_active', '_demo_step')},
            contacts={key: value['state'] for key, value in controller._contacts.items()},
            coils={key: value['state'] for key, value in controller._coils.items()},
            machine_running=controller._machine_running, plc_tick=controller._tick,
            active_alarms=controller._active_alarms))

    def restore(self, snapshot):
        # The signed Flask session is the source; only fixed fields are restored.
        controller = self.plc._plc
        for key in ('_values', '_drift', '_fault_active', '_fault_sensor', '_machine_running',
                    '_tick', '_demo_active', '_demo_step'):
            setattr(self.sensor, key, copy.deepcopy(snapshot['sensor'][key]))
        for key in controller._contacts:
            controller._contacts[key]['state'] = snapshot['contacts'][key]
        for key in controller._coils:
            controller._coils[key]['state'] = snapshot['coils'][key]
        controller._machine_running = snapshot['machine_running']
        controller._tick = snapshot['plc_tick']
        controller._active_alarms = copy.deepcopy(snapshot['active_alarms'])
        self.revision = snapshot['revision']
        self.last_tick = 0
        self.payload = None


def create_demo_app():
    app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('VERCEL') == '1', MAX_CONTENT_LENGTH=16384)
    machines, machines_lock = {}, threading.Lock()
    app.extensions['demo_machines'] = machines

    @app.before_request
    def load_machine():
        if request.path.startswith('/static/') or request.path in ('/health', '/ready'):
            return
        if request.path not in ('/', '/dashboard', '/plc-monitor', '/maintenance') and not request.path.startswith('/api/'):
            return
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            expected = session.get('csrf')
            if not expected or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), expected):
                return jsonify(ok=False, error='Refresh the page before using machine controls.'), 403
        session.setdefault('demo_id', secrets.token_urlsafe(24))
        session.setdefault('csrf', secrets.token_urlsafe(24))
        now = time.monotonic()
        with machines_lock:
            for key in list(machines):
                if now - machines[key].last_seen > 3600:
                    del machines[key]
            key = session['demo_id']
            if key not in machines:
                if len(machines) >= 32:
                    del machines[min(machines, key=lambda item: machines[item].last_seen)]
                machines[key] = DemoMachine()
            snapshot = session.get('machine_state')
            machine = machines[key]
            if snapshot and (machine.payload is None or snapshot['revision'] > machine.revision):
                with machine.lock:
                    machine.restore(snapshot)
            g.machine = machines[key]
            g.machine.last_seen = now

    @app.context_processor
    def demo_context():
        return dict(classic_demo=True, current_user=None, light_theme=False, csrf_token=session.get('csrf', ''))

    @app.after_request
    def headers(response):
        if g.get('machine') is not None and request.path.startswith('/api/') and response.status_code < 400:
            with g.machine.lock:
                session['machine_state'] = g.machine.snapshot()
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/plc-monitor')
    def plc_monitor():
        return render_template('plc_monitor.html')

    @app.route('/maintenance')
    def maintenance():
        return render_template('maintenance.html')

    @app.route('/health')
    @app.route('/ready')
    def health():
        return jsonify(ok=True, status='ready' if request.path == '/ready' else 'healthy',
                       mode='simulation', plc_mode='sim', persistent=False)

    @app.route('/api/<path:resource>')
    def data(resource):
        supported = {'demo/data', 'sensors', 'sensors/history', 'plc/status', 'plc/monitor',
                     'prediction', 'prediction/health-history', 'prediction/anomaly-history', 'demo/status'}
        if resource not in supported:
            return jsonify(ok=False, error='Not found'), 404
        try:
            n = int(request.args.get('n', '60'))
            if not 1 <= n <= 300:
                raise ValueError()
        except ValueError:
            return jsonify(ok=False, error='n must be between 1 and 300'), 400
        machine = g.machine
        with machine.lock:
            payload = machine.refresh()
            result = {
                'demo/data': payload,
                'sensors': payload['sensors'],
                'sensors/history': machine.sensor.get_all_history(n),
                'plc/status': payload['plc'],
                'plc/monitor': dict(ok=True, plc=payload['plc'], timestamp=datetime.now(timezone.utc).isoformat()),
                'prediction': payload['prediction'],
                'prediction/health-history': machine.predictor.get_health_history(n),
                'prediction/anomaly-history': machine.predictor.get_anomaly_history(n),
                'demo/status': dict(ok=True, demo=payload['demo']),
            }[resource]
        return jsonify(result)

    @app.route('/api/<path:resource>', methods=['POST'])
    def command(resource):
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(ok=False, error='A JSON object is required'), 400
        name = resource.removeprefix('plc/')
        if resource == 'plc/monitor/command':
            name = data.get('command')
        controls = {'start', 'stop', 'estop', 'reset-estop'}
        supported = {f'plc/{control}' for control in controls} | {
            'plc/monitor/command', 'plc/monitor/acknowledge', 'plc/acknowledge-alarm',
            'fault/inject', 'fault/clear', 'demo/start', 'demo/stop'}
        if resource not in supported:
            return jsonify(ok=False, error='Not found'), 404
        if resource == 'plc/monitor/command' and (not isinstance(name, str) or name not in controls):
            return jsonify(ok=False, error='Invalid command'), 400
        machine = g.machine
        with machine.lock:
            if name in controls:
                if name == 'start':
                    machine.plc.start_machine()
                    machine.sensor.set_machine_running(True)
                elif name == 'stop':
                    machine.plc.stop_machine()
                    machine.sensor.set_machine_running(False)
                elif name == 'estop':
                    machine.plc.emergency_stop()
                    machine.sensor.set_machine_running(False)
                else:
                    machine.plc.reset_estop()
            elif resource in ('plc/monitor/acknowledge', 'plc/acknowledge-alarm'):
                alarm_id = data.get('alarm_id')
                if not isinstance(alarm_id, str) or not alarm_id:
                    return jsonify(ok=False, error='alarm_id is required'), 400
                machine.plc.acknowledge_alarm(alarm_id)
            elif resource == 'fault/inject':
                sensor, magnitude = data.get('sensor'), data.get('magnitude', 3.0)
                if not isinstance(sensor, str) or sensor not in SENSORS or type(magnitude) not in (int, float) or not 0 < magnitude <= 10 or not math.isfinite(magnitude):
                    return jsonify(ok=False, error='Choose a valid sensor and magnitude from 0 to 10'), 400
                machine.sensor.inject_fault(sensor, magnitude)
            elif resource == 'demo/start':
                machine.sensor.start_demo()
                machine.plc.reset_estop()
                machine.plc.start_machine()
                machine.sensor.set_machine_running(True)
            else:
                machine.sensor.stop_demo()
                if resource == 'demo/stop':
                    machine.plc.reset_estop()
                    machine.plc.start_machine()
                    machine.sensor.set_machine_running(True)
            payload = machine.refresh(force=True)
        return jsonify(ok=True, message='Simulation updated', command=name if name in controls else resource,
                       demo=payload['demo'], plc=payload['plc'])

    return app
