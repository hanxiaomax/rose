class BagManager:
    """Manages multiple ROS bag files"""
    def __init__(self, parser: IBagParser):
        """
        Initialize BagManager with a parser implementation
        
        Args:
            parser: Implementation of IBagParser to use
        """
        self.bags: Dict[str, Bag] = {}
        self.bag_mutate_callback = None
        self.selected_topics = set()
        self._parser = parser

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
            
            self._parser.filter_bag(
                str(bag_path),
                str(output_file),
                config.topic_list,
                config.time_range
            )
            
            process_end = time.time()
            time_elapsed = int((process_end - process_start) * 1000)
            
            self.set_time_elapsed(bag_path, time_elapsed)
            self.set_size_after_filter(bag_path, output_file.stat().st_size)
            self.set_status(bag_path, BagStatus.SUCCESS)
            
        except Exception as e:
            self.set_status(bag_path, BagStatus.ERROR)
            raise Exception(f"Error processing bag {bag_path}: {str(e)}")

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