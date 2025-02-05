from typing import Dict, Set, Optional, Tuple,Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from core.util import Operation

@dataclass
class BagInfo:
    """Store basic information about a ROS bag"""
    start_time: datetime
    end_time: datetime
    size: int
    topics: Set[str]

@dataclass
class FilterConfig:
    """Store basic information about a ROS bag"""
    time_range: '[Tuple[tuple, tuple]]'
    topics: Set[str]

class Bag:
    """Represents a ROS bag file with its metadata"""
    def __init__(self, path: Path, bag_info: BagInfo):
        self.path = path
        self.info = bag_info
        self.selected_topics: Set[str] = set()
        self.filter_time_range = None
        
    def __repr__(self) -> str:
        return f"Bag(path={self.path}, info={self.info}, filter_config={self.get_filter_config()})"
    
    def select_topic(self, topic: str) -> None:
        if not self.info or topic not in self.info.topics:
            raise ValueError(f"Topic {topic} not found in bag")
        self.selected_topics.add(topic)
    
    def deselect_topic(self, topic: str) -> None:
        self.selected_topics.discard(topic)

    def set_filter_time_range(self, start_time, end_time) -> None:
        self.filter_time_range = (start_time, end_time)
        
    def get_filter_config(self) -> FilterConfig:
        return FilterConfig(
            time_range=self.filter_time_range,
            topics=self.selected_topics
        )
    def get_bag_info(self) -> BagInfo:
        return self.info
    
    
        
  
class BagManager:
    """Manages multiple ROS bag files"""
    def __init__(self):
        self.bags: Dict[str, Bag] = {}
    
    def __repr__(self) -> str:
        return f"BagManager(bags={self.bags}) Size = {self.get_bag_numbers()}"
    
    def get_bag_numbers(self):
      return len(self.bags)
    
    def load_bag(self,path:Path,mutate_callback:Callable) -> None:
        if path in self.bags:
            raise ValueError(f"Bag with path {path} already exists")
        
        topics, connections, (start_time, end_time) = Operation.load_bag(str(path))
        bag = Bag(path, BagInfo(
            start_time=start_time,
            end_time=end_time,
            size=0,
            topics=set(topics)
        ))
        self.bags[path] = bag
        
    def unload_bag(self, path: Path,mutate_callback:Callable) -> None:
        if path not in self.bags:
            raise KeyError(f"Bag with path {path} not found")
        del self.bags[path]
        
    def clear_bags(self) -> None:
        self.bags.clear()

    def get_topic_summary(self) -> 'dict[str, int]':
        """
        Get the number of bags each topic appears in
        
        Returns:
            dict[str, int]: A dictionary where keys are topics and values are the number of bags they appear in
        """
        topic_summary = {}
        for bag in self.bags.values():
            for topic in bag.info.topics:
                if topic in topic_summary:
                    topic_summary[topic] += 1
                else:
                    topic_summary[topic] = 1
        return topic_summary
    
    def selected_topic(self, topic: str) -> None:
        for bag in self.bags.values():
            bag.selected_topics.add(topic)
    def deselected_topic(self, topic: str) -> None:
        for bag in self.bags.values():
            bag.selected_topics.discard(topic)
