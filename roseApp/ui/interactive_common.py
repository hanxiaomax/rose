#!/usr/bin/env python3
"""
Common interactive UI components for Rose commands
Provides reusable interactive elements for bag selection, topic selection, etc.
"""

import os
import time
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import PathValidator
from rich.console import Console

from .common_ui import Message
from .theme import get_color
from ..core.directories import get_rose_directories
from ..core.util import get_logger

logger = get_logger("InteractiveUI")


class InteractiveCommon:
    """Common interactive UI components for Rose commands"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.rose_dirs = get_rose_directories()
    
    def ask_for_bag_file(self, message: str = "Enter bag file path:") -> Optional[str]:
        """
        Ask user to input a bag file path
        
        Args:
            message: Custom message to display
            
        Returns:
            Selected bag file path or None if cancelled
        """
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
    
    def ask_for_bag_files_from_directory(self, directory_path: str) -> Optional[List[str]]:
        """
        Ask user to select multiple bag files from a directory
        
        Args:
            directory_path: Path to directory containing bag files
            
        Returns:
            List of selected bag files or None if cancelled
        """
        from ..cli.util import collect_bag_files
        
        # Find bag files
        bag_files = collect_bag_files(directory_path)
        if not bag_files:
            Message.error("No bag files found in directory", self.console)
            return None
            
        # Create file selection choices
        file_choices = [
            Choice(
                value=f,
                name=f"{os.path.relpath(f, directory_path)} ({os.path.getsize(f)/1024/1024:.1f} MB)"
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
        
        return selected_files if selected_files else None
    
    def ask_for_output_bag(self, default_path: str) -> Tuple[Optional[str], bool]:
        """
        Ask user to input output bag file path with overwrite handling
        
        Args:
            default_path: Default file path to suggest
            
        Returns:
            Tuple of (output_path, should_overwrite) or (None, False) if cancelled
        """
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
                # Ask user if they want to overwrite
                overwrite = inquirer.confirm(
                    message=f"Output file '{output_bag}' already exists. Do you want to overwrite it?",
                    default=False
                ).execute()
                
                if overwrite:
                    return output_bag, True  # File path and overwrite=True
                else:
                    # User doesn't want to overwrite, ask for different filename
                    Message.warning("Please choose a different filename.", self.console)
                    continue  # Go back to filename input
            else:
                # File doesn't exist, no need to overwrite
                return output_bag, False
    
    def ask_for_compression_type(self, message: str = "Choose compression type:") -> Optional[str]:
        """
        Ask user to select compression type
        
        Args:
            message: Custom message to display
            
        Returns:
            Selected compression type or None if cancelled
        """
        from ..core.util import get_available_compression_types
        available_compressions = get_available_compression_types()
        
        # Create compression choice list based on availability
        compression_choices = []
        if "none" in available_compressions:
            compression_choices.append(Choice(value="none", name="No compression (fastest, largest file)"))
        if "bz2" in available_compressions:
            compression_choices.append(Choice(value="bz2", name="BZ2 compression (slower, smallest file)"))
        if "lz4" in available_compressions:
            compression_choices.append(Choice(value="lz4", name="LZ4 compression (balanced speed/size)"))
        
        compression = inquirer.select(
            message=message,
            choices=compression_choices,
            default="none"
        ).execute()
        
        return compression
    
    def ask_for_topics_from_whitelist(self) -> Optional[List[str]]:
        """
        Ask user to select topics from a whitelist file
        
        Returns:
            List of topics from selected whitelist or None if cancelled
        """
        whitelists = self.rose_dirs.list_whitelists()
        if not whitelists:
            Message.warning("No whitelists found", self.console)
            return None
            
        # Select whitelist to use
        selected = inquirer.select(
            message="Select whitelist to use:",
            choices=whitelists
        ).execute()
        
        if not selected:
            return None
            
        # Load selected whitelist
        whitelist_path = self.rose_dirs.get_whitelist_file(selected)
        return self._load_whitelist_from_file(whitelist_path)
    
    def ask_for_filter_method(self) -> Optional[str]:
        """
        Ask user to select a filter method
        
        Returns:
            The selected filter method ('whitelist', 'manual', or None if cancelled)
        """
        return inquirer.select(
            message="Select filter method:",
            choices=[
                Choice(value="whitelist", name="Use whitelist"),
                Choice(value="manual", name="Select topics manually"),
            ]
        ).execute()
    
    def ask_for_topics_manual_selection(self, available_topics: List[str], 
                                      bag_path: Optional[str] = None) -> Optional[List[str]]:
        """
        Ask user to manually select topics from a list
        
        Args:
            available_topics: List of available topics
            bag_path: Optional bag file path for context
            
        Returns:
            List of selected topics or None if cancelled
        """
        from ..cli.util import ask_topics
        from ..core.parser import create_parser
        
        parser = create_parser()
        return ask_topics(self.console, available_topics, parser=parser, bag_path=bag_path)
    
    def ask_for_time_range(self, time_range: Any) -> Tuple[Optional[float], Optional[float]]:
        """
        Ask user to specify a time range
        
        Args:
            time_range: Time range object from bag analysis
            
        Returns:
            Tuple of (start_time, end_time) in seconds or (None, None) if not specified
        """
        use_time_range = inquirer.confirm(
            message="Do you want to specify a time range?",
            default=False
        ).execute()
        
        if not use_time_range or not time_range:
            return None, None
        
        # Convert time range to seconds for easier input
        if hasattr(time_range, 'get_start_ns'):
            start_sec = time_range.get_start_ns() / 1_000_000_000
            end_sec = time_range.get_end_ns() / 1_000_000_000
        else:
            start_sec = time_range.start_time[0] + time_range.start_time[1] / 1_000_000_000
            end_sec = time_range.end_time[0] + time_range.end_time[1] / 1_000_000_000
        
        self.console.print(f"Bag time range: {start_sec:.3f} - {end_sec:.3f} seconds")
        
        start_time = inquirer.text(
            message=f"Enter start time (seconds, default: {start_sec:.3f}):",
            default=str(start_sec),
            validate=lambda x: self._validate_float_in_range(x, start_sec, end_sec) or 
                              f"Must be a number between {start_sec:.3f} and {end_sec:.3f}",
            filter=lambda x: float(x) if x else start_sec
        ).execute()
        
        if start_time is None:
            return None, None
        
        end_time = inquirer.text(
            message=f"Enter end time (seconds, default: {end_sec:.3f}):",
            default=str(end_sec),
            validate=lambda x: self._validate_float_in_range(x, start_time, end_sec) or 
                              f"Must be a number between {start_time:.3f} and {end_sec:.3f}",
            filter=lambda x: float(x) if x else end_sec
        ).execute()
        
        return start_time, end_time
    
    def ask_for_workers_count(self, max_workers: Optional[int] = None) -> Optional[int]:
        """
        Ask user to specify number of workers
        
        Args:
            max_workers: Maximum number of workers allowed
            
        Returns:
            Number of workers or None if using default
        """
        if max_workers is None:
            max_workers = os.cpu_count() or 4
        
        use_custom_workers = inquirer.confirm(
            message="Do you want to specify number of workers?",
            default=False
        ).execute()
        
        if not use_custom_workers:
            return None
        
        workers = inquirer.text(
            message=f"Enter number of workers (1-{max_workers}):",
            default=str(max_workers // 2),
            validate=lambda x: (x.isdigit() and 1 <= int(x) <= max_workers) or 
                              f"Must be a number between 1 and {max_workers}",
            filter=lambda x: int(x) if x.isdigit() else None
        ).execute()
        
        return workers
    
    def ask_for_output_format(self, available_formats: List[str], 
                            default: str = "csv") -> Optional[str]:
        """
        Ask user to select output format
        
        Args:
            available_formats: List of available format options
            default: Default format selection
            
        Returns:
            Selected format or None if cancelled
        """
        format_choices = [
            Choice(value=fmt, name=fmt.upper()) for fmt in available_formats
        ]
        
        return inquirer.select(
            message="Select output format:",
            choices=format_choices,
            default=default
        ).execute()
    
    def confirm_operation(self, message: str, default: bool = True) -> bool:
        """
        Ask user to confirm an operation
        
        Args:
            message: Confirmation message
            default: Default choice
            
        Returns:
            True if confirmed, False otherwise
        """
        return inquirer.confirm(
            message=message,
            default=default
        ).execute()
    
    def _validate_float_in_range(self, value_str: str, min_val: float, max_val: float) -> bool:
        """Validate that a string represents a float within the given range"""
        try:
            value = float(value_str)
            return min_val <= value <= max_val
        except (ValueError, TypeError):
            return False
    
    def _load_whitelist_from_file(self, whitelist_path: str) -> List[str]:
        """
        Load whitelist from file
        
        Args:
            whitelist_path: Path to whitelist file
            
        Returns:
            List of topics from whitelist
        """
        try:
            with open(whitelist_path, 'r') as f:
                lines = f.readlines()
            
            # Filter out comments and empty lines
            topics = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    topics.append(line)
            
            return topics
        except Exception as e:
            logger.error(f"Error loading whitelist {whitelist_path}: {str(e)}")
            Message.error(f"Error loading whitelist: {str(e)}", self.console)
            return []


class BagLoader:
    """Common bag loading functionality for interactive commands"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        from ..core.parser import create_parser
        from ..core.cache import create_bag_cache_manager
        self.parser = create_parser()
        self.cache_manager = create_bag_cache_manager()
    
    def load_bag_sync(self, bag_path: str, build_index: bool = False) -> Tuple[List[str], Dict[str, str], Any]:
        """
        Synchronous wrapper for bag loading
        
        Args:
            bag_path: Path to bag file
            build_index: Whether to build DataFrame index
            
        Returns:
            Tuple of (topics, connections, time_range)
        """
        import asyncio
        
        async def _load():
            # Try to get from cache first
            cached_entry = self.cache_manager.get_analysis(Path(bag_path))
            if cached_entry and cached_entry.is_valid(Path(bag_path)):
                logger.debug(f"Using cached bag info for {bag_path}")
                bag_info = cached_entry.bag_info
            else:
                # Load using parser
                bag_info, _ = await self.parser.load_bag_async(
                    bag_path, 
                    build_index=build_index
                )
            
            # Extract data in the format expected by CLI
            topics = bag_info.get_topic_names()
            # Create connections dict for backward compatibility
            connections = {}
            for topic in bag_info.topics:
                if isinstance(topic, str):
                    connections[topic] = "unknown"
                else:
                    connections[topic.name] = topic.message_type
            time_range = bag_info.time_range
            
            return topics, connections, time_range
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_load())


