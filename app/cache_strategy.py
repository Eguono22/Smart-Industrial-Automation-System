"""
Cache Strategy Module
Implements Redis caching, cache invalidation, and cache warming strategies
"""

import logging
import json
import hashlib
from functools import wraps
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class CacheManager:
    """Centralized cache management with Redis"""
    
    def __init__(self, redis_client=None, default_ttl: int = 3600):
        """
        Initialize cache manager
        
        Args:
            redis_client: Redis client instance
            default_ttl: Default time-to-live in seconds (1 hour)
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        self.cache_registry: Dict[str, Dict[str, Any]] = {}
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None):
        """Set a value in cache"""
        if not self.redis:
            logger.warning("Redis not available, cache operation skipped")
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            
            if self.redis.setex(key, ttl, serialized):
                self.cache_stats['sets'] += 1
                
                # Register cache entry
                self.cache_registry[key] = {
                    'created_at': datetime.now(),
                    'ttl': ttl,
                    'tags': tags or [],
                    'size': len(serialized)
                }
                
                # Register by tags for batch invalidation
                if tags:
                    for tag in tags:
                        tag_key = f"cache_tag:{tag}"
                        self.redis.sadd(tag_key, key)
                        self.redis.expire(tag_key, ttl * 2)
                
                logger.debug(f"Cache SET: {key} (TTL: {ttl}s, Tags: {tags})")
                return True
        except Exception as e:
            logger.error(f"Cache SET failed for {key}: {e}")
        
        return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if not self.redis:
            logger.warning("Redis not available, cache operation skipped")
            return None
        
        try:
            cached = self.redis.get(key)
            if cached:
                self.cache_stats['hits'] += 1
                logger.debug(f"Cache HIT: {key}")
                return json.loads(cached)
            else:
                self.cache_stats['misses'] += 1
                logger.debug(f"Cache MISS: {key}")
        except Exception as e:
            logger.error(f"Cache GET failed for {key}: {e}")
        
        return None
    
    def delete(self, key: str):
        """Delete a key from cache"""
        if not self.redis:
            return False
        
        try:
            if self.redis.delete(key):
                self.cache_stats['deletes'] += 1
                if key in self.cache_registry:
                    del self.cache_registry[key]
                logger.debug(f"Cache DELETE: {key}")
                return True
        except Exception as e:
            logger.error(f"Cache DELETE failed for {key}: {e}")
        
        return False
    
    def invalidate_by_tag(self, tag: str):
        """Invalidate all cache entries with a specific tag"""
        if not self.redis:
            return 0
        
        try:
            tag_key = f"cache_tag:{tag}"
            keys = self.redis.smembers(tag_key)
            count = 0
            
            for key in keys:
                if self.redis.delete(key):
                    count += 1
                    if key in self.cache_registry:
                        del self.cache_registry[key]
            
            self.redis.delete(tag_key)
            logger.info(f"Invalidated {count} cache entries with tag '{tag}'")
            return count
        except Exception as e:
            logger.error(f"Tag invalidation failed for '{tag}': {e}")
        
        return 0
    
    def clear_expired(self):
        """Remove expired entries from registry"""
        expired_keys = []
        now = datetime.now()
        
        for key, info in self.cache_registry.items():
            age = (now - info['created_at']).total_seconds()
            if age > info['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache_registry[key]
        
        logger.info(f"Cleared {len(expired_keys)} expired cache entries")
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'hit_rate': f"{hit_rate:.2f}%",
            'sets': self.cache_stats['sets'],
            'deletes': self.cache_stats['deletes'],
            'cached_entries': len(self.cache_registry),
            'total_size_kb': sum(info['size'] for info in self.cache_registry.values()) / 1024
        }
    
    def warm_cache(self, data: Dict[str, Any]):
        """Warm cache with initial data"""
        count = 0
        for key, value in data.items():
            if self.set(key, value):
                count += 1
        
        logger.info(f"Cache warmed with {count} entries")
        return count


def cache_result(ttl: Optional[int] = None, tags: List[str] = None):
    """
    Decorator to cache function results
    
    Usage:
        @cache_result(ttl=3600, tags=['machines'])
        def get_machines():
            return db.query(Machine).all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cache_manager = _get_cache_manager()
            if cache_manager:
                cached = cache_manager.get(cache_key)
                if cached is not None:
                    return cached
            
            # Execute function
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            # Store in cache
            if cache_manager:
                cache_manager.set(cache_key, result, ttl=ttl, tags=tags)
                logger.debug(f"Cached result of {func.__name__} ({duration:.3f}s) - Key: {cache_key}")
            
            return result
        return wrapper
    return decorator


