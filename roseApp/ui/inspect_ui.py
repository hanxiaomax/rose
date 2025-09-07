"""
UI components for the inspect command.
Handles display formatting for bag file inspection results.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from .common_ui import Message
from .common_ui import CommonUI
from .theme import get_color


class InspectUI:
    """UI components specifically for the inspect command."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
    
    def display_simple_list(self, result: Dict[str, Any], verbose: bool = False) -> None:
        """Display topics in simple list format (non-verbose mode)."""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        # Show summary
        self.console.print(f"\nFile: {bag_info.get('file_path', 'Unknown')}")
        self.console.print(f"Topics: {len(topics)}")
        self.console.print(f"File Size: {bag_info.get('file_size_mb', 0):.1f} MB")
        self.console.print(f"Duration: {bag_info.get('duration_seconds', 0):.1f}s")
        
        # List topics
        self.console.print(f"\nTopics:")
        for topic in topics:
            topic_line = Text()
            topic_line.append(f"  • {topic['name']}", style=f"bold {get_color('primary')}")
            topic_line.append(f" ({topic['message_type']})", style="dim")
            self.console.print(topic_line)
    
    def display_inspection_result(self, result: Dict[str, Any], display_config: Dict[str, Any]) -> None:
        """Display comprehensive inspection results."""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        # Display file summary
        self.display_file_summary(bag_info)
        
        # Display topics based on verbosity
        if display_config.get('verbose', False):
            self.display_verbose_topics(topics)
        else:
            self.display_simple_topics(topics)
    
    def display_file_summary(self, bag_info: Dict[str, Any]) -> None:
        """Display file summary information."""
        summary_data = {
            "File": bag_info.get('file_name', 'Unknown'),
            "Path": bag_info.get('file_path', 'Unknown'),
            "File Size": f"{bag_info.get('file_size_mb', 0):.1f} MB",
            "Topics": bag_info.get('topics_count', 0),
            "Total Messages": bag_info.get('total_messages', 0),
            "Duration": f"{bag_info.get('duration_seconds', 0):.1f}s",
            "Cached": "Yes" if bag_info.get('cached', False) else "No"
        }
        
        self.common_ui.display_summary_table(summary_data, "File Summary")
    
    def display_verbose_topics(self, topics: List[Dict[str, Any]]) -> None:
        """Display topics with detailed information."""
        if not topics:
            Message.info("No topics found.", self.console)
            return
        
        self.console.print("\n[bold]Topics:[/bold]")
        
        for i, topic in enumerate(topics, 1):
            name = topic.get('name', '')
            msg_type = topic.get('message_type', '')
            messages = topic.get('message_count', 0)
            frequency = f"{topic.get('frequency', 0):.1f} Hz" if 'frequency' in topic else "-"
            size = self.common_ui.format_file_size(topic.get('size_bytes', 0))
            
            self.console.print(
                f"  {i:2d}. [{get_color('primary')}]{name}[/{get_color('primary')}] "
                f"([{get_color('accent')}]{msg_type}[/{get_color('accent')}]) "
                f"- [{get_color('success')}]{messages} messages[/{get_color('success')}] "
                f"@ [{get_color('info')}]{frequency}[/{get_color('info')}] "
                f"([{get_color('warning')}]{size}[/{get_color('warning')}])"
            )
    
    def display_simple_topics(self, topics: List[Dict[str, Any]]) -> None:
        """Display topics in simple format."""
        if not topics:
            Message.info("No topics found.", self.console)
            return
        
        Message.info(f"Topics ({len(topics)}):")
        for topic in topics:
            topic_line = Text()
            topic_line.append(f"  • {topic['name']}", style="bold cyan")
            topic_line.append(f" ({topic['message_type']})", style="dim")
            self.console.print(topic_line)
    
    def display_field_analysis(self, field_analysis: Dict[str, Any], topics: List[Dict[str, Any]]) -> None:
        """Display field analysis for message types."""
        if not field_analysis and not any('field_paths' in topic for topic in topics):
            return
        
        # Display field analysis per topic
        for topic in topics:
            if 'field_paths' in topic:
                self.console.print(f"\n[bold cyan]{topic['name']}[/bold cyan] ({topic['message_type']}):")
                for field_path in sorted(topic['field_paths']):
                    self.console.print(f"  • {field_path}")
        
        # Display field analysis from field_analysis dict
        if field_analysis:
            for topic_name, analysis in field_analysis.items():
                self.console.print(f"\n[bold cyan]{topic_name}[/bold cyan] ({analysis['message_type']}):")
                for field_path in sorted(analysis['field_paths']):
                    self.console.print(f"  • {field_path}")
    
    def display_export_success(self, output_file: Optional[Path]) -> None:
        """Display export success message."""
        if output_file:
            Message.success(f"Export saved to: {output_file}", self.console)
    
    def display_export_failed(self) -> None:
        """Display export failure message."""
        Message.error("Failed to export results", self.console)
    
    def display_cache_status(self, cached: bool, file_path: str) -> None:
        """Display cache status information."""
        if cached:
            Message.info(f"Loaded from cache: {file_path}", self.console)
        else:
            Message.info(f"Loaded fresh: {file_path}", self.console)
    
    def display_loading_message(self, file_path: str) -> None:
        """Display loading message."""
        Message.info(f"Loading bag file: {file_path}", self.console)
    
    def display_filtering_topics(self, filtered_topics: List[str], original_count: int) -> None:
        """Display topic filtering results."""
        Message.info(
            f"Filtered to {len(filtered_topics)} topics from {original_count} total"
        )