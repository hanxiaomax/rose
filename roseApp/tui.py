#!/usr/bin/env python3

# Standard library imports
import json
import logging
import time
from pathlib import Path
from typing import Iterable

# Third-party imports
from art import text2art
from rich.style import Style
from rich.text import Text
from textual import work, log
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.logging import TextualHandler
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, DirectoryTree, Footer, Header, Input, Label,
    Placeholder, Static, Switch, Tree, Select
)
from textual.widgets.directory_tree import DirEntry
from themes.cassette_theme import CASSETTE_THEME
from util import Operation, setup_logging

# Initialize logging at the start of the file
logger = setup_logging()

def load_config():
    """Load configuration from config.json"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            logger.info("Successfully loaded config.json")
            return config
    except FileNotFoundError:
        logger.warning("config.json not found, using default configuration")
        return {"show_splash_screen": True}  # Default value
    except json.JSONDecodeError:
        logger.error("Error parsing config.json, using default configuration")
        return {"show_splash_screen": True}

class TopicTree(Tree):
    """A tree widget for displaying ROS bag topics with multi-selection capability"""
    
    def __init__(self):
        super().__init__("Topics")
        self.selected_topics = set()
        self.border_title = "Topics"
        self.border_subtitle = "Selected: 0"
    
    async def on_mount(self) -> None:
        """Initialize when the widget is mounted"""
        self.theme = "gruvbox"
        self.root.expand()
    
    def update_border_subtitle(self):
        """Update subtitle with selected topics count"""
        self.border_subtitle = f"Topic selected: {len(self.selected_topics)}"
    
    def update_border_title(self):
        """Update title with whitelist info if available"""
        if self.app.selected_whitelist_path:
            self.border_title = f"Topics (Whitelist: {Path(self.app.selected_whitelist_path).stem})"
        else:
            self.border_title = "Topics"

    def set_topics(self, topics: list) -> None:
        """Set topics and clear previous selections"""
        self.root.remove_children()
        self.selected_topics.clear()
        
        for topic in sorted(topics):
            self.root.add(
                topic,
                data={"topic": topic, "selected": False},
                allow_expand=False
            )
        
        self.update_border_subtitle()
        self.update_border_title()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle topic selection toggle"""
        if event.node.allow_expand or "Time range" in event.node.label:
            return
            
        data = event.node.data
        if data:
            data["selected"] = not data["selected"]
            topic = data["topic"]
            
            if data["selected"]:
                self.selected_topics.add(topic)
                event.node.label = Text("☑️ ")+Text(topic)
            else:
                self.selected_topics.discard(topic)
                event.node.label = topic
                
            self.update_border_subtitle()

    def get_selected_topics(self) -> list:
        """Return list of selected topics"""
        return list(self.selected_topics)

class BagSelector(DirectoryTree):
    """A directory tree widget specialized for selecting ROS bag files"""

    def __init__(self, init_path: str = "."):
        super().__init__(path=init_path)
        self.current_path = Path(init_path)
        self.guide_depth = 4
        self.show_root = True  
        self.show_guides = True
        self.show_only_bags = False
        self.border_title = "File Explorer"
        self.logger = logger.getChild("BagSelector")

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths based on show_only_bags setting"""
        paths = super().filter_paths(paths)
        paths = [p for p in paths if not p.name.startswith('.')]
        if self.show_only_bags:
            return [p for p in paths if p.is_dir() or p.suffix.lower() == '.bag']
        return paths

    def render_label(self, node: DirEntry, base_style, style) -> Text:
        label = super().render_label(node, base_style, style)
        if node.data.path.suffix.lower() == ".bag":
            label.stylize(Style(color="#ea5949", bold=True))
        return label

    @work
    async def on_tree_node_selected(self, event: DirectoryTree.NodeSelected) -> None:
        """Handle file selection with improved directory navigation"""
        path = event.node.data.path
        self.current_node = event.node
        self.show_guides = True
        status = self.app.query_one(StatusBar)

        if path.is_dir():
            if path == self.current_path:
                self.path = self.current_path.parent
            else:
                self.path = path
            self.current_path = self.path
            status.update_status(f"Entering directory: {path}", "success")

        elif str(path).endswith('.bag'):
            self.app.selected_bag = str(path)
            
            try:
                topics, connections, (start_time, end_time) = Operation.load_bag(str(path))
            except Exception as e:
                self.logger.error(f"Error loading bag file: {str(e)}", exc_info=True)
                status.update_status(f"Error loading bag file: {str(e)}", "error")
                return

            
   
            # Update TopicTree
            topic_tree = self.app.query_one(TopicTree)
            topic_tree.set_topics(topics)
            
            # Update ControlPanel
            control_panel = self.app.query_one(ControlPanel)
            start_str, end_str = Operation.convert_time_range_to_str(start_time, end_time)
            control_panel.set_time_range(start_str, end_str)
            control_panel.set_output_file(f"{path.stem}_filtered.bag")
            
            # Apply whitelist after loading bag
            main_screen = self.app.query_one(MainScreen)
            main_screen.apply_whitelist(topics)
            
            status.update_status(f"File: {path} loaded successfully", "success")
        
        else:
            # Clear TopicTree when selecting non-bag files
            topic_tree = self.app.query_one(TopicTree)
            topic_tree.set_topics([])
            self.app.selected_bag = None

            status.update_status(f"File: {path} is not a bag file", "error")

class ControlPanel(Container):
    """A container widget providing controls for ROS bag file operations"""
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the control panel"""
        with Vertical():
            with Horizontal():
                with Vertical(id="time-range-container1"):
                    yield Label("From:")
                    yield Input(placeholder="Start Time", id="start-time", classes="time-input")
                with Vertical(id="time-range-container2"):
                    yield Label("To:")
                    yield Input(placeholder="End Time", id="end-time", classes="time-input")
                with Vertical(id="output-file-container"):
                    yield Label("Output File:")
                    yield Input(placeholder="", id="output-file", classes="file-input")
            with Horizontal():
                with Container(id="add-task-btn-container"):
                    yield Button(label="Add Task", variant="primary", id="add-task-btn", classes="task-btn")
    
    def on_mount(self) -> None:
        """Initialize control panel"""
        self.border_title = "Control Panel"
        self.query_one("#start-time").value = "N.A"
        self.query_one("#end-time").value = "N.A"
    
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

