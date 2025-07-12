"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
Uses rosbags library for better performance and full compression support.
"""

import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable

from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Writer as Rosbag1Writer
from rosbags.typesys import get_types_from_msg, register_types

from roseApp.core.util import TimeUtil, get_logger

_logger = get_logger("parser")


class FileExistsError(Exception):
    """Custom exception for file existence errors"""
    pass


class ParserType(Enum):
    """Enum for different parser implementations"""
    CPP = "cpp"
    ROSBAGS = "rosbags"  # Enhanced rosbags-based implementation (default)


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

    @abstractmethod
    def get_topic_sizes(self, bag_path: str) -> Dict[str, int]:
        """
        Get total size in bytes for each topic in the bag file
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            Dictionary mapping topic names to total size in bytes
        """
        pass

    @abstractmethod
    def get_topic_stats(self, bag_path: str) -> Dict[str, Dict[str, int]]:
        """
        Get comprehensive statistics for each topic (count and size) in the bag file
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            Dictionary mapping topic names to stats dict containing:
            - count: number of messages
            - size: total size in bytes
            - avg_size: average message size in bytes
        """
        pass

    @abstractmethod
    def read_messages(self, bag_path: str, topics: List[str]):
        """
        Read messages from specified topics in the bag file
        
        Args:
            bag_path: Path to bag file
            topics: List of topic names to read from
            
        Yields:
            Tuple of (timestamp, message) where:
            - timestamp: tuple of (seconds, nanoseconds)
            - message: deserialized ROS message
        """
        pass


class RosbagsBagParser(IBagParser):
    """High-performance rosbags implementation using AnyReader/Rosbag1Writer"""
    
    def __init__(self):
        """Initialize enhanced rosbags parser"""
        self._registered_types = set()
        # Use debug level to avoid noise during command completion
        _logger.debug("Initialized RosbagsBagParser with enhanced performance features")
    
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
        Filter rosbag using enhanced rosbags AnyReader/Rosbag1Writer
        
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
            
            # Check if output file exists
            if os.path.exists(output_bag) and not overwrite:
                raise FileExistsError(f"Output file '{output_bag}' already exists. Use overwrite=True to overwrite.")
            
            # Remove existing file if overwrite is True
            if os.path.exists(output_bag) and overwrite:
                os.remove(output_bag)
            
            start_time = time.time()
            
            # Convert compression format for rosbags
            rosbags_compression = self._get_compression_format(compression)
            
            # Initialize progress tracking variables
            last_progress = -1
            processed_messages = 0
            
            # Count total messages first for progress tracking
            total_messages = 0
            selected_topic_counts = {}
            
            # Use AnyReader for enhanced performance
            with AnyReader([Path(input_bag)]) as reader:
                # Pre-filter connections based on selected topics
                selected_connections = [
                    conn for conn in reader.connections 
                    if conn.topic in topics
                ]
                
                if not selected_connections:
                    _logger.warning(f"No matching topics found in {input_bag}")
                    if progress_callback:
                        progress_callback(100)
                    return "No messages found for selected topics"
                
                # Count messages for each selected topic
                for connection in selected_connections:
                    # Use efficient message counting
                        count = sum(1 for _ in reader.messages([connection]))
                        selected_topic_counts[connection.topic] = count
                        total_messages += count
            
            if total_messages == 0:
                _logger.warning(f"No messages found for selected topics in {input_bag}")
                if progress_callback:
                    progress_callback(100)
                return "No messages found for selected topics"
            
                # Create output directory if needed
                output_dir = os.path.dirname(output_bag)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Filter and write messages using Rosbag1Writer
                output_path = Path(output_bag)
                writer = Rosbag1Writer(output_path)
                
                # Set compression if specified
                if rosbags_compression:
                    writer.set_compression(rosbags_compression)
                
                with writer:
                    # Convert time range if provided
                    start_ns = None
                    end_ns = None
                    if time_range:
                        start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
                        end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
                    
                    # Add connections to writer
                    topic_connections = {}
                    for connection in selected_connections:
                        # Extract connection information with proper defaults
                        callerid = '/rosbags_enhanced_parser'
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
                    
                    # Process messages with progress tracking
                    
                    # Use efficient message iteration with pre-filtered connections
                    for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
                        # Check time range if specified
                        if time_range:
                            if timestamp < start_ns or timestamp > end_ns:
                                continue
                        
                        # Write message using connection mapping
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
            
            if progress_callback and last_progress < 100:
                progress_callback(100)
                
            # Log performance statistics
            _logger.info(f"Filtered {processed_messages} messages from {len(selected_connections)} topics in {elapsed:.2f}s")
                
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag with AnyReader: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def _get_compression_format(self, compression: str):
        """Get rosbags CompressionFormat enum from string"""
        try:
            if compression == 'bz2':
                return Rosbag1Writer.CompressionFormat.BZ2
            elif compression == 'lz4':
                return Rosbag1Writer.CompressionFormat.LZ4
            else:
                return None
        except Exception:
            return None
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file and return topics, connections and time range using AnyReader"""
        try:
            with AnyReader([Path(bag_path)]) as reader:
                # Get topics and message types
                topics = [conn.topic for conn in reader.connections]
                connections = {conn.topic: conn.msgtype for conn in reader.connections}
                
                # Get time range (AnyReader provides nanosecond timestamps)
                start_ns = reader.start_time
                end_ns = reader.end_time
                
                # Convert nanoseconds to (seconds, nanoseconds)
                start = (int(start_ns // 1_000_000_000), int(start_ns % 1_000_000_000))
                end = (int(end_ns // 1_000_000_000), int(end_ns % 1_000_000_000))
                
                return topics, connections, (start, end)
                
        except Exception as e:
            _logger.error(f"Error loading bag with AnyReader: {e}")
            raise Exception(f"Error loading bag: {e}")
    
    def inspect_bag(self, bag_path: str) -> str:
        """List all topics and message types in the bag file using AnyReader"""
        try:
            topics, connections, (start_time, end_time) = self.load_bag(bag_path)
            
            # Get topic statistics
            topic_stats = self.get_topic_stats(bag_path)
            
            # Helper function to format size
            def format_size(size_bytes: int) -> str:
                """Format size in bytes to human readable format"""
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024:
                        return f"{size_bytes:.1f}{unit}"
                    size_bytes /= 1024
                return f"{size_bytes:.1f}TB"
            
            result = [f"\nTopics in {bag_path}:"]
            result.append("{:<35} {:<35} {:<10} {:<10}".format("Topic", "Message Type", "Count", "Size"))
            result.append("-" * 90)
            
            for topic in topics:
                stats = topic_stats.get(topic, {'count': 0, 'size': 0})
                count = stats['count']
                size = stats['size']
                
                result.append("{:<35} {:<35} {:<10} {:<10}".format(
                    topic[:33], 
                    connections[topic][:33], 
                    count, 
                    format_size(size)
                ))
            
            # Calculate totals
            total_count = sum(stats['count'] for stats in topic_stats.values())
            total_size = sum(stats['size'] for stats in topic_stats.values())
            
            result.append("-" * 90)
            result.append(f"Total: {len(topics)} topics, {total_count} messages, {format_size(total_size)}")
            result.append(f"\nTime range: {TimeUtil.to_datetime(start_time)} - {TimeUtil.to_datetime(end_time)}")
            return "\n".join(result)
            
        except Exception as e:
            _logger.error(f"Error inspecting bag file: {e}")
            raise Exception(f"Error inspecting bag file: {e}")

    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """Get message counts for each topic in the bag file using AnyReader"""
        try:
            with AnyReader([Path(bag_path)]) as reader:
                # Count messages for each topic
                topic_counts = {}
                
                for connection in reader.connections:
                    # Count messages efficiently
                    count = sum(1 for _ in reader.messages([connection]))
                    topic_counts[connection.topic] = count
                
                return topic_counts
            
        except Exception as e:
            _logger.error(f"Error getting message counts: {e}")
            raise Exception(f"Error getting message counts: {e}")

    def get_topic_sizes(self, bag_path: str) -> Dict[str, int]:
        """Get total size in bytes for each topic in the bag file using AnyReader"""
        try:
            with AnyReader([Path(bag_path)]) as reader:
                # Calculate sizes for each topic
                topic_sizes = {}
                
                for connection in reader.connections:
                    # Sum up message sizes for this topic
                    total_size = 0
                    for (_, _, rawdata) in reader.messages([connection]):
                        total_size += len(rawdata)
                    
                    topic_sizes[connection.topic] = total_size
                
                return topic_sizes
                
        except Exception as e:
            _logger.error(f"Error getting topic sizes: {e}")
            raise Exception(f"Error getting topic sizes: {e}")
    
    def get_topic_stats(self, bag_path: str) -> Dict[str, Dict[str, int]]:
        """Get comprehensive statistics for each topic using AnyReader"""
        try:
            with AnyReader([Path(bag_path)]) as reader:
                # Calculate both counts and sizes efficiently
                topic_stats = {}
                
                for connection in reader.connections:
                    count = 0
                    total_size = 0
                    
                    # Process messages for this topic
                    for (_, _, rawdata) in reader.messages([connection]):
                        count += 1
                        total_size += len(rawdata)
                    
                    # Calculate average size
                    avg_size = total_size // count if count > 0 else 0
                    
                    topic_stats[connection.topic] = {
                        'count': count,
                        'size': total_size,
                        'avg_size': avg_size
                    }
                
                return topic_stats
                
        except Exception as e:
            _logger.error(f"Error getting topic stats: {e}")
            raise Exception(f"Error getting topic stats: {e}")
    
    def read_messages(self, bag_path: str, topics: List[str]):
        """
        Read messages from specified topics in the bag file
        
        Args:
            bag_path: Path to bag file
            topics: List of topic names to read from
            
        Yields:
            Tuple of (timestamp, message) where:
            - timestamp: tuple of (seconds, nanoseconds)
            - message: deserialized ROS message
        """
        try:
            with AnyReader([Path(bag_path)]) as reader:
                # Pre-filter connections based on selected topics
                selected_connections = [
                    conn for conn in reader.connections 
                    if conn.topic in topics
                ]
                
                if not selected_connections:
                    _logger.warning(f"No matching topics found in {bag_path}")
                    return
                
                # Use AnyReader's high-level message iteration with automatic deserialization
                for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
                    try:
                        # Use AnyReader's built-in deserialize method
                        msg = reader.deserialize(rawdata, connection.msgtype)
                        
                        # Convert nanosecond timestamp to (seconds, nanoseconds) format
                        seconds = timestamp // 1_000_000_000
                        nanoseconds = timestamp % 1_000_000_000
                        time_tuple = (int(seconds), int(nanoseconds))
                        
                        yield (time_tuple, msg)
                        
                    except Exception as e:
                        _logger.warning(f"Could not deserialize message for {connection.topic} ({connection.msgtype}): {e}")
                        continue
                
        except Exception as e:
            _logger.error(f"Error reading messages from bag with AnyReader: {e}")
            raise Exception(f"Error reading messages from bag: {e}")


def create_parser(parser_type: ParserType = ParserType.ROSBAGS) -> IBagParser:
    """
    Factory function to create parser instances
    
    Args:
        parser_type: Type of parser to create (defaults to ROSBAGS for best performance)
        
    Returns:
        Instance of IBagParser implementation
        
    Raises:
        ValueError: If parser_type is CPP but C++ implementation is not available
    """
    if parser_type == ParserType.ROSBAGS:
        return RosbagsBagParser()
    elif parser_type == ParserType.CPP:     
        raise ValueError("C++ implementation not available.")
    else:
        raise ValueError(f"Unknown parser type: {parser_type}")


def create_best_parser() -> IBagParser:
    """
    Create the best available parser based on system capabilities
    
    Returns:
        Instance of the best available IBagParser implementation (always RosbagsBagParser)
    """
    return RosbagsBagParser()
