#!/usr/bin/env python3
"""
Enhanced cache management with cross-command support and intelligent strategies.

This module provides an advanced caching system that supports multiple cache
strategies optimized for different command types and use cases.
"""

import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

from ..core.util import get_logger
from ..core.unified_cache import UnifiedCache, CacheLevel, get_unified_cache_manager


class CacheStrategy(Enum):
    """Cache strategy types"""
    INSPECT_OPTIMIZED = "inspect_optimized"
    FILTER_OPTIMIZED = "filter_optimized"
    PLOT_OPTIMIZED = "plot_optimized"
    PRUNE_OPTIMIZED = "prune_optimized"
    SHARED_METADATA = "shared_metadata"


@dataclass
class CacheRequest:
    """Cache request specification"""
    bag_path: str
    command: str
    level: CacheLevel
    strategy: CacheStrategy
    priority: int = 5  # 1 = highest, 10 = lowest
    expires_in: Optional[float] = None  # seconds from now


@dataclass
class CacheAnalysis:
    """Cache analysis result"""
    cache_key: str
    hit_rate: float
    total_requests: int
    cache_hits: int
    cache_misses: int
    average_access_time: float
    storage_size: int


class BaseCacheStrategy(ABC):
    """Base class for cache strategies"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"cache.{name}")
        
    @abstractmethod
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get cached data for request"""
        pass
        
    @abstractmethod
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store data in cache"""
        pass
        
    @abstractmethod
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for request"""
        pass
        
    @abstractmethod
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if data should be cached"""
        pass


class InspectCacheStrategy(BaseCacheStrategy):
    """Cache strategy optimized for inspect command"""
    
    def __init__(self):
        super().__init__("inspect")
        self.cache_manager = get_unified_cache_manager()
        
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get cached data optimized for inspect operations"""
        try:
            # Use unified cache manager for inspect operations
            unified_cache = await self.cache_manager.get_analysis(
                request.bag_path,
                request.level,
                console=None,
                is_async=True
            )
            return unified_cache
            
        except Exception as e:
            self.logger.error(f"Error getting cached data for inspect: {e}")
            return None
            
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store data optimized for inspect operations"""
        # Unified cache manager handles storage automatically
        pass
        
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for inspect operations"""
        return f"inspect_{request.bag_path}_{request.level.value}"
        
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if inspect data should be cached"""
        # Always cache inspect data as it's frequently reused
        return True


class FilterCacheStrategy(BaseCacheStrategy):
    """Cache strategy optimized for filter command"""
    
    def __init__(self):
        super().__init__("filter")
        self.metadata_cache: Dict[str, Any] = {}
        self.topic_cache: Dict[str, Set[str]] = {}
        self.cache_lock = threading.Lock()
        
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get cached data optimized for filter operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            if cache_key in self.metadata_cache:
                cached_data = self.metadata_cache[cache_key]
                if self._is_cache_valid(cached_data):
                    return cached_data['data']
                    
        # If not in filter cache, try unified cache
        try:
            cache_manager = get_unified_cache_manager()
            unified_cache = await cache_manager.get_analysis(
                request.bag_path,
                CacheLevel.METADATA,  # Filter typically only needs metadata
                console=None,
                is_async=True
            )
            
            # Store in filter cache for fast access
            await self.store_cached_data(request, unified_cache)
            return unified_cache
            
        except Exception as e:
            self.logger.error(f"Error getting cached data for filter: {e}")
            return None
            
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store data optimized for filter operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            self.metadata_cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'expires_at': time.time() + (request.expires_in or 3600)  # 1 hour default
            }
            
            # Store topic list for fast lookup
            if hasattr(data, 'metadata') and data.metadata:
                self.topic_cache[request.bag_path] = set(data.metadata.topics)
                
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for filter operations"""
        return f"filter_{request.bag_path}_metadata"
        
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if filter data should be cached"""
        # Cache metadata for filter operations
        return request.level == CacheLevel.METADATA
        
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid"""
        return time.time() < cached_data.get('expires_at', 0)
        
    def get_available_topics(self, bag_path: str) -> Optional[Set[str]]:
        """Get available topics for a bag file"""
        with self.cache_lock:
            return self.topic_cache.get(bag_path)


