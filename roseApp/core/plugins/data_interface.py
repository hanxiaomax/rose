"""
Data interface for plugins to access Rose bag data
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from ..model import ComprehensiveBagInfo, TopicInfo
from ..cache import create_bag_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class PluginDataContext:
    """Context information for plugin data operations"""
    bag_path: Path
    bag_info: ComprehensiveBagInfo
    topics: List[str]
    operation: str  # 'load', 'inspect', 'extract', 'export', etc.
    parameters: Dict[str, Any]
    cache_available: bool = True


class DataInterface:
    """
    Interface for plugins to access and manipulate Rose bag data
    
    This provides a clean API for plugins to:
    - Access cached bag information
    - Get DataFrames for specific topics
    - Filter and process data
    - Export data in various formats
    """
    
    def __init__(self):
        self.cache_manager = create_bag_cache_manager()
        self._data_processor = None
        logger.debug("DataInterface initialized")
    
    def _get_data_processor(self):
        """Lazy initialization of DataProcessor to avoid circular import"""
        if self._data_processor is None:
            from ...cli.data import DataProcessor
            self._data_processor = DataProcessor()
        return self._data_processor
    
    def get_bag_info(self, bag_path: Union[str, Path]) -> Optional[ComprehensiveBagInfo]:
        """
        Get comprehensive bag information from cache
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            ComprehensiveBagInfo if available, None otherwise
        """
        if isinstance(bag_path, str):
            bag_path = Path(bag_path)
        
        cached_entry = self.cache_manager.get_analysis(bag_path)
        if cached_entry and cached_entry.is_valid(bag_path):
            return cached_entry.bag_info
        return None
    
    def is_bag_cached(self, bag_path: Union[str, Path]) -> bool:
        """Check if bag is available in cache"""
        bag_info = self.get_bag_info(bag_path)
        return bag_info is not None
    
    def has_dataframes(self, bag_path: Union[str, Path]) -> bool:
        """Check if bag has DataFrame index available"""
        bag_info = self.get_bag_info(bag_path)
        if bag_info:
            return bag_info.has_any_dataframes()
        return False
    
    def get_topics(self, bag_path: Union[str, Path]) -> List[str]:
        """
        Get list of topic names from bag
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            List of topic names
        """
        bag_info = self.get_bag_info(bag_path)
        if bag_info and bag_info.topics:
            return [t.name if isinstance(t, TopicInfo) else str(t) for t in bag_info.topics]
        return []
    
    def get_topic_info(self, bag_path: Union[str, Path], topic_name: str) -> Optional[TopicInfo]:
        """
        Get detailed information for a specific topic
        
        Args:
            bag_path: Path to the bag file
            topic_name: Name of the topic
            
        Returns:
            TopicInfo if found, None otherwise
        """
        bag_info = self.get_bag_info(bag_path)
        if bag_info and bag_info.topics:
            for topic in bag_info.topics:
                if isinstance(topic, TopicInfo) and topic.name == topic_name:
                    return topic
        return None
    
    def get_dataframe(self, bag_path: Union[str, Path], topic_name: str) -> Any:
        """
        Get DataFrame for a specific topic
        
        Args:
            bag_path: Path to the bag file
            topic_name: Name of the topic
            
        Returns:
            pandas DataFrame if available, None otherwise
        """
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas not available, cannot return DataFrame")
            return None
        
        topic_info = self.get_topic_info(bag_path, topic_name)
        if topic_info and topic_info.has_dataframe():
            return topic_info.get_dataframe()
        return None
    
    def get_multiple_dataframes(self, bag_path: Union[str, Path], topic_names: List[str]) -> Dict[str, Any]:
        """
        Get DataFrames for multiple topics
        
        Args:
            bag_path: Path to the bag file
            topic_names: List of topic names
            
        Returns:
            Dict mapping topic names to DataFrames
        """
        bag_info = self.get_bag_info(bag_path)
        if bag_info:
            return self._get_data_processor().get_topic_dataframes(bag_info, topic_names)
        return {}
    
    def merge_dataframes(self, dataframes: Dict[str, Any]) -> Any:
        """
        Merge multiple DataFrames by timestamp
        
        Args:
            dataframes: Dict mapping topic names to DataFrames
            
        Returns:
            Merged DataFrame
        """
        return self._get_data_processor().merge_topic_dataframes(dataframes)
    
    def filter_dataframe(self, df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to DataFrame
        
        Args:
            df: DataFrame to filter
            filters: Filter conditions
            
        Returns:
            Filtered DataFrame
        """
        return self._get_data_processor().filter_dataframe(df, filters)
    
    def export_to_csv(self, df: Any, output_path: Union[str, Path], include_index: bool = True) -> bool:
        """
        Export DataFrame to CSV
        
        Args:
            df: DataFrame to export
            output_path: Output file path
            include_index: Whether to include index
            
        Returns:
            bool: True if export successful
        """
        return self._get_data_processor().export_to_csv(df, str(output_path), include_index)
    
    def get_bag_statistics(self, bag_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get bag file statistics
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            Dict with bag statistics
        """
        bag_info = self.get_bag_info(bag_path)
        if bag_info:
            return {
                'file_path': bag_info.file_path,
                'file_size_mb': bag_info.file_size_mb,
                'total_messages': bag_info.total_messages,
                'duration_seconds': bag_info.duration_seconds,
                'topics_count': len(bag_info.topics) if bag_info.topics else 0,
                'time_range': bag_info.time_range.to_dict() if bag_info.time_range else None,
                'has_dataframes': bag_info.has_any_dataframes()
            }
        return {}
    
    def filter_topics(self, bag_path: Union[str, Path], patterns: List[str]) -> List[str]:
        """
        Filter topics using patterns
        
        Args:
            bag_path: Path to the bag file
            patterns: List of patterns to match
            
        Returns:
            List of matching topic names
        """
        from ...cli.util import filter_topics
        all_topics = self.get_topics(bag_path)
        return filter_topics(all_topics, patterns, None)
    
    def create_context(self, bag_path: Union[str, Path], operation: str, **kwargs) -> PluginDataContext:
        """
        Create a data context for plugin operations
        
        Args:
            bag_path: Path to the bag file
            operation: Operation name
            **kwargs: Additional parameters
            
        Returns:
            PluginDataContext
        """
        if isinstance(bag_path, str):
            bag_path = Path(bag_path)
        
        bag_info = self.get_bag_info(bag_path)
        topics = self.get_topics(bag_path) if bag_info else []
        
        return PluginDataContext(
            bag_path=bag_path,
            bag_info=bag_info,
            topics=topics,
            operation=operation,
            parameters=kwargs,
            cache_available=self.is_bag_cached(bag_path)
        )
