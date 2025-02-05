from pathlib import Path
from typing import Iterable
from rich.text import Text
from textual import work
from textual.widgets import (
    Button, DataTable, DirectoryTree, Footer, Header, Input, Label,
    Placeholder, Static, Switch, Tree, Rule, Link, SelectionList, TextArea, RichLog
)
from textual.reactive import reactive
from core.BagManager import BagManager
from core.util import Operation, setup_logging
from components.StatusBar import StatusBar

logger = setup_logging()

class BagSelector(DirectoryTree):
    """A directory tree widget specialized for selecting ROS bag files"""
    bags = reactive(BagManager())
    multi_select_mode = reactive(False)
    
    BINDINGS = [
        ("f", "toggle_bags_only", "Filter Bags"),
        ("m", "toggle_multi_select", "Multi Mode"),
    ]
    
    def __init__(self, init_path: str = "."):
        super().__init__(path=init_path)
        self.current_path = Path(init_path)
        self.guide_depth = 2
        self.show_root = True  
        self.show_guides = True
        self.show_only_bags = False

        # self.selected_bags = set()
        self.border_title = "File Explorer"
        self.logger = logger.getChild("BagSelector")
    
    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.update_border_subtitle()

    def mutate_callback(self):
        self.mutate_reactive(BagSelector.bags)
    
    def update_border_subtitle(self):
        """Update subtitle to show multi-select mode status"""
        #mode = "Multi-Select Mode" if self.multi_select_mode else ""
        self.border_subtitle = f" ({self.bags.get_bag_numbers()} selected)" if self.multi_select_mode else ""

    def action_toggle_bags_only(self) -> None:
        self.show_only_bags = not self.show_only_bags
        self.reload()
    
    def action_toggle_multi_select(self) -> None:
        self.multi_select_mode = not self.multi_select_mode
        self.show_only_bags = self.multi_select_mode
        self.reload()   
        self.update_border_subtitle()

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

    # def _update_ui_for_selected_bag(self, path: Path, topics: list, time_range: tuple) -> None:
    #     """Update UI components after selecting a bag file"""
    #     #TODO remove
    #     # topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
    #     # topic_tree.set_topics(topics)
        
        
    #     # main_screen = self.app.query_one(MainScreen)
    #     # main_screen.apply_whitelist(topics)

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
            status.update_status(f"File: {path} is not a bag file", "warning")
            return

        if self.multi_select_mode:
            self._handle_multi_select_bag(path, event, status)
        else:
            self._handle_single_select_bag(path, status)
