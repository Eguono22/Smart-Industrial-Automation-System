"""
Machine Learning Models Module
Implements anomaly detection and predictive maintenance models
"""

import logging
import json
from typing import Any, Callable, Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import statistics
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalyDetectionAlgorithm(Enum):
    """Anomaly detection algorithms"""
    STATISTICAL = "statistical"  # Z-score based
    ISOLATION_FOREST = "isolation_forest"  # Isolation Forest
    CONTEXTUAL = "contextual"  # Context-aware detection


class StatisticalAnomalyDetector:
    """Statistical anomaly detection using Z-score and IQR"""
    
    def __init__(self, z_score_threshold: float = 3.0, iqr_multiplier: float = 1.5):
        """
        Initialize detector
        
        Args:
            z_score_threshold: Z-score threshold for anomaly (default 3.0 = 99.7%)
            iqr_multiplier: IQR multiplier for outlier detection
        """
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
    
    def learn_baseline(self, data: List[float], metric_name: str):
        """Learn baseline statistics from normal data"""
        if len(data) < 5:
            logger.warning(f"Insufficient data for baseline: {metric_name}")
            return
        
        mean = statistics.mean(data)
        stdev = statistics.stdev(data)
        sorted_data = sorted(data)
        
        q1_idx = len(sorted_data) // 4
        q3_idx = (3 * len(sorted_data)) // 4
        q1 = sorted_data[q1_idx]
        q3 = sorted_data[q3_idx]
        
        self.baseline_stats[metric_name] = {
            'mean': mean,
            'stdev': stdev,
            'q1': q1,
            'q3': q3,
            'iqr': q3 - q1,
            'min': min(data),
            'max': max(data),
            'count': len(data)
        }
        
        logger.info(f"Learned baseline for {metric_name}: mean={mean:.2f}, stdev={stdev:.2f}")
    
    def detect_anomaly(self, value: float, metric_name: str) -> Tuple[bool, float]:
        """
        Detect anomaly using Z-score and IQR
        
        Args:
            value: Value to check
            metric_name: Metric identifier
        
        Returns:
            (is_anomaly, anomaly_score)
        """
        if metric_name not in self.baseline_stats:
            logger.warning(f"No baseline for {metric_name}")
            return False, 0.0
        
        stats = self.baseline_stats[metric_name]
        
        # Z-score method
        if stats['stdev'] > 0:
            z_score = abs((value - stats['mean']) / stats['stdev'])
            if z_score > self.z_score_threshold:
                return True, z_score
        
        # IQR method
        lower_bound = stats['q1'] - self.iqr_multiplier * stats['iqr']
        upper_bound = stats['q3'] + self.iqr_multiplier * stats['iqr']
        
        if value < lower_bound or value > upper_bound:
            distance = max(abs(value - lower_bound), abs(value - upper_bound))
            score = distance / stats['iqr'] if stats['iqr'] > 0 else 0
            return True, score
        
        return False, 0.0


class ContextualAnomalyDetector:
    """Detect anomalies based on context and patterns"""
    
    def __init__(self, window_size: int = 10):
        """
        Initialize contextual detector
        
        Args:
            window_size: Number of previous values to consider
        """
        self.window_size = window_size
        self.data_windows: Dict[str, List[float]] = {}
    
    def add_value(self, metric_name: str, value: float):
        """Add value to data window"""
        if metric_name not in self.data_windows:
            self.data_windows[metric_name] = []
        
        self.data_windows[metric_name].append(value)
        
        # Keep only window_size values
        if len(self.data_windows[metric_name]) > self.window_size:
            self.data_windows[metric_name].pop(0)
    
    def detect_anomaly(self, metric_name: str, value: float) -> Tuple[bool, float, str]:
        """
        Detect contextual anomalies
        
        Args:
            metric_name: Metric identifier
            value: Value to check
        
        Returns:
            (is_anomaly, anomaly_score, reason)
        """
        if metric_name not in self.data_windows:
            return False, 0.0, "No history"
        
        window = self.data_windows[metric_name]
        if len(window) < 2:
            return False, 0.0, "Insufficient history"
        
        # Detect sudden spikes
        prev_value = window[-1]
        if prev_value > 0:
            change_ratio = abs(value - prev_value) / prev_value
            if change_ratio > 0.5:  # 50% change
                return True, change_ratio, f"Sudden change ({change_ratio:.1%})"
        
        # Detect trend breaks
        if len(window) >= 3:
            recent_trend = window[-1] - window[-2]
            older_trend = window[-2] - window[-3]
            
            if recent_trend != 0 and older_trend != 0:
                if (recent_trend > 0 and older_trend < 0) or (recent_trend < 0 and older_trend > 0):
                    return True, 0.7, "Trend reversal detected"
        
        # Detect stagnation
        if len(window) >= self.window_size:
            variance = statistics.variance(window)
            if variance < 0.01:
                current_change = abs(value - window[-1])
                if current_change > statistics.stdev(window) * 2:
                    return True, 0.6, "Stagnation break"
        
        return False, 0.0, "Normal"


