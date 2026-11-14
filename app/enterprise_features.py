"""
Enterprise Features Module
Implements multi-tenancy, RBAC, audit logging, and compliance features
"""

import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class Role(Enum):
    """System roles"""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"
    CUSTOM = "custom"


class Permission(Enum):
    """System permissions"""
    # Machine management
    MACHINES_READ = "machines:read"
    MACHINES_WRITE = "machines:write"
    MACHINES_DELETE = "machines:delete"
    MACHINES_CONFIG = "machines:config"
    
    # Workflow management
    WORKFLOWS_READ = "workflows:read"
    WORKFLOWS_WRITE = "workflows:write"
    WORKFLOWS_EXECUTE = "workflows:execute"
    WORKFLOWS_DELETE = "workflows:delete"
    
    # User management
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_DELETE = "users:delete"
    
    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    
    # Administration
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_COMPLIANCE = "admin:compliance"


class RoleBasedAccessControl:
    """Role-based access control system"""
    
    # Default role permissions
    DEFAULT_PERMISSIONS = {
        Role.SUPER_ADMIN: set(Permission),  # All permissions
        Role.TENANT_ADMIN: {
            Permission.MACHINES_READ, Permission.MACHINES_WRITE, Permission.MACHINES_CONFIG,
            Permission.WORKFLOWS_READ, Permission.WORKFLOWS_WRITE, Permission.WORKFLOWS_EXECUTE,
            Permission.USERS_READ, Permission.USERS_WRITE,
            Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT,
            Permission.ADMIN_SETTINGS, Permission.ADMIN_AUDIT
        },
        Role.MANAGER: {
            Permission.MACHINES_READ, Permission.MACHINES_WRITE,
            Permission.WORKFLOWS_READ, Permission.WORKFLOWS_WRITE, Permission.WORKFLOWS_EXECUTE,
            Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT
        },
        Role.OPERATOR: {
            Permission.MACHINES_READ, Permission.MACHINES_WRITE,
            Permission.WORKFLOWS_READ, Permission.WORKFLOWS_EXECUTE,
            Permission.ANALYTICS_READ
        },
        Role.VIEWER: {
            Permission.MACHINES_READ,
            Permission.WORKFLOWS_READ,
            Permission.ANALYTICS_READ
        }
    }
    
    def __init__(self):
        self.user_roles: Dict[str, Set[Role]] = {}
        self.custom_roles: Dict[str, Dict[str, Any]] = {}
        self.role_permissions: Dict[Role, Set[Permission]] = self.DEFAULT_PERMISSIONS.copy()
    
    def assign_role(self, user_id: str, role: Role):
        """Assign role to user"""
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        
        self.user_roles[user_id].add(role)
        logger.info(f"Assigned role {role.value} to user {user_id}")
    
    def remove_role(self, user_id: str, role: Role):
        """Remove role from user"""
        if user_id in self.user_roles:
            self.user_roles[user_id].discard(role)
            logger.info(f"Removed role {role.value} from user {user_id}")
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has permission"""
        if user_id not in self.user_roles:
            return False
        
        user_roles = self.user_roles[user_id]
        
        for role in user_roles:
            if permission in self.role_permissions.get(role, set()):
                return True
        
        return False
    
    def create_custom_role(self, role_name: str, permissions: List[Permission]) -> bool:
        """Create custom role"""
        role_id = f"custom_{role_name}"
        if role_id in self.custom_roles:
            return False
        
        self.custom_roles[role_id] = {
            'name': role_name,
            'permissions': permissions,
            'created_at': datetime.now()
        }
        
        logger.info(f"Created custom role: {role_name}")
        return True
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for user"""
        permissions = set()
        
        if user_id in self.user_roles:
            for role in self.user_roles[user_id]:
                permissions.update(self.role_permissions.get(role, set()))
        
        return permissions


class MultiTenancy:
    """Multi-tenancy support"""
    
    def __init__(self):
        self.tenants: Dict[str, Dict[str, Any]] = {}
        self.user_tenant_mapping: Dict[str, str] = {}  # user_id -> tenant_id
        self.tenant_resources: Dict[str, Dict[str, Any]] = {}  # tenant_id -> resources
    
    def create_tenant(self, tenant_id: str, tenant_name: str, 
                     settings: Dict[str, Any] = None) -> bool:
        """Create new tenant"""
        if tenant_id in self.tenants:
            return False
        
        self.tenants[tenant_id] = {
            'id': tenant_id,
            'name': tenant_name,
            'created_at': datetime.now(),
            'settings': settings or {},
            'status': 'active',
            'quotas': {
                'max_users': 100,
                'max_machines': 1000,
                'max_workflows': 500,
                'storage_gb': 100
            }
        }
        
        self.tenant_resources[tenant_id] = {
            'users': 0,
            'machines': 0,
            'workflows': 0,
            'storage_used_gb': 0
        }
        
        logger.info(f"Created tenant: {tenant_name} ({tenant_id})")
        return True
    
    def assign_user_to_tenant(self, user_id: str, tenant_id: str) -> bool:
        """Assign user to tenant"""
        if tenant_id not in self.tenants:
            return False
        
        self.user_tenant_mapping[user_id] = tenant_id
        self.tenant_resources[tenant_id]['users'] += 1
        
        logger.info(f"Assigned user {user_id} to tenant {tenant_id}")
        return True
    
    def get_user_tenant(self, user_id: str) -> Optional[str]:
        """Get tenant for user"""
        return self.user_tenant_mapping.get(user_id)
    
    def check_tenant_quota(self, tenant_id: str, resource_type: str) -> bool:
        """Check if tenant has quota available"""
        if tenant_id not in self.tenants:
            return False
        
        tenant = self.tenants[tenant_id]
        resources = self.tenant_resources[tenant_id]
        
        quota_key = f"max_{resource_type}"
        resource_key = f"{resource_type}_count" if resource_type != "storage" else "storage_used_gb"
        
        if quota_key not in tenant['quotas']:
            return True  # No quota limit
        
        return resources.get(resource_key, 0) < tenant['quotas'][quota_key]
    
    def list_tenant_users(self, tenant_id: str) -> List[str]:
        """List all users in tenant"""
        return [uid for uid, tid in self.user_tenant_mapping.items() if tid == tenant_id]


