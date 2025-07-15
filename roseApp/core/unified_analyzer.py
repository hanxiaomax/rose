#!/usr/bin/env python3
"""
Unified Analyzer Interface

This module provides a unified interface for both synchronous and asynchronous
bag analysis, using the shared unified cache system for consistent performance.
"""

import time
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from roseApp.core.unified_cache import *
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.message_type_analyzer import get_message_type_analyzer, TypeDefinition
from roseApp.core.util import get_logger
from rich.console import Console

logger = get_logger("UnifiedAnalyzer")


class UnifiedBagAnalyzer:
    """
    Unified bag analyzer that provides both sync and async interfaces
    with optimized field analysis using static type definitions.
    """
    
    def __init__(self):
        self.cache_manager = UnifiedCacheManager()
        self.type_analyzer = get_message_type_analyzer()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def analyze_async(
        self, 
        bag_path: str, 
        required_level: int = CacheLevel.STATISTICS,
        console: Optional[Console] = None
    ) -> UnifiedCache:
        """Async interface for bag analysis"""
        return await self.cache_manager.get_analysis(
            bag_path=bag_path,
            required_level=required_level,
            console=console,
            is_async=True
        )
    
    def analyze_sync(
        self, 
        bag_path: str, 
        required_level: int = CacheLevel.STATISTICS,
        console: Optional[Console] = None
    ) -> UnifiedCache:
        """Sync interface for bag analysis"""
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an event loop, we need to use a different approach
            # Run the async method in a thread pool to avoid asyncio.run() in running loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.cache_manager.get_analysis(
                        bag_path=bag_path,
                        required_level=required_level,
                        console=console,
                        is_async=False
                    )
                )
                return future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            return asyncio.run(self.cache_manager.get_analysis(
                bag_path=bag_path,
                required_level=required_level,
                console=console,
                is_async=False
            ))
    
    def _analyze_fields_optimized(self, bag_path: str, topics: List[str], connections: Dict[str, str]) -> Dict[str, Any]:
        """
        Optimized field analysis using static type definitions.
        This is the main performance improvement - avoid message deserialization.
        """
        start_time = time.time()
        field_analysis = {}
        
        # Performance counters
        type_system_hits = 0
        sample_fallbacks = 0
        
        for topic in topics:
            if topic not in connections:
                continue
                
            msg_type = connections[topic]
            
            try:
                # Try optimized type system analysis first
                type_def = self.type_analyzer.analyze_message_type(msg_type)
                
                if type_def.source == 'type_system':
                    # Success! We got the field structure without deserialization
                    field_analysis[topic] = self.type_analyzer.convert_to_legacy_format(type_def)
                    type_system_hits += 1
                    logger.debug(f"Type system analysis successful for {topic} ({msg_type})")
                    
                else:
                    # Fallback to sample analysis
                    field_analysis[topic] = self._analyze_fields_from_samples(bag_path, topic, msg_type)
                    sample_fallbacks += 1
                    logger.debug(f"Sample analysis fallback for {topic} ({msg_type})")
                    
            except Exception as e:
                logger.warning(f"Field analysis failed for {topic}: {e}")
                field_analysis[topic] = {
                    'fields': {},
                    'message_type': msg_type,
                    'samples_analyzed': 0,
                    'analysis_source': 'error',
                    'error': str(e)
                }
        
        analysis_time = time.time() - start_time
        
        # Log performance metrics
        total_topics = len(topics)
        if total_topics > 0:
            logger.info(f"Field analysis completed in {analysis_time:.3f}s for {total_topics} topics")
            logger.info(f"Type system hits: {type_system_hits}/{total_topics} ({type_system_hits/total_topics*100:.1f}%)")
            logger.info(f"Sample fallbacks: {sample_fallbacks}/{total_topics} ({sample_fallbacks/total_topics*100:.1f}%)")
        
        return field_analysis
    
    def _analyze_fields_from_samples(self, bag_path: str, topic: str, msg_type: str) -> Dict[str, Any]:
        """
        Fallback method: analyze fields from message samples.
        Used when type system analysis fails.
        """
        parser = create_parser(ParserType.ROSBAGS)
        
        try:
            # Read a few messages from the topic to analyze structure
            messages = []
            message_count = 0
            max_samples = 3  # Reduced from 5 for better performance
            
            for timestamp, msg_data in parser.read_messages(bag_path, [topic]):
                if message_count >= max_samples:
                    break
                messages.append(msg_data)
                message_count += 1
            
            if messages:
                # Analyze the structure of the first message
                fields = self._extract_message_fields(messages[0])
                return {
                    'fields': fields,
                    'message_type': msg_type,
                    'samples_analyzed': len(messages),
                    'analysis_source': 'sample_analysis'
                }
            else:
                return {
                    'fields': {},
                    'message_type': msg_type,
                    'samples_analyzed': 0,
                    'analysis_source': 'no_messages'
                }
                
        except Exception as e:
            logger.warning(f"Sample analysis failed for {topic}: {e}")
            return {
                'fields': {},
                'message_type': msg_type,
                'samples_analyzed': 0,
                'analysis_source': 'error',
                'error': str(e)
            }
    
    def _extract_message_fields(self, msg_data: Any, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Extract field information from a message recursively (legacy method)"""
        fields = {}
        
        if current_depth >= max_depth:
            return {'...': f'(max depth {max_depth} reached)'}
        
        if hasattr(msg_data, '__dict__'):
            # ROS message object
            for attr_name in dir(msg_data):
                if not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(msg_data, attr_name)
                        if not callable(attr_value):
                            field_name = f"{prefix}.{attr_name}" if prefix else attr_name
                            field_info = self._get_field_info(attr_value, field_name, max_depth, current_depth + 1)
                            fields[attr_name] = field_info
                    except Exception:
                        continue
        elif isinstance(msg_data, dict):
            # Dictionary
            for key, value in msg_data.items():
                field_name = f"{prefix}.{key}" if prefix else key
                field_info = self._get_field_info(value, field_name, max_depth, current_depth + 1)
                fields[key] = field_info
        else:
            # Primitive type
            fields['value'] = self._get_field_info(msg_data, prefix, max_depth, current_depth)
        
        return fields
    
    def _get_field_info(self, value: Any, field_name: str, max_depth: int, current_depth: int) -> Dict[str, Any]:
        """Get information about a specific field (legacy method)"""
        field_info = {
            'type': type(value).__name__,
            'full_path': field_name
        }
        
        if isinstance(value, (int, float, bool)):
            field_info['value'] = value
        elif isinstance(value, str):
            field_info['value'] = f'"{value}"' if len(value) <= 50 else f'"{value[:47]}..."'
        elif isinstance(value, (list, tuple)):
            field_info['length'] = len(value)
            if len(value) > 0 and current_depth < max_depth:
                field_info['element_type'] = type(value[0]).__name__
                if hasattr(value[0], '__dict__') or isinstance(value[0], dict):
                    field_info['element_structure'] = self._extract_message_fields(value[0], f"{field_name}[0]", max_depth, current_depth + 1)
        elif hasattr(value, '__dict__') or isinstance(value, dict):
            if current_depth < max_depth:
                field_info['fields'] = self._extract_message_fields(value, field_name, max_depth, current_depth + 1)
        
        return field_info
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for the analyzer"""
        return {
            'type_analyzer_stats': self.type_analyzer.get_analysis_stats(),
            'cache_stats': self.cache_manager.get_cache_stats()
        }
    
    def clear_all_caches(self):
        """Clear all caches"""
        self.cache_manager.clear_cache()
        self.type_analyzer.clear_cache()
        logger.info("All caches cleared")
    
    def convert_to_legacy_format(self, cache: UnifiedCache) -> Dict[str, Any]:
        """Convert unified cache to legacy format for backward compatibility"""
        
        # Create stats dictionary in the expected format
        stats_dict = {}
        if cache.statistics:
            for topic, topic_stats in cache.statistics.items():
                stats_dict[topic] = {
                    'count': topic_stats.count,
                    'size': topic_stats.size,
                    'avg_size': topic_stats.avg_size
                }
        
        # Calculate duration
        duration = None
        if cache.metadata and cache.metadata.time_range:
            start_time = cache.metadata.time_range[0]
            end_time = cache.metadata.time_range[1]
            if start_time and end_time:
                start_seconds = start_time[0] + start_time[1] / 1_000_000_000
                end_seconds = end_time[0] + end_time[1] / 1_000_000_000
                duration = end_seconds - start_seconds
        
        # Build the result in the expected legacy format
        result = {
            'topics': cache.metadata.topics if cache.metadata else [],
            'connections': cache.metadata.connections if cache.metadata else {},
            'stats': stats_dict,
            'file_size': cache.metadata.file_size if cache.metadata else 0,
            'total_messages': cache.total_messages,
            'total_data_size': cache.total_data_size,
            'duration': duration,
            'start_time': cache.metadata.time_range[0] if cache.metadata else (0, 0),
            'end_time': cache.metadata.time_range[1] if cache.metadata else (0, 0),
            'topic_count': len(cache.metadata.topics) if cache.metadata else 0,
            'is_lite_mode': cache.cache_level < CacheLevel.FIELDS,
            'original_bag_path': cache.metadata.original_bag_path if cache.metadata else "",
            'analysis_time': 0.0,  # This would be set by the caller
            'is_async_analysis': False,  # This would be set by the caller
            'cache_level': cache.cache_level
        }
        
        # Add field analysis if available
        if cache.field_analysis and cache.cache_level >= CacheLevel.FIELDS:
            result['field_analysis'] = cache.field_analysis
        
        return result


# Global instance
_global_analyzer: Optional[UnifiedBagAnalyzer] = None


def get_unified_analyzer() -> UnifiedBagAnalyzer:
    """Get global unified analyzer instance"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = UnifiedBagAnalyzer()
    return _global_analyzer


async def analyze_bag_async(
    bag_path: str, 
    required_level: int = CacheLevel.STATISTICS,
    console: Optional[Console] = None
) -> UnifiedCache:
    """Convenience function for async bag analysis"""
    return await get_unified_analyzer().analyze_async(bag_path, required_level, console)


def analyze_bag_sync(
    bag_path: str, 
    required_level: int = CacheLevel.STATISTICS,
    console: Optional[Console] = None
) -> UnifiedCache:
    """Convenience function for sync bag analysis"""
    return get_unified_analyzer().analyze_sync(bag_path, required_level, console) 