"""
Phase 8.6: Self-Healing & Anomaly Detection Engine

Provides:
- Automatic recovery from common failures
- ML-based anomaly detection
- Alert correlation and aggregation
- Predictive operations
"""

from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque
import numpy as np
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class RecoveryStatus(Enum):
    """Recovery action status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"


@dataclass
class Alert:
    """Alert message."""
    type: str
    severity: AlertSeverity
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime
    source: str  # e.g., 'api', 'database', 'cache'


@dataclass
class AnomalyScore:
    """Anomaly detection score."""
    metric: str
    timestamp: datetime
    value: float
    score: float  # 0-1, higher = more anomalous
    is_anomaly: bool
    reason: str
    confidence: float  # 0-1


class AnomalyDetector(ABC):
    """Base class for anomaly detection."""
    
    @abstractmethod
    def detect(self, value: float) -> AnomalyScore:
        """Detect if value is anomalous."""
        pass
    
    @abstractmethod
    def train(self, historical_values: List[float]):
        """Train detector on historical data."""
        pass


class StatisticalAnomalyDetector(AnomalyDetector):
    """Detect anomalies using statistical methods (Z-score)."""
    
    def __init__(self, z_threshold: float = 3.0):
        self.z_threshold = z_threshold
        self.mean = None
        self.std = None
        self.trained = False
    
    def train(self, historical_values: List[float]):
        """Calculate mean and standard deviation."""
        if len(historical_values) < 10:
            logger.warning("Need at least 10 values for training")
            return
        
        self.mean = np.mean(historical_values)
        self.std = np.std(historical_values)
        self.trained = True
    
    def detect(self, value: float, metric: str = "unknown", 
               timestamp: datetime = None) -> AnomalyScore:
        """Detect anomaly using Z-score."""
        if not self.trained or self.std == 0:
            return AnomalyScore(
                metric=metric,
                timestamp=timestamp or datetime.utcnow(),
                value=value,
                score=0,
                is_anomaly=False,
                reason="Detector not trained",
                confidence=0
            )
        
        z_score = abs((value - self.mean) / self.std)
        is_anomaly = z_score > self.z_threshold
        
        return AnomalyScore(
            metric=metric,
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            score=min(z_score / self.z_threshold, 1.0),
            is_anomaly=is_anomaly,
            reason=f"Z-score: {z_score:.2f} (threshold: {self.z_threshold})",
            confidence=0.8 if is_anomaly else 0.9
        )


class IsolationForestDetector(AnomalyDetector):
    """Detect anomalies using Isolation Forest algorithm."""
    
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination  # Expected % of anomalies
        self.values = deque(maxlen=1000)  # Keep last 1000 values
        self.threshold = None
        self.trained = False
    
    def train(self, historical_values: List[float]):
        """Build isolation forest model."""
        # Simplified: use percentile-based threshold
        sorted_vals = sorted(historical_values)
        percentile_low = int(len(sorted_vals) * (self.contamination / 2))
        percentile_high = int(len(sorted_vals) * (1 - self.contamination / 2))
        
        self.lower_bound = sorted_vals[percentile_low]
        self.upper_bound = sorted_vals[percentile_high]
        self.trained = True
    
    def detect(self, value: float, metric: str = "unknown",
               timestamp: datetime = None) -> AnomalyScore:
        """Detect anomaly using isolation score."""
        self.values.append(value)
        
        if not self.trained:
            return AnomalyScore(
                metric=metric,
                timestamp=timestamp or datetime.utcnow(),
                value=value,
                score=0,
                is_anomaly=False,
                reason="Detector not trained",
                confidence=0
            )
        
        # Calculate isolation score
        is_anomaly = value < self.lower_bound or value > self.upper_bound
        
        if is_anomaly:
            distance = min(
                abs(value - self.lower_bound),
                abs(value - self.upper_bound)
            )
            max_distance = (self.upper_bound - self.lower_bound) / 2
            score = 1.0 - (distance / max_distance) if max_distance > 0 else 1.0
        else:
            score = 0
        
        return AnomalyScore(
            metric=metric,
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            score=score,
            is_anomaly=is_anomaly,
            reason=f"Value {'outside' if is_anomaly else 'within'} bounds "
                   f"[{self.lower_bound:.2f}, {self.upper_bound:.2f}]",
            confidence=0.85
        )


class TimeSeriesAnomalyDetector(AnomalyDetector):
    """Detect anomalies in time-series using trend analysis."""
    
    def __init__(self, window_size: int = 10, threshold: float = 0.2):
        self.window_size = window_size
        self.threshold = threshold  # Rate of change threshold
        self.values = deque(maxlen=window_size)
        self.trend = 0
    
    def train(self, historical_values: List[float]):
        """Calculate baseline trend."""
        if len(historical_values) >= self.window_size:
            recent = historical_values[-self.window_size:]
            self.trend = (recent[-1] - recent[0]) / (len(recent) - 1)
    
    def detect(self, value: float, metric: str = "unknown",
               timestamp: datetime = None) -> AnomalyScore:
        """Detect anomaly based on trend deviation."""
        self.values.append(value)
        
        if len(self.values) < self.window_size:
            return AnomalyScore(
                metric=metric,
                timestamp=timestamp or datetime.utcnow(),
                value=value,
                score=0,
                is_anomaly=False,
                reason="Not enough history",
                confidence=0
            )
        
        # Calculate expected value based on trend
        expected = self.values[0] + self.trend * len(self.values)
        
        # Check deviation
        deviation = abs(value - expected) / (expected or 1)
        is_anomaly = deviation > self.threshold
        
        return AnomalyScore(
            metric=metric,
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            score=min(deviation / self.threshold, 1.0),
            is_anomaly=is_anomaly,
            reason=f"Trend deviation: {deviation:.2%} (expected ~{expected:.2f})",
            confidence=0.75
        )


class AlertCorrelationEngine:
    """Correlate and aggregate related alerts."""
    
    def __init__(self, correlation_window: int = 300):
        self.correlation_window = correlation_window  # seconds
        self.recent_alerts = deque()
        self.alert_groups = {}
    
    def add_alert(self, alert: Alert) -> Optional[str]:
        """Add alert and return group ID if correlated."""
        self.recent_alerts.append(alert)
        
        # Remove old alerts (outside correlation window)
        cutoff = datetime.utcnow() - timedelta(seconds=self.correlation_window)
        while self.recent_alerts and self.recent_alerts[0].timestamp < cutoff:
            self.recent_alerts.popleft()
        
        # Find correlating alerts
        group_id = self.find_correlation(alert)
        
        if group_id:
            self.alert_groups[group_id].append(alert)
        else:
            group_id = self.create_group(alert)
        
        return group_id
    
    def find_correlation(self, alert: Alert) -> Optional[str]:
        """Find if alert correlates with existing group."""
        for group_id, alerts in self.alert_groups.items():
            # Same source and related metrics
            if alerts and alerts[0].source == alert.source:
                if self.are_related(alert.metric_name, alerts[0].metric_name):
                    return group_id
            
            # Temporal correlation (within 5 minutes)
            if alerts:
                time_diff = (alert.timestamp - alerts[-1].timestamp).total_seconds()
                if time_diff < 300 and alert.severity.value == alerts[0].severity.value:
                    return group_id
        
        return None
    
    def are_related(self, metric1: str, metric2: str) -> bool:
        """Check if two metrics are related."""
        related_groups = {
            'error_rate': ['error_rate', 'exception_count', 'failure_rate'],
            'response_time': ['response_time', 'latency', 'processing_time'],
            'cpu': ['cpu', 'processor', 'cpu_usage'],
            'memory': ['memory', 'ram', 'heap_size'],
            'cache': ['cache', 'hit_rate', 'miss_rate'],
        }
        
        for group, metrics in related_groups.items():
            if metric1 in metrics and metric2 in metrics:
                return True
        
        return False
    
    def create_group(self, alert: Alert) -> str:
        """Create new alert group."""
        group_id = f"alert_group_{int(datetime.utcnow().timestamp())}"
        self.alert_groups[group_id] = [alert]
        return group_id
    
    def get_alert_groups(self) -> Dict[str, List[Alert]]:
        """Get all alert groups."""
        return self.alert_groups
    
    def infer_root_cause(self, group_id: str) -> str:
        """Infer root cause from alert group."""
        alerts = self.alert_groups.get(group_id, [])
        
        if not alerts:
            return "Unknown"
        
        # Look for patterns
        metric_names = [a.metric_name for a in alerts]
        
        # Database issue pattern
        if any('db' in m or 'query' in m for m in metric_names):
            if any('connection' in m for m in metric_names):
                return "Database connection pool exhausted"
            if any('slow' in m for m in metric_names):
                return "Database queries are slow"
        
        # Cache issue pattern
        if any('cache' in m for m in metric_names):
            if any('hit_rate' in m for m in metric_names):
                return "Cache effectiveness low"
            return "Cache service unavailable"
        
        # Resource exhaustion pattern
        if any('cpu' in m for m in metric_names) and any('memory' in m for m in metric_names):
            if any('error' in m for m in metric_names):
                return "Resource exhaustion causing errors"
            return "High resource usage"
        
        return "Unknown root cause"


class SelfHealingEngine:
    """Execute automatic recovery actions."""
    
    def __init__(self):
        self.recovery_actions: Dict[str, Callable] = {}
        self.recovery_history = deque(maxlen=100)
    
    def register_action(self, pattern: str, handler: Callable):
        """Register recovery handler for alert pattern."""
        self.recovery_actions[pattern] = handler
    
    def handle_alert(self, alert: Alert) -> RecoveryStatus:
        """Attempt automatic recovery for alert."""
        logger.info(f"Processing alert: {alert.type} - {alert.message}")
        
        # Find matching handler
        for pattern, handler in self.recovery_actions.items():
            if pattern in alert.type.lower():
                try:
                    status = handler(alert)
                    self.recovery_history.append({
                        'alert': alert.type,
                        'status': status,
                        'timestamp': datetime.utcnow()
                    })
                    return status
                except Exception as e:
                    logger.error(f"Recovery action failed: {e}")
                    return RecoveryStatus.FAILURE
        
        # No handler found
        return RecoveryStatus.IN_PROGRESS
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        total = len(self.recovery_history)
        successful = sum(1 for r in self.recovery_history 
                        if r['status'] == RecoveryStatus.SUCCESS)
        
        return {
            'total_recoveries': total,
            'successful': successful,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'recent_actions': list(self.recovery_history)[-10:],
        }


class PredictiveCapacity:
    """Predict future capacity needs."""
    
    def __init__(self):
        self.historical_metrics = deque(maxlen=10080)  # 1 week at 1-min interval
    
    def add_metric(self, metric_name: str, value: float, timestamp: datetime):
        """Add historical metric."""
        self.historical_metrics.append({
            'name': metric_name,
            'value': value,
            'timestamp': timestamp
        })
    
    def forecast_capacity(self, metric: str, horizon_days: int = 30) -> Dict[str, Any]:
        """Forecast capacity need."""
        values = [m['value'] for m in self.historical_metrics 
                 if m['name'] == metric]
        
        if not values or len(values) < 7:
            return {'status': 'insufficient_data'}
        
        # Simple linear regression for forecast
        x = np.arange(len(values))
        y = np.array(values)
        coeffs = np.polyfit(x, y, 1)
        
        # Forecast to future days
        future_x = len(values) + (horizon_days * 24 * 60)
        forecast_value = coeffs[0] * future_x + coeffs[1]
        
        current = values[-1]
        growth_rate = (forecast_value - current) / current if current > 0 else 0
        
        return {
            'current_value': current,
            'forecast_value': forecast_value,
            'growth_rate': growth_rate,
            'forecast_date': datetime.utcnow() + timedelta(days=horizon_days),
            'recommendation': self.generate_recommendation(metric, forecast_value)
        }
    
    def generate_recommendation(self, metric: str, forecast: float) -> str:
        """Generate capacity recommendation."""
        if metric == 'cpu_percent' and forecast > 85:
            return "Scale up compute by 20-30%"
        elif metric == 'memory_percent' and forecast > 85:
            return "Increase memory allocation by 25-30%"
        elif metric == 'storage_gb' and forecast > 1000:
            return "Increase storage capacity"
        else:
            return "Current capacity sufficient"


class ObservabilityDashboard:
    """Central observability dashboard."""
    
    def __init__(self):
        self.anomaly_detectors: Dict[str, AnomalyDetector] = {}
        self.correlation_engine = AlertCorrelationEngine()
        self.self_healing_engine = SelfHealingEngine()
        self.capacity_predictor = PredictiveCapacity()
    
    def register_metric(self, metric_name: str, detector: AnomalyDetector):
        """Register anomaly detector for metric."""
        self.anomaly_detectors[metric_name] = detector
    
    def process_metric(self, metric_name: str, value: float) -> List[Alert]:
        """Process metric and return any alerts."""
        alerts = []
        
        if metric_name not in self.anomaly_detectors:
            return alerts
        
        detector = self.anomaly_detectors[metric_name]
        anomaly = detector.detect(value, metric_name)
        
        if anomaly.is_anomaly:
            alert = Alert(
                type=f"anomaly_{metric_name}",
                severity=AlertSeverity.WARNING,
                message=f"Anomaly detected in {metric_name}: {anomaly.reason}",
                metric_name=metric_name,
                current_value=value,
                threshold=0,  # Anomaly score threshold
                timestamp=datetime.utcnow(),
                source="anomaly_detector"
            )
            alerts.append(alert)
            
            # Correlate alert
            self.correlation_engine.add_alert(alert)
            
            # Attempt recovery
            self.self_healing_engine.handle_alert(alert)
        
        return alerts
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'recovery_stats': self.self_healing_engine.get_recovery_stats(),
            'alert_groups': self.correlation_engine.get_alert_groups(),
            'capacity_forecast': {
                'cpu': self.capacity_predictor.forecast_capacity('cpu_percent'),
                'memory': self.capacity_predictor.forecast_capacity('memory_percent'),
            }
        }


# Global observability instance
observability = ObservabilityDashboard()
