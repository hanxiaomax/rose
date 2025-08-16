"""
Unified Bag Data Interface

This module provides a clean, modern interface for accessing ROS bag data
using the new topic-based DataFrame storage system.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
import time

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from .model import ComprehensiveBagInfo, AnalysisLevel
from .parser import BagParser

_logger = logging.getLogger(__name__)


class BagData:
    """
    Modern, clean interface for ROS bag data access
    
    This class provides an intuitive API for working with ROS bag data
    using the new topic-based storage system.
    
    Example usage:
        bag = BagData.load("path/to/bag.bag")
        
        # Access topic data
        radar_data = bag.get_topic('/radar/points')
        gps_data = bag.get_topic('/gps/fix')
        
        # Query with filters
        recent_radar = bag.query('/radar/points', time_start=123.0, time_end=456.0)
        
        # Export data
        bag.export_topic('/radar/points', 'radar_data.csv')
        bag.export_all_topics('output_dir/')
    """
    
    def __init__(self, bag_info: ComprehensiveBagInfo):
        """Initialize BagData with ComprehensiveBagInfo"""
        self.bag_info = bag_info
        self._file_path = bag_info.file_path
        
    @classmethod
    async def load_async(cls, bag_path: Union[str, Path], 
                        use_cache: bool = True) -> 'BagData':
        """
        Asynchronously load a ROS bag file
        
        Args:
            bag_path: Path to the bag file
            use_cache: Whether to use caching (default: True)
            
        Returns:
            BagData instance
        """
        parser = BagParser()
        bag_info, _ = await parser.load_bag_async(str(bag_path), build_index=True)
        return cls(bag_info)
    
    @classmethod
    def load(cls, bag_path: Union[str, Path], use_cache: bool = True) -> 'BagData':
        """
        Synchronously load a ROS bag file
        
        Args:
            bag_path: Path to the bag file
            use_cache: Whether to use caching (default: True)
            
        Returns:
            BagData instance
        """
        import asyncio
        return asyncio.run(cls.load_async(bag_path, use_cache))
    
    # ===== BASIC PROPERTIES =====
    
    @property
    def file_path(self) -> str:
        """Get the bag file path"""
        return self._file_path
    
    @property
    def topics(self) -> List[str]:
        """Get list of all topics in the bag"""
        return self.bag_info.get_all_topics()
    
    @property
    def message_types(self) -> Dict[str, List[str]]:
        """Get mapping of message types to topics"""
        return self.bag_info.topics_by_type.copy()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get comprehensive bag statistics"""
        return self.bag_info.get_dataframe_stats()
    
    @property
    def time_range(self) -> Optional[Tuple[float, float]]:
        """Get time range of the bag (start_time, end_time)"""
        if hasattr(self.bag_info, 'time_range') and self.bag_info.time_range:
            if hasattr(self.bag_info.time_range, 'start_time'):
                return (self.bag_info.time_range.start_time, self.bag_info.time_range.end_time)
            elif isinstance(self.bag_info.time_range, (tuple, list)) and len(self.bag_info.time_range) == 2:
                return tuple(self.bag_info.time_range)
        return None
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration of the bag in seconds"""
        return self.bag_info.duration_seconds
    
    # ===== DATA ACCESS METHODS =====
    
    def get_topic(self, topic_name: str) -> Optional[Any]:
        """
        Get DataFrame for a specific topic
        
        Args:
            topic_name: Name of the topic (e.g., '/radar/points')
            
        Returns:
            pandas DataFrame or None if topic not found
        """
        return self.bag_info.get_topic_data(topic_name)
    
    def get_topics_by_type(self, message_type: str) -> List[str]:
        """
        Get all topics with a specific message type
        
        Args:
            message_type: ROS message type (e.g., 'sensor_msgs/msg/PointCloud2')
            
        Returns:
            List of topic names
        """
        return self.bag_info.get_topics_by_type(message_type)
    
    def query(self, topic_name: str, 
             time_start: Optional[float] = None,
             time_end: Optional[float] = None,
             **filters) -> Optional[Any]:
        """
        Query a topic with optional filtering
        
        Args:
            topic_name: Name of the topic
            time_start: Start time in seconds (optional)
            time_end: End time in seconds (optional)
            **filters: Additional column filters
            
        Returns:
            Filtered pandas DataFrame or None
            
        Example:
            # Time-based query
            recent_data = bag.query('/radar/points', time_start=123.0, time_end=456.0)
            
            # Column-based query
            specific_data = bag.query('/gps/fix', status=4)
        """
        return self.bag_info.query_topic(topic_name, time_start, time_end, **filters)
    
    def query_all(self, time_start: Optional[float] = None,
                  time_end: Optional[float] = None,
                  topic_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Query multiple topics with the same criteria
        
        Args:
            time_start: Start time in seconds (optional)
            time_end: End time in seconds (optional)
            topic_filter: List of topics to query (optional, defaults to all)
            
        Returns:
            Dictionary mapping topic names to filtered DataFrames
        """
        results = {}
        topics_to_query = topic_filter or self.topics
        
        for topic in topics_to_query:
            result = self.query(topic, time_start, time_end)
            if result is not None and len(result) > 0:
                results[topic] = result
        
        return results
    
    def get_timeline(self, topics: Optional[List[str]] = None) -> Optional[Any]:
        """
        Create a unified timeline DataFrame
        
        Args:
            topics: List of topics to include (optional, defaults to all)
            
        Returns:
            pandas DataFrame with timeline data
        """
        return self.bag_info.create_unified_timeline(topics)
    
    # ===== ANALYSIS METHODS =====
    
    def apply_to_topic(self, topic_name: str, func: Callable, *args, **kwargs) -> Any:
        """
        Apply a function to a specific topic's DataFrame
        
        Args:
            topic_name: Name of the topic
            func: Function to apply
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function
            
        Example:
            # Get basic statistics
            stats = bag.apply_to_topic('/radar/points', lambda df: df.describe())
            
            # Count messages
            count = bag.apply_to_topic('/gps/fix', len)
        """
        df = self.get_topic(topic_name)
        if df is not None:
            return func(df, *args, **kwargs)
        return None
    
    def apply_to_all(self, func: Callable, topic_filter: Optional[List[str]] = None,
                     *args, **kwargs) -> Dict[str, Any]:
        """
        Apply a function to all (or filtered) topics
        
        Args:
            func: Function to apply
            topic_filter: List of topics to process (optional)
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary mapping topic names to function results
        """
        results = {}
        topics_to_process = topic_filter or self.topics
        
        for topic_name in topics_to_process:
            result = self.apply_to_topic(topic_name, func, *args, **kwargs)
            if result is not None:
                results[topic_name] = result
        
        return results
    
    def get_message_counts(self) -> Dict[str, int]:
        """Get message count for each topic"""
        return self.apply_to_all(len)
    
    def get_topic_info(self, topic_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific topic
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            Dictionary with topic information
        """
        df = self.get_topic(topic_name)
        if df is None:
            return {}
        
        # Find message type
        message_type = 'unknown'
        for msg_type, topics in self.message_types.items():
            if topic_name in topics:
                message_type = msg_type
                break
        
        info = {
            'topic_name': topic_name,
            'message_type': message_type,
            'message_count': len(df),
            'columns': list(df.columns),
            'column_count': len(df.columns),
            'memory_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
            'sparsity': 0.0  # No sparsity in topic-based storage!
        }
        
        # Add time information if available
        if 'timestamp_sec' in df.columns:
            info.update({
                'time_start': df['timestamp_sec'].min(),
                'time_end': df['timestamp_sec'].max(),
                'duration': df['timestamp_sec'].max() - df['timestamp_sec'].min(),
                'frequency_hz': len(df) / (df['timestamp_sec'].max() - df['timestamp_sec'].min()) if len(df) > 1 else 0
            })
        
        return info
    
    # ===== EXPORT METHODS =====
    
    def export_topic(self, topic_name: str, output_path: Union[str, Path]) -> bool:
        """
        Export a specific topic to CSV
        
        Args:
            topic_name: Name of the topic
            output_path: Path for the output CSV file
            
        Returns:
            True if successful, False otherwise
        """
        return self.bag_info.export_topic_csv(topic_name, Path(output_path))
    
    def export_all_topics(self, output_dir: Union[str, Path],
                          topic_filter: Optional[List[str]] = None) -> Dict[str, Path]:
        """
        Export all topics to separate CSV files
        
        Args:
            output_dir: Directory for output files
            topic_filter: List of topics to export (optional)
            
        Returns:
            Dictionary mapping topic names to output file paths
        """
        return self.bag_info.export_all_topics_csv(Path(output_dir), topic_filter)
    
    def export_timeline(self, output_path: Union[str, Path],
                       topics: Optional[List[str]] = None) -> bool:
        """
        Export unified timeline to CSV
        
        Args:
            output_path: Path for the output CSV file
            topics: List of topics to include (optional)
            
        Returns:
            True if successful, False otherwise
        """
        timeline = self.get_timeline(topics)
        if timeline is not None:
            timeline.to_csv(output_path, index=False)
            return True
        return False
    
    # ===== UTILITY METHODS =====
    
    def summary(self) -> str:
        """
        Get a human-readable summary of the bag
        
        Returns:
            Multi-line string with bag summary
        """
        stats = self.stats
        lines = [
            f"ROS Bag Summary: {Path(self.file_path).name}",
            "=" * 50,
            f"Topics: {stats['total_topics']}",
            f"Messages: {stats['total_messages']:,}",
            f"Memory: {stats['total_memory_mb']:.1f} MB",
        ]
        
        if self.time_range:
            start, end = self.time_range
            lines.append(f"Duration: {end - start:.1f} seconds")
        
        lines.append("\nTopics by Message Type:")
        for msg_type, topic_count in stats['topics_by_type'].items():
            lines.append(f"  {msg_type}: {topic_count} topics")
        
        lines.append("\nTop Topics by Message Count:")
        topic_counts = self.get_message_counts()
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        for topic, count in sorted_topics[:10]:
            lines.append(f"  {topic}: {count:,} messages")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        """String representation"""
        return f"BagData({Path(self.file_path).name}, {len(self.topics)} topics)"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        stats = self.stats
        return (f"BagData(file='{self.file_path}', "
                f"topics={stats['total_topics']}, "
                f"messages={stats['total_messages']}, "
                f"memory_mb={stats['total_memory_mb']:.1f})")


# ===== CONVENIENCE FUNCTIONS =====

async def load_bag_async(bag_path: Union[str, Path], use_cache: bool = True) -> BagData:
    """
    Convenience function to load a bag asynchronously
    
    Args:
        bag_path: Path to the bag file
        use_cache: Whether to use caching
        
    Returns:
        BagData instance
    """
    return await BagData.load_async(bag_path, use_cache)


def load_bag(bag_path: Union[str, Path], use_cache: bool = True) -> BagData:
    """
    Convenience function to load a bag synchronously
    
    Args:
        bag_path: Path to the bag file
        use_cache: Whether to use caching
        
    Returns:
        BagData instance
    """
    return BagData.load(bag_path, use_cache)


def compare_bags(*bag_paths: Union[str, Path]) -> Dict[str, Any]:
    """
    Compare multiple bag files
    
    Args:
        *bag_paths: Paths to bag files to compare
        
    Returns:
        Dictionary with comparison results
    """
    bags = [load_bag(path) for path in bag_paths]
    
    comparison = {
        'bag_count': len(bags),
        'bags': {},
        'common_topics': set.intersection(*[set(bag.topics) for bag in bags]) if bags else set(),
        'all_topics': set.union(*[set(bag.topics) for bag in bags]) if bags else set(),
        'total_messages': sum(bag.stats['total_messages'] for bag in bags),
        'total_memory_mb': sum(bag.stats['total_memory_mb'] for bag in bags)
    }
    
    for i, bag in enumerate(bags):
        stats = bag.stats
        comparison['bags'][f'bag_{i}'] = {
            'path': bag.file_path,
            'topics': len(bag.topics),
            'messages': stats['total_messages'],
            'memory_mb': stats['total_memory_mb'],
            'duration': bag.duration
        }
    
    return comparison