class TopicSelector:
    """Interactive topic selection with fuzzy search and filtering"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def select_topics_interactive(self, available_topics: List[str], 
                                bag_path: Optional[str] = None,
                                multi_select: bool = True,
                                allow_patterns: bool = True) -> Optional[List[str]]:
        """
        Interactive topic selection with search and filtering
        
        Args:
            available_topics: List of available topics
            bag_path: Optional bag file path for context
            multi_select: Whether to allow multiple topic selection
            allow_patterns: Whether to allow pattern-based selection
            
        Returns:
            List of selected topics or None if cancelled
        """
        from ..cli.util import ask_topics
        from ..core.parser import create_parser
        
        parser = create_parser()
        return ask_topics(self.console, available_topics, parser=parser, bag_path=bag_path)


class OutputManager:
    """Common output file management for interactive commands"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def ask_for_output_path(self, default_path: str, 
                          file_extension: str = ".bag",
                          message: str = "Enter output file path:") -> Tuple[Optional[str], bool]:
        """
        Ask user for output file path with overwrite handling
        
        Args:
            default_path: Default file path to suggest
            file_extension: Required file extension
            message: Custom message to display
            
        Returns:
            Tuple of (output_path, should_overwrite) or (None, False) if cancelled
        """
        while True:
            output_path = inquirer.filepath(
                message=message,
                default=default_path,
                validate=lambda x: x.endswith(file_extension) or f"File must have {file_extension} extension"
            ).execute()
            
            if not output_path:  # User cancelled
                return None, False
            
            # Check if file already exists
            if os.path.exists(output_path):
                # Ask user if they want to overwrite
                overwrite = inquirer.confirm(
                    message=f"Output file '{output_path}' already exists. Do you want to overwrite it?",
                    default=False
                ).execute()
                
                if overwrite:
                    return output_path, True
                else:
                    Message.warning("Please choose a different filename.", self.console)
                    continue
            else:
                return output_path, False
    
    def ask_for_output_directory(self, default_dir: str = ".", 
                               message: str = "Enter output directory:") -> Optional[str]:
        """
        Ask user for output directory
        
        Args:
            default_dir: Default directory path
            message: Custom message to display
            
        Returns:
            Selected directory path or None if cancelled
        """
        output_dir = inquirer.filepath(
            message=message,
            default=default_dir,
            validate=lambda x: os.path.isdir(x) or "Must be a valid directory"
        ).execute()
        
        return output_dir


