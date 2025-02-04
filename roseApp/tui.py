#!/usr/bin/env python3

# Standard library imports
import json
import logging
import time
from pathlib import Path
from typing import Iterable
from collections import defaultdict

# Third-party imports
from art import text2art
from rich.style import Style
from rich.text import Text
from textual import work, log
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, Vertical
from textual.logging import TextualHandler
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, DirectoryTree, Footer, Header, Input, Label,
    Placeholder, Static, Switch, Tree, Rule, Link, SelectionList, TextArea
)
from textual.widgets.directory_tree import DirEntry
from themes.cassette_theme import CASSETTE_THEME_DARK, CASSETTE_THEME_LIGHT
from util import Operation, setup_logging
from textual.fuzzy import FuzzySearch

# Initialize logging at the start of the file
logger = setup_logging()

def load_config():
    """Load configuration from config.json"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        logger.warning("config.json not found, using default configuration")
        return {"show_splash_screen": True}  # Default value
    except json.JSONDecodeError as e:
        logger.error("Error parsing config.json, using default configuration")
        logger.error(f"Error: {e}")
        return {"show_splash_screen": True}

class TopicManager:
    """Manager for handling topic-bag relationships and counts"""
    
    def __init__(self):
        # 存储每个topic对应的bag set
        self.topic_bags: dict[str, 'set[str]'] = defaultdict(set)
        # 存储每个bag对应的topics list，用于快速查找bag包含的所有topics
        self.bag_topics: dict[str, 'list[str]'] = {}
        
    def add_bag(self, bag_path: str, topics: 'list[str]') -> None:
        """
        Add a bag and its topics to the manager.
        
        Args:
            bag_path: Path to the bag file
            topics: List of topics in the bag
        """
        # 记录bag包含的topics
        self.bag_topics[bag_path] = topics
        # 为每个topic添加这个bag
        for topic in topics:
            self.topic_bags[topic].add(bag_path)
    
    def remove_bag(self, bag_path: str) -> 'tuple[list[str], list[str]]':
        """
        Remove a bag and update topic counts.
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            tuple[list[str], list[str]]: (removed_topics, updated_topics)
            - removed_topics: Topics that should be removed (count became 0)
            - updated_topics: Topics that still exist but count decreased
        """
        if bag_path not in self.bag_topics:
            return [], []
            
        removed_topics = []
        updated_topics = []
        
        # 获取这个bag包含的所有topics
        topics = self.bag_topics[bag_path]
        
        # 从每个topic的bags集合中移除这个bag
        for topic in topics:
            self.topic_bags[topic].remove(bag_path)
            # 如果topic不再被任何bag包含，则应该被删除
            if not self.topic_bags[topic]:
                removed_topics.append(topic)
                del self.topic_bags[topic]
            else:
                updated_topics.append(topic)
        
        # 删除bag的记录
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
    
    def __init__(self):
        super().__init__("Topics")
        self.selected_topics = set()
        self.topic_manager = TopicManager()  # 使用新的topic管理器
        self.all_topics = []  # Store all topics for filtering
        self.border_title = "Topics"
        self.border_subtitle = "Selected: 0"
        self.fuzzy_searcher = FuzzySearch(case_sensitive=False)
        self.multi_select_mode = False  # Add flag for multi-select mode
        self.show_root = False

    def on_mount(self) -> None:
        """Initialize when mounted"""
        super().on_mount()
        self.root.expand()

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
                # 添加新topic节点
                self.root.add(
                    self.get_node_label(topic),
                    data={"topic": topic, "selected": False},
                    allow_expand=False
                )
            else:
                # 更新已存在topic的显示
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
        
        # 移除不再存在的topics
        for topic in removed_topics:
            self.selected_topics.discard(topic)
            for node in list(self.root.children): 
                if node.data.get("topic") == topic:
                    node.remove()  
                    break
        
        # 更新计数减少但仍存在的topics
        for topic in updated_topics:
            for node in self.root.children:
                if node.data.get("topic") == topic:
                    node.label = self.get_node_label(
                        topic,
                        node.data.get("selected", False)
                    )
                    break
        
        self.update_border_subtitle()

    def toggle_select_all(self, event: Tree.NodeSelected) -> 'tuple[bool, int]':
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

class TopicTreeWrap(Container):
    """A wrapper component that contains a search input and a topic tree"""
    
    def __init__(self):
        super().__init__()
        self.topic_tree = None

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Input(
            placeholder="Search topics...",
            id="topic-search",
        )
        self.topic_tree = TopicTree()
        yield self.topic_tree

    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.border_title = "Topics"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        if event.input.id == "topic-search":
            self.topic_tree.filter_topics(event.value)

    # Delegate methods to TopicTree
    def set_topics(self, topics: list) -> None:
        """Set topics in the tree"""
        self.topic_tree.set_topics(topics)

    def get_selected_topics(self) -> list:
        """Get selected topics from the tree"""
        return self.topic_tree.get_selected_topics()

    def merge_topics(self, bag_path: str, new_topics: list) -> None:
        """Merge new topics into the tree"""
        self.topic_tree.merge_topics(bag_path, new_topics)

    def update_border_title(self):
        """Update the border title"""
        self.topic_tree.update_border_title()

    def toggle_select_all(self) -> 'tuple[bool, int]':
        """
        Toggle selection of all topics.
        
        Returns:
            tuple[bool, int]: (is_all_deselected, count_of_selected)
        """
        return self.topic_tree.toggle_select_all()

class BagSelector(DirectoryTree):
    """A directory tree widget specialized for selecting ROS bag files"""

    def __init__(self, init_path: str = "."):
        super().__init__(path=init_path)
        self.current_path = Path(init_path)
        self.guide_depth = 2
        self.show_root = True  
        self.show_guides = True
        self.show_only_bags = False
        self.multi_select_mode = False
        self.selected_bags = set()
        self.border_title = "File Explorer"
        self.logger = logger.getChild("BagSelector")
    
    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.update_border_subtitle()

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
        self._update_control_panel_state()
        self._update_topic_tree_mode()
    
    def _update_control_panel_state(self):
        """Update control panel enabled state based on multi-select mode"""
        control_panel = self.app.query_one(ControlPanel)
        control_panel.set_enabled(not self.multi_select_mode)
    
    def _update_topic_tree_mode(self):
        """Update topic tree mode based on multi-select mode"""
        topic_tree = self.app.query_one(TopicTreeWrap).topic_tree
        topic_tree.multi_select_mode = self.multi_select_mode
        topic_tree.filter_topics("")  # Refresh display
    
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths based on show_only_bags setting"""
        paths = super().filter_paths(paths)
        paths = [p for p in paths if not p.name.startswith('.')]
        if self.show_only_bags:
            return [p for p in paths if p.is_dir() or p.suffix.lower() == '.bag']
        return paths


    def _handle_directory_selection(self, path: Path, status: "StatusBar") -> None:
        """Handle directory selection logic"""
        if path == self.current_path:
            self.path = self.current_path.parent
        else:
            self.path = path
        self.current_path = self.path
        status.update_status(f"Entering directory: {path}")

    def _handle_non_bag_file(self, path: Path, status: "StatusBar") -> None:
        """Handle selection of non-bag files"""
        topic_tree = self.app.query_one(TopicTree)
        topic_tree.set_topics([])
        self.app.selected_bag = None
        status.update_status(f"File: {path} is not a bag file", "warning")

    def _handle_multi_select_bag(self, path: Path, event, status: "StatusBar") -> None:
        """Handle bag file selection in multi-select mode"""
        if str(path) in self.selected_bags:
            self._deselect_bag(path, event, status)
        else:
            self._select_bag(path, event, status)
        self.update_border_subtitle()

    def _deselect_bag(self, path: Path, event, status: "StatusBar") -> None:
        """Handle bag file deselection"""
        try:
            # Get topics from the bag before removing it
            topics, _, _ = Operation.load_bag(str(path))
            
            # Remove the bag from selected bags
            self.selected_bags.remove(str(path))
            event.node.label = Text(path.name)
            
            # Remove topics from TopicTree
            topic_tree = self.app.query_one(TopicTree)
            topic_tree.remove_bag_topics(str(path))
            
            status.update_status(f"Deselected: {path}")
        except Exception as e:
            self.logger.error(f"Error deselecting bag file: {str(e)}", exc_info=True)
            status.update_status(f"Error deselecting bag file: {str(e)}", "error")

    def _select_bag(self, path: Path, event, status: "StatusBar") -> None:
        """Handle bag file selection"""
        self.selected_bags.add(str(path))
        event.node.label = Text("☑️ ") + Text(path.name)
        status.update_status(f"Selected: {path}")
        
        try:
            topics, _, _ = Operation.load_bag(str(path))
            topic_tree = self.app.query_one(TopicTree)
            topic_tree.merge_topics(str(path), topics)
        except Exception as e:
            self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
            status.update_status(f"Error loading bag file: {str(e)}", "error")

    def _handle_single_select_bag(self, path: Path, status: "StatusBar") -> None:
        """Handle bag file selection in single-select mode"""
        self.app.selected_bag = str(path)
        try:
            topics, connections, (start_time, end_time) = Operation.load_bag(str(path))
            self._update_ui_for_selected_bag(path, topics, (start_time, end_time))
            status.update_status(f"File: {path} loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
            status.update_status(f"Error loading bag file: {str(e)}", "error")

    def _update_ui_for_selected_bag(self, path: Path, topics: list, time_range: tuple) -> None:
        """Update UI components after selecting a bag file"""
        topic_tree = self.app.query_one(TopicTree)
        topic_tree.set_topics(topics)
        
        control_panel = self.app.query_one(ControlPanel)
        start_str, end_str = Operation.convert_time_range_to_str(*time_range)
        control_panel.set_time_range(start_str, end_str)
        control_panel.set_output_file(f"{path.stem}_filtered.bag")
        
        main_screen = self.app.query_one(MainScreen)
        main_screen.apply_whitelist(topics)

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

class ControlPanel(Container):
    """A container widget providing controls for ROS bag file operations"""
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the control panel"""
        with Vertical():
            with Vertical():
                with Vertical(id="time-range-container1"):
                    yield Label("From:")
                    yield Input(placeholder="[YY/MM/DD HH:MM:SS]", id="start-time", classes="time-input")
                with Vertical(id="time-range-container2"):
                    yield Label("To:")
                    yield Input(placeholder="[YY/MM/DD HH:MM:SS]", id="end-time", classes="time-input")
                with Vertical(id="output-file-container"):
                    yield Label("Output File:")
                    yield Input(placeholder="", id="output-file", classes="file-input")
            
            with Container(id="add-task-btn-container"):
                yield Button(label="Add Task", variant="primary", id="add-task-btn", classes="task-btn")
    
    def on_mount(self) -> None:
        """Initialize control panel"""
        self.border_title = "Control Panel"
    
    def get_time_range(self) -> 'tuple[str, str]':
        """Get the current time range from inputs, converting to milliseconds"""
        return self.query_one("#start-time").value, self.query_one("#end-time").value
    
    def get_output_file(self) -> str:
        """Get the output file name"""
        return self.query_one("#output-file").value or "output.bag"
    
    def set_time_range(self, start_time_st: str, end_time_str: str) -> None:
        """Set the time range in inputs, converting from milliseconds to seconds"""
        self.query_one("#start-time").value = start_time_st
        self.query_one("#end-time").value = end_time_str

    def set_output_file(self, output_file: str) -> None:
        """Set the output file name"""
        self.query_one("#output-file").value = output_file

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable all input controls in the panel.
        
        Args:
            enabled (bool): Whether to enable the controls
        """
        for input_widget in self.query("Input"):
            input_widget.disabled = not enabled
        if input_widget.disabled:
            self.query_one("#start-time").value = ""
            self.query_one("#end-time").value = ""
            self.query_one("#output-file").value = "Filename will be generated"
            self.query_one("#add-task-btn").label = "Add Tasks"
        else:
            self.query_one("#add-task-btn").label = "Add Task"

class SplashScreen(Screen):
    """Splash screen for the app."""
    
    BINDINGS = [
        ("space", "continue", "Enter"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help")
    ]

    def compose(self) -> ComposeResult:
        txt2art = text2art("ROSE",font="big")
        with Vertical(id="splash-content"):
            yield Vertical(
                Static(txt2art, id="logo"),
                Static("Yet another ros bag editor", id="subtitle"),
                Static("Press SPACE to Enter, H for help, Q to quit", id="prompt"),
                id="splash-content"
            )

            with Container():
                with Horizontal(id="about"):  
                    yield Link(
                        "Project Page: https://github.com/hanxiaomax/rose",
                        url="https://github.com/hanxiaomax/rose",
                        tooltip="Ctrl + Click to open in browser",
                        classes="about-link",
                    )
                    yield Rule(orientation="vertical",id="about-divider")
                    yield Link(
                        "Author: Lingfeng_Ai",
                        url="https://github.com/hanxiaomax",
                        tooltip="Ctrl + Click to open in browser",
                        classes="about-link",
                    )
        yield Footer()

    def action_continue(self) -> None:
        """Handle space key press to switch to main screen"""
        self.app.switch_mode("main")

    def action_quit(self) -> None:
        """Handle q key press to quit the app"""
        self.app.exit()

    def action_help(self) -> None:
        """Handle h key press to show help screen"""
        self.app.notify("Help screen not implemented yet", title="Help")

class TaskTable(DataTable):
    """Table for displaying tasks"""
    
    def __init__(self):
        super().__init__()
        self.task_count = 0
    
    def on_mount(self) -> None:
        """Initialize table when mounted"""
        self.cursor_type = "row"
        self.border_title = "Tasks"
    
    def get_file_size(self, file_path: str) -> str:
        """Get file size with appropriate unit (B, KB, MB, GB)"""
        try:
            size_bytes = Path(file_path).stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.2f} GB"
        except FileNotFoundError:
            return "0.00 B"

    def add_task(self, input_bag: str, output_bag: str, time_cost: float, time_range: tuple) -> None:
        """Add a new task to the table"""
        if self.task_count == 0:
            self.add_columns("ID", "Input", "Output", "Time Range", "Size", "Time Elapsed")
            self.add_class("has-header") 

        self.task_count += 1

        input_size = self.get_file_size(input_bag)
        output_size = self.get_file_size(output_bag)
        start_time, end_time = Operation.convert_time_range_to_str(*time_range)

        self.add_row(
            str(self.task_count),
            Path(input_bag).name,
            Path(output_bag).name,
            f"{start_time} - {end_time}",
            f"{input_size} -> {output_size}",
            f"{time_cost}s"
        )

class StatusBar(Static):
    """Custom status bar with dynamic styling"""

    def update_status(self, message: str, status_class: str = "") -> None:
        """Update status message with optional style"""
        message = Text(message)
        self.classes = ""
        if status_class:
            self.classes = status_class
        
        self.update(message)

class ConfirmDialog(Screen):
    """Dialog screen for confirming actions"""
    
    def compose(self) -> ComposeResult:
        """Create dialog content"""
        with Vertical(id="dialog-container"):
            yield Label("Are you sure you want to quit?")
            with Horizontal(id="dialog-buttons"):
                yield Button("No", id="confirm-no")
                yield Button("Yes",id="confirm-yes")
                

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "confirm-yes":
            self.app.exit()
        else:
            self.app.pop_screen()

class MainScreen(Screen):
    """Main screen of the app."""
    BINDINGS = [
        ("f", "toggle_bags_only", "Filter Bags"),
        ("w", "load_whitelist", "Load Whitelist"),
        ("s", "save_whitelist", "Save Whitelist"),
        ("a", "toggle_select_all_topics", "Select All"),
        ("m", "toggle_multi_select", "Multi Mode"),
        ("q", "quit", "Quit"),
    ]
    
    selected_bag = reactive(None)
    selected_whitelist_path = reactive(None)  

    def __init__(self):
        super().__init__()
        self.logger = logger.getChild("MainScreen")
        self.config = load_config()
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Container():
            with Vertical(id="file-explorer-area"):
                yield BagSelector(str(Path(__file__).parent))

            with Vertical(id="main-area"):
                with Horizontal(id="topics-area"):
                    yield TopicTreeWrap()
                    yield ControlPanel()
                with Container(id="tasks-table-container"):
                    yield TaskTable()
        
        with Container(id="status-bar"):
            yield StatusBar("", id="status")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        status = self.query_one(StatusBar)
        
        if event.button.id == "add-task-btn":
            bag_selector = self.query_one(BagSelector)
            control_panel = self.query_one(ControlPanel)
            topic_tree = self.query_one(TopicTreeWrap)
            selected_topics = topic_tree.get_selected_topics()
            
            if not selected_topics:
                self.app.notify("Please select at least one topic", title="Error", severity="error")
                return

            try:
                if bag_selector.multi_select_mode:
                    # 多选模式下处理多个bag文件
                    if not bag_selector.selected_bags:
                        self.app.notify("Please select at least one bag file", title="Error", severity="error")
                        return

                    success_count = 0
                    
                    for bag_path in bag_selector.selected_bags:
                        try:
                            # 获取bag文件的完整时间范围
                            _, _, bag_time_range = Operation.load_bag(bag_path)
                            output_file = f"{Path(bag_path).stem}_filtered.bag"
                            
                            process_start = time.time()
                            Operation.filter_bag(
                                bag_path,
                                output_file,
                                selected_topics,
                                bag_time_range  # 使用bag自己的时间范围
                            )
                            process_end = time.time()
                            time_cost = int(process_end - process_start)
                            
                            task_table = self.query_one(TaskTable)
                            task_table.add_task(
                                bag_path, 
                                output_file, 
                                time_cost,
                                bag_time_range  # 使用bag自己的时间范围
                            )
                            success_count += 1
                            
                        except Exception as e:
                            self.logger.error(f"Error processing {bag_path}: {str(e)}", exc_info=True)
                            self.app.notify(f"Error processing {Path(bag_path).name}: {str(e)}", 
                                          title="Error", 
                                          severity="error")
                            continue
                    
                    if success_count > 0:
                        self.app.notify(f"Successfully processed {success_count} of {len(bag_selector.selected_bags)} bag files", 
                                      title="Success", 
                                      severity="information")
                
                else:
                    # 单选模式下的处理逻辑
                    if not self.app.selected_bag:
                        self.app.notify("Please select a bag file first", title="Error", severity="error")
                        return

                    self.logger.debug(f"Starting bag filtering task: {self.app.selected_bag} -> {control_panel.get_output_file()}")
                    start_time = time.time()
                    Operation.filter_bag(
                        self.app.selected_bag,
                        control_panel.get_output_file(),
                        selected_topics,
                        Operation.convert_time_range_to_tuple(*control_panel.get_time_range())
                    )
                    end_time = time.time()
                    time_cost = int(end_time - start_time)
                    
                    task_table = self.query_one(TaskTable)
                    task_table.add_task(
                        self.app.selected_bag, 
                        control_panel.get_output_file(), 
                        time_cost, 
                        Operation.convert_time_range_to_tuple(*control_panel.get_time_range())
                    )
                    
                    self.app.notify(f"Bag conversion completed in {time_cost} seconds", 
                                  title="Success", 
                                  severity="information")
                
            except Exception as e:
                self.logger.error(f"Error during bag filtering: {str(e)}", exc_info=True)
                self.app.notify(f"Error during bag filtering: {str(e)}", title="Error", severity="error")

    def apply_whitelist(self, topics: list) -> None:
        """Apply whitelist to loaded topics"""
        if not self.app.selected_whitelist_path:
            return
            
        try:
            whitelist = self.load_whitelist(self.app.selected_whitelist_path)
            topic_tree = self.app.query_one(TopicTreeWrap)
            
            topic_tree.selected_topics.clear()
            
            for node in topic_tree.root.children:
                topic = node.data.get("topic")
                if topic in whitelist:
                    node.data["selected"] = True
                    topic_tree.selected_topics.add(topic)
                    node.label = Text("☑️ ") + Text(topic)
                else:
                    node.data["selected"] = False
                    node.label = topic
                    
            topic_tree.update_border_title()
            

        except Exception as e:
            self.logger.error(f"Error applying whitelist: {str(e)}", exc_info=True)
            self.app.notify(f"Error applying whitelist: {str(e)}", title="Error", severity="error")

    def load_whitelist(self, path: str) -> 'list[str]':
        """Load whitelist from file"""
        try:
            with open(path, 'r') as f:
                return [line.strip() for line in f.readlines() 
                       if line.strip() and not line.strip().startswith('#')]
        except Exception as e:
            raise Exception(f"Error loading whitelist: {str(e)}")
    def action_toggle_bags_only(self) -> None:
        """Toggle show only bags mode"""
        bag_selector = self.query_one(BagSelector)
        bag_selector.show_only_bags = not bag_selector.show_only_bags
        bag_selector.reload()
    
    def action_load_whitelist(self) -> None:
        """Load whitelist from config"""
        if not self.config.get("whitelists"):
            self.app.notify("No whitelists configured", title="Error", severity="warning")
            return
    
        self.app.switch_mode("whitelist")
    
    def action_toggle_select_all_topics(self) -> None:
        """Toggle select all topics in the topic tree"""
        topic_tree_wrap = self.app.query_one(TopicTreeWrap)
        status = self.query_one(StatusBar)
        
        try:
            all_deselected, selected_count = topic_tree_wrap.toggle_select_all()
            if selected_count == 0:
                status.update_status("No topics available to select", "error")
            else:
                if all_deselected:
                    status.update_status("Deselected all topics")
                else:
                    status.update_status(f"Selected all {selected_count} topics")
        except Exception as e:
            self.logger.error(f"Error toggling topic selection: {str(e)}", exc_info=True)
            status.update_status(f"Error toggling topic selection: {str(e)}", "error")

    def action_save_whitelist(self) -> None:
        """Save currently selected topics as a whitelist"""
        topic_tree = self.app.query_one(TopicTreeWrap)
        selected_topics = topic_tree.get_selected_topics()
        
        if not selected_topics:
            status = self.query_one(StatusBar)
            status.update_status("No topics selected to save", "error")
            return
        
        # Create whitelists directory if it doesn't exist
        whitelist_dir = Path("whitelists")
        whitelist_dir.mkdir(exist_ok=True)
        
        # Generate a unique filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        whitelist_path = whitelist_dir / f"whitelist_{timestamp}.txt"
        
        try:
            with open(whitelist_path, "w") as f:
                f.write("# Automatically generated whitelist\n")
                for topic in sorted(selected_topics):
                    f.write(f"{topic}\n")
            
            # Update config with new whitelist
            whitelist_name = f"whitelist_{timestamp}"
            self.config.setdefault("whitelists", {})[whitelist_name] = str(whitelist_path)
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=4)
            
            self.app.notify(f"Whitelist saved to {whitelist_path}", title="Success", severity="information")
        except Exception as e:
            self.app.notify(f"Error saving whitelist: {str(e)}", title="Error", severity="error")

    def action_toggle_multi_select(self) -> None:
        """Toggle multi-select mode"""
        bag_selector = self.query_one(BagSelector)
        bag_selector.toggle_multi_select_mode()

    def action_quit(self) -> None:
        """Show confirmation dialog before quitting"""
        self.app.push_screen(ConfirmDialog())

