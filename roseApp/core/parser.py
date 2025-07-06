"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
Uses rosbags library for better performance and full compression support.
"""

import time
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Tuple, List, Dict, Optional, Callable
from pathlib import Path

from rosbags.rosbag2 import Reader, Writer
from rosbags.rosbag1 import Reader as Rosbag1Reader, Writer as Rosbag1Writer
from rosbags.serde import deserialize_cdr, serialize_cdr
from rosbags.typesys import get_types_from_msg, register_types

from roseApp.core.util import TimeUtil, get_logger

_logger = get_logger(__name__)


class FileExistsError(Exception):
    """Custom exception for file exists scenarios"""
    pass


class ParserType(Enum):
    """Enum for different parser implementations"""
    PYTHON = "python"
    CPP = "cpp"
    ROSBAGS = "rosbags"  # New rosbags-based implementation


class IBagParser(ABC):
    """Abstract base class for bag parser implementations"""
    
    @abstractmethod
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        """
        Load topics from whitelist file
        
        Args:
            whitelist_path: Path to the whitelist file
            
        Returns:
            List of topic names
        """
        pass
    
    @abstractmethod
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], 
                  time_range: Optional[Tuple] = None, 
                  progress_callback: Optional[Callable] = None,
                  compression: str = 'none',
                  overwrite: bool = False) -> str:
        """
        Filter rosbag using selected implementation
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Optional tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
            progress_callback: Optional callback function that accepts a float (0-100) progress percentage
            compression: Compression type ('none', 'bz2', 'lz4')
        
        Returns:
            Status message with completion time
        """
        pass
    
    @abstractmethod
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """
        Load bag file and return topics, connections and time range
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Tuple containing:
            - List of topics
            - Dict mapping topics to message types
            - Tuple of (start_time, end_time)
        """
        pass
    
    @abstractmethod
    def inspect_bag(self, bag_path: str) -> str:
        """
        List all topics and message types
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Formatted string containing bag information
        """
        pass

    @abstractmethod
    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """
        Get message counts for each topic in the bag file
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Dict mapping topic names to message counts
        """
        pass


class RosbagsBagParser(IBagParser):
    """High-performance rosbags implementation of bag parser"""
    
    def __init__(self):
        """Initialize rosbags parser"""
        self._registered_types = set()
    
    def _ensure_types_registered(self, reader):
        """Ensure all message types are registered for serialization"""
        try:
            # Register types for all connections that have message definitions
            for connection in reader.connections:
                msg_type = connection.msgtype
                if msg_type not in self._registered_types:
                    try:
                        # Try to register types using msgdef if available
                        if hasattr(connection, 'msgdef') and connection.msgdef:
                            type_map = get_types_from_msg(connection.msgdef, msg_type)
                            register_types(type_map)
                            self._registered_types.add(msg_type)
                            _logger.debug(f"Registered type: {msg_type}")
                    except Exception as e:
                        # If type registration fails, continue - rosbags might handle it automatically
                        _logger.debug(f"Could not register type {msg_type}: {e}")
                        pass
        except Exception as e:
            _logger.warning(f"Type registration warning: {e}")
    
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        """Load topics from whitelist file"""
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
    
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], 
                  time_range: Optional[Tuple] = None,
                  progress_callback: Optional[Callable] = None,
                  compression: str = 'none',
                  overwrite: bool = False) -> str:
        """
        Filter rosbag using rosbags library
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Optional tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
            progress_callback: Optional callback function to report progress percentage (0-100)
            compression: Compression type ('none', 'bz2', 'lz4')
            overwrite: Whether to overwrite existing output file
        
        Returns:
            Status message with completion time
        """
        try:
            # Validate compression type before starting
            from roseApp.core.util import validate_compression_type
            is_valid, error_message = validate_compression_type(compression)
            if not is_valid:
                raise ValueError(error_message)
            
            start_time = time.time()
            
            # Convert compression format for rosbags
            rosbags_compression = self._convert_compression_format(compression)
            
            # Count total messages first
            total_messages = 0
            selected_topic_counts = {}
            
            with Rosbag1Reader(Path(input_bag)) as reader:
                # Get connections for selected topics
                selected_connections = []
                for connection in reader.connections:
                    if connection.topic in topics:
                        selected_connections.append(connection)
                        count = sum(1 for _ in reader.messages([connection]))
                        selected_topic_counts[connection.topic] = count
                        total_messages += count
            
            if total_messages == 0:
                _logger.warning(f"No messages found for selected topics in {input_bag}")
                if progress_callback:
                    progress_callback(100)
                return "No messages found for selected topics"
            
            # Convert time range
            start_ns = None
            end_ns = None
            if time_range:
                start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
                end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
            
            # Start filtering process
            with Rosbag1Reader(Path(input_bag)) as reader:
                # Try to ensure types are registered (optional, rosbags often handles this automatically)
                try:
                    self._ensure_types_registered(reader)
                except Exception as e:
                    _logger.debug(f"Type registration skipped: {e}")
                    # Continue without type registration - rosbags often works without it
                
                # Create output bag
                output_path = Path(output_bag)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Check if output file exists
                if output_path.exists() and not overwrite:
                    raise FileExistsError(f"Output file '{output_bag}' already exists. Use overwrite=True to overwrite.")
                
                # Remove existing file if overwrite is True
                if output_path.exists() and overwrite:
                    output_path.unlink()
                
                writer = Rosbag1Writer(output_path)
                
                # Set compression if specified
                if rosbags_compression != 'none':
                    compression_format = self._get_compression_format(rosbags_compression)
                    if compression_format:
                        writer.set_compression(compression_format)
                
                with writer:
                    # Add connections for selected topics
                    topic_connections = {}
                    for connection in reader.connections:
                        if connection.topic in topics:
                            # Extract connection information with proper defaults
                            # Get callerid from ext attribute if available
                            callerid = '/unknown'
                            if hasattr(connection, 'ext') and hasattr(connection.ext, 'callerid'):
                                if connection.ext.callerid is not None:
                                    callerid = connection.ext.callerid
                            
                            msgdef = getattr(connection, 'msgdef', None)
                            md5sum = getattr(connection, 'digest', None)
                            
                            new_connection = writer.add_connection(
                                topic=connection.topic,
                                msgtype=connection.msgtype,
                                msgdef=msgdef,
                                md5sum=md5sum,
                                callerid=callerid
                            )
                            topic_connections[connection.topic] = new_connection
                    
                    # Process messages
                    processed_messages = 0
                    last_progress = -1
                    
                    for connection, timestamp, rawdata in reader.messages():
                        if connection.topic in topics:
                            # Check time range
                            if time_range:
                                if timestamp < start_ns or timestamp > end_ns:
                                    continue
                            
                            # Write message
                            writer.write(topic_connections[connection.topic], timestamp, rawdata)
                            
                            # Update progress
                            processed_messages += 1
                            if progress_callback and total_messages > 0:
                                current_progress = int((processed_messages / total_messages) * 100)
                                if current_progress != last_progress:
                                    progress_callback(current_progress)
                                    last_progress = current_progress
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            
            # Ensure final progress is 100%
            if progress_callback and last_progress < 100:
                progress_callback(100)
                
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            # Re-raise ValueError as is (for compression validation errors)
            raise ve
        except FileExistsError as fe:
            # Re-raise FileExistsError as is (for file overwrite handling)
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def _convert_compression_format(self, compression: str) -> str:
        """Convert compression format from our format to rosbags format"""
        compression_map = {
            'none': 'none',
            'bz2': 'bz2',
            'lz4': 'lz4'
        }
        return compression_map.get(compression, 'none')
    
    def _get_compression_format(self, compression: str):
        """Get rosbags CompressionFormat enum from string"""
        try:
            from rosbags.rosbag1 import Writer
            if compression == 'bz2':
                return Writer.CompressionFormat.BZ2
            elif compression == 'lz4':
                return Writer.CompressionFormat.LZ4
            else:
                return None
        except Exception:
            return None
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """
        Load bag file and return topics, connections and time range
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Tuple containing:
            - List of topics
            - Dict mapping topics to message types
            - Tuple of (start_time, end_time)
        """
        try:
            with Rosbag1Reader(Path(bag_path)) as reader:
                # Get topics and message types
                topics = []
                connections = {}
                
                for connection in reader.connections:
                    topics.append(connection.topic)
                    connections[connection.topic] = connection.msgtype
                
                # Get time range
                start_time = reader.start_time
                end_time = reader.end_time
                
                # Convert nanoseconds to (seconds, nanoseconds)
                start_tuple = (int(start_time // 1_000_000_000), int(start_time % 1_000_000_000))
                end_tuple = (int(end_time // 1_000_000_000), int(end_time % 1_000_000_000))
                
                return topics, connections, (start_tuple, end_tuple)
                
        except Exception as e:
            _logger.error(f"Error loading bag: {e}")
            raise Exception(f"Error loading bag: {e}")
    
    def inspect_bag(self, bag_path: str) -> str:
        """
        List all topics and message types in the bag file
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Formatted string containing bag information
        """
        try:
            topics, connections, (start_time, end_time) = self.load_bag(bag_path)
            
            result = [f"\nTopics in {bag_path}:"]
            result.append("{:<40} {:<30}".format("Topic", "Message Type"))
            result.append("-" * 80)
            for topic in topics:
                result.append("{:<40} {:<30}".format(topic, connections[topic]))
            
            result.append(f"\nTime range: {TimeUtil.to_datetime(start_time)} - {TimeUtil.to_datetime(end_time)}")
            return "\n".join(result)
            
        except Exception as e:
            _logger.error(f"Error inspecting bag file: {e}")
            raise Exception(f"Error inspecting bag file: {e}")

    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """
        Get message counts for each topic in the bag file
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Dict mapping topic names to message counts
        """
        try:
            message_counts = {}
            with Rosbag1Reader(Path(bag_path)) as reader:
                for connection in reader.connections:
                    count = sum(1 for _ in reader.messages([connection]))
                    message_counts[connection.topic] = count
            return message_counts
            
        except Exception as e:
            _logger.error(f"Error getting message counts: {e}")
            raise Exception(f"Error getting message counts: {e}")


class BagParser(IBagParser):
    """Legacy rosbag implementation - kept for backward compatibility"""
    
    def __init__(self):
        """Initialize legacy parser"""
        _logger.warning("Using legacy rosbag parser. Consider migrating to RosbagsBagParser for better performance.")
    
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
    
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], 
                  time_range: Optional[Tuple] = None,
                  progress_callback: Optional[Callable] = None,
                  compression: str = 'none',
                  overwrite: bool = False) -> str:
        """
        Filter rosbag using legacy rosbag Python API
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Optional tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
            progress_callback: Optional callback function to report progress percentage (0-100)
            compression: Compression type ('none', 'bz2', 'lz4')
            overwrite: Whether to overwrite existing output file
        
        Returns:
            Status message with completion time
        """
        try:
            import rosbag
            
            # Check if output file exists
            if os.path.exists(output_bag) and not overwrite:
                raise FileExistsError(f"Output file '{output_bag}' already exists. Use overwrite=True to overwrite.")
            
            # Remove existing file if overwrite is True
            if os.path.exists(output_bag) and overwrite:
                os.remove(output_bag)
            
            # Validate compression type before starting
            from roseApp.core.util import validate_compression_type
            is_valid, error_message = validate_compression_type(compression)
            if not is_valid:
                raise ValueError(error_message)
            
            start_time = time.time()
            
            # Get total messages for progress tracking
            total_messages = 0
            selected_topic_counts = {}
            
            with rosbag.Bag(input_bag, 'r') as inbag:
                info = inbag.get_type_and_topic_info()
                for topic in topics:
                    if topic in info.topics:
                        count = info.topics[topic].message_count
                        selected_topic_counts[topic] = count
                        total_messages += count
            
            if total_messages == 0:
                _logger.warning(f"No messages found for selected topics in {input_bag}")
                if progress_callback:
                    progress_callback(100)
                return "No messages found for selected topics"
            
            # Start filtering process
            with rosbag.Bag(output_bag, 'w', compression=compression) as outbag:
                # Convert time range
                start_sec = None
                end_sec = None
                if time_range:
                    start_sec = time_range[0][0] + time_range[0][1]/1e9
                    end_sec = time_range[1][0] + time_range[1][1]/1e9
                
                # Process messages
                processed_messages = 0
                last_progress = -1
                
                for topic, msg, t in rosbag.Bag(input_bag).read_messages(topics=topics):
                    # Check time range
                    msg_time = t.to_sec()
                    if time_range:
                        if msg_time >= start_sec and msg_time <= end_sec:
                            outbag.write(topic, msg, t)
                    else:
                        outbag.write(topic, msg, t)
                    
                    # Update progress
                    processed_messages += 1
                    if progress_callback and total_messages > 0:
                        current_progress = int((processed_messages / total_messages) * 100)
                        if current_progress != last_progress:
                            progress_callback(current_progress)
                            last_progress = current_progress

            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            
            if progress_callback and last_progress < 100:
                progress_callback(100)
                
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            # Re-raise FileExistsError as is (for file overwrite handling)
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file and return topics, connections and time range"""
        try:
            import rosbag
            
            with rosbag.Bag(bag_path) as bag:
                # Get topics and message types
                info = bag.get_type_and_topic_info()
                topics = list(info.topics.keys())
                connections = {topic: data.msg_type for topic, data in info.topics.items()}
                
                # Get time range
                start_time = bag.get_start_time()
                end_time = bag.get_end_time()
                
                # Convert to (seconds, nanoseconds)
                start = (int(start_time), int((start_time % 1) * 1e9))
                end = (int(end_time), int((end_time % 1) * 1e9))
                
                return topics, connections, (start, end)
                
        except Exception as e:
            _logger.error(f"Error loading bag: {e}")
            raise Exception(f"Error loading bag: {e}")
    
    def inspect_bag(self, bag_path: str) -> str:
        """List all topics and message types in the bag file"""
        try:
            topics, connections, (start_time, end_time) = self.load_bag(bag_path)
            
            result = [f"\nTopics in {bag_path}:"]
            result.append("{:<40} {:<30}".format("Topic", "Message Type"))
            result.append("-" * 80)
            for topic in topics:
                result.append("{:<40} {:<30}".format(topic, connections[topic]))
            
            result.append(f"\nTime range: {TimeUtil.to_datetime(start_time)} - {TimeUtil.to_datetime(end_time)}")
            return "\n".join(result)
            
        except Exception as e:
            _logger.error(f"Error inspecting bag file: {e}")
            raise Exception(f"Error inspecting bag file: {e}")

    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """Get message counts for each topic in the bag file"""
        try:
            import rosbag
            
            with rosbag.Bag(bag_path) as bag:
                info = bag.get_type_and_topic_info()
                return {topic: data.message_count for topic, data in info.topics.items()}
                
        except Exception as e:
            _logger.error(f"Error getting message counts: {e}")
            raise Exception(f"Error getting message counts: {e}")


def create_parser(parser_type: ParserType) -> IBagParser:
    """
    Factory function to create parser instances
    
    Args:
        parser_type: Type of parser to create
        
    Returns:
        Instance of IBagParser implementation
        
    Raises:
        ValueError: If parser_type is CPP but C++ implementation is not available
    """
    if parser_type == ParserType.PYTHON:
        return BagParser()
    elif parser_type == ParserType.ROSBAGS:
        return RosbagsBagParser()
    elif parser_type == ParserType.CPP:     
        raise ValueError("C++ implementation not available.")
    else:
        raise ValueError(f"Unknown parser type: {parser_type}")