class PlotCacheStrategy(BaseCacheStrategy):
    """Cache strategy optimized for plot command"""
    
    def __init__(self):
        super().__init__("plot")
        self.field_cache: Dict[str, Any] = {}
        self.sample_cache: Dict[str, Any] = {}
        self.cache_lock = threading.Lock()
        
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get cached data optimized for plot operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            if cache_key in self.field_cache:
                cached_data = self.field_cache[cache_key]
                if self._is_cache_valid(cached_data):
                    return cached_data['data']
                    
        # If not in plot cache, try unified cache
        try:
            cache_manager = get_unified_cache_manager()
            unified_cache = await cache_manager.get_analysis(
                request.bag_path,
                CacheLevel.FIELDS,  # Plot typically needs field analysis
                console=None,
                is_async=True
            )
            
            # Store in plot cache for fast access
            await self.store_cached_data(request, unified_cache)
            return unified_cache
            
        except Exception as e:
            self.logger.error(f"Error getting cached data for plot: {e}")
            return None
            
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store data optimized for plot operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            self.field_cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'expires_at': time.time() + (request.expires_in or 1800)  # 30 minutes default
            }
            
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for plot operations"""
        return f"plot_{request.bag_path}_fields"
        
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if plot data should be cached"""
        # Cache field analysis for plot operations
        return request.level >= CacheLevel.FIELDS
        
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid"""
        return time.time() < cached_data.get('expires_at', 0)


class PruneCacheStrategy(BaseCacheStrategy):
    """Cache strategy optimized for prune command"""
    
    def __init__(self):
        super().__init__("prune")
        self.statistics_cache: Dict[str, Any] = {}
        self.cache_lock = threading.Lock()
        
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get cached data optimized for prune operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            if cache_key in self.statistics_cache:
                cached_data = self.statistics_cache[cache_key]
                if self._is_cache_valid(cached_data):
                    return cached_data['data']
                    
        # If not in prune cache, try unified cache
        try:
            cache_manager = get_unified_cache_manager()
            unified_cache = await cache_manager.get_analysis(
                request.bag_path,
                CacheLevel.STATISTICS,  # Prune typically needs statistics
                console=None,
                is_async=True
            )
            
            # Store in prune cache for fast access
            await self.store_cached_data(request, unified_cache)
            return unified_cache
            
        except Exception as e:
            self.logger.error(f"Error getting cached data for prune: {e}")
            return None
            
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store data optimized for prune operations"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            self.statistics_cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'expires_at': time.time() + (request.expires_in or 1800)  # 30 minutes default
            }
            
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for prune operations"""
        return f"prune_{request.bag_path}_statistics"
        
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if prune data should be cached"""
        # Cache statistics for prune operations
        return request.level >= CacheLevel.STATISTICS
        
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid"""
        return time.time() < cached_data.get('expires_at', 0)


class SharedMetadataStrategy(BaseCacheStrategy):
    """Shared metadata cache strategy for cross-command optimization"""
    
    def __init__(self):
        super().__init__("shared_metadata")
        self.shared_cache: Dict[str, Any] = {}
        self.access_patterns: Dict[str, List[float]] = {}
        self.cache_lock = threading.Lock()
        
    async def get_cached_data(self, request: CacheRequest) -> Optional[Any]:
        """Get shared metadata cache"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            if cache_key in self.shared_cache:
                cached_data = self.shared_cache[cache_key]
                if self._is_cache_valid(cached_data):
                    # Record access pattern
                    self._record_access(cache_key)
                    return cached_data['data']
                    
        return None
        
    async def store_cached_data(self, request: CacheRequest, data: Any) -> None:
        """Store shared metadata"""
        cache_key = self.get_cache_key(request)
        
        with self.cache_lock:
            self.shared_cache[cache_key] = {
                'data': data,
                'timestamp': time.time(),
                'expires_at': time.time() + (request.expires_in or 7200),  # 2 hours default
                'access_count': 1
            }
            
    def get_cache_key(self, request: CacheRequest) -> str:
        """Generate cache key for shared metadata"""
        return f"shared_{request.bag_path}_metadata"
        
    def should_cache(self, request: CacheRequest, data: Any) -> bool:
        """Determine if shared metadata should be cached"""
        # Always cache shared metadata
        return True
        
    def _is_cache_valid(self, cached_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid"""
        return time.time() < cached_data.get('expires_at', 0)
        
    def _record_access(self, cache_key: str) -> None:
        """Record access pattern for predictive caching"""
        if cache_key not in self.access_patterns:
            self.access_patterns[cache_key] = []
            
        self.access_patterns[cache_key].append(time.time())
        
        # Keep only recent accesses (last hour)
        cutoff_time = time.time() - 3600
        self.access_patterns[cache_key] = [
            t for t in self.access_patterns[cache_key] if t > cutoff_time
        ]


