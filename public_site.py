"""Stateless SIAS Hub public site for Vercel; operational app stays in server.py."""
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template
from app.founder import FOUNDER
from app.models.hub import CAPABILITIES, INDUSTRIES

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
operations_url = os.environ.get('SIAS_OPERATIONS_URL', '').rstrip('/')
if operations_url:
    parsed = urlsplit(operations_url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('SIAS_OPERATIONS_URL must be an HTTPS URL without embedded credentials')


@app.context_processor
def public_context():
    return dict(current_user=None, csrf_token='', operations_enabled=False, operations_url=operations_url)


@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.route('/')
def index():
    return render_template('index.html', industries=INDUSTRIES, capabilities=CAPABILITIES)


@app.route('/founder')
def founder():
    return render_template('founder.html', founder=FOUNDER)


@app.route('/api/hub/catalog')
def catalog():
    return jsonify(industries=INDUSTRIES, capabilities=CAPABILITIES)


@app.route('/health')
@app.route('/ready')
def health():
    return jsonify(ok=True, status='healthy', mode='public_site', timestamp=datetime.now(timezone.utc).isoformat())


@app.route('/operations')
@app.route('/login')
@app.route('/assets')
@app.route('/work-orders')
@app.route('/telemetry')
@app.route('/notifications')
@app.route('/users')
@app.route('/dashboard')
@app.route('/plc-monitor')
@app.route('/maintenance')
def operations():
    return render_template('operations.html')
