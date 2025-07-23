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
    """High-performance rosbags implementation using AnyReader/Rosbag1Writer with memory optimization"""
    
    # Memory optimization constants
    CHUNK_SIZE = 10000  # Messages per chunk for memory efficiency
    CHUNK_MEMORY_LIMIT = 64 * 1024 * 1024  # 64MB per chunk
    
    def __init__(self):
        """Initialize rosbags parser"""
        if not ROSBAGS_AVAILABLE:
            raise ImportError("rosbags library is not available")
        self._registered_types = set()
        # Initialize type system optimization
        self._typestore = None
        self._message_cache = {}
        _logger.debug("Initialized RosbagsBagParser with enhanced performance features and memory optimization")
    
    def _initialize_typestore(self):
        """Initialize optimized typestore for better performance"""
        if self._typestore is None:
            try:
                from rosbags.typesys import get_typestore, Stores
                self._typestore = get_typestore(Stores.ROS1_NOCT)
                _logger.debug("Initialized optimized typestore for ROS1")
            except Exception as e:
                _logger.warning(f"Could not initialize typestore optimization: {e}")
                self._typestore = None
    
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
    
    def _optimize_compression_settings(self, writer: Any, compression: str) -> None:
        """Optimize compression settings based on compression type"""
        rosbags_compression = self._get_compression_format(compression)
        if rosbags_compression:
            writer.set_compression(rosbags_compression)
            
            # Optimize chunk threshold based on compression type
            if compression == 'lz4':
                # LZ4 benefits from larger chunks for better compression ratio
                writer.set_chunk_threshold(256 * 1024)  # 256KB chunks
                _logger.debug("Set LZ4 chunk threshold to 256KB for optimal performance")
            elif compression == 'bz2':
                # BZ2 benefits from smaller chunks for better parallelism
                writer.set_chunk_threshold(64 * 1024)   # 64KB chunks
                _logger.debug("Set BZ2 chunk threshold to 64KB for optimal performance")
    
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
    
    def _in_time_range(self, timestamp: int, time_range: Optional[Tuple]) -> bool:
        """Check if timestamp is within the specified time range"""
        if not time_range:
            return True
        start_ns, end_ns = self._convert_time_range(time_range)
        if start_ns is None or end_ns is None:
            return True
        return start_ns <= timestamp <= end_ns
    
    def _setup_writer_connections(self, writer: Any, selected_connections: List[Any]) -> Dict[str, Any]:
        """Setup writer connections once for efficient reuse"""
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
        
        return topic_connections
    
    def _write_chunk_sorted(self, writer: Any, topic_connections: Dict[str, Any], 
                           chunk: List[Tuple], progress_callback: Optional[Callable] = None) -> int:
        """Write a chunk of messages after sorting by timestamp"""
        if not chunk:
            return 0
        
        # Sort chunk by timestamp for chronological order
        chunk.sort(key=lambda x: x[1])
        
        # Write messages immediately to reduce memory usage
        messages_written = 0
        for connection, timestamp, rawdata in chunk:
            writer.write(topic_connections[connection.topic], timestamp, rawdata)
            messages_written += 1
        
        return messages_written
    
    def _process_bag_chunked(self, reader: Any, selected_connections: List[Any], 
                           writer: Any, time_range: Optional[Tuple],
                           progress_callback: Optional[Callable] = None) -> int:
        """Process bag using memory-efficient chunked approach"""
        # Setup writer connections once
        topic_connections = self._setup_writer_connections(writer, selected_connections)
        
        chunk = []
        total_processed = 0
        chunk_memory_usage = 0
        
        # Process messages in chunks for memory efficiency
        for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
            # Apply time range filtering early
            if not self._in_time_range(timestamp, time_range):
                continue
            
            # Add to current chunk
            chunk.append((connection, timestamp, rawdata))
            chunk_memory_usage += len(rawdata)
            
            # Process chunk when size or memory limit is reached
            if (len(chunk) >= self.CHUNK_SIZE or 
                chunk_memory_usage >= self.CHUNK_MEMORY_LIMIT):
                
                # Write chunk and update progress
                written = self._write_chunk_sorted(writer, topic_connections, chunk, progress_callback)
                total_processed += written
                
                # Clear chunk to free memory
                chunk.clear()
                chunk_memory_usage = 0
                
                # Update progress
                if progress_callback:
                    try:
                        progress_callback(total_processed)
                    except TypeError:
                        # Handle different callback signatures
                        pass
        
        # Process remaining messages in final chunk
        if chunk:
            written = self._write_chunk_sorted(writer, topic_connections, chunk, progress_callback)
            total_processed += written
        
        return total_processed
    
    def _count_messages_single_pass(self, reader: Any, selected_connections: List[Any], 
                                  time_range: Optional[Tuple]) -> int:
        """Count messages in single pass for efficiency"""
        total_count = 0
        
        for connection in selected_connections:
            for (_, timestamp, _) in reader.messages([connection]):
                if self._in_time_range(timestamp, time_range):
                    total_count += 1
        
        return total_count
    
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
        """Filter bag with simple progress callback using memory-efficient chunked processing"""
        # Initialize typestore for better performance
        self._initialize_typestore()
        
        # Quick check for empty selection
        if not selected_connections:
            _logger.warning(f"No messages found for selected topics")
            if progress_callback:
                progress_callback(100)  # type: ignore
            return "No messages found for selected topics"
        
        # Write messages to output bag using chunked processing
        output_path = Path(output_bag)
        writer = Rosbag1Writer(output_path)  # type: ignore
        
        # Apply optimized compression settings
        self._optimize_compression_settings(writer, rosbags_compression or 'none')
        
        with writer:
            # Process bag using memory-efficient chunked approach
            total_processed = self._process_bag_chunked(
                reader, selected_connections, writer, time_range, progress_callback
            )
            
            # Update final progress
            if progress_callback:
                progress_callback(100)  # type: ignore
        
        end_time = time.time()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)
        
        _logger.info(f"Filtered {total_processed} messages from {len(selected_connections)} topics in {elapsed:.2f}s (memory-optimized chunked processing)")
        
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
        
        # Phase 3: Write messages using chunked processing
        output_path = Path(output_bag)
        writer = Rosbag1Writer(output_path)  # type: ignore
        
        # Apply optimized compression settings
        self._optimize_compression_settings(writer, rosbags_compression or 'none')
        
        with writer:
            # Process the collected messages using chunked approach for memory efficiency
            topic_connections = self._setup_writer_connections(writer, selected_connections)
            
            # Process messages in chunks to maintain chronological order
            total_written = 0
            chunk_size = self.CHUNK_SIZE
            
            for i in range(0, len(messages_to_write), chunk_size):
                chunk = messages_to_write[i:i + chunk_size]
                written = self._write_chunk_sorted(writer, topic_connections, chunk)
                total_written += written
                
                # Update progress
                progress = min(100, int((i + len(chunk)) / len(messages_to_write) * 100))
                topic_progress_callback(len(selected_connections) + 1, "Writing messages", 
                                      i + len(chunk), len(messages_to_write), "processing")
            
            # Update final progress
            topic_progress_callback(len(selected_connections) + 1, "Writing messages", 
                                  len(messages_to_write), len(messages_to_write), "completed")
        
        end_time = time.time()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)
        
        _logger.info(f"Filtered {len(messages_to_write)} messages from {len(selected_connections)} topics in {elapsed:.2f}s (chronologically sorted)")
        
        return f"Filtering completed in {int(mins)}m {secs:.2f}s"
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file and return topics, connections and time range using optimized AnyReader"""
        try:
            # Initialize typestore for better performance
            self._initialize_typestore()
            
            reader_args = [Path(bag_path)]
            if self._typestore:
                with AnyReader(reader_args, typestore=self._typestore) as reader:  # type: ignore
                    return self._extract_bag_metadata(reader)
            else:
                with AnyReader(reader_args) as reader:  # type: ignore
                    return self._extract_bag_metadata(reader)
                
        except Exception as e:
            _logger.error(f"Error loading bag with AnyReader: {e}")
            raise Exception(f"Error loading bag: {e}")
    
    def _extract_bag_metadata(self, reader: Any) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Extract metadata from bag reader efficiently"""
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
        """Get message counts for each topic using optimized single-pass approach"""
        try:
            # Use the comprehensive stats method and extract counts
            stats = self.get_topic_stats(bag_path)
            return {topic: stats[topic]['count'] for topic in stats}
            
        except Exception as e:
            _logger.error(f"Error getting message counts: {e}")
            raise Exception(f"Error getting message counts: {e}")

    def get_topic_sizes(self, bag_path: str) -> Dict[str, int]:
        """Get total size in bytes for each topic using optimized single-pass approach"""
        try:
            # Use the comprehensive stats method and extract sizes
            stats = self.get_topic_stats(bag_path)
            return {topic: stats[topic]['size'] for topic in stats}
                
        except Exception as e:
            _logger.error(f"Error getting topic sizes: {e}")
            raise Exception(f"Error getting topic sizes: {e}")
    
    def get_topic_stats(self, bag_path: str) -> Dict[str, Dict[str, int]]:
        """Get comprehensive statistics for each topic using memory-efficient streaming"""
        try:
            # Initialize typestore for better performance
            self._initialize_typestore()
            
            reader_args = [Path(bag_path)]
            if self._typestore:
                with AnyReader(reader_args, typestore=self._typestore) as reader:  # type: ignore
                    return self._calculate_stats_streaming(reader)
            else:
                with AnyReader(reader_args) as reader:  # type: ignore
                    return self._calculate_stats_streaming(reader)
                
        except Exception as e:
            _logger.error(f"Error getting topic stats: {e}")
            raise Exception(f"Error getting topic stats: {e}")
    
    def _calculate_stats_streaming(self, reader: Any) -> Dict[str, Dict[str, int]]:
        """Calculate statistics using memory-efficient streaming approach"""
        topic_stats = {}
        
        # Process each connection's messages in streaming fashion
        for connection in reader.connections:
            count = 0
            total_size = 0
            min_size = float('inf')
            max_size = 0
            
            # Stream messages one by one to avoid memory buildup
            for (_, _, rawdata) in reader.messages([connection]):
                count += 1
                msg_size = len(rawdata)
                total_size += msg_size
                min_size = min(min_size, msg_size)
                max_size = max(max_size, msg_size)
            
            # Calculate statistics
            avg_size = total_size // count if count > 0 else 0
            min_size = min_size if min_size != float('inf') else 0
            
            topic_stats[connection.topic] = {
                'count': count,
                'size': total_size,
                'avg_size': avg_size,
                'min_size': min_size,
                'max_size': max_size
            }
        
        return topic_stats
    
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