class EnhancedCacheManager:
    """Enhanced cache manager with cross-command support"""
    
    def __init__(self):
        """Initialize enhanced cache manager"""
        self.strategies: Dict[CacheStrategy, BaseCacheStrategy] = {
            CacheStrategy.INSPECT_OPTIMIZED: InspectCacheStrategy(),
            CacheStrategy.FILTER_OPTIMIZED: FilterCacheStrategy(),
            CacheStrategy.PLOT_OPTIMIZED: PlotCacheStrategy(),
            CacheStrategy.PRUNE_OPTIMIZED: PruneCacheStrategy(),
            CacheStrategy.SHARED_METADATA: SharedMetadataStrategy()
        }
        
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.cache_stats: Dict[str, CacheAnalysis] = {}
        self.logger = get_logger(__name__)
        
    async def get_cached_analysis(self, bag_path: str, 
                                 command: str,
                                 level: CacheLevel,
                                 strategy: Optional[CacheStrategy] = None) -> Optional[Any]:
        """
        Get cached analysis optimized for specific command
        
        Args:
            bag_path: Path to bag file
            command: Command name ('inspect', 'filter', 'plot', 'prune')
            level: Required cache level
            strategy: Optional specific strategy to use
            
        Returns:
            Cached analysis data or None if not available
        """
        # Determine strategy if not specified
        if strategy is None:
            strategy = self._get_default_strategy(command)
            
        # Create cache request
        request = CacheRequest(
            bag_path=bag_path,
            command=command,
            level=level,
            strategy=strategy
        )
        
        # Get data from appropriate strategy
        cache_strategy = self.strategies.get(strategy)
        if cache_strategy:
            start_time = time.time()
            result = await cache_strategy.get_cached_data(request)
            
            # Update statistics
            self._update_stats(request, result is not None, time.time() - start_time)
            
            return result
            
        return None
        
    async def store_analysis(self, bag_path: str,
                           command: str,
                           level: CacheLevel,
                           data: Any,
                           strategy: Optional[CacheStrategy] = None) -> None:
        """
        Store analysis data with appropriate strategy
        
        Args:
            bag_path: Path to bag file
            command: Command name
            level: Cache level
            data: Data to store
            strategy: Optional specific strategy to use
        """
        # Determine strategy if not specified
        if strategy is None:
            strategy = self._get_default_strategy(command)
            
        # Create cache request
        request = CacheRequest(
            bag_path=bag_path,
            command=command,
            level=level,
            strategy=strategy
        )
        
        # Store data using appropriate strategy
        cache_strategy = self.strategies.get(strategy)
        if cache_strategy and cache_strategy.should_cache(request, data):
            await cache_strategy.store_cached_data(request, data)
            
    def _get_default_strategy(self, command: str) -> CacheStrategy:
        """Get default cache strategy for command"""
        strategy_map = {
            'inspect': CacheStrategy.INSPECT_OPTIMIZED,
            'filter': CacheStrategy.FILTER_OPTIMIZED,
            'plot': CacheStrategy.PLOT_OPTIMIZED,
            'prune': CacheStrategy.PRUNE_OPTIMIZED
        }
        return strategy_map.get(command, CacheStrategy.SHARED_METADATA)
        
    def _update_stats(self, request: CacheRequest, cache_hit: bool, access_time: float) -> None:
        """Update cache statistics"""
        cache_key = f"{request.command}_{request.strategy.value}"
        
        if cache_key not in self.cache_stats:
            self.cache_stats[cache_key] = CacheAnalysis(
                cache_key=cache_key,
                hit_rate=0.0,
                total_requests=0,
                cache_hits=0,
                cache_misses=0,
                average_access_time=0.0,
                storage_size=0
            )
            
        stats = self.cache_stats[cache_key]
        stats.total_requests += 1
        
        if cache_hit:
            stats.cache_hits += 1
        else:
            stats.cache_misses += 1
            
        stats.hit_rate = stats.cache_hits / stats.total_requests
        stats.average_access_time = (
            (stats.average_access_time * (stats.total_requests - 1) + access_time) / 
            stats.total_requests
        )
        
    def get_cache_statistics(self) -> Dict[str, CacheAnalysis]:
        """Get cache statistics for all strategies"""
        return dict(self.cache_stats)
        
    def clear_cache_statistics(self) -> None:
        """Clear cache statistics"""
        self.cache_stats.clear()
        
    async def warm_cache(self, bag_paths: List[str], 
                        commands: List[str]) -> None:
        """
        Warm cache for frequently accessed bags and commands
        
        Args:
            bag_paths: List of bag paths to warm
            commands: List of commands to warm cache for
        """
        for bag_path in bag_paths:
            for command in commands:
                try:
                    await self.get_cached_analysis(
                        bag_path, 
                        command, 
                        CacheLevel.METADATA
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to warm cache for {bag_path}, {command}: {e}")
                    
    async def cleanup_expired_cache(self) -> None:
        """Clean up expired cache entries"""
        for strategy in self.strategies.values():
            if hasattr(strategy, 'cleanup_expired'):
                await strategy.cleanup_expired()


# Global enhanced cache manager instance
_global_enhanced_cache_manager: Optional[EnhancedCacheManager] = None


def get_enhanced_cache_manager() -> EnhancedCacheManager:
    """Get global enhanced cache manager instance"""
    global _global_enhanced_cache_manager
    if _global_enhanced_cache_manager is None:
        _global_enhanced_cache_manager = EnhancedCacheManager()
    return _global_enhanced_cache_manager 