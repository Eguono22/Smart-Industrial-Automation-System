"""
Phase 8.5: Infrastructure Monitoring & Observability

Provides:
- Prometheus metrics collection
- Health check endpoints
- Performance monitoring
- Cost tracking
- Alert generation
"""

from datetime import datetime, timedelta
import time
import json
from typing import Dict, List, Any, Tuple
from functools import wraps
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Collect and track performance metrics for API endpoints."""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'total_requests': 0,
            'total_errors': 0,
            'total_response_time': 0,
            'min_response_time': float('inf'),
            'max_response_time': 0,
            'response_times': [],
            'error_codes': defaultdict(int),
        })
        self.start_time = time.time()
    
    def record_request(self, endpoint: str, response_time: float, 
                      status_code: int, error: bool = False):
        """Record a request metric."""
        metric = self.metrics[endpoint]
        
        metric['total_requests'] += 1
        metric['total_response_time'] += response_time
        metric['min_response_time'] = min(metric['min_response_time'], response_time)
        metric['max_response_time'] = max(metric['max_response_time'], response_time)
        metric['response_times'].append(response_time)
        
        if error:
            metric['total_errors'] += 1
            metric['error_codes'][status_code] += 1
        
        # Keep only last 1000 response times for percentile calculation
        if len(metric['response_times']) > 1000:
            metric['response_times'] = metric['response_times'][-1000:]
    
    def get_percentile(self, endpoint: str, percentile: int) -> float:
        """Calculate response time percentile."""
        times = self.metrics[endpoint]['response_times']
        if not times:
            return 0
        
        times_sorted = sorted(times)
        index = int(len(times_sorted) * (percentile / 100))
        return times_sorted[min(index, len(times_sorted) - 1)]
    
    def get_metrics(self, endpoint: str = None) -> Dict[str, Any]:
        """Get metrics for endpoint or all endpoints."""
        if endpoint:
            metric = self.metrics.get(endpoint, {})
            if not metric.get('total_requests'):
                return {}
            
            return {
                'endpoint': endpoint,
                'total_requests': metric['total_requests'],
                'total_errors': metric['total_errors'],
                'error_rate': (metric['total_errors'] / metric['total_requests'] * 100) 
                             if metric['total_requests'] else 0,
                'avg_response_time': metric['total_response_time'] / metric['total_requests'],
                'min_response_time': metric['min_response_time'],
                'max_response_time': metric['max_response_time'],
                'p50_response_time': self.get_percentile(endpoint, 50),
                'p95_response_time': self.get_percentile(endpoint, 95),
                'p99_response_time': self.get_percentile(endpoint, 99),
                'error_codes': dict(metric['error_codes']),
            }
        
        result = {}
        for ep in self.metrics:
            result[ep] = self.get_metrics(ep)
        return result
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        uptime = time.time() - self.start_time
        total_requests = sum(m['total_requests'] for m in self.metrics.values())
        total_errors = sum(m['total_errors'] for m in self.metrics.values())
        
        return {
            'uptime_seconds': uptime,
            'total_requests': total_requests,
            'total_errors': total_errors,
            'requests_per_second': total_requests / uptime if uptime > 0 else 0,
            'error_rate': (total_errors / total_requests * 100) if total_requests else 0,
            'endpoints_monitored': len(self.metrics),
            'timestamp': datetime.utcnow().isoformat(),
        }


class CostTracker:
    """Track and analyze infrastructure costs."""
    
    # Hourly rates (USD)
    RATES = {
        'compute': {
            'on_demand': 0.5,      # per hour
            'reserved': 0.3,        # per hour
            'spot': 0.15,           # per hour
        },
        'database': {
            'primary': 1.5,         # per hour
            'replica': 0.75,        # per hour
        },
        'cache': {
            'redis': 0.25,          # per hour per 1GB
        },
        'network': {
            'transfer_out': 0.12,   # per GB
            'load_balancer': 0.025, # per hour
        },
        'storage': {
            'volume': 0.1,          # per GB per month = 0.0000138/hour
            'backup': 0.05,         # per GB per month = 0.0000069/hour
        },
    }
    
    def __init__(self):
        self.cost_history = []
        self.resource_usage = defaultdict(float)
        self.start_time = datetime.utcnow()
    
    def record_resource_usage(self, resource_type: str, quantity: float):
        """Record resource usage for cost calculation."""
        self.resource_usage[resource_type] += quantity
    
    def calculate_hourly_cost(self) -> Dict[str, float]:
        """Calculate hourly cost by category."""
        costs = {}
        
        # Compute costs
        costs['compute'] = (
            self.resource_usage['compute_on_demand'] * self.RATES['compute']['on_demand'] +
            self.resource_usage['compute_reserved'] * self.RATES['compute']['reserved'] +
            self.resource_usage['compute_spot'] * self.RATES['compute']['spot']
        )
        
        # Database costs
        costs['database'] = (
            self.resource_usage['db_primary'] * self.RATES['database']['primary'] +
            self.resource_usage['db_replica'] * self.RATES['database']['replica']
        )
        
        # Cache costs
        costs['cache'] = (
            self.resource_usage['cache_gb'] * self.RATES['cache']['redis']
        )
        
        # Network costs
        costs['network'] = (
            self.resource_usage['network_transfer_gb'] * self.RATES['network']['transfer_out'] +
            self.RATES['network']['load_balancer']
        )
        
        # Storage costs
        costs['storage'] = (
            (self.resource_usage['storage_volume_gb'] * self.RATES['storage']['volume'] / 730) +
            (self.resource_usage['storage_backup_gb'] * self.RATES['storage']['backup'] / 730)
        )
        
        costs['total'] = sum(costs.values())
        return costs
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary."""
        hourly = self.calculate_hourly_cost()
        return {
            'hourly_cost': hourly,
            'daily_cost': {k: v * 24 for k, v in hourly.items()},
            'monthly_cost': {k: v * 24 * 30 for k, v in hourly.items()},
            'annual_cost': {k: v * 24 * 365 for k, v in hourly.items()},
        }


