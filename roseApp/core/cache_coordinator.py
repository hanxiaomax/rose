"""
Cache Coordination System for Rose

This module provides unified cache coordination between analyzer and parser,
implementing a multi-phase optimization strategy to eliminate redundancy
and improve overall performance.
"""

import time
import hashlib
from pathlib import Path
from typing import Dict, Optional, Any, Union, Tuple, List
from dataclasses import dataclass
from enum import Enum

from .cache import get_cache
from .util import get_logger

_logger = get_logger("cache_coordinator")


class CacheStrategy(Enum):
    """Cache strategy types"""
    PARSER_DATA = "parser_data"
    ANALYSIS_METADATA = "analysis_metadata"
    ANALYSIS_FULL = "analysis_full"
    MESSAGE_TYPES = "message_types"


@dataclass
class CacheConfig:
    """Cache configuration for different data types"""
    ttl: int  # Time to live in seconds
    storage_preference: str  # 'memory', 'file', or 'both'
    description: str
    max_size_mb: Optional[int] = None


class CacheKeyManager:
    """Unified cache key management following consistent naming strategy"""
    
    # Cache configuration for different data types
    CACHE_CONFIGS = {
        CacheStrategy.PARSER_DATA: CacheConfig(
            ttl=1800,  # 30 minutes
            storage_preference='memory',
            description='Raw bag metadata and statistics for fast access',
            max_size_mb=50
        ),
        CacheStrategy.ANALYSIS_METADATA: CacheConfig(
            ttl=3600,  # 1 hour
            storage_preference='file',
            description='Lightweight analysis results for persistence',
            max_size_mb=100
        ),
        CacheStrategy.ANALYSIS_FULL: CacheConfig(
            ttl=7200,  # 2 hours
            storage_preference='file',
            description='Complete analysis with message types for long-term cache',
            max_size_mb=200
        ),
        CacheStrategy.MESSAGE_TYPES: CacheConfig(
            ttl=86400,  # 24 hours
            storage_preference='file',
            description='Message type structure analysis for very long-term cache',
            max_size_mb=20
        )
    }
    
    @staticmethod
    def generate_cache_key(bag_path: str, operation: str, 
                          params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate unified cache key following consistent naming strategy
        
        Args:
            bag_path: Path to the bag file
            operation: Operation type (e.g., 'parser_data', 'analysis')
            params: Additional parameters to include in key
            
        Returns:
            Standardized cache key
        """
        try:
            # Get file modification time for cache invalidation
            mtime = Path(bag_path).stat().st_mtime
        except (OSError, FileNotFoundError):
            # If file doesn't exist, use current time (will cause cache miss)
            mtime = time.time()
        
        # Build parameter string
        param_str = ""
        if params:
            # Sort parameters for consistent keys
            sorted_params = sorted(params.items())
            param_parts = [f"{k}:{v}" for k, v in sorted_params]
            param_str = "_" + "_".join(param_parts)
        
        # Create base key
        base_key = f"rose_{operation}_{bag_path}_{int(mtime)}{param_str}"
        
        # Hash long keys to avoid filesystem limitations
        if len(base_key) > 200:
            key_hash = hashlib.md5(base_key.encode()).hexdigest()
            base_key = f"rose_{operation}_{key_hash}"
        
        return base_key
    
    @staticmethod
    def get_config(strategy: CacheStrategy) -> CacheConfig:
        """Get cache configuration for a strategy"""
        return CacheKeyManager.CACHE_CONFIGS[strategy]
    
    @staticmethod
    def generate_parser_key(bag_path: str) -> str:
        """Generate cache key for parser data"""
        return CacheKeyManager.generate_cache_key(bag_path, "parser_data")
    
    @staticmethod
    def generate_analysis_key(bag_path: str, analysis_type: str) -> str:
        """Generate cache key for analysis results"""
        return CacheKeyManager.generate_cache_key(
            bag_path, "analysis", {"type": analysis_type}
        )
    
    @staticmethod
    def generate_message_type_key(message_type: str) -> str:
        """Generate cache key for message type analysis"""
        return CacheKeyManager.generate_cache_key(
            "", "message_type", {"type": message_type}
        )


class CacheBridge:
    """Bridge between different cache layers for coordination"""
    
    def __init__(self):
        self.cache = get_cache()
        self.stats = {
            'parser_hits': 0,
            'analyzer_hits': 0,
            'coordination_saves': 0,
            'cache_builds': 0
        }
    
    def get_parser_data_with_fallback(self, bag_path: str, 
                                     parser_instance=None) -> Optional[Any]:
        """
        Get parser data with unified cache fallback
        
        Args:
            bag_path: Path to bag file
            parser_instance: Parser instance to use if cache miss
            
        Returns:
            Parser data from cache or fresh load
        """
        cache_key = CacheKeyManager.generate_parser_key(bag_path)
        
        # Try unified cache first
        cached_data = self.cache.get(cache_key)
        if cached_data:
            self.stats['parser_hits'] += 1
            _logger.debug(f"Parser cache hit (unified): {bag_path}")
            return cached_data
        
        # Try parser instance cache if available
        if parser_instance and hasattr(parser_instance, '_bag_info_cache'):
            instance_cached = parser_instance._bag_info_cache.get(bag_path)
            if instance_cached:
                # Promote to unified cache
                config = CacheKeyManager.get_config(CacheStrategy.PARSER_DATA)
                self.cache.put(cache_key, instance_cached, ttl=config.ttl)
                self.stats['coordination_saves'] += 1
                _logger.debug(f"Parser cache promoted to unified: {bag_path}")
                return instance_cached
        
        return None
    
    def store_parser_data(self, bag_path: str, data: Any, 
                         parser_instance=None) -> None:
        """
        Store parser data in unified cache and optionally instance cache
        
        Args:
            bag_path: Path to bag file
            data: Parser data to store
            parser_instance: Parser instance to also store in
        """
        cache_key = CacheKeyManager.generate_parser_key(bag_path)
        config = CacheKeyManager.get_config(CacheStrategy.PARSER_DATA)
        
        # Store in unified cache
        self.cache.put(cache_key, data, ttl=config.ttl)
        
        # Also store in parser instance cache if available
        if parser_instance and hasattr(parser_instance, '_bag_info_cache'):
            parser_instance._bag_info_cache[bag_path] = data
        
        _logger.debug(f"Parser data stored (unified + instance): {bag_path}")
    
    def can_build_analysis_from_parser(self, bag_path: str, 
                                      analysis_type: str) -> bool:
        """Check if analysis can be built from parser cache"""
        if analysis_type != "metadata":
            return False
        
        cache_key = CacheKeyManager.generate_parser_key(bag_path)
        return self.cache.get(cache_key) is not None
    
    def build_analysis_from_parser(self, bag_path: str, 
                                  analysis_type: str) -> Optional[Any]:
        """
        Build lightweight analysis result from parser cache
        
        Args:
            bag_path: Path to bag file
            analysis_type: Type of analysis
            
        Returns:
            Analysis result built from parser data or None
        """
        if analysis_type != "metadata":
            return None
        
        parser_data = self.get_parser_data_with_fallback(bag_path)
        if not parser_data:
            return None
        
        # Import here to avoid circular imports
        from .analyzer import AnalysisResult, BagInfo, AnalysisType
        
        # Build BagInfo from parser data
        bag_info = BagInfo(
            path=Path(bag_path),
            size_bytes=getattr(parser_data, 'total_size', 0),
            topics=set(getattr(parser_data, 'topics', [])),
            message_counts=getattr(parser_data, 'message_counts', {}),
            time_range=getattr(parser_data, 'time_range', None),
            connections=getattr(parser_data, 'connections', {}),
            duration_seconds=getattr(parser_data, 'duration_seconds', 0.0)
        )
        
        # Convert string to AnalysisType enum
        analysis_type_enum = AnalysisType.METADATA if analysis_type == "metadata" else AnalysisType.FULL_ANALYSIS
        
        # Create lightweight analysis result
        result = AnalysisResult(
            bag_info=bag_info,
            analysis_type=analysis_type_enum,
            analysis_time=0.001,  # Very fast since built from cache
            cached=True
        )
        
        self.stats['cache_builds'] += 1
        _logger.info(f"Built analysis from parser cache: {bag_path}")
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache coordination statistics"""
        total_requests = sum(self.stats.values())
        
        return {
            'total_requests': total_requests,
            'parser_hits': self.stats['parser_hits'],
            'analyzer_hits': self.stats['analyzer_hits'],
            'coordination_saves': self.stats['coordination_saves'],
            'cache_builds': self.stats['cache_builds'],
            'coordination_efficiency': (
                self.stats['coordination_saves'] + self.stats['cache_builds']
            ) / max(1, total_requests) * 100
        }


# Global cache bridge instance
_cache_bridge: Optional[CacheBridge] = None


def get_cache_bridge() -> CacheBridge:
    """Get or create global cache bridge instance"""
    global _cache_bridge
    if _cache_bridge is None:
        _cache_bridge = CacheBridge()
        _logger.info("Initialized global cache bridge for coordination")
    return _cache_bridge


def get_cache_coordination_stats() -> Dict[str, Any]:
    """Get cache coordination statistics"""
    bridge = get_cache_bridge()
    return bridge.get_cache_stats()


def clear_cache_coordination():
    """Clear cache coordination state"""
    global _cache_bridge
    if _cache_bridge:
        _cache_bridge.stats = {
            'parser_hits': 0,
            'analyzer_hits': 0,
            'coordination_saves': 0,
            'cache_builds': 0
        }
        _logger.info("Cleared cache coordination statistics") 


class UnifiedCacheCoordinator:
    """Phase 3: Unified cache coordinator for intelligent cache management"""
    
    def __init__(self):
        self.cache = get_cache()
        self.bridge = get_cache_bridge()
        self.performance_monitor = CachePerformanceMonitor()
        self.strategy_optimizer = CacheStrategyOptimizer()
        
    def get_optimized_data(self, request_type: str, bag_path: str, **params) -> Any:
        """
        Get data using optimized cache strategy
        
        Args:
            request_type: Type of request ('parser_data', 'analysis_metadata', etc.)
            bag_path: Path to bag file
            **params: Additional parameters
            
        Returns:
            Requested data with optimal caching strategy
        """
        strategy = self.strategy_optimizer.get_optimal_strategy(request_type, **params)
        
        # Record request for performance monitoring
        start_time = time.time()
        self.performance_monitor.record_request(request_type, bag_path)
        
        try:
            # Execute strategy
            result = strategy.execute(self.cache, self.bridge, bag_path, **params)
            
            # Record success
            self.performance_monitor.record_success(request_type, time.time() - start_time)
            return result
            
        except Exception as e:
            # Record failure
            self.performance_monitor.record_failure(request_type, str(e))
            raise
    
    def optimize_cache_performance(self) -> Dict[str, Any]:
        """Optimize cache performance based on usage patterns"""
        analysis = self.performance_monitor.analyze_performance()
        recommendations = self.strategy_optimizer.generate_recommendations(analysis)
        
        # Apply automatic optimizations
        optimizations_applied = []
        for recommendation in recommendations:
            if recommendation['auto_apply']:
                self._apply_optimization(recommendation)
                optimizations_applied.append(recommendation['description'])
        
        return {
            'performance_analysis': analysis,
            'recommendations': recommendations,
            'optimizations_applied': optimizations_applied
        }
    
    def _apply_optimization(self, recommendation: Dict[str, Any]) -> None:
        """Apply cache optimization recommendation"""
        if recommendation['type'] == 'preload':
            self._preload_frequent_data(recommendation['data'])
        elif recommendation['type'] == 'cleanup':
            self._cleanup_stale_cache(recommendation['criteria'])
        elif recommendation['type'] == 'rebalance':
            self._rebalance_cache_storage(recommendation['strategy'])
    
    def _preload_frequent_data(self, data_patterns: List[str]) -> None:
        """Preload frequently accessed data patterns"""
        for pattern in data_patterns:
            # Implementation for preloading based on access patterns
            _logger.debug(f"Preloading data pattern: {pattern}")
    
    def _cleanup_stale_cache(self, criteria: Dict[str, Any]) -> None:
        """Clean up stale cache entries based on criteria"""
        # Implementation for cache cleanup
        _logger.debug(f"Cleaning up cache with criteria: {criteria}")
    
    def _rebalance_cache_storage(self, strategy: str) -> None:
        """Rebalance cache between memory and file storage"""
        # Implementation for cache rebalancing
        _logger.debug(f"Rebalancing cache with strategy: {strategy}")
    
    def get_comprehensive_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics across all layers"""
        return {
            'unified_cache': self.cache.get_stats(),
            'coordination': self.bridge.get_cache_stats(),
            'performance': self.performance_monitor.get_performance_summary(),
            'optimization': self.strategy_optimizer.get_optimization_status()
        }


class CachePerformanceMonitor:
    """Monitors cache performance and usage patterns"""
    
    def __init__(self):
        self.request_history = []
        self.performance_metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'coordination_saves': 0,
            'avg_response_time': 0.0
        }
        self.pattern_tracker = {}
    
    def record_request(self, request_type: str, resource_id: str) -> None:
        """Record a cache request"""
        self.request_history.append({
            'type': request_type,
            'resource': resource_id,
            'timestamp': time.time()
        })
        self.performance_metrics['total_requests'] += 1
        
        # Track access patterns
        pattern_key = f"{request_type}:{resource_id}"
        if pattern_key not in self.pattern_tracker:
            self.pattern_tracker[pattern_key] = {'count': 0, 'last_access': 0}
        self.pattern_tracker[pattern_key]['count'] += 1
        self.pattern_tracker[pattern_key]['last_access'] = time.time()
    
    def record_success(self, request_type: str, response_time: float) -> None:
        """Record a successful cache operation"""
        self.performance_metrics['cache_hits'] += 1
        # Update average response time
        total_time = self.performance_metrics['avg_response_time'] * (self.performance_metrics['cache_hits'] - 1)
        self.performance_metrics['avg_response_time'] = (total_time + response_time) / self.performance_metrics['cache_hits']
    
    def record_failure(self, request_type: str, error: str) -> None:
        """Record a cache miss or failure"""
        self.performance_metrics['cache_misses'] += 1
        _logger.debug(f"Cache miss for {request_type}: {error}")
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze cache performance and return insights"""
        total_requests = self.performance_metrics['total_requests']
        hit_rate = self.performance_metrics['cache_hits'] / max(1, total_requests)
        
        # Identify frequent access patterns
        frequent_patterns = [
            {'pattern': pattern, 'count': data['count']}
            for pattern, data in self.pattern_tracker.items()
            if data['count'] >= 3  # Accessed 3+ times
        ]
        frequent_patterns.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'hit_rate': hit_rate,
            'avg_response_time': self.performance_metrics['avg_response_time'],
            'total_requests': total_requests,
            'frequent_patterns': frequent_patterns[:10],  # Top 10
            'performance_grade': self._calculate_performance_grade(hit_rate)
        }
    
    def _calculate_performance_grade(self, hit_rate: float) -> str:
        """Calculate performance grade based on hit rate"""
        if hit_rate >= 0.9:
            return 'A'
        elif hit_rate >= 0.8:
            return 'B'
        elif hit_rate >= 0.7:
            return 'C'
        elif hit_rate >= 0.6:
            return 'D'
        else:
            return 'F'
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return self.performance_metrics.copy()


