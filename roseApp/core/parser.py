"""
Enhanced ROS bag parser module using rosbags library.

This module provides comprehensive bag parsing capabilities using the modern
rosbags library for high performance and reliability.
"""

import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, Any, Union, TYPE_CHECKING
from dataclasses import dataclass

# Import rosbags modules at module level to avoid repeated imports
try:
    from rosbags.highlevel import AnyReader
    from rosbags.rosbag1 import Writer as Rosbag1Writer
    ROSBAGS_AVAILABLE = True
except ImportError:
    AnyReader = None
    Rosbag1Writer = None
    ROSBAGS_AVAILABLE = False

if TYPE_CHECKING and ROSBAGS_AVAILABLE:
    # For type checking, import the actual types
    from rosbags.highlevel import AnyReader
    from rosbags.rosbag1 import Writer as Rosbag1Writer

from roseApp.core.util import get_logger

_logger = get_logger("parser")


class FileExistsError(Exception):
    """Custom exception for file existence errors"""
    pass


class ParserType(Enum):
    """Enum for parser implementation"""
    ROSBAGS = "rosbags"  # Enhanced rosbags-based implementation


@dataclass
class ParserHealth:
    """Parser health status information"""
    available: bool
    version: Optional[str] = None
    performance_score: float = 0.0
    last_check: float = 0.0
    error_message: Optional[str] = None
    
    def is_healthy(self) -> bool:
        """Check if parser is healthy and available"""
        return self.available and not self.error_message


