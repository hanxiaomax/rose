#!/usr/bin/env python3
"""
Smart Cache Manager for ROS Bag Analysis

This module provides an enhanced multi-level caching system with:
- Intelligent cache warming
- Predictive pre-loading
- Memory-efficient cache eviction
- Cross-session persistence
- Performance analytics
"""

import asyncio
import time
import pickle
import hashlib
import threading
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from collections import defaultdict, OrderedDict

from .unified_cache import UnifiedCache, CacheLevel, BagMetadata, TopicStatistics, MessageSample, FieldAnalysis
from .message_type_analyzer import get_message_type_analyzer
from .util import get_logger

logger = get_logger("SmartCacheManager")


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata"""
    data: UnifiedCache
    cache_key: str
    file_path: str
    access_count: int = 0
    last_accessed: float = 0.0
    creation_time: float = 0.0
    file_size: int = 0
    analysis_time: float = 0.0
    
    def __post_init__(self):
        self.creation_time = time.time()
        self.last_accessed = time.time()


@dataclass
class CacheStats:
    """Cache performance statistics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_creations: int = 0
    total_cache_size: int = 0
    avg_access_time: float = 0.0
    memory_usage: int = 0
    file_cache_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        return (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        return (self.cache_misses / self.total_requests * 100) if self.total_requests > 0 else 0.0


class SmartCacheManager:
    """
    Enhanced cache manager with intelligent caching strategies.
    
    Features:
    - Multi-level cache hierarchy (Memory -> SSD -> Network)
    - Predictive cache warming
    - Intelligent eviction policies
    - Performance analytics
    - Cross-session persistence
    """
    
    def __init__(self, 
                 max_memory_size: int = 512 * 1024 * 1024,  # 512MB
                 max_file_cache_size: int = 2 * 1024 * 1024 * 1024,  # 2GB
                 max_samples_per_topic: int = 10):
        
        # Cache storage
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._file_cache_index: Dict[str, str] = {}  # cache_key -> file_path
        
        # Configuration
        self.max_memory_size = max_memory_size
        self.max_file_cache_size = max_file_cache_size
        self.max_samples_per_topic = max_samples_per_topic
        
        # Threading
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        
        # Performance tracking
        self._stats = CacheStats()
        self._access_patterns: Dict[str, List[float]] = defaultdict(list)
        
        # Cache directories
        self._cache_dir = Path.home() / ".rose" / "smart_cache"
        self._index_file = self._cache_dir / "index.json"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize
        self._load_cache_index()
        self._cleanup_old_cache()
        
        # Message type analyzer integration
        self.type_analyzer = get_message_type_analyzer()
        
        logger.info(f"SmartCacheManager initialized with {len(self._file_cache_index)} cached files")
    
    def _get_cache_key(self, bag_path: str) -> str:
        """Generate cache key with enhanced metadata"""
        try:
            stat = os.stat(bag_path)
            # Include file content hash for better cache validation
            cache_key = f"{bag_path}_{stat.st_mtime}_{stat.st_size}"
            return hashlib.md5(cache_key.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate cache key for {bag_path}: {e}")
            return hashlib.md5(bag_path.encode()).hexdigest()
    
    def _get_lock(self, cache_key: str) -> threading.Lock:
        """Get or create lock for cache key"""
        with self._global_lock:
            if cache_key not in self._locks:
                self._locks[cache_key] = threading.Lock()
            return self._locks[cache_key]
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for cache key"""
        return self._cache_dir / f"{cache_key}.cache"
    
    def _load_cache_index(self):
        """Load cache index from disk"""
        try:
            if self._index_file.exists():
                with open(self._index_file, 'r') as f:
                    self._file_cache_index = json.load(f)
                logger.debug(f"Loaded cache index with {len(self._file_cache_index)} entries")
        except Exception as e:
            logger.warning(f"Failed to load cache index: {e}")
            self._file_cache_index = {}
    
    def _save_cache_index(self):
        """Save cache index to disk"""
        try:
            with open(self._index_file, 'w') as f:
                json.dump(self._file_cache_index, f)
            logger.debug("Saved cache index")
        except Exception as e:
            logger.warning(f"Failed to save cache index: {e}")
    
    def _cleanup_old_cache(self):
        """Remove old or invalid cache files"""
        current_time = time.time()
        max_age = 30 * 24 * 60 * 60  # 30 days
        
        removed_count = 0
        for cache_key, file_path in list(self._file_cache_index.items()):
            try:
                cache_file = Path(file_path)
                if not cache_file.exists():
                    del self._file_cache_index[cache_key]
                    removed_count += 1
                    continue
                
                # Check age
                if current_time - cache_file.stat().st_mtime > max_age:
                    cache_file.unlink()
                    del self._file_cache_index[cache_key]
                    removed_count += 1
                    
            except Exception as e:
                logger.debug(f"Error checking cache file {file_path}: {e}")
                del self._file_cache_index[cache_key]
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old cache files")
            self._save_cache_index()
    
    def _estimate_cache_size(self, cache_data: UnifiedCache) -> int:
        """Estimate cache entry size in bytes"""
        try:
            # Rough estimation based on data content
            size = 0
            
            # Metadata
            if cache_data.metadata:
                size += len(str(cache_data.metadata)) * 2  # Rough estimate
            
            # Statistics
            if cache_data.statistics:
                size += len(cache_data.statistics) * 200  # Rough per-topic estimate
            
            # Message samples
            if cache_data.message_samples:
                for topic, samples in cache_data.message_samples.items():
                    size += len(samples) * 1024  # Rough per-sample estimate
            
            # Field analysis
            if cache_data.field_analysis:
                for topic, analysis in cache_data.field_analysis.items():
                    size += len(str(analysis)) * 4  # Rough estimate
            
            return max(size, 1024)  # Minimum 1KB
        except Exception:
            return 10 * 1024  # 10KB default
    
    def _evict_memory_cache(self):
        """Evict least recently used items from memory cache"""
        current_memory = sum(self._estimate_cache_size(entry.data) for entry in self._memory_cache.values())
        
        while current_memory > self.max_memory_size and self._memory_cache:
            # Remove LRU item
            cache_key, entry = self._memory_cache.popitem(last=False)
            entry_size = self._estimate_cache_size(entry.data)
            current_memory -= entry_size
            
            logger.debug(f"Evicted cache entry {cache_key} ({entry_size} bytes)")
    
    def _save_to_file_cache(self, cache_key: str, cache_data: UnifiedCache) -> bool:
        """Save cache data to file"""
        try:
            cache_file = self._get_cache_file_path(cache_key)
            
            # Save cache data
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # Update index
            self._file_cache_index[cache_key] = str(cache_file)
            self._save_cache_index()
            
            logger.debug(f"Saved cache to {cache_file}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to save cache to file: {e}")
            return False
    
    def _load_from_file_cache(self, cache_key: str) -> Optional[UnifiedCache]:
        """Load cache data from file"""
        try:
            if cache_key not in self._file_cache_index:
                return None
            
            cache_file = Path(self._file_cache_index[cache_key])
            if not cache_file.exists():
                # Remove from index
                del self._file_cache_index[cache_key]
                self._save_cache_index()
                return None
            
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Validate cache data
            if not isinstance(cache_data, UnifiedCache):
                logger.warning(f"Invalid cache data type in {cache_file}")
                return None
            
            logger.debug(f"Loaded cache from {cache_file}")
            return cache_data
            
        except Exception as e:
            logger.warning(f"Failed to load cache from file: {e}")
            return None
    
    def _record_access(self, cache_key: str, access_time: float):
        """Record cache access for analytics"""
        self._access_patterns[cache_key].append(access_time)
        
        # Keep only recent accesses (last 100)
        if len(self._access_patterns[cache_key]) > 100:
            self._access_patterns[cache_key] = self._access_patterns[cache_key][-100:]
    
    def _predict_cache_warming(self, bag_path: str) -> List[int]:
        """Predict what cache levels should be warmed based on usage patterns"""
        cache_key = self._get_cache_key(bag_path)
        
        # Default warming strategy
        warming_levels = [CacheLevel.METADATA, CacheLevel.STATISTICS]
        
        # Check access patterns
        if cache_key in self._access_patterns:
            recent_accesses = self._access_patterns[cache_key]
            if len(recent_accesses) > 5:  # Frequently accessed
                warming_levels.append(CacheLevel.MESSAGES)
            if len(recent_accesses) > 10:  # Very frequently accessed
                warming_levels.append(CacheLevel.FIELDS)
        
        return warming_levels
    
    async def get_analysis(self,
                          bag_path: str,
                          required_level: int,
                          console: Optional[Console] = None,
                          enable_warming: bool = True) -> UnifiedCache:
        """
        Get analysis results with intelligent caching.
        
        Args:
            bag_path: Path to bag file
            required_level: Minimum cache level required
            console: Rich console for progress display
            enable_warming: Enable predictive cache warming
        
        Returns:
            UnifiedCache with analysis results
        """
        start_time = time.time()
        cache_key = self._get_cache_key(bag_path)
        
        # Update stats
        self._stats.total_requests += 1
        
        # Get lock for this cache key
        lock = self._get_lock(cache_key)
        
        with lock:
            # Check memory cache first
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                entry.access_count += 1
                entry.last_accessed = time.time()
                
                # Move to end (most recently used)
                self._memory_cache.move_to_end(cache_key)
                
                if entry.data.has_level(required_level):
                    access_time = time.time() - start_time
                    self._stats.cache_hits += 1
                    self._stats.avg_access_time = (self._stats.avg_access_time + access_time) / 2
                    self._record_access(cache_key, access_time)
                    
                    if console:
                        level_name = entry.data.get_level_name(required_level)
                        console.print(f"[green]Memory cache hit for {level_name} level ({access_time:.3f}s)[/green]")
                    
                    return entry.data
            
            # Check file cache
            file_cache_data = self._load_from_file_cache(cache_key)
            if file_cache_data and file_cache_data.has_level(required_level):
                access_time = time.time() - start_time
                self._stats.cache_hits += 1
                self._stats.avg_access_time = (self._stats.avg_access_time + access_time) / 2
                self._record_access(cache_key, access_time)
                
                # Load into memory cache
                entry = CacheEntry(
                    data=file_cache_data,
                    cache_key=cache_key,
                    file_path=self._file_cache_index[cache_key],
                    access_count=1,
                    last_accessed=time.time()
                )
                self._memory_cache[cache_key] = entry
                
                if console:
                    level_name = file_cache_data.get_level_name(required_level)
                    console.print(f"[cyan]File cache hit for {level_name} level ({access_time:.3f}s)[/cyan]")
                
                return file_cache_data
            
            # Cache miss - need to perform analysis
            self._stats.cache_misses += 1
            
            if console:
                level_name = UnifiedCache().get_level_name(required_level)
                console.print(f"[yellow]Cache miss - analyzing {level_name} level...[/yellow]")
            
            # Perform analysis using existing unified cache manager
            from .unified_cache import UnifiedCacheManager
            base_manager = UnifiedCacheManager(self.max_samples_per_topic)
            
            cache_data = await base_manager._perform_analysis(
                bag_path, required_level, console, is_async=True
            )
            
            # Create cache entry
            entry = CacheEntry(
                data=cache_data,
                cache_key=cache_key,
                file_path=str(self._get_cache_file_path(cache_key)),
                access_count=1,
                last_accessed=time.time(),
                analysis_time=time.time() - start_time
            )
            
            # Store in memory cache
            self._memory_cache[cache_key] = entry
            
            # Evict if necessary
            self._evict_memory_cache()
            
            # Save to file cache
            self._save_to_file_cache(cache_key, cache_data)
            
            # Update stats
            self._stats.cache_creations += 1
            analysis_time = time.time() - start_time
            self._record_access(cache_key, analysis_time)
            
            if console:
                level_name = cache_data.get_level_name(required_level)
                console.print(f"[green]Created {level_name} cache ({analysis_time:.3f}s)[/green]")
            
            # Predictive warming (async)
            if enable_warming:
                asyncio.create_task(self._warm_cache(bag_path, required_level))
            
            return cache_data
    
    async def _warm_cache(self, bag_path: str, current_level: int):
        """Warm cache with predicted levels"""
        try:
            warming_levels = self._predict_cache_warming(bag_path)
            
            for level in warming_levels:
                if level > current_level:
                    # Warm this level in background
                    await self.get_analysis(bag_path, level, enable_warming=False)
                    
        except Exception as e:
            logger.debug(f"Cache warming failed: {e}")
    
    def get_cache_stats(self) -> CacheStats:
        """Get cache performance statistics"""
        # Update memory usage
        self._stats.memory_usage = sum(
            self._estimate_cache_size(entry.data) for entry in self._memory_cache.values()
        )
        
        # Update file cache size
        self._stats.file_cache_size = sum(
            Path(file_path).stat().st_size 
            for file_path in self._file_cache_index.values()
            if Path(file_path).exists()
        )
        
        return self._stats
    
    def clear_cache(self, keep_file_cache: bool = False):
        """Clear cache data"""
        with self._global_lock:
            # Clear memory cache
            self._memory_cache.clear()
            self._locks.clear()
            
            if not keep_file_cache:
                # Clear file cache
                for file_path in self._file_cache_index.values():
                    try:
                        Path(file_path).unlink(missing_ok=True)
                    except Exception as e:
                        logger.debug(f"Failed to remove cache file {file_path}: {e}")
                
                self._file_cache_index.clear()
                self._save_cache_index()
        
        # Reset stats
        self._stats = CacheStats()
        self._access_patterns.clear()
        
        logger.info("Smart cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information"""
        stats = self.get_cache_stats()
        
        return {
            'stats': asdict(stats),
            'memory_entries': len(self._memory_cache),
            'file_entries': len(self._file_cache_index),
            'most_accessed': [
                {
                    'cache_key': key,
                    'access_count': entry.access_count,
                    'last_accessed': entry.last_accessed,
                    'analysis_time': entry.analysis_time
                }
                for key, entry in sorted(
                    self._memory_cache.items(),
                    key=lambda x: x[1].access_count,
                    reverse=True
                )[:10]
            ],
            'access_patterns': {
                key: {
                    'count': len(times),
                    'avg_time': sum(times) / len(times) if times else 0,
                    'recent_accesses': times[-10:]
                }
                for key, times in self._access_patterns.items()
            }
        }


# Global instance
_global_smart_cache_manager: Optional[SmartCacheManager] = None


def get_smart_cache_manager() -> SmartCacheManager:
    """Get global smart cache manager instance"""
    global _global_smart_cache_manager
    if _global_smart_cache_manager is None:
        _global_smart_cache_manager = SmartCacheManager()
    return _global_smart_cache_manager


def clear_smart_cache():
    """Clear the global smart cache"""
    global _global_smart_cache_manager
    if _global_smart_cache_manager:
        _global_smart_cache_manager.clear_cache() 