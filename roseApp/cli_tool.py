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
    ('instruction', '#93a1a1'), # Gray
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

class CliTool:
    def __init__(self):
        self.console = Console()
        self.parser = create_parser(ParserType.PYTHON)
        
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
    
    def run(self):
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
    
    def _run_quick_filter(self):
        """Run quick filter workflow"""
        # Get input bag
        input_bag = self.ask_for_bag("Enter input bag file path:")
        if not input_bag:
            return
            
        # Load bag file
        with self.show_loading("Loading bag file...") as progress:
            progress.add_task(description="Loading...")
            topics, connections, time_range = self.parser.load_bag(input_bag)
        
        # Show bag info
        self._show_current_bag_info(input_bag, topics)
        
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
                self._show_bag_info(input_bag, topics, connections, time_range)
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
                selected_topics = []
                if method == "whitelist":
                    whitelist_path = self._select_whitelist()
                    if not whitelist_path:
                        continue
                    selected_topics = self.parser.load_whitelist(whitelist_path)
                else:
                    selected_topics = self._select_topics(topics, connections)
                    if not selected_topics:
                        continue
                
                # Get output path
                output_bag = self._ask_for_output_bag()
                if not output_bag:
                    continue
                    
                # Run filter
                start_time = time.time()
                with self.show_loading("Filtering bag file...") as progress:
                    progress.add_task(description="Processing...")
                    self.parser.filter_bag(input_bag, output_bag, selected_topics)
                end_time = time.time()
                
                # Show statistics
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
                    f"• Topics: {len(topics)} -> {len(selected_topics)}"
                )
                rprint(Panel(stats, style="bold green", title="[bold]Filter Results[/bold]"))
                
                self.console.print(f"\nFilter completed: {output_bag}", style="green")
                
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
            instruction="Use space to select/unselect topics",
            style=CUSTOM_STYLE
        ).ask()
        
        return selected_topics
    
    def _ask_for_output_bag(self) -> Optional[str]:
        """Ask for output bag path"""
        while True:
            output = questionary.path(
                "Enter output bag path:",
                default="filtered.bag",
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

def main():
    """Entry point for the CLI tool"""
    tool = CliTool()
    tool.run() 