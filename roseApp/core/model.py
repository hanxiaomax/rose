"""
Optimized core data models for ROS bag processing
Reduces dictionary usage and improves direct member access
"""
import json
import pickle
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union, Any, Tuple, Dict
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

logger = logging.getLogger(__name__)


class AnalysisLevel(Enum):
    """Analysis depth levels for bag processing"""
    NONE = "none"      # No analysis performed
    QUICK = "quick"    # Basic metadata without message traversal
    INDEX = "index"    # Message indexing with DataFrame creation


@dataclass
class TopicInfo:
    """Detailed information about a ROS topic"""
    name: str
    message_type: str
    message_count: Optional[int] = None
    message_frequency: Optional[float] = None  # Hz
    total_size_bytes: Optional[int] = None
    average_message_size: Optional[int] = None
    first_message_time: Optional[Tuple[int, int]] = None  # (sec, nsec)
    last_message_time: Optional[Tuple[int, int]] = None   # (sec, nsec)
    connection_id: Optional[str] = None
    
    # DataFrame caching support (only populated when build_index=True)
    df: Optional[Any] = field(default=None)  # Topic-specific DataFrame
    df_memory_usage: Optional[int] = field(default=None)  # Memory usage in bytes
    df_created_at: Optional[float] = field(default=None)  # Timestamp when DataFrame was created
    
    def __lt__(self, other) -> bool:
        """Less than comparison based on topic name"""
        if not isinstance(other, TopicInfo):
            return NotImplemented
        return self.name < other.name
    
    def __le__(self, other) -> bool:
        """Less than or equal comparison based on topic name"""
        if not isinstance(other, TopicInfo):
            return NotImplemented
        return self.name <= other.name
    
    def __gt__(self, other) -> bool:
        """Greater than comparison based on topic name"""
        if not isinstance(other, TopicInfo):
            return NotImplemented
        return self.name > other.name
    
    def __ge__(self, other) -> bool:
        """Greater than or equal comparison based on topic name"""
        if not isinstance(other, TopicInfo):
            return NotImplemented
        return self.name >= other.name
    
    def __eq__(self, other) -> bool:
        """Equality comparison based on topic name and message type"""
        if not isinstance(other, TopicInfo):
            return NotImplemented
        return self.name == other.name and self.message_type == other.message_type
    
    def __hash__(self) -> int:
        """Hash based on topic name and message type for use in sets and dicts"""
        return hash((self.name, self.message_type))
    
    @property
    def count_str(self) -> str:
        """Get message count as string"""
        if self.message_count is not None and self.message_count > 0:
            return f"{self.message_count}"
        return 'N.A'
    
    @property
    def frequency_str(self) -> str:
        """Get message frequency as string"""
        return f"{self.message_frequency or 'N.A'} Hz"
    
    @property
    def size_str(self) -> str:
        """Get total size as string"""
        return f"{self.total_size_bytes or 'N.A'} bytes"
    
    def get_duration_seconds(self) -> Optional[float]:
        """Calculate topic duration in seconds"""
        if not (self.first_message_time and self.last_message_time):
            return None
        
        start_ns = self.first_message_time[0] * 1_000_000_000 + self.first_message_time[1]
        end_ns = self.last_message_time[0] * 1_000_000_000 + self.last_message_time[1]
        return (end_ns - start_ns) / 1_000_000_000
    
    def calculate_frequency(self) -> Optional[float]:
        """Calculate message frequency in Hz"""
        duration = self.get_duration_seconds()
        if duration and duration > 0 and self.message_count:
            self.message_frequency = self.message_count / duration
            return self.message_frequency
        return None
    
    # DataFrame management methods
    def set_dataframe(self, df: Any) -> None:
        """Set DataFrame for this topic and update metadata"""
        import time
        self.df = df
        self.df_created_at = time.time()
        
        # Calculate memory usage if pandas is available
        if PANDAS_AVAILABLE and df is not None:
            try:
                self.df_memory_usage = df.memory_usage(deep=True).sum()
            except:
                self.df_memory_usage = None
            
            # Auto-calculate statistics from DataFrame
            self._calculate_statistics_from_dataframe()
    
    def get_dataframe(self) -> Optional[Any]:
        """Get DataFrame for this topic"""
        return self.df
    
    def has_dataframe(self) -> bool:
        """Check if this topic has a DataFrame"""
        return self.df is not None
    
    def clear_dataframe(self) -> None:
        """Clear DataFrame to free memory"""
        self.df = None
        self.df_memory_usage = None
        self.df_created_at = None
    
    @property
    def df_memory_mb(self) -> Optional[float]:
        """Get DataFrame memory usage in MB"""
        if self.df_memory_usage:
            return self.df_memory_usage / 1024 / 1024
        return None
    
    def _calculate_statistics_from_dataframe(self) -> None:
        """Calculate topic statistics from DataFrame data"""
        if not PANDAS_AVAILABLE or self.df is None or len(self.df) == 0:
            return
        
        try:
            # 1. Message count
            self.message_count = len(self.df)
            
            # 2. Message size statistics
            if 'message_size' in self.df.columns:
                self.total_size_bytes = int(self.df['message_size'].sum())
                self.average_message_size = int(self.df['message_size'].mean())
            
            # 3. Time range and frequency
            if hasattr(self.df.index, 'min') and hasattr(self.df.index, 'max'):
                start_time_sec = float(self.df.index.min())
                end_time_sec = float(self.df.index.max())
                
                # Convert to (sec, nsec) format for compatibility
                start_sec = int(start_time_sec)
                start_nsec = int((start_time_sec - start_sec) * 1_000_000_000)
                end_sec = int(end_time_sec)
                end_nsec = int((end_time_sec - end_sec) * 1_000_000_000)
                
                self.first_message_time = (start_sec, start_nsec)
                self.last_message_time = (end_sec, end_nsec)
                
                # Calculate frequency
                duration = end_time_sec - start_time_sec
                if duration > 0:
                    self.message_frequency = self.message_count / duration
            
            # 4. Alternative time extraction from timestamp_ns if available
            elif 'timestamp_ns' in self.df.columns:
                first_ts_ns = int(self.df['timestamp_ns'].min())
                last_ts_ns = int(self.df['timestamp_ns'].max())
                
                # Convert nanoseconds to (sec, nsec)
                first_sec = first_ts_ns // 1_000_000_000
                first_nsec = first_ts_ns % 1_000_000_000
                last_sec = last_ts_ns // 1_000_000_000
                last_nsec = last_ts_ns % 1_000_000_000
                
                self.first_message_time = (first_sec, first_nsec)
                self.last_message_time = (last_sec, last_nsec)
                
                # Calculate frequency
                duration_ns = last_ts_ns - first_ts_ns
                if duration_ns > 0:
                    duration_sec = duration_ns / 1_000_000_000
                    self.message_frequency = self.message_count / duration_sec
                    
        except Exception as e:
            # If calculation fails, keep existing values
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to calculate statistics from DataFrame for topic {self.name}: {e}")
    
    def refresh_statistics_from_dataframe(self) -> bool:
        """Manually refresh statistics from DataFrame data"""
        if self.has_dataframe():
            self._calculate_statistics_from_dataframe()
            return True
        return False
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get a summary of all statistics for this topic"""
        return {
            'name': self.name,
            'message_type': self.message_type,
            'message_count': self.message_count,
            'total_size_bytes': self.total_size_bytes,
            'average_message_size': self.average_message_size,
            'message_frequency': self.message_frequency,
            'first_message_time': self.first_message_time,
            'last_message_time': self.last_message_time,
            'duration_seconds': self.get_duration_seconds(),
            'has_dataframe': self.has_dataframe(),
            'df_memory_mb': self.df_memory_mb,
            'df_created_at': self.df_created_at
        }


@dataclass
class MessageFieldInfo:
    """Information about a message field structure"""
    field_name: str
    field_type: str
    is_array: bool = False
    array_size: Optional[int] = None  # None for dynamic arrays
    is_builtin: bool = True
    nested_fields: Optional[List['MessageFieldInfo']] = None  # Changed from Dict to List
    
    def get_flattened_paths(self, prefix: str = '') -> List[str]:
        """Get all flattened field paths"""
        current_path = f"{prefix}.{self.field_name}" if prefix else self.field_name
        paths = [current_path]
        
        if self.nested_fields:
            for nested_field in self.nested_fields:
                paths.extend(nested_field.get_flattened_paths(current_path))
        
        return paths


@dataclass
class MessageTypeInfo:
    """Complete information about a ROS message type"""
    message_type: str
    definition: Optional[str] = None
    md5sum: Optional[str] = None
    fields: Optional[List[MessageFieldInfo]] = None  # Changed from Dict to List
    
    def get_all_field_paths(self) -> List[str]:
        """Get all flattened field paths for this message type"""
        if not self.fields:
            return []
        
        paths = []
        for field in self.fields:
            paths.extend(field.get_flattened_paths())
        
        return paths
    
    def find_field(self, field_name: str) -> Optional[MessageFieldInfo]:
        """Find a field by name"""
        if not self.fields:
            return None
        
        for field in self.fields:
            if field.field_name == field_name:
                return field
        return None


@dataclass
class TimeRange:
    """Time range information with utility methods"""
    start_time: Tuple[int, int]  # (sec, nsec)
    end_time: Tuple[int, int]    # (sec, nsec)
    
    def get_start_ns(self) -> int:
        """Get start time in nanoseconds"""
        return self.start_time[0] * 1_000_000_000 + self.start_time[1]
    
    def get_end_ns(self) -> int:
        """Get end time in nanoseconds"""
        return self.end_time[0] * 1_000_000_000 + self.end_time[1]
    
    def get_duration_seconds(self) -> float:
        """Get duration in seconds"""
        return (self.get_end_ns() - self.get_start_ns()) / 1_000_000_000
    
    def get_duration_ns(self) -> int:
        """Get duration in nanoseconds"""
        return self.get_end_ns() - self.get_start_ns()
    
    def contains_time(self, timestamp: Tuple[int, int]) -> bool:
        """Check if timestamp is within this range"""
        ts_ns = timestamp[0] * 1_000_000_000 + timestamp[1]
        return self.get_start_ns() <= ts_ns <= self.get_end_ns()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'start_time': self.start_time,
            'end_time': self.end_time
        }





@dataclass
class BagInfo:
    """
    Optimized comprehensive bag information data structure
    
    Key improvements:
    - Reduced dictionary usage, prefer lists and direct member access
    - Simplified initialization from parser
    - Better type safety and IDE support
    - More efficient memory usage
    - Direct member access without getters/setters
    """
    
    # === BASIC METADATA (always present) ===
    file_path: str
    file_size: int
    file_mtime: float = 0.0  # Added for cache validation
    analysis_level: AnalysisLevel = AnalysisLevel.NONE
    last_updated: float = field(default_factory=time.time)
    
    # === QUICK ANALYSIS DATA ===
    # Use lists instead of dictionaries for better performance and simpler access
    topics: List[TopicInfo] = field(default_factory=list)
    message_types: List[MessageTypeInfo] = field(default_factory=list)
    
    # Time information  
    time_range: Optional[Union[TimeRange, Tuple[float, float]]] = None
    duration_seconds: Optional[float] = None
    
    # === FULL ANALYSIS DATA ===
    # Statistics organized as list of objects instead of nested dictionaries
    total_messages: Optional[int] = None
    total_size: Optional[int] = None
    
    # === OPTIONAL CACHED DATA ===
    # Keep this as simple structure since it's optional
    cached_message_topics: List[str] = field(default_factory=list)
    
    # === SMART DATAFRAME STORAGE ===
    # Topic-based DataFrame storage (replaces sparse DataFrame)
    topic_dataframes: Dict[str, Any] = field(default_factory=dict)  # topic_name -> TopicDataFrame
    topics_by_type: Dict[str, List[str]] = field(default_factory=dict)  # message_type -> [topic_names]
    
    # === METADATA FOR PERSISTENCE ===
    # Minimal metadata needed for cache validation is now integrated (file_size, file_mtime)
    
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size / (1024 * 1024)
    
    # === ANALYSIS LEVEL CHECKS ===
    
    def has_quick_analysis(self) -> bool:
        """Check if quick analysis data is available"""
        return (self.analysis_level.value in ['quick', 'index'] and 
                len(self.topics) > 0 and 
                self.time_range is not None)
    
    def has_field_analysis(self) -> bool:
        """Check if message field analysis data is available"""
        return len(self.message_types) > 0
    
    def has_cached_messages(self) -> bool:
        """Check if cached messages data is available"""
        return len(self.cached_message_topics) > 0
    
    def has_message_index(self) -> bool:
        """Check if message index DataFrame is available"""
        return (self.analysis_level == AnalysisLevel.INDEX and 
                self.df is not None and 
                PANDAS_AVAILABLE)
    
    # === CONVENIENT ACCESS METHODS ===
    
    def find_topic(self, topic_name: str) -> Optional[TopicInfo]:
        """Find a topic by name"""
        for topic in self.topics:
            if isinstance(topic, str):
                if topic == topic_name:
                    # Create a minimal TopicInfo for string topics
                    return TopicInfo(name=topic, message_type="unknown")
            elif topic.name == topic_name:
                return topic
        return None
    
    def find_message_type(self, message_type: str) -> Optional[MessageTypeInfo]:
        """Find a message type by name"""
        for msg_type in self.message_types:
            if isinstance(msg_type, str):
                if msg_type == message_type:
                    # Create a minimal MessageTypeInfo for string message types
                    return MessageTypeInfo(message_type=msg_type)
            elif msg_type.message_type == message_type:
                return msg_type
        return None
    

    
    # === DATAFRAME MANAGEMENT METHODS ===
    
    def get_topic_dataframe(self, topic_name: str) -> Optional[Any]:
        """Get DataFrame for a specific topic"""
        topic = self.find_topic(topic_name)
        if topic and topic.has_dataframe():
            return topic.get_dataframe()
        return None
    
    def set_topic_dataframe(self, topic_name: str, df: Any) -> bool:
        """Set DataFrame for a specific topic"""
        topic = self.find_topic(topic_name)
        if topic:
            topic.set_dataframe(df)
            return True
        return False
    
    def has_topic_dataframe(self, topic_name: str) -> bool:
        """Check if a topic has a DataFrame"""
        topic = self.find_topic(topic_name)
        return topic.has_dataframe() if topic else False
    
    def get_topics_with_dataframes(self) -> List[str]:
        """Get list of topic names that have DataFrames"""
        return [topic.name for topic in self.topics if isinstance(topic, TopicInfo) and topic.has_dataframe()]
    
    def get_all_dataframes(self) -> Dict[str, Any]:
        """Get all DataFrames as a dictionary {topic_name: dataframe}"""
        result = {}
        for topic in self.topics:
            if isinstance(topic, TopicInfo) and topic.has_dataframe():
                result[topic.name] = topic.get_dataframe()
        return result
    
    def clear_topic_dataframe(self, topic_name: str) -> bool:
        """Clear DataFrame for a specific topic to free memory"""
        topic = self.find_topic(topic_name)
        if topic and topic.has_dataframe():
            topic.clear_dataframe()
            return True
        return False
    
    def clear_all_dataframes(self) -> int:
        """Clear all DataFrames to free memory. Returns count of cleared DataFrames."""
        count = 0
        for topic in self.topics:
            if isinstance(topic, TopicInfo) and topic.has_dataframe():
                topic.clear_dataframe()
                count += 1
        return count
    
    def get_dataframe_memory_summary(self) -> Dict[str, Any]:
        """Get memory usage summary for all DataFrames"""
        total_memory = 0
        topic_memory = {}
        
        for topic in self.topics:
            if isinstance(topic, TopicInfo) and topic.has_dataframe():
                memory_mb = topic.df_memory_mb or 0
                topic_memory[topic.name] = {
                    'memory_mb': memory_mb,
                    'message_count': topic.message_count or 0,
                    'message_type': topic.message_type,
                    'created_at': topic.df_created_at
                }
                total_memory += memory_mb
        
        return {
            'total_memory_mb': total_memory,
            'topic_count': len(topic_memory),
            'topics': topic_memory
        }
    
    def has_any_dataframes(self) -> bool:
        """Check if any topic has DataFrames"""
        return len(self.get_topics_with_dataframes()) > 0
    
    def has_message_index(self) -> bool:
        """Check if this bag has message index (DataFrames) - for backward compatibility"""
        return self.has_any_dataframes()
    
    def refresh_all_statistics_from_dataframes(self) -> int:
        """Refresh statistics for all topics that have DataFrames"""
        count = 0
        total_messages = 0
        total_size = 0
        
        for topic in self.topics:
            if isinstance(topic, TopicInfo) and topic.has_dataframe():
                topic.refresh_statistics_from_dataframe()
                count += 1
                # Accumulate totals
                if topic.message_count:
                    total_messages += topic.message_count
                if topic.total_size_bytes:
                    total_size += topic.total_size_bytes
        
        # Update total statistics
        if count > 0:
            self.total_messages = total_messages
            self.total_size = total_size
            
        return count
    
    def get_statistics_summary_all_topics(self) -> Dict[str, Any]:
        """Get statistics summary for all topics"""
        topics_stats = []
        total_messages = 0
        total_size = 0
        
        for topic in self.topics:
            if isinstance(topic, TopicInfo):
                stats = topic.get_statistics_summary()
                topics_stats.append(stats)
                
                if stats['message_count']:
                    total_messages += stats['message_count']
                if stats['total_size_bytes']:
                    total_size += stats['total_size_bytes']
        
        return {
            'bag_file': self.file_path,
            'total_topics': len(self.topics),
            'topics_with_dataframes': len(self.get_topics_with_dataframes()),
            'total_messages': total_messages,
            'total_size_bytes': total_size,
            'analysis_level': self.analysis_level.value,
            'topics': topics_stats
        }
    
    def get_topics(self) -> List[TopicInfo]:
        """Get list of topics"""
        return self.topics
    
    def get_topic_names(self) -> List[str]:
        """Get list of all topic names"""
        return [topic if isinstance(topic, str) else topic.name for topic in self.topics]
    
    def get_message_type_names(self) -> List[str]:
        """Get list of all message type names"""
        return [msg_type if isinstance(msg_type, str) else msg_type.message_type for msg_type in self.message_types]
    
    def get_topic_fields(self, topic_name: str) -> Optional[List[MessageFieldInfo]]:
        """Get field structure for a specific topic"""
        
        topic = self.find_topic(topic_name)
        if not topic:
            return None
        
        message_type_info = self.find_message_type(topic.message_type)
        if message_type_info:
            return message_type_info.fields
        return None
    
    def get_topic_field_paths(self, topic_name: str) -> List[str]:
        """Get flattened field paths for a specific topic"""
        
        fields = self.get_topic_fields(topic_name)
        if not fields:
            return []
        
        paths = []
        for field in fields:
            paths.extend(field.get_flattened_paths())
        
        return paths
    
    # === BUILDER METHODS FOR PARSER ===
    
    def add_topic(self, topic_info: TopicInfo) -> None:
        """Add a topic (used by parser during initialization)"""
        # Check if topic already exists, replace if so
        for i, existing_topic in enumerate(self.topics):
            if existing_topic.name == topic_info.name:
                self.topics[i] = topic_info
                return
        self.topics.append(topic_info)
    
    def add_message_type(self, message_type_info: MessageTypeInfo) -> None:
        """Add a message type (used by parser during initialization)"""
        # Check if message type already exists, replace if so
        for i, existing_type in enumerate(self.message_types):
            if existing_type.message_type == message_type_info.message_type:
                self.message_types[i] = message_type_info
                return
        self.message_types.append(message_type_info)
    

    
    def set_time_range(self, start_time: Tuple[int, int], end_time: Tuple[int, int]) -> None:
        """Set time range (used by parser)"""
        self.time_range = TimeRange(start_time=start_time, end_time=end_time)
        self.duration_seconds = self.time_range.get_duration_seconds()
    
    # === MEMORY MANAGEMENT ===
    # Removed runtime memory management for simplification

    
    # === SERIALIZATION (SIMPLIFIED) ===
    
    def to_json(self) -> str:
        """Serialize to JSON string (simplified without complex dict conversions)"""
        
        # Use dataclass's built-in serialization capabilities
        data = {
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_mtime': self.file_mtime,
            'analysis_level': self.analysis_level.value,
            'last_updated': self.last_updated,
            'duration_seconds': self.duration_seconds,
            'total_messages': self.total_messages,
            'total_size': self.total_size,
            
            # Serialize lists directly (much simpler than dict conversion)
            'topics': [
                {
                    'name': t.name,
                    'message_type': t.message_type,
                    'message_count': t.message_count,
                    'message_frequency': t.message_frequency,
                    'total_size_bytes': t.total_size_bytes,
                    'average_message_size': t.average_message_size,
                    'first_message_time': t.first_message_time,
                    'last_message_time': t.last_message_time,
                    'connection_id': t.connection_id
                } for t in self.topics
            ],
            
            'message_types': [
                {
                    'message_type': mt.message_type,
                    'definition': mt.definition,
                    'md5sum': mt.md5sum,
                    'fields': [
                        {
                            'field_name': f.field_name,
                            'field_type': f.field_type,
                            'is_array': f.is_array,
                            'array_size': f.array_size,
                            'is_builtin': f.is_builtin
                        } for f in (mt.fields or [])
                    ]
                } for mt in self.message_types
            ],
            
            'time_range': {
                'start_time': self.time_range.start_time,
                'end_time': self.time_range.end_time
            } if self.time_range else None,
            

            
            'cached_message_topics': self.cached_message_topics,
            
            # Serialize topic DataFrames
            'topic_dataframes_data': {
                topic_name: topic_df.to_json(orient='records', date_format='iso')
                for topic_name, topic_df in self.topic_dataframes.items()
                if topic_df is not None and PANDAS_AVAILABLE
            },
            'topics_by_type': self.topics_by_type
        }
        
        return json.dumps(data, indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ComprehensiveBagInfo':
        """Deserialize from JSON string (simplified)"""
        data = json.loads(json_str)
        
        # Create instance with basic fields
        instance = cls(
            file_path=data['file_path'],
            file_size=data['file_size'],
            file_mtime=data.get('file_mtime', 0.0),
            analysis_level=AnalysisLevel(data['analysis_level']),
            last_updated=data['last_updated'],
            duration_seconds=data.get('duration_seconds'),
            total_messages=data.get('total_messages'),
            total_size=data.get('total_size')
        )
        
        # Restore topics
        if 'topics' in data:
            for topic_data in data['topics']:
                topic = TopicInfo(**topic_data)
                instance.add_topic(topic)
        
        # Restore message types
        if 'message_types' in data:
            for mt_data in data['message_types']:
                fields = []
                if 'fields' in mt_data and mt_data['fields']:
                    for field_data in mt_data['fields']:
                        fields.append(MessageFieldInfo(**field_data))
                
                msg_type = MessageTypeInfo(
                    message_type=mt_data['message_type'],
                    definition=mt_data.get('definition'),
                    md5sum=mt_data.get('md5sum'),
                    fields=fields if fields else None
                )
                instance.add_message_type(msg_type)
        
        # Restore time range
        if 'time_range' in data and data['time_range']:
            tr_data = data['time_range']
            instance.time_range = TimeRange(
                start_time=tr_data['start_time'],
                end_time=tr_data['end_time']
            )
        
        # Restore statistics
        if 'topic_statistics' in data:
            for stats_data in data['topic_statistics']:
                stats = TopicStatistics(**stats_data)
                instance.add_topic_statistics(stats)
        
        # Restore cached message topics
        if 'cached_message_topics' in data:
            instance.cached_message_topics = data['cached_message_topics']
        
        # Restore topic DataFrames if available
        if 'topic_dataframes_data' in data and PANDAS_AVAILABLE:
            try:
                from io import StringIO
                for topic_name, df_json in data['topic_dataframes_data'].items():
                    topic_df = pd.read_json(StringIO(df_json), orient='records')
                    instance.topic_dataframes[topic_name] = topic_df
            except Exception as e:
                logger.warning(f"Failed to restore topic DataFrames: {e}")
        
        # Restore topics by type index
        if 'topics_by_type' in data:
            instance.topics_by_type = data['topics_by_type']
        
        # Restore metadata
        instance._access_count = data.get('_access_count', 0)
        instance._last_accessed = data.get('_last_accessed', time.time())
        
        return instance
    
    # === UTILITY METHODS ===
    
    def upgrade_analysis_level(self, new_level: AnalysisLevel) -> None:
        """Upgrade the analysis level"""
        if new_level.value in ['quick', 'full', 'index'] and self.analysis_level == AnalysisLevel.NONE:
            self.analysis_level = new_level
            self.last_updated = time.time()
        elif new_level == AnalysisLevel.FULL and self.analysis_level == AnalysisLevel.QUICK:
            self.analysis_level = new_level
            self.last_updated = time.time()
        elif new_level == AnalysisLevel.INDEX and self.analysis_level in [AnalysisLevel.QUICK, AnalysisLevel.FULL]:
            self.analysis_level = new_level
            self.last_updated = time.time()
    
    # === SMART DATAFRAME ACCESS METHODS ===
    
    def add_topic_dataframe(self, topic_name: str, topic_df: Any, message_type: str) -> None:
        """Add a topic DataFrame to the storage"""
        self.topic_dataframes[topic_name] = topic_df
        
        # Update type index
        if message_type not in self.topics_by_type:
            self.topics_by_type[message_type] = []
        if topic_name not in self.topics_by_type[message_type]:
            self.topics_by_type[message_type].append(topic_name)
    
    def get_topic_data(self, topic_name: str) -> Optional[Any]:
        """Get DataFrame for a specific topic"""
        return self.topic_dataframes.get(topic_name)
    
    def get_topics_by_type(self, message_type: str) -> List[str]:
        """Get all topics with a specific message type"""
        return self.topics_by_type.get(message_type, [])
    
    def get_all_topics(self) -> List[str]:
        """Get list of all topic names"""
        return list(self.topic_dataframes.keys())
    
    def query_topic(self, topic_name: str, time_start: Optional[float] = None, 
                   time_end: Optional[float] = None, **filters) -> Optional[Any]:
        """Query a topic with optional time filtering and other filters"""
        if not PANDAS_AVAILABLE:
            return None
            
        df = self.get_topic_data(topic_name)
        if df is None:
            return None
        
        result_df = df
        
        # Apply time filtering
        if time_start is not None or time_end is not None:
            if 'timestamp_sec' not in df.columns:
                logger.warning(f"Topic {topic_name} has no timestamp_sec column for time filtering")
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
    
    def create_unified_timeline(self, topics: Optional[List[str]] = None) -> Optional[Any]:
        """Create a unified timeline DataFrame with just timestamps and topics"""
        if not PANDAS_AVAILABLE:
            return None
        
        timeline_data = []
        topics_to_process = topics or self.get_all_topics()
        
        for topic_name in topics_to_process:
            topic_df = self.get_topic_data(topic_name)
            if topic_df is not None and 'timestamp_sec' in topic_df.columns:
                # Get message type for this topic
                message_type = 'unknown'
                for msg_type, topic_list in self.topics_by_type.items():
                    if topic_name in topic_list:
                        message_type = msg_type
                        break
                
                topic_timeline = pd.DataFrame({
                    'timestamp_sec': topic_df['timestamp_sec'],
                    'topic': topic_name,
                    'message_type': message_type,
                    'message_size': topic_df.get('message_size', None)
                })
                timeline_data.append(topic_timeline)
        
        if timeline_data:
            unified = pd.concat(timeline_data, ignore_index=True)
            return unified.sort_values('timestamp_sec').reset_index(drop=True)
        
        return None
    
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
        from pathlib import Path
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        exported_files = {}
        
        topics_to_export = topic_filter or self.get_all_topics()
        
        for topic_name in topics_to_export:
            clean_name = topic_name.replace('/', '_').replace(':', '_')
            csv_path = output_dir / f"{clean_name}.csv"
            
            if self.export_topic_csv(topic_name, csv_path):
                exported_files[topic_name] = csv_path
        
        return exported_files
    
    def get_dataframe_stats(self) -> Dict[str, Any]:
        """Get comprehensive DataFrame statistics"""
        total_messages = 0
        total_memory = 0
        
        topic_stats = {}
        for topic_name, topic_df in self.topic_dataframes.items():
            if topic_df is not None and PANDAS_AVAILABLE:
                message_count = len(topic_df)
                memory_usage = topic_df.memory_usage(deep=True).sum()
                
                total_messages += message_count
                total_memory += memory_usage
                
                topic_stats[topic_name] = {
                    'message_count': message_count,
                    'memory_mb': memory_usage / 1024 / 1024,
                    'columns': len(topic_df.columns)
                }
        
        return {
            'total_topics': len(self.topic_dataframes),
            'total_messages': total_messages,
            'total_memory_mb': total_memory / 1024 / 1024,
            'topics_by_type': {k: len(v) for k, v in self.topics_by_type.items()},
            'topic_stats': topic_stats
        }

    def __str__(self) -> str:
        """String representation for debugging"""
        return f"ComprehensiveBagInfo(file='{self.file_path}', level={self.analysis_level.value}, topics={len(self.topics)})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"ComprehensiveBagInfo(file_path='{self.file_path}', "
                f"analysis_level={self.analysis_level.value}, "
                f"topics={len(self.topics)}, "
                f"memory_mb={self.get_memory_footprint() / (1024 * 1024):.2f}, "
                f"access_count={self._access_count})")