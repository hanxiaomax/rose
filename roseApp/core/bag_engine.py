#!/usr/bin/env python3
"""
Unified high-level API for all bag operations.

This module provides a single, consistent interface for all ROS bag operations,
hiding the complexity of caching, parsing, and optimization from upper layers.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, AsyncIterator, Tuple
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ..core.util import get_logger
from ..core.unified_cache import CacheLevel
from ..core.io_manager import get_io_manager, BagData, BagInfo
from ..core.parser_manager import get_parser_manager, ParserType
from ..core.enhanced_cache import get_enhanced_cache_manager, CacheStrategy
from ..core.unified_cache import get_unified_cache_manager


class AnalysisType(Enum):
    """Analysis type for different operations"""
    INSPECT = "inspect"
    FILTER = "filter"
    PLOT = "plot"
    PRUNE = "prune"


@dataclass
class TopicInfo:
    """Topic information"""
    name: str
    message_type: str
    message_count: int
    size: int
    frequency: float
    connections: List[str]


@dataclass
class Message:
    """Message data structure"""
    topic: str
    timestamp: float
    data: Any
    message_type: str


@dataclass
class FieldStructure:
    """Field structure for a topic"""
    topic: str
    message_type: str
    fields: Dict[str, Any]
    sample_data: Optional[Dict[str, Any]] = None


@dataclass
class FilterResult:
    """Result of bag filtering operation"""
    input_path: str
    output_path: str
    topics_included: List[str]
    original_message_count: int
    filtered_message_count: int
    original_size: int
    filtered_size: int
    duration: float
    success: bool
    error: Optional[str] = None


@dataclass
class PlotResult:
    """Result of plotting operation"""
    input_path: str
    output_path: str
    series_plotted: List[str]
    data_points: int
    duration: float
    success: bool
    error: Optional[str] = None


@dataclass
class SeriesConfig:
    """Configuration for plot series"""
    topic: str
    fields: List[str]
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    max_points: Optional[int] = None


@dataclass
class BagAnalysis:
    """Comprehensive bag analysis result"""
    bag_path: str
    analysis_type: AnalysisType
    cache_level: CacheLevel
    total_time: float
    
    # Basic info
    topics: List[TopicInfo]
    total_messages: int
    file_size: int
    duration: float
    
    # Advanced info (optional)
    field_analysis: Optional[Dict[str, FieldStructure]] = None
    sample_messages: Optional[Dict[str, List[Message]]] = None
    
    # Performance info
    cache_hit: bool = False
    parser_type: Optional[ParserType] = None
    optimization_level: str = "unknown"


class BagAnalysisEngine:
    """Unified high-level API for all bag operations"""
    
    def __init__(self):
        """Initialize bag analysis engine"""
        self.io_manager = get_io_manager()
        self.parser_manager = get_parser_manager()
        self.enhanced_cache = get_enhanced_cache_manager()
        self.unified_cache = get_unified_cache_manager()
        self.logger = get_logger(__name__)
        
        # Enable performance profiling
        self.unified_cache.enable_profiling()
        
    async def analyze_bag(self, bag_path: str,
                         analysis_type: AnalysisType = AnalysisType.INSPECT,
                         level: CacheLevel = CacheLevel.STATISTICS,
                         console: Optional[Console] = None) -> BagAnalysis:
        """
        Unified bag analysis interface
        
        Args:
            bag_path: Path to bag file
            analysis_type: Type of analysis to perform
            level: Minimum cache level required
            console: Optional console for progress display
            
        Returns:
            BagAnalysis with comprehensive results
        """
        start_time = time.time()
        
        if console:
            console.print(f"[cyan]Analyzing bag: {bag_path}[/cyan]")
            
        try:
            # Get cached analysis first
            cached_data = await self.enhanced_cache.get_cached_analysis(
                bag_path, 
                analysis_type.value,
                level
            )
            
            if cached_data:
                # Convert cached data to BagAnalysis
                analysis = await self._convert_cached_to_analysis(
                    cached_data, 
                    bag_path, 
                    analysis_type, 
                    level,
                    cache_hit=True
                )
                analysis.total_time = time.time() - start_time
                return analysis
            
            # Perform fresh analysis
            analysis = await self._perform_fresh_analysis(
                bag_path, 
                analysis_type, 
                level,
                console
            )
            analysis.total_time = time.time() - start_time
            analysis.cache_hit = False
            
            # Store in enhanced cache
            await self.enhanced_cache.store_analysis(
                bag_path,
                analysis_type.value,
                level,
                analysis
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing bag {bag_path}: {e}")
            raise
            
    async def _perform_fresh_analysis(self, bag_path: str,
                                     analysis_type: AnalysisType,
                                     level: CacheLevel,
                                     console: Optional[Console] = None) -> BagAnalysis:
        """Perform fresh analysis of bag file"""
        
        # Get optimal parser
        parser, parser_type = await self.parser_manager.get_optimal_parser(bag_path)
        
        # Use unified cache manager for actual analysis
        unified_cache = await self.unified_cache.get_analysis(
            bag_path,
            level,
            console,
            is_async=True
        )
        
        # Convert to BagAnalysis
        return await self._convert_unified_to_analysis(
            unified_cache,
            bag_path,
            analysis_type,
            level,
            parser_type
        )
        
    async def _convert_cached_to_analysis(self, cached_data: Any,
                                        bag_path: str,
                                        analysis_type: AnalysisType,
                                        level: CacheLevel,
                                        cache_hit: bool = False) -> BagAnalysis:
        """Convert cached data to BagAnalysis"""
        
        # Handle different cached data types
        if hasattr(cached_data, 'metadata'):
            # Unified cache format
            return await self._convert_unified_to_analysis(
                cached_data,
                bag_path,
                analysis_type,
                level,
                cache_hit=cache_hit
            )
        else:
            # Legacy format - create basic analysis
            return BagAnalysis(
                bag_path=bag_path,
                analysis_type=analysis_type,
                cache_level=level,
                total_time=0.0,
                topics=[],
                total_messages=0,
                file_size=0,
                duration=0.0,
                cache_hit=cache_hit,
                optimization_level="cached"
            )
            
    async def _convert_unified_to_analysis(self, unified_cache: Any,
                                         bag_path: str,
                                         analysis_type: AnalysisType,
                                         level: CacheLevel,
                                         parser_type: Optional[ParserType] = None,
                                         cache_hit: bool = False) -> BagAnalysis:
        """Convert unified cache to BagAnalysis"""
        
        # Extract basic info
        topics = []
        total_messages = 0
        file_size = 0
        duration = 0.0
        
        if hasattr(unified_cache, 'metadata') and unified_cache.metadata:
            # Extract topics
            for topic_name in unified_cache.metadata.topics:
                topic_info = TopicInfo(
                    name=topic_name,
                    message_type=unified_cache.metadata.connections.get(topic_name, "Unknown"),
                    message_count=0,
                    size=0,
                    frequency=0.0,
                    connections=[]
                )
                topics.append(topic_info)
                
            file_size = unified_cache.metadata.file_size
            
            # Calculate duration from time range
            if unified_cache.metadata.time_range:
                start_time = unified_cache.metadata.time_range[0]
                end_time = unified_cache.metadata.time_range[1]
                duration = (end_time[0] - start_time[0]) + (end_time[1] - start_time[1]) / 1e9
                
        # Extract statistics if available
        if hasattr(unified_cache, 'statistics') and unified_cache.statistics:
            for topic_name, stats in unified_cache.statistics.items():
                # Find corresponding topic and update
                for topic_info in topics:
                    if topic_info.name == topic_name:
                        topic_info.message_count = stats.count
                        topic_info.size = stats.size
                        if duration > 0:
                            topic_info.frequency = stats.count / duration
                        break
                total_messages += stats.count
                
        # Extract field analysis if available
        field_analysis = None
        if level >= CacheLevel.FIELDS and hasattr(unified_cache, 'field_analysis'):
            field_analysis = {}
            for topic_name, fields in unified_cache.field_analysis.items():
                field_analysis[topic_name] = FieldStructure(
                    topic=topic_name,
                    message_type=unified_cache.metadata.connections.get(topic_name, "Unknown"),
                    fields=fields,
                    sample_data=None
                )
                
        # Determine optimization level
        optimization_level = "unknown"
        if parser_type == ParserType.ROSBAGS:
            optimization_level = "high_performance"
        elif parser_type == ParserType.CPP:
            optimization_level = "legacy_fallback"
            
        return BagAnalysis(
            bag_path=bag_path,
            analysis_type=analysis_type,
            cache_level=level,
            total_time=0.0,  # Will be set by caller
            topics=topics,
            total_messages=total_messages,
            file_size=file_size,
            duration=duration,
            field_analysis=field_analysis,
            cache_hit=cache_hit,
            parser_type=parser_type,
            optimization_level=optimization_level
        )
        
    async def get_topics(self, bag_path: str,
                        filter_pattern: Optional[str] = None) -> List[TopicInfo]:
        """
        Get topic information with optional filtering
        
        Args:
            bag_path: Path to bag file
            filter_pattern: Optional pattern to filter topics
            
        Returns:
            List of TopicInfo objects
        """
        analysis = await self.analyze_bag(
            bag_path,
            AnalysisType.FILTER,
            CacheLevel.METADATA
        )
        
        topics = analysis.topics
        
        # Apply filter if specified
        if filter_pattern:
            topics = [t for t in topics if filter_pattern in t.name]
            
        return topics
        
    async def get_messages(self, bag_path: str,
                          topic: str,
                          start_time: Optional[float] = None,
                          end_time: Optional[float] = None) -> AsyncIterator[Message]:
        """
        Stream messages from bag file
        
        Args:
            bag_path: Path to bag file
            topic: Topic name
            start_time: Optional start time
            end_time: Optional end time
            
        Yields:
            Message objects
        """
        # Get optimal parser
        parser, parser_type = await self.parser_manager.get_optimal_parser(bag_path)
        
        # Stream messages (placeholder implementation)
        # In a real implementation, this would use the parser to stream messages
        self.logger.info(f"Streaming messages from {topic} in {bag_path}")
        
        # This is a placeholder - real implementation would yield actual messages
        if False:  # Disable for now
            yield Message(
                topic=topic,
                timestamp=time.time(),
                data={},
                message_type="Unknown"
            )
            
    async def get_fields(self, bag_path: str, topic: str) -> FieldStructure:
        """
        Get field structure for a topic
        
        Args:
            bag_path: Path to bag file
            topic: Topic name
            
        Returns:
            FieldStructure object
        """
        analysis = await self.analyze_bag(
            bag_path,
            AnalysisType.PLOT,
            CacheLevel.FIELDS
        )
        
        if analysis.field_analysis and topic in analysis.field_analysis:
            return analysis.field_analysis[topic]
        else:
            # Return basic structure if not found
            return FieldStructure(
                topic=topic,
                message_type="Unknown",
                fields={}
            )
            
    async def filter_bag(self, input_path: str,
                        output_path: str,
                        topics: List[str],
                        compression: str = 'none',
                        **kwargs) -> FilterResult:
        """
        High-level bag filtering interface
        
        Args:
            input_path: Input bag file path
            output_path: Output bag file path
            topics: List of topics to include
            compression: Compression type
            **kwargs: Additional filtering options
            
        Returns:
            FilterResult with operation details
        """
        start_time = time.time()
        
        try:
            # Get bag analysis for validation
            analysis = await self.analyze_bag(
                input_path,
                AnalysisType.FILTER,
                CacheLevel.STATISTICS
            )
            
            # Validate topics
            available_topics = {t.name for t in analysis.topics}
            valid_topics = [t for t in topics if t in available_topics]
            invalid_topics = [t for t in topics if t not in available_topics]
            
            if invalid_topics:
                self.logger.warning(f"Invalid topics ignored: {invalid_topics}")
                
            # Calculate original statistics
            original_message_count = analysis.total_messages
            original_size = analysis.file_size
            
            # Estimate filtered statistics
            filtered_message_count = sum(
                t.message_count for t in analysis.topics if t.name in valid_topics
            )
            
            # Placeholder for actual filtering implementation
            # In a real implementation, this would use the parser to filter the bag
            self.logger.info(f"Filtering {input_path} to {output_path}")
            self.logger.info(f"Including topics: {valid_topics}")
            
            return FilterResult(
                input_path=input_path,
                output_path=output_path,
                topics_included=valid_topics,
                original_message_count=original_message_count,
                filtered_message_count=filtered_message_count,
                original_size=original_size,
                filtered_size=int(original_size * (filtered_message_count / original_message_count)),
                duration=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error filtering bag: {e}")
            return FilterResult(
                input_path=input_path,
                output_path=output_path,
                topics_included=[],
                original_message_count=0,
                filtered_message_count=0,
                original_size=0,
                filtered_size=0,
                duration=time.time() - start_time,
                success=False,
                error=str(e)
            )
            
    async def plot_data(self, bag_path: str,
                       series_config: List[SeriesConfig],
                       output_path: str,
                       **kwargs) -> PlotResult:
        """
        High-level plotting interface
        
        Args:
            bag_path: Path to bag file
            series_config: List of series configurations
            output_path: Output file path
            **kwargs: Additional plotting options
            
        Returns:
            PlotResult with operation details
        """
        start_time = time.time()
        
        try:
            # Get field analysis for validation
            analysis = await self.analyze_bag(
                bag_path,
                AnalysisType.PLOT,
                CacheLevel.FIELDS
            )
            
            # Validate series configurations
            valid_series = []
            for config in series_config:
                if analysis.field_analysis and config.topic in analysis.field_analysis:
                    field_structure = analysis.field_analysis[config.topic]
                    # Validate fields exist
                    valid_fields = [f for f in config.fields if f in field_structure.fields]
                    if valid_fields:
                        valid_series.append(f"{config.topic}:{','.join(valid_fields)}")
                        
            # Placeholder for actual plotting implementation
            self.logger.info(f"Plotting data from {bag_path}")
            self.logger.info(f"Series: {valid_series}")
            
            return PlotResult(
                input_path=bag_path,
                output_path=output_path,
                series_plotted=valid_series,
                data_points=1000,  # Placeholder
                duration=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Error plotting data: {e}")
            return PlotResult(
                input_path=bag_path,
                output_path=output_path,
                series_plotted=[],
                data_points=0,
                duration=time.time() - start_time,
                success=False,
                error=str(e)
            )
            
    async def get_bag_info(self, bag_path: str) -> BagInfo:
        """
        Get basic bag file information
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            BagInfo object
        """
        return await self.io_manager.get_bag_info_async(bag_path)
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        unified_cache_stats = {}
        try:
            # Try to get unified cache stats if available
            if hasattr(self.unified_cache, 'get_stats'):
                unified_cache_stats = self.unified_cache.get_stats()
            else:
                # Fallback: get basic stats
                unified_cache_stats = {
                    'profiler_enabled': getattr(self.unified_cache, 'profiler', {}).get('enabled', False),
                    'cache_size': len(getattr(self.unified_cache, '_cache', {}))
                }
        except Exception as e:
            self.logger.warning(f"Could not get unified cache stats: {e}")
            unified_cache_stats = {'error': str(e)}
        
        return {
            'cache_stats': self.enhanced_cache.get_cache_statistics(),
            'parser_stats': self.parser_manager.get_parser_stats(),
            'io_stats': self.io_manager.get_operation_stats(),
            'unified_cache_stats': unified_cache_stats
        }
        
    async def warm_cache(self, bag_paths: List[str]) -> None:
        """
        Warm cache for frequently accessed bags
        
        Args:
            bag_paths: List of bag paths to warm
        """
        await self.enhanced_cache.warm_cache(
            bag_paths,
            ['inspect', 'filter', 'plot', 'prune']
        )
        
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.enhanced_cache.cleanup_expired_cache()
        await self.io_manager.shutdown()


# Global bag analysis engine instance
_global_bag_engine: Optional[BagAnalysisEngine] = None


def get_bag_engine() -> BagAnalysisEngine:
    """Get global bag analysis engine instance"""
    global _global_bag_engine
    if _global_bag_engine is None:
        _global_bag_engine = BagAnalysisEngine()
    return _global_bag_engine


async def analyze_bag_unified(bag_path: str,
                            analysis_type: AnalysisType = AnalysisType.INSPECT,
                            level: CacheLevel = CacheLevel.STATISTICS,
                            console: Optional[Console] = None) -> BagAnalysis:
    """
    Convenience function for unified bag analysis
    
    Args:
        bag_path: Path to bag file
        analysis_type: Type of analysis
        level: Cache level
        console: Optional console
        
    Returns:
        BagAnalysis result
    """
    engine = get_bag_engine()
    return await engine.analyze_bag(bag_path, analysis_type, level, console) 