"""
ROS bag parser module using C++ implementation for better performance.
This module provides the same interface as parser.py but uses rosbag_io_py for operations.
"""

import time
import logging
from pathlib import Path
from typing import Tuple, List, Dict
from textual.logging import TextualHandler

# Third-party imports
import rosbag_io_py

# Add this at the top of the file, after imports
_logger = None

def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance with the given name"""
    global _logger
    if _logger is None:
        _logger = _setup_logging()
    return _logger.getChild(name) if name else _logger

def setup_logging():
    """Backward compatibility function"""
    return get_logger()

def _setup_logging():
    """Configure logging settings for the application"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Define log file path
    log_file = log_dir / "rose_tui.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Stream handler for console output
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Set default level to INFO
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    
    # Add custom handler for Textual if needed
    try:
        textual_handler = TextualHandler()
        textual_handler.setFormatter(formatter)
        root_logger.addHandler(textual_handler)
    except ImportError:
        pass
    
    return root_logger

# Call setup_logging once when module is imported
_logger = _setup_logging()

class BagParserCPP:
    """
    A class that handles ROS bag file operations using C++ implementation.
    Provides the same interface as BagParser but with better performance.
    """
    
    @staticmethod
    def load_whitelist(whitelist_path: str) -> List[str]:
        """
        Load topics from whitelist file
        
        Args:
            whitelist_path: Path to the whitelist file
            
        Returns:
            List of topic names
        """
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
    
    @staticmethod
    def filter_bag(input_bag: str, output_bag: str, topics: List[str], time_range: Tuple) -> str:
        """
        Filter rosbag using C++ interface
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Tuple of (start_time, end_time)
        
        Returns:
            Status message with completion time
        """
        try:
            start_time = time.time()
            io = rosbag_io_py.rosbag_io()
            
            _logger.info(f"Filtering bag: {input_bag} to {output_bag}")
            _logger.info(f"Topics: {topics}")
            _logger.info(f"Time range: {time_range}")
            
            io.load(str(input_bag))
            io.dump(str(output_bag), topics, time_range)
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except Exception as e:
            _logger.error(f"Error filtering bag: {e}")
            raise Exception(f"Error filtering bag: {e}")

    @staticmethod
    def load_bag(bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
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
        io = rosbag_io_py.rosbag_io()
        io.load(bag_path)
        topics = io.get_topics()
        connections = io.get_connections()
        timerange = io.get_time_range()
        
        return topics, connections, timerange
    
    @staticmethod
    def inspect_bag(bag_path: str) -> str:
        """
        List all topics and message types using C++ interface
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Formatted string containing bag information
        """
        try:
            topics, connections, (start_time, end_time) = BagParserCPP.load_bag(bag_path)
            
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

class TimeUtil:
    """Utility class for handling time conversions"""
    
    @staticmethod
    def to_datetime(time_tuple: Tuple[int, int]) -> str:
        """
        Convert (seconds, nanoseconds) tuple to [YY/MM/DD HH:MM:SS] formatted string
        
        Args:
            time_tuple: Tuple of (seconds, nanoseconds)
            
        Returns:
            Formatted time string
        """
        if not time_tuple or len(time_tuple) != 2:
            return "N.A"
        
        seconds, nanoseconds = time_tuple
        total_seconds = seconds + nanoseconds / 1e9
        return time.strftime("%y/%m/%d %H:%M:%S", time.localtime(total_seconds))

    @staticmethod
    def from_datetime(time_str: str) -> Tuple[int, int]:
        """
        Convert [YY/MM/DD HH:MM:SS] formatted string to (seconds, nanoseconds) tuple
        
        Args:
            time_str: Time string in YY/MM/DD HH:MM:SS format
            
        Returns:
            Tuple of (seconds, nanoseconds)
        """
        try:
            # Parse time string to time struct
            time_struct = time.strptime(time_str, "%y/%m/%d %H:%M:%S")
            # Convert to Unix timestamp
            total_seconds = time.mktime(time_struct)
            # Return (seconds, nanoseconds) tuple
            return (int(total_seconds), 0)
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}. Expected format: YY/MM/DD HH:MM:SS")

    @staticmethod
    def convert_time_range_to_tuple(start_time_str: str, end_time_str: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Create time range from start and end time strings
        
        Args:
            start_time_str: Start time in YY/MM/DD HH:MM:SS format
            end_time_str: End time in YY/MM/DD HH:MM:SS format
            
        Returns:
            Tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
        """
        try:
            start_time = TimeUtil.from_datetime(start_time_str)
            end_time = TimeUtil.from_datetime(end_time_str)
            # make sure start and end are within range of output bag file
            start_time = (start_time[0] - 1, start_time[1])
            end_time = (end_time[0] + 1, end_time[1]) 
            return (start_time, end_time)
        except ValueError as e:
            raise ValueError(f"Invalid time range format: {e}")