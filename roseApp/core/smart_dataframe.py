"""
Smart DataFrame Management System

This module provides an intelligent DataFrame caching and management system that:
1. Maintains compatibility with ComprehensiveBagInfo
2. Eliminates sparsity through topic-based storage
3. Provides unified query and analysis interfaces
4. Supports flexible export options
5. Maintains pandas compatibility
"""

import logging
import pickle
import gzip
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from pathlib import Path
import hashlib

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from .model import ComprehensiveBagInfo
from .cache import get_cache

_logger = logging.getLogger(__name__)


@dataclass
class TopicDataFrame:
    """Efficient storage for a single topic's messages"""
    topic_name: str
    message_type: str
    df: Any  # pandas DataFrame
    message_count: int = 0
    memory_usage: int = 0
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    
    def __post_init__(self):
        if PANDAS_AVAILABLE and self.df is not None:
            self.message_count = len(self.df)
            self.memory_usage = self.df.memory_usage(deep=True).sum()
    
    def mark_accessed(self):
        """Mark this topic as accessed for cache management"""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class DataFrameIndex:
    """Index for managing topic DataFrames"""
    topics: Dict[str, TopicDataFrame] = field(default_factory=dict)
    topics_by_type: Dict[str, List[str]] = field(default_factory=dict)
    total_messages: int = 0
    total_memory_usage: int = 0
    time_range: Optional[Tuple[float, float]] = None
    cache_strategy: str = "smart"  # "all", "hot", "smart", "none"
    
    def add_topic(self, topic_df: TopicDataFrame):
        """Add a topic DataFrame to the index"""
        self.topics[topic_df.topic_name] = topic_df
        
        # Update type index
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


