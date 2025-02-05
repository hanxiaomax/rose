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

    @property
    def time_range_str(self) -> Tuple[str, str]:
        """Return the start and end time as formatted strings"""
        return Operation.to_datetime(self.start_time), Operation.to_datetime(self.end_time)

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
    
    
    def set_filter_time_range(self, start_time, end_time) -> None:
        self.filter_time_range = (start_time, end_time)
    
    def set_selected_topics(self, topics: Set[str]) -> None:
        self.selected_topics = topics
    
    def get_filter_config(self) -> FilterConfig:
        #fitler config is bag by bag becase time range can be different
        return FilterConfig(
            time_range=self.filter_time_range,
            topics=self.selected_topics
        )
        
  
class BagManager:
    """Manages multiple ROS bag files"""
    def __init__(self):
        self.bags: Dict[str, Bag] = {}
        self.bag_mutate_callback = None #call it when bag mutate
        # for now, maintain selected topics in bag manager
        # because bags have same selected topics
        self.selected_topics = set()

    def __repr__(self) -> str:
        return f"BagManager(bags={self.bags}) \n" \
               f"Size = {self.get_bag_numbers()} \n" \
               f"Selected topics = {self.selected_topics}"

    def set_bag_mutate_callback(self, bag_mutate_callback: Callable) -> None:
        self.bag_mutate_callback = bag_mutate_callback

    def populate_selected_topics(self) -> None:
        for bag in self.bags.values():
            bag.set_selected_topics(self.selected_topics)
    
    def get_bag_numbers(self):
      return len(self.bags)
    
    def get_single_bag(self) -> Optional[Bag]:
        if self.get_bag_numbers() == 1:
            return next(iter(self.bags.values()))
        else:
            return None
    
    def is_bag_loaded(self, path: Path) -> bool:
        return path in self.bags
    
    def load_bag(self,path:Path) -> None:
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
        self.selected_topics.clear()
        self.bag_mutate_callback()
        
    def unload_bag(self, path: Path) -> None:
        if path not in self.bags:
            raise KeyError(f"Bag with path {path} not found")
        del self.bags[path]
        self.selected_topics.clear()
        self.bag_mutate_callback()
        
    def clear_bags(self) -> None:
        self.bags.clear()
        self.selected_topics.clear()
        self.bag_mutate_callback()

    def get_topic_summary(self) -> 'dict[str, int]':
        topic_summary = {}
        for bag in self.bags.values():
            for topic in bag.info.topics:
                if topic in topic_summary:
                    topic_summary[topic] += 1
                else:
                    topic_summary[topic] = 1
        return topic_summary
    
    def select_topic(self, topic: str) -> None:
        self.selected_topics.add(topic)
        self.populate_selected_topics()
        self.bag_mutate_callback()

        
        
    def deselect_topic(self, topic: str) -> None:
        self.selected_topics.discard(topic)
        self.populate_selected_topics()
        self.bag_mutate_callback()
    
    def clear_selected_topics(self) -> None:
        self.selected_topics.clear()
        self.populate_selected_topics()
        self.bag_mutate_callback()
    
    def get_selected_topics(self) -> Set[str]:
        return self.selected_topics


class Whitelist:
    """Represents a whitelist of topics"""
    def __init__(self, path: Path):
        self.path = path
        self.topics = set()
        
        