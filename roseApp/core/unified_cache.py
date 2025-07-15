#!/usr/bin/env python3
"""
Unified Cache System for ROS Bag Analysis

This module provides a unified caching mechanism that can be used by both
synchronous and asynchronous bag analysis methods, ensuring consistent
performance and cache behavior.
"""

import asyncio
import time
import pickle
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console

from .parser import create_parser, ParserType
from .util import get_logger

logger = get_logger()


@dataclass
class CacheLevel:
    """Cache levels for hierarchical caching"""
    METADATA = 1      # Basic bag metadata (topics, connections, time_range)
    STATISTICS = 2    # Message counts and sizes
    MESSAGES = 3      # Sample messages for field analysis
    FIELDS = 4        # Complete field analysis


@dataclass
class ProfileInfo:
    """Performance profiling information"""
    operation: str
    duration_seconds: float
    cache_action: str  # 'hit', 'miss', 'create'
    cache_level: int
    timestamp: float


class PerformanceProfiler:
    """Collects and manages performance profiling data"""
    
    def __init__(self):
        self.enabled = False
        self.profiles: List[ProfileInfo] = []
        self._lock = threading.Lock()
    
    def enable(self):
        """Enable performance profiling"""
        self.enabled = True
    
    def disable(self):
        """Disable performance profiling"""
        self.enabled = False
    
    def record(self, operation: str, duration: float, cache_action: str, cache_level: int):
        """Record a performance measurement"""
        if not self.enabled:
            return
        
        with self._lock:
            self.profiles.append(ProfileInfo(
                operation=operation,
                duration_seconds=duration,
                cache_action=cache_action,
                cache_level=cache_level,
                timestamp=time.time()
            ))
    
    def get_profiles(self) -> List[ProfileInfo]:
        """Get all recorded profiles"""
        with self._lock:
            return self.profiles.copy()
    
    def clear(self):
        """Clear all recorded profiles"""
        with self._lock:
            self.profiles.clear()
    
    def print_summary(self, console: Console):
        """Print a summary of performance profiles"""
        if not self.enabled or not self.profiles:
            return
        
        console.print("\n[bold cyan]Performance Profile Summary[/bold cyan]")
        
        from rich.table import Table
        table = Table(title="Analysis Performance")
        table.add_column("Operation", style="cyan")
        table.add_column("Duration", style="yellow")
        table.add_column("Cache Action", style="green")
        table.add_column("Cache Level", style="blue")
        
        for profile in self.profiles:
            cache_action_color = {
                'hit': 'green',
                'miss': 'yellow', 
                'create': 'blue'
            }.get(profile.cache_action, 'white')
            
            table.add_row(
                profile.operation,
                f"{profile.duration_seconds:.3f}s",
                f"[{cache_action_color}]{profile.cache_action}[/{cache_action_color}]",
                str(profile.cache_level)
            )
        
        console.print(table)
        
        # Summary statistics
        total_time = sum(p.duration_seconds for p in self.profiles)
        cache_hits = sum(1 for p in self.profiles if p.cache_action == 'hit')
        total_ops = len(self.profiles)
        
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total time: {total_time:.3f}s")
        console.print(f"  Cache hit rate: {cache_hits}/{total_ops} ({cache_hits/total_ops*100:.1f}%)")


@dataclass
class BagMetadata:
    """Basic bag metadata structure"""
    topics: List[str]
    connections: Dict[str, str]
    time_range: Tuple[Tuple[int, int], Tuple[int, int]]
    file_size: int
    original_bag_path: str
    cache_timestamp: float


@dataclass
class TopicStatistics:
    """Topic statistics structure"""
    count: int
    size: int
    avg_size: int
    frequency: Optional[float] = None


@dataclass
class MessageSample:
    """Sample message data for field analysis"""
    timestamp: Tuple[int, int]
    raw_data: bytes
    topic: str
    msg_type: str


@dataclass
class FieldAnalysis:
    """Field analysis results"""
    fields: Dict[str, Any]
    message_type: str
    samples_analyzed: int
    max_depth: int


@dataclass
class UnifiedCache:
    """Unified cache structure for all analysis levels"""
    # Level 1: Metadata
    metadata: Optional[BagMetadata] = None
    
    # Level 2: Statistics
    statistics: Optional[Dict[str, TopicStatistics]] = None
    total_messages: int = 0
    total_data_size: int = 0
    duration: Optional[float] = None
    
    # Level 3: Message samples
    message_samples: Optional[Dict[str, List[MessageSample]]] = None
    
    # Level 4: Field analysis results
    field_analysis: Optional[Dict[str, FieldAnalysis]] = None
    
    # Cache metadata
    cache_level: int = 0
    analysis_timestamp: float = 0.0
    
    def has_level(self, level: int) -> bool:
        """Check if cache has data for the specified level"""
        return self.cache_level >= level
    
    def get_level_name(self, level: int) -> str:
        """Get human-readable name for cache level"""
        level_names = {
            CacheLevel.METADATA: "metadata",
            CacheLevel.STATISTICS: "statistics", 
            CacheLevel.MESSAGES: "messages",
            CacheLevel.FIELDS: "fields"
        }
        return level_names.get(level, f"level_{level}")


