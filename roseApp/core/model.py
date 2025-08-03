"""
Core data models for ROS bag processing
Contains the primary data structures used throughout the application
"""
import json
import pickle
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple, Set
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
    average_message_size: Optional[float] = None  # Average message size in bytes
    first_message_time: Optional[Tuple[int, int]] = None  # (sec, nsec)
    last_message_time: Optional[Tuple[int, int]] = None   # (sec, nsec)
    connection_id: Optional[str] = None  # Connection identifier for rosbag connections
    
    
    @property
    def count(self) -> str:
        """Get message count"""
        return f"{self.message_count or 'N.A'}"
    
    @property
    def frequency(self) -> str:
        """Get message frequency"""
        return f"{self.message_frequency or 'N.A'} Hz"
    
    @property
    def size(self) -> str:
        """Get total size in bytes"""
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'message_type': self.message_type,
            'message_count': self.message_count,
            'message_frequency': self.message_frequency,
            'total_size_bytes': self.total_size_bytes,
            'average_message_size': self.average_message_size,
            'first_message_time': self.first_message_time,
            'last_message_time': self.last_message_time,
            'connection_id': self.connection_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopicInfo':
        """Create from dictionary"""
        return cls(**data)



@dataclass
class MessageFieldInfo:
    """Information about a message field structure"""
    field_name: str
    field_type: str
    is_array: bool = False
    array_size: Optional[int] = None  # None for dynamic arrays
    is_builtin: bool = True
    nested_fields: Optional[Dict[str, 'MessageFieldInfo']] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {
            'field_name': self.field_name,
            'field_type': self.field_type,
            'is_array': self.is_array,
            'array_size': self.array_size,
            'is_builtin': self.is_builtin
        }
        
        if self.nested_fields:
            result['nested_fields'] = {
                k: v.to_dict() for k, v in self.nested_fields.items()
            }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageFieldInfo':
        """Create from dictionary"""
        nested_fields = None
        if 'nested_fields' in data and data['nested_fields']:
            nested_fields = {
                k: cls.from_dict(v) for k, v in data['nested_fields'].items()
            }
        
        return cls(
            field_name=data['field_name'],
            field_type=data['field_type'],
            is_array=data.get('is_array', False),
            array_size=data.get('array_size'),
            is_builtin=data.get('is_builtin', True),
            nested_fields=nested_fields
        )
    
    def get_flattened_paths(self, prefix: str = '') -> List[str]:
        """Get all flattened field paths"""
        current_path = f"{prefix}.{self.field_name}" if prefix else self.field_name
        paths = [current_path]
        
        if self.nested_fields:
            for nested_field in self.nested_fields.values():
                paths.extend(nested_field.get_flattened_paths(current_path))
        
        return paths