def invalidate_cache(*patterns: str):
    """
    Decorator to invalidate cache after function execution
    
    Usage:
        @invalidate_cache('machines')
        def update_machine(id, data):
            return db.update(Machine, id, data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            cache_manager = _get_cache_manager()
            if cache_manager:
                for pattern in patterns:
                    cache_manager.invalidate_by_tag(pattern)
                    logger.debug(f"Invalidated cache pattern: {pattern}")
            
            return result
        return wrapper
    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a unique cache key from function name and arguments"""
    key_parts = [func_name]
    
    # Add args to key
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
    
    # Add kwargs to key
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(f"{k}={hashlib.md5(str(v).encode()).hexdigest()[:8]}")
    
    # Create key with max length of 250 chars
    key = ":".join(key_parts)
    if len(key) > 250:
        hash_suffix = hashlib.md5(key.encode()).hexdigest()[:8]
        key = key[:240] + ":" + hash_suffix
    
    return key


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def init_cache_manager(redis_client=None, default_ttl: int = 3600) -> CacheManager:
    """Initialize the global cache manager"""
    global _cache_manager
    _cache_manager = CacheManager(redis_client, default_ttl)
    logger.info("Cache manager initialized")
    return _cache_manager


def _get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance"""
    return _cache_manager


class CacheWarming:
    """Strategies for warming cache on startup"""
    
    @staticmethod
    def warm_frequently_accessed_data(cache_manager: CacheManager, get_funcs: Dict[str, Callable]):
        """
        Warm cache with frequently accessed data
        
        Args:
            cache_manager: Cache manager instance
            get_funcs: Dict of {cache_key: callable} to populate cache
        """
        count = 0
        for key, func in get_funcs.items():
            try:
                data = func()
                if cache_manager.set(key, data, ttl=3600, tags=['warmup']):
                    count += 1
                    logger.info(f"Warmed cache: {key}")
            except Exception as e:
                logger.error(f"Failed to warm cache for {key}: {e}")
        
        logger.info(f"Cache warming completed: {count}/{len(get_funcs)} entries")
        return count
    
    @staticmethod
    def schedule_periodic_refresh(cache_manager: CacheManager, refresh_funcs: Dict[str, Callable], interval: int = 300):
        """
        Schedule periodic cache refresh
        
        Args:
            cache_manager: Cache manager instance
            refresh_funcs: Dict of {cache_key: callable}
            interval: Refresh interval in seconds
        """
        import threading
        
        def refresh_worker():
            while True:
                time.sleep(interval)
                for key, func in refresh_funcs.items():
                    try:
                        data = func()
                        cache_manager.set(key, data, ttl=interval * 2, tags=['periodic'])
                    except Exception as e:
                        logger.error(f"Periodic refresh failed for {key}: {e}")
        
        thread = threading.Thread(target=refresh_worker, daemon=True)
        thread.start()
        logger.info(f"Periodic cache refresh scheduled (interval: {interval}s)")


class CacheInvalidationStrategy:
    """Define cache invalidation strategies"""
    
    # Tag-based invalidation
    MACHINE_UPDATES = 'machines'
    ASSET_UPDATES = 'assets'
    ALERT_UPDATES = 'alerts'
    WORKFLOW_UPDATES = 'workflows'
    ANALYTICS_UPDATES = 'analytics'
    
    # Composite tags for related data
    PERFORMANCE_DATA = 'performance'
    HEALTH_DATA = 'health'
    PREDICTION_DATA = 'predictions'


# Export functions for easy access
def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache"""
    if _cache_manager:
        return _cache_manager.get(key)
    return None


def cache_set(key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
    """Set a value in cache"""
    if _cache_manager:
        return _cache_manager.set(key, value, ttl, tags)
    return False


def cache_delete(key: str) -> bool:
    """Delete a key from cache"""
    if _cache_manager:
        return _cache_manager.delete(key)
    return False


def cache_invalidate_tag(tag: str) -> int:
    """Invalidate all entries with a tag"""
    if _cache_manager:
        return _cache_manager.invalidate_by_tag(tag)
    return 0


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    if _cache_manager:
        return _cache_manager.get_stats()
    return {}