class SplashScreen(Screen):
    """Splash screen for the app."""

    def compose(self) -> ComposeResult:
        txt2art = text2art("ROSE",font="big")
        yield Vertical(
            Static(txt2art, id="logo"),
            Static("Yet another ros bag editor", id="subtitle"),
            Static("Press H to continue", id="prompt"),
            id="splash-content"
        )

    def on_key(self) -> None:
        """Switch to the main screen when any key is pressed."""
        self.app.switch_mode("main")

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

class MainScreen(Screen):
    """Main screen of the app."""
    BINDINGS = [("f", "toggle_bags_only", "Toggle Bags Only"),
                ("w", "load_whitelist", "Load Whitelist"),
                ("s", "save_whitelist", "Save Whitelist"),
                ("a", "toggle_select_all_topics", "Toggle Select All Topics")]
    
    selected_bag = reactive(None)
    selected_whitelist_path = reactive(None)  # Move selected_whitelist_path to App level

    def __init__(self):
        super().__init__()
        self.logger = logger.getChild("MainScreen")
        self.config = load_config()
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Container():
            with Vertical(id="left-column"):
                with Container(id="file-explorer"):
                    yield BagSelector(str(Path(__file__).parent))

            with Vertical(id="main-area"):
                with Horizontal(id="topics-area"):
                    with Container(id="topics-container"):
                        yield TopicTree()

                    with Container(id="right-panel"):
                        yield Placeholder()

                yield ControlPanel()

                with Container(id="tasks-table"):
                    yield TaskTable()
        
        with Container(id="status-bar"):
            yield StatusBar("", id="status")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        status = self.query_one(StatusBar)
        
        if event.button.id == "add-task-btn":
            if not self.app.selected_bag:
                self.logger.warning("Attempted to add task without selecting bag file")
                status.update_status("Please select a bag file first", "error")
                return
            
            control_panel = self.query_one(ControlPanel)
            output_file = control_panel.get_output_file()
            start_time_str, end_time_str = control_panel.get_time_range()
            topic_tree = self.query_one(TopicTree)
            selected_topics = topic_tree.get_selected_topics()
            
            if not selected_topics:
                status.update_status("Please select at least one topic", "error")
                return
            
            try:
                self.logger.info(f"Starting bag filtering task: {self.app.selected_bag} -> {output_file}")
                start_time = time.time()  
                Operation.filter_bag(
                    self.app.selected_bag,
                    output_file,
                    selected_topics,
                    Operation.convert_time_range_to_tuple(start_time_str, end_time_str)
                )
                end_time = time.time()  
                time_cost = int(end_time - start_time)
                                
                task_table = self.query_one(TaskTable)
                task_table.add_task(self.app.selected_bag, output_file, time_cost, Operation.convert_time_range_to_tuple(start_time_str, end_time_str))
                
                self.logger.info(f"Task completed successfully in {time_cost}s")
                status.update_status(f"Task completed successfully in {time_cost}s", "success")
                
            except Exception as e:
                self.logger.error(f"Error during bag filtering: {str(e)}", exc_info=True)
                status.update_status(f"Error: {str(e)}", "error")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch toggle"""
        if event.switch.id == "bag-filter-switch":
            bag_selector = self.query_one(BagSelector)
            bag_selector.show_only_bags = event.value
            bag_selector.reload()

    def apply_whitelist(self, topics: list) -> None:
        """Apply whitelist to loaded topics"""
        if not self.app.selected_whitelist_path:
            return
            
        try:
            self.logger.info(f"Applying whitelist from: {self.app.selected_whitelist_path}")
            whitelist = self.load_whitelist(self.app.selected_whitelist_path)
            topic_tree = self.app.query_one(TopicTree)
            
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
                    
            topic_tree.update_border_subtitle()
            topic_tree.update_border_title()
            
            status = self.app.query_one(StatusBar)
            status.update_status(f"Applied whitelist: {Path(self.app.selected_whitelist_path).stem}", "success")
            
        except Exception as e:
            self.logger.error(f"Error applying whitelist: {str(e)}", exc_info=True)
            status = self.app.query_one(StatusBar)
            status.update_status(f"Error applying whitelist: {str(e)}", "error")

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
            status = self.query_one(StatusBar)
            status.update_status("No whitelists configured", "error")
            return
    
        self.app.switch_mode("whitelist")
    
    def action_toggle_select_all_topics(self) -> None:
        """Toggle select all topics in the topic tree"""
        topic_tree = self.app.query_one(TopicTree)
        if not topic_tree.root.children:
            status = self.query_one(StatusBar)
            status.update_status("No topics available to select", "error")
            return
        
        # Check if all topics are already selected
        all_selected = all(node.data["selected"] for node in topic_tree.root.children)
        
        # Toggle selection state
        for node in topic_tree.root.children:
            node.data["selected"] = not all_selected
            topic = node.data.get("topic")
            if node.data["selected"]:
                topic_tree.selected_topics.add(topic)
                node.label = Text("☑️ ") + Text(topic)
            else:
                topic_tree.selected_topics.discard(topic)
                node.label = topic
        
        topic_tree.update_border_subtitle()
        status = self.query_one(StatusBar)
        if all_selected:
            status.update_status("Deselected all topics", "success")
        else:
            status.update_status(f"Selected all {len(topic_tree.selected_topics)} topics", "success")

    def action_save_whitelist(self) -> None:
        """Save currently selected topics as a whitelist"""
        topic_tree = self.app.query_one(TopicTree)
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
            
            status = self.query_one(StatusBar)
            status.update_status(f"Whitelist saved to {whitelist_path}", "success")
        except Exception as e:
            status = self.query_one(StatusBar)
            status.update_status(f"Error saving whitelist: {str(e)}", "error")

class WhitelistScreen(Screen):
    """Screen for selecting whitelists"""
    
    BINDINGS = [("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the whitelist screen"""
        yield Header()
        with Vertical(id="whitelist-container"):
            yield Static("Select a whitelist to apply", id="whitelist-header")
            whitelist_names = list(self.app.config.get("whitelists", {}).keys())
            yield Select(
                options=[(name, name) for name in whitelist_names],
                prompt="Select whitelist",
                id="whitelist-select"
            )
        yield Footer()

    def action_quit(self) -> None:
        """Handle q key press to quit whitelist selection"""
        self.app.switch_mode("main")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle whitelist selection and apply if topics are loaded"""
        whitelist_name = event.value
        whitelist_path = self.app.config["whitelists"].get(whitelist_name)
        
        if not whitelist_path:
            return
        
        self.app.selected_whitelist_path = whitelist_path
        self.app.switch_mode("main")
        
        topic_tree = self.app.query_one(TopicTree)
        if topic_tree and topic_tree.root.children:
            main_screen = self.app.query_one(MainScreen)
            main_screen.apply_whitelist([node.data.get("topic") for node in topic_tree.root.children])
        elif topic_tree:
            topic_tree.update_border_title()

        status = self.app.query_one(StatusBar)
        status.update_status(f"Selected whitelist: {Path(whitelist_path).stem}", "success")

class RoseTUI(App):
    """Textual TUI for filtering ROS bags"""
    
    CSS_PATH = "style.tcss"
    BINDINGS = [("q", "quit", "Quit")]
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
            self.logger.info("Starting with splash screen")
            self.switch_mode("splash")
        else:
            self.logger.info("Starting with main screen")
            self.switch_mode("main")
        # self.theme = "monokai"
        self.register_theme(CASSETTE_THEME)
        self.theme = "cassette"
    

if __name__ == "__main__":
    RoseTUI().run()
