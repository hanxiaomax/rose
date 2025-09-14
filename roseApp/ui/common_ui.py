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

# Import theme system
from .theme import get_color


@dataclass
class DisplayConfig:
    """Configuration for result display"""
    show_summary: bool = True
    show_details: bool = True
    show_cache_stats: bool = True
    show_performance: bool = True
    verbose: bool = False
    full_width: bool = True


class Message:
    """Unified message interface with theme colors"""
    
    @staticmethod
    def _print_styled(text: str, color: str, console: Optional[Console] = None, bold: bool = False) -> None:
        """Print styled text using theme colors"""
        if console is None:
            console = Console()
        
        style = f"bold {color}" if bold else color
        console.print(f"[{style}]{text}[/{style}]")
    
    @staticmethod
    def success(text: str, console: Optional[Console] = None) -> None:
        """Display success message"""
        Message._print_styled(text, get_color('success'), console)
    
    @staticmethod
    def error(text: str, console: Optional[Console] = None) -> None:
        """Display error message"""
        Message._print_styled(text, get_color('error'), console)
    
    @staticmethod
    def warning(text: str, console: Optional[Console] = None) -> None:
        """Display warning message"""
        Message._print_styled(text, get_color('warning'), console)
    
    @staticmethod
    def info(text: str, console: Optional[Console] = None) -> None:
        """Display info message"""
        Message._print_styled(text, get_color('info'), console)
    
    @staticmethod
    def primary(text: str, console: Optional[Console] = None) -> None:
        """Display primary message"""
        Message._print_styled(text, get_color('primary'), console)
    
    @staticmethod
    def accent(text: str, console: Optional[Console] = None) -> None:
        """Display accent message"""
        Message._print_styled(text, get_color('accent'), console)
    
    @staticmethod
    def claude(text: str, console: Optional[Console] = None) -> None:
        """Display Claude signature message"""
        Message._print_styled(text, get_color('claude'), console, bold=True)
    
    @staticmethod
    def muted(text: str, console: Optional[Console] = None) -> None:
        """Display muted message"""
        Message._print_styled(text, get_color('muted'), console)



class CommonUI:
    """Shared UI utilities for consistent display across CLI commands."""
    
    def __init__(self):
        self.console = Console()
    
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
    

    
    def create_progress_bar(self, description: str = "Processing...", total: int = 100) -> Progress:
        """Create a standard progress bar with theme colors."""
        return Progress(
            SpinnerColumn(),
            TextColumn(f"[{get_color('primary')}][progress.description]{{task.description}}[/{get_color('primary')}]"),
            BarColumn(complete_style=get_color('success'), finished_style=get_color('success')),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
    
    def display_file_list(self, files: List[Path], title: str = "Files") -> None:
        """Display a list of files with sizes."""
        if not files:
            Message.info("No files found.", self.console)
            return
        
        Message.info(f"{title} ({len(files)}):", self.console)
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
            Message.info("No topics found.", self.console)
            return
        
        Message.info(f"Topics ({len(topics)}):", self.console)
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
        self.console.print("\n[bold]Processing Summary:[/bold]")
        
        if success_count > 0:
            self.console.print(f"  • [green]✓ Successful: {success_count}[/green]")
        if fail_count > 0:
            self.console.print(f"  • [red]✗ Failed: {fail_count}[/red]")
        
        self.console.print(f"  • [cyan]⏱ Total Time: {total_time:.2f}s[/cyan]")


class TableUI:
    """Table display utilities."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def create_topics_list(self, topics_data: List[Dict[str, Any]], verbose: bool = False) -> None:
        """Display topics as a list."""
        if not topics_data:
            return
            
        self.console.print("\n[bold]Topics:[/bold]")
        
        for i, topic in enumerate(topics_data, 1):
            name = topic.get('name', '')
            msg_type = topic.get('message_type', '')
            
            if verbose:
                messages = topic.get('message_count', 0)
                frequency = topic.get('frequency', 0)
                size = CommonUI.format_file_size(topic.get('size_bytes', 0))
                self.console.print(
                    f"  {i:2d}. [cyan]{name}[/cyan] "
                    f"([magenta]{msg_type}[/magenta]) "
                    f"- [green]{messages} messages[/green] "
                    f"@ [blue]{frequency:.1f} Hz[/blue] "
                    f"([yellow]{size}[/yellow])"
                )
            else:
                self.console.print(
                    f"  {i:2d}. [cyan]{name}[/cyan] "
                    f"([magenta]{msg_type}[/magenta])"
                )
    
    def display_compression_summary_list(self, results: List[Dict[str, Any]]) -> None:
        """Display compression results as a list."""
        if not results:
            return
            
        self.console.print("\n[bold]Compression Results:[/bold]")
        
        total_original = 0
        total_compressed = 0
        
        for i, result in enumerate(results, 1):
            if result.get('success'):
                original_size = Path(result['input_file']).stat().st_size
                compressed_size = Path(result['output_file']).stat().st_size
                
                filename = Path(result['input_file']).name
                original_str = CommonUI.format_file_size(original_size)
                compressed_str = CommonUI.format_file_size(compressed_size)
                reduction = CommonUI.format_compression_ratio(original_size, compressed_size)
                
                self.console.print(
                    f"  {i:2d}. [cyan]{filename}[/cyan]: "
                    f"[red]{original_str}[/red] → [green]{compressed_str}[/green] "
                    f"([blue]{reduction}[/blue])"
                )
                
                total_original += original_size
                total_compressed += compressed_size
        
        if len(results) > 1:
            total_original_str = CommonUI.format_file_size(total_original)
            total_compressed_str = CommonUI.format_file_size(total_compressed)
            total_reduction = CommonUI.format_compression_ratio(total_original, total_compressed)
            
            self.console.print(
                f"\n  [bold]TOTAL:[/bold] "
                f"[red]{total_original_str}[/red] → [green]{total_compressed_str}[/green] "
                f"([blue]{total_reduction}[/blue])"
            )