from sre_constants import SUCCESS
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from .theme import DIM_INFO, style, SUCCESS, YELLOW, INFO, ACCENT, PRIMARY  # Import colors and style
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
import os
from typing import List, Dict, Optional, Any, Union
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

ROSE_BANNER = """
██████╗  ██████╗ ███████╗███████╗
██╔══██╗██╔═══██╗██╔════╝██╔════╝
██████╔╝██║   ██║███████╗█████╗  
██╔══██╗██║   ██║╚════██║██╔══╝  
██║  ██║╚██████╔╝███████║███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝
"""

def build_banner():
    """Display the ROSE banner"""
    # Create title with link
    title = Text()
    title.append("ROS Bag Filter Tool") 
    subtitle = Text()
    subtitle.append("Github", style=f"{YELLOW} link https://github.com/hanxiaomax/rose")
    subtitle.append(" • ", style="dim")
    subtitle.append("Author", style=f"{YELLOW} link https://github.com/hanxiaomax")

    # Create banner content
    content = Text()
    content.append(ROSE_BANNER, style="")
    content.append("Yet another cross-platform and ROS Environment independent editor/filter tool for ROS bag files", style=f"dim {PRIMARY}")
    
    # Create panel with all elements
    panel = Panel(
        content,
        title=title,
        subtitle=subtitle,  
        border_style=YELLOW,  
        highlight=True
    )
    
    # Print the panel
    # self.console.print(panel)
    return panel
  
def print_usage_instructions(console:Console, is_fuzzy:bool = False):
    console.print("\nUsage Instructions:",style=f"bold {ACCENT}")
    if is_fuzzy:
        console.print(f"•  [{ACCENT}]Type to search[/{ACCENT}]")
    else:
        console.print(f"•  [{ACCENT}]Space[/{ACCENT}] to select/unselect") 
    console.print(f"•  [{ACCENT}]↑/↓[/{ACCENT}] to navigate options")
    console.print(f"•  [{ACCENT}]Tab[/{ACCENT}] to select and move to next item")
    console.print(f"•  [{ACCENT}]Shift+Tab[/{ACCENT}] to select and move to previous item")
    console.print(f"•  [{ACCENT}]Ctrl+A[/{ACCENT}] to select all")
    console.print(f"•  [{ACCENT}]Enter[/{ACCENT}] to confirm selection\n")


def collect_bag_files(directory: str) -> List[str]:
    """Recursively find all bag files in the given directory"""
    bag_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.bag'):
                bag_files.append(os.path.join(root, file))
    return sorted(bag_files)

def print_bag_info(console:Console, bag_path: str, topics: List[str], connections: dict, time_range: tuple):
    """Show bag file information using rich panels"""
    # Calculate file info
    file_size = os.path.getsize(bag_path)
    file_size_mb = file_size / (1024 * 1024)
    
    # Create basic bag info text
    bag_info = Text()
    bag_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {SUCCESS}")
    bag_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n",style=f"{DIM_INFO}")
    bag_info.append(f"Path: {os.path.abspath(bag_path)}\n",style=f"{DIM_INFO}")
    bag_info.append(f"Topics({len(topics)} in total):\n", style="bold")
    
    # First, display all topics
    for topic in sorted(topics):
        bag_info.append(f"• {topic:<40}", style=f"{SUCCESS}")
        bag_info.append(f"{connections[topic]}\n", style=f"{DIM_INFO}")
    
    panel = Panel(bag_info,
                  title=f"Bag Information",
                  border_style=INFO,
                  padding=(0, 1))
    
    console.print(panel)
    
    # Ask if user wants to filter topics
    while True:
        action = inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice(value="filter", name="1. Filter topics (fuzzy search)"),
                Choice(value="back", name="2. Back")
            ],
            style=style
        ).execute()
        
        if action == "back":
            return
        elif action == "filter":
            # Use the new select_topics_with_fuzzy function
            filtered_topics = ask_topics(console, topics)
            
            if not filtered_topics:
                console.print("No topics selected. Showing all topics.", style=YELLOW)
                continue
            
            # Create filtered topics panel
            filtered_info = Text()
            filtered_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {SUCCESS}")
            filtered_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n")
            filtered_info.append(f"Path: {os.path.abspath(bag_path)}\n")
            filtered_info.append(f"Filtered Topics({len(filtered_topics)} of {len(topics)}):\n", style="bold")
            
            for topic in sorted(filtered_topics):
                filtered_info.append(f"• {topic:<40}", style=PRIMARY)
                filtered_info.append(f"{connections[topic]}\n", style="dim")
            
            filtered_panel = Panel(filtered_info,
                                  title=f"Filtered Bag Information",
                                  border_style=SUCCESS,
                                  padding=(0, 1))
            
            console.print(filtered_panel)

