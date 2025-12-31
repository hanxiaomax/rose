"""
ROS bag parser module using rosbags library.

Provides high-performance bag parsing capabilities with intelligent caching
and memory optimization using the rosbags library.
"""

import os
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, Any, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from rosbags.highlevel import AnyReader


from roseApp.core.logging import get_logger
from .model import BagInfo, AnalysisLevel, TopicInfo, MessageTypeInfo, MessageFieldInfo, TimeRange

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

_logger = get_logger("parser")



class BagReader:
    """
    Singleton high-performance ROS bag reader using rosbags library
    
    Public Interface:
    - load_bag_async(): Async load bag into cache with configurable analysis level
    
    The reader automatically chooses between quick and index analysis based on
    the required information and caching status.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(BagReader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize singleton instance only once"""
        if BagReader._initialized:
            return
        
        # Current bag information
        self._current_bag_info: Optional[BagInfo] = None
        
        # Type system optimization
        self._typestore = None
        
        # Cache settings
        self._cache_ttl = 300  # 5 minutes
        
        BagReader._initialized = True
        _logger.debug("Initialized singleton BagReader")
    
    async def load_bag_async(
        self, 
        bag_path: str, 
        level: AnalysisLevel = AnalysisLevel.QUICK,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Tuple[BagInfo, float]:
        """
        Asynchronously load bag into cache with configurable analysis level
        
        Args:
            bag_path: Path to the bag file
            level: Target analysis level (QUICK or INDEX)
            progress_callback: Optional callback for progress updates (phase, progress_pct)
            
        Returns:
            Tuple of (BagInfo, elapsed_time_seconds)
        """
        start_time = time.time()
        loop = asyncio.get_event_loop()
        
        if progress_callback:
            progress_callback(f"Starting analysis (Level: {level.value})...", 10.0)
        
        try:
            # 1. Determine strategy based on requested level
            if level == AnalysisLevel.INDEX:
                # INDEX level: parsing all messages and building DataFrames
                method = self._analyze_bag_with_index
                phase_name = "Building message index..."
            else:
                # QUICK level (default): Metadata only
                method = self._analyze_bag_quick
                phase_name = "Performing quick analysis..."

            # 2. Execute analysis
            if progress_callback:
                progress_callback(phase_name, 30.0)
            
            bag_info, _ = await loop.run_in_executor(
                None,
                method,
                bag_path
            )
            
            # 3. Cache results
            if progress_callback:
                progress_callback("Caching results...", 80.0)
            
            from .cache import create_bag_cache_manager
            cache_manager = create_bag_cache_manager()
            cache_manager.put_analysis(Path(bag_path), bag_info)
            
            if progress_callback:
                progress_callback("Complete", 100.0)
            
            elapsed = time.time() - start_time
            _logger.info(f"Async load completed in {elapsed:.3f}s for {bag_path} (Level: {level.value})")
            
            return bag_info, elapsed
            
        except Exception as e:
            if progress_callback:
                progress_callback("Error", 0.0)
            _logger.error(f"Error in async load for {bag_path}: {e}")
            raise
            
    def clear(self) -> Tuple[str, float]:
        """
        Clear all internal information
        
        Returns:
            Tuple of (result_message, elapsed_time_seconds)
        """
        start_time = time.time()
        
        self._current_bag_info = None
        self._typestore = None
        
        elapsed = time.time() - start_time
        _logger.debug("Cleared all internal information")
        
        return "Internal information cleared", elapsed
    
    # === PRIVATE METHODS ===
    
    def _initialize_typestore(self):
        """Initialize optimized typestore for better performance"""
        if self._typestore is None:
            try:
                from rosbags.typesys import get_typestore, Stores
                try:
                    self._typestore = get_typestore(Stores.ROS1_NOETIC)
                    _logger.debug("Initialized typestore for ROS1_NOETIC")
                except:
                    self._typestore = get_typestore(Stores.LATEST)
                    _logger.debug("Initialized typestore with LATEST")
            except Exception as e:
                _logger.warning(f"Could not initialize typestore: {e}")
                self._typestore = None
    
    def _is_cache_valid(self, bag_path: str) -> bool:
        """Check if current cache is valid for the given bag path"""
        if self._current_bag_info is None:
            return False
        
        if self._current_bag_info.file_path != bag_path:
            return False
        
        if time.time() - self._current_bag_info.last_updated > self._cache_ttl:
            return False
        
        return True
    
    def _analyze_bag_quick(self, bag_path: str) -> Tuple[BagInfo, float]:
        """
        Perform quick analysis without message traversal
        
        Gets basic metadata: topics, connections, time range, duration
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            Tuple of (BagInfo, elapsed_time_seconds)
        """
        start_time = time.time()
        
        # Check if we already have quick analysis for this bag
        if (self._is_cache_valid(bag_path) and 
            self._current_bag_info is not None and
            self._current_bag_info.has_quick_analysis()):
            elapsed = time.time() - start_time
            _logger.info(f"Using cached quick analysis for {bag_path}")
            return self._current_bag_info, elapsed
        
        _logger.info(f"Performing quick analysis for {bag_path}")
        
        try:
            self._initialize_typestore()
            
            reader_args = [Path(bag_path)]
            reader_kwargs = {'default_typestore': self._typestore} if self._typestore else {}
            
            with AnyReader(reader_args, **reader_kwargs) as reader:
                # Extract time range using new TimeRange structure
                start_ns = reader.start_time
                end_ns = reader.end_time
                start_time_tuple = (int(start_ns // 1_000_000_000), int(start_ns % 1_000_000_000))
                end_time_tuple = (int(end_ns // 1_000_000_000), int(end_ns % 1_000_000_000))
                time_range = TimeRange(start_time=start_time_tuple, end_time=end_time_tuple)
                
                # Calculate duration
                duration_seconds = time_range.get_duration_seconds()
                
                # Create or update bag info first
                if (self._current_bag_info is None or 
                    self._current_bag_info.file_path != bag_path):
                    file_size = os.path.getsize(bag_path)
                    file_mtime = os.path.getmtime(bag_path)
                    self._current_bag_info = BagInfo(
                        file_path=bag_path,
                        file_size=file_size,
                        file_mtime=file_mtime,
                        analysis_level=AnalysisLevel.QUICK
                    )
                
                # Set time range using the optimized method
                self._current_bag_info.set_time_range(start_time_tuple, end_time_tuple)
                
                # Process connections using optimized builder methods
                for connection in reader.connections:
                    topic_name = connection.topic
                    message_type = connection.msgtype
                    
                    # Create and add TopicInfo object directly
                    topic_info = TopicInfo(
                        name=topic_name,
                        message_type=message_type,
                        first_message_time=start_time_tuple,
                        last_message_time=end_time_tuple,
                        connection_id=str(connection.id) if hasattr(connection, 'id') else None
                    )
                    self._current_bag_info.add_topic(topic_info)
                    
                    # Create and add MessageTypeInfo object if not exists
                    if message_type and not self._current_bag_info.find_message_type(message_type):
                        message_type_info = MessageTypeInfo(
                            message_type=message_type,
                            definition=connection.msgdef if hasattr(connection, 'msgdef') else None
                        )
                        
                        # Parse message fields if available
                        if hasattr(connection, 'msgdef') and connection.msgdef:
                            try:
                                fields = self._parse_message_definition_to_fields(connection.msgdef)
                                message_type_info.fields = fields
                            except Exception as e:
                                _logger.warning(f"Failed to parse message definition for {message_type}: {e}")
                        
                        self._current_bag_info.add_message_type(message_type_info)
                
                # Update metadata
                self._current_bag_info.last_updated = time.time()
                
                elapsed = time.time() - start_time
                _logger.info(f"Quick analysis completed in {elapsed:.3f}s - {len(self._current_bag_info.topics)} topics")
                
                return self._current_bag_info, elapsed
                
        except Exception as e:
            _logger.error(f"Error in quick analysis for {bag_path}: {e}")
            raise Exception(f"Error in quick analysis: {e}")
    
    def _analyze_bag_with_index(self, bag_path: str) -> Tuple[BagInfo, float]:
        """
        Perform analysis with message indexing and DataFrame creation
        
        Gets basic metadata plus creates a pandas DataFrame with all message data
        for data analysis purposes.
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            Tuple of (BagInfo, elapsed_time_seconds)
        """
        start_time = time.time()
        
        if not PANDAS_AVAILABLE:
            _logger.warning("pandas not available, falling back to quick analysis")
            return self._analyze_bag_quick(bag_path)
        
        # Check if we already have index analysis for this bag
        if (self._is_cache_valid(bag_path) and 
            self._current_bag_info is not None and
            self._current_bag_info.has_message_index()):
            elapsed = time.time() - start_time
            _logger.info(f"Using cached index analysis for {bag_path}")
            return self._current_bag_info, elapsed
        
        _logger.info(f"Performing analysis with message indexing for {bag_path}")
        
        try:
            self._initialize_typestore()
            
            reader_args = [Path(bag_path)]
            reader_kwargs = {'default_typestore': self._typestore} if self._typestore else {}
            
            with AnyReader(reader_args, **reader_kwargs) as reader:
                # First, do quick analysis to get basic info
                quick_info, _ = self._analyze_bag_quick(bag_path)
                
                # Upgrade analysis level to INDEX
                quick_info.analysis_level = AnalysisLevel.INDEX
                
                # Prepare data for DataFrame
                message_data = []
                
                _logger.info(f"Reading messages for indexing...")
                message_count = 0
                
                # Read all messages and create index with content
                for connection, timestamp, rawdata in reader.messages():
                    # Convert timestamp to seconds for easier analysis
                    timestamp_sec = timestamp / 1_000_000_000
                    timestamp_ns = timestamp
                    
                    # Start with basic message record
                    message_record = {
                        'timestamp_sec': timestamp_sec,
                        'timestamp_ns': timestamp_ns,
                        'topic': connection.topic,
                        'message_type': connection.msgtype,
                        'message_size': len(rawdata),
                        'connection_id': connection.id if hasattr(connection, 'id') else None
                    }
                    
                    # Deserialize and flatten message content
                    try:
                        # Use the reader's built-in deserialization
                        msg = reader.deserialize(rawdata, connection.msgtype)
                        
                        # Flatten message fields
                        flattened_fields = self._flatten_message_fields(msg)
                        message_record.update(flattened_fields)
                        
                    except Exception as e:
                        _logger.debug(f"Failed to deserialize message on {connection.topic}: {e}")
                        # Continue with basic record if deserialization fails
                    
                    message_data.append(message_record)
                    message_count += 1
                    
                    # Log progress for large bags
                    if message_count % 10000 == 0:
                        _logger.debug(f"Indexed {message_count} messages with content...")
                
                # Create topic-specific DataFrames (replacing sparse DataFrame)
                if message_data:
                    # Group messages by topic
                    topic_groups = {}
                    for record in message_data:
                        topic_name = record['topic']
                        if topic_name not in topic_groups:
                            topic_groups[topic_name] = []
                        topic_groups[topic_name].append(record)
                    
                    # Create DataFrame for each topic
                    total_dataframes_created = 0
                    total_memory_saved = 0
                    
                    for topic_name, topic_messages in topic_groups.items():
                        if not topic_messages:
                            continue
                            
                        # Create DataFrame for this topic
                        topic_df = pd.DataFrame(topic_messages)
                        
                        # Remove completely empty columns for this topic
                        topic_df = topic_df.dropna(axis=1, how='all')
                        
                        # Optimize DataFrame dtypes for memory efficiency
                        if 'timestamp_sec' in topic_df.columns:
                            topic_df['timestamp_sec'] = topic_df['timestamp_sec'].astype('float64')
                        if 'timestamp_ns' in topic_df.columns:
                            topic_df['timestamp_ns'] = topic_df['timestamp_ns'].astype('int64')
                        if 'topic' in topic_df.columns:
                            topic_df['topic'] = topic_df['topic'].astype('category')
                        if 'message_type' in topic_df.columns:
                            topic_df['message_type'] = topic_df['message_type'].astype('category')
                        if 'message_size' in topic_df.columns:
                            topic_df['message_size'] = topic_df['message_size'].astype('int32')
                        
                        # Optimize numeric columns
                        for col in topic_df.columns:
                            if col not in ['timestamp_sec', 'timestamp_ns', 'topic', 'message_type', 'message_size', 'connection_id']:
                                if topic_df[col].dtype == 'object':
                                    # Try to convert to numeric if possible
                                    try:
                                        numeric_col = pd.to_numeric(topic_df[col], errors='coerce')
                                        # Only convert if we have some numeric values
                                        if not numeric_col.isna().all():
                                            topic_df[col] = numeric_col
                                    except:
                                        pass
                        
                        # Set timestamp as index for time-based analysis
                        if 'timestamp_sec' in topic_df.columns:
                            topic_df.set_index('timestamp_sec', inplace=True)
                            topic_df.sort_index(inplace=True)
                        
                        # Store DataFrame in the corresponding TopicInfo
                        topic_info = quick_info.find_topic(topic_name)
                        if topic_info:
                            topic_info.set_dataframe(topic_df)
                            total_dataframes_created += 1
                            
                            # Calculate memory saved compared to sparse approach
                            if topic_info.df_memory_usage:
                                total_memory_saved += topic_info.df_memory_usage
                    
                    _logger.info(f"Created {total_dataframes_created} topic-specific DataFrames with {message_count} total messages")
                    _logger.info(f"Memory efficient storage: {total_memory_saved / 1024 / 1024:.1f} MB (vs sparse DataFrame)")
                else:
                    _logger.warning("No messages found in bag file")
                
                # Update aggregated statistics from DataFrames
                quick_info.refresh_all_statistics_from_dataframes()
                
                # Update metadata
                quick_info.last_updated = time.time()
                self._current_bag_info = quick_info
                
                elapsed = time.time() - start_time
                _logger.info(f"Index analysis completed in {elapsed:.3f}s - {message_count} messages indexed")
                
                return quick_info, elapsed
                
        except Exception as e:
            _logger.error(f"Error in index analysis for {bag_path}: {e}")
            raise Exception(f"Error in index analysis: {e}")
    
    def _flatten_message_fields(self, msg: Any, prefix: str = '', max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """
        Flatten message fields into a dictionary for DataFrame storage
        
        Args:
            msg: The deserialized message object
            prefix: Field name prefix for nested structures
            max_depth: Maximum nesting depth to prevent infinite recursion
            current_depth: Current nesting depth
            
        Returns:
            Dictionary of flattened field values
        """
        flattened = {}
        
        if current_depth >= max_depth:
            return flattened
        
        try:
            # Handle different message types
            if hasattr(msg, '__dict__'):
                # Standard message with attributes
                for field_name, field_value in msg.__dict__.items():
                    if field_name.startswith('_'):
                        continue  # Skip private fields
                    
                    full_field_name = f"{prefix}.{field_name}" if prefix else field_name
                    
                    # Handle different data types
                    if field_value is None:
                        flattened[full_field_name] = None
                    elif isinstance(field_value, (int, float, bool, str)):
                        flattened[full_field_name] = field_value
                    elif isinstance(field_value, (list, tuple)):
                        # Handle arrays/lists
                        if len(field_value) == 0:
                            flattened[f"{full_field_name}_length"] = 0
                        else:
                            flattened[f"{full_field_name}_length"] = len(field_value)
                            # Store first few elements for arrays of primitives
                            for i, item in enumerate(field_value[:5]):  # Limit to first 5 elements
                                if isinstance(item, (int, float, bool, str)):
                                    flattened[f"{full_field_name}[{i}]"] = item
                                elif hasattr(item, '__dict__') and current_depth < max_depth - 1:
                                    # Nested object in array
                                    nested = self._flatten_message_fields(
                                        item, f"{full_field_name}[{i}]", max_depth, current_depth + 1
                                    )
                                    flattened.update(nested)
                    elif hasattr(field_value, '__dict__') and current_depth < max_depth - 1:
                        # Nested message
                        nested = self._flatten_message_fields(
                            field_value, full_field_name, max_depth, current_depth + 1
                        )
                        flattened.update(nested)
                    else:
                        # Convert other types to string representation
                        flattened[full_field_name] = str(field_value)
            
            elif hasattr(msg, '__slots__'):
                # Message with slots
                for field_name in msg.__slots__:
                    if hasattr(msg, field_name):
                        field_value = getattr(msg, field_name)
                        full_field_name = f"{prefix}.{field_name}" if prefix else field_name
                        
                        if isinstance(field_value, (int, float, bool, str)):
                            flattened[full_field_name] = field_value
                        elif field_value is None:
                            flattened[full_field_name] = None
                        elif hasattr(field_value, '__dict__') and current_depth < max_depth - 1:
                            nested = self._flatten_message_fields(
                                field_value, full_field_name, max_depth, current_depth + 1
                            )
                            flattened.update(nested)
                        else:
                            flattened[full_field_name] = str(field_value)
            
        except Exception as e:
            _logger.warning(f"Error flattening message fields: {e}")
        
        return flattened
    
    def _parse_message_definition(self, msgdef: str) -> Dict[str, Any]:
        """
        Parse ROS message definition string into structured field information
        
        Args:
            msgdef: Message definition string from connection metadata
            
        Returns:
            Dictionary containing field structure information
        """
        if not msgdef:
            return {}
        
        fields = {}
        lines = msgdef.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Skip constant definitions (contain '=')
            if '=' in line:
                continue
            
            # Parse field definition: "type name" or "type[] name"
            parts = line.split()
            if len(parts) >= 2:
                field_type = parts[0]
                field_name = parts[1]
                
                field_info = {
                    'type': field_type,
                    'is_array': '[]' in field_type,
                    'is_builtin': self._is_builtin_type(field_type.replace('[]', ''))
                }
                
                # For complex types, we could recursively parse them
                # but for now, we'll just mark them as complex
                if not field_info['is_builtin']:
                    field_info['is_complex'] = True
                
                fields[field_name] = field_info
        
        return fields
    
    def _is_builtin_type(self, type_name: str) -> bool:
        """Check if a type is a ROS builtin type"""
        builtin_types = {
            'bool', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32',
            'int64', 'uint64', 'float32', 'float64', 'string', 'time', 'duration'
        }
        return type_name in builtin_types
    
    def _parse_message_definition_to_fields(self, msgdef: str) -> List[MessageFieldInfo]:
        """
        Parse ROS message definition string into MessageFieldInfo objects with nested structure
        
        Args:
            msgdef: Message definition string from connection metadata
            
        Returns:
            List of MessageFieldInfo objects with proper nesting
        """
        if not msgdef:
            return []
        
        # Split the message definition by MSG: separators to handle nested types
        sections = msgdef.split('================================================================================')
        
        # Parse the main message (first section)
        main_section = sections[0] if sections else msgdef
        main_fields = self._parse_message_section(main_section)
        
        # Parse nested message types (additional sections)
        nested_types = {}
        for i in range(1, len(sections)):
            section = sections[i].strip()
            if section.startswith('MSG:'):
                # Extract message type name
                lines = section.split('\n')
                if len(lines) > 0:
                    msg_line = lines[0].strip()
                    if msg_line.startswith('MSG:'):
                        msg_type = msg_line[4:].strip()  # Remove 'MSG: ' prefix
                        # Parse fields for this nested type
                        nested_content = '\n'.join(lines[1:])
                        nested_fields = self._parse_message_section(nested_content)
                        nested_types[msg_type] = nested_fields
        
        # Helper to recursively link nested fields
        def link_fields(fields_list, visited_types=None):
            if visited_types is None:
                visited_types = set()
                
            for field in fields_list:
                if not field.is_builtin and field.nested_fields is None:
                    # Avoid infinite recursion if type references itself
                    if field.field_type in visited_types:
                        continue
                        
                    # Try exact match first
                    target_nested = None
                    if field.field_type in nested_types:
                        target_nested = nested_types[field.field_type]
                    else:
                        # Try partial match (e.g., 'Header' matches 'std_msgs/Header')
                        for nested_type_name, nested_fields_list in nested_types.items():
                            if nested_type_name.endswith('/' + field.field_type) or nested_type_name == field.field_type:
                                target_nested = nested_fields_list
                                break
                    
                    if target_nested:
                        # Create a copy to prevent shared state issues if we modify it
                        # But MessageFieldInfo is a dataclass...
                        # Actually we need to link deeply.
                        
                        # IMPORTANT: We must propagate this linking!
                        # But we can't just assign the list, we need to potentially link *its* children.
                        
                        # Let's clone the list of fields to attach to this node
                        import copy
                        field.nested_fields = copy.deepcopy(target_nested)
                        
                        # Recurse into these new fields
                        new_visited = visited_types | {field.field_type}
                        link_fields(field.nested_fields, new_visited)

        # Now link nested fields to their parent fields recursively
        link_fields(main_fields)
        
        return main_fields
    
    def _parse_message_section(self, section: str) -> List[MessageFieldInfo]:
        """Parse a single message section into fields"""
        fields = []
        lines = section.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Skip MSG: lines
            if line.startswith('MSG:'):
                continue
                
            # Skip constant definitions (contain '=')
            if '=' in line:
                continue
            
            # Parse field definition: "type name" or "type[] name"
            parts = line.split()
            if len(parts) >= 2:
                field_type_raw = parts[0]
                field_name = parts[1]
                
                # Check if it's an array
                is_array = '[]' in field_type_raw
                field_type = field_type_raw.replace('[]', '')
                
                # Determine array size (None for dynamic arrays)
                array_size = None
                if '[' in field_type_raw and ']' in field_type_raw:
                    # Extract array size if specified like [10]
                    try:
                        start = field_type_raw.find('[')
                        end = field_type_raw.find(']')
                        size_str = field_type_raw[start+1:end]
                        if size_str:
                            array_size = int(size_str)
                    except (ValueError, IndexError):
                        pass  # Keep array_size as None for dynamic arrays
                
                # Check if it's a builtin type
                is_builtin = self._is_builtin_type(field_type)
                
                # Create MessageFieldInfo object
                field_info = MessageFieldInfo(
                    field_name=field_name,
                    field_type=field_type,
                    is_array=is_array,
                    array_size=array_size,
                    is_builtin=is_builtin,
                    nested_fields=None  # Will be populated later if it's a complex type
                )
                
                fields.append(field_info)
        
        return fields


def create_reader() -> BagReader:
    """Create or get singleton reader instance"""
    return BagReader()

