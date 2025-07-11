# Standard library imports
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple
import time

# Local application imports
from roseApp.core.parser import IBagParser, ParserType, create_parser, FileExistsError
from roseApp.core.util import TimeUtil, get_preferred_parser_type

class BagStatus(Enum):
    IDLE = "IDLE"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class CompressionType(Enum):
    """Available compression types for bag files"""
    NONE = "none"
    BZ2 = "bz2"
    LZ4 = "lz4"


@dataclass
class BagInfo:
    """Store basic information about a ROS bag"""
    time_range: Tuple[tuple, tuple]
    init_time_range: Tuple[tuple, tuple]
    size: int
    topics: Set[str]
    size_after_filter: int

    @property
    def time_range_str(self) -> Tuple[str, str]:
        """Return the start and end time as formatted strings"""
        return TimeUtil.to_datetime(self.time_range[0]), TimeUtil.to_datetime(self.time_range[1])
    
    @property
    def init_time_range_str(self) -> Tuple[str, str]:
        """Return the start and end time as formatted strings"""
        return TimeUtil.to_datetime(self.init_time_range[0]), TimeUtil.to_datetime(self.init_time_range[1])
    
    def _covert_size_to_str(self, size_bytes: int) -> str:
        try:
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.2f}{unit}"
                size_bytes /= 1024
            return f"{size_bytes:.2f}GB"
        except FileNotFoundError:
            return "0.00B"
    
    @property
    def size_str(self) -> str:
        """Get file size with appropriate unit (B, KB, MB, GB)"""
        return self._covert_size_to_str(self.size)
    
    @property
    def size_after_filter_str(self) -> str:
        """Get file size with appropriate unit (B, KB, MB, GB)"""
        return self._covert_size_to_str(self.size_after_filter)


@dataclass
class FilterConfig:
    """Store basic information about a ROS bag"""
    time_range: '[Tuple[tuple, tuple]]'
    topic_list: List[str] #dump API accept list
    compression: str = 'none'  # Compression type: 'none', 'bz2', 'lz4'

class Bag:
    """Represents a ROS bag file with its metadata"""
    def __init__(self, path: Path, bag_info: BagInfo):
        self.path = path
        self.info = bag_info
        self.selected_topics: Set[str] = set()
        self.status = BagStatus.IDLE
        self.output_file = Path(str(self.path.parent / f"{self.path.stem}_out{self.path.suffix}"))
        self.time_elapsed = 0
        
        
    def __repr__(self) -> str:
        return f"Bag(path={self.path}, info={self.info}, filter_config={self.get_filter_config()})"
    
    def set_selected_topics(self, topics: Set[str]) -> None:
        self.selected_topics = topics
    
    def get_filter_config(self, compression: str = 'none') -> FilterConfig:
        #fitler config is bag by bag becase time range can be different
        return FilterConfig(
            time_range=self.info.time_range,
            topic_list=list(self.selected_topics),
            compression=compression
        )
    def set_status(self, status: BagStatus) -> None:
        self.status = status

    def set_time_elapsed(self, time_elapsed: float) -> None:
        self.time_elapsed = time_elapsed
        
    def set_size_after_filter(self, size_after_filter: int) -> None:
        self.info.size_after_filter = size_after_filter
        
    def set_time_range(self, time_range: Tuple[tuple, tuple]) -> None:
        self.info.time_range = time_range
  