def print_filter_stats(console:Console, input_bag: str, output_bag: str):
    """Show filtering statistics in a three-column table format comparing input, output and changes"""
    input_size = os.path.getsize(input_bag)
    output_size = os.path.getsize(output_bag)
    input_size_mb:float = input_size / (1024 * 1024)
    output_size_mb:float = output_size / (1024 * 1024)
    reduction_ratio = (1 - output_size / input_size) * 100
    
    table = Table(box=None, padding=(0, 2))
    table.add_column("Input", style=PRIMARY)
    table.add_column("Output", style=DIM_INFO)
    table.add_column("Changes", style=ACCENT)
    

    table.add_row(
        os.path.basename(input_bag),
        os.path.basename(output_bag),
        " "
    )

    table.add_row(
        f"{input_size_mb:.2f} MB",
        f"{output_size_mb:.2f} MB",
        f"↓ {reduction_ratio:.1f}% smaller"
    )
    

    console.print(Panel(table, title="Filter Results", border_style=PRIMARY))

def print_batch_filter_summary(console:Console, success_count: int, fail_count: int):
    """Show filtering results for batch processing
    
    Args:
        console: Rich console instance to print results
        success_count: Number of successfully processed files
        fail_count: Number of files that failed to process
    """
    total_processed = success_count + fail_count
    
    summary = (
        f"Processing Complete!\n"
        f"• Successfully processed: {success_count} files\n"
        f"• Failed: {fail_count} files"
    )
    
    if fail_count == 0:
        console.print(summary, style=f"{SUCCESS}")
    else:
        console.print(summary, style=f"{ACCENT}")

def ask_topics(console: Console, topics: List[str]) -> Optional[List[str]]:
    return ask_topics_with_fuzzy(
        console=console,
        topics=topics,
        message="Select topics:",
        require_selection=True,
        show_instructions=True
    )

def ask_topics_with_fuzzy(
    console: Console, 
    topics: List[str], 
    message: str = "Select topics:",
    require_selection: bool = True,
    show_instructions: bool = True,
    preselected: Optional[List[str]] = None
) -> List[str]:
    """Select topics using fuzzy search
    
    Args:
        console: Rich console instance for displaying messages
        topics: List of topics to select from
        message: Prompt message to display
        require_selection: Whether to require at least one topic to be selected
        show_instructions: Whether to show usage instructions
        preselected: List of topics to preselect
        
    Returns:
        List of selected topics
    """
    # Sort topics for consistent display
    topic_choices = sorted(topics)
    
    # Display usage instructions if requested
    if show_instructions:
        print_usage_instructions(console, is_fuzzy=True)
    
    # Prepare validation if required
    validate = None
    invalid_message = None
    if require_selection:
        validate = lambda result: len(result) > 0
        invalid_message = "Please select at least one topic"
    
    # Use fuzzy search to select topics
    selected_topics = inquirer.fuzzy(
        message=message,
        choices=topic_choices,
        multiselect=True,
        validate=validate,
        invalid_message=invalid_message,
        transformer=lambda result: f"{len(result)} topic{'s' if len(result) > 1 else ''} selected",
        max_height="70%",
        instruction="",
        marker="● ",
        border=True,
        cycle=True,
        style=style,
        default=preselected
    ).execute()
    
    return selected_topics


class PanelProgress(Progress):
    def __init__(self, *columns, title: Optional[str] = None, **kwargs):
        self.title = title
        super().__init__(*columns, **kwargs)

    def get_renderables(self):
        yield Panel(self.make_tasks_table(self.tasks), title=self.title)

def LoadingAnimation(title: Optional[str] = None, dismiss: bool = False):
    """Show a loading spinner with message in a panel
    
    Args:
        title (Optional[str], optional): The title of the panel. Defaults to None.
        dismiss (bool, optional): Whether to dismiss the panel after completion. Defaults to False.
    
    Returns:
        PanelProgress: A progress bar wrapped in a panel with optional title
    """
    return PanelProgress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),  # 设置为 None 以自适应宽度
        TaskProgressColumn(),
        TimeRemainingColumn(),
        title=title,
        transient=dismiss,  # 设置为 False 以保持任务完成后的显示
    )

