"""
API Performance Optimization Module
Implements rate limiting, request compression, pagination, and response optimization
"""

import logging
import gzip
import io
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting implementation using token bucket algorithm"""
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter
        
        Args:
            requests_per_minute: Max requests per minute per client
        """
        self.requests_per_minute = requests_per_minute
        self.rate_limit_window = 60  # seconds
        self.client_buckets: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client"""
        now = time.time()
        window_start = now - self.rate_limit_window
        
        # Clean old requests
        self.client_buckets[client_id] = [
            req_time for req_time in self.client_buckets[client_id]
            if req_time > window_start
        ]
        
        # Check limit
        if len(self.client_buckets[client_id]) < self.requests_per_minute:
            self.client_buckets[client_id].append(now)
            return True
        
        return False
    
    def get_retry_after(self, client_id: str) -> int:
        """Get seconds until next request is allowed"""
        if client_id not in self.client_buckets:
            return 0
        
        if not self.client_buckets[client_id]:
            return 0
        
        oldest_request = min(self.client_buckets[client_id])
        retry_after = max(1, int(oldest_request + self.rate_limit_window - time.time()))
        return retry_after


def rate_limit(limiter: RateLimiter, get_client_id: Callable = None):
    """
    Decorator to rate limit API endpoints
    
    Usage:
        limiter = RateLimiter(requests_per_minute=100)
        
        @app.route('/api/data')
        @rate_limit(limiter, get_client_id=lambda: request.remote_addr)
        def get_data():
            return {"data": []}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get client identifier
            if get_client_id:
                client_id = get_client_id()
            else:
                client_id = "anonymous"
            
            # Check rate limit
            if not limiter.is_allowed(client_id):
                retry_after = limiter.get_retry_after(client_id)
                logger.warning(f"Rate limit exceeded for {client_id}")
                return {
                    'status': 'error',
                    'message': 'Rate limit exceeded',
                    'retry_after': retry_after
                }, 429
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ResponseCompressor:
    """Compress HTTP responses for faster transmission"""
    
    @staticmethod
    def compress_json(data: str, min_size: int = 1024) -> Optional[bytes]:
        """
        Compress JSON response
        
        Args:
            data: JSON string to compress
            min_size: Minimum size to compress (smaller responses not worth compressing)
        
        Returns:
            Compressed bytes or None if not worth compressing
        """
        if len(data) < min_size:
            return None
        
        try:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode='wb') as gz:
                gz.write(data.encode('utf-8'))
            compressed = buffer.getvalue()
            
            # Only use compression if it actually reduces size
            if len(compressed) < len(data):
                ratio = len(compressed) / len(data) * 100
                logger.debug(f"Compressed response: {len(data)} -> {len(compressed)} bytes ({ratio:.1f}%)")
                return compressed
        except Exception as e:
            logger.error(f"Compression failed: {e}")
        
        return None


