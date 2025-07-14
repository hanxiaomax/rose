#!/usr/bin/env python3
"""
Unified Analyzer Interface

This module provides a unified interface for both synchronous and asynchronous
bag analysis, using the shared unified cache system for consistent performance.
"""

import asyncio
from typing import Optional, Dict, Any
from rich.console import Console

from .unified_cache import (
    get_unified_cache_manager, 
    analyze_bag_unified,
    CacheLevel,
    UnifiedCache
)
from .util import get_logger

logger = get_logger()


class UnifiedBagAnalyzer:
    """Unified bag analyzer that works for both sync and async usage"""
    
    def __init__(self):
        self.cache_manager = get_unified_cache_manager()
    
    async def analyze_async(
        self,
        bag_path: str,
        console: Optional[Console] = None,
        required_level: int = CacheLevel.STATISTICS
    ) -> UnifiedCache:
        """
        Asynchronous bag analysis using unified cache
        
        Args:
            bag_path: Path to bag file
            console: Rich console for progress display
            required_level: Minimum cache level required
            
        Returns:
            UnifiedCache with analysis results
        """
        return await analyze_bag_unified(
            bag_path=bag_path,
            console=console,
            required_level=required_level,
            is_async=True
        )
    
    def analyze_sync(
        self,
        bag_path: str,
        console: Optional[Console] = None,
        required_level: int = CacheLevel.STATISTICS
    ) -> UnifiedCache:
        """
        Synchronous bag analysis using unified cache
        
        Args:
            bag_path: Path to bag file
            console: Rich console for progress display
            required_level: Minimum cache level required
            
        Returns:
            UnifiedCache with analysis results
        """
        # For sync calls, we need to run the async function in a new event loop
        # or use the existing one if available
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete
                # So we create a task and wait for it
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        analyze_bag_unified(
                            bag_path=bag_path,
                            console=console,
                            required_level=required_level,
                            is_async=False
                        )
                    )
                    return future.result()
            else:
                # Loop exists but not running, use it
                return loop.run_until_complete(
                    analyze_bag_unified(
                        bag_path=bag_path,
                        console=console,
                        required_level=required_level,
                        is_async=False
                    )
                )
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(
                analyze_bag_unified(
                    bag_path=bag_path,
                    console=console,
                    required_level=required_level,
                    is_async=False
                )
            )
    
    def convert_to_legacy_format(self, unified_cache: UnifiedCache) -> Dict[str, Any]:
        """
        Convert UnifiedCache to legacy format for backward compatibility
        
        Args:
            unified_cache: UnifiedCache object
            
        Returns:
            Dictionary in legacy format
        """
        result = {}
        
        if unified_cache.metadata:
            result['topics'] = unified_cache.metadata.topics
            result['connections'] = unified_cache.metadata.connections
            result['time_range'] = unified_cache.metadata.time_range
            result['file_size'] = unified_cache.metadata.file_size
            result['topic_count'] = len(unified_cache.metadata.topics)
            result['start_time'] = unified_cache.metadata.time_range[0] if unified_cache.metadata.time_range else None
            result['end_time'] = unified_cache.metadata.time_range[1] if unified_cache.metadata.time_range else None
            result['original_bag_path'] = unified_cache.metadata.original_bag_path
        else:
            # Provide default values when metadata is not available
            result['topics'] = []
            result['connections'] = {}
            result['time_range'] = None
            result['file_size'] = 0
            result['topic_count'] = 0
            result['start_time'] = None
            result['end_time'] = None
            result['original_bag_path'] = ""
        
        if unified_cache.statistics:
            result['stats'] = {}  # Legacy format uses 'stats' not 'statistics'
            for topic, stats in unified_cache.statistics.items():
                result['stats'][topic] = {
                    'count': stats.count,
                    'size': stats.size,
                    'avg_size': stats.avg_size,
                    'frequency': stats.frequency
                }
            result['total_messages'] = unified_cache.total_messages
            result['total_data_size'] = unified_cache.total_data_size
            
            # Calculate duration from time range if available
            if unified_cache.metadata and unified_cache.metadata.time_range:
                start_time = unified_cache.metadata.time_range[0]
                end_time = unified_cache.metadata.time_range[1]
                if start_time and end_time:
                    start_sec = start_time[0] + start_time[1] * 1e-9
                    end_sec = end_time[0] + end_time[1] * 1e-9
                    result['duration'] = end_sec - start_sec
                else:
                    result['duration'] = unified_cache.duration or 0.0
            else:
                result['duration'] = unified_cache.duration or 0.0
        else:
            # Add empty stats for compatibility
            result['stats'] = {}
            result['total_messages'] = 0
            result['total_data_size'] = 0
            result['duration'] = 0.0
        
        if unified_cache.message_samples:
            result['message_samples'] = unified_cache.message_samples
        
        if unified_cache.field_analysis:
            result['field_analysis'] = unified_cache.field_analysis
        
        # Add cache metadata
        result['cache_level'] = unified_cache.cache_level
        result['analysis_timestamp'] = unified_cache.analysis_timestamp
        result['is_async_analysis'] = True
        result['is_lite_mode'] = unified_cache.cache_level <= 1
        
        return result
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache_manager.clear_cache()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        return self.cache_manager.get_cache_info()
    
    def enable_profiling(self):
        """Enable performance profiling"""
        self.cache_manager.enable_profiling()
    
    def disable_profiling(self):
        """Disable performance profiling"""
        self.cache_manager.disable_profiling()
    
    def print_profile_summary(self, console: Console):
        """Print performance profile summary"""
        self.cache_manager.print_profile_summary(console)


# Global unified analyzer instance
_global_unified_analyzer: Optional[UnifiedBagAnalyzer] = None


def get_unified_analyzer() -> UnifiedBagAnalyzer:
    """Get global unified analyzer instance"""
    global _global_unified_analyzer
    if _global_unified_analyzer is None:
        _global_unified_analyzer = UnifiedBagAnalyzer()
    return _global_unified_analyzer


# Convenience functions for easy migration
async def analyze_bag_async_unified(
    bag_path: str,
    console: Optional[Console] = None,
    required_level: int = CacheLevel.STATISTICS
) -> Dict[str, Any]:
    """
    Async bag analysis with unified cache (legacy format output)
    
    Returns results in legacy dictionary format for backward compatibility
    """
    analyzer = get_unified_analyzer()
    unified_cache = await analyzer.analyze_async(bag_path, console, required_level)
    return analyzer.convert_to_legacy_format(unified_cache)


def analyze_bag_sync_unified(
    bag_path: str,
    console: Optional[Console] = None,
    required_level: int = CacheLevel.STATISTICS
) -> Dict[str, Any]:
    """
    Sync bag analysis with unified cache (legacy format output)
    
    Returns results in legacy dictionary format for backward compatibility
    """
    analyzer = get_unified_analyzer()
    unified_cache = analyzer.analyze_sync(bag_path, console, required_level)
    return analyzer.convert_to_legacy_format(unified_cache) 