class CacheStrategyOptimizer:
    """Optimizes cache strategies based on usage patterns"""
    
    def __init__(self):
        self.strategies = {}
        self.optimization_history = []
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self) -> None:
        """Initialize default cache strategies"""
        self.strategies = {
            'parser_data': OptimizedCacheStrategy(
                name='parser_data',
                prefetch=True,
                ttl_multiplier=1.0,
                storage_preference='memory'
            ),
            'analysis_metadata': OptimizedCacheStrategy(
                name='analysis_metadata',
                prefetch=False,
                ttl_multiplier=1.5,
                storage_preference='file'
            ),
            'analysis_full': OptimizedCacheStrategy(
                name='analysis_full',
                prefetch=False,
                ttl_multiplier=2.0,
                storage_preference='file'
            )
        }
    
    def get_optimal_strategy(self, request_type: str, **params) -> 'OptimizedCacheStrategy':
        """Get optimal cache strategy for request type"""
        base_strategy = self.strategies.get(request_type)
        if not base_strategy:
            # Create default strategy
            base_strategy = OptimizedCacheStrategy(
                name=request_type,
                prefetch=False,
                ttl_multiplier=1.0,
                storage_preference='memory'
            )
        
        # Optimize strategy based on parameters and usage patterns
        return self._optimize_strategy(base_strategy, **params)
    
    def _optimize_strategy(self, strategy: 'OptimizedCacheStrategy', **params) -> 'OptimizedCacheStrategy':
        """Optimize strategy based on current conditions"""
        # Clone strategy for modification
        optimized = OptimizedCacheStrategy(
            name=strategy.name,
            prefetch=strategy.prefetch,
            ttl_multiplier=strategy.ttl_multiplier,
            storage_preference=strategy.storage_preference
        )
        
        # Apply optimizations based on parameters
        if params.get('high_frequency', False):
            optimized.prefetch = True
            optimized.storage_preference = 'memory'
        
        if params.get('large_data', False):
            optimized.storage_preference = 'file'
            optimized.ttl_multiplier *= 1.5
        
        return optimized
    
    def generate_recommendations(self, performance_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate optimization recommendations based on performance"""
        recommendations = []
        
        hit_rate = performance_analysis['hit_rate']
        frequent_patterns = performance_analysis['frequent_patterns']
        
        # Low hit rate recommendations
        if hit_rate < 0.7:
            recommendations.append({
                'type': 'increase_ttl',
                'description': 'Increase cache TTL for better hit rates',
                'auto_apply': True,
                'impact': 'medium'
            })
        
        # Frequent access pattern optimizations
        if len(frequent_patterns) > 5:
            recommendations.append({
                'type': 'preload',
                'description': 'Preload frequently accessed data',
                'data': [p['pattern'] for p in frequent_patterns[:3]],
                'auto_apply': False,
                'impact': 'high'
            })
        
        return recommendations
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status"""
        return {
            'active_strategies': len(self.strategies),
            'optimizations_applied': len(self.optimization_history),
            'last_optimization': self.optimization_history[-1] if self.optimization_history else None
        }


@dataclass
class OptimizedCacheStrategy:
    """Optimized cache strategy configuration"""
    name: str
    prefetch: bool
    ttl_multiplier: float
    storage_preference: str  # 'memory', 'file', 'both'
    
    def execute(self, cache, bridge, bag_path: str, **params) -> Any:
        """Execute the cache strategy"""
        # Strategy execution logic
        cache_key = CacheKeyManager.generate_cache_key(bag_path, self.name, params)
        
        # Try cache first
        result = cache.get(cache_key)
        if result:
            return result
        
        # If cache miss, determine how to load data
        if self.name == 'parser_data':
            return self._load_parser_data(bridge, bag_path, cache_key, cache)
        elif self.name.startswith('analysis'):
            return self._load_analysis_data(bridge, bag_path, cache_key, cache, **params)
        else:
            # Generic data loading
            return self._load_generic_data(bag_path, cache_key, cache, **params)
    
    def _load_parser_data(self, bridge, bag_path: str, cache_key: str, cache) -> Any:
        """Load parser data using strategy"""
        # Try to get from bridge first
        result = bridge.get_parser_data_with_fallback(bag_path)
        if result:
            return result
        
        # If not available, need to create parser and load
        # This would typically involve creating parser instance and loading
        _logger.debug(f"Would load parser data for {bag_path}")
        return None
    
    def _load_analysis_data(self, bridge, bag_path: str, cache_key: str, cache, **params) -> Any:
        """Load analysis data using strategy"""
        analysis_type = params.get('type', 'metadata')
        
        # Try building from parser cache first
        if analysis_type == 'metadata':
            result = bridge.build_analysis_from_parser(bag_path, analysis_type)
            if result:
                return result
        
        # Need full analysis
        _logger.debug(f"Would perform full analysis for {bag_path}")
        return None
    
    def _load_generic_data(self, bag_path: str, cache_key: str, cache, **params) -> Any:
        """Load generic data using strategy"""
        _logger.debug(f"Would load generic data for {bag_path}")
        return None


# Global coordinator instance
_unified_coordinator: Optional[UnifiedCacheCoordinator] = None


def get_unified_coordinator() -> UnifiedCacheCoordinator:
    """Get or create global unified cache coordinator"""
    global _unified_coordinator
    if _unified_coordinator is None:
        _unified_coordinator = UnifiedCacheCoordinator()
        _logger.info("Initialized unified cache coordinator")
    return _unified_coordinator


def optimize_cache_performance() -> Dict[str, Any]:
    """Optimize cache performance globally"""
    coordinator = get_unified_coordinator()
    return coordinator.optimize_cache_performance()


def get_comprehensive_cache_stats() -> Dict[str, Any]:
    """Get comprehensive cache statistics"""
    coordinator = get_unified_coordinator()
    return coordinator.get_comprehensive_cache_stats() 