@dataclass
class MessageTypeInfo:
    """Complete information about a ROS message type"""
    message_type: str
    definition: Optional[str] = None
    md5sum: Optional[str] = None
    fields: Optional[Dict[str, MessageFieldInfo]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {
            'message_type': self.message_type,
            'definition': self.definition,
            'md5sum': self.md5sum
        }
        
        if self.fields:
            result['fields'] = {
                k: v.to_dict() for k, v in self.fields.items()
            }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageTypeInfo':
        """Create from dictionary"""
        fields = None
        if 'fields' in data and data['fields']:
            fields = {
                k: MessageFieldInfo.from_dict(v) for k, v in data['fields'].items()
            }
        
        return cls(
            message_type=data['message_type'],
            definition=data.get('definition'),
            md5sum=data.get('md5sum'),
            fields=fields
        )
    
    def get_all_field_paths(self) -> List[str]:
        """Get all flattened field paths for this message type"""
        if not self.fields:
            return []
        
        paths = []
        for field in self.fields.values():
            paths.extend(field.get_flattened_paths())
        
        return paths


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
    
    def to_tuple(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Convert to tuple format for backward compatibility"""
        return (self.start_time, self.end_time)
    
    @classmethod
    def from_tuple(cls, time_range: Tuple[Tuple[int, int], Tuple[int, int]]) -> 'TimeRange':
        """Create from tuple format"""
        return cls(start_time=time_range[0], end_time=time_range[1])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'start_time': self.start_time,
            'end_time': self.end_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeRange':
        """Create from dictionary"""
        return cls(
            start_time=data['start_time'],
            end_time=data['end_time']
        )


@dataclass
class ComprehensiveBagInfo:
    """
    Comprehensive bag information data structure organized by analysis level
    
    This is the core data structure for the entire application. Every bag operation
    (parsing, caching, extraction, export) uses this as the single source of truth.
    
    Features:
    - Hierarchical analysis levels (NONE -> QUICK -> FULL)
    - Persistent storage support (JSON/pickle)
    - Memory management for efficient caching
    - Extensible field structure for future enhancements
    
    Fields are grouped by the analysis level required to obtain them:
    - Basic metadata: Always available
    - Quick analysis: Topics, connections, time info, field structures  
    - Full analysis: Message counts, sizes, detailed statistics
    """
    
    # === BASIC METADATA (always present) ===
    file_path: str
    file_size: int
    analysis_level: AnalysisLevel = AnalysisLevel.NONE
    last_updated: float = field(default_factory=time.time)
    
    # === QUICK ANALYSIS DATA ===
    # Enhanced topic and connection information
    topics: Optional[Dict[str, TopicInfo]] = None  # topic_name -> TopicInfo
    connections: Optional[Dict[str, str]] = None  
    message_types: Optional[Dict[str, MessageTypeInfo]] = None  # message_type -> MessageTypeInfo
    
    # Time information
    time_range: Optional[TimeRange] = None
    duration_seconds: Optional[float] = None
    
    # Legacy compatibility fields (deprecated, use structured fields above)
    _legacy_topics: Optional[List[str]] = field(default=None, init=False)  # For backward compatibility
    _legacy_connections: Optional[Dict[str, str]] = field(default=None, init=False)  # For backward compatibility
    _legacy_message_definitions: Optional[Dict[str, str]] = field(default=None, init=False)  # For backward compatibility
    _legacy_message_fields: Optional[Dict[str, Dict[str, Any]]] = field(default=None, init=False)  # For backward compatibility
    
    # === FULL ANALYSIS DATA (requires message traversal) ===
    # Message statistics
    message_counts: Optional[Dict[str, int]] = None
    topic_sizes: Optional[Dict[str, int]] = None
    topic_stats: Optional[Dict[str, Dict[str, int]]] = None  # detailed per-topic stats
    
    # Overall statistics
    total_messages: Optional[int] = None
    total_size: Optional[int] = None
    
    # === OPTIONAL CACHED DATA ===
    cached_messages: Optional[Dict[str, List[Any]]] = None
    
    # === METADATA FOR PERSISTENCE AND MEMORY MANAGEMENT ===
    _memory_footprint: Optional[int] = field(default=None, init=False)
    _access_count: int = field(default=0, init=False)
    _last_accessed: float = field(default_factory=time.time, init=False)
    
    def __post_init__(self):
        """Initialize computed fields after creation"""
        self._calculate_memory_footprint()
        self._last_accessed = time.time()
    
    # === ANALYSIS LEVEL CHECKS ===
    
    def has_quick_analysis(self) -> bool:
        """Check if quick analysis data is available"""
        return (self.analysis_level.value in ['quick', 'full'] and 
                self.topics is not None and 
                self.connections is not None and 
                self.time_range is not None)
    
    def has_full_analysis(self) -> bool:
        """Check if full analysis data is available"""
        return (self.analysis_level == AnalysisLevel.FULL and 
                self.total_messages is not None and 
                self.total_size is not None)
    
    def has_field_analysis(self) -> bool:
        """Check if message field analysis data is available"""
        return self.message_types is not None and len(self.message_types) > 0
    
    def has_cached_messages(self) -> bool:
        """Check if cached messages data is available"""
        return self.cached_messages is not None and len(self.cached_messages) > 0
    
    # === NEW STRUCTURED DATA ACCESS METHODS ===
    
    def get_topic_names(self) -> List[str]:
        """Get list of topic names"""
        self._record_access()
        return list(self.topics.keys()) if self.topics else []
    
    def get_topic_info(self, topic_name: str) -> Optional[TopicInfo]:
        """Get detailed information for a specific topic"""
        self._record_access()
        return self.topics.get(topic_name) if self.topics else None
    
    def get_message_types(self) -> List[str]:
        """Get list of message types used in the bag"""
        self._record_access()
        return list(self.message_types.keys()) if self.message_types else []
    
    def get_message_type_info(self, message_type: str) -> Optional[MessageTypeInfo]:
        """Get detailed information for a specific message type"""
        self._record_access()
        return self.message_types.get(message_type) if self.message_types else None
    
    def get_topics_by_message_type(self, message_type: str) -> List[str]:
        """Get all topics that use a specific message type"""
        self._record_access()
        if not self.topics:
            return []
        
        return [
            topic_name for topic_name, topic_info in self.topics.items()
            if topic_info.message_type == message_type
        ]
    
    def get_connection_by_topic(self, topic_name: str) -> Optional[Dict[str, str]]:
        """Get connection information for a specific topic"""
        self._record_access()
        if not self.topics or not self.connections:
            return None
        
        topic_info = self.topics.get(topic_name)
        if topic_info and topic_info.connection_id is not None:
            return self.connections.get(topic_info.connection_id)
        return None
    
    def get_topic_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive statistics for all topics"""
        self._record_access()
        if not self.topics:
            return {}
        
        stats = {}
        for topic_name, topic_info in self.topics.items():
            stats[topic_name] = {
                'message_type': topic_info.message_type,
                'message_count': topic_info.message_count,
                'message_frequency': topic_info.message_frequency,
                'total_size_bytes': topic_info.total_size_bytes,
                'average_message_size': topic_info.average_message_size,
                'duration_seconds': topic_info.get_duration_seconds()
            }
        
        return stats
    
    # === DATA ACCESS METHODS ===
    
    def get_topic_fields(self, topic: str) -> Optional[Dict[str, MessageFieldInfo]]:
        """Get field structure for a specific topic"""
        self._record_access()
        
        if not self.has_field_analysis() or not self.topics:
            return None
        
        topic_info = self.topics.get(topic)
        if topic_info and self.message_types:
            message_type_info = self.message_types.get(topic_info.message_type)
            if message_type_info:
                return message_type_info.fields
        return None
    
    def get_topic_field_paths(self, topic: str) -> List[str]:
        """Get flattened field paths for a specific topic"""
        self._record_access()
        
        fields = self.get_topic_fields(topic)
        if not fields:
            return []
        
        paths = []
        for field in fields.values():
            paths.extend(field.get_flattened_paths())
        
        return paths
    
    def get_meta(self) -> Dict[str, Any]:
        """Get basic metadata dictionary"""
        self._record_access()
        
        meta = {
            'file_path': self.file_path,
            'analysis_level': self.analysis_level.value,
            'last_updated': self.last_updated
        }
        
        if self.has_quick_analysis():
            meta.update({
                'topic_count': len(self.topics) if self.topics else 0,
                'duration_seconds': self.duration_seconds,
                'time_range': self.time_range,
                'has_field_analysis': self.has_field_analysis()
            })
        
        if self.has_full_analysis():
            meta.update({
                'total_messages': self.total_messages,
                'total_size': self.total_size
            })
        
        return meta
    
    # === PERSISTENCE METHODS ===
    
    def to_json(self, include_cached_messages: bool = False) -> str:
        """
        Serialize to JSON string
        
        Args:
            include_cached_messages: Whether to include cached message data
        
        Returns:
            JSON string representation
        """
        self._record_access()
        
        data = {
            'file_path': self.file_path,
            'analysis_level': self.analysis_level.value,
            'last_updated': self.last_updated,
            'topics': {k: v.to_dict() for k, v in self.topics.items()} if self.topics else None,
            'connections': self.connections,
            'message_types': {k: v.to_dict() for k, v in self.message_types.items()} if self.message_types else None,
            'time_range': self.time_range.to_dict() if self.time_range else None,
            'duration_seconds': self.duration_seconds,
            'message_counts': self.message_counts,
            'topic_sizes': self.topic_sizes,
            'topic_stats': self.topic_stats,
            'total_messages': self.total_messages,
            'total_size': self.total_size,
            '_access_count': self._access_count,
            '_last_accessed': self._last_accessed
        }
        
        if include_cached_messages:
            # Convert cached messages to serializable format
            if self.cached_messages:
                serializable_messages = {}
                for topic, messages in self.cached_messages.items():
                    # Convert messages to dict format for JSON serialization
                    serializable_messages[topic] = [
                        msg if isinstance(msg, dict) else str(msg) 
                        for msg in messages
                    ]
                data['cached_messages'] = serializable_messages
        
        return json.dumps(data, indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ComprehensiveBagInfo':
        """
        Deserialize from JSON string
        
        Args:
            json_str: JSON string representation
        
        Returns:
            ComprehensiveBagInfo instance
        """
        data = json.loads(json_str)
        
        # Convert analysis_level back to enum
        if 'analysis_level' in data:
            data['analysis_level'] = AnalysisLevel(data['analysis_level'])
        
        # Convert topics back to TopicInfo objects
        if 'topics' in data and data['topics']:
            topics_dict = {}
            for topic_name, topic_data in data['topics'].items():
                topics_dict[topic_name] = TopicInfo.from_dict(topic_data)
            data['topics'] = topics_dict
        
        # Convert message_types back to MessageTypeInfo objects
        if 'message_types' in data and data['message_types']:
            message_types_dict = {}
            for msg_type, msg_data in data['message_types'].items():
                message_types_dict[msg_type] = MessageTypeInfo.from_dict(msg_data)
            data['message_types'] = message_types_dict
        
        # Convert time_range back to TimeRange object
        if 'time_range' in data and data['time_range']:
            data['time_range'] = TimeRange.from_dict(data['time_range'])
        
        # Handle special fields
        access_count = data.pop('_access_count', 0)
        last_accessed = data.pop('_last_accessed', time.time())
        
        # Create instance
        instance = cls(**data)
        instance._access_count = access_count
        instance._last_accessed = last_accessed
        
        return instance
    
    def save_to_file(self, file_path: Union[str, Path], format: str = 'json', 
                     include_cached_messages: bool = False) -> None:
        """
        Save to file
        
        Args:
            file_path: Target file path
            format: 'json' or 'pickle'
            include_cached_messages: Whether to include cached message data
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if format.lower() == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.to_json(include_cached_messages))
            elif format.lower() == 'pickle':
                with open(file_path, 'wb') as f:
                    pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            logger.debug(f"Saved ComprehensiveBagInfo to {file_path} (format: {format})")
            
        except Exception as e:
            logger.error(f"Failed to save ComprehensiveBagInfo to {file_path}: {e}")
            raise
    
    @classmethod
    def load_from_file(cls, file_path: Union[str, Path], format: str = 'auto') -> 'ComprehensiveBagInfo':
        """
        Load from file
        
        Args:
            file_path: Source file path
            format: 'json', 'pickle', or 'auto' (detect from extension)
        
        Returns:
            ComprehensiveBagInfo instance
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Auto-detect format
        if format == 'auto':
            if file_path.suffix.lower() == '.json':
                format = 'json'
            elif file_path.suffix.lower() in ['.pkl', '.pickle']:
                format = 'pickle'
            else:
                # Try JSON first, then pickle
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                    format = 'json'
                except:
                    format = 'pickle'
        
        try:
            if format.lower() == 'json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return cls.from_json(f.read())
            elif format.lower() == 'pickle':
                with open(file_path, 'rb') as f:
                    instance = pickle.load(f)
                    # Ensure it's the right type
                    if not isinstance(instance, cls):
                        raise TypeError(f"Loaded object is not ComprehensiveBagInfo: {type(instance)}")
                    return instance
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            logger.error(f"Failed to load ComprehensiveBagInfo from {file_path}: {e}")
            raise
    
    # === MEMORY MANAGEMENT METHODS ===
    
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
            
            # Quick analysis data
            if self.topics:
                footprint += sys.getsizeof(self.topics)
                footprint += sum(sys.getsizeof(str(t)) for t in self.topics.values())
            if self.connections:
                footprint += sys.getsizeof(self.connections)
                footprint += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.connections.items())
            if self.message_types:
                footprint += sys.getsizeof(self.message_types)
                footprint += sum(sys.getsizeof(str(mt)) for mt in self.message_types.values())
            if self.time_range:
                footprint += sys.getsizeof(self.time_range)
            
            # Full analysis data
            if self.message_counts:
                footprint += sys.getsizeof(self.message_counts)
                footprint += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.message_counts.items())
            if self.topic_sizes:
                footprint += sys.getsizeof(self.topic_sizes)
                footprint += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.topic_sizes.items())
            if self.topic_stats:
                footprint += sys.getsizeof(self.topic_stats)
                footprint += sum(sys.getsizeof(str(v)) for v in self.topic_stats.values()) * 2
            
            # Cached messages (can be large)
            if self.cached_messages:
                footprint += sys.getsizeof(self.cached_messages)
                for topic, messages in self.cached_messages.items():
                    footprint += sys.getsizeof(topic)
                    footprint += sys.getsizeof(messages)
                    footprint += sum(sys.getsizeof(str(msg)) for msg in messages)
            
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
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory management information"""
        return {
            'memory_footprint_bytes': self.get_memory_footprint(),
            'memory_footprint_mb': self.get_memory_footprint() / (1024 * 1024),
            'access_count': self._access_count,
            'last_accessed': self._last_accessed,
            'age_seconds': time.time() - self._last_accessed,
            'has_cached_messages': self.has_cached_messages(),
            'cached_message_topics': list(self.cached_messages.keys()) if self.cached_messages else []
        }
    
    def clear_cached_messages(self) -> None:
        """Clear cached messages to free memory"""
        if self.cached_messages:
            self.cached_messages.clear()
            self.cached_messages = None
            self._calculate_memory_footprint()
            logger.debug(f"Cleared cached messages for {self.file_path}")
    
    def is_stale(self, max_age_seconds: float = 3600) -> bool:
        """Check if the data is stale based on last access time"""
        return (time.time() - self._last_accessed) > max_age_seconds
    
    def should_evict(self, max_age_seconds: float = 3600, 
                     min_access_count: int = 1) -> bool:
        """Determine if this instance should be evicted from memory"""
        return (self.is_stale(max_age_seconds) and 
                self._access_count < min_access_count)
    
    # === UTILITY METHODS ===
    
    def clone(self, include_cached_messages: bool = False) -> 'ComprehensiveBagInfo':
        """Create a deep copy of this instance"""
        json_str = self.to_json(include_cached_messages)
        return self.from_json(json_str)
    
    def upgrade_analysis_level(self, new_level: AnalysisLevel) -> None:
        """Upgrade the analysis level (used when more detailed analysis is performed)"""
        if new_level.value in ['quick', 'full'] and self.analysis_level == AnalysisLevel.NONE:
            self.analysis_level = new_level
            self.last_updated = time.time()
        elif new_level == AnalysisLevel.FULL and self.analysis_level == AnalysisLevel.QUICK:
            self.analysis_level = new_level
            self.last_updated = time.time()
    
    def __str__(self) -> str:
        """String representation for debugging"""
        return f"ComprehensiveBagInfo(file='{self.file_path}', level={self.analysis_level.value}, topics={len(self.topics) if self.topics else 0})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"ComprehensiveBagInfo(file_path='{self.file_path}', "
                f"analysis_level={self.analysis_level.value}, "
                f"topics={len(self.topics) if self.topics else 0}, "
                f"memory_mb={self.get_memory_footprint() / (1024 * 1024):.2f}, "
                f"access_count={self._access_count})")