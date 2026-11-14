"""
Phase 4: Real-time Updates via SocketIO
Event handlers for broadcasting real-time data and notifications to connected clients.
"""

from flask_socketio import emit, join_room, leave_room
from datetime import datetime
import json


def register_socket_handlers(socketio, app):
    """Register all SocketIO event handlers for real-time updates"""
    
    # ========================================================================
    # Connection Management
    # ========================================================================
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f'[SocketIO] Client connected: {request.sid}')
        emit('connection_response', {
            'status': 'connected',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'Connected to real-time updates'
        })
        # Join all users to a broadcast room for global updates
        join_room('broadcasts')
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print(f'[SocketIO] Client disconnected: {request.sid}')
        leave_room('broadcasts')
    
    # ========================================================================
    # Machine Simulator Events
    # ========================================================================
    
    @socketio.on('subscribe_machine')
    def handle_subscribe_machine(data):
        """Subscribe to real-time updates for a specific machine"""
        machine_id = data.get('machine_id')
        if machine_id:
            room = f'machine_{machine_id}'
            join_room(room)
            emit('subscription_response', {
                'status': 'subscribed',
                'machine_id': machine_id,
                'message': f'Subscribed to machine {machine_id}'
            })
            print(f'[SocketIO] Client subscribed to machine {machine_id}')
    
    @socketio.on('unsubscribe_machine')
    def handle_unsubscribe_machine(data):
        """Unsubscribe from real-time updates for a specific machine"""
        machine_id = data.get('machine_id')
        if machine_id:
            room = f'machine_{machine_id}'
            leave_room(room)
            emit('subscription_response', {
                'status': 'unsubscribed',
                'machine_id': machine_id
            })
    
    @socketio.on('request_machine_telemetry')
    def handle_machine_telemetry_request(data):
        """Request immediate telemetry snapshot"""
        machine_id = data.get('machine_id')
        # This would normally fetch from the module
        emit('machine_telemetry_update', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'temperature': 42.5,
                'rpm': 1500,
                'vibration': 2.3,
                'pressure': 8.5
            }
        })
    
    # ========================================================================
    # Digital Twin Events
    # ========================================================================
    
    @socketio.on('subscribe_asset')
    def handle_subscribe_asset(data):
        """Subscribe to real-time updates for a specific asset"""
        asset_id = data.get('asset_id')
        if asset_id:
            room = f'asset_{asset_id}'
            join_room(room)
            emit('subscription_response', {
                'status': 'subscribed',
                'asset_id': asset_id,
                'message': f'Subscribed to asset {asset_id}'
            })
            print(f'[SocketIO] Client subscribed to asset {asset_id}')
    
    @socketio.on('unsubscribe_asset')
    def handle_unsubscribe_asset(data):
        """Unsubscribe from real-time updates for a specific asset"""
        asset_id = data.get('asset_id')
        if asset_id:
            room = f'asset_{asset_id}'
            leave_room(room)
            emit('subscription_response', {
                'status': 'unsubscribed',
                'asset_id': asset_id
            })
    
    @socketio.on('request_sync_status')
    def handle_sync_status_request(data):
        """Request sync status update"""
        asset_id = data.get('asset_id')
        emit('asset_sync_update', {
            'asset_id': asset_id,
            'timestamp': datetime.utcnow().isoformat(),
            'sync_status': 'synced',
            'progress': 100
        })
    
    # ========================================================================
    # Predictive Maintenance Events
    # ========================================================================
    
    @socketio.on('subscribe_fleet')
    def handle_subscribe_fleet():
        """Subscribe to real-time fleet health updates"""
        room = 'fleet_health'
        join_room(room)
        emit('subscription_response', {
            'status': 'subscribed',
            'room': room,
            'message': 'Subscribed to fleet health updates'
        })
        print('[SocketIO] Client subscribed to fleet health')
    
    @socketio.on('unsubscribe_fleet')
    def handle_unsubscribe_fleet():
        """Unsubscribe from fleet health updates"""
        room = 'fleet_health'
        leave_room(room)
        emit('subscription_response', {
            'status': 'unsubscribed',
            'room': room
        })
    
    @socketio.on('request_health_update')
    def handle_health_update_request(data):
        """Request immediate health update"""
        machine_id = data.get('machine_id')
        emit('health_update', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'health_score': 85,
            'risk_level': 'low',
            'status': 'running'
        })
    
    # ========================================================================
    # Alert/Notification Events
    # ========================================================================
    
    @socketio.on('subscribe_alerts')
    def handle_subscribe_alerts(data):
        """Subscribe to real-time alerts and notifications"""
        alert_type = data.get('type', 'all')  # 'all', 'critical', 'warning'
        room = f'alerts_{alert_type}'
        join_room(room)
        emit('subscription_response', {
            'status': 'subscribed',
            'alert_type': alert_type,
            'message': f'Subscribed to {alert_type} alerts'
        })
    
    @socketio.on('unsubscribe_alerts')
    def handle_unsubscribe_alerts(data):
        """Unsubscribe from alerts"""
        alert_type = data.get('type', 'all')
        room = f'alerts_{alert_type}'
        leave_room(room)
        emit('subscription_response', {
            'status': 'unsubscribed',
            'alert_type': alert_type
        })
    
    # ========================================================================
    # Dashboard Status Events
    # ========================================================================
    
    @socketio.on('get_dashboard_status')
    def handle_dashboard_status():
        """Get current status of all modules"""
        emit('dashboard_status', {
            'timestamp': datetime.utcnow().isoformat(),
            'modules': {
                'machine_simulator': {'online': True, 'machines': 5},
                'digital_twin': {'online': True, 'assets': 3},
                'predictive_maintenance': {'online': True, 'fleet_size': 8}
            }
        })
    
    # ========================================================================
    # Broadcast Functions (called from Flask routes)
    # ========================================================================
    
    def broadcast_machine_telemetry(machine_id, telemetry_data):
        """Broadcast machine telemetry to subscribed clients"""
        socketio.emit('machine_telemetry_update', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'data': telemetry_data
        }, room=f'machine_{machine_id}')
    
    def broadcast_machine_fault(machine_id, fault_data):
        """Broadcast machine fault alert"""
        socketio.emit('machine_fault_alert', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'fault': fault_data,
            'severity': fault_data.get('severity', 'warning')
        }, room=f'machine_{machine_id}')
        
        # Also broadcast to alerts room
        if fault_data.get('severity') == 'critical':
            socketio.emit('alert', {
                'type': 'critical',
                'message': f'Critical fault on machine {machine_id}',
                'data': fault_data
            }, room='alerts_critical')
    
    def broadcast_asset_sync_update(asset_id, sync_data):
        """Broadcast asset synchronization update"""
        socketio.emit('asset_sync_update', {
            'asset_id': asset_id,
            'timestamp': datetime.utcnow().isoformat(),
            'sync_status': sync_data.get('status'),
            'progress': sync_data.get('progress', 0)
        }, room=f'asset_{asset_id}')
    
    def broadcast_health_update(machine_id, health_data):
        """Broadcast equipment health update"""
        socketio.emit('health_update', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'health_score': health_data.get('score'),
            'risk_level': health_data.get('risk_level'),
            'status': health_data.get('status')
        }, room='fleet_health')
    
    def broadcast_failure_prediction(machine_id, prediction_data):
        """Broadcast equipment failure prediction"""
        socketio.emit('failure_prediction', {
            'machine_id': machine_id,
            'timestamp': datetime.utcnow().isoformat(),
            'prediction': prediction_data
        }, room='fleet_health')
        
        # Alert if high confidence prediction
        if prediction_data.get('confidence', 0) > 0.7:
            socketio.emit('alert', {
                'type': 'warning',
                'message': f'High-risk failure prediction for machine {machine_id}',
                'data': prediction_data
            }, room='alerts_warning')
    
    def broadcast_global_alert(alert_data):
        """Broadcast alert to all connected clients"""
        socketio.emit('alert', {
            'timestamp': datetime.utcnow().isoformat(),
            **alert_data
        }, room='broadcasts')
    
    # Store broadcast functions in app for use in routes
    app.socketio_broadcast = {
        'machine_telemetry': broadcast_machine_telemetry,
        'machine_fault': broadcast_machine_fault,
        'asset_sync': broadcast_asset_sync_update,
        'health_update': broadcast_health_update,
        'failure_prediction': broadcast_failure_prediction,
        'global_alert': broadcast_global_alert
    }


