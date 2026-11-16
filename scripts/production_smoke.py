"""Verify a running release with an existing administrator account.

Set SIAS_ADMIN_USERNAME and SIAS_ADMIN_PASSWORD; credentials never appear in output.
Install requests and websocket-client in the validation environment.
"""
import argparse
import os
import time

import requests
import socketio


def check(base_url):
    base_url = base_url.rstrip('/')
    with requests.Session() as http:
        for path in ('/health', '/ready', '/login'):
            response = http.get(base_url + path, timeout=10)
            response.raise_for_status()
        assert http.get(base_url + '/api/sensors', timeout=10).status_code == 401
        token = http.get(base_url + '/api/auth/me', timeout=10).json()['csrf_token']
        response = http.post(base_url + '/api/auth/login', json={
            'username': os.environ['SIAS_ADMIN_USERNAME'],
            'password': os.environ['SIAS_ADMIN_PASSWORD'],
        }, headers={'X-CSRF-Token': token}, timeout=10)
        response.raise_for_status()
        token = response.json()['csrf_token']
        assert response.json()['user']['role'] == 'admin'
        for path in ('/operations', '/assets', '/work-orders', '/users', '/dashboard',
                     '/api/sensors', '/api/plc/status', '/api/prediction'):
            http.get(base_url + path, timeout=10).raise_for_status()
        # Verify the actual network WebSocket transport and a live broadcast.
        client = socketio.Client(http_session=http, reconnection=False)
        updates = []
        client.on('data_update', lambda data: updates.append(data))
        try:
            client.connect(base_url, transports=['websocket'], wait_timeout=10)
            deadline = time.monotonic() + 10
            while not updates and time.monotonic() < deadline:
                client.sleep(0.1)
            assert updates, 'No live telemetry received'
        finally:
            if client.connected:
                client.disconnect()
        # A state-changing request without CSRF must be refused.
        assert http.post(base_url + '/api/auth/logout', timeout=10).status_code == 403
        http.post(base_url + '/api/auth/logout', headers={'X-CSRF-Token': token}, timeout=10).raise_for_status()
        assert http.get(base_url + '/api/sensors', timeout=10).status_code == 401
    print('Production smoke passed: readiness, login, pages, APIs, WebSocket telemetry, CSRF, logout')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    check(parser.parse_args().base_url)