class SmartDataFrameManager:
    """
    Smart DataFrame manager that integrates with ComprehensiveBagInfo
    
    Key Features:
    - Transparent integration with existing ComprehensiveBagInfo
    - Automatic topic-based DataFrame splitting
    - Intelligent caching strategies
    - Unified query interface
    - Pandas-compatible operations
    """
    
    def __init__(self, bag_info: ComprehensiveBagInfo, cache_strategy: str = "smart"):
        self.bag_info = bag_info
        self.cache_strategy = cache_strategy
        self.index = DataFrameIndex(cache_strategy=cache_strategy)
        self._cache = get_cache()
        self._initialized = False
        
        # Initialize from existing DataFrame if available
        if hasattr(bag_info, 'df') and bag_info.df is not None:
            self._initialize_from_sparse_df()
    
    def _initialize_from_sparse_df(self):
        """Initialize topic DataFrames from sparse DataFrame"""
        if not PANDAS_AVAILABLE or self.bag_info.df is None:
            return
        
        _logger.info("Converting sparse DataFrame to topic-based storage...")
        
        df = self.bag_info.df.reset_index()  # Reset index to get timestamp_sec as column
        
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
            
            self.index.add_topic(topic_df)
        
        self._initialized = True
        _logger.info(f"Initialized SmartDataFrameManager with {len(self.index.topics)} topics")
    
    # ===== COMPATIBILITY INTERFACE =====
    
    @property
    def df(self) -> Optional[Any]:
        """
        Provide backward compatibility by returning a unified DataFrame when requested
        This is a computed property that creates the sparse DataFrame on-demand
        """
        if not self._initialized or not PANDAS_AVAILABLE:
            return self.bag_info.df
        
        # Create unified DataFrame on-demand (for backward compatibility)
        return self._create_unified_dataframe()
    
    def _create_unified_dataframe(self) -> Optional[Any]:
        """Create a unified DataFrame from topic DataFrames (for compatibility)"""
        if not self.index.topics:
            return None
        
        # Get all unique columns across all topics
        all_columns = set()
        for topic_df in self.index.topics.values():
            if topic_df.df is not None:
                all_columns.update(topic_df.df.columns)
        
        all_columns = sorted(list(all_columns))
        
        # Create unified DataFrame
        unified_data = []
        for topic_df in self.index.topics.values():
            if topic_df.df is not None:
                # Reindex to include all columns (fills missing with NaN)
                topic_data = topic_df.df.reindex(columns=all_columns)
                unified_data.append(topic_data)
        
        if unified_data:
            unified_df = pd.concat(unified_data, ignore_index=True)
            unified_df.set_index('timestamp_sec', inplace=True)
            unified_df.sort_index(inplace=True)
            return unified_df
        
        return None
    
    # ===== SMART QUERY INTERFACE =====
    
    def get_topic_data(self, topic_name: str) -> Optional[Any]:
        """Get DataFrame for a specific topic"""
        if topic_name in self.index.topics:
            topic_df = self.index.topics[topic_name]
            topic_df.mark_accessed()
            return topic_df.df
        return None
    
    def get_topics_by_type(self, message_type: str) -> List[str]:
        """Get all topics with a specific message type"""
        return self.index.topics_by_type.get(message_type, [])
    
    def query_topic(self, topic_name: str, time_start: Optional[float] = None, 
                   time_end: Optional[float] = None, **filters) -> Optional[Any]:
        """Query a topic with optional time filtering and other filters"""
        df = self.get_topic_data(topic_name)
        if df is None or not PANDAS_AVAILABLE:
            return None
        
        result_df = df
        
        # Apply time filtering
        if time_start is not None or time_end is not None:
            if 'timestamp_sec' not in df.columns:
                _logger.warning(f"Topic {topic_name} has no timestamp_sec column for time filtering")
            else:
                query_conditions = []
                if time_start is not None:
                    query_conditions.append(f"timestamp_sec >= {time_start}")
                if time_end is not None:
                    query_conditions.append(f"timestamp_sec <= {time_end}")
                
                if query_conditions:
                    result_df = df.query(" and ".join(query_conditions))
        
        # Apply additional filters
        for column, value in filters.items():
            if column in result_df.columns:
                if isinstance(value, (list, tuple)):
                    result_df = result_df[result_df[column].isin(value)]
                else:
                    result_df = result_df[result_df[column] == value]
        
        return result_df
    
    def query_all_topics(self, time_start: Optional[float] = None, 
                        time_end: Optional[float] = None, 
                        topic_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """Query multiple topics with the same criteria"""
        results = {}
        topics_to_query = topic_filter or list(self.index.topics.keys())
        
        for topic in topics_to_query:
            result = self.query_topic(topic, time_start, time_end)
            if result is not None and len(result) > 0:
                results[topic] = result
        
        return results
    
    def create_unified_timeline(self, topics: Optional[List[str]] = None) -> Optional[Any]:
        """Create a unified timeline DataFrame with just timestamps and topics"""
        if not PANDAS_AVAILABLE:
            return None
        
        timeline_data = []
        topics_to_process = topics or list(self.index.topics.keys())
        
        for topic_name in topics_to_process:
            topic_df = self.get_topic_data(topic_name)
            if topic_df is not None and 'timestamp_sec' in topic_df.columns:
                topic_timeline = pd.DataFrame({
                    'timestamp_sec': topic_df['timestamp_sec'],
                    'topic': topic_name,
                    'message_type': self.index.topics[topic_name].message_type,
                    'message_size': topic_df.get('message_size', None)
                })
                timeline_data.append(topic_timeline)
        
        if timeline_data:
            unified = pd.concat(timeline_data, ignore_index=True)
            return unified.sort_values('timestamp_sec').reset_index(drop=True)
        
        return None
    
    # ===== PANDAS COMPATIBILITY =====
    
    def apply_to_topic(self, topic_name: str, func: Callable, *args, **kwargs) -> Any:
        """Apply a pandas function to a specific topic's DataFrame"""
        df = self.get_topic_data(topic_name)
        if df is not None:
            return func(df, *args, **kwargs)
        return None
    
    def apply_to_all_topics(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Apply a pandas function to all topic DataFrames"""
        results = {}
        for topic_name in self.index.topics.keys():
            result = self.apply_to_topic(topic_name, func, *args, **kwargs)
            if result is not None:
                results[topic_name] = result
        return results
    
    # ===== EXPORT INTERFACE =====
    
    def export_topic_csv(self, topic_name: str, output_path: Path) -> bool:
        """Export a specific topic to CSV"""
        df = self.get_topic_data(topic_name)
        if df is not None:
            df.to_csv(output_path, index=False)
            return True
        return False
    
    def export_all_topics_csv(self, output_dir: Path, 
                             topic_filter: Optional[List[str]] = None) -> Dict[str, Path]:
        """Export all topics to separate CSV files"""
        output_dir.mkdir(exist_ok=True)
        exported_files = {}
        
        topics_to_export = topic_filter or list(self.index.topics.keys())
        
        for topic_name in topics_to_export:
            clean_name = topic_name.replace('/', '_').replace(':', '_')
            csv_path = output_dir / f"{clean_name}.csv"
            
            if self.export_topic_csv(topic_name, csv_path):
                exported_files[topic_name] = csv_path
        
        return exported_files
    
    def export_unified_csv(self, output_path: Path) -> bool:
        """Export unified DataFrame to CSV (for compatibility)"""
        unified_df = self._create_unified_dataframe()
        if unified_df is not None:
            unified_df.to_csv(output_path)
            return True
        return False
    
    # ===== CACHE MANAGEMENT =====
    
    def _get_cache_key(self, suffix: str = "") -> str:
        """Generate cache key for this manager"""
        base_key = f"smart_df_{hashlib.md5(self.bag_info.file_path.encode()).hexdigest()}"
        return f"{base_key}_{suffix}" if suffix else base_key
    
    def save_to_cache(self, compress: bool = True) -> None:
        """Save topic DataFrames to cache with intelligent strategy"""
        if not self._initialized:
            return
        
        cache_data = {
            'index_metadata': {
                'topics_by_type': self.index.topics_by_type,
                'total_messages': self.index.total_messages,
                'total_memory_usage': self.index.total_memory_usage,
                'time_range': self.index.time_range,
                'cache_strategy': self.index.cache_strategy
            },
            'topic_metadata': {},
            'topic_data': {}
        }
        
        # Save based on cache strategy
        for topic_name, topic_df in self.index.topics.items():
            # Always save metadata
            cache_data['topic_metadata'][topic_name] = {
                'message_type': topic_df.message_type,
                'message_count': topic_df.message_count,
                'memory_usage': topic_df.memory_usage,
                'last_accessed': topic_df.last_accessed,
                'access_count': topic_df.access_count
            }
            
            # Save DataFrame based on strategy
            should_cache_data = self._should_cache_topic_data(topic_df)
            if should_cache_data and topic_df.df is not None:
                cache_data['topic_data'][topic_name] = topic_df.df.to_json(orient='records')
        
        # Save to cache
        cache_key = self._get_cache_key("smart")
        
        if compress:
            # Compress the data
            serialized = pickle.dumps(cache_data)
            compressed = gzip.compress(serialized)
            self._cache.put(cache_key, compressed)
        else:
            self._cache.put(cache_key, cache_data)
        
        _logger.info(f"Saved SmartDataFrameManager to cache with {len(cache_data['topic_data'])} topic DataFrames")
    
    def load_from_cache(self) -> bool:
        """Load topic DataFrames from cache"""
        cache_key = self._get_cache_key("smart")
        cached_data = self._cache.get(cache_key)
        
        if cached_data is None:
            return False
        
        try:
            # Handle compressed data
            if isinstance(cached_data, bytes):
                decompressed = gzip.decompress(cached_data)
                cache_data = pickle.loads(decompressed)
            else:
                cache_data = cached_data
            
            # Restore index metadata
            index_meta = cache_data['index_metadata']
            self.index = DataFrameIndex(
                topics_by_type=index_meta['topics_by_type'],
                total_messages=index_meta['total_messages'],
                total_memory_usage=index_meta['total_memory_usage'],
                time_range=index_meta['time_range'],
                cache_strategy=index_meta['cache_strategy']
            )
            
            # Restore topics
            for topic_name, topic_meta in cache_data['topic_metadata'].items():
                # Create TopicDataFrame with metadata
                topic_df = TopicDataFrame(
                    topic_name=topic_name,
                    message_type=topic_meta['message_type'],
                    df=None,  # Will be loaded on-demand
                    message_count=topic_meta['message_count'],
                    memory_usage=topic_meta['memory_usage'],
                    last_accessed=topic_meta['last_accessed'],
                    access_count=topic_meta['access_count']
                )
                
                # Load DataFrame if cached
                if topic_name in cache_data['topic_data'] and PANDAS_AVAILABLE:
                    df_json = cache_data['topic_data'][topic_name]
                    topic_df.df = pd.read_json(df_json, orient='records')
                
                self.index.topics[topic_name] = topic_df
            
            self._initialized = True
            _logger.info(f"Loaded SmartDataFrameManager from cache with {len(self.index.topics)} topics")
            return True
            
        except Exception as e:
            _logger.error(f"Failed to load from cache: {e}")
            return False
    
    def _should_cache_topic_data(self, topic_df: TopicDataFrame) -> bool:
        """Determine if a topic's DataFrame should be cached based on strategy"""
        if self.cache_strategy == "all":
            return True
        elif self.cache_strategy == "none":
            return False
        elif self.cache_strategy == "hot":
            # Cache if accessed more than threshold
            return topic_df.access_count > 5
        elif self.cache_strategy == "smart":
            # Smart caching based on size, access pattern, and recency
            recent_access = (time.time() - topic_df.last_accessed) < 3600  # 1 hour
            frequent_access = topic_df.access_count > 2
            reasonable_size = topic_df.memory_usage < 10 * 1024 * 1024  # 10MB
            
            return (recent_access and frequent_access) or (frequent_access and reasonable_size)
        
        return False
    
    # ===== STATISTICS AND MONITORING =====
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        return {
            'total_topics': len(self.index.topics),
            'total_messages': self.index.total_messages,
            'total_memory_mb': self.index.total_memory_usage / 1024 / 1024,
            'time_range': self.index.time_range,
            'cache_strategy': self.index.cache_strategy,
            'topics_by_type': {k: len(v) for k, v in self.index.topics_by_type.items()},
            'most_accessed_topics': sorted(
                [(name, tdf.access_count) for name, tdf in self.index.topics.items()],
                key=lambda x: x[1], reverse=True
            )[:10]
        }


# ===== INTEGRATION WITH ComprehensiveBagInfo =====

def enhance_bag_info_with_smart_dataframe(bag_info: ComprehensiveBagInfo, 
                                        cache_strategy: str = "smart") -> ComprehensiveBagInfo:
    """
    Enhance ComprehensiveBagInfo with SmartDataFrameManager
    
    This function provides seamless integration while maintaining backward compatibility
    """
    if not hasattr(bag_info, '_smart_df_manager'):
        bag_info._smart_df_manager = SmartDataFrameManager(bag_info, cache_strategy)
        
        # Try to load from cache first
        if not bag_info._smart_df_manager.load_from_cache():
            # If no cache, initialize from existing DataFrame
            if hasattr(bag_info, 'df') and bag_info.df is not None:
                bag_info._smart_df_manager._initialize_from_sparse_df()
        
        # Override df property to use smart manager
        original_df = bag_info.df
        
        def smart_df_property(self):
            return self._smart_df_manager.df
        
        # Monkey patch the df property (for demonstration - in real implementation, 
        # this would be done through proper class inheritance)
        bag_info.__class__.df = property(smart_df_property)
        
        # Add convenience methods
        bag_info.get_topic_data = bag_info._smart_df_manager.get_topic_data
        bag_info.query_topic = bag_info._smart_df_manager.query_topic
        bag_info.export_topics_csv = bag_info._smart_df_manager.export_all_topics_csv
        bag_info.get_smart_stats = bag_info._smart_df_manager.get_stats
    
    return bag_info


# ===== CONVENIENCE FUNCTIONS =====

def create_smart_dataframe_manager(bag_info: ComprehensiveBagInfo, 
                                 cache_strategy: str = "smart") -> SmartDataFrameManager:
    """Create a SmartDataFrameManager from ComprehensiveBagInfo"""
    return SmartDataFrameManager(bag_info, cache_strategy)


def migrate_sparse_to_smart(bag_info: ComprehensiveBagInfo) -> SmartDataFrameManager:
    """Migrate from sparse DataFrame to smart DataFrame management"""
    manager = SmartDataFrameManager(bag_info)
    manager.save_to_cache()  # Save to cache for future use
    return manager