class IBagParser(ABC):
    """Abstract base class for bag parser implementations"""
    
    @abstractmethod
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        """Load topics from whitelist file"""
        pass
    
    @abstractmethod
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], 
                  time_range: Optional[Tuple] = None, 
                  progress_callback: Optional[Callable] = None,
                  compression: str = 'none',
                  overwrite: bool = False) -> str:
        """Filter rosbag using rosbags implementation"""
        pass
    
    @abstractmethod
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file and return topics, connections and time range"""
        pass
    
    @abstractmethod
    def inspect_bag(self, bag_path: str) -> str:
        """List all topics and message types"""
        pass

    @abstractmethod
    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """Get message counts for each topic in the bag file"""
        pass

    @abstractmethod
    def get_topic_sizes(self, bag_path: str) -> Dict[str, int]:
        """Get total size in bytes for each topic in the bag file"""
        pass

    @abstractmethod
    def get_topic_stats(self, bag_path: str) -> Dict[str, Dict[str, int]]:
        """Get comprehensive statistics for each topic"""
        pass

    @abstractmethod
    def read_messages(self, bag_path: str, topics: List[str]):
        """Read messages from specified topics in the bag file"""
        pass


class RosbagsBagParser(IBagParser):
    """High-performance rosbags implementation using AnyReader/Rosbag1Writer"""
    
    def __init__(self):
        """Initialize rosbags parser"""
        if not ROSBAGS_AVAILABLE:
            raise ImportError("rosbags library is not available")
        self._registered_types = set()
        _logger.debug("Initialized RosbagsBagParser with enhanced performance features")
    
    def _validate_compression(self, compression: str) -> None:
        """Validate compression type"""
        from roseApp.core.util import validate_compression_type
        is_valid, error_message = validate_compression_type(compression)
        if not is_valid:
            raise ValueError(error_message)
    
    def _get_compression_format(self, compression: str):
        """Get rosbags CompressionFormat enum from string"""
        try:
            if compression == 'bz2':
                return Rosbag1Writer.CompressionFormat.BZ2  # type: ignore
            elif compression == 'lz4':
                return Rosbag1Writer.CompressionFormat.LZ4  # type: ignore
            else:
                return None
        except Exception:
            return None
    
    def _prepare_output_file(self, output_bag: str, overwrite: bool) -> None:
        """Prepare output file, handling existence and overwrite logic"""
        if os.path.exists(output_bag) and not overwrite:
            raise FileExistsError(f"Output file '{output_bag}' already exists. Use overwrite=True to overwrite.")
        
        if os.path.exists(output_bag) and overwrite:
            os.remove(output_bag)
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_bag)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
    
    def _convert_time_range(self, time_range: Optional[Tuple]) -> Tuple[Optional[int], Optional[int]]:
        """Convert time range to nanoseconds"""
        if not time_range:
            return None, None
        
        start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
        end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
        return start_ns, end_ns
    
    def _collect_messages_chronologically(self, reader: Any, selected_connections: List[Any], 
                                        time_range: Optional[Tuple]) -> List[Tuple]:
        """Collect all messages from selected connections and sort chronologically"""
        messages_to_write = []
        start_ns, end_ns = self._convert_time_range(time_range)
        
        # Collect all messages from selected connections
        for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
            # Check time range if specified
            if time_range and (timestamp < start_ns or timestamp > end_ns):
                continue
            
            messages_to_write.append((connection, timestamp, rawdata))
        
        # Sort messages by timestamp to ensure chronological order
        messages_to_write.sort(key=lambda x: x[1])
        return messages_to_write
    
    def _write_messages_to_bag(self, writer: Any, selected_connections: List[Any], 
                             messages_to_write: List[Tuple]) -> Dict[str, Any]:
        """Write messages to output bag and return connection mapping"""
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
        
        # Write messages in chronological order
        for connection, timestamp, rawdata in messages_to_write:
            writer.write(topic_connections[connection.topic], timestamp, rawdata)
        
        return topic_connections
    
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
                  progress_callback: Optional[Union[Callable[[float], None], 
                                                  Callable[[int, str, int, int, str], None]]] = None,
                  compression: str = 'none',
                  overwrite: bool = False) -> str:
        """
        Filter bag file by topics and time range using AnyReader for performance
        
        Supports both simple progress callback (float) and detailed topic progress callback
        (topic_index, topic_name, processed_count, total_count, status)
        """
        try:
            # Validate compression type
            self._validate_compression(compression)
            
            # Prepare output file
            self._prepare_output_file(output_bag, overwrite)
            
            start_time = time.time()
            rosbags_compression = self._get_compression_format(compression)
            
            # Determine callback type
            is_topic_progress = (progress_callback and 
                               hasattr(progress_callback, '__code__') and 
                               progress_callback.__code__.co_argcount >= 5)
            
            with AnyReader([Path(input_bag)]) as reader:  # type: ignore
                # Pre-filter connections based on selected topics
                selected_connections = [
                    conn for conn in reader.connections 
                    if conn.topic in topics
                ]
                
                if not selected_connections:
                    _logger.warning(f"No matching topics found in {input_bag}")
                    if progress_callback and not is_topic_progress:
                        progress_callback(100)  # type: ignore
                    return "No messages found for selected topics"
                
                if is_topic_progress:
                    return self._filter_with_topic_progress(
                        reader, selected_connections, output_bag, time_range,
                        rosbags_compression, progress_callback, start_time
                    )
                else:
                    return self._filter_with_simple_progress(
                        reader, selected_connections, output_bag, time_range,
                        rosbags_compression, progress_callback, start_time
                    )
                    
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag with AnyReader: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def _filter_with_simple_progress(self, reader: Any, selected_connections: List[Any], 
                                   output_bag: str, time_range: Optional[Tuple],
                                   rosbags_compression: Any, progress_callback: Optional[Callable],
                                   start_time: float) -> str:
        """Filter bag with simple progress callback"""
        # Count total messages for progress tracking
        total_messages = 0
        for connection in selected_connections:
            count = sum(1 for _ in reader.messages([connection]))
            total_messages += count
        
        if total_messages == 0:
            _logger.warning(f"No messages found for selected topics")
            if progress_callback:
                progress_callback(100)  # type: ignore
            return "No messages found for selected topics"
        
        # Collect all messages chronologically
        messages_to_write = self._collect_messages_chronologically(
            reader, selected_connections, time_range
        )
        
        # Write messages to output bag
        output_path = Path(output_bag)
        writer = Rosbag1Writer(output_path)  # type: ignore
        
        if rosbags_compression:
            writer.set_compression(rosbags_compression)
        
        with writer:
            self._write_messages_to_bag(writer, selected_connections, messages_to_write)
            
            # Update progress
            if progress_callback:
                progress_callback(100)  # type: ignore
        
        end_time = time.time()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)
        
        _logger.info(f"Filtered {len(messages_to_write)} messages from {len(selected_connections)} topics in {elapsed:.2f}s (chronologically sorted)")
        
        return f"Filtering completed in {int(mins)}m {secs:.2f}s"
    
    def _filter_with_topic_progress(self, reader: Any, selected_connections: List[Any], 
                                  output_bag: str, time_range: Optional[Tuple],
                                  rosbags_compression: Any, topic_progress_callback: Any,
                                  start_time: float) -> str:
        """Filter bag with detailed topic-by-topic progress tracking"""
        # Phase 1: Analyze topics and count messages
        topic_progress_callback(0, "Initialization", 0, 0, "analyzing")
        
        topic_message_counts = {}
        for i, connection in enumerate(selected_connections):
            topic = connection.topic
            topic_progress_callback(i, topic, 0, 0, "analyzing")
            
            # Count messages efficiently
            count = sum(1 for _ in reader.messages([connection]))
            topic_message_counts[topic] = count
            
            topic_progress_callback(i, topic, count, count, "completed")
        
        total_messages = sum(topic_message_counts.values())
        if total_messages == 0:
            _logger.warning(f"No messages found for selected topics")
            return "No messages found for selected topics"
        
        # Phase 2: Collect messages topic by topic for progress tracking
        messages_to_write = []
        start_ns, end_ns = self._convert_time_range(time_range)
        
        total_processed = 0
        for topic_index, connection in enumerate(selected_connections):
            topic = connection.topic
            topic_total = topic_message_counts[topic]
            topic_processed = 0
            
            topic_progress_callback(topic_index, topic, 0, topic_total, "processing")
            
            # Collect all messages for this topic
            for (conn, timestamp, rawdata) in reader.messages([connection]):
                # Check time range if specified
                if time_range and (timestamp < start_ns or timestamp > end_ns):
                    continue
                
                messages_to_write.append((conn, timestamp, rawdata))
                topic_processed += 1
                total_processed += 1
                
                # Update progress every 100 messages or at 10% intervals
                if (topic_processed % 100 == 0 or 
                    topic_processed % max(1, topic_total // 10) == 0 or
                    topic_processed == topic_total):
                    topic_progress_callback(
                        topic_index, topic, 
                        topic_processed, topic_total, 
                        "processing"
                    )
            
            # Mark topic as completed
            topic_progress_callback(topic_index, topic, topic_processed, topic_total, "completed")
        
        # Sort all messages by timestamp to ensure chronological order
        topic_progress_callback(len(selected_connections), "Sorting messages", 0, len(messages_to_write), "processing")
        messages_to_write.sort(key=lambda x: x[1])
        topic_progress_callback(len(selected_connections), "Sorting messages", len(messages_to_write), len(messages_to_write), "completed")
        
        # Phase 3: Write messages in chronological order
        output_path = Path(output_bag)
        writer = Rosbag1Writer(output_path)  # type: ignore
        
        if rosbags_compression:
            writer.set_compression(rosbags_compression)
        
        with writer:
            self._write_messages_to_bag(writer, selected_connections, messages_to_write)
            
            # Update final progress
            topic_progress_callback(len(selected_connections) + 1, "Writing messages", len(messages_to_write), len(messages_to_write), "completed")
        
        end_time = time.time()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)
        
        _logger.info(f"Filtered {len(messages_to_write)} messages from {len(selected_connections)} topics in {elapsed:.2f}s (chronologically sorted)")
        
        return f"Filtering completed in {int(mins)}m {secs:.2f}s"
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file and return topics, connections and time range using AnyReader"""
        try:
            with AnyReader([Path(bag_path)]) as reader:  # type: ignore
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
                size = float(size_bytes)
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024:
                        return f"{size:.1f}{unit}"
                    size /= 1024
                return f"{size:.1f}TB"
            
            from roseApp.core.util import TimeUtil
            
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
            with AnyReader([Path(bag_path)]) as reader:  # type: ignore
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
            with AnyReader([Path(bag_path)]) as reader:  # type: ignore
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
            with AnyReader([Path(bag_path)]) as reader:  # type: ignore
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
            with AnyReader([Path(bag_path)]) as reader:  # type: ignore
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


