"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
"""

import time
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Tuple, List, Dict
import rosbag
from core.util import TimeUtil

# Try to import C++ implementation
try:
    import rosbag_io_py
    _HAS_CPP_IMPL = True
    _logger = logging.getLogger(__name__)
    _logger.info("Successfully loaded C++ implementation (rosbag_io_py)")
except ImportError:
    _HAS_CPP_IMPL = False
    _logger = logging.getLogger(__name__)
    _logger.warning("C++ implementation (rosbag_io_py) not available. Only Python implementation will be used.")

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
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], time_range: Tuple) -> str:
        """
        Filter rosbag using selected implementation
        
        Args:
            input_bag: Path to input bag file
            output_bag: Path to output bag file  
            topics: List of topics to include
            time_range: Tuple of (start_time, end_time)
        
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

class BagParser(IBagParser):
    """Python implementation of bag parser using rosbag"""
    
    def load_whitelist(self, whitelist_path: str) -> List[str]:
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
    
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], time_range: Tuple) -> str:
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

class BagParserCPP(IBagParser):
    """C++ implementation of bag parser using rosbag_io_py"""
    
    def load_whitelist(self, whitelist_path: str) -> List[str]:
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
    
    def filter_bag(self, input_bag: str, output_bag: str, topics: List[str], time_range: Tuple) -> str:
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

            io.load(str(input_bag))
            io.dump(str(output_bag), topics, time_range)
            
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
        io = rosbag_io_py.rosbag_io()
        io.load(bag_path)
        topics = io.get_topics()
        connections = io.get_connections()
        timerange = io.get_time_range()
        
        return topics, connections, timerange
    
    def inspect_bag(self, bag_path: str) -> str:
        """
        List all topics and message types using C++ interface
        
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
        if not _HAS_CPP_IMPL:
            raise ValueError("C++ implementation not available. Please install rosbag_io_py first.")
        return BagParserCPP()
    else:
        raise ValueError(f"Unknown parser type: {parser_type}")
