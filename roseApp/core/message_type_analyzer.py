#!/usr/bin/env python3
"""
Message Type Analyzer for ROS bag field analysis optimization.
This module provides static analysis of message type definitions to extract
field structures without the need for message deserialization.
"""

import time
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path

from roseApp.core.util import get_logger

logger = get_logger("MessageTypeAnalyzer")


@dataclass
class FieldInfo:
    """Information about a message field"""
    name: str
    type: str
    full_path: str
    is_array: bool = False
    array_size: Optional[int] = None
    nested_fields: Optional[Dict[str, 'FieldInfo']] = None
    description: Optional[str] = None


@dataclass
class TypeDefinition:
    """Message type definition with field structure"""
    msg_type: str
    fields: Dict[str, FieldInfo]
    analyzed_at: float
    source: str  # 'type_system' or 'sample_analysis'


class MessageTypeAnalyzer:
    """
    High-performance message type analyzer that extracts field structures
    directly from ROS message type definitions, avoiding costly deserialization.
    """
    
    def __init__(self):
        self._type_cache: Dict[str, TypeDefinition] = {}
        self._analysis_stats = {
            'cache_hits': 0,
            'type_system_analyses': 0,
            'sample_fallbacks': 0,
            'total_requests': 0
        }
        
    def analyze_message_type(self, msg_type: str) -> TypeDefinition:
        """
        Analyze message type and extract field structure.
        
        Args:
            msg_type: ROS message type (e.g., 'geometry_msgs/msg/Twist')
            
        Returns:
            TypeDefinition containing field structure
        """
        self._analysis_stats['total_requests'] += 1
        
        # Check cache first
        if msg_type in self._type_cache:
            self._analysis_stats['cache_hits'] += 1
            logger.debug(f"Cache hit for message type: {msg_type}")
            return self._type_cache[msg_type]
        
        # Try type system analysis first
        try:
            type_def = self._analyze_from_type_system(msg_type)
            self._analysis_stats['type_system_analyses'] += 1
            logger.debug(f"Type system analysis successful for: {msg_type}")
        except Exception as e:
            logger.warning(f"Type system analysis failed for {msg_type}: {e}")
            # Fallback to sample analysis marker
            type_def = self._create_fallback_definition(msg_type)
            self._analysis_stats['sample_fallbacks'] += 1
        
        # Cache the result
        self._type_cache[msg_type] = type_def
        return type_def
    
    def _analyze_from_type_system(self, msg_type: str) -> TypeDefinition:
        """
        Analyze message type using rosbags type system.
        This is the main optimization - direct type definition analysis.
        """
        try:
            from rosbags.typesys import get_typestore, Stores
            
            # Get the latest typestore
            store = get_typestore(Stores.LATEST)
            
            # Check if this message type is known
            if msg_type not in store.types:
                # Try common variations
                variations = [
                    msg_type,
                    msg_type.replace('/', '/msg/'),
                    msg_type.replace('/msg/', '/'),
                ]
                
                found_type = None
                for variation in variations:
                    if variation in store.types:
                        found_type = variation
                        break
                
                if not found_type:
                    raise Exception(f"Message type not found in typestore: {msg_type}")
                
                msg_type = found_type
            
            # Get the message definition class
            msg_class = store.types[msg_type]
            
            # Parse the message class to extract fields
            fields = self._parse_message_class(msg_class, msg_type)
            
            return TypeDefinition(
                msg_type=msg_type,
                fields=fields,
                analyzed_at=time.time(),
                source='type_system'
            )
            
        except ImportError:
            logger.warning("rosbags.typesys not available, falling back to sample analysis")
            raise Exception("Type system not available")
        except Exception as e:
            logger.debug(f"Type system analysis failed for {msg_type}: {e}")
            raise
    
    def _parse_message_class(self, msg_class: Any, msg_type: str, prefix: str = "") -> Dict[str, FieldInfo]:
        """
        Parse rosbags message class into field structure.
        
        Args:
            msg_class: Message class from rosbags typestore
            msg_type: Message type name
            prefix: Field path prefix
            
        Returns:
            Dictionary of field names to FieldInfo objects
        """
        fields = {}
        
        try:
            # Get field definitions from the message class
            if hasattr(msg_class, '__annotations__'):
                # Modern Python dataclass style
                for field_name, field_type in msg_class.__annotations__.items():
                    if field_name.startswith('_'):
                        continue
                        
                    full_path = f"{prefix}.{field_name}" if prefix else field_name
                    
                    field_info = FieldInfo(
                        name=field_name,
                        type=self._get_field_type_name(field_type),
                        full_path=full_path,
                        is_array=self._is_array_type(field_type),
                        array_size=self._get_array_size(field_type)
                    )
                    
                    # Handle nested complex types
                    if self._is_complex_type(field_type):
                        try:
                            nested_type = self._get_base_type(field_type)
                            from rosbags.typesys import get_typestore, Stores
                            store = get_typestore(Stores.LATEST)
                            
                            if nested_type in store.types:
                                nested_msg_class = store.types[nested_type]
                                field_info.nested_fields = self._parse_message_class(
                                    nested_msg_class, 
                                    nested_type, 
                                    full_path
                                )
                        except Exception as e:
                            logger.debug(f"Failed to parse nested type {field_type}: {e}")
                            field_info.nested_fields = {}
                    
                    fields[field_name] = field_info
                    
            elif hasattr(msg_class, '__slots__'):
                # Older style with __slots__
                for field_name in msg_class.__slots__:
                    if field_name.startswith('_'):
                        continue
                        
                    full_path = f"{prefix}.{field_name}" if prefix else field_name
                    
                    # Try to get field type from defaults or other attributes
                    field_type = 'unknown'
                    try:
                        if hasattr(msg_class, '_slot_types'):
                            field_type = msg_class._slot_types.get(field_name, 'unknown')
                    except:
                        pass
                    
                    field_info = FieldInfo(
                        name=field_name,
                        type=field_type,
                        full_path=full_path,
                        is_array=self._is_array_type_str(field_type),
                        array_size=self._get_array_size_str(field_type)
                    )
                    
                    fields[field_name] = field_info
            
        except Exception as e:
            logger.warning(f"Failed to parse message class {msg_type}: {e}")
            
        return fields
    
    def _get_field_type_name(self, field_type: Any) -> str:
        """Extract field type name from type annotation"""
        if hasattr(field_type, '__name__'):
            return field_type.__name__
        elif hasattr(field_type, '_name'):
            return field_type._name
        elif hasattr(field_type, '__origin__'):
            # Handle generic types like List[T], Optional[T]
            origin = field_type.__origin__
            args = getattr(field_type, '__args__', ())
            if origin == list and args:
                return f"List[{self._get_field_type_name(args[0])}]"
            elif origin == tuple and args:
                return f"Tuple[{', '.join(self._get_field_type_name(arg) for arg in args)}]"
            else:
                return str(origin.__name__ if hasattr(origin, '__name__') else origin)
        else:
            return str(field_type)
    
    def _is_array_type(self, field_type: Any) -> bool:
        """Check if field type is an array (List, Tuple, etc.)"""
        if hasattr(field_type, '__origin__'):
            return field_type.__origin__ in (list, tuple)
        
        type_str = str(field_type)
        return '[' in type_str and ']' in type_str
    
    def _is_array_type_str(self, type_str: str) -> bool:
        """Check if type string represents an array"""
        return '[' in type_str and ']' in type_str
    
    def _get_array_size(self, field_type: Any) -> Optional[int]:
        """Get array size if fixed size array"""
        if hasattr(field_type, '__origin__') and field_type.__origin__ == tuple:
            args = getattr(field_type, '__args__', ())
            if len(args) == 2 and isinstance(args[1], int):
                return args[1]
        
        type_str = str(field_type)
        return self._get_array_size_str(type_str)
    
    def _get_array_size_str(self, type_str: str) -> Optional[int]:
        """Get array size from type string"""
        if '[' in type_str and ']' in type_str:
            try:
                start = type_str.index('[') + 1
                end = type_str.index(']')
                size_str = type_str[start:end]
                return int(size_str) if size_str.isdigit() else None
            except (ValueError, IndexError):
                return None
        return None
    
    def _is_complex_type(self, field_type: Any) -> bool:
        """Check if field type is a complex/nested ROS message type"""
        type_str = str(field_type)
        
        # Check for ROS message patterns
        if '/' in type_str or 'msg' in type_str.lower():
            return True
            
        # Check for generic types with ROS message arguments
        if hasattr(field_type, '__args__'):
            args = field_type.__args__
            for arg in args:
                if self._is_complex_type(arg):
                    return True
                    
        return False
    
    def _get_base_type(self, field_type: Any) -> str:
        """Get base type name for complex types"""
        if hasattr(field_type, '__args__'):
            # For generic types like List[geometry_msgs/msg/Point], get the inner type
            args = field_type.__args__
            if args:
                return str(args[0])
        
        type_str = str(field_type)
        # Remove array notation if present
        if '[' in type_str:
            type_str = type_str[:type_str.index('[')]
        return type_str
    
    def _is_array_annotation(self, field_type: Any) -> bool:
        """Check if type annotation indicates array"""
        # Handle typing annotations like List[T], Sequence[T], etc.
        return hasattr(field_type, '__origin__') and field_type.__origin__ in (list, tuple)
    
    def _get_array_size_annotation(self, field_type: Any) -> Optional[int]:
        """Get array size from type annotation"""
        # For most ROS types, this will be dynamic arrays
        return None
    
    def _create_fallback_definition(self, msg_type: str) -> TypeDefinition:
        """Create a fallback definition when type system analysis fails"""
        return TypeDefinition(
            msg_type=msg_type,
            fields={},
            analyzed_at=time.time(),
            source='sample_analysis'  # Indicates this needs sample-based analysis
        )
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get analyzer performance statistics"""
        total = self._analysis_stats['total_requests']
        if total == 0:
            return self._analysis_stats
        
        return {
            **self._analysis_stats,
            'cache_hit_rate': self._analysis_stats['cache_hits'] / total * 100,
            'type_system_success_rate': self._analysis_stats['type_system_analyses'] / total * 100,
            'fallback_rate': self._analysis_stats['sample_fallbacks'] / total * 100
        }
    
    def clear_cache(self):
        """Clear the type definition cache"""
        self._type_cache.clear()
        self._analysis_stats = {
            'cache_hits': 0,
            'type_system_analyses': 0,
            'sample_fallbacks': 0,
            'total_requests': 0
        }
        logger.info("Message type analyzer cache cleared")
    
    def convert_to_legacy_format(self, type_def: TypeDefinition) -> Dict[str, Any]:
        """
        Convert TypeDefinition to legacy field format for backward compatibility.
        
        Args:
            type_def: TypeDefinition object
            
        Returns:
            Legacy format dictionary
        """
        def convert_field_info(field_info: FieldInfo) -> Dict[str, Any]:
            result = {
                'type': field_info.type,
                'full_path': field_info.full_path
            }
            
            if field_info.is_array:
                result['length'] = field_info.array_size or 'dynamic'
                result['element_type'] = field_info.type
            
            if field_info.nested_fields:
                result['fields'] = {
                    name: convert_field_info(nested_field)
                    for name, nested_field in field_info.nested_fields.items()
                }
            
            return result
        
        return {
            'fields': {
                name: convert_field_info(field_info)
                for name, field_info in type_def.fields.items()
            },
            'message_type': type_def.msg_type,
            'samples_analyzed': 0,  # Static analysis doesn't use samples
            'analysis_source': type_def.source,
            'analyzed_at': type_def.analyzed_at
        }


# Global instance for singleton pattern
_global_analyzer: Optional[MessageTypeAnalyzer] = None


def get_message_type_analyzer() -> MessageTypeAnalyzer:
    """Get global message type analyzer instance"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = MessageTypeAnalyzer()
    return _global_analyzer


def analyze_message_type(msg_type: str) -> TypeDefinition:
    """Convenience function to analyze message type using global analyzer"""
    return get_message_type_analyzer().analyze_message_type(msg_type)


def clear_analyzer_cache():
    """Clear the global analyzer cache"""
    global _global_analyzer
    if _global_analyzer:
        _global_analyzer.clear_cache() 