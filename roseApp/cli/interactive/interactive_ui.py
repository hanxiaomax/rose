#!/usr/bin/env python3
"""
Interactive UI utilities for Rose interactive environment
Provides specialized message formatting and console utilities for interactive commands
"""

from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.tree import Tree
from pathlib import Path

from ...ui.theme import get_color
from ...ui.common_ui import Message as BaseMessage


class InteractiveMessage:
    """Enhanced message interface for interactive environment with console binding"""
    
    def __init__(self, console: Console):
        self.console = console
    
    def success(self, text: str, prefix: str = "SUCCESS") -> None:
        """Display success message with prefix"""
        self.console.print(f"[{get_color('success')}]{prefix}: {text}[/{get_color('success')}]")
    
    def error(self, text: str, prefix: str = "ERROR") -> None:
        """Display error message with prefix"""
        self.console.print(f"[{get_color('error')}]{prefix}: {text}[/{get_color('error')}]")
    
    def warning(self, text: str, prefix: str = "WARNING") -> None:
        """Display warning message with prefix"""
        self.console.print(f"[{get_color('warning')}]{prefix}: {text}[/{get_color('warning')}]")
    
    def info(self, text: str, prefix: str = "") -> None:
        """Display info message"""
        if prefix:
            self.console.print(f"[{get_color('info')}]{prefix}: {text}[/{get_color('info')}]")
        else:
            self.console.print(f"[{get_color('info')}]{text}[/{get_color('info')}]")
    
    def primary(self, text: str) -> None:
        """Display primary message"""
        self.console.print(f"[{get_color('primary')}]{text}[/{get_color('primary')}]")
    
    def accent(self, text: str) -> None:
        """Display accent message"""
        self.console.print(f"[{get_color('accent')}]{text}[/{get_color('accent')}]")
    
    def muted(self, text: str) -> None:
        """Display muted message"""
        self.console.print(f"[{get_color('muted')}]{text}[/{get_color('muted')}]")
    
    def operation_result(self, operation: str, success: bool, message: str = "", error: str = "") -> None:
        """Display operation result with consistent formatting"""
        if success:
            msg = message or f'{operation.title()} completed successfully'
            self.success(msg)
        else:
            err = error or 'Unknown error'
            self.error(f'{operation.title()} failed: {err}')
    
    def command_help(self, command: str, description: str) -> None:
        """Display command help in consistent format"""
        self.console.print(f"  [{get_color('accent')}]{command:<15}[/{get_color('accent')}] - {description}")
    
    def status_item(self, key: str, value: Any, style: str = "info") -> None:
        """Display status item with key-value formatting"""
        color = get_color(style)
        self.console.print(f"  [{get_color('muted')}]{key}:[/{get_color('muted')}] [{color}]{value}[/{color}]")
    
    def file_item(self, file_path: str, details: str = "") -> None:
        """Display file item with consistent formatting"""
        file_name = Path(file_path).name
        if details:
            self.console.print(f"  [{get_color('file')}]{file_name}[/{get_color('file')}] [{get_color('muted')}]({details})[/{get_color('muted')}]")
        else:
            self.console.print(f"  [{get_color('file')}]{file_name}[/{get_color('file')}]")
    
    def topic_item(self, topic: str, details: str = "") -> None:
        """Display topic item with consistent formatting"""
        if details:
            self.console.print(f"  [{get_color('accent')}]{topic}[/{get_color('accent')}] [{get_color('muted')}]({details})[/{get_color('muted')}]")
        else:
            self.console.print(f"  [{get_color('accent')}]{topic}[/{get_color('accent')}]")
    
    def section_header(self, title: str) -> None:
        """Display section header"""
        self.console.print(f"[bold {get_color('primary')}]{title}[/bold {get_color('primary')}]")
    
    def subsection_header(self, title: str) -> None:
        """Display subsection header"""
        self.console.print(f"[bold {get_color('info')}]{title}:[/bold {get_color('info')}]")
    
    def tip(self, text: str) -> None:
        """Display tip message"""
        self.console.print(f"[{get_color('muted')}]→ {text}[/{get_color('muted')}]")
    
    def shell_command(self, command: str) -> None:
        """Display shell command being executed"""
        self.console.print(f"[dim]$ {command}[/dim]")
    
    def task_status(self, task_id: str, command: str, elapsed: float) -> None:
        """Display task status"""
        self.console.print(f"  [{get_color('accent')}]{task_id}[/{get_color('accent')}]: {command} [{get_color('muted')}]({elapsed:.1f}s)[/{get_color('muted')}]")
    
    def progress_message(self, text: str, icon: str = "🔄") -> None:
        """Display progress message"""
        self.console.print(f"[{get_color('info')}]{icon} {text}[/{get_color('info')}]")
    
    def completion_message(self, text: str, icon: str = "✓") -> None:
        """Display completion message"""
        self.console.print(f"[{get_color('success')}]{icon} {text}[/{get_color('success')}]")