def check_rosbags_availability() -> ParserHealth:
    """Check rosbags parser availability and health"""
    try:
        if not ROSBAGS_AVAILABLE:
            raise ImportError("rosbags modules not available")
        
        # Try to get version
        try:
            import rosbags
            version = getattr(rosbags, '__version__', 'unknown')
        except:
            version = 'unknown'
        
        return ParserHealth(
            available=True,
            version=version,
            performance_score=100.0,
            last_check=time.time()
        )
        
    except ImportError as e:
        return ParserHealth(
            available=False,
            error_message=f"rosbags not available: {e}",
            last_check=time.time()
        )
    except Exception as e:
        return ParserHealth(
            available=False,
            error_message=f"rosbags health check failed: {e}",
            last_check=time.time()
        )


def create_parser() -> IBagParser:
    """Create parser instance"""
    health = check_rosbags_availability()
    if not health.is_healthy():
        raise RuntimeError(f"rosbags parser is not available: {health.error_message}")
    
    return RosbagsBagParser()


def create_best_parser() -> IBagParser:
    """Create the best available parser (same as create_parser)"""
    return create_parser()


def get_parser_health() -> ParserHealth:
    """Get health status for rosbags parser"""
    return check_rosbags_availability()


def check_parser_availability() -> Dict[str, bool]:
    """Check availability of rosbags parser"""
    health = check_rosbags_availability()
    return {"rosbags": health.is_healthy()}
