"""
Optimized data storage system for ROS bag messages

This module provides an alternative to the sparse DataFrame approach by:
1. Storing messages by topic/type in separate DataFrames
2. Providing efficient query interfaces
3. Supporting both structured and time-series analysis
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import time

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from .model import ComprehensiveBagInfo, TopicInfo

_logger = logging.getLogger(__name__)


@dataclass
class TopicDataFrame:
    """
    Efficient storage for a single topic's messages
    
    Instead of one sparse DataFrame, we have focused DataFrames per topic
    """
    topic_name: str
    message_type: str
    df: Any  # pandas DataFrame
    message_count: int = 0
    memory_usage: int = 0
    
    def __post_init__(self):
        if PANDAS_AVAILABLE and self.df is not None:
            self.message_count = len(self.df)
            self.memory_usage = self.df.memory_usage(deep=True).sum()


@dataclass  
class MessageStore:
    """
    High-performance message storage system
    
    Key improvements over sparse DataFrame:
    - Separate DataFrames per topic (no sparsity)
    - Fast topic-specific queries
    - Memory-efficient storage
    - Unified query interface
    """
    
    # Core storage: topic_name -> TopicDataFrame
    topic_dataframes: Dict[str, TopicDataFrame] = field(default_factory=dict)
    
    # Fast lookup indices
    topics_by_type: Dict[str, List[str]] = field(default_factory=dict)  # message_type -> [topic_names]
    
    # Metadata
    total_messages: int = 0
    total_memory_usage: int = 0
    time_range: Optional[Tuple[float, float]] = None
    
    def add_topic_dataframe(self, topic_df: TopicDataFrame) -> None:
        """Add a topic's DataFrame to the store"""
        self.topic_dataframes[topic_df.topic_name] = topic_df
        
        # Update indices
        if topic_df.message_type not in self.topics_by_type:
            self.topics_by_type[topic_df.message_type] = []
        self.topics_by_type[topic_df.message_type].append(topic_df.topic_name)
        
        # Update metadata
        self.total_messages += topic_df.message_count
        self.total_memory_usage += topic_df.memory_usage
        
        # Update time range
        if PANDAS_AVAILABLE and topic_df.df is not None and len(topic_df.df) > 0:
            if 'timestamp_sec' in topic_df.df.columns:
                topic_start = topic_df.df['timestamp_sec'].min()
                topic_end = topic_df.df['timestamp_sec'].max()
                
                if self.time_range is None:
                    self.time_range = (topic_start, topic_end)
                else:
                    self.time_range = (
                        min(self.time_range[0], topic_start),
                        max(self.time_range[1], topic_end)
                    )
    
    def get_topic_data(self, topic_name: str) -> Optional[Any]:
        """Get DataFrame for a specific topic"""
        if topic_name in self.topic_dataframes:
            return self.topic_dataframes[topic_name].df
        return None
    
    def get_topics_by_type(self, message_type: str) -> List[str]:
        """Get all topics with a specific message type"""
        return self.topics_by_type.get(message_type, [])
    
    def query_topic(self, topic_name: str, time_start: Optional[float] = None, 
                   time_end: Optional[float] = None) -> Optional[Any]:
        """Query a topic with optional time filtering"""
        df = self.get_topic_data(topic_name)
        if df is None or not PANDAS_AVAILABLE:
            return None
        
        if time_start is not None or time_end is not None:
            if 'timestamp_sec' not in df.columns:
                _logger.warning(f"Topic {topic_name} has no timestamp_sec column for time filtering")
                return df
            
            query_conditions = []
            if time_start is not None:
                query_conditions.append(f"timestamp_sec >= {time_start}")
            if time_end is not None:
                query_conditions.append(f"timestamp_sec <= {time_end}")
            
            return df.query(" and ".join(query_conditions))
        
        return df
    
    def get_all_topics(self) -> List[str]:
        """Get list of all topic names"""
        return list(self.topic_dataframes.keys())
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get memory usage summary"""
        return {
            'total_memory_mb': self.total_memory_usage / 1024 / 1024,
            'total_messages': self.total_messages,
            'topic_count': len(self.topic_dataframes),
            'memory_per_message': self.total_memory_usage / max(1, self.total_messages),
            'topics': {
                name: {
                    'memory_mb': tdf.memory_usage / 1024 / 1024,
                    'message_count': tdf.message_count,
                    'message_type': tdf.message_type
                }
                for name, tdf in self.topic_dataframes.items()
            }
        }
    
    def create_unified_timeline(self, topics: Optional[List[str]] = None) -> Optional[Any]:
        """
        Create a unified timeline DataFrame with just timestamps and topics
        Useful for time-based analysis without the sparsity problem
        """
        if not PANDAS_AVAILABLE:
            return None
        
        timeline_data = []
        
        topics_to_process = topics or self.get_all_topics()
        
        for topic_name in topics_to_process:
            topic_df = self.get_topic_data(topic_name)
            if topic_df is not None and 'timestamp_sec' in topic_df.columns:
                topic_timeline = pd.DataFrame({
                    'timestamp_sec': topic_df['timestamp_sec'],
                    'topic': topic_name,
                    'message_type': self.topic_dataframes[topic_name].message_type,
                    'message_size': topic_df.get('message_size', None)
                })
                timeline_data.append(topic_timeline)
        
        if timeline_data:
            unified = pd.concat(timeline_data, ignore_index=True)
            return unified.sort_values('timestamp_sec').reset_index(drop=True)
        
        return None


class OptimizedBagParser:
    """
    Enhanced bag parser that creates optimized storage instead of sparse DataFrame
    """
    
    @staticmethod
    def create_message_store_from_bag(bag_info: ComprehensiveBagInfo) -> MessageStore:
        """
        Convert existing sparse DataFrame to optimized MessageStore
        """
        store = MessageStore()
        
        if bag_info.df is None or not PANDAS_AVAILABLE:
            _logger.warning("No DataFrame available in bag_info")
            return store
        
        df = bag_info.df.reset_index()  # Reset index to get timestamp_sec as column
        
        # Group by topic to create separate DataFrames
        for topic_name in df['topic'].unique():
            topic_mask = df['topic'] == topic_name
            topic_data = df[topic_mask].copy()
            
            # Remove completely empty columns for this topic
            topic_data = topic_data.dropna(axis=1, how='all')
            
            # Get message type for this topic
            message_type = topic_data['message_type'].iloc[0] if len(topic_data) > 0 else 'unknown'
            
            # Create TopicDataFrame
            topic_df = TopicDataFrame(
                topic_name=topic_name,
                message_type=message_type,
                df=topic_data
            )
            
            store.add_topic_dataframe(topic_df)
            
        _logger.info(f"Created MessageStore with {len(store.topic_dataframes)} topics, "
                    f"{store.total_messages} messages, "
                    f"{store.total_memory_usage/1024/1024:.1f}MB")
        
        return store
    
    @staticmethod
    def analyze_sparsity(df: Any) -> Dict[str, Any]:
        """Analyze sparsity of the current DataFrame approach"""
        if not PANDAS_AVAILABLE or df is None:
            return {}
        
        total_cells = df.size
        non_null_cells = df.count().sum()
        null_cells = total_cells - non_null_cells
        
        sparsity_ratio = null_cells / total_cells if total_cells > 0 else 0
        
        # Analyze by topic
        topic_sparsity = {}
        if 'topic' in df.columns:
            for topic in df['topic'].unique():
                topic_mask = df['topic'] == topic
                topic_df = df[topic_mask]
                topic_total = topic_df.size
                topic_non_null = topic_df.count().sum()
                topic_sparsity[topic] = {
                    'sparsity_ratio': (topic_total - topic_non_null) / topic_total,
                    'useful_columns': topic_df.count()[topic_df.count() > 0].count(),
                    'total_columns': len(topic_df.columns)
                }
        
        return {
            'overall_sparsity_ratio': sparsity_ratio,
            'total_cells': total_cells,
            'null_cells': null_cells,
            'non_null_cells': non_null_cells,
            'total_columns': len(df.columns),
            'topic_sparsity': topic_sparsity,
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        }


# Convenience functions for easy migration
def optimize_bag_storage(bag_info: ComprehensiveBagInfo) -> MessageStore:
    """
    Convert sparse DataFrame to optimized storage
    
    Usage:
        store = optimize_bag_storage(bag_info)
        radar_data = store.get_topic_data('/radar/points')
        gps_data = store.query_topic('/gps/fix', time_start=123.0, time_end=456.0)
    """
    return OptimizedBagParser.create_message_store_from_bag(bag_info)


def analyze_current_sparsity(bag_info: ComprehensiveBagInfo) -> Dict[str, Any]:
    """
    Analyze sparsity of current DataFrame approach
    
    Usage:
        sparsity_info = analyze_current_sparsity(bag_info)
        print(f"Sparsity ratio: {sparsity_info['overall_sparsity_ratio']:.2%}")
    """
    return OptimizedBagParser.analyze_sparsity(bag_info.df)