class WhitelistManager:
    """Interactive whitelist management functionality"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.rose_dirs = get_rose_directories()
    
    def create_whitelist_interactive(self, topics: List[str]) -> Optional[str]:
        """
        Interactive whitelist creation
        
        Args:
            topics: List of topics to save in whitelist
            
        Returns:
            Path to created whitelist file or None if cancelled
        """
        # Save whitelist
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_name = f"whitelist_{timestamp}.txt"
        
        use_default = inquirer.confirm(
            message=f"Use default name? ({default_name})",
            default=True
        ).execute()
        
        if use_default:
            output_name = default_name
        else:
            output_name = inquirer.text(
                message="Enter whitelist name (without .txt extension):",
                default="my_whitelist",
                validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty"
            ).execute()
            
            if not output_name:
                return None
            
            if not output_name.endswith('.txt'):
                output_name += '.txt'
        
        # Save whitelist
        output_path = self.rose_dirs.get_whitelist_file(output_name)
        try:
            with open(output_path, 'w') as f:
                f.write("# Generated by Rose interactive command\n")
                f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")
                for topic in sorted(topics):
                    f.write(f"{topic}\n")
            
            Message.success(f"Saved whitelist to: {output_path}", self.console)
            return output_path
            
        except Exception as e:
            Message.error(f"Error saving whitelist: {str(e)}", self.console)
            return None
    
    def browse_whitelists_interactive(self) -> Optional[str]:
        """
        Browse and view whitelist files interactively
        
        Returns:
            Selected whitelist name or None if cancelled
        """
        whitelists = self.rose_dirs.list_whitelists()
        if not whitelists:
            Message.warning("No whitelists found", self.console)
            return None
            
        # Select whitelist to view
        selected = inquirer.select(
            message="Select whitelist to view:",
            choices=whitelists
        ).execute()
        
        if not selected:
            return None
            
        # Show whitelist contents
        path = self.rose_dirs.get_whitelist_file(selected)
        try:
            with open(path) as f:
                content = f.read()
                
            self.console.print(f"\nWhitelist: {selected}", style=f"bold {get_color('primary')}")
            self.console.print("─" * 80)
            self.console.print(content)
            return selected
            
        except Exception as e:
            Message.error(f"Error reading whitelist: {str(e)}", self.console)
            return None


class ProgressManager:
    """Common progress management for interactive operations"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def create_loading_context(self, description: str = "Processing..."):
        """
        Create a loading animation context
        
        Args:
            description: Description to display
            
        Returns:
            LoadingAnimation context manager
        """
        from ..cli.util import LoadingAnimation
        return LoadingAnimation(description, dismiss=True)
    
    def show_operation_summary(self, operation: str, success_count: int, 
                             fail_count: int, details: Optional[Dict] = None):
        """
        Show summary of batch operation results
        
        Args:
            operation: Name of the operation (e.g., "extraction", "compression")
            success_count: Number of successful operations
            fail_count: Number of failed operations
            details: Optional additional details to display
        """
        total = success_count + fail_count
        
        self.console.print(f"\n{operation.title()} Summary:", style=f"bold {get_color('primary')}")
        self.console.print("─" * 50)
        
        if success_count > 0:
            Message.success(f"{success_count}/{total} operations completed successfully", self.console)
        
        if fail_count > 0:
            Message.error(f"{fail_count}/{total} operations failed", self.console)
        
        if details:
            for key, value in details.items():
                self.console.print(f"{key}: {value}")
