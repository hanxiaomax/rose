import rosbag_io_py
import time
import logging
from pathlib import Path
from textual.logging import TextualHandler


class Operation():

    @staticmethod
    def load_whitelist(whitelist_path):
        """Load topics from whitelist file"""
        with open(whitelist_path) as f:
            topics = []
            for line in f.readlines():
                if line.strip() and not line.strip().startswith('#'):
                    topics.append(line.strip())
            return topics
        
    @staticmethod
    def filter_bag(input_bag, output_bag, whitelist, time_range):
        """Filter rosbag using C++ interface"""
        try:
            start_time = time.time()
            
            io = rosbag_io_py.rosbag_io()
            ## TODO: support load with whitelist and time range
            io.load(input_bag)
            io.dump(output_bag, whitelist,time_range)
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
        except Exception as e:
            print(e)
            raise Exception(f"Error filtering bag: {e}")

    @staticmethod
    def load_bag(bag_path):
        io = rosbag_io_py.rosbag_io()
        # TODO: support load with whitelist and time range
        # in case whitelist or time range is set before loading bag
        # it betters to load bag partially. dose it make sense?
        io.load(bag_path)
        topics = io.get_topics()
        connections = io.get_connections()
        timerange = io.get_time_range()

        return topics,connections,timerange
    
    @staticmethod
    def inspect_bag(bag_path):
        """List all topics and message types using C++ interface"""
        try:
            topics,connections,(start_time,end_time) = Operation.load_bag(bag_path)
            
            result = [f"\nTopics in {bag_path}:"]
            result.append("{:<40} {:<30}".format("Topic", "Message Type"))
            result.append("-" * 80)
            for topic in topics:
                result.append("{:<40} {:<30}".format(topic, connections[topic]))
            
            result.append(f"\nTime range: {start_time} - {end_time}")
            return "\n".join(result)
        except Exception as e:
            raise Exception(f"Error inspecting bag file: {e}")

    @staticmethod
    def to_datetime(time_tuple):
        """Convert (seconds, nanoseconds) tuple to [YY/MM/DD HH:MM:SS] formatted string"""
        if not time_tuple or len(time_tuple) != 2:
            return "N.A"
        
        seconds, nanoseconds = time_tuple
        total_seconds = seconds + nanoseconds / 1e9
        return time.strftime("%y/%m/%d %H:%M:%S", time.localtime(total_seconds))

    @staticmethod
    def from_datetime(time_str):
        """Convert [YY/MM/DD HH:MM:SS] formatted string to (seconds, nanoseconds) tuple"""
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
    def convert_time_range_to_tuple(start_time_str: str, end_time_str:str):
        """Create time range from start and end time strings to tuple"""
        try:
            start_time = Operation.from_datetime(start_time_str)
            end_time = Operation.from_datetime(end_time_str)
            # make sure start and end are within range of output bag file
            start_time = (start_time[0] - 1, start_time[1])
            end_time = (end_time[0] + 1, end_time[1]) 
            return (start_time, end_time)
        except ValueError as e:
            raise ValueError(f"Invalid time range format: {e}")
        
    @staticmethod
    def convert_time_range_to_str(start_time: tuple, end_time: tuple):
        """Convert time range to string"""
        start_str = Operation.to_datetime(start_time)
        end_str = Operation.to_datetime(end_time)
        return start_str, end_str

def setup_logging():
    """Configure logging settings for the application"""
    log_file = Path("rose_tui.log")
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Textual handler
    textual_handler = TextualHandler()
    textual_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(textual_handler)
    
    return root_logger