class UnifiedCacheManager:
    """Unified cache manager for both sync and async analysis"""
    
    def __init__(self, max_samples_per_topic: int = 10):
        self._cache: Dict[str, UnifiedCache] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self.max_samples_per_topic = max_samples_per_topic
        self.profiler = PerformanceProfiler()
        self._cache_dir = Path.home() / ".rose" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, bag_path: str) -> str:
        """Generate cache key for bag file"""
        import os
        stat = os.stat(bag_path)
        cache_key = f"{bag_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _get_lock(self, cache_key: str) -> threading.Lock:
        """Get or create lock for cache key"""
        with self._global_lock:
            if cache_key not in self._locks:
                self._locks[cache_key] = threading.Lock()
            return self._locks[cache_key]
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for cache key"""
        return self._cache_dir / f"{cache_key}.pickle"
    
    def _save_cache_to_file(self, cache_key: str, cache_data: UnifiedCache):
        """Save cache data to file"""
        try:
            cache_file = self._get_cache_file_path(cache_key)
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.debug(f"Saved cache to {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache to file: {e}")
    
    def _load_cache_from_file(self, cache_key: str) -> Optional[UnifiedCache]:
        """Load cache data from file"""
        try:
            cache_file = self._get_cache_file_path(cache_key)
            if not cache_file.exists():
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
    
    async def get_analysis(
        self,
        bag_path: str,
        required_level: int,
        console: Optional[Console] = None,
        is_async: bool = True
    ) -> UnifiedCache:
        """
        Get analysis results with unified caching
        
        Args:
            bag_path: Path to bag file
            required_level: Minimum cache level required
            console: Rich console for progress display
            is_async: Whether this is an async call (for profiling)
            
        Returns:
            UnifiedCache with at least the required level of data
        """
        cache_key = self._get_cache_key(bag_path)
        lock = self._get_lock(cache_key)
        
        operation_name = f"{'async' if is_async else 'sync'}_analysis_level_{required_level}"
        start_time = time.time()
        
        with lock:
            # Check if we have sufficient cached data
            cached = None
            
            # First check in-memory cache
            if cache_key in self._cache:
                cached = self._cache[cache_key]
            else:
                # If not in memory, try to load from file
                cached = self._load_cache_from_file(cache_key)
                if cached:
                    # Store in memory for faster access
                    self._cache[cache_key] = cached
            
            if cached and cached.has_level(required_level):
                duration = time.time() - start_time
                self.profiler.record(operation_name, duration, 'hit', required_level)
                
                if console and self.profiler.enabled:
                    level_name = cached.get_level_name(required_level)
                    console.print(f"[dim]Cache hit for {level_name} level ({duration:.3f}s)[/dim]")
                return cached
            
            # Cache miss - need to perform analysis
            if console and self.profiler.enabled:
                level_name = UnifiedCache().get_level_name(required_level)
                console.print(f"[yellow]Cache miss - analyzing {level_name} level...[/yellow]")
            
            # Perform analysis
            cache_data = await self._perform_analysis(
                bag_path, required_level, console, is_async
            )
            
            # Store in cache (both memory and file)
            self._cache[cache_key] = cache_data
            self._save_cache_to_file(cache_key, cache_data)
            
            duration = time.time() - start_time
            self.profiler.record(operation_name, duration, 'create', required_level)
            
            if console and self.profiler.enabled:
                level_name = cache_data.get_level_name(required_level)
                console.print(f"[green]Created {level_name} cache ({duration:.3f}s)[/green]")
            
            return cache_data
    
    async def _perform_analysis(
        self,
        bag_path: str,
        target_level: int,
        console: Optional[Console],
        is_async: bool
    ) -> UnifiedCache:
        """Perform actual bag analysis up to target level"""
        
        if is_async:
            # Run in thread pool for async calls
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_analysis, bag_path, target_level, console)
        else:
            # Direct call for sync calls
            return self._sync_analysis(bag_path, target_level, console)
    
    def _sync_analysis(self, bag_path: str, target_level: int, console: Optional[Console]) -> UnifiedCache:
        """Synchronous analysis implementation"""
        
        parser = create_parser(ParserType.ROSBAGS)
        cache = UnifiedCache()
        
        # Level 1: Metadata (always required)
        topics, connections, time_range = parser.load_bag(bag_path)
        
        import os
        file_size = os.path.getsize(bag_path)
        
        cache.metadata = BagMetadata(
            topics=topics,
            connections=connections,
            time_range=time_range,
            file_size=file_size,
            original_bag_path=bag_path,
            cache_timestamp=time.time()
        )
        cache.cache_level = CacheLevel.METADATA
        cache.analysis_timestamp = time.time()
        
        if target_level <= CacheLevel.METADATA:
            return cache
        
        # Level 2: Statistics
        if target_level >= CacheLevel.STATISTICS:
            try:
                if target_level == CacheLevel.STATISTICS:
                    # Lightweight mode for statistics only
                    topic_counts = parser.get_message_counts(bag_path)
                    statistics = {}
                    total_messages = 0
                    
                    for topic in topics:
                        if topic in topic_counts:
                            count = topic_counts[topic]
                            statistics[topic] = TopicStatistics(
                                count=count,
                                size=0,  # Not available in lightweight mode
                                avg_size=0
                            )
                            total_messages += count
                        else:
                            statistics[topic] = TopicStatistics(count=0, size=0, avg_size=0)
                else:
                    # Full mode for higher levels
                    topic_stats = parser.get_topic_stats(bag_path)
                    statistics = {}
                    total_messages = 0
                    total_data_size = 0
                    
                    for topic in topics:
                        if topic in topic_stats:
                            stats = topic_stats[topic]
                            statistics[topic] = TopicStatistics(
                                count=stats['count'],
                                size=stats['size'],
                                avg_size=stats['avg_size']
                            )
                            total_messages += stats['count']
                            total_data_size += stats['size']
                        else:
                            statistics[topic] = TopicStatistics(count=0, size=0, avg_size=0)
                    
                    cache.total_data_size = total_data_size
                
                cache.statistics = statistics
                cache.total_messages = total_messages
                cache.cache_level = CacheLevel.STATISTICS
                
            except Exception as e:
                logger.warning(f"Failed to get topic statistics: {e}")
                # Fallback to basic statistics
                statistics = {}
                for topic in topics:
                    statistics[topic] = TopicStatistics(count=0, size=0, avg_size=0)
                cache.statistics = statistics
                cache.total_messages = 0
                cache.cache_level = CacheLevel.STATISTICS
        
        if target_level <= CacheLevel.STATISTICS:
            return cache
        
        # Level 3 & 4: Messages and Fields - Now optimized!
        if target_level >= CacheLevel.MESSAGES:
            cache.message_samples = {}  # Placeholder for message samples
            cache.cache_level = CacheLevel.MESSAGES
        
        if target_level >= CacheLevel.FIELDS:
            # Use optimized field analysis
            try:
                from roseApp.core.unified_analyzer import UnifiedBagAnalyzer
                analyzer = UnifiedBagAnalyzer()
                
                # Get field analysis using the new optimized method
                field_analysis = analyzer._analyze_fields_optimized(
                    bag_path, 
                    topics, 
                    connections
                )
                
                cache.field_analysis = field_analysis
                cache.cache_level = CacheLevel.FIELDS
                
                if console:
                    console.print(f"[green]Field analysis completed using optimized type system[/green]")
                
            except Exception as e:
                logger.warning(f"Optimized field analysis failed: {e}")
                # Fallback to empty field analysis
                cache.field_analysis = {}
                cache.cache_level = CacheLevel.FIELDS
        
        return cache
    
    def clear_cache(self):
        """Clear all cached data"""
        with self._global_lock:
            self._cache.clear()
            self._locks.clear()
            
        # Clear file cache
        self._clear_file_cache()
    
    def _clear_file_cache(self):
        """Clear all cache files"""
        try:
            if self._cache_dir.exists():
                for cache_file in self._cache_dir.glob("*.pickle"):
                    try:
                        cache_file.unlink()
                        logger.debug(f"Removed cache file: {cache_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {cache_file}: {e}")
        except Exception as e:
            logger.warning(f"Failed to clear file cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        return {
            'cache_size': len(self._cache),
            'cached_files': len(self._cache),
            'profiler_enabled': self.profiler.enabled,
            'total_profiles': len(self.profiler.profiles)
        }
    
    def enable_profiling(self):
        """Enable performance profiling"""
        self.profiler.enable()
    
    def disable_profiling(self):
        """Disable performance profiling"""
        self.profiler.disable()
    
    def print_profile_summary(self, console: Console):
        """Print performance profile summary"""
        self.profiler.print_summary(console)


# Global unified cache manager
_global_cache_manager: Optional[UnifiedCacheManager] = None


def get_unified_cache_manager() -> UnifiedCacheManager:
    """Get global unified cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = UnifiedCacheManager()
    return _global_cache_manager


# Convenience functions for backward compatibility
async def analyze_bag_unified(
    bag_path: str,
    console: Optional[Console] = None,
    required_level: int = CacheLevel.STATISTICS,
    is_async: bool = True
) -> UnifiedCache:
    """
    Unified bag analysis function for both sync and async usage
    
    Args:
        bag_path: Path to bag file
        console: Rich console for progress display
        required_level: Minimum cache level required
        is_async: Whether this is being called from async context
        
    Returns:
        UnifiedCache with analysis results
    """
    cache_manager = get_unified_cache_manager()
    return await cache_manager.get_analysis(bag_path, required_level, console, is_async) 