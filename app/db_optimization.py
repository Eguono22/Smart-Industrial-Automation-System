"""
Database Optimization Module
Implements connection pooling, query optimization, and caching strategies
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Connection pool for database connections with max size limit"""
    
    def __init__(self, db_path: str, max_connections: int = 10, timeout: int = 5):
        """
        Initialize connection pool
        
        Args:
            db_path: Path to SQLite database
            max_connections: Maximum number of concurrent connections
            timeout: Connection timeout in seconds
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self._connections: list = []
        self._available: list = []
        self._lock = __import__('threading').Lock()
        self._initialized = False
        
    def initialize(self):
        """Initialize the connection pool"""
        with self._lock:
            if not self._initialized:
                for _ in range(self.max_connections):
                    conn = self._create_connection()
                    self._connections.append(conn)
                    self._available.append(conn)
                self._initialized = True
                logger.info(f"Connection pool initialized with {self.max_connections} connections")
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        return conn
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        with self._lock:
            if not self._available:
                raise RuntimeError("No connections available")
            conn = self._available.pop()
        
        try:
            yield conn
        finally:
            with self._lock:
                self._available.append(conn)
    
    def close_all(self):
        """Close all connections in the pool"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
            self._connections.clear()
            self._available.clear()
            self._initialized = False


class QueryOptimizer:
    """Optimizes database queries and tracks performance"""
    
    def __init__(self):
        self.slow_queries: Dict[str, Dict[str, Any]] = {}
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self._slow_threshold = 0.1  # 100ms
    
    def track_query(self, query: str, duration: float, success: bool = True):
        """Track query execution time"""
        if query not in self.query_stats:
            self.query_stats[query] = {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'failures': 0
            }
        
        stats = self.query_stats[query]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['avg_time'] = stats['total_time'] / stats['count']
        stats['max_time'] = max(stats['max_time'], duration)
        stats['min_time'] = min(stats['min_time'], duration)
        
        if not success:
            stats['failures'] += 1
        
        if duration > self._slow_threshold:
            self.slow_queries[query] = {
                'duration': duration,
                'timestamp': datetime.now(),
                'status': 'slow' if success else 'failed'
            }
            logger.warning(f"Slow query detected ({duration:.3f}s): {query[:100]}")
    
    def get_slow_queries(self, limit: int = 10) -> list:
        """Get list of slowest queries"""
        sorted_queries = sorted(
            self.query_stats.items(),
            key=lambda x: x[1]['avg_time'],
            reverse=True
        )
        return sorted_queries[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get query statistics"""
        if not self.query_stats:
            return {}
        
        total_queries = sum(s['count'] for s in self.query_stats.values())
        total_time = sum(s['total_time'] for s in self.query_stats.values())
        avg_time = total_time / total_queries if total_queries > 0 else 0
        
        return {
            'total_queries': total_queries,
            'total_time': total_time,
            'avg_time': avg_time,
            'slow_queries': len(self.slow_queries),
            'slow_queries_list': list(self.slow_queries.items())[:5]
        }


# Global optimizer instance
_query_optimizer = QueryOptimizer()


def optimize_query(func: Callable) -> Callable:
    """Decorator to track query performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            query_name = func.__name__
            _query_optimizer.track_query(query_name, duration, success=True)
            return result
        except Exception as e:
            duration = time.time() - start
            query_name = func.__name__
            _query_optimizer.track_query(query_name, duration, success=False)
            logger.error(f"Query failed: {func.__name__} - {str(e)}")
            raise
    return wrapper


class DatabaseIndexes:
    """Create and manage database indexes for optimization"""
    
    INDEXES = {
        'machines': [
            "CREATE INDEX IF NOT EXISTS idx_machines_status ON machines(status)",
            "CREATE INDEX IF NOT EXISTS idx_machines_facility ON machines(facility_id)",
            "CREATE INDEX IF NOT EXISTS idx_machines_created ON machines(created_at)",
        ],
        'sensor_data': [
            "CREATE INDEX IF NOT EXISTS idx_sensor_machine ON sensor_data(machine_id)",
            "CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_sensor_type ON sensor_data(sensor_type)",
            "CREATE INDEX IF NOT EXISTS idx_sensor_composite ON sensor_data(machine_id, timestamp DESC)",
        ],
        'alerts': [
            "CREATE INDEX IF NOT EXISTS idx_alerts_machine ON alerts(machine_id)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)",
        ],
        'workflows': [
            "CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows(created_at)",
        ],
    }
    
    @staticmethod
    def create_all(pool: DatabaseConnectionPool):
        """Create all recommended indexes"""
        with pool.get_connection() as conn:
            for table, indexes in DatabaseIndexes.INDEXES.items():
                for index_sql in indexes:
                    try:
                        conn.execute(index_sql)
                        conn.commit()
                        logger.info(f"Created index: {index_sql[:60]}...")
                    except Exception as e:
                        logger.error(f"Failed to create index: {e}")


class QueryBatcher:
    """Batch multiple queries for better performance"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.batch: list = []
    
    def add(self, query: str, params: tuple = ()):
        """Add query to batch"""
        self.batch.append((query, params))
        if len(self.batch) >= self.batch_size:
            return self.execute()
        return None
    
    def execute(self, pool: DatabaseConnectionPool = None) -> list:
        """Execute all batched queries"""
        if not self.batch:
            return []
        
        results = []
        with pool.get_connection() as conn:
            try:
                for query, params in self.batch:
                    cursor = conn.execute(query, params)
                    results.append(cursor.fetchall())
                conn.commit()
            except Exception as e:
                logger.error(f"Batch execution failed: {e}")
                conn.rollback()
                raise
        
        self.batch.clear()
        return results
    
    def flush(self, pool: DatabaseConnectionPool):
        """Execute any remaining batched queries"""
        return self.execute(pool)


def get_query_stats() -> Dict[str, Any]:
    """Get current query statistics"""
    return _query_optimizer.get_stats()


def get_slow_queries(limit: int = 10) -> list:
    """Get list of slowest queries"""
    return _query_optimizer.get_slow_queries(limit)


class DatabaseAnalyzer:
    """Analyze database performance and provide recommendations"""
    
    @staticmethod
    def analyze_table_sizes(pool: DatabaseConnectionPool) -> Dict[str, int]:
        """Get sizes of all tables"""
        sizes = {}
        with pool.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                sizes[table] = cursor.fetchone()[0]
        
        return sizes
    
    @staticmethod
    def analyze_query_patterns(limit: int = 20) -> list:
        """Analyze query execution patterns"""
        stats = _query_optimizer.query_stats
        patterns = []
        
        for query, stat in stats.items():
            patterns.append({
                'query': query[:100],
                'executions': stat['count'],
                'avg_time_ms': stat['avg_time'] * 1000,
                'max_time_ms': stat['max_time'] * 1000,
                'total_time_ms': stat['total_time'] * 1000,
                'failure_rate': stat['failures'] / stat['count'] if stat['count'] > 0 else 0
            })
        
        return sorted(patterns, key=lambda x: x['total_time_ms'], reverse=True)[:limit]


# Export initialization function
def init_database_optimization(db_path: str) -> DatabaseConnectionPool:
    """Initialize database optimization"""
    pool = DatabaseConnectionPool(db_path)
    pool.initialize()
    DatabaseIndexes.create_all(pool)
    logger.info("Database optimization initialized")
    return pool
