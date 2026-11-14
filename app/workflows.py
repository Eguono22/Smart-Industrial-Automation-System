"""
Phase 5: Multi-Module Workflows
Automated workflows that coordinate actions across multiple SIAS modules.
"""

from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json


class TriggerType(Enum):
    """Types of workflow triggers"""
    SCHEDULE = "schedule"          # Time-based
    CONDITION = "condition"         # Data-driven
    EVENT = "event"                 # Event-based
    MANUAL = "manual"              # User-initiated


class ActionType(Enum):
    """Types of workflow actions"""
    MACHINE_CONTROL = "machine_control"      # Start/stop machine
    SYNC_TWIN = "sync_twin"                  # Sync digital twin
    CREATE_WORK_ORDER = "create_work_order"  # Create maintenance order
    NOTIFY = "notify"                        # Send notification
    LOG = "log"                              # Log event
    API_CALL = "api_call"                    # Call external API
    CONDITIONAL = "conditional"              # Branch logic


@dataclass
class WorkflowTrigger:
    """Defines what starts a workflow"""
    trigger_type: TriggerType
    condition: str = None         # For CONDITION type: e.g., "health_score < 40"
    schedule: str = None          # For SCHEDULE type: cron expression
    event_name: str = None        # For EVENT type: e.g., "fault_detected"
    
    def should_fire(self, context: Dict[str, Any]) -> bool:
        """Evaluate if trigger should fire"""
        if self.trigger_type == TriggerType.CONDITION:
            return self._evaluate_condition(context)
        elif self.trigger_type == TriggerType.EVENT:
            return context.get('event_name') == self.event_name
        return False
    
    def _evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """Safely evaluate Python condition"""
        try:
            # Whitelist allowed context variables
            safe_context = {
                'health_score': context.get('health_score'),
                'temperature': context.get('temperature'),
                'rpm': context.get('rpm'),
                'vibration': context.get('vibration'),
                'pressure': context.get('pressure'),
                'sync_status': context.get('sync_status'),
                'uptime_percentage': context.get('uptime_percentage'),
            }
            return eval(self.condition, {"__builtins__": {}}, safe_context)
        except Exception as e:
            print(f"Error evaluating condition: {e}")
            return False


@dataclass
class WorkflowAction:
    """Defines what a workflow does"""
    action_type: ActionType
    target_module: str           # 'machine_simulator', 'digital_twin', 'predictive_maintenance'
    target_id: str              # Machine ID, Asset ID, etc.
    action_name: str            # Specific action: start, stop, sync, create_order
    parameters: Dict[str, Any] = None
    
    def execute(self, api_client: 'APIClient') -> Dict[str, Any]:
        """Execute the action"""
        if self.action_type == ActionType.MACHINE_CONTROL:
            return self._execute_machine_control(api_client)
        elif self.action_type == ActionType.SYNC_TWIN:
            return self._execute_sync_twin(api_client)
        elif self.action_type == ActionType.CREATE_WORK_ORDER:
            return self._execute_create_work_order(api_client)
        elif self.action_type == ActionType.NOTIFY:
            return self._execute_notify()
        elif self.action_type == ActionType.LOG:
            return self._execute_log()
        return {'status': 'unknown', 'action': self.action_name}
    
    def _execute_machine_control(self, api_client: 'APIClient') -> Dict[str, Any]:
        """Control a machine (start/stop/reset)"""
        endpoint = f"/api/modules/machine-simulator/machine/{self.target_id}/action"
        return api_client.post(endpoint, {'action': self.action_name})
    
    def _execute_sync_twin(self, api_client: 'APIClient') -> Dict[str, Any]:
        """Synchronize a digital twin"""
        endpoint = f"/api/modules/digital-twin/asset/{self.target_id}/sync"
        return api_client.post(endpoint, {})
    
    def _execute_create_work_order(self, api_client: 'APIClient') -> Dict[str, Any]:
        """Create a maintenance work order"""
        endpoint = "/api/modules/predictive-maintenance/work-order"
        return api_client.post(endpoint, {
            'machine_id': self.target_id,
            'description': self.parameters.get('description', 'Automated maintenance'),
            'priority': self.parameters.get('priority', 'high')
        })
    
    def _execute_notify(self) -> Dict[str, Any]:
        """Send notification to technicians"""
        print(f"[WORKFLOW] Notification: {self.parameters.get('message')}")
        return {'status': 'success', 'action': 'notify'}
    
    def _execute_log(self) -> Dict[str, Any]:
        """Log workflow event"""
        print(f"[WORKFLOW] Log: {self.parameters.get('message')}")
        return {'status': 'success', 'action': 'log'}


