"""
Unified analyzer system for Rose.

This module provides comprehensive bag analysis capabilities including
async processing, message type analysis, and intelligent caching.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from enum import Enum

from roseApp.core.util import get_logger
from roseApp.core.cache import get_cache

_logger = get_logger("analyzer")


class AnalysisType(Enum):
    """Types of analysis that can be performed"""
    METADATA = "metadata"
    STATISTICS = "statistics"
    FIELD_ANALYSIS = "field_analysis"
    TOPIC_ANALYSIS = "topic_analysis"
    FULL_ANALYSIS = "full_analysis"


@dataclass
class BagInfo:
    """Basic information about a ROS bag file"""
    path: Path
    size_bytes: int
    topics: Set[str]
    message_counts: Dict[str, int]
    time_range: Tuple[Tuple[int, int], Tuple[int, int]]  # ((start_sec, start_nsec), (end_sec, end_nsec))
    connections: Dict[str, str]  # topic -> message_type
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.duration_seconds == 0.0:
            start_time = self.time_range[0][0] + self.time_range[0][1] / 1e9
            end_time = self.time_range[1][0] + self.time_range[1][1] / 1e9
            self.duration_seconds = end_time - start_time


@dataclass
class FieldInfo:
    """Information about a message field"""
    name: str
    type_name: str
    is_array: bool = False
    array_size: Optional[int] = None
    nested_fields: Optional[Dict[str, 'FieldInfo']] = None
    
    def __post_init__(self):
        if self.nested_fields is None:
            self.nested_fields = {}


@dataclass
class MessageTypeInfo:
    """Information about a ROS message type"""
    type_name: str
    fields: Dict[str, FieldInfo]
    definition: Optional[str] = None
    md5sum: Optional[str] = None
    
    def get_field_paths(self, prefix: str = "") -> List[str]:
        """Get all field paths in dot notation"""
        paths = []
        for field_name, field_info in self.fields.items():
            current_path = f"{prefix}.{field_name}" if prefix else field_name
            paths.append(current_path)
            
            if field_info.nested_fields:
                nested_paths = self._get_nested_paths(field_info.nested_fields, current_path)
                paths.extend(nested_paths)
        
        return paths
    
    def _get_nested_paths(self, fields: Dict[str, FieldInfo], prefix: str) -> List[str]:
        """Recursively get nested field paths"""
        paths = []
        for field_name, field_info in fields.items():
            current_path = f"{prefix}.{field_name}"
            paths.append(current_path)
            
            if field_info.nested_fields:
                nested_paths = self._get_nested_paths(field_info.nested_fields, current_path)
                paths.extend(nested_paths)
        
        return paths


@dataclass
class AnalysisResult:
    """Result of bag analysis"""
    bag_info: BagInfo
    message_types: Dict[str, MessageTypeInfo]
    analysis_type: AnalysisType
    analysis_time: float
    cached: bool = False
    errors: List[str] = field(default_factory=list)
    
    def get_topic_field_paths(self, topic: str) -> List[str]:
        """Get all field paths for a specific topic"""
        if topic not in self.bag_info.connections:
            return []
        
        msg_type = self.bag_info.connections[topic]
        if msg_type not in self.message_types:
            return []
        
        return self.message_types[msg_type].get_field_paths()


class MessageTypeAnalyzer:
    """Analyzes ROS message types and extracts field information"""
    
    def __init__(self):
        self._type_cache: Dict[str, MessageTypeInfo] = {}
        self._lock = threading.RLock()
    
    def analyze_message_type(self, msg_type: str, msg_definition: Optional[str] = None) -> MessageTypeInfo:
        """Analyze a message type and return field information"""
        cache_key = f"msgtype:{msg_type}"
        
        # Check cache first
        cached_result = get_cache().get(cache_key)
        if cached_result:
            _logger.debug(f"Message type analysis cache hit: {msg_type}")
            return cached_result
        
        with self._lock:
            # Double-check cache after acquiring lock
            if msg_type in self._type_cache:
                return self._type_cache[msg_type]
            
            try:
                # Try to analyze using rosbags type system
                type_info = self._analyze_with_rosbags(msg_type, msg_definition)
                
                if not type_info:
                    # Fallback to definition parsing
                    type_info = self._analyze_with_definition(msg_type, msg_definition)
                
                if not type_info:
                    # Create minimal type info
                    type_info = MessageTypeInfo(
                        type_name=msg_type,
                        fields={},
                        definition=msg_definition
                    )
                
                # Cache the result
                self._type_cache[msg_type] = type_info
                get_cache().put(cache_key, type_info, ttl=3600)  # Cache for 1 hour
                
                return type_info
                
            except Exception as e:
                _logger.warning(f"Error analyzing message type {msg_type}: {e}")
                # Return minimal type info on error
                type_info = MessageTypeInfo(
                    type_name=msg_type,
                    fields={},
                    definition=msg_definition
                )
                return type_info
    
    def _analyze_with_rosbags(self, msg_type: str, msg_definition: Optional[str] = None) -> Optional[MessageTypeInfo]:
        """Analyze message type using rosbags type system"""
        try:
            from rosbags.typesys import get_types_from_msg  # type: ignore
            
            if msg_definition:
                # Parse from definition
                types = get_types_from_msg(msg_definition, msg_type)
                if msg_type in types:
                    type_def = types[msg_type]
                    fields = self._extract_fields_from_nodetype(type_def)
                    return MessageTypeInfo(
                        type_name=msg_type,
                        fields=fields,
                        definition=msg_definition
                    )
            
            # Try to get from registered types
            from rosbags.typesys import get_typestore  # type: ignore
            typestore = get_typestore()
            
            if msg_type in typestore:
                type_def = typestore[msg_type]
                fields = self._extract_fields_from_nodetype(type_def)
                return MessageTypeInfo(
                    type_name=msg_type,
                    fields=fields,
                    definition=msg_definition
                )
            
        except ImportError:
            _logger.debug("rosbags not available for type analysis")
        except Exception as e:
            _logger.debug(f"Error in rosbags type analysis: {e}")
        
        return None
    
    def _extract_fields_from_nodetype(self, nodetype) -> Dict[str, FieldInfo]:
        """Extract field information from rosbags Nodetype"""
        fields = {}
        
        try:
            if hasattr(nodetype, 'fields'):
                for field_name, field_type in nodetype.fields:
                    field_info = self._create_field_info(field_name, field_type)
                    fields[field_name] = field_info
        except Exception as e:
            _logger.debug(f"Error extracting fields from nodetype: {e}")
        
        return fields
    
    def _create_field_info(self, field_name: str, field_type) -> FieldInfo:
        """Create FieldInfo from rosbags field type"""
        try:
            # Handle array types
            is_array = hasattr(field_type, '__origin__') and field_type.__origin__ is list
            array_size = None
            
            if is_array:
                # Get the element type
                element_type = field_type.__args__[0] if field_type.__args__ else field_type
                type_name = getattr(element_type, '__name__', str(element_type))
            else:
                type_name = getattr(field_type, '__name__', str(field_type))
            
            # Handle nested types
            nested_fields = {}
            if hasattr(field_type, 'fields'):
                nested_fields = self._extract_fields_from_nodetype(field_type)
            
            return FieldInfo(
                name=field_name,
                type_name=type_name,
                is_array=is_array,
                array_size=array_size,
                nested_fields=nested_fields
            )
        except Exception as e:
            _logger.debug(f"Error creating field info for {field_name}: {e}")
            return FieldInfo(name=field_name, type_name="unknown")
    
    def _analyze_with_definition(self, msg_type: str, msg_definition: Optional[str] = None) -> Optional[MessageTypeInfo]:
        """Analyze message type by parsing definition string"""
        if not msg_definition:
            return None
        
        try:
            fields = {}
            lines = msg_definition.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or '=' in line:
                    continue
                
                # Parse field definition: "type name" or "type[] name"
                parts = line.split()
                if len(parts) >= 2:
                    type_part = parts[0]
                    field_name = parts[1]
                    
                    # Check for array
                    is_array = '[]' in type_part
                    if is_array:
                        type_name = type_part.replace('[]', '')
                    else:
                        type_name = type_part
                    
                    fields[field_name] = FieldInfo(
                        name=field_name,
                        type_name=type_name,
                        is_array=is_array
                    )
            
            return MessageTypeInfo(
                type_name=msg_type,
                fields=fields,
                definition=msg_definition
            )
            
        except Exception as e:
            _logger.debug(f"Error parsing message definition: {e}")
            return None


class BagAnalyzer:
    """Main bag analyzer with async capabilities"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.msg_analyzer = MessageTypeAnalyzer()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._analysis_cache = get_cache()
    
    async def analyze_bag_async(self, 
                               bag_path: Path, 
                               analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                               progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
        """Analyze bag file asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, 
            self.analyze_bag, 
            bag_path, 
            analysis_type, 
            progress_callback
        )
    
    def analyze_bag(self, 
                   bag_path: Path, 
                   analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                   progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
        """Analyze bag file synchronously"""
        start_time = time.time()
        
        # Generate cache key
        cache_key = f"analysis:{bag_path}:{analysis_type.value}:{bag_path.stat().st_mtime}"
        
        # Check cache
        cached_result = self._analysis_cache.get(cache_key)
        if cached_result:
            cached_result.cached = True
            _logger.info(f"Analysis cache hit for {bag_path}")
            if progress_callback:
                progress_callback(100.0)
            return cached_result
        
        try:
            if progress_callback:
                progress_callback(10.0)
            
            # Load bag metadata
            bag_info = self._load_bag_metadata(bag_path)
            
            if progress_callback:
                progress_callback(30.0)
            
            # Analyze message types if needed
            message_types = {}
            if analysis_type in [AnalysisType.FIELD_ANALYSIS, AnalysisType.FULL_ANALYSIS]:
                message_types = self._analyze_message_types(bag_info, progress_callback)
            
            if progress_callback:
                progress_callback(90.0)
            
            # Create result
            analysis_time = time.time() - start_time
            result = AnalysisResult(
                bag_info=bag_info,
                message_types=message_types,
                analysis_type=analysis_type,
                analysis_time=analysis_time
            )
            
            # Cache result
            self._analysis_cache.put(cache_key, result, ttl=1800)  # Cache for 30 minutes
            
            if progress_callback:
                progress_callback(100.0)
            
            _logger.info(f"Analyzed {bag_path} in {analysis_time:.2f}s")
            return result
            
        except Exception as e:
            error_msg = f"Error analyzing {bag_path}: {e}"
            _logger.error(error_msg)
            
            # Return error result
            return AnalysisResult(
                bag_info=BagInfo(
                    path=bag_path,
                    size_bytes=0,
                    topics=set(),
                    message_counts={},
                    time_range=((0, 0), (0, 0)),
                    connections={}
                ),
                message_types={},
                analysis_type=analysis_type,
                analysis_time=time.time() - start_time,
                errors=[error_msg]
            )
    
    def _load_bag_metadata(self, bag_path: Path) -> BagInfo:
        """Load basic bag metadata"""
        try:
            # Try to use the parser from the main module
            from roseApp.core.parser import create_best_parser
            parser = create_best_parser()
            
            # Load bag information
            topics, connections, time_range = parser.load_bag(str(bag_path))
            message_counts = parser.get_message_counts(str(bag_path))
            
            return BagInfo(
                path=bag_path,
                size_bytes=bag_path.stat().st_size,
                topics=set(topics),
                message_counts=message_counts,
                time_range=time_range,
                connections=connections
            )
            
        except Exception as e:
            _logger.error(f"Error loading bag metadata: {e}")
            raise
    
    def _analyze_message_types(self, 
                              bag_info: BagInfo, 
                              progress_callback: Optional[Callable[[float], None]] = None) -> Dict[str, MessageTypeInfo]:
        """Analyze all message types in the bag"""
        message_types = {}
        unique_types = set(bag_info.connections.values())
        
        for i, msg_type in enumerate(unique_types):
            try:
                type_info = self.msg_analyzer.analyze_message_type(msg_type)
                message_types[msg_type] = type_info
                
                if progress_callback:
                    progress = 30 + (i + 1) / len(unique_types) * 60  # 30-90% range
                    progress_callback(progress)
                    
            except Exception as e:
                _logger.warning(f"Error analyzing message type {msg_type}: {e}")
        
        return message_types
    
    async def analyze_multiple_bags_async(self, 
                                         bag_paths: List[Path],
                                         analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                                         progress_callback: Optional[Callable[[str, float], None]] = None) -> Dict[Path, AnalysisResult]:
        """Analyze multiple bags concurrently"""
        results = {}
        
        # Create tasks for concurrent analysis
        tasks = []
        for bag_path in bag_paths:
            def make_progress_callback(path):
                if progress_callback:
                    return lambda p: progress_callback(str(path), p)
                return None
            
            task = self.analyze_bag_async(
                bag_path, 
                analysis_type, 
                make_progress_callback(bag_path)
            )
            tasks.append((bag_path, task))
        
        # Wait for all tasks to complete
        for bag_path, task in tasks:
            try:
                result = await task
                results[bag_path] = result
            except Exception as e:
                _logger.error(f"Error analyzing {bag_path}: {e}")
                results[bag_path] = AnalysisResult(
                    bag_info=BagInfo(
                        path=bag_path,
                        size_bytes=0,
                        topics=set(),
                        message_counts={},
                        time_range=((0, 0), (0, 0)),
                        connections={}
                    ),
                    message_types={},
                    analysis_type=analysis_type,
                    analysis_time=0,
                    errors=[str(e)]
                )
        
        return results
    
    def get_topic_statistics(self, result: AnalysisResult) -> Dict[str, Dict[str, Any]]:
        """Get detailed statistics for each topic"""
        stats = {}
        
        for topic in result.bag_info.topics:
            msg_count = result.bag_info.message_counts.get(topic, 0)
            msg_type = result.bag_info.connections.get(topic, "unknown")
            
            # Calculate frequency
            frequency = 0.0
            if result.bag_info.duration_seconds > 0:
                frequency = msg_count / result.bag_info.duration_seconds
            
            # Get field paths if available
            field_paths = result.get_topic_field_paths(topic)
            
            stats[topic] = {
                'message_count': msg_count,
                'message_type': msg_type,
                'frequency_hz': frequency,
                'field_count': len(field_paths),
                'field_paths': field_paths
            }
        
        return stats
    
    def cleanup(self):
        """Cleanup resources"""
        self._executor.shutdown(wait=True)


# Global analyzer instance
_global_analyzer: Optional[BagAnalyzer] = None


def get_analyzer() -> BagAnalyzer:
    """Get or create global analyzer instance"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = BagAnalyzer()
    return _global_analyzer


async def analyze_bag_async(bag_path: Path, 
                           analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                           progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
    """Convenience function for async bag analysis"""
    return await get_analyzer().analyze_bag_async(bag_path, analysis_type, progress_callback)


def analyze_bag(bag_path: Path, 
               analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
               progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
    """Convenience function for sync bag analysis"""
    return get_analyzer().analyze_bag(bag_path, analysis_type, progress_callback)


def get_topic_field_paths(bag_path: Path, topic: str) -> List[str]:
    """Get field paths for a specific topic in a bag"""
    result = analyze_bag(bag_path, AnalysisType.FIELD_ANALYSIS)
    return result.get_topic_field_paths(topic) 