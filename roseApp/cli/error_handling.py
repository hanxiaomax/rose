#!/usr/bin/env python3
"""
Friendly error handling module for CLI commands
Provides user-friendly error messages and suggestions
"""

import os
import sys
import typer
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from ..core.theme import theme

console = Console()

class FriendlyErrorHandler:
    """Provides friendly error messages and suggestions for common CLI errors"""
    
    @staticmethod
    def file_not_found(file_path: str, file_type: str = "file") -> None:
        """Handle file not found errors with suggestions"""
        console.print(f"\n[bold red]Error:[/bold red] {file_type.capitalize()} not found")
        console.print(f"[dim]Path:[/dim] {file_path}")
        
        # Check if it's a directory vs file issue
        if os.path.exists(file_path):
            if os.path.isdir(file_path) and file_type == "file":
                console.print(f"[yellow]Note:[/yellow] This is a directory, not a file")
            elif os.path.isfile(file_path) and file_type == "directory":
                console.print(f"[yellow]Note:[/yellow] This is a file, not a directory")
        else:
            # Check if parent directory exists
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                console.print(f"[yellow]Suggestion:[/yellow] Parent directory doesn't exist: {parent_dir}")
            else:
                # Look for similar files
                similar_files = FriendlyErrorHandler._find_similar_files(file_path)
                if similar_files:
                    console.print(f"[yellow]Did you mean one of these?[/yellow]")
                    for similar_file in similar_files[:5]:  # Show max 5 suggestions
                        console.print(f"  • {similar_file}")
        
        console.print()
        raise typer.Exit(code=1)
    
    @staticmethod
    def missing_required_option(option_name: str, command_name: str, suggestions: Optional[List[str]] = None) -> None:
        """Handle missing required options with helpful suggestions"""
        console.print(f"\n[bold red]Error:[/bold red] Missing required option: {option_name}")
        console.print(f"[dim]Command:[/dim] {command_name}")
        
        if suggestions:
            console.print(f"\n[yellow]Examples:[/yellow]")
            for suggestion in suggestions:
                console.print(f"  • {suggestion}")
        
        console.print(f"\n[dim]Use[/dim] [cyan]--help[/cyan] [dim]to see all available options[/dim]")
        console.print()
        raise typer.Exit(code=1)
    
    @staticmethod
    def invalid_option_value(option_name: str, value: str, valid_values: List[str], command_name: str) -> None:
        """Handle invalid option values with valid alternatives"""
        console.print(f"\n[bold red]Error:[/bold red] Invalid value for {option_name}: '{value}'")
        console.print(f"[dim]Command:[/dim] {command_name}")
        
        console.print(f"\n[yellow]Valid options:[/yellow]")
        for valid_value in valid_values:
            console.print(f"  • {valid_value}")
        
        # Find closest match
        closest_match = FriendlyErrorHandler._find_closest_match(value, valid_values)
        if closest_match:
            console.print(f"\n[yellow]Did you mean:[/yellow] {closest_match}")
        
        console.print()
        raise typer.Exit(code=1)
    
    @staticmethod
    def dependency_missing(dependency_name: str, install_command: str, feature_name: str) -> None:
        """Handle missing dependencies with installation instructions"""
        console.print(f"\n[bold red]Error:[/bold red] Missing required dependency: {dependency_name}")
        console.print(f"[dim]Required for:[/dim] {feature_name}")
        
        console.print(f"\n[yellow]To install:[/yellow]")
        console.print(f"  {install_command}")
        
        console.print(f"\n[dim]After installation, try running the command again[/dim]")
        console.print()
        raise typer.Exit(code=1)
    
    @staticmethod
    def show_command_help(command_name: str, examples: Optional[List[str]] = None) -> None:
        """Show helpful information about a command"""
        console.print(f"\n[bold cyan]Help for command:[/bold cyan] {command_name}")
        
        if examples:
            console.print(f"\n[yellow]Examples:[/yellow]")
            for example in examples:
                console.print(f"  {example}")
        
        console.print(f"\n[dim]For full help, use:[/dim] [cyan]rose {command_name} --help[/cyan]")
        console.print()
    
    @staticmethod
    def show_available_commands() -> None:
        """Show available commands when no command is specified"""
        console.print(f"\n[bold cyan]Available commands:[/bold cyan]")
        
        commands = [
            ("filter", "Filter ROS bag files by topics", "rose filter input.bag output/"),
            ("inspect", "Inspect ROS bag file contents", "rose inspect input.bag"),
            ("plot", "Plot data from ROS bag files", "rose plot input.bag --series /topic:field --output plot.png"),
            ("prune", "Remove unwanted topics from bag files", "rose prune input.bag --topics /unwanted"),
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
    
    @staticmethod
    def _find_similar_files(file_path: str) -> List[str]:
        """Find similar files in the same directory"""
        try:
            directory = os.path.dirname(file_path) or '.'
            filename = os.path.basename(file_path)
            
            if not os.path.exists(directory):
                return []
            
            files = []
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    # Check for similar extensions or names
                    if (item.endswith('.bag') or 
                        filename.lower() in item.lower() or 
                        item.lower() in filename.lower()):
                        files.append(item_path)
            
            return files[:5]  # Return max 5 suggestions
        except Exception:
            return []
    
    @staticmethod
    def _find_closest_match(value: str, valid_values: List[str]) -> Optional[str]:
        """Find the closest match using simple string similarity"""
        value_lower = value.lower()
        best_match = None
        best_score = 0
        
        for valid_value in valid_values:
            valid_lower = valid_value.lower()
            
            # Simple similarity scoring
            if valid_lower.startswith(value_lower):
                score = 0.9
            elif value_lower in valid_lower:
                score = 0.7
            elif valid_lower.startswith(value_lower[:2]):
                score = 0.5
            else:
                score = 0
            
            if score > best_score:
                best_score = score
                best_match = valid_value
        
        return best_match if best_score > 0.4 else None

# Common error patterns for specific commands
class CommandErrorHandlers:
    """Specific error handlers for each command"""
    
    @staticmethod
    def filter_command_errors(input_path: str, output_dir: Optional[str], 
                            whitelist: Optional[str], topics: Optional[List[str]],
                            compression: str, sort_by: str) -> None:
        """Handle filter command specific errors"""
        # Check input file
        if not os.path.exists(input_path):
            FriendlyErrorHandler.file_not_found(input_path, "bag file")
        
        if not os.path.isfile(input_path):
            if os.path.isdir(input_path):
                if output_dir is None:
                    FriendlyErrorHandler.missing_required_option(
                        "--output", "filter (directory processing)",
                        ["rose filter /path/to/bags/ /path/to/output/"]
                    )
            else:
                FriendlyErrorHandler.file_not_found(input_path, "bag file")
        
        # Check compression
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            FriendlyErrorHandler.invalid_option_value(
                "--compression", compression, valid_compression, "filter"
            )
        
        # Check sort_by
        valid_sort_options = ["topic", "count", "size"]
        if sort_by not in valid_sort_options:
            FriendlyErrorHandler.invalid_option_value(
                "--sort-by", sort_by, valid_sort_options, "filter"
            )
        
        # Check if both whitelist and topics are provided
        if whitelist and topics:
            console.print(f"\n[bold yellow]Warning:[/bold yellow] Both --whitelist and --topics specified")
            console.print(f"[dim]Using topics from --topics option, ignoring whitelist file[/dim]")
        
        # Check if neither whitelist nor topics are provided
        if not whitelist and not topics:
            console.print(f"\n[bold yellow]Note:[/bold yellow] No topic filter specified")
            console.print(f"[dim]All topics will be included in the output[/dim]")
    
    @staticmethod
    def inspect_command_errors(input_path: str, as_format: str, sort_by: str, 
                             output: Optional[str]) -> None:
        """Handle inspect command specific errors"""
        # Check input file
        if not os.path.exists(input_path):
            FriendlyErrorHandler.file_not_found(input_path, "bag file")
        
        if not os.path.isfile(input_path):
            FriendlyErrorHandler.file_not_found(input_path, "bag file")
        
        # Check format
        valid_formats = ["table", "list", "summary", "csv", "html"]
        if as_format not in valid_formats:
            FriendlyErrorHandler.invalid_option_value(
                "--as", as_format, valid_formats, "inspect"
            )
        
        # Check sort_by
        valid_sort_options = ["name", "type", "count", "size", "frequency"]
        if sort_by not in valid_sort_options:
            FriendlyErrorHandler.invalid_option_value(
                "--sort-by", sort_by, valid_sort_options, "inspect"
            )
        
        # Check output requirement for certain formats
        if as_format in ["csv", "html"] and not output:
            FriendlyErrorHandler.missing_required_option(
                "--output", f"inspect (--as={as_format})",
                [f"rose inspect input.bag --as {as_format} --output result.{as_format}"]
            )
    
    @staticmethod
    def plot_command_errors(bag_path: str, series: List[str], output: str,
                          plot_type: str, as_format: str) -> None:
        """Handle plot command specific errors"""
        # Check input file
        if not os.path.exists(bag_path):
            FriendlyErrorHandler.file_not_found(bag_path, "bag file")
        
        if not os.path.isfile(bag_path):
            FriendlyErrorHandler.file_not_found(bag_path, "bag file")
        
        # Check if series is provided
        if not series:
            FriendlyErrorHandler.missing_required_option(
                "--series", "plot",
                [
                    "rose plot input.bag --series /odom:pose.pose.position.x --output plot.png",
                    "rose plot input.bag --series /tf:transform.translation.x,transform.translation.y --output plot.png"
                ]
            )
        
        # Check output is provided
        if not output:
            FriendlyErrorHandler.missing_required_option(
                "--output", "plot",
                ["rose plot input.bag --series /topic:field --output plot.png"]
            )
        
        # Validate plot type
        valid_plot_types = ["line", "scatter"]
        if plot_type not in valid_plot_types:
            FriendlyErrorHandler.invalid_option_value(
                "--type", plot_type, valid_plot_types, "plot"
            )
        
        # Validate output format
        valid_formats = ["png", "svg", "pdf", "html"]
        if as_format not in valid_formats:
            FriendlyErrorHandler.invalid_option_value(
                "--as", as_format, valid_formats, "plot"
            )
        
        # Validate series format
        for i, s in enumerate(series):
            if ':' not in s:
                console.print(f"\n[bold red]Error:[/bold red] Invalid series format: '{s}'")
                console.print(f"[dim]Expected format:[/dim] topic:field1,field2")
                console.print(f"\n[yellow]Examples:[/yellow]")
                console.print(f"  • /odom:pose.pose.position.x")
                console.print(f"  • /tf:transform.translation.x,transform.translation.y")
                console.print()
                raise typer.Exit(code=1)
            
            topic, fields_str = s.split(':', 1)
            if not topic.startswith('/'):
                console.print(f"\n[bold red]Error:[/bold red] Topic must start with '/': '{topic}'")
                console.print(f"[dim]Correct format:[/dim] /{topic}:{fields_str}")
                console.print()
                raise typer.Exit(code=1) 