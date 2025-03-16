from rich.panel import Panel
from rich.text import Text
from .theme import style, GREEN, YELLOW, BLUE, PURPLE, ORANGE  # Import colors and style
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
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
    content.append("Yet another cross-platform and ROS Environment independent editor/filter tool for ROS bag files", style=f"dim {GREEN}")
    
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
    console.print("\nUsage Instructions:",style="bold magenta")
    if is_fuzzy:
        console.print("•  [magenta]Type to search[/magenta]")
    else:
        console.print("•  [magenta]Space[/magenta] to select/unselect") 
    console.print("•  [magenta]↑/↓[/magenta] to navigate options")
    console.print("•  [magenta]Tab[/magenta] to select and move to next item")
    console.print("•  [magenta]Shift+Tab[/magenta] to select and move to previous item")
    console.print("•  [magenta]Ctrl+A[/magenta] to select all")
    console.print("•  [magenta]Enter[/magenta] to confirm selection\n")


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
    bag_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {GREEN}")
    bag_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n")
    bag_info.append(f"Path: {os.path.abspath(bag_path)}\n")
    bag_info.append(f"Topics({len(topics)} in total):\n", style="bold")
    
    # First, display all topics
    for topic in sorted(topics):
        bag_info.append(f"• {topic:<40}", style=f"{PURPLE}")
        bag_info.append(f"{connections[topic]}\n", style="dim")
    
    panel = Panel(bag_info,
                  title=f"Bag Information",
                  border_style=BLUE,
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
            filtered_topics = select_topics_with_fuzzy(
                console=console,
                topics=topics,
                message="Search topics:",
                require_selection=False,
                show_instructions=True
            )
            
            if not filtered_topics:
                console.print("No topics selected. Showing all topics.", style=YELLOW)
                continue
            
            # Create filtered topics panel
            filtered_info = Text()
            filtered_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {GREEN}")
            filtered_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n")
            filtered_info.append(f"Path: {os.path.abspath(bag_path)}\n")
            filtered_info.append(f"Filtered Topics({len(filtered_topics)} of {len(topics)}):\n", style="bold")
            
            for topic in sorted(filtered_topics):
                filtered_info.append(f"• {topic:<40}", style=f"{PURPLE}")
                filtered_info.append(f"{connections[topic]}\n", style="dim")
            
            filtered_panel = Panel(filtered_info,
                                  title=f"Filtered Bag Information",
                                  border_style=GREEN,
                                  padding=(0, 1))
            
            console.print(filtered_panel)

def print_filter_stats(console:Console, input_bag: str, output_bag: str):
    """Show filtering statistics"""
    input_size = os.path.getsize(input_bag)
    output_size = os.path.getsize(output_bag)
    input_size_mb:float = input_size / (1024 * 1024)
    output_size_mb:float = output_size / (1024 * 1024)
    reduction_ratio = (1 - output_size / input_size) * 100
    
    stats = (
        f"Filter Statistics:\n"
        f"• Size: {input_size_mb:.2f} MB -> {output_size_mb:.2f} MB\n"
        f"• Reduction: {reduction_ratio:.1f}%"
    )
    console.print(Panel(stats, style=GREEN, title="Filter Results"))

def print_batch_filter_summary(console:Console, tasks: dict, progress: Progress):
    """Show filtering results for batch processing"""
    success_count = sum(1 for task in tasks.values() if "✓" in progress.tasks[task].description)
    fail_count = sum(1 for task in tasks.values() if "✗" in progress.tasks[task].description)
    
    summary = (
        f"Processing Complete!\n"
        f"• Successfully processed: {success_count} files\n"
        f"• Failed: {fail_count} files"
    )
    
    if fail_count == 0:
        console.print(Panel(summary,style="green", title="[bold]Results[/bold]"))
    else:
        console.print(Panel(summary,style="red", title="[bold]Results[/bold]"))

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

def LoadingAnimation(message: str):
    """Show a loading spinner with message"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )