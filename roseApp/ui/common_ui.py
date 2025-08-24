"""
Common UI utilities and formatters for Rose CLI commands.
Provides shared display formatting, progress indicators, and message templates.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.text import Text
from rich.panel import Panel
from rich.table import Table

# Import simple theme system
from .theme import SimpleTheme, MessageStyle


@dataclass
class DisplayConfig:
    """Configuration for result display"""
    show_summary: bool = True
    show_details: bool = True
    show_cache_stats: bool = True
    show_performance: bool = True
    verbose: bool = False
    full_width: bool = True


@dataclass
class Message:
    """Base message class using unified theme system"""
    text: str
    message_type: str = "info"  # info, success, warning, error
    
    def render(self, console: Optional[Console] = None) -> None:
        """Render the message to console using theme system"""
        if console is None:
            console = Console()
        
        styled_text = MessageStyle.get_message(self.text, self.message_type)
        console.print(styled_text)

class SuccessMessage(Message):
    """Success message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "success")

class ErrorMessage(Message):
    """Error message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "error")

class WarningMessage(Message):
    """Warning message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "warning")

class InfoMessage(Message):
    """Info message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "info")

class TitleMessage(Message):
    """Title message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "title")

class PathMessage(Message):
    """Path message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "path")

class TopicMessage(Message):
    """Topic message using theme system"""
    def __init__(self, text: str):
        super().__init__(text, "topic")


class CommonUI:
    """Shared UI utilities for consistent display across CLI commands."""
    
    def __init__(self):
        self.console = Console()
    
    def show_success(self, message: str) -> None:
        """Display success message using theme system"""
        SuccessMessage(message).render(self.console)
    
    def show_error(self, message: str) -> None:
        """Display error message using theme system"""
        ErrorMessage(message).render(self.console)
    
    def show_warning(self, message: str) -> None:
        """Display warning message using theme system"""
        WarningMessage(message).render(self.console)
    
    def show_info(self, message: str) -> None:
        """Display info message using theme system"""
        InfoMessage(message).render(self.console)
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_mb = size_bytes / 1024 / 1024
        if size_mb >= 1.0:
            return f"{size_mb:.1f} MB"
        else:
            size_kb = size_bytes / 1024
            return f"{size_kb:.1f} KB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    @staticmethod
    def format_compression_ratio(original_size: int, compressed_size: int) -> str:
        """Calculate and format compression ratio."""
        if original_size == 0:
            return "0.0%"
        
        ratio = (1 - compressed_size / original_size) * 100
        return f"{ratio:.1f}%"
    
    def show_success(self, message: str) -> None:
        """Display success message."""
        Message(message, "success").render(self.console)
    
    def show_error(self, message: str) -> None:
        """Display error message."""
        Message(message, "error").render(self.console)
    
    def show_warning(self, message: str) -> None:
        """Display warning message."""
        Message(message, "warning").render(self.console)
    
    def show_info(self, message: str) -> None:
        """Display info message."""
        Message(message, "info").render(self.console)
    
    def create_progress_bar(self, description: str = "Processing...", total: int = 100) -> Progress:
        """Create a standard progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
    
    def display_file_list(self, files: List[Path], title: str = "Files") -> None:
        """Display a list of files with sizes."""
        if not files:
            self.show_info("No files found.")
            return
        
        self.show_info(f"{title} ({len(files)}):")
        for file in files:
            if file.exists():
                size = self.format_file_size(file.stat().st_size)
                self.console.print(f"  • {file} ({size})")
            else:
                self.console.print(f"  • {file} (not found)")
    
    def display_summary_table(self, data: Dict[str, Any], title: str = "Summary") -> None:
        """Display key-value data in a formatted table."""
        table = Table(title=title, show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in data.items():
            table.add_row(str(key), str(value))
        
        self.console.print(table)
    
    def display_topics_list(self, topics: List[str], message_types: Optional[Dict[str, str]] = None) -> None:
        """Display topics in a clean list format."""
        if not topics:
            self.show_info("No topics found.")
            return
        
        self.show_info(f"Topics ({len(topics)}):")
        for topic in sorted(topics):
            if message_types and topic in message_types:
                msg_type = Text(f" ({message_types[topic]})", style="dim")
                topic_text = Text(f"  • {topic}", style="bold cyan")
                topic_text.append(msg_type)
                self.console.print(topic_text)
            else:
                self.console.print(f"  • {topic}")
    
    def ask_confirmation(self, message: str, default: bool = False) -> bool:
        """Standard confirmation prompt."""
        from InquirerPy import inquirer
        return inquirer.confirm(
            message=message,
            default=default
        ).execute()
    
    def ask_file_path(self, message: str, must_exist: bool = True) -> Optional[str]:
        """Standard file path prompt."""
        from InquirerPy import inquirer
        from InquirerPy.validator import PathValidator
        
        validator = PathValidator(is_file=True, message="File does not exist") if must_exist else None
        
        return inquirer.filepath(
            message=message,
            validate=validator
        ).execute()


class ProgressUI:
    """Progress display utilities."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def create_task_progress(self, description: str, total: int = 100) -> tuple[Progress, Any]:
        """Create progress bar with task."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
        task = progress.add_task(description, total=total)
        return progress, task
    
    def show_processing_summary(self, total_files: int, workers: int, operation: str) -> None:
        """Display processing summary."""
        self.console.print(
            f"\nProcessing {total_files} file(s) with {workers} worker(s) ({operation})...",
            style="info"
        )
    
    def show_batch_results(self, success_count: int, fail_count: int, total_time: float) -> None:
        """Display batch processing results."""
        table = Table(title="Processing Summary")
        table.add_column("Status", style="bold")
        table.add_column("Count", justify="right")
        
        if success_count > 0:
            table.add_row("✓ Successful", str(success_count), style="green")
        if fail_count > 0:
            table.add_row("✗ Failed", str(fail_count), style="red")
        
        table.add_row("⏱ Total Time", f"{total_time:.2f}s", style="cyan")
        
        self.console.print(table)


class TableUI:
    """Table display utilities."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def create_topics_table(self, topics_data: List[Dict[str, Any]], verbose: bool = False) -> Table:
        """Create table for displaying topics."""
        table = Table(title="Topics")
        
        if verbose:
            table.add_column("Topic", style="cyan", no_wrap=True)
            table.add_column("Type", style="magenta")
            table.add_column("Messages", justify="right", style="green")
            table.add_column("Frequency", justify="right", style="blue")
            table.add_column("Size", justify="right", style="yellow")
        else:
            table.add_column("Topic", style="cyan")
            table.add_column("Type", style="magenta")
        
        for topic in topics_data:
            if verbose:
                table.add_row(
                    topic.get('name', ''),
                    topic.get('message_type', ''),
                    str(topic.get('message_count', 0)),
                    f"{topic.get('frequency', 0):.1f} Hz",
                    CommonUI.format_file_size(topic.get('size_bytes', 0))
                )
            else:
                table.add_row(
                    topic.get('name', ''),
                    topic.get('message_type', '')
                )
        
        return table
    
    def create_compression_summary_table(self, results: List[Dict[str, Any]]) -> Table:
        """Create table for compression results."""
        table = Table(title="Compression Results")
        table.add_column("File", style="cyan")
        table.add_column("Original", justify="right", style="red")
        table.add_column("Compressed", justify="right", style="green")
        table.add_column("Reduction", justify="right", style="blue")
        
        total_original = 0
        total_compressed = 0
        
        for result in results:
            if result.get('success'):
                original_size = Path(result['input_file']).stat().st_size
                compressed_size = Path(result['output_file']).stat().st_size
                
                table.add_row(
                    Path(result['input_file']).name,
                    CommonUI.format_file_size(original_size),
                    CommonUI.format_file_size(compressed_size),
                    CommonUI.format_compression_ratio(original_size, compressed_size)
                )
                
                total_original += original_size
                total_compressed += compressed_size
        
        if len(results) > 1:
            table.add_section()
            table.add_row(
                "TOTAL",
                CommonUI.format_file_size(total_original),
                CommonUI.format_file_size(total_compressed),
                CommonUI.format_compression_ratio(total_original, total_compressed)
            )
        
        return table