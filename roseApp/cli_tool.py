import os
import time
from typing import Optional, List
import questionary
from questionary import Choice, Style
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
import typer

from .core.parser import create_parser, ParserType
from .core.util import get_logger

logger = get_logger("RoseCLI-Tool")

# Define questionary style
CUSTOM_STYLE = Style([
    ('question', '#ffffff bold'),
    ('answer', '#2aa198'),      # Cyan
    ('path', '#268bd2'),        # Blue
    ('highlighted', '#859900 bold'),  # Green
    ('selected', '#859900'),    # Green
    ('instruction', '#268bd2'), # Blue
    ('text', '#ffffff'),
    ('completion-menu', 'bg:#333333 #ffffff'),
    ('completion-menu-selection', 'bg:#859900 #000000')
])

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
            input_bag = questionary.path(
                message,
                only_directories=False,
                style=CUSTOM_STYLE
            ).ask()
            
            if input_bag is None:  # User cancelled
                return None
            
            # Validate the input
            if not os.path.exists(input_bag):
                self.console.print("Error: File does not exist", style="red")
                continue
                
            if not input_bag.endswith('.bag'):
                self.console.print("Error: File must be a .bag file", style="red")
                continue
                
            return input_bag
    
    def show_loading(self, message: str):
        """Show a loading spinner with message"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        )
    
    def _show_current_bag_info(self, input_bag: str, topics: List[str]):
        """Show current bag file information in a panel"""
        if not input_bag:
            return
            
        file_size = os.path.getsize(input_bag)
        file_size_mb = file_size / (1024 * 1024)
        
        bag_info = (
            f"Current Bag: {os.path.basename(input_bag)}\n"
            f"Size: {file_size_mb:.2f} MB | Topics: {len(topics)}"
        )
        rprint(Panel(bag_info, style="bold blue", title="[bold]Bag Info[/bold]"))
    
    def run_cli(self):
        """Run the CLI tool with improved menu logic"""
        try:
            self.show_banner()
            
            while True:
                # Show main menu
                action = questionary.select(
                    "Select action:",
                    choices=[
                        Choice("1. Bag Editor - View and filter bag files", "filter"),
                        Choice("2. Whitelist - Manage topic whitelists", "whitelist"),
                        Choice("3. Exit", "exit")
                    ],
                    style=CUSTOM_STYLE
                ).ask()
                
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
        directory = questionary.path(
            "Enter directory path to search for bag files:",
            only_directories=True,
            style=CUSTOM_STYLE
        ).ask()
        
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
        
        # Add "Select All" option
        choices.insert(0, Choice(title="[Select All]", value="all"))
        
        # Select files
        selected = questionary.checkbox(
            "Select bag files to process:",
            choices=choices,
            instruction="\n[space] to select/unselect files \n[enter] to confirm \n[a] to select all \n[i] to invert selection",
            style=CUSTOM_STYLE
        ).ask()
        
        if not selected:
            return None
            
        # Handle "Select All" option
        if "all" in selected:
            selected = [f for f in bag_files if f != "all"]
            
        return selected

    def _run_quick_filter(self):
        """Run quick filter workflow"""
        # Select input method
        input_method = questionary.select(
            "Select input method:",
            choices=[
                Choice("1. Single bag file", "single"),
                Choice("2. Multiple bag files from directory", "multiple"),
                Choice("3. Back", "back")
            ],
            style=CUSTOM_STYLE
        ).ask()
        
        if input_method == "back":
            return
        elif input_method == "single":
            # Get input bag
            self.input_bag = self.ask_for_bag("Enter input bag file path:")
            if not self.input_bag:
                return
                
            # Load bag file
            with self.show_loading("Loading bag file...") as progress:
                progress.add_task(description="Loading...")
                self.topics, self.connections, self.time_range = self.parser.load_bag(self.input_bag)
            
            # Show bag info
            self._show_current_bag_info(self.input_bag, self.topics)
            
            # Process single file
            self._process_single_bag(self.input_bag)
        else:
            # Select multiple files
            bag_files = self._select_bag_files()
            if not bag_files:
                return
                
            # Select filter method for all files
            method = questionary.select(
                "Select filter method for all files:",
                choices=[
                    Choice("1. Use whitelist file", "whitelist"),
                    Choice("2. Select topics manually", "manual"),
                    Choice("3. Back", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
            if method == "back":
                return
                
            # Get selected topics
            selected_topics = None
            whitelist_path = None
            if method == "whitelist":
                whitelist_path = self._select_whitelist()
                if not whitelist_path:
                    return
            else:
                # Load first bag to get topics
                with self.show_loading("Loading bag file...") as progress:
                    progress.add_task(description="Loading...")
                    self.topics, self.connections, _ = self.parser.load_bag(bag_files[0])
                selected_topics = self._select_topics(self.topics, self.connections)
                if not selected_topics:
                    return
            
            # Process all files with a progress display
            self.console.print("\nStarting batch processing...", style="bold blue")
            
            # Display all files that will be processed
            self.console.print("\nFiles to be processed:", style="bold yellow")
            for i, bag_file in enumerate(bag_files, 1):
                # Try to get a shorter representation of the path
                try:
                    display_path = os.path.relpath(bag_file)
                except ValueError:
                    display_path = bag_file
                self.console.print(f"{i}. {display_path}")
            self.console.print(f"\n{len(bag_files)} files in total\n", style="bold yellow")
            
            # Create a progress display with one task per file
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=False,
            ) as progress:
                # Create a task for each file (all visible but only current one active)
                file_tasks = {}
                for i, bag_file in enumerate(bag_files):
                    # Try to get a shorter representation of the path
                    try:
                        display_path = os.path.relpath(bag_file)
                    except ValueError:
                        display_path = os.path.basename(bag_file)
                        
                    # Add task with status indicator
                    task_id = progress.add_task(
                        description=f"[dim]{i+1}/{len(bag_files)}[/dim] {display_path} [dim](waiting)[/dim]", 
                        total=None,
                        visible=True
                    )
                    file_tasks[bag_file] = task_id
                
                # Process each file sequentially
                for i, bag_file in enumerate(bag_files):
                    # Try to get a shorter representation of the path
                    try:
                        display_path = os.path.relpath(bag_file)
                    except ValueError:
                        display_path = os.path.basename(bag_file)
                    
                    # Update all tasks to show current progress
                    for j, bf in enumerate(bag_files):
                        if j < i:
                            # Already processed
                            progress.update(file_tasks[bf], description=f"[dim]{j+1}/{len(bag_files)}[/dim] {os.path.relpath(bf, start=os.getcwd()) if os.path.isabs(bf) else bf} [green]✓[/green]")
                        elif j > i:
                            # Waiting
                            progress.update(file_tasks[bf], description=f"[dim]{j+1}/{len(bag_files)}[/dim] {os.path.relpath(bf, start=os.getcwd()) if os.path.isabs(bf) else bf} [dim](processing)[/dim]")
                    
                    # Update current task to show it's active
                    progress.update(file_tasks[bag_file], description=f"[bold]{i+1}/{len(bag_files)} {display_path}[/bold] [yellow](处理中)[/yellow]")
                    
                    # Prepare output path
                    output_bag = os.path.join(
                        os.path.dirname(bag_file),
                        os.path.splitext(os.path.basename(bag_file))[0] + "_filtered.bag"
                    )
                    
                    # Process the file
                    try:
                        success = self.filter_bag(
                            bag_file, 
                            output_bag, 
                            selected_topics, 
                            whitelist_path, 
                            show_stats=False,
                            progress_context=progress
                        )
                        
                        if success:
                            # Mark task as completed
                            progress.update(file_tasks[bag_file], description=f"[dim]{i+1}/{len(bag_files)}[/dim] {display_path} [green]✓[/green]")
                        else:
                            # Mark task as failed
                            progress.update(file_tasks[bag_file], description=f"[dim]{i+1}/{len(bag_files)}[/dim] {display_path} [red]✗[/red]")
                    except Exception as e:
                        # Mark task as failed with error message
                        progress.update(file_tasks[bag_file], description=f"[dim]{i+1}/{len(bag_files)}[/dim] {display_path} [red]✗ - {str(e)}[/red]")
                
            self.console.print("\n所有文件处理完成！", style="green")

    def _process_single_bag(self, input_bag: str):
        """Process a single bag file"""
        while True:
            # Select action
            action = questionary.select(
                "Select action:",
                choices=[
                    Choice("1. Show bag information", "info"),
                    Choice("2. Filter bag file", "filter"),
                    Choice("3. Back", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
            if action == "back":
                return
            elif action == "info":
                self._show_bag_info(input_bag, self.topics, self.connections, self.time_range)
                continue
            elif action == "filter":
                # Select filter method
                method = questionary.select(
                    "Select filter method:",
                    choices=[
                        Choice("1. Use whitelist file", "whitelist"),
                        Choice("2. Select topics manually", "manual"),
                        Choice("3. Back", "back")
                    ],
                    style=CUSTOM_STYLE
                ).ask()
                
                if method == "back":
                    continue
                    
                # Get selected topics
                selected_topics = None
                whitelist_path = None
                if method == "whitelist":
                    whitelist_path = self._select_whitelist()
                    if not whitelist_path:
                        continue
                else:
                    selected_topics = self._select_topics(self.topics, self.connections)
                    if not selected_topics:
                        continue
                
                # Get output path
                output_bag = self._ask_for_output_bag()
                if not output_bag:
                    continue
                    
                # Run filter
                self.filter_bag(input_bag, output_bag, selected_topics, whitelist_path)
                
                # Ask what to do next
                next_action = questionary.select(
                    "What would you like to do next?",
                    choices=[
                        Choice("1. Filter another bag", "continue"),
                        Choice("2. Back", "back")
                    ],
                    style=CUSTOM_STYLE
                ).ask()
                
                if next_action == "continue":
                    self._run_quick_filter()
                    return
                elif next_action == "back":
                    continue
    
    def _run_whitelist_manager(self):
        """Run whitelist management workflow"""
        while True:
            action = questionary.select(
                "Whitelist Management:",
                choices=[
                    Choice("1. Create new whitelist", "create"),
                    Choice("2. View whitelist", "view"),
                    Choice("3. Delete whitelist", "delete"),
                    Choice("4. Back", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
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
        
        # Show bag info
        self._show_current_bag_info(input_bag, topics)
        
        # Select topics
        selected_topics = self._select_topics(topics, connections)
        if not selected_topics:
            return
            
        # Save whitelist
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_path = f"whitelists/whitelist_{timestamp}.txt"
        
        use_default = questionary.confirm(
            f"Use default path? ({default_path})",
            default=True,
            style=CUSTOM_STYLE
        ).ask()
        
        if use_default:
            output = default_path
        else:
            output = questionary.path(
                "Enter save path:",
                default="whitelists/my_whitelist.txt",
                only_directories=False,
                style=CUSTOM_STYLE
            ).ask()
            
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
        next_action = questionary.select(
            "What would you like to do next?",
            choices=[
                Choice("1. Create another whitelist", "continue"),
                Choice("2. Back", "back")
            ],
            style=CUSTOM_STYLE
        ).ask()
        
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
        selected = questionary.select(
            "Select whitelist to view:",
            choices=whitelists,
            style=CUSTOM_STYLE
        ).ask()
        
        if not selected:
            return
            
        # Show whitelist contents
        path = os.path.join(whitelist_dir, selected)
        with open(path) as f:
            content = f.read()
            
        self.console.print(f"\nWhitelist: {selected}", style="bold green")
        self.console.print("─" * 80)
        self.console.print(content)
    
    def _select_whitelist(self) -> Optional[str]:
        """Select a whitelist file"""
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style="yellow")
            return None
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style="yellow")
            return None
            
        selected = questionary.select(
            "Select whitelist:",
            choices=whitelists,
            style=CUSTOM_STYLE
        ).ask()
        
        if not selected:
            return None
            
        return os.path.join(whitelist_dir, selected)
    
    def _select_topics(self, topics: List[str], connections: dict) -> Optional[List[str]]:
        """Select topics manually"""
        topic_choices = [
            Choice(title=f"{topic:<50} {connections[topic]}", value=topic)
            for topic in sorted(topics)
        ]
        
        selected_topics = questionary.checkbox(
            "Select topics to include:",
            choices=topic_choices,
            instruction="\n[space] to select/unselect topics \n[enter] to confirm \n[a] to select all \n[i] to invert selection",
            style=CUSTOM_STYLE
        ).ask()
        
        return selected_topics
    
    def _ask_for_output_bag(self) -> Optional[str]:
        """Ask for output bag path"""
        # Get default output name based on input bag
        input_name = os.path.basename(self.input_bag)
        default_name = os.path.splitext(input_name)[0] + "_filtered.bag"
        default_path = os.path.join(os.path.dirname(self.input_bag), default_name)
        
        while True:
            output = questionary.path(
                "Enter output bag path:",
                default=default_path,
                only_directories=False,
                style=CUSTOM_STYLE
            ).ask()
            
            if not output:
                return None
                
            if not output.endswith('.bag'):
                self.console.print("Error: Output file must be a .bag file", style="red")
                continue
                
            # Check if file exists
            if os.path.exists(output):
                overwrite = questionary.confirm(
                    f"File {output} already exists. Overwrite?",
                    default=False,
                    style=CUSTOM_STYLE
                ).ask()
                
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
        selected = questionary.select(
            "Select whitelist to delete:",
            choices=whitelists,
            style=CUSTOM_STYLE
        ).ask()
        
        if not selected:
            return
            
        # Confirm deletion
        if not questionary.confirm(
            f"Are you sure you want to delete '{selected}'?",
            default=False,
            style=CUSTOM_STYLE
        ).ask():
            return
            
        # Delete the file
        path = os.path.join(whitelist_dir, selected)
        try:
            os.remove(path)
            self.console.print(f"\nDeleted whitelist: {selected}", style="green")
        except Exception as e:
            self.console.print(f"\nError deleting whitelist: {str(e)}", style="red")

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