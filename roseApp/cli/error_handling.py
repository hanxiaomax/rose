#!/usr/bin/env python3
"""
Simplified error handling for CLI commands
Relies on typer/click built-in error handling with minimal custom validation
"""

import os
import typer
import traceback
from typing import Optional, List, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text

from ..core.ui_control import UIControl
from ..core.theme_config import UnifiedThemeManager, ComponentType


console = Console()

class ValidationError(Exception):
    """Custom validation error for parameter values"""
    pass

def validate_file_exists(file_path: str, file_type: str = "file") -> None:
    """Validate that a file exists and is actually a file"""
    if not os.path.exists(file_path):
        raise ValidationError(f"{file_type.capitalize()} not found: {file_path}")
    
    if not os.path.isfile(file_path):
        if os.path.isdir(file_path):
            raise ValidationError(f"Expected a file, but '{file_path}' is a directory")
        else:
            raise ValidationError(f"'{file_path}' is not a valid file")

def validate_choice(value: str, valid_choices: List[str], option_name: str) -> None:
    """Validate that a value is in the list of valid choices"""
    if value not in valid_choices:
        choices_str = ", ".join(valid_choices)
        raise ValidationError(f"Invalid {option_name}: '{value}'. Valid choices: {choices_str}")

def validate_series_format(series: List[str]) -> None:
    """Validate series format for plot command"""
    for s in series:
        if ':' not in s:
            raise ValidationError(f"Invalid series format: '{s}'. Expected format: topic:field1,field2")
        
        topic, _ = s.split(':', 1)
        if not topic.startswith('/'):
            raise ValidationError(f"Topic must start with '/': '{topic}'. Example: /{topic}:field")

def validate_output_requirement(as_format: str, output: Optional[str]) -> None:
    """Validate that output is provided when required by format"""
    if as_format in ["csv", "html", "json"] and not output:
        raise ValidationError(f"--as={as_format} requires --output to be specified")

def show_available_commands() -> None:
    """Show available commands when no command is specified"""
    console.print(f"\n[bold cyan]Available commands:[/bold cyan]")
    
    commands = [
        ("load", "Load ROS bag files into cache", "rose load *.bag"),
        ("extract", "Extract topics from cached bags", "rose extract input.bag --topics gps"),
        ("inspect", "Inspect cached bag file contents", "rose inspect input.bag"),
        ("plot", "Plot data from ROS bag files", "rose plot input.bag --series /topic:field --output plot.png"),
        ("tools", "Cache management and diagnostics", "rose tools cache status"),
        ("cli", "Interactive CLI tool", "rose cli"),
        ("tui", "Text-based user interface", "rose tui")
    ]
    
    table = Table(show_header=True, header_style=UnifiedThemeManager.get_color(ComponentType.CLI, 'primary', 'bold'), box=box.ROUNDED)
    table.add_column("Command", style=UnifiedThemeManager.get_color(ComponentType.CLI, 'secondary'))
    table.add_column("Description", style=UnifiedThemeManager.get_color(ComponentType.CLI, 'foreground'))
    table.add_column("Example", style=UnifiedThemeManager.get_color(ComponentType.CLI, 'muted'))
    
    for cmd, desc, example in commands:
        table.add_row(cmd, desc, example)
    
    console.print(table)
    console.print(f"\n[{UnifiedThemeManager.get_color(ComponentType.CLI, 'muted', 'dim')}]Use[/{UnifiedThemeManager.get_color(ComponentType.CLI, 'muted', 'dim')}] [{UnifiedThemeManager.get_color(ComponentType.CLI, 'info')}]rose <command> --help[/{UnifiedThemeManager.get_color(ComponentType.CLI, 'info')}] [{UnifiedThemeManager.get_color(ComponentType.CLI, 'muted', 'dim')}]for detailed help on any command[/{UnifiedThemeManager.get_color(ComponentType.CLI, 'muted', 'dim')}]")
    console.print()

