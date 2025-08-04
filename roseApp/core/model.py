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

logger = logging.getLogger(__name__)


class AnalysisLevel(Enum):
    """Analysis depth levels for bag processing"""
    NONE = "none"      # No analysis performed
    QUICK = "quick"    # Basic metadata without message traversal
    FULL = "full"      # Full statistics with message traversal


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
class TopicStatistics:
    """Statistics for a single topic"""
    topic_name: str
    message_count: int = 0
    total_size_bytes: int = 0
    average_message_size: int = 0
    min_message_size: int = 0
    max_message_size: int = 0


@dataclass
class ComprehensiveBagInfo:
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
    analysis_level: AnalysisLevel = AnalysisLevel.NONE
    last_updated: float = field(default_factory=time.time)
    
    # === QUICK ANALYSIS DATA ===
    # Use lists instead of dictionaries for better performance and simpler access
    topics: List[TopicInfo] = field(default_factory=list)
    message_types: List[MessageTypeInfo] = field(default_factory=list)
    
    # Time information
    time_range: Optional[TimeRange] = None
    duration_seconds: Optional[float] = None
    
    # === FULL ANALYSIS DATA ===
    # Statistics organized as list of objects instead of nested dictionaries
    topic_statistics: List[TopicStatistics] = field(default_factory=list)
    total_messages: Optional[int] = None
    total_size: Optional[int] = None
    
    # === OPTIONAL CACHED DATA ===
    # Keep this as simple structure since it's optional
    cached_message_topics: List[str] = field(default_factory=list)
    
    # === METADATA FOR PERSISTENCE AND MEMORY MANAGEMENT ===
    _memory_footprint: Optional[int] = field(default=None, init=False)
    _access_count: int = field(default=0, init=False)
    _last_accessed: float = field(default_factory=time.time, init=False)
    
    def __post_init__(self):
        """Initialize computed fields after creation"""
        self._calculate_memory_footprint()
        self._last_accessed = time.time()
    
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size / (1024 * 1024)
    
    # === ANALYSIS LEVEL CHECKS ===
    
    def has_quick_analysis(self) -> bool:
        """Check if quick analysis data is available"""
        return (self.analysis_level.value in ['quick', 'full'] and 
                len(self.topics) > 0 and 
                self.time_range is not None)
    
    def has_full_analysis(self) -> bool:
        """Check if full analysis data is available"""
        return (self.analysis_level == AnalysisLevel.FULL and 
                self.total_messages is not None and 
                self.total_size is not None)
    
    def has_field_analysis(self) -> bool:
        """Check if message field analysis data is available"""
        return len(self.message_types) > 0
    
    def has_cached_messages(self) -> bool:
        """Check if cached messages data is available"""
        return len(self.cached_message_topics) > 0
    
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
    
    def find_topic_statistics(self, topic_name: str) -> Optional[TopicStatistics]:
        """Find statistics for a topic"""
        for stats in self.topic_statistics:
            if stats.topic_name == topic_name:
                return stats
        return None
    
    def get_topics(self) -> List[TopicInfo]:
        """Get list of topics"""
        return self.topics
    
    def get_topic_names(self) -> List[str]:
        """Get list of all topic names"""
        self._record_access()
        return [topic if isinstance(topic, str) else topic.name for topic in self.topics]
    
    def get_message_type_names(self) -> List[str]:
        """Get list of all message type names"""
        self._record_access()
        return [msg_type if isinstance(msg_type, str) else msg_type.message_type for msg_type in self.message_types]
    
    def get_topic_fields(self, topic_name: str) -> Optional[List[MessageFieldInfo]]:
        """Get field structure for a specific topic"""
        self._record_access()
        
        topic = self.find_topic(topic_name)
        if not topic:
            return None
        
        message_type_info = self.find_message_type(topic.message_type)
        if message_type_info:
            return message_type_info.fields
        return None
    
    def get_topic_field_paths(self, topic_name: str) -> List[str]:
        """Get flattened field paths for a specific topic"""
        self._record_access()
        
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
    
    def add_topic_statistics(self, stats: TopicStatistics) -> None:
        """Add topic statistics (used by parser during full analysis)"""
        # Check if statistics already exist, replace if so
        for i, existing_stats in enumerate(self.topic_statistics):
            if existing_stats.topic_name == stats.topic_name:
                self.topic_statistics[i] = stats
                return
        self.topic_statistics.append(stats)
    
    def set_time_range(self, start_time: Tuple[int, int], end_time: Tuple[int, int]) -> None:
        """Set time range (used by parser)"""
        self.time_range = TimeRange(start_time=start_time, end_time=end_time)
        self.duration_seconds = self.time_range.get_duration_seconds()
    
    # === MEMORY MANAGEMENT ===
    
    def _record_access(self) -> None:
        """Record access for memory management"""
        self._access_count += 1
        self._last_accessed = time.time()
    
    def _calculate_memory_footprint(self) -> int:
        """Calculate approximate memory footprint in bytes"""
        try:
            import sys
            
            footprint = 0
            
            # Basic fields
            footprint += sys.getsizeof(self.file_path)
            footprint += sys.getsizeof(self.analysis_level)
            footprint += sys.getsizeof(self.last_updated)
            
            # Topics list
            footprint += sys.getsizeof(self.topics)
            footprint += sum(sys.getsizeof(topic) for topic in self.topics)
            
            # Message types list
            footprint += sys.getsizeof(self.message_types)
            footprint += sum(sys.getsizeof(msg_type) for msg_type in self.message_types)
            
            # Time range
            if self.time_range:
                footprint += sys.getsizeof(self.time_range)
            
            # Statistics
            footprint += sys.getsizeof(self.topic_statistics)
            footprint += sum(sys.getsizeof(stats) for stats in self.topic_statistics)
            
            # Cached message topics
            footprint += sys.getsizeof(self.cached_message_topics)
            footprint += sum(sys.getsizeof(topic) for topic in self.cached_message_topics)
            
            self._memory_footprint = footprint
            return footprint
            
        except Exception as e:
            logger.warning(f"Failed to calculate memory footprint: {e}")
            self._memory_footprint = 0
            return 0
    
    def get_memory_footprint(self) -> int:
        """Get current memory footprint in bytes"""
        if self._memory_footprint is None:
            return self._calculate_memory_footprint()
        return self._memory_footprint
    
    def is_stale(self, max_age_seconds: float = 3600) -> bool:
        """Check if the data is stale based on last access time"""
        return (time.time() - self._last_accessed) > max_age_seconds
    
    def should_evict(self, max_age_seconds: float = 3600, 
                     min_access_count: int = 1) -> bool:
        """Determine if this instance should be evicted from memory"""
        return (self.is_stale(max_age_seconds) and 
                self._access_count < min_access_count)
    
    # === SERIALIZATION (SIMPLIFIED) ===
    
    def to_json(self) -> str:
        """Serialize to JSON string (simplified without complex dict conversions)"""
        self._record_access()
        
        # Use dataclass's built-in serialization capabilities
        data = {
            'file_path': self.file_path,
            'file_size': self.file_size,
            'analysis_level': self.analysis_level.value,
            'last_updated': self.last_updated,
            'duration_seconds': self.duration_seconds,
            'total_messages': self.total_messages,
            'total_size': self.total_size,
            '_access_count': self._access_count,
            '_last_accessed': self._last_accessed,
            
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
            
            'topic_statistics': [
                {
                    'topic_name': ts.topic_name,
                    'message_count': ts.message_count,
                    'total_size_bytes': ts.total_size_bytes,
                    'average_message_size': ts.average_message_size,
                    'min_message_size': ts.min_message_size,
                    'max_message_size': ts.max_message_size
                } for ts in self.topic_statistics
            ],
            
            'cached_message_topics': self.cached_message_topics
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
        
        # Restore metadata
        instance._access_count = data.get('_access_count', 0)
        instance._last_accessed = data.get('_last_accessed', time.time())
        
        return instance
    
    # === UTILITY METHODS ===
    
    def upgrade_analysis_level(self, new_level: AnalysisLevel) -> None:
        """Upgrade the analysis level"""
        if new_level.value in ['quick', 'full'] and self.analysis_level == AnalysisLevel.NONE:
            self.analysis_level = new_level
            self.last_updated = time.time()
        elif new_level == AnalysisLevel.FULL and self.analysis_level == AnalysisLevel.QUICK:
            self.analysis_level = new_level
            self.last_updated = time.time()
    
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