from typing import Dict, Set, Optional, Tuple,Callable,List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from core.util import Operation
from enum import Enum

class BagStatus(Enum):
    IDLE = "IDLE"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class BagInfo:
    """Store basic information about a ROS bag"""
    time_range: Tuple[tuple, tuple]
    size: int
    topics: Set[str]

    @property
    def time_range_str(self) -> Tuple[str, str]:
        """Return the start and end time as formatted strings"""
        return Operation.to_datetime(self.time_range[0]), Operation.to_datetime(self.time_range[1])
    
    @property
    def size_str(self) -> str:
        """Get file size with appropriate unit (B, KB, MB, GB)"""
        try:
            size_bytes = self.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.2f}{unit}"
                size_bytes /= 1024
            return f"{size_bytes:.2f}GB"
        except FileNotFoundError:
            return "0.00B"

@dataclass
class FilterConfig:
    """Store basic information about a ROS bag"""
    time_range: '[Tuple[tuple, tuple]]'
    topic_list: List[str] #dump API accept list

class Bag:
    """Represents a ROS bag file with its metadata"""
    def __init__(self, path: Path, bag_info: BagInfo):
        self.path = path
        self.info = bag_info
        self.selected_topics: Set[str] = set()
        self.filter_time_range = self.info.time_range
        self.status = BagStatus.IDLE
        self.output_file = Path(str(self.path.parent / f"{self.path.stem}_filtered{self.path.suffix}"))
        
    def __repr__(self) -> str:
        return f"Bag(path={self.path}, info={self.info}, filter_config={self.get_filter_config()})"
    
    #TODO: handle time slice
    def set_filter_time_range(self, time_range: Tuple[tuple, tuple]) -> None:
        self.filter_time_range = time_range
    
    def set_selected_topics(self, topics: Set[str]) -> None:
        self.selected_topics = topics
    
    def get_filter_config(self) -> FilterConfig:
        #fitler config is bag by bag becase time range can be different
        return FilterConfig(
            time_range=self.filter_time_range,
            topic_list=list(self.selected_topics)
        )
    def set_status(self, status: BagStatus) -> None:
        self.status = status
        
  
class BagManager:
    """Manages multiple ROS bag files"""
    def __init__(self):
        self.bags: Dict[str, Bag] = {}
        self.bag_mutate_callback = None
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
    
    def publish(func):
        """Decorator to call bag_mutate_callback after function execution"""
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            if self.bag_mutate_callback:
                self.bag_mutate_callback()
            return result
        return wrapper

    @publish
    def load_bag(self, path: Path) -> None:
        if path in self.bags:
            raise ValueError(f"Bag with path {path} already exists")
        
        topics, connections, time_range = Operation.load_bag(str(path))
        bag = Bag(path, BagInfo(
            time_range=time_range,
            size=path.stat().st_size,
            topics=set(topics)
        ))
        self.bags[path] = bag
        self.selected_topics.clear()

    @publish
    def unload_bag(self, path: Path) -> None:
        if path not in self.bags:
            raise KeyError(f"Bag with path {path} not found")
        del self.bags[path]
        self.selected_topics.clear()

    @publish
    def clear_bags(self) -> None:
        self.bags.clear()
        self.selected_topics.clear()
    
    @publish
    def select_topic(self, topic: str) -> None:
        self.selected_topics.add(topic)
        self.populate_selected_topics()

    @publish
    def deselect_topic(self, topic: str) -> None:
        self.selected_topics.discard(topic)
        self.populate_selected_topics()
    
    @publish
    def clear_selected_topics(self) -> None:
        self.selected_topics.clear()
        self.populate_selected_topics()
    
    def get_topic_summary(self) -> 'dict[str, int]':
        topic_summary = {}
        for bag in self.bags.values():
            for topic in bag.info.topics:
                if topic in topic_summary:
                    topic_summary[topic] += 1
                else:
                    topic_summary[topic] = 1
        return topic_summary
    
    def get_selected_topics(self) -> Set[str]:
        return self.selected_topics

    @publish
    def set_output_file(self, bag_path: Path , output_file: str = None) -> None:
        """Set output file name for specific bag or all bags"""
        self.bags[bag_path].output_file = Path(str(bag_path.parent / f"{output_file}"))

    @publish
    def set_time_range(self, bag_path: Path , time_range: Tuple[tuple, tuple]) -> None:
        """Set time range for specific bag or all bags"""
        self.bags[bag_path].set_filter_time_range(time_range)
        
