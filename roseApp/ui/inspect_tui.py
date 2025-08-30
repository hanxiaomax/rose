"""
Simple Interactive TUI for inspect command using textual
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Static, DataTable, Input, Button, TabbedContent, TabPane, Pretty
from textual.message import Message as TextualMessage
from textual.binding import Binding
from textual.screen import ModalScreen

from ..core.parser import create_parser
from ..core.cache import create_bag_cache_manager
from ..core.model import ComprehensiveBagInfo, TopicInfo
from ..core.util import get_logger
from ..ui.common_ui import CommonUI

logger = get_logger("InspectTUI")


class TopicSelected(TextualMessage):
    """Message sent when a topic is selected"""
    
    def __init__(self, topic_name: str):
        super().__init__()
        self.topic_name = topic_name


class FileSelector(ModalScreen):
    """Simple file selector modal"""
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal"):
            yield Static("Open Bag File", classes="title")
            yield Input(placeholder="Enter bag file path...", id="file_input")
            with Horizontal():
                yield Button("Open", id="open_btn", variant="primary")
                yield Button("Cancel", id="cancel_btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open_btn":
            file_path = self.query_one("#file_input", Input).value.strip()
            if file_path and Path(file_path).exists() and file_path.endswith('.bag'):
                self.dismiss(file_path)
            else:
                # Show error (simplified)
                self.query_one("#file_input", Input).value = ""
                self.query_one("#file_input", Input).placeholder = "Invalid bag file path..."
        elif event.button.id == "cancel_btn":
            self.dismiss(None)


class InspectTUI(App):
    """Simple TUI for bag inspection"""
    
    CSS = """
    .title {
        text-align: center;
        background: $primary;
        color: $text;
        padding: 1;
    }
    
    .modal {
        background: $surface;
        border: solid $primary;
        margin: 4 8;
        padding: 2;
        width: 60%;
        height: auto;
    }
    
    .section {
        border: solid $secondary;
        margin: 1 0;
        padding: 1;
    }
    
    #status {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    
    #bag_info {
        height: 8;
    }
    
    #topics_table {
        height: 1fr;
    }
    
    #message_details {
        height: 1fr;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+o", "open_file", "Open"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("f1", "help", "Help"),
    ]
    
    def __init__(self, bag_files: Optional[List[str]] = None):
        super().__init__()
        self.bag_files = bag_files or []
        self.current_bag_path: Optional[str] = None
        self.current_bag_info: Optional[ComprehensiveBagInfo] = None
        self.parser = create_parser()
        self.cache_manager = create_bag_cache_manager()
        self.selected_topic: Optional[str] = None
    
    def compose(self) -> ComposeResult:
        """Create the main layout"""
        yield Header(show_clock=True)
        
        with Vertical():
            # Bag information section
            with Container(classes="section", id="bag_info"):
                yield Static("Bag Information", classes="title")
                yield Static("No bag file loaded", id="bag_summary")
            
            # Topics and message details
            with Horizontal():
                # Topics table
                with Vertical():
                    yield Static("Topics", classes="title")
                    yield DataTable(id="topics_table")
                
                # Message details
                with Vertical():
                    yield Static("Message Details", classes="title")
                    with TabbedContent(id="message_details"):
                        with TabPane("Schema", id="schema_tab"):
                            yield ScrollableContainer(
                                Pretty("Select a topic to view schema"),
                                id="schema_content"
                            )
                        with TabPane("Stats", id="stats_tab"):
                            yield ScrollableContainer(
                                Pretty("Select a topic to view statistics"),
                                id="stats_content"
                            )
        
        yield Static("Ctrl+O: Open | Ctrl+R: Refresh | Ctrl+Q: Quit | F1: Help", id="status")
    
    def on_mount(self) -> None:
        """Initialize the TUI"""
        self.title = "Rose Bag Inspector"
        self._setup_topics_table()
        
        if self.bag_files:
            self.call_after_refresh(self._load_bag, self.bag_files[0])
    
    def _setup_topics_table(self):
        """Setup topics table"""
        table = self.query_one("#topics_table", DataTable)
        table.add_columns("Topic", "Type", "Count", "Freq (Hz)")
        table.cursor_type = "row"
    
    async def action_open_file(self) -> None:
        """Open file selector"""
        result = await self.push_screen(FileSelector())
        if result:
            await self._load_bag(result)
    
    async def action_refresh(self) -> None:
        """Refresh current bag"""
        if self.current_bag_path:
            await self._load_bag(self.current_bag_path)
    
    async def action_help(self) -> None:
        """Show help"""
        help_text = """Rose Bag Inspector

Keyboard Shortcuts:
• Ctrl+O: Open bag files
• Ctrl+R: Refresh current bag  
• Ctrl+Q: Quit application
• F1: Show help

Usage:
• Select topics to view details
• Use tabs to switch between schema and statistics
• Navigate with arrow keys
        """
        await self.push_screen(HelpModal(help_text))
    
    async def _load_bag(self, bag_path: str):
        """Load and analyze bag file"""
        try:
            self.current_bag_path = bag_path
            self._update_status(f"Loading {Path(bag_path).name}...")
            
            # Check cache
            cached_entry = self.cache_manager.get_analysis(Path(bag_path))
            if cached_entry and cached_entry.is_valid(Path(bag_path)):
                self.current_bag_info = cached_entry.bag_info
            else:
                # Load bag
                bag_info, _ = await self.parser.load_bag_async(
                    bag_path, 
                    build_index=False,
                    progress_callback=self._progress_callback
                )
                self.current_bag_info = bag_info
            
            # Update UI
            self._update_bag_summary()
            self._update_topics_table()
            self._update_status(f"Loaded {Path(bag_path).name}")
            
        except Exception as e:
            logger.error(f"Error loading bag: {e}")
            self._update_status(f"Error: {str(e)}")
    
    def _progress_callback(self, phase: str, percent: float):
        """Progress callback"""
        self._update_status(f"Loading: {phase} ({percent:.1f}%)")
    
    def _update_status(self, message: str):
        """Update status bar"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = self.query_one("#status", Static)
        status.update(f"[{timestamp}] {message}")
    
    def _update_bag_summary(self):
        """Update bag information display"""
        if not self.current_bag_info or not self.current_bag_path:
            return
        
        bag_info = self.current_bag_info
        path_obj = Path(self.current_bag_path)
        
        summary = f"""File: {path_obj.name}