# ============================================================================
# Client-side SocketIO Setup Guide
# ============================================================================

CLIENT_SETUP_TEMPLATE = """
<!-- Phase 4: SocketIO Client Setup -->

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
    // Initialize SocketIO connection
    const socket = io();
    
    // Connection events
    socket.on('connect', () => {
        console.log('✓ Connected to real-time updates');
    });
    
    socket.on('connection_response', (data) => {
        console.log('Server response:', data);
    });
    
    socket.on('disconnect', () => {
        console.log('✗ Disconnected from real-time updates');
    });
    
    // Machine Simulator Events
    socket.on('machine_telemetry_update', (data) => {
        console.log('Machine telemetry:', data);
        updateMachineCard(data.machine_id, data.data);
    });
    
    socket.on('machine_fault_alert', (data) => {
        console.log('Machine fault alert:', data);
        showAlert('Fault Alert', data.fault.message, data.severity);
    });
    
    // Digital Twin Events
    socket.on('asset_sync_update', (data) => {
        console.log('Asset sync:', data);
        updateAssetSyncStatus(data.asset_id, data.sync_status, data.progress);
    });
    
    // Predictive Maintenance Events
    socket.on('health_update', (data) => {
        console.log('Health update:', data);
        updateHealthScore(data.machine_id, data.health_score);
    });
    
    socket.on('failure_prediction', (data) => {
        console.log('Failure prediction:', data);
        updatePrediction(data.machine_id, data.prediction);
    });
    
    // Alert Events
    socket.on('alert', (data) => {
        console.log('Alert received:', data);
        showNotification(data.type, data.message);
    });
    
    // Subscribe to machine
    function subscribeMachine(machineId) {
        socket.emit('subscribe_machine', { machine_id: machineId });
    }
    
    // Subscribe to asset
    function subscribeAsset(assetId) {
        socket.emit('subscribe_asset', { asset_id: assetId });
    }
    
    // Subscribe to fleet
    function subscribeFleet() {
        socket.emit('subscribe_fleet');
    }
    
    // Subscribe to alerts
    function subscribeAlerts(type = 'all') {
        socket.emit('subscribe_alerts', { type: type });
    }
</script>
"""