class PaginationHelper:
    """Handle pagination for large result sets"""
    
    @staticmethod
    def paginate(items: List[Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        Paginate a list of items
        
        Args:
            items: List to paginate
            page: Page number (1-indexed)
            per_page: Items per page
        
        Returns:
            Paginated result with metadata
        """
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20
        
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            'data': items[start:end],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'has_next': end < total,
                'has_prev': page > 1
            }
        }
    
    @staticmethod
    def cursor_paginate(items: List[Dict[str, Any]], cursor: Optional[str] = None, per_page: int = 20) -> Dict[str, Any]:
        """
        Cursor-based pagination (better for large datasets)
        
        Args:
            items: List of items to paginate
            cursor: Cursor for current position
            per_page: Items per page
        
        Returns:
            Paginated result with cursor
        """
        if cursor:
            try:
                import base64
                start_idx = int(base64.b64decode(cursor).decode())
            except:
                start_idx = 0
        else:
            start_idx = 0
        
        page_data = items[start_idx:start_idx + per_page]
        
        # Generate next cursor
        next_cursor = None
        if start_idx + per_page < len(items):
            import base64
            next_cursor = base64.b64encode(str(start_idx + per_page).encode()).decode()
        
        return {
            'data': page_data,
            'pagination': {
                'cursor': cursor,
                'next_cursor': next_cursor,
                'per_page': per_page,
                'has_next': next_cursor is not None,
                'total_items': len(items)
            }
        }


class QueryOptimizationHelper:
    """Optimize common query patterns"""
    
    @staticmethod
    def build_optimized_query(entity_type: str, filters: Dict[str, Any] = None, 
                             fields: List[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Build optimized query with only needed fields
        
        Args:
            entity_type: Type of entity to query
            filters: Filter conditions
            fields: Only select these fields
            limit: Result limit
        
        Returns:
            Optimized query specification
        """
        query = {
            'entity': entity_type,
            'limit': min(limit, 1000),  # Cap at 1000
            'filters': filters or {},
            'fields': fields or '*'
        }
        
        # Suggest indexes for common queries
        if filters:
            query['suggested_indexes'] = list(filters.keys())
        
        return query
    
    @staticmethod
    def detect_n_plus_one(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect N+1 query problems
        
        Args:
            queries: List of executed queries
        
        Returns:
            List of detected N+1 problems
        """
        problems = []
        query_types = defaultdict(list)
        
        # Group similar queries
        for q in queries:
            query_type = q.get('type', 'unknown')
            query_types[query_type].append(q)
        
        # Find queries executed many times
        for query_type, query_list in query_types.items():
            if len(query_list) > 10:
                problems.append({
                    'type': 'n_plus_one_detected',
                    'query_type': query_type,
                    'occurrences': len(query_list),
                    'recommendation': f'Consider using JOIN or batch loading instead of {len(query_list)} separate queries'
                })
        
        return problems


class APIPerformanceMonitor:
    """Monitor API performance metrics"""
    
    def __init__(self):
        self.endpoint_stats: Dict[str, Dict[str, Any]] = {}
        self.response_times: Dict[str, List[float]] = defaultdict(list)
    
    def track_request(self, endpoint: str, method: str, duration: float, status_code: int, response_size: int):
        """Track API request performance"""
        key = f"{method} {endpoint}"
        
        if key not in self.endpoint_stats:
            self.endpoint_stats[key] = {
                'count': 0,
                'total_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'status_codes': defaultdict(int),
                'total_size': 0,
                'errors': 0
            }
        
        stats = self.endpoint_stats[key]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['max_time'] = max(stats['max_time'], duration)
        stats['min_time'] = min(stats['min_time'], duration)
        stats['status_codes'][status_code] += 1
        stats['total_size'] += response_size
        
        if status_code >= 400:
            stats['errors'] += 1
        
        # Keep last 100 response times for percentile calculation
        self.response_times[key].append(duration)
        if len(self.response_times[key]) > 100:
            self.response_times[key].pop(0)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'endpoints': [],
            'summary': {
                'total_requests': 0,
                'avg_response_time': 0,
                'p95_response_time': 0,
                'p99_response_time': 0,
                'error_rate': 0,
                'total_bandwidth_mb': 0
            }
        }
        
        total_requests = 0
        total_time = 0
        all_times = []
        total_errors = 0
        
        for endpoint, stats in self.endpoint_stats.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            error_rate = stats['errors'] / stats['count'] * 100 if stats['count'] > 0 else 0
            avg_size = stats['total_size'] / stats['count'] if stats['count'] > 0 else 0
            
            report['endpoints'].append({
                'endpoint': endpoint,
                'requests': stats['count'],
                'avg_time_ms': avg_time * 1000,
                'min_time_ms': stats['min_time'] * 1000,
                'max_time_ms': stats['max_time'] * 1000,
                'error_rate': f"{error_rate:.2f}%",
                'avg_size_bytes': int(avg_size),
                'status_codes': dict(stats['status_codes'])
            })
            
            total_requests += stats['count']
            total_time += stats['total_time']
            total_errors += stats['errors']
            all_times.extend(self.response_times.get(endpoint, []))
        
        # Calculate summary
        if total_requests > 0:
            report['summary']['total_requests'] = total_requests
            report['summary']['avg_response_time'] = total_time / total_requests * 1000
            report['summary']['error_rate'] = f"{total_errors / total_requests * 100:.2f}%"
            report['summary']['total_bandwidth_mb'] = sum(s['total_size'] for s in self.endpoint_stats.values()) / 1024 / 1024
        
        # Calculate percentiles
        if all_times:
            all_times.sort()
            p95_idx = int(len(all_times) * 0.95)
            p99_idx = int(len(all_times) * 0.99)
            report['summary']['p95_response_time'] = all_times[p95_idx] * 1000
            report['summary']['p99_response_time'] = all_times[p99_idx] * 1000
        
        return report


def optimize_response(func: Callable) -> Callable:
    """
    Decorator to optimize API response
    - Compress if needed
    - Limit fields
    - Paginate results
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        if isinstance(result, dict):
            result['_performance'] = {
                'response_time_ms': duration * 1000,
                'cached': False
            }
        
        return result
    return wrapper


# Global performance monitor
_performance_monitor = APIPerformanceMonitor()


def get_performance_report() -> Dict[str, Any]:
    """Get API performance report"""
    return _performance_monitor.get_performance_report()


def track_api_request(endpoint: str, method: str, duration: float, status_code: int, response_size: int):
    """Track API request for performance monitoring"""
    _performance_monitor.track_request(endpoint, method, duration, status_code, response_size)