class HealthChecker:
    """Health check for all system components."""
    
    def __init__(self, db=None, redis_client=None):
        self.db = db
        self.redis_client = redis_client
        self.last_check = {}
        self.check_interval = 30  # seconds
    
    def check_database(self) -> Tuple[bool, str]:
        """Check database health."""
        try:
            if not self.db:
                return False, "Database not initialized"
            
            # Simple query to test connection
            result = self.db.session.execute("SELECT 1")
            return True, "Database healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False, f"Database error: {str(e)}"
    
    def check_cache(self) -> Tuple[bool, str]:
        """Check cache (Redis) health."""
        try:
            if not self.redis_client:
                return False, "Redis not initialized"
            
            self.redis_client.ping()
            return True, "Cache healthy"
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False, f"Cache error: {str(e)}"
    
    def check_api(self) -> Tuple[bool, str]:
        """Check API health."""
        try:
            # This would be called from a health endpoint
            return True, "API healthy"
        except Exception as e:
            return False, f"API error: {str(e)}"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        db_health, db_msg = self.check_database()
        cache_health, cache_msg = self.check_cache()
        api_health, api_msg = self.check_api()
        
        overall_healthy = all([db_health, cache_health, api_health])
        
        return {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'database': {
                    'status': 'up' if db_health else 'down',
                    'message': db_msg,
                },
                'cache': {
                    'status': 'up' if cache_health else 'down',
                    'message': cache_msg,
                },
                'api': {
                    'status': 'up' if api_health else 'down',
                    'message': api_msg,
                },
            }
        }


