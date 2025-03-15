import os
import time
from typing import Optional, List, Tuple
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
import typer
from InquirerPy.validator import PathValidator

from .core.parser import create_parser, ParserType
from .core.util import get_logger, TimeUtil

logger = get_logger("RoseCLI-Tool")

ROSE_BANNER = """
██████╗  ██████╗ ███████╗███████╗
██╔══██╗██╔═══██╗██╔════╝██╔════╝
██████╔╝██║   ██║███████╗█████╗  
██╔══██╗██║   ██║╚════██║██╔══╝  
██║  ██║╚██████╔╝███████║███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝
"""

app = typer.Typer(help="ROS Bag Filter Tool")

class CliTool:
    def __init__(self):
        self.console = Console()
        self.parser = create_parser(ParserType.PYTHON)
        self.input_bag = None
        self.topics = None
        self.connections = None
        self.time_range = None
        
    def show_banner(self):
        """Display the ROSE banner"""
        rprint(Panel(
            Text(ROSE_BANNER, style="bold green"),
            title="[bold]ROS Bag Filter Tool[/bold]",
            subtitle="[dim]Press Ctrl+C to exit[/dim]"
        ))
    
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
    
    def show_loading(self, message: str):
        """Show a loading spinner with message"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        )
    
    def run_cli(self):
        """Run the CLI tool with improved menu logic"""
        try:
            self.show_banner()
            
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
                    self._run_quick_filter()
                elif action == "whitelist":
                    self._run_whitelist_manager()
                
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled by user", style="yellow")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.console.print(f"\nError: {str(e)}", style="red")

    def filter_bag(self, input_bag: str, output_bag: str, selected_topics: Optional[List[str]] = None, whitelist_path: Optional[str] = None, show_stats: bool = True, progress_context: Optional[Progress] = None):
        """Filter a bag file using whitelist or manual selection"""
        try:
            # Load bag file
            if progress_context:
                # If we're in a batch process, update the existing progress
                task_id = progress_context.add_task(f"Loading {os.path.basename(input_bag)}...", total=None)
                self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
                progress_context.update(task_id, description=f"Filtering {os.path.basename(input_bag)}...", visible=True)
                self.parser.filter_bag(input_bag, output_bag, selected_topics)
                progress_context.remove_task(task_id)
            else:
                # Normal single-file process with separate progress indicators
                with self.show_loading("Loading bag file...") as progress:
                    progress.add_task(description="Loading...")
                    self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
                
                # Get selected topics
                if whitelist_path:
                    selected_topics = self.parser.load_whitelist(whitelist_path)
                elif not selected_topics:
                    selected_topics = self._select_topics(self.topics, self.connections)
                    if not selected_topics:
                        return
                
                # Run filter
                start_time = time.time()
                with self.show_loading("Filtering bag file...") as progress:
                    progress.add_task(description="Processing...")
                    self.parser.filter_bag(input_bag, output_bag, selected_topics)
                end_time = time.time()
                
                # Show statistics if requested
                if show_stats:
                    input_size = os.path.getsize(input_bag)
                    output_size = os.path.getsize(output_bag)
                    input_size_mb = input_size / (1024 * 1024)
                    output_size_mb = output_size / (1024 * 1024)
                    reduction_ratio = (1 - output_size / input_size) * 100
                    
                    stats = (
                        f"Filter Statistics:\n"
                        f"• Time: {end_time - start_time:.2f} seconds\n"
                        f"• Size: {input_size_mb:.2f} MB -> {output_size_mb:.2f} MB\n"
                        f"• Reduction: {reduction_ratio:.1f}%\n"
                        f"• Topics: {len(self.topics)} -> {len(selected_topics)}"
                    )
                    rprint(Panel(stats, style="bold green", title="[bold]Filter Results[/bold]"))
                    
                    self.console.print(f"\nFilter completed: {output_bag}", style="green")
            
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.console.print(f"\nError: {str(e)}", style="red")
            if not progress_context:  # Only raise in single-file mode
                raise typer.Exit(1)
            return False
        return True

    def _find_bag_files(self, directory: str) -> List[str]:
        """Recursively find all bag files in the given directory"""
        bag_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.bag'):
                    bag_files.append(os.path.join(root, file))
        return sorted(bag_files)

    def _select_bag_files(self) -> Optional[List[str]]:
        """Ask user to select bag files to process"""
        # Get directory path
        directory = inquirer.filepath(
            message="Enter directory path to search for bag files:",
            validate=PathValidator(is_dir=True, message="Directory does not exist"),
            only_directories=True
        ).execute()
        
        if not directory or not os.path.exists(directory):
            self.console.print("Error: Directory does not exist", style="red")
            return None
            
        # Find all bag files
        with self.show_loading("Searching for bag files...") as progress:
            progress.add_task(description="Searching...")
            bag_files = self._find_bag_files(directory)
            
        if not bag_files:
            self.console.print("No bag files found in the directory", style="yellow")
            return None
            
        # Create choices for selection with relative paths
        choices = []
        for f in bag_files:
            # Get relative path if possible
            try:
                rel_path = os.path.relpath(f, directory)
            except ValueError:
                # Fall back to basename if on different drives
                rel_path = os.path.basename(f)
                
            file_size_mb = os.path.getsize(f) / (1024*1024)
            choices.append(
                Choice(title=f"{rel_path} ({file_size_mb:.1f} MB)", value=f)
            )
        
        
        # Select files
        selected = inquirer.checkbox(
            message="Select bag files to process:",
            choices=choices,
            instruction="[space] to select/unselect files \n[enter] to confirm \n[a] to select all \n[i] to invert selection",
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one file",
        ).execute()
        
        if not selected:
            return None
            
        return selected

    def _run_quick_filter(self):
        """Run quick filter workflow"""
        # Get input method
        input_method = inquirer.select(
            message="Select input method:",
            choices=[
                Choice(value="single", name="1. Single bag file"),
                Choice(value="multiple", name="2. Multiple bag files from directory"),
                Choice(value="back", name="3. Back")
            ]
        ).execute()
        
        if not input_method or input_method == "back":
            return
            
        if input_method == "single":
            # Get input bag
            input_bag = inquirer.filepath(
                message="Enter input bag file path:",
                validate=PathValidator(is_file=True, message="File does not exist"),
                filter=lambda x: x if x.endswith('.bag') else None,
                invalid_message="File must be a .bag file"
            ).execute()
            
            if not input_bag:
                return
                
            # Load bag info
            with self.show_loading("Loading bag file...") as progress:
                progress.add_task(description="Loading...")
                self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
            
            # Ask user what to do next
            next_action = inquirer.select(
                message="What would you like to do?",
                choices=[
                    Choice(value="info", name="1. Show bag information"),
                    Choice(value="filter", name="2. Filter bag file"),
                    Choice(value="back", name="3. Back")
                ]
            ).execute()
            
            if next_action == "back":
                return
            elif next_action == "info":
                self._show_bag_info(input_bag, self.topics, self.connections, self.time_range)
                return
                
            # Get output bag
            output_bag = inquirer.filepath(
                message="Enter output bag file path:",
                default=os.path.splitext(input_bag)[0] + "_filtered.bag",
                validate=lambda x: x.endswith('.bag') or "File must be a .bag file"
            ).execute()
            
            if not output_bag:
                return
                
            # Get filter method
            filter_method = inquirer.select(
                message="Select filter method:",
                choices=[
                    Choice(value="whitelist", name="1. Use whitelist"),
                    Choice(value="manual", name="2. Select topics manually"),
                    Choice(value="back", name="3. Back")
                ]
            ).execute()
            
            if not filter_method or filter_method == "back":
                return
                
            # Process single file
            self._process_single_bag(input_bag, output_bag, filter_method)
            
        else:  # multiple
            # Get directory path
            directory = inquirer.filepath(
                message="Enter directory path:",
                validate=PathValidator(is_dir=True, message="Directory does not exist"),
                only_directories=True
            ).execute()
            
            if not directory:
                return
                
            # Find and select bag files
            bag_files = self._find_bag_files(directory)
            if not bag_files:
                rprint(Panel("No bag files found in directory", style="red"))
                return
                
            # Create file selection choices
            file_choices = [
                Choice(
                    value=f,
                    name=f"{os.path.relpath(f, directory)} ({os.path.getsize(f)/1024/1024:.1f} MB)"
                ) for f in bag_files
            ]
            def bag_list_transformer(result):
                return f"{len(result)} files selected\n" + '\n'.join([f"{bag}" for bag in result])
            # Select files
            selected_files = inquirer.checkbox(
                message="Select bag files to process:",
                choices=file_choices,
                instruction="[space] to select/unselect, [enter] to confirm",
                validate=lambda result: len(result) > 0,
                invalid_message="Please select at least one file",
                transformer=bag_list_transformer,
            ).execute()
            
            if not selected_files:
                return
                
            if "all" in selected_files:
                selected_files = bag_files
                
            # Get filter method
            filter_method = inquirer.select(
                message="Select filter method:",
                choices=[
                    Choice(value="whitelist", name="1. Use whitelist"),
                    Choice(value="manual", name="2. Select topics manually"),
                    Choice(value="back", name="3. Back")
                ]
            ).execute()
            
            if not filter_method or filter_method == "back":
                return
                
            # Load first bag file to get topics for selection
            with self.show_loading("Loading bag file for topic selection...") as progress:
                progress.add_task(description="Loading...")
                self.topics, self.connections, self.time_range = self.parser.load_bag(selected_files[0])
            
            # Get whitelist or selected topics once for all files
            whitelist = None
            if filter_method == "whitelist":
                # Get whitelist file
                whitelist_dir = "whitelists"
                if not os.path.exists(whitelist_dir):
                    self.console.print("No whitelists found", style="yellow")
                    return
                    
                whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
                if not whitelists:
                    self.console.print("No whitelists found", style="yellow")
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
                whitelist = self.parser.load_whitelist(whitelist_path)
                if not whitelist:
                    return
                    
            elif filter_method == "manual":
                whitelist = self._select_topics(self.topics, self.connections)
                if not whitelist:
                    return
                
            # Create progress display for all files
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=False,
            ) as progress:
                # Create tasks for all files
                tasks = {}
                for bag_file in selected_files:
                    rel_path = os.path.relpath(bag_file, directory)
                    task = progress.add_task(
                        f"Waiting: {rel_path}",
                        total=100,
                        style="dim"
                    )
                    tasks[bag_file] = task
                
                # Process each file
                for bag_file in selected_files:
                    rel_path = os.path.relpath(bag_file, directory)
                    task = tasks[bag_file]
                    
                    try:
                        # Update task to show it's being processed
                        progress.update(task, description=f"Processing: {rel_path}", style="yellow")
                        
                        # Create output path
                        output_bag = os.path.splitext(bag_file)[0] + "_filtered.bag"
                        
                        # Process file with the selected whitelist
                        self._process_single_bag(
                            bag_file,
                            output_bag,
                            filter_method,
                            whitelist=whitelist,  # Pass the pre-selected whitelist
                            progress_context=progress,
                            task_id=task
                        )
                        
                        # Update task to show success with green color
                        progress.update(task, description=f"[green]✓ {rel_path}[/green]")
                        
                    except Exception as e:
                        # Update task to show failure with red color
                        progress.update(task, description=f"[red]✗ {rel_path}: {str(e)}[/red]")
                        logger.error(f"Error processing {bag_file}: {str(e)}", exc_info=True)
                    
                    # Update progress
                    progress.update(task, completed=100)
                    
            # Show final summary with color-coded results
            success_count = sum(1 for task in tasks.values() if "✓" in progress.tasks[task].description)
            fail_count = sum(1 for task in tasks.values() if "✗" in progress.tasks[task].description)
            
            summary = (
                f"Processing Complete!\n"
                f"• Successfully processed: {success_count} files\n"
                f"• Failed: {fail_count} files"
            )
            
            if fail_count == 0:
                rprint(Panel(summary,  title="[bold]Results[/bold]"))
            else:
                rprint(Panel(summary,  title="[bold]Results[/bold]"))
            
    def _process_single_bag(self, input_bag: str, output_bag: str, filter_method: str, 
                          whitelist: Optional[List[str]] = None,
                          progress_context: Optional[Progress] = None, task_id: Optional[int] = None):
        """Process a single bag file"""
        # Load bag info
        if progress_context:
            # In batch mode, use the provided progress context
            progress_context.update(task_id, description=f"Loading: {os.path.basename(input_bag)}")
            self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
        else:
            # In single file mode, use independent loading animation
            with self.show_loading("Loading bag file...") as progress:
                progress.add_task(description="Loading...")
                self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
        
        # Get filter parameters based on method if not provided
        if whitelist is None:
            if filter_method == "whitelist":
                # Get whitelist file
                whitelist_dir = "whitelists"
                if not os.path.exists(whitelist_dir):
                    self.console.print("No whitelists found", style="yellow")
                    return
                    
                whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
                if not whitelists:
                    self.console.print("No whitelists found", style="yellow")
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
                whitelist = self.parser.load_whitelist(whitelist_path)
                if not whitelist:
                    return
                    
            elif filter_method == "manual":
                whitelist = self._select_topics(self.topics, self.connections)
                if not whitelist:
                    return
                
        # Filter bag
        if progress_context:
            # In batch mode, use the provided progress context
            progress_context.update(task_id, description=f"Filtering: {os.path.basename(input_bag)}")
            self.parser.filter_bag(input_bag, output_bag, whitelist)
        else:
            # In single file mode, use independent loading animation
            with self.show_loading("Filtering bag file...") as progress:
                progress.add_task(description="Processing...")
                self.parser.filter_bag(input_bag, output_bag, whitelist)
        
        # Show results
        if not progress_context:  # Only show stats for single file processing
            self._show_filter_stats(input_bag, output_bag)
            
        
    def _select_time_range(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Select time range"""
        # Get start time
        start_time = inquirer.text(
            message="Enter start time (YY/MM/DD HH:MM:SS):",
            validate=lambda x: TimeUtil.is_valid_time_format(x),
            invalid_message="Invalid time format"
        ).execute()
        
        if not start_time:
            return None
            
        # Get end time
        end_time = inquirer.text(
            message="Enter end time (YY/MM/DD HH:MM:SS):",
            validate=lambda x: TimeUtil.is_valid_time_format(x),
            invalid_message="Invalid time format"
        ).execute()
        
        if not end_time:
            return None
            
        try:
            return TimeUtil.convert_time_range_to_tuple(start_time, end_time)
        except Exception as e:
            rprint(Panel(f"Error parsing time range: {str(e)}", style="red"))
            return None

    def _run_whitelist_manager(self):
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
        with self.show_loading("Loading bag file...") as progress:
            progress.add_task(description="Loading...")
            topics, connections, _ = self.parser.load_bag(input_bag)
        
        # Select topics
        selected_topics = self._select_topics(topics, connections)
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
            f.write(f"# Source: {input_bag}\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for topic in sorted(selected_topics):
                f.write(f"{topic}\n")
        
        self.console.print(f"\nSaved whitelist to: {output}", style="green")
        
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
    
    def _show_bag_info(self, bag_path: str, topics: List[str], connections: dict, time_range: tuple):
        """Show bag file information"""
        file_size = os.path.getsize(bag_path)
        file_size_mb = file_size / (1024 * 1024)
        
        self.console.print("\nBag Summary:", style="bold green")
        self.console.print("─" * 80)
        self.console.print(f"File Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
        self.console.print(f"Location: {os.path.abspath(bag_path)}")
        self.console.print(f"\nTopics: {len(topics)} total")
        self.console.print("─" * 80)
        
        for topic in sorted(topics):
            msg_type = connections[topic]
            self.console.print(f"• {topic:<40} {msg_type}")
    
    def _show_topics(self, topics: List[str], connections: dict):
        """Show topics with message types"""
        self.console.print("\nTopics List:", style="bold green")
        self.console.print("─" * 80)
        self.console.print(f"{'Topic':<50} {'Type':<35}")
        self.console.print("─" * 80)
        
        for topic in sorted(topics):
            self.console.print(f"{topic:<50} {connections[topic]}")
    
    def _browse_whitelists(self):
        """Browse and view whitelist files"""
        # Get all whitelist files
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style="yellow")
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style="yellow")
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
            
        self.console.print(f"\nWhitelist: {selected}", style="bold green")
        self.console.print("─" * 80)
        self.console.print(content)
    
    def _select_topics(self, topics: List[str], connections: dict) -> Optional[List[str]]:
        """Select topics manually"""
        topic_choices = sorted(topics)
        
        # Display usage instructions
        self.console.print("\nUsage Instructions:",style="bold magenta")
        self.console.print("1. [magenta]Type to search[/magenta]")
        self.console.print("2. [magenta]↑/↓[/magenta] to navigate options")
        self.console.print("3. [magenta]Tab[/magenta] to select and move to next item")
        self.console.print("4. [magenta]Shift+Tab[/magenta] to select and move to previous item")
        self.console.print("5. [magenta]Ctrl+A[/magenta] to select all")
        self.console.print("6. [magenta]Enter[/magenta] to confirm selection\n")
        
        selected_topics = inquirer.fuzzy(
            message="Select topics to include:",
            choices=topic_choices,
            multiselect=True,
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one topic",
            transformer=lambda result: f"{len(result)} topic{'s' if len(result) > 1 else ''} selected",
            max_height="70%",
            instruction="",
            marker="● ",
            border=True,
            cycle=True,
        ).execute()
        
        return selected_topics
    
    def _ask_for_output_bag(self) -> Optional[str]:
        """Ask for output bag path"""
        # Get default output name based on input bag
        input_name = os.path.basename(self.input_bag)
        default_name = os.path.splitext(input_name)[0] + "_filtered.bag"
        default_path = os.path.join(os.path.dirname(self.input_bag), default_name)
        
        while True:
            output = inquirer.filepath(
                message="Enter output bag path:",
                default=default_path,
                validate=lambda x: x.endswith('.bag') or "File must be a .bag file"
            ).execute()
            
            if not output:
                return None
                
            # Check if file exists
            if os.path.exists(output):
                overwrite = inquirer.confirm(
                    message=f"File {output} already exists. Overwrite?",
                    default=False
                ).execute()
                
                if not overwrite:
                    continue
            
            return output
    
    def _delete_whitelist(self):
        """Delete a whitelist file"""
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style="yellow")
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style="yellow")
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
            self.console.print(f"\nDeleted whitelist: {selected}", style="green")
        except Exception as e:
            self.console.print(f"\nError deleting whitelist: {str(e)}", style="red")

    def _show_current_bag_info(self, input_bag: str, topics: List[str]):
        """Show current bag information"""
        # Load bag info
        with self.show_loading("Loading bag file...") as progress:
            progress.add_task(description="Loading...")
            self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
        
        # Show bag info
        self._show_bag_info(input_bag, self.topics, self.connections, self.time_range)

    def _show_filter_stats(self, input_bag: str, output_bag: str):
        """Show filtering statistics"""
        input_size = os.path.getsize(input_bag)
        output_size = os.path.getsize(output_bag)
        input_size_mb = input_size / (1024 * 1024)
        output_size_mb = output_size / (1024 * 1024)
        reduction_ratio = (1 - output_size / input_size) * 100
        
        stats = (
            f"Filter Statistics:\n"
            f"• Size: {input_size_mb:.2f} MB -> {output_size_mb:.2f} MB\n"
            f"• Reduction: {reduction_ratio:.1f}%\n"
            f"• Topics: {len(self.topics)} -> {len(self.connections)}"
        )
        rprint(Panel(stats, style="bold green", title="[bold]Filter Results[/bold]"))
        
        self.console.print(f"\nFilter completed: {output_bag}", style="green")

# Typer commands
@app.command()
def cli():
    """Interactive CLI mode with menu interface"""
    tool = CliTool()
    tool.run_cli()

@app.command()
def filter(
    input_bag: str = typer.Argument(..., help="Input bag file path"),
    output_bag: str = typer.Argument(..., help="Output bag file path"),
    whitelist: Optional[str] = typer.Option(None, help="Whitelist file path")
):
    """Filter a bag file using whitelist or manual selection"""
    tool = CliTool()
    tool.filter_bag(input_bag, output_bag, whitelist_path=whitelist)

def main():
    """Entry point for the CLI tool"""
    app()

if __name__ == "__main__":
    main() 