"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
"""

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Tuple, List, Dict, Optional
import rosbag
from roseApp.core.util import TimeUtil, get_logger
from time import sleep
_logger = get_logger(__name__)


class ParserType(Enum):
    """Enum for different parser implementations"""
    PYTHON = "python"
    CPP = "cpp"

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
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], time_range: Optional[Tuple] = None) -> str:
        """
        Filter rosbag using selected implementation
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Optional tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
        
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

class BagParser(IBagParser):
    """Python implementation of bag parser using rosbag"""
    
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
    
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], time_range: Optional[Tuple] = None) -> str:
        """
        Filter rosbag using rosbag Python API
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Optional tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
        
        Returns:
            Status message with completion time
        """
        try:
            start_time = time.time()
            sleep(2)
            with rosbag.Bag(output_bag, 'w') as outbag:
                # If time range is provided, convert it to seconds
                start_sec = None
                end_sec = None
                if time_range:
                    start_sec = time_range[0][0] + time_range[0][1]/1e9
                    end_sec = time_range[1][0] + time_range[1][1]/1e9
                
                for topic, msg, t in rosbag.Bag(input_bag).read_messages(topics=topics):
                    # Check if message is within time range (if specified)
                    msg_time = t.to_sec()
                    if time_range:
                        if msg_time >= start_sec and msg_time <= end_sec:
                            outbag.write(topic, msg, t)
                    else:
                        # If no time range specified, include all messages
                        outbag.write(topic, msg, t)

            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
            
        except Exception as e:
            _logger.error(f"Error filtering bag: {e}")
            raise Exception(f"Error filtering bag: {e}")

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
    elif parser_type == ParserType.CPP:     
        raise ValueError("C++ implementation not available. Please install rosbag_io_py first.")
    else:
        raise ValueError(f"Unknown parser type: {parser_type}")
