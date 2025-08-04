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
                    full_analysis=False,  # Use quick analysis for CLI
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
                    self.console.print("Please choose a different filename.", style=theme.WARNING)
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
                        Choice(value="whitelist", name="2. Whitelist - Manage topic whitelists"),
                        Choice(value="exit", name="3. Exit")
                    ]
                ).execute()
                
                if action == "exit":
                    break
                elif action == "filter":
                    self.interactive_filter()
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
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            Message("No whitelists found", "warning").render(self.console)
            return None
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
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
        whitelist_path = os.path.join(whitelist_dir, selected)
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
            self.console.print(f"\nProcessing {len(selected_files)} files with {max_workers} parallel workers\n", style=theme.INFO)
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
            whitelist_dir = "whitelists"
            if not os.path.exists(whitelist_dir):
                self.console.print("No whitelists found", style=theme.WARNING)
                return
                
            whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
            if not whitelists:
                self.console.print("No whitelists found", style=theme.WARNING)
                return
                
            # Select whitelist to use
            selected = inquirer.select(
                message="Select whitelist to use:",
                choices=whitelists
            ).execute()
            
            if not selected:
                return
                
            # Load selected whitelist
            whitelist_path = os.path.join(whitelist_dir, selected)
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
        default_path = f"whitelists/whitelist_{timestamp}.txt"
        
        use_default = inquirer.confirm(
            message=f"Use default path? ({default_path})",
            default=True
        ).execute()
        
        if use_default:
            output = default_path
        else:
            output = inquirer.filepath(
                message="Enter save path:",
                default="whitelists/my_whitelist.txt",
                validate=lambda x: x.endswith('.txt') or "File must be a .txt file"
            ).execute()
            
            if not output:
                return
        
        # Save whitelist
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
        with open(output, 'w') as f:
            f.write("# Generated by rose cli-tool\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for topic in sorted(selected_topics):
                f.write(f"{topic}\n")
        
        self.console.print(f"\nSaved whitelist to: {output}", style=theme.PRIMARY)
        
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
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style=theme.WARNING)
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style=theme.WARNING)
            return
            
        # Select whitelist to view
        selected = inquirer.select(
            message="Select whitelist to view:",
            choices=whitelists
        ).execute()
        
        if not selected:
            return
            
        # Show whitelist contents
        path = os.path.join(whitelist_dir, selected)
        with open(path) as f:
            content = f.read()
            
        self.console.print(f"\nWhitelist: {selected}", style=f"bold {theme.PRIMARY}")
        self.console.print("─" * 80)
        self.console.print(content)
    

    

        
    def _delete_whitelist(self):
        """Delete a whitelist file"""
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style=theme.WARNING)
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style=theme.WARNING)
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
        path = os.path.join(whitelist_dir, selected)
        try:
            os.remove(path)
            self.console.print(f"\nDeleted whitelist: {selected}", style=theme.PRIMARY)
        except Exception as e:
            self.console.print(f"\nError deleting whitelist: {str(e)}", style=theme.ERROR)

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