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
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (Footer, Header, 
    Pretty, Static, Rule, Link, SelectionList, TextArea, RichLog, Tabs, Tab
)
from themes.cassette_theme import CASSETTE_THEME_DARK, CASSETTE_THEME_LIGHT
from core.util import Operation, setup_logging

from textual.reactive import reactive
from components.TopicPanel import TopicTreePanel
from components.BagSelector import BagSelector
from components.Dialog import ConfirmDialog
from components.StatusBar import StatusBar
from components.ControlPanel import ControlPanel
from components.TaskTable import TaskTable

from rich.syntax import Syntax

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
        ("q", "quit", "Quit"),
        ("w", "load_whitelist", "Load Whitelist"),
        ("s", "save_whitelist", "Save Whitelist"),
        ("a", "toggle_select_all_topics", "Select All"),
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
        
        bags = self.app.query_one(BagSelector).bags
        selected_topics = bags.get_selected_topics()
        
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
        
        remove_whitelist = False
        if not selected_values:
            whitelist_path = ""
            whitelist = []
            remove_whitelist = True
            
        else:
            whitelist_name = selected_values[0]
            whitelist_path = self.app.config["whitelists"].get(whitelist_name)
            whitelist = self.load_whitelist(whitelist_path)
        
            if not whitelist_path:
                self.app.notify("Whitelist path not found", title="Error", severity="error")
                return
        
        self.app.switch_mode("main")
        bags = self.app.query_one(BagSelector).bags
        
        # apply whitelist
        all_topics = list(bags.get_topic_summary().keys())
        # clear current selected topics
        bags.clear_selected_topics()
        for topic in all_topics:
            if topic in whitelist:
                bags.select_topic(topic)
        
        if remove_whitelist:
            self.app.notify(f"No Whitelist applied", 
                       title="Whitelist Loaded", 
                       severity="information")
        else:
            self.app.notify(f"Whitelist '{Path(whitelist_path).stem}' applied successfully", 
                       title="Whitelist Loaded", 
                       severity="information")
 

    def load_whitelist(self, path: str) -> 'list[str]':
        """Load whitelist from file"""
        try:
            with open(path, 'r') as f:
                return [line.strip() for line in f.readlines() 
                       if line.strip() and not line.strip().startswith('#')]
        except Exception as e:
            raise Exception(f"Error loading whitelist: {str(e)}")
        
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
            preview.load_text("No whitelist selected, press y to remove applied whitelist")
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

class InfoScreen(Screen):
    """Screen for displaying information with tabs"""
    
    BINDINGS = [("q", "quit", "Back to Main")]
    
    def __init__(self, title: str, content):
        super().__init__()
        self.title = title
        self.content = content
        self.log_content = self.load_logs()

    def compose(self) -> ComposeResult:
        """Create child widgets with tabs"""
        yield Header()
        with Container():
            yield Tabs(
                Tab("Debug Info", id="debug-tab"),
                Tab("Logs", id="logs-tab")
            )
            with Vertical(id="content-container"):
                yield Pretty(self.content, id="debug-content")
                yield RichLog(
                    highlight=True,
                    markup=True,
                    wrap=True,
                    id="log-content",
                    classes="logs"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen state"""
        self.query_one("#log-content").write(self.log_content)
        self.query_one("#log-content").visible = False

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle tab switching"""
        debug_content = self.query_one("#debug-content")
        log_content = self.query_one("#log-content")
        
        if event.tab.id == "debug-tab":
            debug_content.visible = True
            log_content.visible = False
        else:
            debug_content.visible = False
            log_content.visible = True

    def load_logs(self) -> str:
        """Load logs from file"""
        try:
            log_path = Path("rose_tui.log")
            if not log_path.exists():
                return "[red]No log file found at rose_tui.log[/red]"
                
            with open(log_path, "r") as f:
                return f.read()
        except Exception as e:
            return f"[red]Error loading logs: {str(e)}[/red]"

    def action_quit(self) -> None:
        """Handle q key press to return to main screen"""
        self.app.pop_screen()

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
    #selected_bag = reactive(None)
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
        yield SystemCommand(
            "Show Debug Info",
            "Show current state of BagManager and other debug information",
            self.show_bagmanager_info,
        )

    def show_logs(self):
        self.push_screen(InfoScreen(title="Logs", content=self.load_logs()))

    def show_bagmanager_info(self):
        """Display complete BagManager information using Pretty"""
        bag_manager = self.query_one(BagSelector).bags
        
        # Create a dictionary with all BagManager data
        bag_manager_data = {
            "bags": {str(path): bag.__dict__ for path, bag in bag_manager.bags.items()},
            "selected_topics": list(bag_manager.selected_topics),
            "total_bags": len(bag_manager.bags)
        }
        
        self.push_screen(
            InfoScreen(
                title="Debug Info - BagManager",
                content=bag_manager_data
            )
        )

    def toggle_dark_mode(self):
        self.theme = "cassette-dark" if self.theme == "cassette-light" else "cassette-light"
    
    

if __name__ == "__main__":
    RoseTUI().run()
