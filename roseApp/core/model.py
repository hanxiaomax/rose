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
from typing import Dict, List, Optional, Union, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class AnalysisLevel(Enum):
    """Analysis depth levels for bag processing"""
    NONE = "none"      # No analysis performed
    QUICK = "quick"    # Basic metadata without message traversal
    FULL = "full"      # Full statistics with message traversal


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
    analysis_level: AnalysisLevel = AnalysisLevel.NONE
    last_updated: float = field(default_factory=time.time)
    
    # === QUICK ANALYSIS DATA ===
    # Topic and connection information
    topics: Optional[List[str]] = None
    connections: Optional[Dict[str, str]] = None  # topic -> message_type
    
    # Time information
    time_range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    duration_seconds: Optional[float] = None
    
    # Message structure information (from connection metadata)
    message_definitions: Optional[Dict[str, str]] = None  # message_type -> definition
    message_fields: Optional[Dict[str, Dict[str, Any]]] = None  # message_type -> field_structure
    
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
                self.message_counts is not None and 
                self.topic_stats is not None)
    
    def has_field_analysis(self) -> bool:
        """Check if message field analysis data is available"""
        return (self.message_definitions is not None and 
                self.message_fields is not None)
    
    def has_cached_messages(self) -> bool:
        """Check if cached messages data is available"""
        return self.cached_messages is not None and len(self.cached_messages) > 0
    
    # === DATA ACCESS METHODS ===
    
    def get_topic_fields(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get field structure for a specific topic"""
        self._record_access()
        
        if not self.has_field_analysis() or not self.connections:
            return None
        
        message_type = self.connections.get(topic)
        if message_type and self.message_fields:
            return self.message_fields.get(message_type)
        return None
    
    def get_topic_field_paths(self, topic: str) -> List[str]:
        """Get flattened field paths for a specific topic"""
        self._record_access()
        
        fields = self.get_topic_fields(topic)
        if not fields:
            return []
        
        paths = []
        def extract_paths(field_dict, prefix=""):
            for field_name, field_info in field_dict.items():
                current_path = f"{prefix}.{field_name}" if prefix else field_name
                paths.append(current_path)
                
                if isinstance(field_info, dict) and 'fields' in field_info:
                    extract_paths(field_info['fields'], current_path)
        
        extract_paths(fields)
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
            'topics': self.topics,
            'connections': self.connections,
            'time_range': self.time_range,
            'duration_seconds': self.duration_seconds,
            'message_definitions': self.message_definitions,
            'message_fields': self.message_fields,
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
                footprint += sys.getsizeof(self.topics) + sum(sys.getsizeof(t) for t in self.topics)
            if self.connections:
                footprint += sys.getsizeof(self.connections)
                footprint += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.connections.items())
            if self.time_range:
                footprint += sys.getsizeof(self.time_range)
            if self.message_definitions:
                footprint += sys.getsizeof(self.message_definitions)
                footprint += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.message_definitions.items())
            if self.message_fields:
                footprint += sys.getsizeof(self.message_fields)
                # Approximate nested dict size
                footprint += sum(sys.getsizeof(str(v)) for v in self.message_fields.values()) * 2
            
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