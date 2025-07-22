"""
Enhanced ROS bag parser module with intelligent parser management.

This module provides comprehensive bag parsing capabilities with automatic
parser selection, health checking, and fallback mechanisms.
"""

import os
import time
import threading
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, Any
from dataclasses import dataclass

from roseApp.core.util import get_logger

_logger = get_logger("parser")


class FileExistsError(Exception):
    """Custom exception for file existence errors"""
    pass


class ParserType(Enum):
    """Enum for different parser implementations"""
    ROSBAGS = "rosbags"  # Enhanced rosbags-based implementation (default)
    LEGACY = "legacy"    # Legacy rosbag implementation (fallback)


@dataclass
class ParserHealth:
    """Parser health status information"""
    parser_type: ParserType
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
        """Filter rosbag using selected implementation"""
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
        """Initialize enhanced rosbags parser"""
        self._registered_types = set()
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
        """Filter bag file by topics and time range using AnyReader for performance"""
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
            
            # Use AnyReader for enhanced performance
            from rosbags.highlevel import AnyReader
            from rosbags.rosbag1 import Writer as Rosbag1Writer
            
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
                
                # Count total messages for progress tracking
                total_messages = 0
                for connection in selected_connections:
                    count = sum(1 for _ in reader.messages([connection]))
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
                
                # Collect all messages with timestamps for sorting
                messages_to_write = []
                
                # Convert time range if provided
                start_ns = None
                end_ns = None
                if time_range:
                    start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
                    end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
                
                # Collect all messages from selected connections
                for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
                    # Check time range if specified
                    if time_range:
                        if timestamp < start_ns or timestamp > end_ns:
                            continue
                    
                    messages_to_write.append((connection, timestamp, rawdata))
                
                # Sort messages by timestamp to ensure chronological order
                messages_to_write.sort(key=lambda x: x[1])
                
                # Filter and write messages using Rosbag1Writer
                output_path = Path(output_bag)
                writer = Rosbag1Writer(output_path)
                
                # Set compression if specified
                if rosbags_compression:
                    writer.set_compression(rosbags_compression)
                
                with writer:
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
                        
                        # Update progress
                        processed_messages += 1
                        if progress_callback and total_messages > 0:
                            current_progress = int((processed_messages / len(messages_to_write)) * 100)
                            if current_progress != last_progress:
                                progress_callback(current_progress)
                                last_progress = current_progress
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            
            if progress_callback and last_progress < 100:
                progress_callback(100)
                
            # Log performance statistics
            _logger.info(f"Filtered {processed_messages} messages from {len(selected_connections)} topics in {elapsed:.2f}s (chronologically sorted)")
                
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag with AnyReader: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def filter_bag_with_topic_progress(self, input_bag: str, output_bag: str, topics: List[str], 
                                     time_range: Optional[Tuple] = None,
                                     topic_progress_callback: Optional[Callable] = None,
                                     compression: str = 'none',
                                     overwrite: bool = False) -> str:
        """Filter bag file with detailed topic-by-topic progress tracking and chronological sorting"""
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
            
            # Use AnyReader for enhanced performance
            from rosbags.highlevel import AnyReader
            from rosbags.rosbag1 import Writer as Rosbag1Writer
            
            with AnyReader([Path(input_bag)]) as reader:
                # Pre-filter connections based on selected topics
                selected_connections = [
                    conn for conn in reader.connections 
                    if conn.topic in topics
                ]
                
                if not selected_connections:
                    _logger.warning(f"No matching topics found in {input_bag}")
                    return "No messages found for selected topics"
                
                # Phase 1: Analyze topics and count messages
                if topic_progress_callback:
                    topic_progress_callback(0, "Initialization", 0, 0, "analyzing")
                
                topic_message_counts = {}
                for i, connection in enumerate(selected_connections):
                    topic = connection.topic
                    if topic_progress_callback:
                        topic_progress_callback(i, topic, 0, 0, "analyzing")
                    
                    # Count messages efficiently
                    count = sum(1 for _ in reader.messages([connection]))
                    topic_message_counts[topic] = count
                    
                    if topic_progress_callback:
                        topic_progress_callback(i, topic, count, count, "completed")
                
                total_messages = sum(topic_message_counts.values())
                if total_messages == 0:
                    _logger.warning(f"No messages found for selected topics in {input_bag}")
                    return "No messages found for selected topics"
                
                # Create output directory if needed
                output_dir = os.path.dirname(output_bag)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Phase 2: Collect all messages with timestamps for chronological sorting
                messages_to_write = []
                
                    # Convert time range if provided
                start_ns = None
                end_ns = None
                if time_range:
                        start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
                        end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
                
                # Collect messages topic by topic for progress tracking
                total_processed = 0
                for topic_index, connection in enumerate(selected_connections):
                    topic = connection.topic
                    topic_total = topic_message_counts[topic]
                    topic_processed = 0
                    
                    if topic_progress_callback:
                        topic_progress_callback(topic_index, topic, 0, topic_total, "processing")
                    
                    # Collect all messages for this topic
                    for (conn, timestamp, rawdata) in reader.messages([connection]):
                        # Check time range if specified
                        if time_range:
                            if timestamp < start_ns or timestamp > end_ns:
                                continue
                        
                        messages_to_write.append((conn, timestamp, rawdata))
                        topic_processed += 1
                        total_processed += 1
                        
                        # Update progress every 100 messages or at 10% intervals
                        if (topic_processed % 100 == 0 or 
                            topic_processed % max(1, topic_total // 10) == 0 or
                            topic_processed == topic_total):
                            if topic_progress_callback:
                                topic_progress_callback(
                                    topic_index, topic, 
                                    topic_processed, topic_total, 
                                    "processing"
                                )
                    
                    # Mark topic as completed
                    if topic_progress_callback:
                        topic_progress_callback(topic_index, topic, topic_processed, topic_total, "completed")
                
                # Sort all messages by timestamp to ensure chronological order
                if topic_progress_callback:
                    topic_progress_callback(len(selected_connections), "Sorting messages", 0, len(messages_to_write), "processing")
                
                messages_to_write.sort(key=lambda x: x[1])
                
                if topic_progress_callback:
                    topic_progress_callback(len(selected_connections), "Sorting messages", len(messages_to_write), len(messages_to_write), "completed")
                
                # Phase 3: Write messages in chronological order
                output_path = Path(output_bag)
                writer = Rosbag1Writer(output_path)
                
                # Set compression if specified
                if rosbags_compression:
                    writer.set_compression(rosbags_compression)
                
                with writer:
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
                    
                    # Write all messages in chronological order
                    if topic_progress_callback:
                        topic_progress_callback(len(selected_connections) + 1, "Writing messages", 0, len(messages_to_write), "processing")
                    
                    written_messages = 0
                    for connection, timestamp, rawdata in messages_to_write:
                        writer.write(topic_connections[connection.topic], timestamp, rawdata)
                        written_messages += 1
                        
                        # Update progress every 1000 messages or at 5% intervals
                        if (written_messages % 1000 == 0 or 
                            written_messages % max(1, len(messages_to_write) // 20) == 0 or
                            written_messages == len(messages_to_write)):
                            if topic_progress_callback:
                                topic_progress_callback(
                                    len(selected_connections) + 1, "Writing messages", 
                                    written_messages, len(messages_to_write), 
                                    "processing"
                                )
                    
                    if topic_progress_callback:
                        topic_progress_callback(len(selected_connections) + 1, "Writing messages", written_messages, len(messages_to_write), "completed")
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            
            # Log performance statistics
            _logger.info(f"Filtered {written_messages} messages from {len(selected_connections)} topics in {elapsed:.2f}s (chronologically sorted)")
                
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag with topic progress: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def filter_bag_streaming(self, input_bag: str, output_bag: str, topics: List[str], 
                            time_range: Optional[Tuple] = None,
                            progress_callback: Optional[Callable] = None,
                            compression: str = 'none',
                            overwrite: bool = False,
                            chunk_size: int = 10000) -> str:
        """
        Filter bag file using streaming approach for large files
        
        This method processes messages in chunks to avoid memory issues with large bags,
        but may still produce overlap chunk warnings if timestamps are not strictly ordered.
        Use this for very large files where memory is a constraint.
        
        Args:
            chunk_size: Number of messages to process in each chunk (default: 10000)
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
            
            # Use AnyReader for enhanced performance
            from rosbags.highlevel import AnyReader
            from rosbags.rosbag1 import Writer as Rosbag1Writer
            
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
                
                # Count total messages for progress tracking
                total_messages = 0
                for connection in selected_connections:
                    count = sum(1 for _ in reader.messages([connection]))
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
                
                # Convert time range if provided
                start_ns = None
                end_ns = None
                if time_range:
                    start_ns = time_range[0][0] * 1_000_000_000 + time_range[0][1]
                    end_ns = time_range[1][0] * 1_000_000_000 + time_range[1][1]
                
                # Process messages in chunks with local sorting
                output_path = Path(output_bag)
                writer = Rosbag1Writer(output_path)
                
                # Set compression if specified
                if rosbags_compression:
                    writer.set_compression(rosbags_compression)
                
                with writer:
                    # Add connections to writer
                    topic_connections = {}
                    for connection in selected_connections:
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
                    
                    # Process messages in chunks
                    processed_messages = 0
                    last_progress = -1
                    message_buffer = []
                    
                    for (connection, timestamp, rawdata) in reader.messages(connections=selected_connections):
                        # Check time range if specified
                        if time_range:
                            if timestamp < start_ns or timestamp > end_ns:
                                continue
                        
                        message_buffer.append((connection, timestamp, rawdata))
                        
                        # Process chunk when buffer is full
                        if len(message_buffer) >= chunk_size:
                            # Sort current chunk by timestamp
                            message_buffer.sort(key=lambda x: x[1])
                            
                            # Write sorted chunk
                            for conn, ts, rd in message_buffer:
                                writer.write(topic_connections[conn.topic], ts, rd)
                                processed_messages += 1
                        
                        # Update progress
                                if progress_callback and total_messages > 0:
                                    current_progress = int((processed_messages / total_messages) * 100)
                                    if current_progress != last_progress:
                                        progress_callback(current_progress)
                                        last_progress = current_progress
                            
                            message_buffer.clear()
                    
                    # Process remaining messages
                    if message_buffer:
                        message_buffer.sort(key=lambda x: x[1])
                        for conn, ts, rd in message_buffer:
                            writer.write(topic_connections[conn.topic], ts, rd)
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
            _logger.info(f"Filtered {processed_messages} messages from {len(selected_connections)} topics in {elapsed:.2f}s (streaming with chunk size {chunk_size})")
                
            return f"Streaming filtering completed in {int(mins)}m {secs:.2f}s"
            
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error filtering bag with streaming: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def _get_compression_format(self, compression: str):
        """Get rosbags CompressionFormat enum from string"""
        try:
            from rosbags.rosbag1 import Writer as Rosbag1Writer
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
            from rosbags.highlevel import AnyReader
            
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
            from rosbags.highlevel import AnyReader
            
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
            from rosbags.highlevel import AnyReader
            
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
            from rosbags.highlevel import AnyReader
            
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
            from rosbags.highlevel import AnyReader
            
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


class LegacyBagParser(IBagParser):
    """Legacy rosbag parser implementation as fallback"""
    
    def __init__(self):
        """Initialize legacy parser"""
        _logger.info("Initialized LegacyBagParser for compatibility")
    
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
        """Filter bag using legacy rosbag implementation"""
        try:
            import rosbag
            
            # Check if output file exists
            if os.path.exists(output_bag) and not overwrite:
                raise FileExistsError(f"Output file '{output_bag}' already exists. Use overwrite=True to overwrite.")
            
            # Remove existing file if overwrite is True
            if os.path.exists(output_bag) and overwrite:
                os.remove(output_bag)
            
            start_time = time.time()
            
            # Create output directory if needed
            output_dir = os.path.dirname(output_bag)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Convert compression format for legacy rosbag
            compression_format = rosbag.Compression.NONE
            if compression == 'bz2':
                compression_format = rosbag.Compression.BZ2
            elif compression == 'lz4':
                compression_format = rosbag.Compression.LZ4
            
            processed_messages = 0
            total_messages = 0
            
            # Count total messages first for progress tracking
            with rosbag.Bag(input_bag, 'r') as input_bag_obj:
                for topic, _, _ in input_bag_obj.read_messages(topics=topics):
                    total_messages += 1
            
            if total_messages == 0:
                _logger.warning(f"No messages found for selected topics in {input_bag}")
                if progress_callback:
                    progress_callback(100)
                return "No messages found for selected topics"
            
            # Filter and write messages
            with rosbag.Bag(input_bag, 'r') as input_bag_obj:
                with rosbag.Bag(output_bag, 'w', compression=compression_format) as output_bag_obj:
                    
                    last_progress = -1
                    
                    for topic, msg, t in input_bag_obj.read_messages(topics=topics):
                        # Check time range if specified
                        if time_range:
                            msg_time = (t.secs, t.nsecs)
                            if (msg_time < time_range[0] or msg_time > time_range[1]):
                                continue
                        
                        output_bag_obj.write(topic, msg, t)
                        processed_messages += 1
                        
                        # Update progress
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
            
            _logger.info(f"Legacy filtered {processed_messages} messages in {elapsed:.2f}s")
            
            return f"Legacy filtering completed in {int(mins)}m {secs:.2f}s"
            
        except Exception as e:
            _logger.error(f"Error filtering bag with legacy parser: {e}")
            raise Exception(f"Error filtering bag: {e}")
    
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Load bag file using legacy rosbag"""
        try:
            import rosbag
            
            with rosbag.Bag(bag_path, 'r') as bag:
                # Get topics and message types
                info = bag.get_type_and_topic_info()
                topics = list(info.topics.keys())
                connections = {topic: info.topics[topic].msg_type for topic in topics}
                
                # Get time range
                start_time = bag.get_start_time()
                end_time = bag.get_end_time()
                
                # Convert to (seconds, nanoseconds) format
                start = (int(start_time), int((start_time % 1) * 1e9))
                end = (int(end_time), int((end_time % 1) * 1e9))
                
                return topics, connections, (start, end)
                
        except Exception as e:
            _logger.error(f"Error loading bag with legacy parser: {e}")
            raise Exception(f"Error loading bag: {e}")
    
    def inspect_bag(self, bag_path: str) -> str:
        """Inspect bag using legacy rosbag"""
        try:
            import rosbag
            
            topics, connections, (start_time, end_time) = self.load_bag(bag_path)
            topic_stats = self.get_topic_stats(bag_path)
            
            from roseApp.core.util import TimeUtil
            
            def format_size(size_bytes: int) -> str:
                size = float(size_bytes)
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024:
                        return f"{size:.1f}{unit}"
                    size /= 1024
                return f"{size:.1f}TB"
            
            result = [f"\nTopics in {bag_path} (Legacy Parser):"]
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
            
            total_count = sum(stats['count'] for stats in topic_stats.values())
            total_size = sum(stats['size'] for stats in topic_stats.values())
            
            result.append("-" * 90)
            result.append(f"Total: {len(topics)} topics, {total_count} messages, {format_size(total_size)}")
            result.append(f"\nTime range: {TimeUtil.to_datetime(start_time)} - {TimeUtil.to_datetime(end_time)}")
            return "\n".join(result)
            
        except Exception as e:
            _logger.error(f"Error inspecting bag with legacy parser: {e}")
            raise Exception(f"Error inspecting bag: {e}")
    
    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """Get message counts using legacy rosbag"""
        try:
            import rosbag
            
            with rosbag.Bag(bag_path, 'r') as bag:
                info = bag.get_type_and_topic_info()
                return {topic: info.topics[topic].message_count for topic in info.topics}
                
        except Exception as e:
            _logger.error(f"Error getting message counts with legacy parser: {e}")
            raise Exception(f"Error getting message counts: {e}")
    
    def get_topic_sizes(self, bag_path: str) -> Dict[str, int]:
        """Get topic sizes using legacy rosbag (estimated)"""
        try:
            import rosbag
            
            topic_sizes = {}
            
            with rosbag.Bag(bag_path, 'r') as bag:
                for topic, msg, _ in bag.read_messages():
                    if topic not in topic_sizes:
                        topic_sizes[topic] = 0
                    # Estimate size (this is approximate for legacy)
                    topic_sizes[topic] += len(str(msg))
            
            return topic_sizes
            
        except Exception as e:
            _logger.error(f"Error getting topic sizes with legacy parser: {e}")
            raise Exception(f"Error getting topic sizes: {e}")
    
    def get_topic_stats(self, bag_path: str) -> Dict[str, Dict[str, int]]:
        """Get topic statistics using legacy rosbag"""
        try:
            message_counts = self.get_message_counts(bag_path)
            topic_sizes = self.get_topic_sizes(bag_path)
            
            stats = {}
            for topic in message_counts:
                count = message_counts[topic]
                size = topic_sizes.get(topic, 0)
                avg_size = size // count if count > 0 else 0
                
                stats[topic] = {
                    'count': count,
                    'size': size,
                    'avg_size': avg_size
                }
            
            return stats
            
        except Exception as e:
            _logger.error(f"Error getting topic stats with legacy parser: {e}")
            raise Exception(f"Error getting topic stats: {e}")
    
    def read_messages(self, bag_path: str, topics: List[str]):
        """Read messages using legacy rosbag"""
        try:
            import rosbag
            
            with rosbag.Bag(bag_path, 'r') as bag:
                for topic, msg, t in bag.read_messages(topics=topics):
                    # Convert timestamp to (seconds, nanoseconds) format
                    time_tuple = (t.secs, t.nsecs)
                    yield (time_tuple, msg)
                    
        except Exception as e:
            _logger.error(f"Error reading messages with legacy parser: {e}")
            raise Exception(f"Error reading messages: {e}")


class ParserHealthChecker:
    """Health checker for parser implementations"""
    
    def __init__(self):
        self._health_cache: Dict[ParserType, ParserHealth] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = 300  # 5 minutes
    
    def check_parser_health(self, parser_type: ParserType, force_check: bool = False) -> ParserHealth:
        """Check health of a specific parser type"""
        with self._cache_lock:
            current_time = time.time()
            
            # Return cached result if available and not expired
            if not force_check and parser_type in self._health_cache:
                cached = self._health_cache[parser_type]
                if current_time - cached.last_check < self._cache_ttl:
                    return cached
            
            # Perform health check
            if parser_type == ParserType.ROSBAGS:
                health = self._check_rosbags_health()
            elif parser_type == ParserType.LEGACY:
                health = self._check_legacy_health()
            else:
                health = ParserHealth(
                    parser_type=parser_type,
                    available=False,
                    error_message=f"Unknown parser type: {parser_type}"
                )
            
            health.last_check = current_time
            self._health_cache[parser_type] = health
            
            return health
    
    def _check_rosbags_health(self) -> ParserHealth:
        """Check rosbags parser health"""
        try:
            from rosbags.highlevel import AnyReader
            from rosbags.rosbag1 import Writer as Rosbag1Writer
            
            # Try to get version
            try:
                import rosbags
                version = getattr(rosbags, '__version__', 'unknown')
            except:
                version = 'unknown'
            
            return ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True,
                version=version,
                performance_score=100.0  # High performance score
            )
            
        except ImportError as e:
            return ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=False,
                error_message=f"rosbags not available: {e}"
            )
        except Exception as e:
            return ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=False,
                error_message=f"rosbags health check failed: {e}"
            )
    
    def _check_legacy_health(self) -> ParserHealth:
        """Check legacy rosbag parser health"""
        try:
            import rosbag
            
            # Try to get version
            try:
                version = getattr(rosbag, '__version__', 'unknown')
            except:
                version = 'legacy'
            
            return ParserHealth(
                parser_type=ParserType.LEGACY,
                available=True,
                version=version,
                performance_score=30.0  # Lower performance score
            )
            
        except ImportError as e:
            return ParserHealth(
                parser_type=ParserType.LEGACY,
                available=False,
                error_message=f"legacy rosbag not available: {e}"
            )
        except Exception as e:
            return ParserHealth(
                parser_type=ParserType.LEGACY,
                available=False,
                error_message=f"legacy rosbag health check failed: {e}"
            )
    
    def get_best_parser(self) -> ParserType:
        """Get the best available parser based on health and performance"""
        # Check rosbags first (preferred)
        rosbags_health = self.check_parser_health(ParserType.ROSBAGS)
        if rosbags_health.is_healthy():
            return ParserType.ROSBAGS
        
        # Fall back to legacy
        legacy_health = self.check_parser_health(ParserType.LEGACY)
        if legacy_health.is_healthy():
            _logger.warning("Using legacy rosbag parser. Performance may be reduced. Consider installing rosbags for better performance.")
            return ParserType.LEGACY
        
        # No parser available
        raise RuntimeError("No healthy bag parser available. Please install rosbags or legacy rosbag.")
    
    def get_all_health_status(self) -> Dict[ParserType, ParserHealth]:
        """Get health status for all parsers"""
        return {
            ParserType.ROSBAGS: self.check_parser_health(ParserType.ROSBAGS),
            ParserType.LEGACY: self.check_parser_health(ParserType.LEGACY)
        }


