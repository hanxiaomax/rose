#!/usr/bin/env python3
"""
Simplified error handling for CLI commands
Relies on typer/click built-in error handling with minimal custom validation
"""

import os
import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich import box

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
        ("filter-bag", "Filter ROS bag files by topics", "rose filter-bag input.bag output/"),
        ("inspect", "Inspect ROS bag file contents", "rose inspect input.bag"),
        ("plot", "Plot data from ROS bag files", "rose plot input.bag --series /topic:field --output plot.png"),
        ("prune", "Manage analysis cache", "rose prune --clear"),
        ("cli", "Interactive CLI tool", "rose cli"),
        ("tui", "Text-based user interface", "rose tui")
    ]
    
    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Example", style="dim")
    
    for cmd, desc, example in commands:
        table.add_row(cmd, desc, example)
    
    console.print(table)
    console.print(f"\n[dim]Use[/dim] [cyan]rose <command> --help[/cyan] [dim]for detailed help on any command[/dim]")
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