class AlertManager:
    """Manage alerts based on metrics."""
    
    THRESHOLDS = {
        'error_rate': 1.0,              # % errors
        'response_time_p99': 500,       # ms
        'response_time_p95': 300,       # ms
        'cpu_usage': 80,                # %
        'memory_usage': 85,             # %
        'cache_hit_rate': 70,           # %
        'db_connections': 90,           # % of pool
        'replication_lag': 30,          # seconds
    }
    
    def __init__(self):
        self.active_alerts = {}
        self.alert_history = []
    
    def check_metrics(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        
        # Check error rate
        if metrics.get('error_rate', 0) > self.THRESHOLDS['error_rate']:
            alerts.append({
                'severity': 'critical',
                'type': 'error_rate',
                'message': f"Error rate {metrics['error_rate']:.2f}% exceeds threshold",
                'value': metrics['error_rate'],
                'threshold': self.THRESHOLDS['error_rate'],
            })
        
        # Check response times
        if metrics.get('p99_response_time', 0) > self.THRESHOLDS['response_time_p99']:
            alerts.append({
                'severity': 'warning',
                'type': 'slow_response_p99',
                'message': f"P99 response time {metrics['p99_response_time']:.0f}ms exceeds threshold",
                'value': metrics['p99_response_time'],
                'threshold': self.THRESHOLDS['response_time_p99'],
            })
        
        if metrics.get('p95_response_time', 0) > self.THRESHOLDS['response_time_p95']:
            alerts.append({
                'severity': 'info',
                'type': 'slow_response_p95',
                'message': f"P95 response time {metrics['p95_response_time']:.0f}ms exceeds threshold",
                'value': metrics['p95_response_time'],
                'threshold': self.THRESHOLDS['response_time_p95'],
            })
        
        # Record alerts
        for alert in alerts:
            alert['timestamp'] = datetime.utcnow().isoformat()
            self.active_alerts[alert['type']] = alert
            self.alert_history.append(alert)
        
        return alerts
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def clear_alert(self, alert_type: str):
        """Clear an active alert."""
        if alert_type in self.active_alerts:
            del self.active_alerts[alert_type]
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history for last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            a for a in self.alert_history
            if datetime.fromisoformat(a['timestamp']) > cutoff
        ]


def track_performance(func):
    """Decorator to track performance metrics for a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        status_code = 200
        error = False
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = True
            status_code = 500
            raise
        finally:
            response_time = (time.time() - start_time) * 1000  # ms
            endpoint = getattr(func, '__name__', 'unknown')
            
            # This would integrate with the global metrics collector
            logger.info(
                f"Endpoint: {endpoint}, Response Time: {response_time:.2f}ms, "
                f"Status: {status_code}, Error: {error}"
            )
    
    return wrapper


class MetricsCollector:
    """Central metrics collector for entire system."""
    
    def __init__(self):
        self.performance = PerformanceMetrics()
        self.cost = CostTracker()
        self.alerts = AlertManager()
        self.health = None  # Set after app initialization
        self.last_summary = None
    
    def generate_prometheus_metrics(self) -> str:
        """Generate Prometheus-format metrics."""
        metrics_text = "# HELP sias_metrics SIAS Application Metrics\n"
        metrics_text += "# TYPE sias_metrics gauge\n"
        
        system_metrics = self.performance.get_system_metrics()
        
        # System metrics
        metrics_text += f"sias_uptime_seconds {system_metrics['uptime_seconds']}\n"
        metrics_text += f"sias_total_requests {system_metrics['total_requests']}\n"
        metrics_text += f"sias_total_errors {system_metrics['total_errors']}\n"
        metrics_text += f"sias_requests_per_second {system_metrics['requests_per_second']}\n"
        metrics_text += f"sias_error_rate {system_metrics['error_rate']}\n"
        
        # Per-endpoint metrics
        for endpoint, metrics in self.performance.get_metrics().items():
            if metrics:
                safe_endpoint = endpoint.replace('/', '_').replace('-', '_')
                metrics_text += f"sias_endpoint_{safe_endpoint}_requests {metrics['total_requests']}\n"
                metrics_text += f"sias_endpoint_{safe_endpoint}_avg_response_time {metrics['avg_response_time']}\n"
                metrics_text += f"sias_endpoint_{safe_endpoint}_p95_response_time {metrics['p95_response_time']}\n"
                metrics_text += f"sias_endpoint_{safe_endpoint}_error_rate {metrics['error_rate']}\n"
        
        # Cost metrics
        hourly_costs = self.cost.calculate_hourly_cost()
        for category, cost in hourly_costs.items():
            metrics_text += f"sias_hourly_cost_{category} {cost}\n"
        
        return metrics_text
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get summary for monitoring dashboard."""
        system_metrics = self.performance.get_system_metrics()
        health_status = self.health.get_health_status() if self.health else {}
        cost_summary = self.cost.get_cost_summary()
        active_alerts = self.alerts.get_active_alerts()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'system': system_metrics,
            'health': health_status,
            'costs': cost_summary,
            'alerts': active_alerts,
            'endpoints': self.performance.get_metrics(),
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()
