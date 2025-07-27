"""
Async bag analyzer with intelligent caching and message type analysis
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Set, List, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from .parser import create_parser
from .cache import get_cache
from .util import get_logger


class AnalysisType(Enum):
    """Types of bag analysis"""
    METADATA = "metadata"
    FULL_ANALYSIS = "full_analysis"


@dataclass
class BagInfo:
    """Bag file information"""
    path: Path
    size_bytes: int
    topics: Set[str]
    message_counts: Dict[str, int]
    time_range: Optional[tuple] = None
    connections: Dict[str, str] = field(default_factory=dict)
    duration_seconds: float = 0.0


@dataclass
class MessageTypeInfo:
    """Message type information"""
    type_name: str
    fields: Dict[str, Any] = field(default_factory=dict)
    definition: str = ""
    md5sum: str = ""

    def get_field_paths(self) -> List[str]:
        """Get all field paths for this message type"""
        paths = []
        
        def extract_paths(fields_dict, prefix=""):
            for field_name, field_info in fields_dict.items():
                current_path = f"{prefix}.{field_name}" if prefix else field_name
                paths.append(current_path)
                
                if isinstance(field_info, dict) and 'fields' in field_info:
                    extract_paths(field_info['fields'], current_path)
        
        extract_paths(self.fields)
        return paths


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    bag_info: BagInfo
    message_types: Dict[str, MessageTypeInfo] = field(default_factory=dict)
    analysis_type: AnalysisType = AnalysisType.METADATA
    analysis_time: float = 0.0
    cached: bool = False
    errors: List[str] = field(default_factory=list)

    def get_topic_field_paths(self, topic: str) -> List[str]:
        """Get field paths for a specific topic"""
        msg_type = self.bag_info.connections.get(topic)
        if msg_type and msg_type in self.message_types:
            return self.message_types[msg_type].get_field_paths()
        return []


class BagAnalyzer:
    """Async bag analyzer with intelligent caching"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache = get_cache()
        self.logger = get_logger()
        
    async def analyze_bag_async(
        self,
        bag_path: Path,
        analysis_type: AnalysisType = AnalysisType.METADATA,
        progress_callback: Optional[Callable[[float], None]] = None,
        no_cache: bool = False
    ) -> AnalysisResult:
        """Analyze bag file asynchronously"""
        start_time = time.time()
        
        # Phase 2 optimization: Try cache coordination first
        if no_cache:
            self.logger.info(f"Skipping cache for {bag_path} (--no-cache specified)")
        else:
            try:
                from .cache_coordinator import get_cache_bridge, CacheKeyManager
                cache_bridge = get_cache_bridge()
                
                # Generate unified cache key
                cache_key = CacheKeyManager.generate_analysis_key(str(bag_path), analysis_type.value)
                
                # Try full analysis cache
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    cache_lookup_time = time.time() - start_time
                    self.logger.info(f"Using cached analysis for {bag_path} (cache lookup: {cache_lookup_time:.3f}s)")
                    cached_result.cached = True
                    cached_result.analysis_time = cache_lookup_time
                    return cached_result
                
                # Try building from parser cache for metadata analysis
                if analysis_type == AnalysisType.METADATA:
                    lightweight_result = cache_bridge.build_analysis_from_parser(str(bag_path), analysis_type.value)
                    if lightweight_result:
                        cache_lookup_time = time.time() - start_time
                        lightweight_result.analysis_time = cache_lookup_time
                        self.logger.info(f"Built lightweight analysis from parser cache: {bag_path}")
                        return lightweight_result
            except ImportError:
                # Fallback to original cache strategy
                cache_key = f"analysis_{bag_path}_{analysis_type.value}_{bag_path.stat().st_mtime}"
                
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    cache_lookup_time = time.time() - start_time
                    self.logger.info(f"Using cached analysis for {bag_path} (cache lookup: {cache_lookup_time:.3f}s)")
                    cached_result.cached = True
                    cached_result.analysis_time = cache_lookup_time
                    return cached_result
        
        try:
            if progress_callback:
                progress_callback(10.0)
            
            # Create parser
            parser = create_parser()
            
            if progress_callback:
                progress_callback(20.0)
            
            # Load basic bag info
            bag_info = await self._load_bag_info_async(parser, bag_path)
            
            if progress_callback:
                progress_callback(60.0)
            
            # Create result
            result = AnalysisResult(
                bag_info=bag_info,
                analysis_type=analysis_type,
                analysis_time=time.time() - start_time,
                cached=False
            )
            
            # Perform message type analysis if requested
            if analysis_type == AnalysisType.FULL_ANALYSIS:
                result.message_types = await self._analyze_message_types_async(
                    bag_info.connections,
                    bag_path
                )
            
            if progress_callback:
                progress_callback(100.0)
            
            # Cache the result (unless no_cache is specified)
            if not no_cache:
                self.cache.put(cache_key, result, ttl=3600)  # Cache for 1 hour
            
            self.logger.info(f"Analysis completed in {result.analysis_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            # Return minimal result on error
            return AnalysisResult(
                bag_info=BagInfo(
                    path=bag_path,
                    size_bytes=bag_path.stat().st_size if bag_path.exists() else 0,
                    topics=set(),
                    message_counts={}
                ),
                analysis_type=analysis_type,
                analysis_time=time.time() - start_time,
                cached=False,
                errors=[str(e)]
            )
    
    async def _load_bag_info_async(self, parser, bag_path: Path) -> BagInfo:
        """Load basic bag information asynchronously using new parser interface"""
        loop = asyncio.get_event_loop()
        
        # Use new parser interface - get comprehensive bag details
        def get_bag_info():
            bag_details, _ = parser.get_bag_details(str(bag_path))
            return bag_details
        
        bag_details = await loop.run_in_executor(
            self.executor,
            get_bag_info
        )
        
        # Extract information from comprehensive bag details
        topics = bag_details.topics or []
        connections = bag_details.connections or {}
        time_range = bag_details.time_range
        message_counts = bag_details.message_counts or {}
        
        # Use duration from comprehensive bag details
        duration = bag_details.duration_seconds or 0.0
        
        return BagInfo(
            path=bag_path,
            size_bytes=bag_path.stat().st_size,
            topics=set(topics),
            message_counts=message_counts,
            time_range=time_range,
            connections=connections,
            duration_seconds=duration
        )
    
    async def _analyze_message_types_async(
        self,
        connections: Dict[str, str],
        bag_path: Path
    ) -> Dict[str, MessageTypeInfo]:
        """
        Analyze message types using new parser interface field analysis
        
        This method now uses the field structure information from the parser's
        ComprehensiveBagInfo instead of sampling messages.
        """
        message_types = {}
        
        # Get unique message types
        unique_types = set(connections.values())
        
        loop = asyncio.get_event_loop()
        parser = create_parser()
        
        # Get comprehensive bag info with field analysis
        def get_field_info():
            bag_details, _ = parser.get_bag_details(str(bag_path))
            return bag_details
        
        try:
            bag_details = await loop.run_in_executor(self.executor, get_field_info)
            
            # Extract field information from parser's analysis
            for msg_type in unique_types:
                try:
                    fields = {}
                    definition = ""
                    
                    # Get field structure from parser's analysis
                    if (bag_details.has_field_analysis() and 
                        bag_details.message_fields and 
                        msg_type in bag_details.message_fields):
                        
                        # Convert parser field format to analyzer format
                        parser_fields = bag_details.message_fields[msg_type]
                        fields = self._convert_parser_fields_to_analyzer_format(parser_fields)
                        
                        # Get message definition if available
                        if (bag_details.message_definitions and 
                            msg_type in bag_details.message_definitions):
                            definition = bag_details.message_definitions[msg_type]
                    
                    message_types[msg_type] = MessageTypeInfo(
                        type_name=msg_type,
                        fields=fields,
                        definition=definition,
                        md5sum=""  # Could be extracted from connection if needed
                    )
                    
                    self.logger.debug(f"Analyzed message type {msg_type} with {len(fields)} fields")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to analyze message type {msg_type}: {e}")
                    # Create empty message type info as fallback
                    message_types[msg_type] = MessageTypeInfo(
                        type_name=msg_type,
                        fields={},
                        definition="",
                        md5sum=""
                    )
        
        except Exception as e:
            self.logger.error(f"Failed to get field information from parser: {e}")
            # Fallback: create empty message types for all connections
            for msg_type in unique_types:
                message_types[msg_type] = MessageTypeInfo(
                    type_name=msg_type,
                    fields={},
                    definition="",
                    md5sum=""
                )
        
        return message_types
    
    def _convert_parser_fields_to_analyzer_format(self, parser_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parser field format to analyzer field format
        
        Parser format: {field_name: {'type': str, 'is_array': bool, 'is_builtin': bool, ...}}
        Analyzer format: {field_name: {'type': str, 'array': bool, 'fields': dict, ...}}
        """
        analyzer_fields = {}
        
        for field_name, field_info in parser_fields.items():
            analyzer_field = {
                'type': field_info.get('type', 'unknown'),
                'value_sample': None
            }
            
            # Handle array types
            if field_info.get('is_array', False):
                analyzer_field['array'] = True
                # Clean the type name by removing array brackets
                clean_type = field_info.get('type', '').replace('[]', '')
                analyzer_field['element_type'] = clean_type
            
            # Handle complex types (nested messages)
            if field_info.get('is_complex', False):
                # For now, mark as complex but don't recursively parse
                # This could be enhanced to support nested field analysis
                analyzer_field['is_complex'] = True
            
            # Add builtin type information
            if field_info.get('is_builtin', False):
                analyzer_field['is_builtin'] = True
            
            analyzer_fields[field_name] = analyzer_field
        
        return analyzer_fields
    
    def _extract_message_fields(self, message) -> Dict[str, Any]:
        """Extract field structure from a ROS message"""
        fields = {}
        
        if hasattr(message, '__slots__'):
            # ROS message with __slots__
            for field_name in message.__slots__:
                if hasattr(message, field_name):
                    field_value = getattr(message, field_name)
                    fields[field_name] = self._analyze_field_value(field_value)
        elif hasattr(message, '__dict__'):
            # Regular object with __dict__
            for field_name, field_value in message.__dict__.items():
                if not field_name.startswith('_'):
                    fields[field_name] = self._analyze_field_value(field_value)
        else:
            # Try to get common ROS message fields
            common_fields = ['header', 'data', 'pose', 'twist', 'position', 'orientation']
            for field_name in common_fields:
                if hasattr(message, field_name):
                    field_value = getattr(message, field_name)
                    fields[field_name] = self._analyze_field_value(field_value)
        
        return fields
    
    def _analyze_field_value(self, value) -> Dict[str, Any]:
        """Analyze the type and structure of a field value"""
        field_info = {
            'type': type(value).__name__,
            'value_sample': None
        }
        
        # Handle different value types
        if hasattr(value, '__slots__') or hasattr(value, '__dict__'):
            # Nested message
            field_info['fields'] = self._extract_message_fields(value)
        elif isinstance(value, (list, tuple)) and len(value) > 0:
            # Array/list
            field_info['array'] = True
            field_info['length'] = len(value)
            field_info['element_type'] = type(value[0]).__name__
            # Analyze first element if it's a complex type
            if hasattr(value[0], '__slots__') or hasattr(value[0], '__dict__'):
                field_info['element_fields'] = self._extract_message_fields(value[0])
        elif isinstance(value, (int, float, str, bool)):
            # Primitive type
            field_info['value_sample'] = str(value)[:50]  # Limit sample length
        
        return field_info
    
    def _merge_fields(self, existing_fields: Dict[str, Any], new_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Merge field structures from multiple message samples"""
        merged = existing_fields.copy()
        
        for field_name, field_info in new_fields.items():
            if field_name not in merged:
                merged[field_name] = field_info
            else:
                # Merge nested fields if present
                if 'fields' in field_info and 'fields' in merged[field_name]:
                    merged[field_name]['fields'] = self._merge_fields(
                        merged[field_name]['fields'], 
                        field_info['fields']
                    )
        
        return merged
    
    def cleanup(self):
        """Clean up resources"""
        self.executor.shutdown(wait=True)


# Global analyzer instance
_analyzer = None


async def analyze_bag_async(
    bag_path: Path,
    analysis_type: AnalysisType = AnalysisType.METADATA,
    progress_callback: Optional[Callable[[float], None]] = None,
    no_cache: bool = False
) -> AnalysisResult:
    """Analyze bag file asynchronously - main public interface"""
    global _analyzer
    
    if _analyzer is None:
        _analyzer = BagAnalyzer()
    
    return await _analyzer.analyze_bag_async(
        bag_path=bag_path,
        analysis_type=analysis_type,
        progress_callback=progress_callback,
        no_cache=no_cache
    )


def cleanup_analyzer():
    """Clean up global analyzer"""
    global _analyzer
    if _analyzer:
        _analyzer.cleanup()
        _analyzer = None 