class AuditLog:
    """Audit logging for compliance"""
    
    def __init__(self, max_logs: int = 10000):
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = max_logs
    
    def log_action(self, user_id: str, action: str, resource_type: str, 
                   resource_id: str, status: str = 'success', details: Dict = None):
        """Log user action"""
        log_entry = {
            'timestamp': datetime.now(),
            'user_id': user_id,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'status': status,
            'details': details or {}
        }
        
        self.logs.append(log_entry)
        
        # Keep memory bounded
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        logger.debug(f"Audit log: {user_id} {action} {resource_type}/{resource_id} {status}")
    
    def get_logs(self, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict]:
        """Get audit logs with filters"""
        filtered_logs = self.logs
        
        if filters:
            if 'user_id' in filters:
                filtered_logs = [l for l in filtered_logs if l['user_id'] == filters['user_id']]
            
            if 'action' in filters:
                filtered_logs = [l for l in filtered_logs if l['action'] == filters['action']]
            
            if 'resource_type' in filters:
                filtered_logs = [l for l in filtered_logs if l['resource_type'] == filters['resource_type']]
            
            if 'start_date' in filters:
                filtered_logs = [l for l in filtered_logs if l['timestamp'] >= filters['start_date']]
        
        return filtered_logs[-limit:]  # Return most recent
    
    def get_user_activity(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get user activity summary"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        user_logs = [l for l in self.logs if l['user_id'] == user_id and l['timestamp'].timestamp() > cutoff]
        
        actions = {}
        for log in user_logs:
            action = log['action']
            actions[action] = actions.get(action, 0) + 1
        
        return {
            'user_id': user_id,
            'total_actions': len(user_logs),
            'actions_breakdown': actions,
            'last_activity': user_logs[-1]['timestamp'] if user_logs else None
        }


class ComplianceReporter:
    """Generate compliance reports"""
    
    def __init__(self, audit_log: AuditLog):
        self.audit_log = audit_log
    
    def generate_gdpr_report(self, user_id: str) -> Dict[str, Any]:
        """Generate GDPR data subject report"""
        logs = self.audit_log.get_logs({'user_id': user_id}, limit=10000)
        
        return {
            'user_id': user_id,
            'report_type': 'GDPR_DSR',
            'generated_at': datetime.now().isoformat(),
            'data_processed': len(logs),
            'date_range': {
                'earliest': logs[0]['timestamp'].isoformat() if logs else None,
                'latest': logs[-1]['timestamp'].isoformat() if logs else None
            },
            'access_log': logs
        }
    
    def generate_soc2_report(self, days: int = 90) -> Dict[str, Any]:
        """Generate SOC 2 compliance report"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        recent_logs = [l for l in self.audit_log.logs if l['timestamp'].timestamp() > cutoff]
        
        # Count by action type
        actions_summary = {}
        failures = 0
        
        for log in recent_logs:
            action = log['action']
            actions_summary[action] = actions_summary.get(action, 0) + 1
            if log['status'] == 'failed':
                failures += 1
        
        return {
            'report_type': 'SOC2',
            'period_days': days,
            'generated_at': datetime.now().isoformat(),
            'total_actions': len(recent_logs),
            'total_failures': failures,
            'failure_rate': f"{failures / len(recent_logs) * 100:.2f}%" if recent_logs else "0%",
            'actions_summary': actions_summary
        }
    
    def generate_audit_trail_report(self, resource_type: str, 
                                   resource_id: str) -> Dict[str, Any]:
        """Generate audit trail for specific resource"""
        logs = self.audit_log.get_logs(
            {'resource_type': resource_type, 'resource_id': resource_id},
            limit=10000
        )
        
        return {
            'resource_type': resource_type,
            'resource_id': resource_id,
            'total_changes': len(logs),
            'audit_trail': logs,
            'first_change': logs[0]['timestamp'].isoformat() if logs else None,
            'last_change': logs[-1]['timestamp'].isoformat() if logs else None
        }


# Global instances
_rbac = None
_multi_tenancy = None
_audit_log = None
_compliance = None


def init_enterprise_features() -> Dict[str, Any]:
    """Initialize enterprise features"""
    global _rbac, _multi_tenancy, _audit_log, _compliance
    
    _rbac = RoleBasedAccessControl()
    _multi_tenancy = MultiTenancy()
    _audit_log = AuditLog()
    _compliance = ComplianceReporter(_audit_log)
    
    logger.info("Enterprise features initialized")
    
    return {
        'rbac': _rbac,
        'multi_tenancy': _multi_tenancy,
        'audit_log': _audit_log,
        'compliance': _compliance
    }


def get_rbac() -> RoleBasedAccessControl:
    """Get RBAC instance"""
    return _rbac


def get_multi_tenancy() -> MultiTenancy:
    """Get multi-tenancy instance"""
    return _multi_tenancy


def get_audit_log() -> AuditLog:
    """Get audit log instance"""
    return _audit_log


def get_compliance() -> ComplianceReporter:
    """Get compliance reporter instance"""
    return _compliance
