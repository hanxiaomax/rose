"""
UI components for the interactive CLI.
Handles display formatting for menu-driven CLI interface.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from .common_ui import Message
from .common_ui import CommonUI, ProgressUI, TableUI


class CliUI:
    """UI components specifically for the interactive CLI."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
        self.progress_ui = ProgressUI()
        self.table_ui = TableUI()
    
    def display_banner(self) -> None:
        """Display CLI banner."""
        from roseApp.cli.util import build_banner
        self.console.print(build_banner())
    
    def display_main_menu(self) -> str:
        """Display main menu and return selected action."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        action = inquirer.select(
            message="Select action:",
            choices=[
                Choice(value="filter", name="1. Bag Editor - View and filter bag files"),
                Choice(value="wizard", name="2. Extraction Wizard - Generate extract commands"),
                Choice(value="whitelist", name="3. Whitelist - Manage topic whitelists"),
                Choice(value="exit", name="4. Exit")
            ]
        ).execute()
        
        return action
    
    def ask_for_bag_file(self, message: str = "Enter bag file path:") -> Optional[str]:
        """Ask user to input a bag file path."""
        from InquirerPy import inquirer
        from InquirerPy.validator import PathValidator
        
        while True:
            input_bag = inquirer.filepath(
                message=message,
                validate=PathValidator(is_file=True, message="File does not exist"),
                filter=lambda x: x if x.endswith('.bag') else None,
                invalid_message="File must be a .bag file"
            ).execute()
            
            if input_bag is None:  # User cancelled
                return None
                
            return input_bag
    
    def ask_for_output_bag(self, default_path: str) -> Tuple[Optional[str], bool]:
        """Ask user for output bag file path with overwrite handling."""
        from InquirerPy import inquirer
        
        while True:
            output_bag = inquirer.filepath(
                message="Enter output bag file path:",
                default=default_path,
                validate=lambda x: x.endswith('.bag') or "File must be a .bag file"
            ).execute()
            
            if not output_bag:  # User cancelled
                return None, False
            
            # Check if file already exists
            if os.path.exists(output_bag):
                overwrite = inquirer.confirm(
                    message=f"Output file '{output_bag}' already exists. Do you want to overwrite it?",
                    default=False
                ).execute()
                
                if overwrite:
                    return output_bag, True
                else:
                    self.console.print("Please choose a different filename.", style="warning")
                    continue
            else:
                return output_bag, False
    
    def ask_filter_method(self) -> str:
        """Ask user to select filter method."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        return inquirer.select(
            message="Select filter method:",
            choices=[
                Choice(value="whitelist", name="1. Use whitelist"),
                Choice(value="manual", name="2. Select topics manually"),
                Choice(value="back", name="3. Back")
            ]
        ).execute()
    
    def display_bag_info(self, bag_path: str, topics: List[str], connections: Dict[str, str], 
                        time_range: Tuple, parser=None) -> None:
        """Display bag file information."""
        from roseApp.cli.util import print_bag_info
        console = self.console
        print_bag_info(console, bag_path, topics, connections, time_range, parser=parser)
    
    def ask_topics_selection(self, topics: List[str], parser=None, bag_path: str = None) -> List[str]:
        """Ask user to select topics."""
        from roseApp.cli.util import ask_topics
        return ask_topics(self.console, topics, parser=parser, bag_path=bag_path)
    
    def ask_compression_type(self, available_compressions: List[str]) -> str:
        """Ask user to select compression type."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        choices = []
        if "none" in available_compressions:
            choices.append(Choice(value="none", name="1. No compression (fastest, largest file)"))
        if "bz2" in available_compressions:
            choices.append(Choice(value="bz2", name="2. BZ2 compression (slower, smallest file)"))
        if "lz4" in available_compressions:
            choices.append(Choice(value="lz4", name="3. LZ4 compression (balanced speed/size)"))
        
        return inquirer.select(
            message="Choose compression type:",
            choices=choices,
            default="none"
        ).execute()
    
    def ask_directory_path(self, message: str = "Enter directory path:") -> Optional[str]:
        """Ask user for directory path."""
        from InquirerPy import inquirer
        from InquirerPy.validator import PathValidator
        
        return inquirer.filepath(
            message=message,
            validate=PathValidator(is_file=False, message="Directory does not exist")
        ).execute()
    
    def display_file_selection(self, bag_files: List[Path], base_path: str) -> List[str]:
        """Display file selection for multiple bag files."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        # Create file selection choices
        file_choices = [
            Choice(
                value=str(f),
                name=f"{os.path.relpath(f, base_path)} ({os.path.getsize(f)/1024/1024:.1f} MB)"
            ) for f in bag_files
        ]
        
        def bag_list_transformer(result):
            return f"{len(result)} files selected\n" + '\n'.join([f"• {os.path.basename(bag)}" for bag in result])
        
        selected_files = inquirer.checkbox(
            message="Select bag files to process:",
            choices=file_choices,
            instruction="",
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one file",
            transformer=bag_list_transformer
        ).execute()
        
        return selected_files
    
    def confirm_operation(self, message: str) -> bool:
        """Confirm operation with user."""
        from InquirerPy import inquirer
        return inquirer.confirm(message=message, default=False).execute()
    
    def display_progress_bar(self, description: str, total: int = 100) -> object:
        """Create and display progress bar."""
        return self.common_ui.create_progress_bar(description, total)
    
    def display_loading_animation(self, message: str, dismiss: bool = True) -> object:
        """Display loading animation."""
        from roseApp.cli.util import LoadingAnimation
        return LoadingAnimation(message, dismiss=dismiss)
    
    def display_whitelist_menu(self) -> str:
        """Display whitelist management menu."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        return inquirer.select(
            message="Whitelist Management:",
            choices=[
                Choice(value="create", name="1. Create new whitelist"),
                Choice(value="view", name="2. View whitelist"),
                Choice(value="delete", name="3. Delete whitelist"),
                Choice(value="back", name="4. Back")
            ]
        ).execute()
    
    def ask_whitelist_selection(self, whitelists: List[str]) -> Optional[str]:
        """Ask user to select a whitelist."""
        from InquirerPy import inquirer
        
        if not whitelists:
            Message.warning("No whitelists found", self.console)
            return None
            
        return inquirer.select(
            message="Select whitelist to use:",
            choices=whitelists
        ).execute()
    
    def display_whitelist_contents(self, name: str, content: str) -> None:
        """Display whitelist contents."""
        self.console.print(f"\n[bold cyan]Whitelist: {name}[/bold cyan]")
        self.console.print("─" * 80)
        self.console.print(content)
    
    def ask_whitelist_name(self, default_name: str) -> str:
        """Ask user for whitelist name."""
        from InquirerPy import inquirer
        
        use_default = inquirer.confirm(
            message=f"Use default name? ({default_name})",
            default=True
        ).execute()
        
        if use_default:
            return default_name
        else:
            name = inquirer.text(
                message="Enter whitelist name (without .txt extension):",
                default="my_whitelist",
                validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty"
            ).execute()
            
            if not name.endswith('.txt'):
                name += '.txt'
            return name
    
    def display_wizard_menu(self) -> str:
        """Display extract wizard menu."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        return inquirer.select(
            message="Extract Wizard:",
            choices=[
                Choice(value="create", name="1. Create new extract command"),
                Choice(value="view", name="2. View saved commands"),
                Choice(value="run", name="3. Run saved command"),
                Choice(value="delete", name="4. Delete saved command"),
                Choice(value="back", name="5. Back")
            ]
        ).execute()
    
    def ask_extract_command_name(self, default_name: str) -> str:
        """Ask for extract command name."""
        from InquirerPy import inquirer
        
        return inquirer.text(
            message="Enter command name:",
            default=default_name,
            validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty"
        ).execute()
    
    def ask_output_pattern(self, default: str = "{input}_extracted.bag") -> str:
        """Ask for output file pattern."""
        from InquirerPy import inquirer
        
        return inquirer.text(
            message="Enter output file pattern (use {input} for input filename):",
            default=default,
            validate=lambda x: len(x.strip()) > 0 or "Pattern cannot be empty"
        ).execute()
    
    def ask_topic_mode(self) -> str:
        """Ask for topic selection mode."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        return inquirer.select(
            message="Topic selection mode:",
            choices=[
                Choice(value="include", name="Include selected topics (default)"),
                Choice(value="exclude", name="Exclude selected topics (use --reverse)")
            ],
            default="include"
        ).execute()
    
    def ask_time_range(self, start_time: float, end_time: float) -> Tuple[Optional[float], Optional[float]]:
        """Ask for time range selection."""
        from InquirerPy import inquirer
        
        use_time_range = inquirer.confirm(
            message="Do you want to specify a time range?",
            default=False
        ).execute()
        
        if not use_time_range:
            return None, None
            
        self.console.print(f"Bag time range: {start_time:.3f} - {end_time:.3f} seconds")
        
        start = inquirer.text(
            message=f"Enter start time (seconds, default: {start_time:.3f}):",
            default=str(start_time),
            validate=lambda x: self._validate_float(x, start_time, end_time),
            filter=lambda x: float(x) if x else start_time
        ).execute()
        
        end = inquirer.text(
            message=f"Enter end time (seconds, default: {end_time:.3f}):",
            default=str(end_time),
            validate=lambda x: self._validate_float(x, start, end_time),
            filter=lambda x: float(x) if x else end_time
        ).execute()
        
        return start, end
    
    def _validate_float(self, value_str: str, min_val: float, max_val: float) -> bool:
        """Validate float in range."""
        try:
            value = float(value_str)
            return min_val <= value <= max_val
        except (ValueError, TypeError):
            return False
    
    def display_extract_commands(self, commands: List[Dict[str, Any]]) -> Optional[int]:
        """Display extract commands for selection."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        if not commands:
            Message.warning("No saved extract commands found", self.console)
            return None
        
        choices = [
            Choice(value=i, name=f"{cmd['name']} - {cmd['description']} ({cmd['created']})")
            for i, cmd in enumerate(commands)
        ]
        
        return inquirer.select(
            message="Select command:",
            choices=choices
        ).execute()
    
    def display_error(self, message: str) -> None:
        """Display error message."""
        Message.error(message, self.console)
    
    def display_success(self, message: str) -> None:
        """Display success message."""
        Message.success(message, self.console)
    
    def display_info(self, message: str) -> None:
        """Display info message."""
        Message.info(message, self.console)
    
    def display_warning(self, message: str) -> None:
        """Display warning message."""
        Message.warning(message, self.console)
    
    def display_usage_instructions(self) -> None:
        """Display usage instructions."""
        from roseApp.cli.util import print_usage_instructions
        print_usage_instructions(self.console)