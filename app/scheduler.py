"""
Workflow Scheduler Module
Enables scheduled workflow execution using cron expressions and time-based triggers
"""

import logging
import json
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Schedule types for workflows"""
    CRON = "cron"  # Cron expression (e.g., "0 9 * * *" = 9 AM daily)
    INTERVAL = "interval"  # Fixed interval (seconds)
    DAILY = "daily"  # Daily at specific time
    WEEKLY = "weekly"  # Weekly on specific day/time
    MONTHLY = "monthly"  # Monthly on specific day/time


class CronSchedule:
    """Parse and evaluate cron expressions"""
    
    # Simplified cron parser (minute hour day month day_of_week)
    FIELDS = ['minute', 'hour', 'day', 'month', 'day_of_week']
    
    def __init__(self, cron_expr: str):
        """
        Initialize cron schedule
        
        Args:
            cron_expr: Cron expression (e.g., "0 9 * * *")
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        
        self.minute = parts[0]
        self.hour = parts[1]
        self.day = parts[2]
        self.month = parts[3]
        self.day_of_week = parts[4]
        self.cron_expr = cron_expr
    
    def should_run(self, dt: datetime) -> bool:
        """
        Check if a workflow should run at given datetime
        
        Args:
            dt: Datetime to check
        
        Returns:
            True if cron expression matches
        """
        return (
            self._match_field(self.minute, dt.minute) and
            self._match_field(self.hour, dt.hour) and
            self._match_field(self.day, dt.day) and
            self._match_field(self.month, dt.month) and
            self._match_field(self.day_of_week, dt.weekday())
        )
    
    @staticmethod
    def _match_field(pattern: str, value: int) -> bool:
        """Check if cron pattern matches value"""
        if pattern == '*':
            return True
        
        # Handle ranges (e.g., "9-17")
        if '-' in pattern:
            start, end = pattern.split('-')
            return int(start) <= value <= int(end)
        
        # Handle lists (e.g., "0,6")
        if ',' in pattern:
            return str(value) in pattern.split(',')
        
        # Handle steps (e.g., "*/15" = every 15 minutes)
        if '/' in pattern:
            base, step = pattern.split('/')
            if base == '*':
                return value % int(step) == 0
        
        # Exact match
        return str(value) == pattern


class WorkflowSchedule:
    """Schedule for workflow execution"""
    
    def __init__(self, schedule_type: ScheduleType, schedule_value: str):
        """
        Initialize workflow schedule
        
        Args:
            schedule_type: Type of schedule
            schedule_value: Schedule expression (cron, interval, time, etc.)
        """
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.created_at = datetime.now()
        self.last_run = None
        self.next_run = self._calculate_next_run()
    
    def _calculate_next_run(self) -> datetime:
        """Calculate next run time"""
        now = datetime.now()
        
        if self.schedule_type == ScheduleType.CRON:
            cron = CronSchedule(self.schedule_value)
            # Find next matching time (check every minute for up to 1 year)
            check_time = now.replace(second=0, microsecond=0)
            for _ in range(525600):  # 1 year in minutes
                check_time += timedelta(minutes=1)
                if cron.should_run(check_time):
                    return check_time
            return None
        
        elif self.schedule_type == ScheduleType.INTERVAL:
            interval = int(self.schedule_value)
            return now + timedelta(seconds=interval)
        
        elif self.schedule_type == ScheduleType.DAILY:
            hour, minute = map(int, self.schedule_value.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        
        elif self.schedule_type == ScheduleType.WEEKLY:
            # Format: "MON:09:00" (day:hour:minute)
            day_name, time_str = self.schedule_value.split(':')[0], ':'.join(self.schedule_value.split(':')[1:])
            days = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5, 'SUN': 6}
            target_day = days.get(day_name, 0)
            hour, minute = map(int, time_str.split(':'))
            
            days_ahead = (target_day - now.weekday()) % 7
            if days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute > minute)):
                days_ahead = 7
            
            return now + timedelta(days=days_ahead, hours=hour-now.hour, minutes=minute-now.minute)
        
        return None
    
    def should_run_now(self) -> bool:
        """Check if schedule should run now"""
        if not self.next_run:
            return False
        
        now = datetime.now()
        # Allow 1-minute window for execution
        return now >= self.next_run and now < self.next_run + timedelta(minutes=1)


