"""
Unified cache management system for Rose.

This module provides a comprehensive caching solution with multiple cache levels,
smart preheating, performance analysis, and cross-session persistence.
"""

import asyncio
import hashlib
import json
import pickle
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from roseApp.core.util import get_logger

_logger = get_logger("cache")


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata"""
    key: str
    value: Any
    timestamp: float
    access_count: int = 0
    last_access: float = 0
    size_bytes: int = 0
    ttl: Optional[float] = None
    tags: Optional[Set[str]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = set()
        if self.last_access == 0:
            self.last_access = self.timestamp
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def touch(self):
        """Update access information"""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'total_size': self.total_size,
            'entry_count': self.entry_count,
            'hit_rate': self.hit_rate
        }


class CacheBackend(ABC):
    """Abstract base class for cache backends"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """Retrieve a cache entry by key"""
        pass
    
    @abstractmethod
    def put(self, entry: CacheEntry) -> bool:
        """Store a cache entry"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a cache entry by key"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries"""
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """Get all cache keys"""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get total cache size in bytes"""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache backend with LRU eviction"""
    
    def __init__(self, max_size: int = 512 * 1024 * 1024):  # 512MB default
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
        self._current_size = 0
    
    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                # Move to end of access order (most recently used)
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return entry
            elif entry and entry.is_expired():
                # Remove expired entry
                self.delete(key)
            return None
    
    def put(self, entry: CacheEntry) -> bool:
        with self._lock:
            # Calculate entry size
            entry.size_bytes = len(pickle.dumps(entry.value))
            
            # Check if we need to evict entries
            while (self._current_size + entry.size_bytes > self.max_size and 
                   self._access_order):
                oldest_key = self._access_order.pop(0)
                self._evict_entry(oldest_key)
            
            # Store the entry
            if entry.key in self._cache:
                # Update existing entry
                old_entry = self._cache[entry.key]
                self._current_size -= old_entry.size_bytes
                self._access_order.remove(entry.key)
            
            self._cache[entry.key] = entry
            self._current_size += entry.size_bytes
            self._access_order.append(entry.key)
            return True
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._current_size -= entry.size_bytes
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._current_size = 0
    
    def keys(self) -> List[str]:
        with self._lock:
            return list(self._cache.keys())
    
    def size(self) -> int:
        return self._current_size
    
    def _evict_entry(self, key: str) -> None:
        """Evict a cache entry"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size -= entry.size_bytes


