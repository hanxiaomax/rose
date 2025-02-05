from pathlib import Path
from collections import defaultdict
from typing import Optional, Iterable
from textual import work

from rich.text import Text
from textual.widgets import Tree
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import (
    Button, DataTable, DirectoryTree, Footer, Header, Input, Label,
    Placeholder, Static, Switch, Tree, Rule, Link, SelectionList, TextArea, RichLog
)
from textual.fuzzy import FuzzySearch
from core.BagManager import BagManager
from core.util import Operation, setup_logging
from components.StatusBar import StatusBar

logger = setup_logging()

class TopicManager:
    """Manager for handling topic-bag relationships and counts"""
    
    def __init__(self):
        # 存储每个topic对应的bag set
        self.topic_bags: dict[str, 'set[str]'] = defaultdict(set)
        # 存储每个bag对应的topics list，用于快速查找bag包含的所有topics
        self.bag_topics: dict[str, 'list[str]'] = {}
        
    def add_bag(self, bag_path: str, topics: 'list[str]') -> None:
        # 记录bag包含的topics
        self.bag_topics[bag_path] = topics
        # 为每个topic添加这个bag
        for topic in topics:
            self.topic_bags[topic].add(bag_path)
    
    def remove_bag(self, bag_path: str) -> 'tuple[list[str], list[str]]':
        if bag_path not in self.bag_topics:
            return [], []
            
        removed_topics = []
        updated_topics = []
        

        topics = self.bag_topics[bag_path]

        for topic in topics:
            self.topic_bags[topic].remove(bag_path)
            if not self.topic_bags[topic]:
                removed_topics.append(topic)
                del self.topic_bags[topic]
            else:
                updated_topics.append(topic)

        del self.bag_topics[bag_path]
        
        return removed_topics, updated_topics
    
    def get_topic_count(self, topic: str) -> int:
        """Get the number of bags containing a topic"""
        return len(self.topic_bags.get(topic, set()))
    
    def get_topics(self) -> 'list[str]':
        """Get all current topics"""
        return list(self.topic_bags.keys())

