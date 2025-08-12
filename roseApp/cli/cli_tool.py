import os
import time
import asyncio
from typing import Optional, List, Tuple, Dict
from pathlib import Path
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
import typer
from InquirerPy.validator import PathValidator
# Process files in parallel
import concurrent.futures
import threading
import queue
# Import parser and cache related modules
from ..core.parser import create_parser, ExtractOption
from ..core.cache import create_bag_cache_manager
from ..core.model import ComprehensiveBagInfo
from ..core.util import get_logger, get_preferred_parser_type
from ..core.ui_control import UIControl, Message
from ..core.directories import get_rose_directories
from .util import (LoadingAnimation, build_banner, 
                   collect_bag_files, 
                   print_usage_instructions, 
                   print_bag_info, 
                   print_filter_stats,
                   print_batch_filter_summary,
                   ask_topics)
logger = get_logger("RoseCLI-Tool")

WORKERS = os.cpu_count() - 2
app = typer.Typer(help="ROS Bag Filter Tool")


class CliTool:
    def __init__(self):
        self.console = Console()
        # Initialize Rose directories
        self.rose_dirs = get_rose_directories()
        # Use parser directly instead of BagManager
        self.parser = create_parser()
        self.cache_manager = create_bag_cache_manager()
        logger.debug("Using BagParser with cache for enhanced performance")
        # Cache for current bag info
        self.current_bag_info: Optional[ComprehensiveBagInfo] = None
        self.current_bag_path: Optional[str] = None
    
    def _run_async(self, coro):
        """Helper to run async coroutines in sync context"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    
    def _validate_float_in_range(self, value_str: str, min_val: float, max_val: float) -> bool:
        """Validate that a string represents a float within the given range"""
        try:
            value = float(value_str)
            return min_val <= value <= max_val
        except (ValueError, TypeError):
            return False
    
    def _load_bag_sync(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """Synchronous wrapper for bag loading using parser.load_bag_async"""
        async def _load():
            # Try to get from cache first
            cached_entry = self.cache_manager.get_analysis(Path(bag_path))
            if cached_entry and cached_entry.is_valid(Path(bag_path)):
                logger.debug(f"Using cached bag info for {bag_path}")
                bag_info = cached_entry.bag_info
            else:
                # Load using parser with progress callback
                def progress_callback(phase: str, percent: float):
                    logger.debug(f"Loading {bag_path}: {phase} ({percent:.1f}%)")
                
                bag_info, _ = await self.parser.load_bag_async(
                    bag_path, 
                    build_index=False,  # Use quick analysis for CLI
                    progress_callback=progress_callback
                )
            
            # Cache the current bag info for later use
            self.current_bag_info = bag_info
            self.current_bag_path = bag_path
            
            # Extract data in the format expected by CLI
            # Get topic names from optimized list structure
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
        
        return self._run_async(_load())
    
    def _filter_bag_sync(self, input_bag: str, output_bag: str, whitelist: List[str], 
                        progress_callback=None, compression="none", overwrite=False) -> Dict:
        """Synchronous wrapper for bag filtering using parser.extract"""
        def _filter():
            extract_option = ExtractOption(
                topics=whitelist,
                compression=compression,
                overwrite=overwrite
            )
            
            result_message, elapsed_time = self.parser.extract(
                input_bag, 
                output_bag, 
                extract_option,
                progress_callback
            )
            
            return {
                'message': result_message,
                'elapsed_time': elapsed_time,
                'input_file': input_bag,
                'output_file': output_bag,
                'topics': whitelist,
                'compression': compression
            }
        
        return _filter()
    
    def _load_whitelist_sync(self, whitelist_path: str) -> List[str]:
        """Load whitelist from file - simple file reading"""
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
            return []
 
    def ask_for_bag(self, message: str = "Enter bag file path:") -> Optional[str]:
        """Ask user to input a bag file path"""
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
                    self.console.print("Please choose a different filename.", style=UIControl.get_color("warning"))
                    continue  # Go back to filename input
            else:
                # File doesn't exist, no need to overwrite
                return output_bag, False
    

    
    def run_cli(self):
        """Run the CLI tool with improved menu logic"""
        try:
            # Show banner
            self.console.print(build_banner())
            
            while True:
                # Show main menu
                action = inquirer.select(
                    message="Select action:",
                    choices=[
                        Choice(value="filter", name="1. Bag Editor - View and filter bag files"),
                        Choice(value="wizard", name="2. Extraction Wizard - Generate extract commands"),
                        Choice(value="whitelist", name="3. Whitelist - Manage topic whitelists"),
                        Choice(value="exit", name="4. Exit")
                    ]
                ).execute()
                
                if action == "exit":
                    break
                elif action == "filter":
                    self.interactive_filter()
                elif action == "wizard":
                    self.extract_wizard()
                elif action == "whitelist":
                    self.whitelist_manager()
                
        except KeyboardInterrupt:
            Message("\nOperation cancelled by user", "warning").render(self.console)
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            Message(f"\nError: {str(e)}", "error").render(self.console)

    def interactive_filter(self):
        """Run interactive filter workflow"""
        while True:
            # Ask for input bag file or directory
            input_path = inquirer.filepath(
                message="Load Bag file(s):\n • Please specify the bag file or a directory to search \n • Leave blank to return to main menu\nFilename/Directory:",
                validate=lambda x: os.path.exists(x) or "Path does not exist"
            ).execute()
            
            if not input_path:
                return  # Return to main menu
                
            # Check if input is a file or directory
            if os.path.isfile(input_path):
                # Single bag file processing
                if not input_path.endswith('.bag'):
                    Message("File must be a .bag file", "error").render(self.console)
                    continue
                
                # Process single bag file
                self.handle_single_bag_interactive(input_path)
            else:
                # Process multiple bag files from directory
                # If return value is True, return to main menu
                self.handle_multiple_bags_interactive(input_path)
                # Ask if user wants to continue or go back to main menu
                continue_action = inquirer.select(
                    message="What would you like to do next?",
                    choices=[
                        Choice(value="continue", name="1. Process more files"),
                        Choice(value="main", name="2. Return to main menu")
                    ]
                ).execute()
                
                if continue_action == "main":
                    return
    
    def _get_filter_method(self):
        """Ask user to select a filter method
        
        Returns:
            str: The selected filter method ('whitelist', 'manual', or 'back')
        """
        return inquirer.select(
            message="Select filter method:",
            choices=[
                Choice(value="whitelist", name="1. Use whitelist"),
                Choice(value="manual", name="2. Select topics manually"),
                Choice(value="back", name="3. Back")
            ]
        ).execute()
    
    def handle_single_bag_interactive(self, bag_path: str):
        """Process a single bag file interactively
        
        Args:
            bag_path: Path to the bag file
        """
        # Load bag info
        with LoadingAnimation("Loading bag file...",dismiss=True) as progress:
            progress.add_task(description="Loading...")
            self.topics, self.connections, self.time_range = self._load_bag_sync(bag_path)
        
        # Create a loop for bag operations
        while True:
            # Ask user what to do next
            next_action = inquirer.select(
                message="What would you like to do?",
                choices=[
                    Choice(value="info", name="1. Show bag information"),
                    Choice(value="filter", name="2. Filter bag file"),
                    Choice(value="back", name="3. Back to file selection")
                ]
            ).execute()
            
            if next_action == "back":
                break  # Go back to input selection
            elif next_action == "info":
                # Use cached bag info if available
                if self.current_bag_info and self.current_bag_path == bag_path:
                    # Get topic names from optimized list structure
                    topics_list = self.current_bag_info.get_topic_names()
                    # Create connections dict for backward compatibility
                    connections_dict = {}
                    for topic in self.current_bag_info.topics:
                        if isinstance(topic, str):
                            connections_dict[topic] = "unknown"
                        else:
                            connections_dict[topic.name] = topic.message_type
                    print_bag_info(self.console, bag_path, 
                                 topics_list, 
                                 connections_dict, 
                                 self.current_bag_info.time_range, 
                                 parser=self.parser)
                else:
                    # Fallback to loaded data
                    print_bag_info(self.console, bag_path, self.topics, self.connections, self.time_range, parser=self.parser)
                continue  # Stay in the current menu
            elif next_action == "filter":
                # Get output bag with overwrite handling
                default_output = os.path.splitext(bag_path)[0] + "_filtered.bag"
                output_result = self.ask_for_output_bag(default_output)
                
                if output_result[0] is None:  # User cancelled
                    continue  # Stay in the current menu
                
                output_bag, should_overwrite = output_result
                    
                # Get filter method using the helper function
                filter_method = self._get_filter_method()
                
                if not filter_method or filter_method == "back":
                    continue  # Stay in the current menu
                    
                # Process single file with overwrite flag
                self._process_single_bag(bag_path, output_bag, filter_method, should_overwrite)
    
    def handle_multiple_bags_interactive(self, directory_path: str):
        """Process multiple bag files from a directory interactively
        
        Args:
            directory_path: Path to the directory containing bag files
        """
        # Find and select bag files
        bag_files = collect_bag_files(directory_path)
        if not bag_files:
            Message("No bag files found in directory", "error").render(self.console)
            return  # Go back to input selection
            
        # Create file selection choices
        file_choices = [
            Choice(
                value=f,
                name=f"{os.path.relpath(f, directory_path)} ({os.path.getsize(f)/1024/1024:.1f} MB)"
            ) for f in bag_files
        ]
        
        def bag_list_transformer(result):
            return f"{len(result)} files selected\n" + '\n'.join([f"• {os.path.basename(bag)}" for bag in result])
        
        print_usage_instructions(self.console)

        selected_files = inquirer.checkbox(
            message="Select bag files to process:",
            choices=file_choices,
            instruction="",
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one file",
            transformer=bag_list_transformer
        ).execute()
        
        if not selected_files:
            return  # Go back to input selection
            
        # Get filter method using the helper function
        filter_method = self._get_filter_method()
        
        if not filter_method or filter_method == "back":
            return  # Go back to input selection
            
        # Get whitelist based on filter method
        if filter_method == "whitelist":
            whitelist = self._get_filter_topics_from_whitelist()
                
        elif filter_method == "manual":
            whitelist = self._get_filter_topics_from_manual_selection(selected_files)
            if not whitelist:
                return

        if not whitelist:
            return  # Go back to input selection
        
        # Ask user about compression
        from roseApp.core.util import get_available_compression_types
        available_compressions = get_available_compression_types()
        
        # Create compression choice list based on availability
        compression_choices = []
        if "none" in available_compressions:
            compression_choices.append(Choice(value="none", name="1. No compression (fastest, largest file)"))
        if "bz2" in available_compressions:
            compression_choices.append(Choice(value="bz2", name="2. BZ2 compression (slower, smallest file)"))
        if "lz4" in available_compressions:
            compression_choices.append(Choice(value="lz4", name="3. LZ4 compression (balanced speed/size)"))
        
        compression = inquirer.select(
            message="Choose compression type:",
            choices=compression_choices,
            default="none"
        ).execute()
        
        if compression is None:
            return
        
        # Process bag files in parallel
        confirm = inquirer.confirm(
            message="Are you sure you want to process these bag files?",
            default=False
        ).execute()
        if not confirm:
            return  # Go back to input selection
        
        self._process_bags_in_parallel(selected_files, directory_path, whitelist, compression)
        
        
    
    def _get_filter_topics_from_whitelist(self) -> Optional[List[str]]:
        whitelists = self.rose_dirs.list_whitelists()
        if not whitelists:
            Message("No whitelists found", "warning").render(self.console)
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
        return self._load_whitelist_sync(whitelist_path)

    def _get_filter_topics_from_manual_selection(self, selected_files: List[str]) -> Optional[List[str]]:
        """Get topics from manual selection
        
        Returns:
            List of topics to include, or None if cancelled
        """
        # Load all bag files to get the union of topics
        all_topics = set()
        all_connections = {}
        
        with LoadingAnimation("Loading bag files for topic selection...") as progress:
            task = progress.add_task("Loading bag files for topic selection...", total=len(selected_files))
            
            for i, bag_file in enumerate(selected_files):
                progress.update(task, description=f"Loading {i+1}/{len(selected_files)}: {os.path.basename(bag_file)}")
                try:
                    topics, connections, _ = self._load_bag_sync(bag_file)
                    all_topics.update(topics)
                    all_connections.update(connections)
                    progress.advance(task)
                except Exception as e:
                    Message(f"Error loading {bag_file}: {str(e)}", "error").render(self.console)
                    # Continue with other files
        
        if not all_topics:
            Message("No topics found in selected bag files", "error").render(self.console)
            return None
        
        Message(f"Found {len(all_topics)} unique topics across {len(selected_files)} bag files", "success").render(self.console)
        
        # Use the first bag file for statistics display (as an example)
        bag_path_for_stats = selected_files[0] if selected_files else None
        
        return ask_topics(self.console, list(all_topics), parser=self.parser, bag_path=bag_path_for_stats)


    def _process_bags_in_parallel(self, selected_files, input_path, whitelist, compression="none"):
        """Process multiple bag files in parallel
        
        Args:
            selected_files: List of bag files to process
            input_path: Base directory path for relative path display
            whitelist: List of topics to include in filtered bags
            compression: Compression type to use (default: "none")
            
        Returns:
            Dictionary mapping bag files to their task IDs
        """
        # Create progress display for all files
        with LoadingAnimation() as progress:
            # Track tasks for all files (will be created when processing starts)
            tasks = {}
            # Track success and failure counts
            success_count = 0
            fail_count = 0
            success_fail_lock = threading.Lock()
            
            # Create a thread-local storage for progress updates
            thread_local = threading.local()
            
            # Generate a timestamp for this batch
            batch_timestamp = time.strftime("%H%M%S")
            
            # Create a queue for files to process
            file_queue = queue.Queue()
            for bag_file in selected_files:
                file_queue.put(bag_file)
            
            # Track active files
            active_files = set()
            active_files_lock = threading.Lock()
            
            def _process_bag_file(bag_file):
                rel_path = os.path.relpath(bag_file, input_path)
                display_path = rel_path
                if len(rel_path) > 40:
                    display_path = f"{rel_path[:15]}...{rel_path[-20:]}"
                
                # Create task for this file at the start of processing
                with active_files_lock:
                    task = progress.add_task(
                        f"Processing: {display_path}",
                        total=100,
                        completed=0,
                        style=UIControl.get_color("accent")
                    )
                    tasks[bag_file] = task
                    active_files.add(bag_file)
                
                try:
                    # Create output path with timestamp
                    base_name = os.path.splitext(bag_file)[0]
                    output_bag = f"{base_name}_filtered_{batch_timestamp}.bag"
                    
                    # Process file with the selected whitelist
                    # BagManager handles thread safety internally
                    
                    # Initialize progress to 30% to indicate preparation complete
                    progress.update(task, description=f"Processing: {display_path}", style=UIControl.get_color("accent"), completed=0)
                    
                    # Define progress update callback function
                    def update_progress(percent: int):
                        # Map percentage to 30%-100% range, as 30% indicates preparation work complete
                        progress.update(task, 
                                       description=f"Processing: {display_path}", 
                                        style=UIControl.get_color("accent"), 
                                       completed=percent)
                    
                    # Use progress callback for filtering
                    try:
                        result = self._filter_bag_sync(
                            bag_file, 
                            output_bag, 
                            whitelist,
                            progress_callback=update_progress,
                            compression=compression,
                            overwrite=True  # For batch processing, always overwrite
                        )
                    except Exception as e:
                        # Handle any filtering errors
                        raise e
                    
                    # Update task status to complete, showing green success mark
                    progress.update(task, description=f"[green]✓ {display_path}[/green]", completed=100)
                    
                    # Increment success count
                    with success_fail_lock:
                        nonlocal success_count
                        success_count += 1
                        
                    return True
                    
                except Exception as e:
                    # Update task status to failed, showing red error mark
                    progress.update(task, description=f"[red]✗ {display_path}: {str(e)}[/red]", completed=100)
                    logger.error(f"Error processing {bag_file}: {str(e)}", exc_info=True)
                    
                    # Increment failure count
                    with success_fail_lock:
                        nonlocal fail_count
                        fail_count += 1
                        
                    return False
                finally:
                    # Remove file from active set
                    with active_files_lock:
                        active_files.remove(bag_file)
            
            max_workers = min(len(selected_files), WORKERS)
            self.console.print(f"\nProcessing {len(selected_files)} files with {max_workers} parallel workers\n", style=UIControl.get_color("info"))
            # Use ThreadPoolExecutor for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks to the executor without creating progress tasks yet
                futures = {}
                
                # Submit all files to the executor
                while not file_queue.empty():
                    bag_file = file_queue.get()
                    futures[executor.submit(_process_bag_file, bag_file)] = bag_file
                
                # Wait for all tasks to complete
                while futures:
                    # Wait for the next task to complete
                    done, _ = concurrent.futures.wait(
                        futures, 
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    
                    # Process completed futures
                    for future in done:
                        bag_file = futures.pop(future)
                        try:
                            future.result()  # This will re-raise any exception from the thread
                        except Exception as e:
                            # This should not happen as exceptions are caught in process_bag_file
                            logger.error(f"Unexpected error processing {bag_file}: {str(e)}", exc_info=True)

        # Show final summary with color-coded results
        print_batch_filter_summary(self.console, success_count, fail_count)
        
        return tasks

    def _process_single_bag(self, input_bag: str, output_bag: str, filter_method: str, overwrite: bool = False):
        """Process a single bag file"""
        # Load bag information
        with LoadingAnimation("Loading bag file...",dismiss=True) as progress:
            progress.add_task(description="Loading...")
            self.topics, self.connections, self.time_range = self._load_bag_sync(input_bag)
        
        # Get filter parameters based on method (if not provided)
        if filter_method == "whitelist":
            # Get whitelist file
            whitelists = self.rose_dirs.list_whitelists()
            if not whitelists:
                self.console.print("No whitelists found", style=UIControl.get_color("warning"))
                return
                
            # Select whitelist to use
            selected = inquirer.select(
                message="Select whitelist to use:",
                choices=whitelists
            ).execute()
            
            if not selected:
                return
                
            # Load selected whitelist
            whitelist_path = self.rose_dirs.get_whitelist_file(selected)
            whitelist = self._load_whitelist_sync(whitelist_path)
            if not whitelist:
                return
                
        elif filter_method == "manual":
            # Use cached bag info if available
            topics_to_use = self.topics
            if self.current_bag_info and self.current_bag_path == input_bag:
                # Convert TopicInfo objects to topic names
                bag_topics = self.current_bag_info.get_topic_names() if self.current_bag_info.topics else []
                topics_to_use = bag_topics or self.topics
            
            whitelist = ask_topics(self.console, topics_to_use, parser=self.parser, bag_path=input_bag)
            if not whitelist:
                return

        # Ask user about compression
        from roseApp.core.util import get_available_compression_types
        available_compressions = get_available_compression_types()
        
        # Create compression choice list based on availability
        compression_choices = []
        if "none" in available_compressions:
            compression_choices.append(Choice(value="none", name="1. No compression (fastest, largest file)"))
        if "bz2" in available_compressions:
            compression_choices.append(Choice(value="bz2", name="2. BZ2 compression (slower, smallest file)"))
        if "lz4" in available_compressions:
            compression_choices.append(Choice(value="lz4", name="3. LZ4 compression (balanced speed/size)"))
        
        compression = inquirer.select(
            message="Choose compression type:",
            choices=compression_choices,
            default="none"
        ).execute()
        
        if compression is None:
            return
        
        input_basename = os.path.basename(input_bag)
        display_name = input_basename
        if len(input_basename) > 40:
            display_name = f"{input_basename[:15]}...{input_basename[-20:]}"
            
        # Use rich progress bar to process file
        with LoadingAnimation("Processing bag file...",dismiss=True) as progress:
            # Create progress task
            task_id = progress.add_task(f"Filtering: {display_name}", total=100)
            
            # Define progress update callback function
            def update_progress(percent: int):
                progress.update(task_id, description=f"Filtering: {display_name}", completed=percent)
            
            # Execute filtering with progress callback
            result = self._filter_bag_sync(
                input_bag, 
                output_bag, 
                whitelist,
                progress_callback=update_progress,
                compression=compression,
                overwrite=overwrite
            )
            
            # progress.update(task_id, description=f"[green]✓ Complete: {display_name}[/green]", completed=100)
        
        
        # Show filtering result statistics
        print_filter_stats(self.console, input_bag, output_bag)
            
        
    def whitelist_manager(self):
        """Run whitelist management workflow"""
        while True:
            action = inquirer.select(
                message="Whitelist Management:",
                choices=[
                    Choice(value="create", name="1. Create new whitelist"),
                    Choice(value="view", name="2. View whitelist"),
                    Choice(value="delete", name="3. Delete whitelist"),
                    Choice(value="back", name="4. Back")
                ]
            ).execute()
            
            if action == "back":
                return
            elif action == "create":
                self._create_whitelist_workflow()
            elif action == "view":
                self._browse_whitelists()
            elif action == "delete":
                self._delete_whitelist()
    
    def _create_whitelist_workflow(self):
        """Create whitelist workflow"""
        # Get bag file
        input_bag = self.ask_for_bag("Enter bag file path to create whitelist from:")
        if not input_bag:
            return
            
        # Load bag file
        with LoadingAnimation("Loading bag file...",dismiss=True) as progress:
            progress.add_task(description="Loading...")
            topics, connections, _ = self._load_bag_sync(input_bag)
        
        # Select topics
        selected_topics = ask_topics(self.console, topics, parser=self.parser, bag_path=input_bag)
        if not selected_topics:
            return
            
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
                return
            
            if not output_name.endswith('.txt'):
                output_name += '.txt'
        
        # Save whitelist
        output = self.rose_dirs.get_whitelist_file(output_name)
        with open(output, 'w') as f:
            f.write("# Generated by rose cli-tool\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for topic in sorted(selected_topics):
                f.write(f"{topic}\n")
        
        self.console.print(f"\nSaved whitelist to: {output}", style=UIControl.get_color("primary"))
        
        # Ask what to do next
        next_action = inquirer.select(
            message="What would you like to do next?",
            choices=[
                Choice(value="continue", name="1. Create another whitelist"),
                Choice(value="back", name="2. Back")
            ]
        ).execute()
        
        if next_action == "continue":
            self._create_whitelist_workflow()
    
    def _browse_whitelists(self):
        """Browse and view whitelist files"""
        # Get all whitelist files
        whitelists = self.rose_dirs.list_whitelists()
        if not whitelists:
            self.console.print("No whitelists found", style=UIControl.get_color("warning"))
            return
            
        # Select whitelist to view
        selected = inquirer.select(
            message="Select whitelist to view:",
            choices=whitelists
        ).execute()
        
        if not selected:
            return
            
        # Show whitelist contents
        path = self.rose_dirs.get_whitelist_file(selected)
        with open(path) as f:
            content = f.read()
            
        self.console.print(f"\nWhitelist: {selected}", style=f"bold {UIControl.get_color('primary')}")
        self.console.print("─" * 80)
        self.console.print(content)
    

    

        
    def _delete_whitelist(self):
        """Delete a whitelist file"""
        whitelists = self.rose_dirs.list_whitelists()
        if not whitelists:
            self.console.print("No whitelists found", style=UIControl.get_color("warning"))
            return
            
        # Select whitelist to delete
        selected = inquirer.select(
            message="Select whitelist to delete:",
            choices=whitelists
        ).execute()
        
        if not selected:
            return
            
        # Confirm deletion
        if not inquirer.confirm(
            message=f"Are you sure you want to delete '{selected}'?",
            default=False
        ).execute():
            return
            
        # Delete the file
        path = self.rose_dirs.get_whitelist_file(selected)
        try:
            os.remove(path)
            self.console.print(f"\nDeleted whitelist: {selected}", style=UIControl.get_color("primary"))
        except Exception as e:
            self.console.print(f"\nError deleting whitelist: {str(e)}", style=UIControl.get_color("error"))

    def extract_wizard(self):
        """Extract wizard - Generate extract commands for reuse"""
        while True:
            action = inquirer.select(
                message="Extract Wizard:",
                choices=[
                    Choice(value="create", name="1. Create new extract command"),
                    Choice(value="view", name="2. View saved commands"),
                    Choice(value="run", name="3. Run saved command"),
                    Choice(value="delete", name="4. Delete saved command"),
                    Choice(value="back", name="5. Back")
                ]
            ).execute()
            
            if action == "back":
                return
            elif action == "create":
                self._create_extract_command()
            elif action == "view":
                self._view_extract_commands()
            elif action == "run":
                self._run_extract_command()
            elif action == "delete":
                self._delete_extract_command()
    
    def _create_extract_command(self):
        """Create a new extract command"""
        # Get input bag file
        input_bag = self.ask_for_bag("Select input bag file:")
        if not input_bag:
            return
        
        # Load bag information
        with LoadingAnimation("Loading bag file...", dismiss=True) as progress:
            progress.add_task(description="Loading...")
            topics, connections, time_range = self._load_bag_sync(input_bag)
        
        # Get output file pattern
        output_pattern = inquirer.text(
            message="Enter output file pattern (use {input} for input filename):",
            default="{input}_extracted.bag",
            validate=lambda x: len(x.strip()) > 0 or "Pattern cannot be empty"
        ).execute()
        
        if not output_pattern:
            return
        
        # Ask user whether to include or exclude topics
        topic_mode = inquirer.select(
            message="Topic selection mode:",
            choices=[
                Choice(value="include", name="Include selected topics (default)"),
                Choice(value="exclude", name="Exclude selected topics (use --reverse)")
            ],
            default="include"
        ).execute()
        
        if not topic_mode:
            return
        
        # Select topics
        if topic_mode == "include":
            prompt_message = "Select topics to INCLUDE in the extract:"
        else:
            prompt_message = "Select topics to EXCLUDE from the extract:"
        
        # Show the mode to user
        self.console.print(f"\n{prompt_message}", style=UIControl.get_color("info"))
        selected_topics = ask_topics(self.console, topics, parser=self.parser, bag_path=input_bag)
        if not selected_topics:
            return
        
        # Time range selection
        use_time_range = inquirer.confirm(
            message="Do you want to specify a time range?",
            default=False
        ).execute()
        
        start_time = None
        end_time = None
        if use_time_range and time_range:
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
                validate=lambda x: self._validate_float_in_range(x, start_sec, end_sec) or f"Must be a number between {start_sec:.3f} and {end_sec:.3f}",
                filter=lambda x: float(x) if x else start_sec
            ).execute()
            
            if start_time is not None:
                end_time = inquirer.text(
                    message=f"Enter end time (seconds, default: {end_sec:.3f}):",
                    default=str(end_sec),
                    validate=lambda x: self._validate_float_in_range(x, start_time, end_sec) or f"Must be a number between {start_time:.3f} and {end_sec:.3f}",
                    filter=lambda x: float(x) if x else end_sec
                ).execute()
        
        # Compression selection
        from roseApp.core.util import get_available_compression_types
        available_compressions = get_available_compression_types()
        
        compression_choices = []
        if "none" in available_compressions:
            compression_choices.append(Choice(value="none", name="No compression"))
        if "bz2" in available_compressions:
            compression_choices.append(Choice(value="bz2", name="BZ2 compression"))
        if "lz4" in available_compressions:
            compression_choices.append(Choice(value="lz4", name="LZ4 compression"))
        
        compression = inquirer.select(
            message="Choose compression type:",
            choices=compression_choices,
            default="none"
        ).execute()
        
        if compression is None:
            return
        
        # Save command
        command_name = inquirer.text(
            message="Enter command name:",
            default=f"extract_{time.strftime('%Y%m%d_%H%M%S')}",
            validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty"
        ).execute()
        
        if not command_name:
            return
        
        # Create command data
        command_data = {
            'name': command_name,
            'created': time.strftime('%Y-%m-%d %H:%M:%S'),
            'input_pattern': input_bag,  # Can be modified to use patterns
            'output_pattern': output_pattern,
            'topics': selected_topics,
            'topic_mode': topic_mode,  # 'include' or 'exclude'
            'start_time': start_time,
            'end_time': end_time,
            'compression': compression,
            'description': f"{'Exclude' if topic_mode == 'exclude' else 'Extract'} {len(selected_topics)} topics from bag files"
        }
        
        # Save to config directory
        commands_file = self.rose_dirs.get_config_file('extract_commands.json')
        
        # Load existing commands
        commands = []
        if os.path.exists(commands_file):
            try:
                import json
                with open(commands_file, 'r') as f:
                    commands = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load existing commands: {e}")
                commands = []
        
        # Add new command
        commands.append(command_data)
        
        # Save updated commands
        try:
            import json
            with open(commands_file, 'w') as f:
                json.dump(commands, f, indent=2)
            
            self.console.print(f"\nSaved extract command: {command_name}", style=UIControl.get_color("primary"))
            self._show_extract_command_summary(command_data)
            
        except Exception as e:
            self.console.print(f"\nError saving command: {str(e)}", style=UIControl.get_color("error"))
    
    def _show_extract_command_summary(self, command_data):
        """Show a summary of the extract command"""
        self.console.print("\nCommand Summary:", style=f"bold {UIControl.get_color('primary')}")
        self.console.print("─" * 50)
        self.console.print(f"Name: {command_data['name']}")
        self.console.print(f"Output: {command_data['output_pattern']}")
        topic_mode = command_data.get('topic_mode', 'include')
        mode_text = "exclude" if topic_mode == 'exclude' else "include"
        self.console.print(f"Topics: {len(command_data['topics'])} selected to {mode_text}")
        if command_data['start_time'] is not None:
            self.console.print(f"Time range: {command_data['start_time']:.3f} - {command_data['end_time']:.3f} seconds")
        self.console.print(f"Compression: {command_data['compression']}")
        
        # Show equivalent command line
        topics_str = ' '.join([f'"{topic}"' for topic in command_data['topics']])
        cmd = f"rose extract --input \"{{input_bag}}\" --output \"{command_data['output_pattern']}\" --topics {topics_str}"
        
        # Add --reverse flag if topic_mode is exclude
        if topic_mode == 'exclude':
            cmd += " --reverse"
            
        if command_data['start_time'] is not None:
            cmd += f" --start-time {command_data['start_time']:.3f} --end-time {command_data['end_time']:.3f}"
        if command_data['compression'] != "none":
            cmd += f" --compression {command_data['compression']}"
        
        self.console.print(f"\nEquivalent command:")
        self.console.print(f"  {cmd}", style=UIControl.get_color("info"))
    
    def _view_extract_commands(self):
        """View saved extract commands"""
        commands = self._load_extract_commands()
        if not commands:
            self.console.print("No saved extract commands found", style=UIControl.get_color("warning"))
            return
        
        # Select command to view
        choices = [
            Choice(value=i, name=f"{cmd['name']} - {cmd['description']} ({cmd['created']})")
            for i, cmd in enumerate(commands)
        ]
        
        selected_idx = inquirer.select(
            message="Select command to view:",
            choices=choices
        ).execute()
        
        if selected_idx is not None:
            self._show_extract_command_summary(commands[selected_idx])
    
    def _run_extract_command(self):
        """Run a saved extract command"""
        commands = self._load_extract_commands()
        if not commands:
            self.console.print("No saved extract commands found", style=UIControl.get_color("warning"))
            return
        
        # Select command to run
        choices = [
            Choice(value=i, name=f"{cmd['name']} - {cmd['description']}")
            for i, cmd in enumerate(commands)
        ]
        
        selected_idx = inquirer.select(
            message="Select command to run:",
            choices=choices
        ).execute()
        
        if selected_idx is None:
            return
        
        command_data = commands[selected_idx]
        
        # Get input bag file(s)
        input_bag = self.ask_for_bag("Select input bag file:")
        if not input_bag:
            return
        
        # Generate output filename
        input_name = os.path.splitext(os.path.basename(input_bag))[0]
        output_bag = command_data['output_pattern'].replace('{input}', input_name)
        
        # Ask for output confirmation
        output_bag = inquirer.text(
            message="Output file:",
            default=output_bag
        ).execute()
        
        if not output_bag:
            return
        
        # Check if output exists
        if os.path.exists(output_bag):
            overwrite = inquirer.confirm(
                message=f"Output file '{output_bag}' already exists. Overwrite?",
                default=False
            ).execute()
            
            if not overwrite:
                return
        
        # Run the extraction
        self.console.print(f"\nRunning extract command: {command_data['name']}")
        
        try:
            # Determine actual topics to extract based on topic_mode
            topic_mode = command_data.get('topic_mode', 'include')
            
            if topic_mode == 'exclude':
                # Load bag to get all available topics
                all_topics, _, _ = self._load_bag_sync(input_bag)
                # Exclude the specified topics
                actual_topics = [t for t in all_topics if t not in command_data['topics']]
                self.console.print(f"Excluding {len(command_data['topics'])} topics, extracting {len(actual_topics)} topics")
            else:
                # Include mode (default)
                actual_topics = command_data['topics']
                self.console.print(f"Including {len(actual_topics)} topics")
            
            if not actual_topics:
                self.console.print("No topics to extract", style=UIControl.get_color("warning"))
                return
            
            # Create ExtractOption
            extract_option = ExtractOption(
                topics=actual_topics,
                compression=command_data['compression'],
                overwrite=True
            )
            
            # Set time range if specified
            if command_data['start_time'] is not None:
                # Convert to nanoseconds
                start_ns = int(command_data['start_time'] * 1_000_000_000)
                end_ns = int(command_data['end_time'] * 1_000_000_000)
                extract_option.time_range = (start_ns, end_ns)
            
            # Run extraction with progress
            with LoadingAnimation("Extracting...", dismiss=True) as progress:
                task_id = progress.add_task(f"Extracting: {os.path.basename(input_bag)}", total=100)
                
                def update_progress(percent: int):
                    progress.update(task_id, completed=percent)
                
                result = self._filter_bag_sync(
                    input_bag,
                    output_bag,
                    actual_topics,
                    progress_callback=update_progress,
                    compression=command_data['compression'],
                    overwrite=True
                )
            
            self.console.print(f"\nExtraction completed successfully!", style=UIControl.get_color("success"))
            self.console.print(f"Output: {output_bag}")
            
        except Exception as e:
            self.console.print(f"\nExtraction failed: {str(e)}", style=UIControl.get_color("error"))
    
    def _delete_extract_command(self):
        """Delete a saved extract command"""
        commands = self._load_extract_commands()
        if not commands:
            self.console.print("No saved extract commands found", style=UIControl.get_color("warning"))
            return
        
        # Select command to delete
        choices = [
            Choice(value=i, name=f"{cmd['name']} - {cmd['description']}")
            for i, cmd in enumerate(commands)
        ]
        
        selected_idx = inquirer.select(
            message="Select command to delete:",
            choices=choices
        ).execute()
        
        if selected_idx is None:
            return
        
        command_data = commands[selected_idx]
        
        # Confirm deletion
        if not inquirer.confirm(
            message=f"Are you sure you want to delete '{command_data['name']}'?",
            default=False
        ).execute():
            return
        
        # Remove command and save
        commands.pop(selected_idx)
        
        try:
            import json
            commands_file = self.rose_dirs.get_config_file('extract_commands.json')
            with open(commands_file, 'w') as f:
                json.dump(commands, f, indent=2)
            
            self.console.print(f"\nDeleted extract command: {command_data['name']}", style=UIControl.get_color("primary"))
            
        except Exception as e:
            self.console.print(f"\nError deleting command: {str(e)}", style=UIControl.get_color("error"))
    
    def _load_extract_commands(self):
        """Load saved extract commands"""
        commands_file = self.rose_dirs.get_config_file('extract_commands.json')
        
        if not os.path.exists(commands_file):
            return []
        
        try:
            import json
            with open(commands_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load extract commands: {e}")
            return []

# Typer commands
@app.command()
def cli():
    """Interactive CLI mode with menu interface"""
    tool = CliTool()
    tool.run_cli()


def main():
    """Entry point for the CLI tool"""
    app()

if __name__ == "__main__":
    main() 