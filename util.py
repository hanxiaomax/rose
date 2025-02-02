import rosbag_io_py
import time

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
    def filter_bag(input_bag, output_bag, whitelist):
        """Filter rosbag using C++ interface"""
        try:
            start_time = time.time()
            
            io = rosbag_io_py.rosbag_io()
            io.load(input_bag, whitelist)
            io.dump(output_bag, whitelist)
            
            end_time = time.time()
            elapsed = end_time - start_time
            mins, secs = divmod(elapsed, 60)
            return f"Filtering completed in {int(mins)}m {secs:.2f}s"
        except Exception as e:
            raise Exception(f"Error filtering bag: {e}")

    @staticmethod
    def load_bag(bag_path):
        io = rosbag_io_py.rosbag_io()
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
            
            # start_time, end_time = io.get_time_range()
            result.append(f"\nTime range: {start_time} - {end_time}")
            return "\n".join(result)
        except Exception as e:
            raise Exception(f"Error inspecting bag file: {e}")