class TopicTree(Tree):
    """A tree widget for displaying ROS bag topics with multi-selection capability"""
    
    def __init__(self, topic_manager: TopicManager):
        super().__init__("Topics")
        self.selected_topics = set() # selected topics used for filtering
        self.topic_manager = topic_manager  # manager for topic-bag relationships
        self.all_topics = []  # Store all topics for filtering
        self.border_subtitle = "Selected: 0"
        self.fuzzy_searcher = FuzzySearch(case_sensitive=False)
        self.multi_select_mode = False
        self.show_root = False

    def on_mount(self) -> None:
        """Initialize when mounted"""
        super().on_mount()
        self.root.expand()
        self.watch(self.app.query_one(BagSelector), "bags", self.handle_bags_change)

    def handle_bags_change(self, bags: BagManager) -> None:
        print(f"++ bags: {bags}")
    
    def get_node_label(self, topic: str, selected: bool = False) -> Text:
        """
        Get the label for a topic node based on mode and selection state.
        
        Args:
            topic: The topic name
            selected: Whether the topic is selected
        """
        if self.multi_select_mode:
            count = self.topic_manager.get_topic_count(topic)
            label = f"{topic} [{count}]"
        else:
            label = topic
            
        if selected:
            return Text("√ ") + Text(label)
        return Text(label)

    def filter_topics(self, search_text: str) -> None:
        """Filter topics based on search text using fuzzy search."""
        self.root.remove_children()
        
        if not search_text:
            filtered_topics = self.all_topics
        else:
            scored_topics = [
                (topic, self.fuzzy_searcher.match(search_text, topic)[0])
                for topic in self.all_topics
            ]
            filtered_topics = [
                topic for topic, score in sorted(
                    scored_topics,
                    key=lambda x: x[1],
                    reverse=True
                ) if score > 0
            ]
        
        for topic in filtered_topics:
            self.root.add(
                self.get_node_label(topic, topic in self.selected_topics),
                data={"topic": topic, "selected": topic in self.selected_topics},
                allow_expand=False
            )

    def set_topics(self, topics: list) -> None:
        """Set topics and clear previous selections"""
        self.all_topics = topics
        self.selected_topics.clear()
        self.root.remove_children()
        
        for topic in sorted(topics):
            self.root.add(
                self.get_node_label(topic),
                data={"topic": topic, "selected": False},
                allow_expand=False
            )
        
        self.update_border_subtitle()
        self.update_border_title()

    def update_border_subtitle(self):
        """Update subtitle with selected topics count"""
        self.border_subtitle = f"Topic selected: {len(self.selected_topics)}"
    
    def update_border_title(self):
        """Update title with whitelist info if available"""
        if self.app.selected_whitelist_path:
            self.border_title = f"Topics (Whitelist: {Path(self.app.selected_whitelist_path).stem})"
        else:
            self.border_title = "Topics"

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle topic selection toggle"""
        if event.node.allow_expand:
            return
            
        data = event.node.data
        if data:
            data["selected"] = not data["selected"]
            topic = data["topic"]
            
            if data["selected"]:
                self.selected_topics.add(topic)
            else:
                self.selected_topics.discard(topic)
                
            event.node.label = self.get_node_label(topic, data["selected"])
            self.update_border_subtitle()

    def get_selected_topics(self) -> list:
        """Return list of selected topics"""
        return list(self.selected_topics)

    def merge_topics(self, bag_path: str, new_topics: list) -> None:
        """Add topics from a bag"""
        self.topic_manager.add_bag(bag_path, new_topics)
        
        for topic in new_topics:
            if topic not in [node.data.get("topic") for node in self.root.children]:
                self.root.add(
                    self.get_node_label(topic),
                    data={"topic": topic, "selected": False},
                    allow_expand=False
                )
            else:
                for node in self.root.children:
                    if node.data.get("topic") == topic:
                        node.label = self.get_node_label(
                            topic, 
                            node.data.get("selected", False)
                        )
                        break

        self.update_border_subtitle()

    def remove_bag_topics(self, bag_path: str) -> None:
        """Remove topics from a bag"""
        removed_topics, updated_topics = self.topic_manager.remove_bag(bag_path)
        
        for topic in removed_topics:
            self.selected_topics.discard(topic)
            for node in list(self.root.children): 
                if node.data.get("topic") == topic:
                    node.remove()  
                    break
        

        for topic in updated_topics:
            for node in self.root.children:
                if node.data.get("topic") == topic:
                    node.label = self.get_node_label(
                        topic,
                        node.data.get("selected", False)
                    )
                    break
        
        self.update_border_subtitle()

    def toggle_select_all(self) -> 'tuple[bool, int]':
        """
        Toggle selection state of all topics.
        
        Returns:
            tuple[bool, int]: (is_all_deselected, count_of_selected)
        """
        if not self.root.children:
            return False, 0
            
        # Check if all topics are already selected
        all_selected = all(node.data["selected"] for node in self.root.children)
        
        # Toggle selection state
        for node in self.root.children:
            node.data["selected"] = not all_selected
            topic = node.data.get("topic")
            if node.data["selected"]:
                self.selected_topics.add(topic)
                node.label = self.get_node_label(topic, True)
            else:
                self.selected_topics.discard(topic)
                node.label = self.get_node_label(topic, False)
        
        self.update_border_subtitle()
        return all_selected, len(self.selected_topics)

class TopicSearchInput(Input):
    """Input widget for searching topics"""
    
    def __init__(self):
        super().__init__(placeholder="Search topics...", id="topic-search")
        self._topic_tree = None

    def on_mount(self) -> None:
        """Get reference to topic tree when mounted"""
        self._topic_tree = self.parent.query_one(TopicTree)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        if self._topic_tree:
            self._topic_tree.filter_topics(event.value)

class TopicTreePanel(Container):
    """A wrapper component that contains a search input and a topic tree"""
    
    def __init__(self):
        super().__init__()
        self._topic_manager = TopicManager()

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield TopicSearchInput()
        yield TopicTree(self._topic_manager)

    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.border_title = "Topics"

    def get_topic_tree(self) -> TopicTree:
        """Get the topic tree"""
        return self.query_one(TopicTree)
    

class BagSelector(DirectoryTree):
    """A directory tree widget specialized for selecting ROS bag files"""
    bags = reactive(BagManager())
    multi_select_mode = reactive(False)
    
    def __init__(self, init_path: str = "."):
        super().__init__(path=init_path)
        self.current_path = Path(init_path)
        self.guide_depth = 2
        self.show_root = True  
        self.show_guides = True
        self.show_only_bags = False

        self.selected_bags = set()
        self.border_title = "File Explorer"
        self.logger = logger.getChild("BagSelector")
    
    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.update_border_subtitle()

    def mutate_callback(self):
        self.mutate_reactive(BagSelector.bags)
    
    def update_border_subtitle(self):
        """Update subtitle to show multi-select mode status"""
        mode = "Multi-Select Mode" if self.multi_select_mode else ""
        count = f" ({len(self.selected_bags)} selected)" if self.multi_select_mode else ""
        self.border_subtitle = f"{mode}{count}"

    def toggle_multi_select_mode(self):
        """Toggle multi-select mode on/off."""
        self.multi_select_mode = not self.multi_select_mode
        self.selected_bags.clear()
        self.show_only_bags = self.multi_select_mode
        self.reload()   
        self.update_border_subtitle()
        self._update_topic_tree_mode()
    
    
    def _update_topic_tree_mode(self):
        """Update topic tree mode based on multi-select mode"""
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        topic_tree.multi_select_mode = self.multi_select_mode
        topic_tree.filter_topics("")

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths based on show_only_bags setting"""
        paths = super().filter_paths(paths)
        paths = [p for p in paths if not p.name.startswith('.')]
        if self.show_only_bags:
            return [p for p in paths if p.is_dir() or p.suffix.lower() == '.bag']
        return paths


    def _handle_directory_selection(self, path: Path, status) -> None:
        """Handle directory selection logic"""
        if path == self.current_path:
            self.path = self.current_path.parent
        else:
            self.path = path
        self.current_path = self.path
        status.update_status(f"Entering directory: {path}")

    def _handle_non_bag_file(self, path: Path, status) -> None:
        """Handle selection of non-bag files"""
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        topic_tree.set_topics([])
        self.app.selected_bag = None
        status.update_status(f"File: {path} is not a bag file", "warning")

    def _handle_multi_select_bag(self, path: Path, event, status) -> None:
        """Handle bag file selection in multi-select mode"""
        try:
            if self.bags.is_bag_loaded(path):
                self.bags.unload_bag(path,self.mutate_callback)
                event.node.label = Text(path.name)  
                status.update_status(f"Deselected: {path}")
            else:
                self.bags.load_bag(path,self.mutate_callback)
                event.node.label = Text("☑️ ") + Text(path.name)  # Add checkbox symbol
                status.update_status(f"Selected: {path}")   
            self.update_border_subtitle()
        except Exception as e:
            self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
            status.update_status(f"Error loading bag file: {str(e)}", "error")
            
    # def _select_bag(self, path: Path, event, status) -> None:
    #     """Handle bag file selection"""
    #     self.selected_bags.add(str(path))
    #     event.node.label = Text("☑️ ") + Text(path.name)  # Add checkbox symbol
    #     status.update_status(f"Selected: {path}")
        
    #     try:
    #         topics, _, _ = Operation.load_bag(str(path))
    #         topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
    #         topic_tree.merge_topics(str(path), topics)
    #     except Exception as e:
    #         self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
    #         status.update_status(f"Error loading bag file: {str(e)}", "error")

    # def _deselect_bag(self, path: Path, event, status) -> None:
    #     """Handle bag file deselection"""
    #     try:
    #         self.selected_bags.remove(str(path))
            
    #         topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
    #         topic_tree.remove_bag_topics(str(path))
            
            
    #     except Exception as e:
    #         self.logger.error(f"Error deselecting bag file: {str(e)}", exc_info=True)
    #         status.update_status(f"Error deselecting bag file: {str(e)}", "error")

    def _handle_single_select_bag(self, path: Path, status) -> None:
        """Handle bag file selection in single-select mode"""
        # for single select mode, clear bags before load current bag
        try:
            self.bags.clear_bags()
            self.bags.load_bag(path,self.mutate_callback)
            status.update_status(f"File: {path} loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
            status.update_status(f"Error loading bag file: {str(e)}", "error")

    def _update_ui_for_selected_bag(self, path: Path, topics: list, time_range: tuple) -> None:
        """Update UI components after selecting a bag file"""
        #TODO remove
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        topic_tree.set_topics(topics)
        
        
        # main_screen = self.app.query_one(MainScreen)
        # main_screen.apply_whitelist(topics)

    @work(thread=True)
    async def on_tree_node_selected(self, event: DirectoryTree.NodeSelected) -> None:
        """Handle file selection with support for multi-select mode"""
        path = event.node.data.path
        self.current_node = event.node
        self.show_guides = True
        status = self.app.query_one(StatusBar)

        if path.is_dir():
            self._handle_directory_selection(path, status)
            return

        if not str(path).endswith('.bag'):
            self._handle_non_bag_file(path, status)
            return

        if self.multi_select_mode:
            self._handle_multi_select_bag(path, event, status)
        else:
            self._handle_single_select_bag(path, status)
