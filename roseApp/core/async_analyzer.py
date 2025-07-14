#!/usr/bin/env python3
"""
Asynchronous ROS bag analyzer with intelligent caching for performance optimization.
Implements space-for-time strategy by caching comprehensive analysis results.
"""

import asyncio
import time
import pickle
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .parser import create_parser, ParserType
from .util import get_logger

logger = get_logger()


@dataclass
class CacheLevel:
    """Different levels of cache data"""
    METADATA = 1      # Basic bag metadata (topics, connections, time_range)
    STATISTICS = 2    # Message counts and sizes  
    MESSAGES = 3      # Sample messages for field analysis
    FIELDS = 4        # Complete field analysis


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
class ComprehensiveCache:
    """Complete cache structure with all levels"""
    # Level 1: Metadata
    metadata: BagMetadata
    
    # Level 2: Statistics  
    statistics: Dict[str, TopicStatistics]
    total_messages: int
    total_data_size: int
    duration: Optional[float]
    
    # Level 3: Message samples (limited to save space)
    message_samples: Dict[str, List[MessageSample]]  # topic -> samples
    
    # Level 4: Field analysis results
    field_analysis: Dict[str, FieldAnalysis]  # topic -> analysis
    
    # Cache metadata
    cache_level: int
    analysis_timestamp: float
    is_async_complete: bool = False