Size: {CommonUI().format_file_size(path_obj.stat().st_size)}
Duration: {bag_info.duration:.2f}s
Topics: {len(bag_info.topics)}
Messages: {bag_info.message_count}
Start: {datetime.fromtimestamp(bag_info.start_time).strftime('%H:%M:%S')}
End: {datetime.fromtimestamp(bag_info.end_time).strftime('%H:%M:%S')}"""
        
        summary_widget = self.query_one("#bag_summary", Static)
        summary_widget.update(summary)
    
    def _update_topics_table(self):
        """Update topics table"""
        if not self.current_bag_info:
            return
        
        table = self.query_one("#topics_table", DataTable)
        table.clear()
        
        for topic in self.current_bag_info.topics:
            if isinstance(topic, str):
                table.add_row(topic, "unknown", "0", "0.0")
            else:
                freq_str = f"{topic.frequency:.1f}" if topic.frequency > 0 else "0.0"
                table.add_row(
                    topic.name,
                    topic.message_type.split('/')[-1] if '/' in topic.message_type else topic.message_type,
                    str(topic.message_count),
                    freq_str
                )
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle topic selection"""
        if event.row_key is not None:
            row_data = event.data_table.get_row(event.row_key)
            topic_name = str(row_data[0])
            self.selected_topic = topic_name
            self._update_message_details(topic_name)
    
    def _update_message_details(self, topic_name: str):
        """Update message details for selected topic"""
        if not self.current_bag_info:
            return
        
        # Find topic info
        topic_info = None
        for topic in self.current_bag_info.topics:
            if (isinstance(topic, str) and topic == topic_name) or \
               (hasattr(topic, 'name') and topic.name == topic_name):
                topic_info = topic
                break
        
        # Update schema tab
        if topic_info and hasattr(topic_info, 'message_type'):
            schema_text = f"Topic: {topic_name}\nMessage Type: {topic_info.message_type}"
            if hasattr(topic_info, 'message_definition') and topic_info.message_definition:
                schema_text += f"\n\nDefinition:\n{topic_info.message_definition}"
        else:
            schema_text = f"Topic: {topic_name}\nType: unknown"
        
        schema_content = self.query_one("#schema_content", ScrollableContainer)
        schema_content.remove_children()
        schema_content.mount(Pretty(schema_text))
        
        # Update stats tab
        if topic_info and hasattr(topic_info, 'message_count'):
            stats_text = f"Topic: {topic_name}\n"
            stats_text += f"Message Count: {topic_info.message_count}\n"
            if hasattr(topic_info, 'frequency'):
                stats_text += f"Frequency: {topic_info.frequency:.2f} Hz\n"
            if hasattr(topic_info, 'first_message_time'):
                start_time = datetime.fromtimestamp(topic_info.first_message_time)
                stats_text += f"First Message: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if hasattr(topic_info, 'last_message_time'):
                end_time = datetime.fromtimestamp(topic_info.last_message_time)
                stats_text += f"Last Message: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        else:
            stats_text = f"Topic: {topic_name}\nStatistics not available"
        
        stats_content = self.query_one("#stats_content", ScrollableContainer)
        stats_content.remove_children()
        stats_content.mount(Pretty(stats_text))


class HelpModal(ModalScreen):
    """Simple help modal"""
    
    def __init__(self, help_text: str):
        super().__init__()
        self.help_text = help_text
    
    def compose(self) -> ComposeResult:
        with Container(classes="modal"):
            yield Static("Help", classes="title")
            yield ScrollableContainer(Static(self.help_text))
            yield Button("Close", id="close_btn", variant="primary")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss()


def run_inspect_tui(bag_files: Optional[List[str]] = None) -> None:
    """Run the inspect TUI application"""
    app = InspectTUI(bag_files)
    app.run(inline=True)


if __name__ == "__main__":
    # For testing
    import sys
    bag_files = sys.argv[1:] if len(sys.argv) > 1 else None
    run_inspect_tui(bag_files)