class ScheduledWorkflow:
    """A workflow with schedule information"""
    
    def __init__(self, workflow_id: str, workflow_name: str, schedule: WorkflowSchedule, 
                 enabled: bool = True, timezone: str = 'UTC'):
        """
        Initialize scheduled workflow
        
        Args:
            workflow_id: Unique workflow ID
            workflow_name: Friendly workflow name
            schedule: WorkflowSchedule object
            enabled: Whether workflow is enabled
            timezone: Timezone for scheduling
        """
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.schedule = schedule
        self.enabled = enabled
        self.timezone = timezone
        self.execution_history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
    
    def mark_executed(self, success: bool = True, duration: float = 0, error: str = None):
        """Record workflow execution"""
        execution = {
            'timestamp': datetime.now(),
            'success': success,
            'duration': duration,
            'error': error
        }
        self.execution_history.append(execution)
        
        # Keep only last 100 executions
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
        
        # Update next run
        self.schedule.last_run = datetime.now()
        self.schedule.next_run = self.schedule._calculate_next_run()
        
        status = "success" if success else "failed"
        logger.info(f"Workflow '{self.workflow_name}' executed: {status} ({duration:.2f}s)")
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get workflow execution statistics"""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'success_count': 0,
                'failure_count': 0,
                'success_rate': 0,
                'avg_duration': 0
            }
        
        successes = sum(1 for e in self.execution_history if e['success'])
        failures = len(self.execution_history) - successes
        avg_duration = sum(e['duration'] for e in self.execution_history) / len(self.execution_history)
        
        return {
            'total_executions': len(self.execution_history),
            'success_count': successes,
            'failure_count': failures,
            'success_rate': f"{successes / len(self.execution_history) * 100:.1f}%",
            'avg_duration': f"{avg_duration:.2f}s",
            'last_execution': self.execution_history[-1]['timestamp'].isoformat() if self.execution_history else None
        }


class WorkflowScheduler:
    """Manages workflow scheduling and execution"""
    
    def __init__(self):
        self.scheduled_workflows: Dict[str, ScheduledWorkflow] = {}
        self.execution_callbacks: Dict[str, Callable] = {}
        self.running = False
        self.scheduler_thread = None
        self.execution_stats = {
            'total_executed': 0,
            'total_success': 0,
            'total_failed': 0,
            'average_duration': 0
        }
    
    def register_workflow(self, scheduled_workflow: ScheduledWorkflow, callback: Callable):
        """
        Register a scheduled workflow
        
        Args:
            scheduled_workflow: ScheduledWorkflow instance
            callback: Function to execute (receives workflow_id as argument)
        """
        self.scheduled_workflows[scheduled_workflow.workflow_id] = scheduled_workflow
        self.execution_callbacks[scheduled_workflow.workflow_id] = callback
        logger.info(f"Registered workflow: {scheduled_workflow.workflow_name}")
    
    def unregister_workflow(self, workflow_id: str):
        """Unregister a workflow"""
        if workflow_id in self.scheduled_workflows:
            del self.scheduled_workflows[workflow_id]
            del self.execution_callbacks[workflow_id]
            logger.info(f"Unregistered workflow: {workflow_id}")
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Workflow scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Workflow scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                self._check_and_execute_workflows()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    def _check_and_execute_workflows(self):
        """Check and execute due workflows"""
        for workflow_id, workflow in self.scheduled_workflows.items():
            if not workflow.enabled:
                continue
            
            if workflow.schedule.should_run_now():
                self._execute_workflow(workflow_id, workflow)
    
    def _execute_workflow(self, workflow_id: str, workflow: ScheduledWorkflow):
        """Execute a workflow"""
        if workflow_id not in self.execution_callbacks:
            logger.error(f"No callback registered for workflow: {workflow_id}")
            return
        
        start_time = time.time()
        try:
            callback = self.execution_callbacks[workflow_id]
            callback(workflow_id)
            
            duration = time.time() - start_time
            workflow.mark_executed(success=True, duration=duration)
            
            self.execution_stats['total_executed'] += 1
            self.execution_stats['total_success'] += 1
        
        except Exception as e:
            duration = time.time() - start_time
            workflow.mark_executed(success=False, duration=duration, error=str(e))
            
            self.execution_stats['total_executed'] += 1
            self.execution_stats['total_failed'] += 1
            logger.error(f"Workflow execution failed: {workflow_id} - {str(e)}")
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of a workflow"""
        if workflow_id not in self.scheduled_workflows:
            return None
        
        workflow = self.scheduled_workflows[workflow_id]
        return {
            'workflow_id': workflow.workflow_id,
            'workflow_name': workflow.workflow_name,
            'enabled': workflow.enabled,
            'schedule_type': workflow.schedule.schedule_type.value,
            'schedule_value': workflow.schedule.schedule_value,
            'next_run': workflow.schedule.next_run.isoformat() if workflow.schedule.next_run else None,
            'last_run': workflow.schedule.last_run.isoformat() if workflow.schedule.last_run else None,
            'statistics': workflow.get_execution_stats()
        }
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all scheduled workflows"""
        return [self.get_workflow_status(wid) for wid in self.scheduled_workflows.keys()]
    
    def enable_workflow(self, workflow_id: str):
        """Enable a workflow"""
        if workflow_id in self.scheduled_workflows:
            self.scheduled_workflows[workflow_id].enabled = True
            logger.info(f"Workflow enabled: {workflow_id}")
    
    def disable_workflow(self, workflow_id: str):
        """Disable a workflow"""
        if workflow_id in self.scheduled_workflows:
            self.scheduled_workflows[workflow_id].enabled = False
            logger.info(f"Workflow disabled: {workflow_id}")
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        avg_duration = 0
        total_duration = sum(
            e['duration']
            for wf in self.scheduled_workflows.values()
            for e in wf.execution_history
        )
        total_executions = sum(
            len(wf.execution_history)
            for wf in self.scheduled_workflows.values()
        )
        if total_executions > 0:
            avg_duration = total_duration / total_executions
        
        return {
            'scheduler_running': self.running,
            'total_workflows': len(self.scheduled_workflows),
            'enabled_workflows': sum(1 for wf in self.scheduled_workflows.values() if wf.enabled),
            'total_executions': self.execution_stats['total_executed'],
            'successful_executions': self.execution_stats['total_success'],
            'failed_executions': self.execution_stats['total_failed'],
            'success_rate': f"{self.execution_stats['total_success'] / max(1, self.execution_stats['total_executed']) * 100:.1f}%",
            'average_execution_time': f"{avg_duration:.2f}s"
        }


# Global scheduler instance
_scheduler: Optional[WorkflowScheduler] = None


def init_scheduler() -> WorkflowScheduler:
    """Initialize global scheduler"""
    global _scheduler
    _scheduler = WorkflowScheduler()
    _scheduler.start()
    logger.info("Workflow scheduler initialized")
    return _scheduler


def get_scheduler() -> Optional[WorkflowScheduler]:
    """Get global scheduler instance"""
    return _scheduler


# Example pre-built scheduled workflow templates
class ScheduledWorkflowTemplates:
    """Pre-built scheduled workflow templates"""
    
    @staticmethod
    def daily_health_check() -> ScheduledWorkflow:
        """Daily machine health check at 2 AM"""
        schedule = WorkflowSchedule(ScheduleType.DAILY, "02:00")
        workflow = ScheduledWorkflow(
            workflow_id="daily_health_check",
            workflow_name="Daily Health Check",
            schedule=schedule
        )
        return workflow
    
    @staticmethod
    def hourly_performance_analysis() -> ScheduledWorkflow:
        """Hourly performance analysis (every hour on the hour)"""
        schedule = WorkflowSchedule(ScheduleType.CRON, "0 * * * *")
        workflow = ScheduledWorkflow(
            workflow_id="hourly_performance",
            workflow_name="Hourly Performance Analysis",
            schedule=schedule
        )
        return workflow
    
    @staticmethod
    def weekly_maintenance_report() -> ScheduledWorkflow:
        """Weekly maintenance report every Monday at 9 AM"""
        schedule = WorkflowSchedule(ScheduleType.WEEKLY, "MON:09:00")
        workflow = ScheduledWorkflow(
            workflow_id="weekly_maintenance",
            workflow_name="Weekly Maintenance Report",
            schedule=schedule
        )
        return workflow
    
    @staticmethod
    def monthly_optimization() -> ScheduledWorkflow:
        """Monthly optimization on 1st of month at midnight"""
        schedule = WorkflowSchedule(ScheduleType.CRON, "0 0 1 * *")
        workflow = ScheduledWorkflow(
            workflow_id="monthly_optimization",
            workflow_name="Monthly Optimization",
            schedule=schedule
        )
        return workflow
