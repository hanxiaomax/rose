"""
Unified cache management system for Rose.

This module provides a comprehensive caching solution with simple interfaces
for bag analysis data, message caching, and general-purpose caching.
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


# ===== BAG-SPECIFIC CACHE DATA STRUCTURES =====

@dataclass
class CachedMessageData:
    """Cached message traversal data"""
    topic: str
    message_type: str
    timestamp: float
    message_data: Dict[str, Any]  # Serialized message content


@dataclass
class BagCacheEntry:
    """Complete bag cache entry with metadata and message data"""
    bag_info: Any  # ComprehensiveBagInfo - avoiding circular import
    cached_messages: Dict[str, List[CachedMessageData]]  # topic -> messages
    cache_timestamp: float
    file_mtime: float
    file_size: int
    
    def is_valid(self, bag_path: Path) -> bool:
        """Check if cache entry is still valid"""
        if not bag_path.exists():
            return False
        
        stat = bag_path.stat()
        return (stat.st_mtime == self.file_mtime and 
                stat.st_size == self.file_size)


# ===== CACHE BACKENDS =====

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


# ===== UNIFIED CACHE SYSTEM =====

class UnifiedCache:
    """
    Unified cache system with simple interfaces for different data types
    
    Provides:
    - General purpose caching (get/put/delete/clear)
    - Bag-specific caching (bag analysis data + messages)
    - Statistics and monitoring
    """
    
    def __init__(self, 
                 memory_size: int = 512 * 1024 * 1024,  # 512MB
                 file_size: int = 2 * 1024 * 1024 * 1024,  # 2GB
                 cache_dir: Optional[Path] = None):
        
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "rose_cache"
        
        self.memory_cache = MemoryCache(memory_size)
        self.file_cache = FileCache(cache_dir, file_size)
        
        self.stats = CacheStats()
        self._lock = threading.RLock()
        
        # Bag-specific configuration
        self.max_memory_entries = 50
        self.max_cached_messages_per_topic = 1000
        
        _logger.info(f"Initialized UnifiedCache with memory: {memory_size//1024//1024}MB, "
                    f"file: {file_size//1024//1024}MB, dir: {cache_dir}")
    
    # ===== GENERAL PURPOSE CACHE INTERFACE =====
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache with multi-level fallback"""
        # Try memory cache first
        entry = self.memory_cache.get(key)
        if entry:
            self.stats.hits += 1
            _logger.debug(f"Cache hit (memory): {key}")
            return entry.value
        
        # Try file cache
        entry = self.file_cache.get(key)
        if entry:
            self.stats.hits += 1
            
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
        entry_size = len(pickle.dumps(value))
        
        # Strategy: Store large items (>1MB) or analysis results directly in file cache for persistence
        # Store small, frequently accessed items in memory cache for speed
        if (entry_size > 1024 * 1024 or  # Large items > 1MB
            key.startswith('analysis_') or  # Analysis results for cross-process persistence
            key.startswith('bag_')):        # Bag data for persistence
            
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
        
        self._update_stats()
    
    def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        memory_deleted = self.memory_cache.delete(key)
        file_deleted = self.file_cache.delete(key)
        
        if memory_deleted or file_deleted:
            self._update_stats()
            return True
        return False
    
    def clear(self, pattern: Optional[str] = None) -> None:
        """Clear cache entries, optionally filtered by key pattern"""
        if pattern is None:
            # Clear all caches
            self.memory_cache.clear()
            self.file_cache.clear()
            self.stats = CacheStats()
            _logger.info("All caches cleared")
        else:
            # Clear entries matching pattern
            keys_to_delete = []
            for key in self.memory_cache.keys():
                if pattern in key:
                    keys_to_delete.append(key)
            for key in self.file_cache.keys():
                if pattern in key and key not in keys_to_delete:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                self.delete(key)
            
            _logger.info(f"Cleared {len(keys_to_delete)} cache entries matching pattern: {pattern}")
    
    # ===== BAG-SPECIFIC CACHE INTERFACE =====
    
    def get_bag_cache_key(self, bag_path: Path) -> str:
        """Generate cache key for bag file"""
        return f"bag_{hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()}"
    
    def get_bag_analysis(self, bag_path: Path) -> Optional[BagCacheEntry]:
        """Get cached bag analysis data"""
        cache_key = self.get_bag_cache_key(bag_path)
        cached_data = self.get(cache_key)
        
        if cached_data and isinstance(cached_data, BagCacheEntry):
            if cached_data.is_valid(bag_path):
                _logger.debug(f"Using cached bag analysis for {bag_path}")
                return cached_data
            else:
                # Remove invalid cache
                self.delete(cache_key)
        
        return None
    
    def put_bag_analysis(self, bag_path: Path, bag_info: Any, 
                        cached_messages: Optional[Dict[str, List[CachedMessageData]]] = None) -> None:
        """Store bag analysis data in cache"""
        if not bag_path.exists():
            return
        
        cache_key = self.get_bag_cache_key(bag_path)
        stat = bag_path.stat()
        
        cache_entry = BagCacheEntry(
            bag_info=bag_info,
            cached_messages=cached_messages or {},
            cache_timestamp=time.time(),
            file_mtime=stat.st_mtime,
            file_size=stat.st_size
        )
        
        self.put(cache_key, cache_entry, tags={'bag_analysis'})
        _logger.debug(f"Cached bag analysis for {bag_path}")
    
    def get_bag_messages(self, bag_path: Path, topic: str) -> Optional[List[CachedMessageData]]:
        """Get cached messages for a specific topic"""
        bag_cache = self.get_bag_analysis(bag_path)
        if bag_cache:
            return bag_cache.cached_messages.get(topic)
        return None
    
    def put_bag_messages(self, bag_path: Path, topic: str, messages: List[CachedMessageData]) -> None:
        """Add cached messages for a topic"""
        bag_cache = self.get_bag_analysis(bag_path)
        if bag_cache is None:
            return
        
        # Limit number of cached messages per topic
        if len(messages) > self.max_cached_messages_per_topic:
            messages = messages[:self.max_cached_messages_per_topic]
        
        bag_cache.cached_messages[topic] = messages
        
        # Update cache
        self.put_bag_analysis(bag_path, bag_cache.bag_info, bag_cache.cached_messages)
        _logger.debug(f"Cached {len(messages)} messages for topic {topic} in {bag_path}")
    
    def clear_bag_cache(self, bag_path: Optional[Path] = None) -> None:
        """Clear bag-specific cache entries"""
        if bag_path is None:
            # Clear all bag caches
            self.clear("bag_")
        else:
            # Clear specific bag cache
            cache_key = self.get_bag_cache_key(bag_path)
            self.delete(cache_key)
            _logger.debug(f"Cleared cache for {bag_path}")
    
    # ===== STATISTICS AND MONITORING =====
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'hit_rate': self.stats.hit_rate,
            'evictions': self.stats.evictions,
            'total_size': self.stats.total_size,
            'entry_count': self.stats.entry_count,
            'memory': {
                'size_bytes': self.memory_cache.size(),
                'entry_count': len(self.memory_cache.keys()),
                'max_size': self.memory_cache.max_size
            },
            'file': {
                'size_bytes': self.file_cache.size(),
                'entry_count': len(self.file_cache.keys()),
                'max_size': self.file_cache.max_size
            },
            'bag_specific': {
                'max_memory_entries': self.max_memory_entries,
                'max_cached_messages_per_topic': self.max_cached_messages_per_topic
            }
        }
    
    def _update_stats(self):
        """Update cache statistics"""
        self.stats.total_size = self.memory_cache.size() + self.file_cache.size()
        self.stats.entry_count = len(self.memory_cache.keys()) + len(self.file_cache.keys())


