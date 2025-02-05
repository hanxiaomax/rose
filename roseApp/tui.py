#!/usr/bin/env python3

# Standard library imports
import json
import logging
import time
from pathlib import Path
from typing import Iterable

# Third-party imports
from art import text2art
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, DirectoryTree, Footer, Header, Input, Label,
    Placeholder, Static, Switch, Tree, Rule, Link, SelectionList, TextArea, RichLog
)
from themes.cassette_theme import CASSETTE_THEME_DARK, CASSETTE_THEME_LIGHT
from core.util import Operation, setup_logging
from textual.worker import Worker, WorkerState
from textual.reactive import reactive
from components.Panel import TopicTreePanel,BagSelector
from components.Dialog import ConfirmDialog
from components.StatusBar import StatusBar
from core.BagManager import BagManager

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



class ControlPanel(Container):
    """A container widget providing controls for ROS bag file operations"""
    
    def __init__(self):
        super().__init__()
        self.logger = logger.getChild("ControlPanel")
        
    def on_mount(self) -> None:
        """Initialize control panel"""
        self.border_title = "Control Panel"
        self.watch(self.app.query_one(BagSelector), "bags", self.handle_bags_change)
        self.watch(self.app.query_one(BagSelector), "multi_select_mode", 
                                self.handle_multi_select_mode_change)
    
    def handle_multi_select_mode_change(self, multi_select_mode: bool) -> None:
        """Handle multi select mode change"""
        self.set_enabled(not multi_select_mode)
        self.query_one("#add-task-btn").label = "Add Tasks" if multi_select_mode else "Add Task"

    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle bag change event"""
        # control panel should be disabled when multi select mode is on
        bag = bags.get_single_bag()
        if bag and not self.disabled:
            self.set_time_range(bag.info.time_range_str)
            self.set_output_file(f"{bag.path.stem}_filtered.bag")
        
    
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
    
    def get_time_range(self) -> 'tuple[str, str]':
        """Get the current time range from inputs, converting to milliseconds"""
        return self.query_one("#start-time").value, self.query_one("#end-time").value
    
    def get_output_file(self) -> str:
        """Get the output file name"""
        return self.query_one("#output-file").value or "output.bag"
    
    def set_time_range(self, time_range_str) -> None:
        """Set the time range in inputs, converting from milliseconds to seconds"""
        self.query_one("#start-time").value = time_range_str[0]
        self.query_one("#end-time").value = time_range_str[1]

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "add-task-btn":
            self._handle_add_task()

    
    def _handle_add_task(self) -> None:
        """Handle add task button press"""
        bag_selector = self.app.query_one(BagSelector)
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        selected_topics = topic_tree.get_selected_topics()
        
        if not selected_topics:
            self.app.notify("Please select at least one topic", title="Error", severity="error")
            return

        try:
            if bag_selector.multi_select_mode:
                self._handle_multi_bag_task(bag_selector, selected_topics)
            else:
                self._handle_single_bag_task(selected_topics)
        except Exception as e:
            self.logger.error(f"Error during bag filtering: {str(e)}", exc_info=True)
            self.app.notify(f"Error during bag filtering: {str(e)}", title="Error", severity="error")

    @work(thread=True)
    def _process(self,task_table, bag_path: str, selected_topics: list,time_range:tuple,output_file:str) -> None:
        """Handle task creation for single bag"""
        process_start = time.time()
        
        Operation.filter_bag(
            bag_path,
            output_file,
            selected_topics,
            time_range
        )
        process_end = time.time()
        time_cost = int(process_end - process_start)
        
        # update UI
        self.app.call_from_thread(
            task_table.add_task,
            bag_path,
            output_file,
            time_cost,
            time_range
        )
            

    def _handle_multi_bag_task(self, bag_selector: BagSelector, selected_topics: list) -> None:
        """Handle task creation for multiple bags"""
        if not bag_selector.selected_bags:
            self.app.notify("Please select at least one bag file", title="Error", severity="error")
            return

        task_count = 0
        task_table = self.app.query_one(TaskTable)
        
        for bag_path in bag_selector.selected_bags:
            try:
                _, _, bag_time_range = Operation.load_bag(bag_path)
                output_file = f"{Path(bag_path).stem}_filtered.bag"
                self._process(task_table,bag_path,selected_topics,bag_time_range,output_file)
                task_count += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {bag_path}: {str(e)}", exc_info=True)
                self.app.notify(f"Error processing {Path(bag_path).name}: {str(e)}",
                title="Error",
                severity="error")
        
        if task_count > 0:
            self.app.notify(
                f"Successfully add {task_count} tasks",
                title="INFO",severity="information")
               

    def _handle_single_bag_task(self, selected_topics: list) -> None:
        """Handle task creation for single bag"""
        if not self.app.selected_bag:
            self.app.notify("Please select a bag file first",title="Error",severity="error")
            return

        try:
            self.logger.debug(f"Starting bag filtering task: {self.app.selected_bag} -> {self.get_output_file()}")
            start_time = time.time()
            time_range = Operation.convert_time_range_to_tuple(*self.get_time_range())
            task_table = self.app.query_one(TaskTable)

            self._process(task_table,self.app.selected_bag,selected_topics,time_range,self.get_output_file())

        except Exception as e:
            self.logger.error(f"Error processing bag: {str(e)}", exc_info=True)
            self.app.notify(f"Error processing bag: {str(e)}",
                title="Error",
                severity="error")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        worker = event.worker
        state = event.state
        bag_name = Path(worker.description.split(",")[1]).stem
        if state == WorkerState.SUCCESS:
            self.app.notify(f"Successfully processed {bag_name}",
                title="Success",
                severity="information")
        elif state == WorkerState.ERROR:
            self.app.notify(f"Failed when processing {bag_name} ",
                title="Error",
                severity="error")
        #elif state == WorkerState.RUNNING:
        #    self.app.notify(
        #        f"Task started, please wait...",
        #        title="INFO",severity="information")


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
            self.add_columns("ID", "Status", "Input", "Output", "Time Range", "Size", "Time Elapsed")
            self.add_class("has-header") 

        self.task_count += 1

        input_size = self.get_file_size(input_bag)
        output_size = self.get_file_size(output_bag)
        start_time, end_time = Operation.convert_time_range_to_str(*time_range)

        self.add_row(
            str(self.task_count),
            "done",
            Path(input_bag).name,
            Path(output_bag).name,
            f"{start_time[9:]} - {end_time[9:]}", #only display time in HH:MM:SS
            f"{input_size} -> {output_size}",
            f"{time_cost}s"
        )



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
                    yield TopicTreePanel()
                    yield ControlPanel()
                with Container(id="tasks-table-container"):
                    yield TaskTable()
        
        with Container(id="status-bar"):
            yield StatusBar("", id="status")
        yield Footer()
    
    def apply_whitelist(self, topics: list) -> None:
        """Apply whitelist to loaded topics"""
        if not self.app.selected_whitelist_path:
            return
            
        try:
            whitelist = self.load_whitelist(self.app.selected_whitelist_path)
            topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
            topic_tree.clear_selection()
            
            for topic in topics:
                if topic in whitelist:
                    topic_tree.select_topic(topic)
                    
            # Update panel title
            topic_panel = self.app.query_one(TopicTreePanel)
            topic_panel.border_title = f"Topics (Whitelist: {Path(self.app.selected_whitelist_path).stem})"

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
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        status = self.query_one(StatusBar)
        
        try:
            all_deselected, selected_count = topic_tree.toggle_select_all()
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
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
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
        self.app.push_screen(ConfirmDialog("Are you sure you want to quit?",self.app.exit,self.app.pop_screen))

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
        
        topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        if topic_tree and topic_tree.all_topics:
            main_screen = self.app.query_one(MainScreen)
            main_screen.apply_whitelist(topic_tree.all_topics)
        else:
            # Update panel title
            topic_panel = self.app.query_one(TopicTreePanel)
            topic_panel.border_title = f"Topics (Whitelist: {Path(whitelist_path).stem})"

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

class LogsScreen(Screen):
    """Screen for displaying application logs"""
    
    BINDINGS = [
        ("q", "quit", "Back"),
        ("r", "reload", "Reload"),
        ("j", "scroll_end", "Scroll to End"),
        ("k", "scroll_home", "Scroll to Top"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the logs screen"""
        yield Header(show_clock=True)
        
        with Container(id="logs-container"):
            yield RichLog(
                highlight=True,
                markup=True,
                wrap=True,
                id="log-viewer",
                classes="logs"
            )
            
        yield Footer()

    def on_mount(self) -> None:
        """Load logs when screen is mounted"""
        self.load_logs()

    def load_logs(self) -> None:
        """Load and display logs from file"""
        log_viewer = self.query_one(RichLog)
        log_viewer.clear()
        
        try:
            log_path = Path("rose_tui.log")
            if not log_path.exists():
                log_viewer.write("[red]No log file found at rose_tui.log[/red]")
                return
                
            with open(log_path, "r") as f:
                log_content = f.read()
                
            # Split content into lines and add syntax highlighting
            from rich.syntax import Syntax
            log_viewer.write(
                Syntax(
                    log_content, 
                    "log",
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True
                )
            )
            
            # Scroll to end by default
            log_viewer.scroll_end(animate=False)
            
        except Exception as e:
            log_viewer.write(f"[red]Error loading logs: {str(e)}[/red]")

    def action_quit(self) -> None:
        """Handle q key press to return to previous screen"""
        self.app.pop_screen()

    def action_reload(self) -> None:
        """Handle r key press to reload logs"""
        self.load_logs()
        self.notify("Logs reloaded", severity="information")

    def action_scroll_end(self) -> None:
        """Handle end key press to scroll to bottom"""
        log_viewer = self.query_one(RichLog)
        log_viewer.scroll_end(animate=True)

    def action_scroll_home(self) -> None:
        """Handle home key press to scroll to top"""
        log_viewer = self.query_one(RichLog)
        log_viewer.scroll_home(animate=True)

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
        yield SystemCommand(
            "Show Logs",
            "Show Logs",
            self.show_logs,
        )

    def show_logs(self):
        self.push_screen(LogsScreen())

    def toggle_dark_mode(self):
        self.theme = "cassette-dark" if self.theme == "cassette-light" else "cassette-light"
    
    

if __name__ == "__main__":
    RoseTUI().run()
