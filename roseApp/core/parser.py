"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
"""

import time
import logging
from typing import Tuple, List, Dict
import rosbag

_logger = logging.getLogger(__name__)

class BagParser:
    """
    A class that handles ROS bag file operations including reading, filtering and inspection.
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
        Filter rosbag using rosbag Python API
        
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
            
            _logger.info(f"Filtering bag: {input_bag} to {output_bag}")
            _logger.info(f"Topics: {topics}")
            _logger.info(f"Time range: {time_range}")

            with rosbag.Bag(output_bag, 'w') as outbag:
                # Convert time range to seconds
                start_sec = time_range[0][0] + time_range[0][1]/1e9
                end_sec = time_range[1][0] + time_range[1][1]/1e9
                
                for topic, msg, t in rosbag.Bag(input_bag).read_messages(topics=topics):
                    # Check if message is within time range
                    msg_time = t.to_sec()
                    if msg_time >= start_sec and msg_time <= end_sec:
                        outbag.write(topic, msg, t)

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
        with rosbag.Bag(bag_path) as bag:
            # Get topics and message types
            info = bag.get_type_and_topic_info()
            topics = list(info.topics.keys())
            connections = {topic: data.msg_type for topic, data in info.topics.items()}
            
            # Get time range
            start_time = bag.get_start_time()
            end_time = bag.get_end_time()
            
            # Convert to seconds and nanoseconds tuples
            start = (int(start_time), int((start_time % 1) * 1e9))
            end = (int(end_time), int((end_time % 1) * 1e9))
            
            return topics, connections, (start, end)
    
    @staticmethod
    def inspect_bag(bag_path: str) -> str:
        """
        List all topics and message types in the bag file
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Formatted string containing bag information
        """
        try:
            topics, connections, (start_time, end_time) = BagParser.load_bag(bag_path)
            
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