class AsyncBagAnalyzer:
    """Asynchronous bag analyzer with intelligent caching"""
    
    def __init__(self, max_samples_per_topic: int = 10, max_workers: int = 4):
        self.max_samples_per_topic = max_samples_per_topic
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._analysis_cache: Dict[str, ComprehensiveCache] = {}
        self._analysis_locks: Dict[str, threading.Lock] = {}
        
    def _get_cache_key(self, bag_path: str) -> str:
        """Generate cache key for bag file"""
        import os
        stat = os.stat(bag_path)
        cache_key = f"{bag_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    async def analyze_bag_comprehensive(
        self, 
        bag_path: str, 
        console: Optional[Console] = None,
        required_level: int = CacheLevel.STATISTICS,
        background_full_analysis: bool = True
    ) -> ComprehensiveCache:
        """
        Comprehensive bag analysis with intelligent caching
        
        Args:
            bag_path: Path to bag file
            console: Rich console for progress display
            required_level: Minimum cache level required
            background_full_analysis: Whether to start full analysis in background
            
        Returns:
            ComprehensiveCache with at least the required level of data
        """
        cache_key = self._get_cache_key(bag_path)
        
        # Check if we have sufficient cached data
        if cache_key in self._analysis_cache:
            cached = self._analysis_cache[cache_key]
            if cached.cache_level >= required_level:
                if console:
                    console.print("[dim]Using cached analysis results[/dim]")
                return cached
        
        # Ensure thread safety for concurrent analysis
        if cache_key not in self._analysis_locks:
            self._analysis_locks[cache_key] = threading.Lock()
        
        with self._analysis_locks[cache_key]:
            # Double-check after acquiring lock
            if cache_key in self._analysis_cache:
                cached = self._analysis_cache[cache_key]
                if cached.cache_level >= required_level:
                    return cached
            
            # Perform analysis
            cache_data = await self._perform_comprehensive_analysis(
                bag_path, console, required_level
            )
            
            # Store in cache
            self._analysis_cache[cache_key] = cache_data
            
            # Start background full analysis if requested
            if background_full_analysis and required_level < CacheLevel.FIELDS:
                asyncio.create_task(
                    self._background_full_analysis(bag_path, cache_key, console)
                )
            
            return cache_data
    
    async def _perform_comprehensive_analysis(
        self, 
        bag_path: str, 
        console: Optional[Console],
        target_level: int
    ) -> ComprehensiveCache:
        """Perform comprehensive analysis up to target level"""
        
        if console:
            console.print("[cyan]Performing comprehensive bag analysis...[/cyan]")
        
        # Step 1: Always get metadata (Level 1)
        metadata = await self._analyze_metadata(bag_path)
        
        if target_level == CacheLevel.METADATA:
            return ComprehensiveCache(
                metadata=metadata,
                statistics={},
                total_messages=0,
                total_data_size=0,
                duration=None,
                message_samples={},
                field_analysis={},
                cache_level=CacheLevel.METADATA,
                analysis_timestamp=time.time()
            )
        
        # Step 2: Get statistics (Level 2) - This is where we do the main optimization
        stats_data = await self._analyze_statistics_and_samples(
            bag_path, metadata, console, target_level
        )
        
        return stats_data
    
    async def _analyze_metadata(self, bag_path: str) -> BagMetadata:
        """Analyze basic metadata (fast operation)"""
        
        def _load_metadata():
            parser = create_parser(ParserType.ROSBAGS)
            topics, connections, time_range = parser.load_bag(bag_path)
            file_size = Path(bag_path).stat().st_size
            
            return BagMetadata(
                topics=topics,
                connections=connections,
                time_range=time_range,
                file_size=file_size,
                original_bag_path=str(Path(bag_path).absolute()),
                cache_timestamp=time.time()
            )
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _load_metadata)
    
    async def _analyze_statistics_and_samples(
        self, 
        bag_path: str, 
        metadata: BagMetadata,
        console: Optional[Console],
        target_level: int
    ) -> ComprehensiveCache:
        """Analyze statistics and collect message samples in single pass"""
        
        def _comprehensive_analysis():
            from rosbags.highlevel import AnyReader
            from rosbags.serde import deserialize_cdr
            from rosbags.typesys import get_types_from_msg, register_types
            
            statistics = {}
            message_samples = {}
            total_messages = 0
            total_data_size = 0
            
            # Initialize sample storage
            for topic in metadata.topics:
                message_samples[topic] = []
            
            try:
                with AnyReader([Path(bag_path)]) as reader:
                    # Process each topic in a single pass
                    for connection in reader.connections:
                        topic = connection.topic
                        count = 0
                        total_size = 0
                        samples_collected = 0
                        
                        # Collect both statistics and samples in one iteration
                        for (connection_inner, timestamp, rawdata) in reader.messages([connection]):
                            count += 1
                            size = len(rawdata)
                            total_size += size
                            
                            # Collect samples for field analysis (space-for-time optimization)
                            if (target_level >= CacheLevel.MESSAGES and 
                                samples_collected < self.max_samples_per_topic):
                                
                                # Convert timestamp to tuple format
                                seconds = timestamp // 1_000_000_000
                                nanoseconds = timestamp % 1_000_000_000
                                time_tuple = (int(seconds), int(nanoseconds))
                                
                                sample = MessageSample(
                                    timestamp=time_tuple,
                                    raw_data=rawdata,
                                    topic=topic,
                                    msg_type=connection.msgtype
                                )
                                message_samples[topic].append(sample)
                                samples_collected += 1
                        
                        # Calculate statistics
                        avg_size = total_size // count if count > 0 else 0
                        
                        statistics[topic] = TopicStatistics(
                            count=count,
                            size=total_size,
                            avg_size=avg_size
                        )
                        
                        total_messages += count
                        total_data_size += total_size
                
                # Calculate frequencies
                duration = None
                if metadata.time_range and len(metadata.time_range) == 2:
                    start_time, end_time = metadata.time_range
                    start_seconds = start_time[0] + start_time[1] / 1_000_000_000
                    end_seconds = end_time[0] + end_time[1] / 1_000_000_000
                    duration = end_seconds - start_seconds
                    
                    if duration > 0:
                        for topic, stats in statistics.items():
                            stats.frequency = stats.count / duration
                
                return statistics, message_samples, total_messages, total_data_size, duration
                
            except Exception as e:
                logger.error(f"Error in comprehensive analysis: {e}")
                raise
        
        # Show progress for the comprehensive analysis
        if console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Analyzing bag comprehensively...", total=100)
                
                # Run analysis in thread pool
                loop = asyncio.get_event_loop()
                stats, samples, total_msgs, total_size, duration = await loop.run_in_executor(
                    self.executor, _comprehensive_analysis
                )
                
                progress.update(task, advance=100, description="Analysis complete")
        else:
            loop = asyncio.get_event_loop()
            stats, samples, total_msgs, total_size, duration = await loop.run_in_executor(
                self.executor, _comprehensive_analysis
            )
        
        # Field analysis if requested
        field_analysis = {}
        if target_level >= CacheLevel.FIELDS:
            field_analysis = await self._analyze_fields_from_samples(samples, console)
        
        cache_level = min(target_level, CacheLevel.FIELDS)
        
        return ComprehensiveCache(
            metadata=metadata,
            statistics=stats,
            total_messages=total_msgs,
            total_data_size=total_size,
            duration=duration,
            message_samples=samples if target_level >= CacheLevel.MESSAGES else {},
            field_analysis=field_analysis,
            cache_level=cache_level,
            analysis_timestamp=time.time()
        )
    
    async def _analyze_fields_from_samples(
        self, 
        message_samples: Dict[str, List[MessageSample]],
        console: Optional[Console]
    ) -> Dict[str, FieldAnalysis]:
        """Analyze field structures from cached message samples"""
        
        def _analyze_topic_fields(topic: str, samples: List[MessageSample]) -> FieldAnalysis:
            from rosbags.highlevel import AnyReader
            
            if not samples:
                return FieldAnalysis(
                    fields={},
                    message_type="Unknown",
                    samples_analyzed=0,
                    max_depth=3
                )
            
            # Use first sample's message type
            msg_type = samples[0].msg_type
            fields = {}
            
            # Analyze samples using the cached raw data
            try:
                # Create a temporary reader context for deserialization
                # We'll deserialize the cached raw data
                for i, sample in enumerate(samples):
                    if i >= 5:  # Limit to first 5 samples for performance
                        break
                    
                    try:
                        # Here we would need to deserialize the raw data
                        # For now, we'll create a basic structure
                        # This would need to be improved with actual deserialization
                        
                        # Mock field analysis - in real implementation,
                        # we would deserialize the raw_data and extract fields
                        fields[f"field_{i}"] = {
                            "type": "analyzed_from_cache",
                            "cached_at": sample.timestamp
                        }
                    except Exception as e:
                        logger.warning(f"Failed to analyze sample {i} for topic {topic}: {e}")
                        continue
                
                return FieldAnalysis(
                    fields=fields,
                    message_type=msg_type,
                    samples_analyzed=min(len(samples), 5),
                    max_depth=3
                )
                
            except Exception as e:
                logger.error(f"Error analyzing fields for topic {topic}: {e}")
                return FieldAnalysis(
                    fields={},
                    message_type=msg_type,
                    samples_analyzed=0,
                    max_depth=3
                )
        
        field_analysis = {}
        
        if console:
            console.print("[cyan]Analyzing field structures from cached samples...[/cyan]")
        
        # Analyze fields for each topic that has samples
        for topic, samples in message_samples.items():
            if samples:
                loop = asyncio.get_event_loop()
                analysis = await loop.run_in_executor(
                    self.executor, _analyze_topic_fields, topic, samples
                )
                field_analysis[topic] = analysis
        
        return field_analysis
    
    async def _background_full_analysis(
        self, 
        bag_path: str, 
        cache_key: str,
        console: Optional[Console]
    ):
        """Perform full analysis in background to warm up cache"""
        try:
            if console:
                console.print("[dim]Starting background comprehensive analysis...[/dim]")
            
            # Perform full analysis
            full_cache = await self._perform_comprehensive_analysis(
                bag_path, None, CacheLevel.FIELDS
            )
            
            # Update cache
            full_cache.is_async_complete = True
            self._analysis_cache[cache_key] = full_cache
            
            if console:
                console.print("[dim]Background analysis complete - cache warmed up[/dim]")
                
        except Exception as e:
            logger.error(f"Background analysis failed: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about current cache state"""
        return {
            "cached_bags": len(self._analysis_cache),
            "cache_details": {
                key: {
                    "bag_path": cache.metadata.original_bag_path,
                    "cache_level": cache.cache_level,
                    "is_complete": cache.is_async_complete,
                    "topics": len(cache.metadata.topics),
                    "total_messages": cache.total_messages
                }
                for key, cache in self._analysis_cache.items()
            }
        }
    
    def clear_cache(self):
        """Clear all cached analysis data"""
        self._analysis_cache.clear()
        self._analysis_locks.clear()


# Global async analyzer instance
_global_analyzer: Optional[AsyncBagAnalyzer] = None


def get_async_analyzer() -> AsyncBagAnalyzer:
    """Get global async analyzer instance"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = AsyncBagAnalyzer()
    return _global_analyzer


async def analyze_bag_async(
    bag_path: str,
    console: Optional[Console] = None,
    required_level: int = CacheLevel.STATISTICS,
    background_full_analysis: bool = True
) -> ComprehensiveCache:
    """
    Main async function to analyze bag with intelligent caching
    
    This is the primary interface for async bag analysis with performance optimization.
    """
    analyzer = get_async_analyzer()
    return await analyzer.analyze_bag_comprehensive(
        bag_path, console, required_level, background_full_analysis
    ) 