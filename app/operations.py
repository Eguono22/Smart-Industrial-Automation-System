"""Operations navigation shared by the simulator preview and authenticated app."""
import os
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, redirect, render_template, abort

operations_bp = Blueprint('operations', __name__)
MODULES = [
    dict(id='assets', name='Customers, sites & assets', icon='buildings', path='/assets',
         description='Organize customers and locations, register equipment, and track asset status and criticality.',
         roles=('admin', 'manager', 'technician', 'viewer'),
         columns=('Customer', 'Site', 'Equipment', 'Type', 'Criticality', 'Status'),
         rows=(('Demo organization', 'Demo plant', 'Cooling pump 01', 'Pump', 'High', 'Operational'),
               ('Demo organization', 'Demo plant', 'Extrusion line 01', 'Extruder', 'Critical', 'Maintenance'),
               ('Demo organization', 'Demo warehouse', 'Conveyor 02', 'Conveyor', 'Medium', 'Operational'))),
    dict(id='work-orders', name='Maintenance work orders', icon='clipboard-check', path='/work-orders',
         description='Plan maintenance, assign technicians, track due dates and record completed work.',
         roles=('admin', 'manager', 'technician', 'viewer'),
         columns=('Task', 'Asset', 'Assignee', 'Priority', 'Due', 'Status'),
         rows=(('Inspect bearing vibration', 'Extrusion line 01', 'Demo technician', 'High', 'Today', 'In progress'),
               ('Inspect cooling circuit', 'Cooling pump 01', 'Unassigned', 'Medium', 'Tomorrow', 'Open'),
               ('Check conveyor alignment', 'Conveyor 02', 'Demo technician', 'Low', 'Previous shift', 'Completed'))),
    dict(id='telemetry', name='Equipment telemetry', icon='broadcast', path='/telemetry',
         description='Review gateway readings, measurement history and connection freshness for registered equipment.',
         roles=('admin', 'manager', 'technician', 'viewer'),
         columns=('Asset', 'Channel', 'Value', 'Unit', 'Data freshness'),
         rows=(('Cooling pump 01', 'Temperature', '71.2', '°C', 'Recent example'),
               ('Cooling pump 01', 'Pressure', '3.1', 'bar', 'Recent example'),
               ('Conveyor 02', 'Vibration', '1.4', 'mm/s', 'Stale example'))),
    dict(id='notifications', name='Maintenance notifications', icon='bell', path='/notifications',
         description='Review assignment and overdue alerts, delivery status and notifications that need attention.',
         roles=('admin', 'manager', 'technician', 'viewer'),
         columns=('Notice', 'Recipient', 'Type', 'Delivery status'),
         rows=(('Inspect bearing vibration assigned', 'Demo technician', 'Assignment', 'Pending example'),
               ('Cooling circuit inspection overdue', 'Demo technician', 'Overdue', 'Sent example'),
               ('Conveyor inspection assigned', 'Demo technician', 'Assignment', 'Skipped example'))),
    dict(id='users', name='Users & access', icon='people', path='/users',
         description='Manage user accounts, customer access and administrator, manager, technician and viewer roles.',
         roles=('admin',), columns=('Example account', 'Role', 'Scope', 'Access'),
         rows=(('Demo administrator', 'Admin', 'All customers', 'Manage all operations'),
               ('Demo manager', 'Manager', 'Demo organization', 'Manage assets and work orders'),
               ('Demo technician', 'Technician', 'Demo organization', 'Update assigned work'),
               ('Demo viewer', 'Viewer', 'Demo organization', 'Read customer records'))),
    dict(id='industries', name='Industry solutions', icon='grid', path='/industry-hub',
         description='Explore industry use cases and prepare an exportable solution plan with available and planned capabilities.',
         roles=('admin', 'manager', 'technician', 'viewer'), columns=(), rows=()),
]


def workspace_url():
    value = os.environ.get('SIAS_OPERATIONS_URL', '').rstrip('/')
    if value:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('SIAS_OPERATIONS_URL must be a clean HTTPS workspace URL without credentials')
    return value


@operations_bp.app_context_processor
def operations_context():
    preview = current_app.config.get('OPERATIONS_PREVIEW', False)
    user = g.get('user')
    modules = [module for module in MODULES if preview or (user and user['role'] in module['roles'])]
    return dict(operations_modules=modules, operations_preview=preview,
                operations_url=workspace_url() if preview else '')


@operations_bp.route('/operations')
def overview():
    return render_template('operations.html')


@operations_bp.route('/operations/<module_id>')
def module(module_id):
    selected = next((item for item in MODULES if item['id'] == module_id), None)
    if selected is None:
        abort(404)
    if not current_app.config.get('OPERATIONS_PREVIEW', False):
        user = g.get('user')
        if not user or user['role'] not in selected['roles']:
            abort(403)
        return redirect(selected['path'])
    if module_id == 'industries':
        return redirect('/industry-hub')
    return render_template('operations_preview.html', module=selected)