class BagManager:
    """Manages multiple ROS bag files"""
    def __init__(self, parser: IBagParser = None):
        """Initialize BagManager with optimal parser
        
        Args:
            parser: Optional parser instance. If None, will auto-select the best available parser
        """
        self.bags: Dict[str, Bag] = {}
        self.bag_mutate_callback = None
        self.selected_topics = set()
        
        # Auto-select best parser if none provided (always RosbagsBagParser)
        if parser is None:
                self._parser = create_parser(ParserType.ROSBAGS)
        else:
            self._parser = parser
            
        self._processed_count = 0  # 添加处理计数器
        self.compression = CompressionType.NONE.value  # Default: no compression

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
        
        topics, connections, time_range = self._parser.load_bag(str(path))
        bag = Bag(path, BagInfo(
            time_range=time_range,
            init_time_range=time_range,
            size=path.stat().st_size,
            topics=set(topics),
            size_after_filter=path.stat().st_size
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
        self.reset_processed_count()  # 清空时重置计数器
    
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
    
    def get_common_topics(self) -> Set[str]:
        """获取所有bag文件共有的topics
        
        Returns:
            Set[str]: 所有bag文件共有的topics
        """
        if not self.bags:
            return set()
        
        # 获取第一个bag的topics作为起始点
        common_topics = set(next(iter(self.bags.values())).info.topics)
        
        # 与其他bag的topics取交集
        for bag in list(self.bags.values())[1:]:
            common_topics = common_topics.intersection(bag.info.topics)
        
        return common_topics
    
    def get_topic_summary(self) -> 'dict[str, int]':
        """获取所有topics的统计信息
        
        Returns:
            dict[str, int]: topic名称到出现次数的映射
        """
        topic_counts = {}
        for bag in self.bags.values():
            for topic in bag.info.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        return topic_counts
    
    def get_selected_topics(self) -> Set[str]:
        return self.selected_topics
    
    @publish
    def set_output_file(self, bag_path: Path , output_file: str = None) -> None:
        if output_file is None:
            output_file = Path(str(bag_path.parent / f"{bag_path.stem}_out{bag_path.suffix}"))
        self.bags[bag_path].output_file = output_file
    
    @publish
    def set_time_range(self, bag_path: Path , time_range: Tuple[tuple, tuple]) -> None:
        self.bags[bag_path].set_time_range(time_range)
    
    @publish
    def set_status(self, bag_path: Path, status: BagStatus) -> None:
        self.bags[bag_path].set_status(status)
    
    @publish
    def set_time_elapsed(self, bag_path: Path, time_elapsed: float) -> None:
        self.bags[bag_path].set_time_elapsed(time_elapsed)
    
    @publish
    def set_size_after_filter(self, bag_path: Path, size_after_filter: int) -> None:
        self.bags[bag_path].set_size_after_filter(size_after_filter)
    
    def get_processed_count(self) -> int:
        """获取已处理的bag数量"""
        return self._processed_count
    
    def reset_processed_count(self) -> None:
        """重置已处理的bag数量"""
        self._processed_count = 0
    
    def set_compression_type(self, compression: str) -> None:
        """设置压缩类型
        
        Args:
            compression: 压缩类型 ('none', 'bz2', 'lz4')
        """
        from roseApp.core.util import validate_compression_type
        
        is_valid, error_message = validate_compression_type(compression)
        if not is_valid:
            raise ValueError(error_message)
        
        self.compression = compression
    
    def get_compression_type(self) -> str:
        """获取当前压缩类型
        
        Returns:
            str: 当前压缩类型
        """
        return self.compression
    
    @publish
    def filter_bag(self, bag_path: Path, config: FilterConfig, output_file: Path) -> None:
        """
        Process a single bag file with the given configuration
        
        Args:
            bag_path: Path to the input bag file
            config: Filter configuration
            output_file: Path to the output file
        """
        try:
            process_start = time.time()
            
            try:
                self._parser.filter_bag(
                    str(bag_path),
                    str(output_file),
                    config.topic_list,
                    config.time_range,
                    compression=config.compression
                )
            except FileExistsError:
                # For BagManager, always overwrite existing files
                self._parser.filter_bag(
                    str(bag_path),
                    str(output_file),
                    config.topic_list,
                    config.time_range,
                    compression=config.compression,
                    overwrite=True
                )
            
            process_end = time.time()
            time_elapsed = int((process_end - process_start) * 1000)
            
            self.set_time_elapsed(bag_path, time_elapsed)
            self.set_size_after_filter(bag_path, output_file.stat().st_size)
            self.set_status(bag_path, BagStatus.SUCCESS)
            
        except Exception as e:
            self.set_status(bag_path, BagStatus.ERROR)
            raise Exception(f"Error processing bag {bag_path}: {str(e)}")
    
    def get_parser_type(self) -> str:
        """获取当前使用的parser类型
        
        Returns:
            str: parser类型名称 (always 'rosbags')
        """
        parser_class = self._parser.__class__.__name__
        if parser_class == 'RosbagsBagParser':
            return 'rosbags'
        else:
            return 'unknown'