class FileCache(CacheBackend):
    """File-based cache backend with SQLite index"""
    
    def __init__(self, cache_dir: Path, max_size: int = 2 * 1024 * 1024 * 1024):  # 2GB default
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self.db_path = self.cache_dir / "cache.db"
        self._lock = threading.RLock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for cache index"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    ttl REAL,
                    tags TEXT
                )
            """)
            conn.commit()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT filename, timestamp, access_count, last_access, size_bytes, ttl, tags "
                    "FROM cache_entries WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                filename, timestamp, access_count, last_access, size_bytes, ttl, tags_json = row
                
                # Check if expired
                if ttl and time.time() - timestamp > ttl:
                    self.delete(key)
                    return None
                
                # Load value from file
                file_path = self.cache_dir / filename
                if not file_path.exists():
                    # File missing, remove from index
                    self.delete(key)
                    return None
                
                try:
                    with open(file_path, 'rb') as f:
                        value = pickle.load(f)
                    
                    tags = set(json.loads(tags_json)) if tags_json else set()
                    entry = CacheEntry(
                        key=key,
                        value=value,
                        timestamp=timestamp,
                        access_count=access_count,
                        last_access=last_access,
                        size_bytes=size_bytes,
                        ttl=ttl,
                        tags=tags
                    )
                    entry.touch()
                    
                    # Update access info
                    conn.execute(
                        "UPDATE cache_entries SET access_count = ?, last_access = ? WHERE key = ?",
                        (entry.access_count, entry.last_access, key)
                    )
                    conn.commit()
                    
                    return entry
                except Exception as e:
                    _logger.warning(f"Error loading cache entry {key}: {e}")
                    self.delete(key)
                    return None
    
    def put(self, entry: CacheEntry) -> bool:
        with self._lock:
            try:
                # Generate filename
                filename = f"{hashlib.md5(entry.key.encode()).hexdigest()}.pkl"
                file_path = self.cache_dir / filename
                
                # Save value to file
                with open(file_path, 'wb') as f:
                    pickle.dump(entry.value, f)
                
                entry.size_bytes = file_path.stat().st_size
                
                # Check size limits and evict if necessary
                self._ensure_size_limit()
                
                # Update database
                with sqlite3.connect(self.db_path) as conn:
                    tags_json = json.dumps(list(entry.tags)) if entry.tags else None
                    conn.execute(
                        """INSERT OR REPLACE INTO cache_entries 
                           (key, filename, timestamp, access_count, last_access, size_bytes, ttl, tags)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (entry.key, filename, entry.timestamp, entry.access_count,
                         entry.last_access, entry.size_bytes, entry.ttl, tags_json)
                    )
                    conn.commit()
                
                return True
            except Exception as e:
                _logger.error(f"Error storing cache entry {entry.key}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT filename FROM cache_entries WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    filename = row[0]
                    file_path = self.cache_dir / filename
                    
                    # Remove file
                    if file_path.exists():
                        file_path.unlink()
                    
                    # Remove from database
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return True
                
                return False
    
    def clear(self) -> None:
        with self._lock:
            # Remove all cache files
            for file_path in self.cache_dir.glob("*.pkl"):
                file_path.unlink()
            
            # Clear database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
    
    def keys(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key FROM cache_entries")
            return [row[0] for row in cursor.fetchall()]
    
    def size(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT SUM(size_bytes) FROM cache_entries")
            result = cursor.fetchone()[0]
            return result or 0
    
    def _ensure_size_limit(self):
        """Ensure cache doesn't exceed size limit by evicting old entries"""
        current_size = self.size()
        if current_size <= self.max_size:
            return
        
        # Get entries ordered by last access (oldest first)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key FROM cache_entries ORDER BY last_access ASC"
            )
            keys_to_evict = []
            
            for (key,) in cursor:
                keys_to_evict.append(key)
                if len(keys_to_evict) >= 100:  # Batch eviction
                    break
            
            # Evict oldest entries
            for key in keys_to_evict:
                self.delete(key)
                current_size = self.size()
                if current_size <= self.max_size * 0.8:  # Leave some headroom
                    break


class UnifiedCache:
    """Unified multi-level cache system with smart management"""
    
    def __init__(self, 
                 memory_size: int = 512 * 1024 * 1024,  # 512MB
                 file_size: int = 2 * 1024 * 1024 * 1024,  # 2GB
                 cache_dir: Optional[Path] = None):
        
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "rose_cache"
        
        self.memory_cache = MemoryCache(memory_size)
        self.file_cache = FileCache(cache_dir, file_size)
        
        self.stats = CacheStats()
        self._access_patterns: Dict[str, List[float]] = {}
        self._preheating_enabled = True
        self._lock = threading.RLock()
        
        # Performance analyzer
        self._analyzer = CachePerformanceAnalyzer(self)
        
        _logger.info(f"Initialized UnifiedCache with memory: {memory_size//1024//1024}MB, "
                    f"file: {file_size//1024//1024}MB, dir: {cache_dir}")
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache with multi-level fallback"""
        start_time = time.time()
        
        # Try memory cache first
        entry = self.memory_cache.get(key)
        if entry:
            self.stats.hits += 1
            self._record_access_pattern(key)
            _logger.debug(f"Cache hit (memory): {key}")
            return entry.value
        
        # Try file cache
        entry = self.file_cache.get(key)
        if entry:
            self.stats.hits += 1
            self._record_access_pattern(key)
            
            # Promote to memory cache if frequently accessed
            if entry.access_count > 3:
                self.memory_cache.put(entry)
            
            _logger.debug(f"Cache hit (file): {key}")
            return entry.value
        
        # Cache miss
        self.stats.misses += 1
        _logger.debug(f"Cache miss: {key}")
        return None
    
    def put(self, key: str, value: Any, ttl: Optional[float] = None, 
            tags: Optional[Set[str]] = None) -> None:
        """Store value in cache with automatic level selection"""
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl,
            tags=tags or set()
        )
        
        # Calculate entry size
        import pickle
        entry_size = len(pickle.dumps(value))
        
        # Strategy: Store large items (>1MB) or analysis results directly in file cache for persistence
        # Store small, frequently accessed items in memory cache for speed
        if (entry_size > 1024 * 1024 or  # Large items > 1MB
            key.startswith('analysis_')):   # Analysis results for cross-process persistence
            
            # Store in file cache for persistence
            if self.file_cache.put(entry):
                _logger.debug(f"Cached in file: {key} ({entry_size/1024:.1f}KB)")
                
                # Also store in memory if it's not too large (for speed)
                if entry_size < 10 * 1024 * 1024:  # < 10MB
                    self.memory_cache.put(entry)
            else:
                _logger.warning(f"Failed to cache in file: {key}")
        else:
            # Store small items in memory first
            if self.memory_cache.put(entry):
                _logger.debug(f"Cached in memory: {key} ({entry_size/1024:.1f}KB)")
            else:
                # Fall back to file cache
                if self.file_cache.put(entry):
                    _logger.debug(f"Cached in file (fallback): {key}")
                else:
                    _logger.warning(f"Failed to cache: {key}")
        
        self._record_access_pattern(key)
        self._update_stats()
    
    def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        memory_deleted = self.memory_cache.delete(key)
        file_deleted = self.file_cache.delete(key)
        
        if memory_deleted or file_deleted:
            self._update_stats()
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache levels"""
        self.memory_cache.clear()
        self.file_cache.clear()
        self.stats = CacheStats()
        self._access_patterns.clear()
        _logger.info("All caches cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            'unified': self.stats.to_dict(),
            'memory': {
                'size_bytes': self.memory_cache.size(),
                'entry_count': len(self.memory_cache.keys()),
                'max_size': self.memory_cache.max_size
            },
            'file': {
                'size_bytes': self.file_cache.size(),
                'entry_count': len(self.file_cache.keys()),
                'max_size': self.file_cache.max_size
            }
        }
    
    def optimize(self) -> Dict[str, Any]:
        """Optimize cache performance based on access patterns"""
        optimization_results = {}
        
        # Preheating based on access patterns
        if self._preheating_enabled:
            preheated = self._preheat_cache()
            optimization_results['preheated_keys'] = preheated
        
        # Performance analysis
        analysis = self._analyzer.analyze()
        optimization_results['performance_analysis'] = analysis
        
        return optimization_results
    
    def _record_access_pattern(self, key: str):
        """Record access pattern for smart preheating"""
        with self._lock:
            if key not in self._access_patterns:
                self._access_patterns[key] = []
            
            self._access_patterns[key].append(time.time())
            
            # Keep only recent access times (last 24 hours)
            cutoff = time.time() - 86400  # 24 hours
            self._access_patterns[key] = [
                t for t in self._access_patterns[key] if t > cutoff
            ]
    
    def _preheat_cache(self) -> List[str]:
        """Preheat cache based on access patterns"""
        preheated = []
        
        # Find frequently accessed keys that might need preheating
        for key, access_times in self._access_patterns.items():
            if len(access_times) >= 5:  # Frequently accessed
                # Check if key is likely to be accessed soon
                recent_accesses = [t for t in access_times if time.time() - t < 3600]  # Last hour
                if len(recent_accesses) >= 2:
                    # Try to ensure it's in memory cache
                    entry = self.file_cache.get(key)
                    if entry and not self.memory_cache.get(key):
                        if self.memory_cache.put(entry):
                            preheated.append(key)
        
        return preheated
    
    def _update_stats(self):
        """Update cache statistics"""
        self.stats.total_size = self.memory_cache.size() + self.file_cache.size()
        self.stats.entry_count = len(self.memory_cache.keys()) + len(self.file_cache.keys())


class CachePerformanceAnalyzer:
    """Analyzes cache performance and provides optimization recommendations"""
    
    def __init__(self, cache: UnifiedCache):
        self.cache = cache
        self._performance_history: List[Dict[str, Any]] = []
        self._start_time = time.time()
    
    def analyze(self) -> Dict[str, Any]:
        """Perform comprehensive performance analysis"""
        stats = self.cache.get_stats()
        
        analysis = {
            'hit_rate': stats['unified']['hit_rate'],
            'memory_utilization': stats['memory']['size_bytes'] / stats['memory']['max_size'],
            'file_utilization': stats['file']['size_bytes'] / stats['file']['max_size'],
            'recommendations': self._generate_recommendations(stats),
            'efficiency_score': self._calculate_efficiency_score(stats)
        }
        
        # Record performance history
        self._performance_history.append({
            'timestamp': time.time(),
            'analysis': analysis.copy()
        })
        
        # Keep only recent history (last 100 entries)
        self._performance_history = self._performance_history[-100:]
        
        return analysis
    
    def get_analysis(self) -> Dict[str, Any]:
        """Get current performance analysis"""
        if not self._performance_history:
            return self.analyze()
        return self._performance_history[-1]['analysis']
    
    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        hit_rate = stats['unified']['hit_rate']
        memory_util = stats['memory']['size_bytes'] / stats['memory']['max_size']
        file_util = stats['file']['size_bytes'] / stats['file']['max_size']
        
        if hit_rate < 0.5:
            recommendations.append("Low hit rate detected. Consider increasing cache sizes or reviewing access patterns.")
        
        if memory_util > 0.9:
            recommendations.append("Memory cache nearly full. Consider increasing memory cache size.")
        
        if file_util > 0.9:
            recommendations.append("File cache nearly full. Consider increasing file cache size or implementing more aggressive eviction.")
        
        if hit_rate > 0.9 and memory_util < 0.3:
            recommendations.append("High hit rate with low memory utilization. Consider reducing memory cache size.")
        
        return recommendations
    
    def _calculate_efficiency_score(self, stats: Dict[str, Any]) -> float:
        """Calculate overall cache efficiency score (0-100)"""
        hit_rate = stats['unified']['hit_rate']
        memory_util = stats['memory']['size_bytes'] / stats['memory']['max_size']
        
        # Base score from hit rate (0-70 points)
        base_score = hit_rate * 70
        
        # Bonus points for optimal memory utilization (0-30 points)
        optimal_util = 0.7  # Target 70% utilization
        util_score = 30 * (1 - abs(memory_util - optimal_util) / optimal_util)
        util_score = max(0, util_score)
        
        return min(100, base_score + util_score)


# Global cache instance
_global_cache: Optional[UnifiedCache] = None


def get_cache() -> UnifiedCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = UnifiedCache()
    return _global_cache


def clear_cache() -> None:
    """Clear global cache"""
    global _global_cache
    if _global_cache:
        _global_cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    return get_cache().get_stats()


def optimize_cache() -> Dict[str, Any]:
    """Optimize global cache performance"""
    return get_cache().optimize() 