# Global health checker
_health_checker = ParserHealthChecker()


def create_parser(parser_type: Optional[ParserType] = None) -> IBagParser:
    """Create parser instance with automatic type selection"""
    if parser_type is None:
        parser_type = _health_checker.get_best_parser()
    
    health = _health_checker.check_parser_health(parser_type)
    if not health.is_healthy():
        raise RuntimeError(f"Parser {parser_type.value} is not healthy: {health.error_message}")
    
    if parser_type == ParserType.ROSBAGS:
        return RosbagsBagParser()
    elif parser_type == ParserType.LEGACY:
        return LegacyBagParser()
    else:
        raise ValueError(f"Unknown parser type: {parser_type}")


def create_best_parser() -> IBagParser:
    """Create the best available parser"""
    best_type = _health_checker.get_best_parser()
    return create_parser(best_type)


def get_parser_health(parser_type: Optional[ParserType] = None) -> ParserHealth:
    """Get health status for a parser type"""
    if parser_type is None:
        parser_type = _health_checker.get_best_parser()
    return _health_checker.check_parser_health(parser_type)


def get_all_parser_health() -> Dict[ParserType, ParserHealth]:
    """Get health status for all parsers"""
    return _health_checker.get_all_health_status()


def check_parser_availability() -> Dict[str, bool]:
    """Check availability of all parsers"""
    health_status = get_all_parser_health()
    return {
        parser_type.value: health.is_healthy()
        for parser_type, health in health_status.items()
    }