# ===== GLOBAL CACHE INSTANCE =====

_global_cache: Optional[UnifiedCache] = None


def get_cache() -> UnifiedCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = UnifiedCache()
    return _global_cache


def clear_cache(pattern: Optional[str] = None) -> None:
    """Clear global cache"""
    global _global_cache
    if _global_cache:
        _global_cache.clear(pattern)


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    return get_cache().get_stats()


# ===== SIMPLE CACHE INTERFACE FOR BAG MANAGER =====

class BagCacheManager:
    """
    Simple interface for bag-specific caching operations
    Used by BagManager to handle bag analysis and message caching
    """
    
    def __init__(self, cache: Optional[UnifiedCache] = None):
        self.cache = cache or get_cache()
        self.logger = get_logger("bag_cache")
    
    def get_analysis(self, bag_path: Path) -> Optional[BagCacheEntry]:
        """Get cached bag analysis"""
        return self.cache.get_bag_analysis(bag_path)
    
    def put_analysis(self, bag_path: Path, bag_info: Any, 
                    cached_messages: Optional[Dict[str, List[CachedMessageData]]] = None) -> None:
        """Store bag analysis in cache"""
        self.cache.put_bag_analysis(bag_path, bag_info, cached_messages)
    
    def get_messages(self, bag_path: Path, topic: str) -> Optional[List[CachedMessageData]]:
        """Get cached messages for a topic"""
        return self.cache.get_bag_messages(bag_path, topic)
    
    def put_messages(self, bag_path: Path, topic: str, messages: List[CachedMessageData]) -> None:
        """Store messages for a topic"""
        self.cache.put_bag_messages(bag_path, topic, messages)
    
    def clear(self, bag_path: Optional[Path] = None) -> None:
        """Clear bag cache"""
        self.cache.clear_bag_cache(bag_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()


def create_bag_cache_manager() -> BagCacheManager:
    """Create a new bag cache manager instance"""
    return BagCacheManager() 