def handle_runtime_error(error: Exception, context: str = "") -> None:
    """Handle runtime errors with user-friendly messages"""
    error_msg = str(error)
    
    # Remove common path prefixes for cleaner error messages
    if "Error:" in error_msg:
        error_msg = error_msg.split("Error:", 1)[1].strip()
    
    console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
    if context:
        console.print(f"[dim]Context:[/dim] {context}")
    console.print()
    
    raise typer.Exit(code=1) 


def handle_error(e: Exception, context: str = "", console: Optional[Console] = None, show_traceback: bool = False) -> None:
    """
    Handle and display errors with context
    
    Args:
        e: The exception to handle
        context: Additional context about where the error occurred
        console: Rich console instance (optional)
        show_traceback: Whether to show full traceback
    """
    if console is None:
        console = UIControl.get_console()
    
    # Create error message
    error_msg = f"Error: {str(e)}"
    if context:
        error_msg = f"{context} - {error_msg}"
    
    # Display error using unified styling
    UIControl.show_error(error_msg, console)
    
    if show_traceback:
        console.print("\nTraceback:", style=UIControl.get_color('muted', 'bold'))
        console.print(traceback.format_exc(), style=UIControl.get_color('muted'))


def show_validation_errors(errors: List[str], console: Optional[Console] = None) -> None:
    """
    Display validation errors in a formatted table
    
    Args:
        errors: List of validation error messages
        console: Rich console instance (optional)
    """
    if console is None:
        console = UIControl.get_console()
    
    if not errors:
        return
    
    console.print(f"\n{len(errors)} validation error(s) found:", style=UIControl.get_color('error', 'bold'))
    
    for i, error in enumerate(errors, 1):
        console.print(f"  {i}. {error}", style=UIControl.get_color('error'))


def show_command_help(console: Optional[Console] = None) -> None:
    """
    Display helpful command suggestions
    
    Args:
        console: Rich console instance (optional)
    """
    if console is None:
        console = UIControl.get_console()
    
    # Create help table with unified colors
    table = Table(show_header=True, header_style=UIControl.get_color('primary', 'bold'), box=box.ROUNDED)
    table.add_column("Command", style=UIControl.get_color('secondary'))
    table.add_column("Description", style=UIControl.get_color('foreground'))
    table.add_column("Example", style=UIControl.get_color('muted'))
    
    # Add command examples
    commands = [
        ("rose extract", "Extract topics from bag files", "rose extract input.bag -t /camera/image"),
        ("rose inspect", "Inspect bag file contents", "rose inspect input.bag --show-fields"),
        ("rose plot", "Plot topic data", "rose plot input.bag -t /odom"),
        ("rose tui", "Launch interactive interface", "rose tui"),
    ]
    
    for cmd, desc, example in commands:
        table.add_row(cmd, desc, example)
    
    # Display with unified panel styling
    panel = Panel(
        table,
        title=Text("Available Commands", style=UIControl.get_color('accent', 'bold')),
        border_style=UIControl.get_color('border'),
        padding=(1, 2)
    )
    
    console.print(panel)


def show_recovery_suggestions(error_type: str, console: Optional[Console] = None) -> None:
    """
    Show recovery suggestions based on error type
    
    Args:
        error_type: Type of error encountered
        console: Rich console instance (optional)
    """
    if console is None:
        console = UIControl.get_console()
    
    suggestions = {
        "file_not_found": [
            "Check if the file path is correct",
            "Ensure the file exists and is readable",
            "Try using absolute path instead of relative path"
        ],
        "parsing_error": [
            "Verify the bag file is not corrupted",
            "Try using a different parser (rosbags vs rosbag)",
            "Check if the bag file format is supported"
        ],
        "permission_error": [
            "Check file permissions",
            "Run with appropriate user privileges",
            "Ensure output directory is writable"
        ],
        "memory_error": [
            "Try processing smaller chunks of data",
            "Close other applications to free memory",
            "Use streaming processing for large files"
        ]
    }
    
    if error_type in suggestions:
        console.print(f"\nSuggested solutions:", style=UIControl.get_color('info', 'bold'))
        for suggestion in suggestions[error_type]:
            console.print(f"  • {suggestion}", style=UIControl.get_color('info'))
    
    console.print(f"\nFor more help, run: rose --help", style=UIControl.get_color('accent')) 