class WhitelistScreen(Screen):
    """Screen for selecting whitelists"""
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("y", "confirm", "Confirm Selection"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the whitelist screen"""
        with Vertical(id="whitelist-container"):
            yield Static("Shall we select a whitelist?", id="whitelist-header")
            with Horizontal(id="whitelist-container"):
                whitelist_names = list(self.app.config.get("whitelists", {}).keys())
                yield SelectionList(
                    *[(name, name) for name in whitelist_names],
                    id="whitelist-select",
                )
                
                yield TextArea(
                    "No whitelist selected",
                    id="whitelist-preview",
                    language="text",
                    read_only=True,
                    show_line_numbers=True
                )
        
        yield Footer()

    def action_quit(self) -> None:
        """Handle q key press to quit whitelist selection"""
        self.app.switch_mode("main")
    
    def action_confirm(self) -> None:
        """Handle y key press to confirm selection and apply whitelist"""
        selection_list = self.query_one("#whitelist-select")
        selected_values = selection_list.selected
        
        if not selected_values:
            self.app.notify("No whitelist selected", title="Warning", severity="warning")
            return
        
        whitelist_name = selected_values[0]
        whitelist_path = self.app.config["whitelists"].get(whitelist_name)
        
        if not whitelist_path:
            self.app.notify("Whitelist path not found", title="Error", severity="error")
            return
        
        self.app.selected_whitelist_path = whitelist_path
        self.app.switch_mode("main")
        
        topic_tree = self.app.query_one(TopicTreeWrap)
        if topic_tree and topic_tree.root.children:
            main_screen = self.app.query_one(MainScreen)
            main_screen.apply_whitelist([node.data.get("topic") for node in topic_tree.root.children])
        elif topic_tree:
            topic_tree.update_border_title()

        self.app.notify(f"Whitelist '{Path(whitelist_path).stem}' applied successfully", 
                       title="Whitelist Loaded", 
                       severity="information")

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Handle whitelist selection and show preview"""
        selection_list = event.selection_list
        selected_values = selection_list.selected
        preview = self.query_one("#whitelist-preview")
        
        # Ensure single selection by clearing previous selections
        if len(selected_values) > 1:
            last_selected = selected_values[-1]
            selection_list.deselect_all()
            selection_list.select(last_selected)
            selected_values = [last_selected]
        
        if not selected_values:
            preview.load_text("No whitelist selected")
            return
        
        whitelist_name = selected_values[0]
        whitelist_path = self.app.config["whitelists"].get(whitelist_name)
        
        if not whitelist_path:
            preview.load_text("Error: Whitelist path not found")
            return
        
        try:
            with open(whitelist_path, 'r') as f:
                whitelist_content = f.read()
            preview.load_text(whitelist_content)
        except Exception as e:
            preview.load_text(f"Error loading whitelist: {str(e)}")

class RoseTUI(App):
    """Textual TUI for filtering ROS bags"""
    
    CSS_PATH = "style.tcss"
    BINDINGS = [("q", "quit", "Quit")]
    COMMAND_PALETTE_BINDING = "p"
    MODES = {
        "splash": SplashScreen,
        "main": MainScreen,
        "whitelist": WhitelistScreen,  
    }
    selected_bag = reactive(None)
    selected_whitelist_path = reactive(None)  # Move selected_whitelist_path to App level
    
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.logger = logger.getChild("RoseTUI")
        self.logger.info("Initializing RoseTUI application")
        

    def on_mount(self) -> None:
        """Start with the splash screen or main screen based on config"""
        if self.config.get("show_splash_screen", True):
            self.switch_mode("splash")
        else:
            self.switch_mode("main")
        self.register_theme(CASSETTE_THEME_DARK)
        self.register_theme(CASSETTE_THEME_LIGHT)
        self.theme = self.config.get("theme", "cassette-dark")
    
    # command palette
    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        # copy some of the useful commands from the default implementation
        yield SystemCommand("Toggle Dark Mode", "Toggle Dark Mode", self.toggle_dark_mode) 
        if screen.maximized is not None:
            yield SystemCommand(
                "Minimize",
                "Minimize the widget and restore to normal size",
                screen.action_minimize,
            )
        elif screen.focused is not None and screen.focused.allow_maximize:
            yield SystemCommand(
                "Maximize", "Maximize the focused widget", screen.action_maximize
            )
        yield SystemCommand(
            "Quit the application",
            "Quit the application as soon as possible",
            super().action_quit,
        )

    def toggle_dark_mode(self):
        self.theme = "cassette-dark" if self.theme == "cassette-light" else "cassette-light"
    
    

if __name__ == "__main__":
    RoseTUI().run()
