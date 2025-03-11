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
    
    def run_inspector(self):
        """Run the inspector tool"""
        input_bag = None
        topics = None
        connections = None
        time_range = None
        
        while True:
            # Show current bag info if available
            if input_bag:
                self._show_current_bag_info(input_bag, topics)
            
            # Show options first
            action = questionary.select(
                "Select action:",
                choices=[
                    Choice("Show bag information", "info"),
                    Choice("Browse topics", "topics"),
                    Choice("Create whitelist", "create"),
                    Choice("Browse whitelists", "browse"),
                    Choice("Back to main menu", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
            if action == "back":
                return
                
            # Browse whitelists doesn't need bag file
            if action == "browse":
                self._browse_whitelists()
                continue
            
            # For actions that need bag file, load it if not already loaded
            if action in ["info", "topics", "create"]:
                if not input_bag:
                    input_bag = self.ask_for_bag()
                    if not input_bag:
                        continue  # If user cancels bag selection, go back to menu
                    
                    # Load bag file
                    with self.show_loading("Loading bag file...") as progress:
                        progress.add_task(description="Loading...")
                        topics, connections, time_range = self.parser.load_bag(input_bag)
                    
                    # Show bag info after loading
                    self._show_current_bag_info(input_bag, topics)
                
                # Execute the action
                if action == "info":
                    self._show_bag_info(input_bag, topics, connections, time_range)
                elif action == "topics":
                    self._show_topics(topics, connections)
                elif action == "create":
                    self._create_whitelist(input_bag, topics, connections)
            
            # After actions that used a bag file, ask what to do next
            if action in ["info", "topics", "create"]:
                next_action = questionary.select(
                    "What would you like to do next?",
                    choices=[
                        Choice("Continue with current bag", "continue"),
                        Choice("Use different bag", "change"),
                        Choice("Back to action menu", "menu")
                    ],
                    style=CUSTOM_STYLE
                ).ask()
                
                if next_action == "change":
                    input_bag = None
                    topics = None
                    connections = None
                    time_range = None
    
    def run_filter(self):
        """Run the filter tool"""
        input_bag = None
        topics = None
        connections = None
        
        while True:
            # Show current bag info if available
            if input_bag:
                self._show_current_bag_info(input_bag, topics)
            
            if not input_bag:
                # Ask for input bag
                input_bag = self.ask_for_bag("Enter input bag file path:")
                if not input_bag:
                    return
                
                # Load bag file
                with self.show_loading("Loading bag file...") as progress:
                    progress.add_task(description="Loading...")
                    topics, connections, _ = self.parser.load_bag(input_bag)
                
                # Show bag info after loading
                self._show_current_bag_info(input_bag, topics)
            
            # Ask for filter method
            method = questionary.select(
                "Select filter method:",
                choices=[
                    Choice("Use whitelist file", "whitelist"),
                    Choice("Select topics manually", "manual"),
                    Choice("Change bag file", "change"),
                    Choice("Back to main menu", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
            if method == "back":
                return
            
            if method == "change":
                input_bag = None
                topics = None
                connections = None
                continue
            
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
            
            # Ask for output path
            output_bag = self._ask_for_output_bag()
            if not output_bag:
                continue
                
            # Run filter
            with self.show_loading("Filtering bag file...") as progress:
                progress.add_task(description="Processing...")
                self.parser.filter_bag(input_bag, output_bag, selected_topics)
            
            self.console.print(f"\nFilter completed: {output_bag}", style="green")
            
            # Ask what to do next
            next_action = questionary.select(
                "What would you like to do next?",
                choices=[
                    Choice("Continue with current bag", "continue"),
                    Choice("Use different bag", "change"),
                    Choice("Back to main menu", "back")
                ],
                style=CUSTOM_STYLE
            ).ask()
            
            if next_action == "back":
                return
            elif next_action == "change":
                input_bag = None
                topics = None
                connections = None
    
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
    
    def _create_whitelist(self, input_bag: str, topics: List[str], connections: dict):
        """Create whitelist from topics"""
        # Format topics for selection
        topic_choices = [
            Choice(title=f"{topic:<50} {connections[topic]}", value=topic)
            for topic in sorted(topics)
        ]
        
        # Select topics
        selected_topics = questionary.checkbox(
            "Select topics to include:",
            choices=topic_choices,
            instruction="[space] select/unselect [enter] confirm",
            style=CUSTOM_STYLE
        ).ask()
        
        if not selected_topics:
            return
            
        # Ask for save location
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
            instruction="[space] select/unselect [enter] confirm",
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
    
    def run(self):
        """Run the CLI tool"""
        try:
            self.show_banner()
            
            while True:
                action = questionary.select(
                    "Select tool:",
                    choices=[
                        Choice("Inspector - View bag info and manage whitelists", "inspector"),
                        Choice("Filter - Filter bag files", "filter"),
                        Choice("Exit", "exit")
                    ],
                    style=CUSTOM_STYLE
                ).ask()
                
                if action == "exit":
                    break
                elif action == "inspector":
                    self.run_inspector()
                elif action == "filter":
                    self.run_filter()
                
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled by user", style="yellow")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.console.print(f"\nError: {str(e)}", style="red")

def main():
    """Entry point for the CLI tool"""
    tool = CliTool()
    tool.run() 