class PredictiveMaintenance:
    """Predictive maintenance using time-series forecasting"""
    
    def __init__(self, lookback_window: int = 30):
        """
        Initialize predictive maintenance
        
        Args:
            lookback_window: Days of historical data to consider
        """
        self.lookback_window = lookback_window
        self.component_history: Dict[str, List[Dict[str, Any]]] = {}
        self.failure_predictions: Dict[str, Dict[str, Any]] = {}
    
    def add_measurement(self, component_id: str, timestamp: datetime, value: float, severity: str = 'normal'):
        """Add component measurement"""
        if component_id not in self.component_history:
            self.component_history[component_id] = []
        
        self.component_history[component_id].append({
            'timestamp': timestamp,
            'value': value,
            'severity': severity
        })
        
        # Keep only lookback_window days
        cutoff_date = datetime.now() - timedelta(days=self.lookback_window)
        self.component_history[component_id] = [
            m for m in self.component_history[component_id]
            if m['timestamp'] > cutoff_date
        ]
    
    def predict_failure(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Predict potential failure for component
        
        Args:
            component_id: Component identifier
        
        Returns:
            Failure prediction or None
        """
        if component_id not in self.component_history:
            return None
        
        history = self.component_history[component_id]
        if len(history) < 3:
            return None
        
        # Extract values and calculate trend
        values = [m['value'] for m in history]
        times = [m['timestamp'] for m in history]
        
        # Simple linear regression for trend
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum + 1e-6)
        intercept = (y_sum - slope * x_sum) / n
        
        # Predict when threshold might be exceeded
        threshold = 80.0  # Component failure threshold
        if slope > 0:
            # Positive trend - estimate days to failure
            current_value = values[-1]
            if current_value < threshold:
                days_to_failure = (threshold - current_value) / (slope + 1e-6)
                
                return {
                    'component_id': component_id,
                    'current_value': current_value,
                    'trend': 'increasing',
                    'slope': slope,
                    'predicted_failure_days': max(1, int(days_to_failure)),
                    'confidence': min(0.95, 0.5 + n / 100),  # Higher with more data
                    'recommendation': 'Schedule maintenance' if days_to_failure < 7 else 'Monitor'
                }
        
        return None
    
    def get_risk_assessment(self) -> Dict[str, Dict[str, Any]]:
        """Get risk assessment for all components"""
        assessments = {}
        
        for component_id in self.component_history.keys():
            prediction = self.predict_failure(component_id)
            if prediction:
                assessments[component_id] = prediction
        
        return assessments


class ModelVersioning:
    """Version and manage ML models"""
    
    def __init__(self):
        self.models: Dict[str, List[Dict[str, Any]]] = {}
        self.active_models: Dict[str, str] = {}  # model_name -> version
    
    def register_model(self, model_name: str, model_data: Dict[str, Any], 
                      version: Optional[str] = None, metrics: Dict[str, float] = None):
        """Register a model version"""
        if not version:
            # Auto-generate version
            if model_name in self.models:
                version = f"v{len(self.models[model_name]) + 1}"
            else:
                version = "v1"
        
        if model_name not in self.models:
            self.models[model_name] = []
        
        self.models[model_name].append({
            'version': version,
            'created_at': datetime.now(),
            'data': model_data,
            'metrics': metrics or {},
            'status': 'active' if not self.active_models.get(model_name) else 'inactive'
        })
        
        # Set as active if first version
        if model_name not in self.active_models:
            self.active_models[model_name] = version
        
        logger.info(f"Registered model: {model_name}/{version}")
    
    def get_active_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get active model version"""
        if model_name not in self.active_models:
            return None
        
        version = self.active_models[model_name]
        for model in self.models.get(model_name, []):
            if model['version'] == version:
                return model
        
        return None
    
    def switch_model_version(self, model_name: str, version: str) -> bool:
        """Switch to different model version"""
        if model_name not in self.models:
            return False
        
        # Check version exists
        if not any(m['version'] == version for m in self.models[model_name]):
            return False
        
        self.active_models[model_name] = version
        logger.info(f"Switched to model version: {model_name}/{version}")
        return True
    
    def get_model_history(self, model_name: str) -> List[Dict[str, Any]]:
        """Get all versions of a model"""
        return self.models.get(model_name, [])


class FeatureImportance:
    """Calculate feature importance for ML models"""
    
    @staticmethod
    def calculate_correlation(features: List[List[float]], target: List[float]) -> Dict[str, float]:
        """
        Calculate feature importance using correlation
        
        Args:
            features: List of feature vectors
            target: Target values
        
        Returns:
            Feature importance scores
        """
        importance = {}
        
        if not features or not target or len(features[0]) == 0:
            return importance
        
        n_features = len(features[0])
        n_samples = len(features)
        
        # Calculate correlations
        for feat_idx in range(n_features):
            feature_values = [features[i][feat_idx] for i in range(n_samples)]
            
            # Simple correlation coefficient
            if len(feature_values) < 2:
                continue
            
            mean_feature = statistics.mean(feature_values)
            mean_target = statistics.mean(target)
            
            numerator = sum(
                (feature_values[i] - mean_feature) * (target[i] - mean_target)
                for i in range(n_samples)
            )
            
            denom_feature = statistics.stdev(feature_values) if len(feature_values) > 1 else 1
            denom_target = statistics.stdev(target) if len(target) > 1 else 1
            
            correlation = numerator / (n_samples * denom_feature * denom_target + 1e-6)
            importance[f"feature_{feat_idx}"] = abs(correlation)
        
        return importance


# Export initialization function
def init_ml_models() -> Dict[str, Any]:
    """Initialize ML models for the system"""
    return {
        'anomaly_detector': StatisticalAnomalyDetector(),
        'contextual_detector': ContextualAnomalyDetector(),
        'predictive_maintenance': PredictiveMaintenance(),
        'model_versioning': ModelVersioning(),
        'feature_importance': FeatureImportance()
    }