class InteractiveFormatter:
    """Specialized formatting utilities for interactive environment"""
    
    def __init__(self, console: Console):
        self.console = console
        self.msg = InteractiveMessage(console)
    
    def create_status_panel(self, title: str, items: Dict[str, Any]) -> Panel:
        """Create status panel with themed formatting"""
        content = Text()
        
        for key, value in items.items():
            key_display = key.replace('_', ' ').title()
            content.append(f"{key_display}: ", style=get_color('muted'))
            
            if isinstance(value, bool):
                style = get_color('success') if value else get_color('error')
                content.append(f"{'Yes' if value else 'No'}\n", style=style)
            elif isinstance(value, (int, float)):
                content.append(f"{value}\n", style=get_color('accent'))
            elif isinstance(value, list):
                content.append(f"{len(value)} items\n", style=get_color('info'))
            else:
                content.append(f"{value}\n", style=get_color('info'))
        
        return Panel(content, title=title, border_style=get_color('primary'))
    
    def create_command_list(self, commands: Dict[str, str], title: str = "Available Commands") -> Panel:
        """Create formatted command list panel"""
        content = Text()
        
        for cmd, desc in commands.items():
            content.append(f"{cmd:<15}", style=get_color('accent'))
            content.append(f" - {desc}\n", style=get_color('muted'))
        
        return Panel(content, title=title, border_style=get_color('primary'))
    
    def create_file_tree(self, files: List[str], title: str = "Files") -> Tree:
        """Create file tree with themed formatting"""
        tree = Tree(f"[bold {get_color('primary')}]{title}[/bold {get_color('primary')}]")
        
        for file_path in files:
            file_name = Path(file_path).name
            try:
                size = Path(file_path).stat().st_size
                size_str = self._format_size(size)
                tree.add(f"[{get_color('file')}]{file_name}[/{get_color('file')}] [{get_color('muted')}]({size_str})[/{get_color('muted')}]")
            except:
                tree.add(f"[{get_color('file')}]{file_name}[/{get_color('file')}]")
        
        return tree
    
    def create_topic_list(self, topics: List[str], title: str = "Topics") -> Tree:
        """Create topic list with themed formatting"""
        tree = Tree(f"[bold {get_color('primary')}]{title}[/bold {get_color('primary')}]")
        
        for i, topic in enumerate(topics, 1):
            tree.add(f"{i:2d}. [{get_color('accent')}]{topic}[/{get_color('accent')}]")
        
        return tree
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    def show_operation_summary(self, operation: str, success_count: int, total_count: int, elapsed_time: float = 0):
        """Show operation summary with consistent formatting"""
        self.msg.section_header(f"{operation.title()} Summary")
        
        if success_count > 0:
            self.console.print(f"  [{get_color('success')}]✓ Successful: {success_count}[/{get_color('success')}]")
        
        if total_count - success_count > 0:
            fail_count = total_count - success_count
            self.console.print(f"  [{get_color('error')}]✗ Failed: {fail_count}[/{get_color('error')}]")
        
        if elapsed_time > 0:
            self.console.print(f"  [{get_color('info')}]⏱ Total Time: {elapsed_time:.2f}s[/{get_color('info')}]")


class InteractiveUI:
    """Main interactive UI class combining message and formatting utilities"""
    
    def __init__(self, console: Console):
        self.console = console
        self.msg = InteractiveMessage(console)
        self.fmt = InteractiveFormatter(console)
    
    def clear(self) -> None:
        """Clear console"""
        self.console.clear()
    
    def print(self, text: str, style: str = "") -> None:
        """Print text with optional style"""
        if style:
            self.console.print(f"[{style}]{text}[/{style}]")
        else:
            self.console.print(text)
    
    def print_empty_line(self) -> None:
        """Print empty line"""
        self.console.print()
    
    def show_welcome(self, title: str, commands: Dict[str, str], features: List[str]):
        """Show welcome message with commands and features"""
        welcome_text = Text()
        welcome_text.append(f"{title}\n\n", style=f"bold {get_color('primary')}")
        
        # Commands
        welcome_text.append("Available commands:\n", style="bold")
        for cmd, desc in commands.items():
            welcome_text.append(f"{cmd:<12} - {desc}\n", style="dim")
        
        # Features
        welcome_text.append("\nFeatures:\n", style=get_color('success'))
        for feature in features:
            welcome_text.append(f"  • {feature}\n", style="dim")
        
        panel = Panel(welcome_text, title="Interactive Environment", border_style=get_color('primary'))
        self.console.print(panel)
    
    def show_help_hint(self, suggestions: List[str]):
        """Show help hint with suggestions"""
        if suggestions:
            self.msg.muted(f"Did you mean: {', '.join(suggestions)}?")
        self.msg.muted("Type '/help' for detailed documentation or '/help <command>' for specific help.")


# Convenience function to create UI instance
def create_interactive_ui(console: Console) -> InteractiveUI:
    """Create InteractiveUI instance"""
    return InteractiveUI(console)
