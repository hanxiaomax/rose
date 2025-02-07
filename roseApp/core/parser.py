"""
ROS bag parser module that provides functionality for reading and filtering ROS bag files.
"""

import time
import logging
from enum import Enum
from typing import Tuple, List, Dict
import rosbag
import rosbag_io_py
_logger = logging.getLogger(__name__)

class ParserType(Enum):
    """Enum for different parser implementations"""
    PYTHON = "python"
    CPP = "cpp"

class IBagParser:
    """Interface for bag parser implementations"""
    
    _instance = None
    _parser_impl = None
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(IBagParser, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'IBagParser':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def set_implementation(cls, parser_type: ParserType):
        """
        Set the parser implementation to use
        
        Args:
            parser_type: Type of parser to use (PYTHON or CPP)
        """
        if parser_type == ParserType.PYTHON:
            cls._parser_impl = BagParser
        elif parser_type == ParserType.CPP:
            cls._parser_impl = BagParserCPP
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
        
        _logger.info(f"Using {parser_type.value} implementation for bag parsing")
    
    @classmethod
    def load_whitelist(cls, whitelist_path: str) -> List[str]:
        """
        Load topics from whitelist file
        
        Args:
            whitelist_path: Path to the whitelist file
            
        Returns:
            List of topic names
        """
        if cls._parser_impl is None:
            cls.set_implementation(ParserType.CPP)  # Default to C++ implementation
        return cls._parser_impl.load_whitelist(whitelist_path)
    
    @classmethod
    def filter_bag(cls, input_bag: str, output_bag: str, topics: List[str], time_range: Tuple) -> str:
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
        if cls._parser_impl is None:
            cls.set_implementation(ParserType.CPP)
        return cls._parser_impl.filter_bag(input_bag, output_bag, topics, time_range)
    
    @classmethod
    def load_bag(cls, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
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
        if cls._parser_impl is None:
            cls.set_implementation(ParserType.CPP)
        return cls._parser_impl.load_bag(bag_path)
    
    @classmethod
    def inspect_bag(cls, bag_path: str) -> str:
        """
        List all topics and message types using selected implementation
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            Formatted string containing bag information
        """
        if cls._parser_impl is None:
            cls.set_implementation(ParserType.CPP)
        return cls._parser_impl.inspect_bag(bag_path)

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