class Workflow:
    """Represents a multi-module workflow"""
    
    def __init__(self, workflow_id: str, name: str, description: str = ""):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.triggers: List[WorkflowTrigger] = []
        self.actions: List[WorkflowAction] = []
        self.enabled = True
        self.last_execution = None
        self.execution_count = 0
        self.execution_history: List[Dict] = []
    
    def add_trigger(self, trigger: WorkflowTrigger) -> 'Workflow':
        """Add a trigger to the workflow"""
        self.triggers.append(trigger)
        return self
    
    def add_action(self, action: WorkflowAction) -> 'Workflow':
        """Add an action to the workflow"""
        self.actions.append(action)
        return self
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if any trigger fires"""
        if not self.enabled:
            return False
        
        # All triggers must pass (AND logic)
        return all(trigger.should_fire(context) for trigger in self.triggers)
    
    def execute(self, api_client: 'APIClient', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all actions in the workflow"""
        if not self.evaluate(context):
            return {'status': 'skipped', 'reason': 'trigger_condition_not_met'}
        
        results = []
        for action in self.actions:
            try:
                result = action.execute(api_client)
                results.append({
                    'action': action.action_name,
                    'status': result.get('status', 'unknown'),
                    'result': result
                })
            except Exception as e:
                results.append({
                    'action': action.action_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        self.last_execution = datetime.utcnow()
        self.execution_count += 1
        
        execution_record = {
            'timestamp': self.last_execution.isoformat(),
            'context': context,
            'results': results
        }
        self.execution_history.append(execution_record)
        
        return {
            'status': 'executed',
            'workflow_id': self.workflow_id,
            'actions_count': len(self.actions),
            'results': results
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'triggers_count': len(self.triggers),
            'actions_count': len(self.actions),
            'execution_count': self.execution_count,
            'last_execution': self.last_execution.isoformat() if self.last_execution else None
        }


class WorkflowEngine:
    """Manages and executes workflows"""
    
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.execution_log: List[Dict] = []
    
    def register_workflow(self, workflow: Workflow) -> None:
        """Register a workflow with the engine"""
        self.workflows[workflow.workflow_id] = workflow
        print(f"[WorkflowEngine] Registered workflow: {workflow.name}")
    
    def evaluate_all(self, context: Dict[str, Any]) -> List[str]:
        """Evaluate all workflows and return IDs that should fire"""
        triggered = []
        for workflow_id, workflow in self.workflows.items():
            if workflow.evaluate(context):
                triggered.append(workflow_id)
        return triggered
    
    def execute_workflow(self, workflow_id: str, api_client: 'APIClient', 
                        context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific workflow"""
        if workflow_id not in self.workflows:
            return {'status': 'error', 'message': 'Workflow not found'}
        
        workflow = self.workflows[workflow_id]
        result = workflow.execute(api_client, context)
        
        self.execution_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'workflow_id': workflow_id,
            'result': result
        })
        
        return result
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows"""
        return [w.to_dict() for w in self.workflows.values()]
    
    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get details of a specific workflow"""
        if workflow_id not in self.workflows:
            return {'status': 'error', 'message': 'Workflow not found'}
        
        workflow = self.workflows[workflow_id]
        data = workflow.to_dict()
        data['execution_history'] = workflow.execution_history[-10:]  # Last 10 executions
        return data
    
    def get_execution_log(self, limit: int = 100) -> List[Dict]:
        """Get workflow execution log"""
        return self.execution_log[-limit:]


# ============================================================================
# Pre-built Workflow Templates
# ============================================================================

class WorkflowTemplates:
    """Collection of common workflow templates"""
    
    @staticmethod
    def create_predictive_maintenance_workflow(machine_id: str) -> Workflow:
        """
        Workflow: Equipment health critical -> pause machine -> create work order -> notify
        """
        workflow = Workflow(
            workflow_id=f"pm-critical-{machine_id}",
            name="Critical Health Response",
            description="Responds to critical equipment health by pausing machine and creating work order"
        )
        
        # Trigger: Health score drops below 40
        trigger = WorkflowTrigger(
            trigger_type=TriggerType.CONDITION,
            condition="health_score < 40"
        )
        workflow.add_trigger(trigger)
        
        # Action 1: Stop the machine
        workflow.add_action(WorkflowAction(
            action_type=ActionType.MACHINE_CONTROL,
            target_module='machine_simulator',
            target_id=machine_id,
            action_name='stop'
        ))
        
        # Action 2: Create urgent work order
        workflow.add_action(WorkflowAction(
            action_type=ActionType.CREATE_WORK_ORDER,
            target_module='predictive_maintenance',
            target_id=machine_id,
            action_name='create_order',
            parameters={
                'description': 'Critical health condition - urgent maintenance required',
                'priority': 'critical'
            }
        ))
        
        # Action 3: Notify technician
        workflow.add_action(WorkflowAction(
            action_type=ActionType.NOTIFY,
            target_module='notification',
            target_id=machine_id,
            action_name='alert',
            parameters={
                'message': f'CRITICAL: Machine {machine_id} requires immediate maintenance'
            }
        ))
        
        return workflow
    
    @staticmethod
    def create_temperature_warning_workflow(machine_id: str) -> Workflow:
        """
        Workflow: Temperature warning -> sync digital twin -> log event
        """
        workflow = Workflow(
            workflow_id=f"temp-warning-{machine_id}",
            name="Temperature Warning Response",
            description="Monitors temperature and syncs digital twin when threshold exceeded"
        )
        
        trigger = WorkflowTrigger(
            trigger_type=TriggerType.CONDITION,
            condition="temperature > 50"
        )
        workflow.add_trigger(trigger)
        
        workflow.add_action(WorkflowAction(
            action_type=ActionType.SYNC_TWIN,
            target_module='digital_twin',
            target_id=f"twin-{machine_id}",
            action_name='sync'
        ))
        
        workflow.add_action(WorkflowAction(
            action_type=ActionType.LOG,
            target_module='logger',
            target_id=machine_id,
            action_name='log',
            parameters={
                'message': f'High temperature warning for {machine_id}'
            }
        ))
        
        return workflow
    
    @staticmethod
    def create_anomaly_detection_workflow(machine_id: str) -> Workflow:
        """
        Workflow: Anomaly detected -> sync twin -> create work order -> notify
        """
        workflow = Workflow(
            workflow_id=f"anomaly-{machine_id}",
            name="Anomaly Detection Response",
            description="Responds to detected anomalies with investigation actions"
        )
        
        trigger = WorkflowTrigger(
            trigger_type=TriggerType.CONDITION,
            condition="vibration > 5.0 or pressure < 5.0"
        )
        workflow.add_trigger(trigger)
        
        workflow.add_action(WorkflowAction(
            action_type=ActionType.SYNC_TWIN,
            target_module='digital_twin',
            target_id=f"twin-{machine_id}",
            action_name='sync'
        ))
        
        workflow.add_action(WorkflowAction(
            action_type=ActionType.NOTIFY,
            target_module='notification',
            target_id=machine_id,
            action_name='alert',
            parameters={
                'message': f'Anomaly detected on machine {machine_id} - investigating'
            }
        ))
        
        return workflow


# ============================================================================
# API Client Mock (for workflow execution)
# ============================================================================

class APIClient:
    """Mock API client for workflow execution"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
    
    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute POST request"""
        print(f"[API] POST {self.base_url}{endpoint}")
        print(f"[API] Data: {json.dumps(data, indent=2)}")
        return {'status': 'success', 'endpoint': endpoint}
    
    def get(self, endpoint: str) -> Dict[str, Any]:
        """Execute GET request"""
        print(f"[API] GET {self.base_url}{endpoint}")
        return {'status': 'success', 'endpoint': endpoint}


# ============================================================================
# Example Usage
# ============================================================================

def example_workflow_usage():
    """Example of how to use the workflow system"""
    
    # Create workflow engine
    engine = WorkflowEngine()
    
    # Register pre-built workflows
    engine.register_workflow(
        WorkflowTemplates.create_predictive_maintenance_workflow('MILL-001')
    )
    engine.register_workflow(
        WorkflowTemplates.create_temperature_warning_workflow('MILL-001')
    )
    engine.register_workflow(
        WorkflowTemplates.create_anomaly_detection_workflow('MILL-001')
    )
    
    # Simulate incoming data context
    context = {
        'machine_id': 'MILL-001',
        'health_score': 35,           # Triggers critical workflow
        'temperature': 55,             # Triggers temperature warning
        'rpm': 1200,
        'vibration': 5.5,              # Triggers anomaly workflow
        'pressure': 4.8                # Triggers anomaly workflow
    }
    
    # Evaluate which workflows should fire
    triggered = engine.evaluate_all(context)
    print(f"Triggered workflows: {triggered}")
    
    # Execute triggered workflows
    api_client = APIClient()
    for workflow_id in triggered:
        result = engine.execute_workflow(workflow_id, api_client, context)
        print(f"Workflow {workflow_id} result: {json.dumps(result, indent=2)}")
    
    # List all workflows
    print(f"\nAll workflows: {json.dumps(engine.list_workflows(), indent=2)}")


if __name__ == '__main__':
    example_workflow_usage()
