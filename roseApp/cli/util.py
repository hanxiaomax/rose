import time
import os
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.box import SIMPLE
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import PathValidator
from ..ui.common_ui import CommonUI, Message


# Import theme system for colors
from ..ui.theme import get_color

WARNING_COLOR = get_color('warning')
PRIMARY_COLOR = get_color('primary')
ACCENT_COLOR = get_color('accent')
SUCCESS_COLOR = get_color('success')

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
    subtitle.append("Github", style=f"{get_color('primary')} link https://github.com/hanxiaomax/rose")
    subtitle.append(" • ", style="dim")
    subtitle.append("Author", style=f"{get_color('primary')} link https://github.com/hanxiaomax")

    # Create banner content
    content = Text()
    content.append(ROSE_BANNER, style=f"{get_color('primary')}")
    content.append("ROSE is a Ros Bag One-Stop Editor", style=f"{get_color('primary')}")
    
    # Create panel with all elements
    panel = Panel(
        content,
        title=title,
        subtitle=subtitle,  
        border_style=get_color('accent'),  # Use Claude's signature color
        highlight=True
    )
    
    # Print the panel
    # self.console.print(panel)
    return panel
  
def print_usage_instructions(console:Console, is_fuzzy:bool = False):
    ui = CommonUI()
    ui.console = console
    
    Message.accent("Usage Instructions:", console)
    if is_fuzzy:
        Message.accent("•  Type to search", console)
    else:
        Message.accent("•  Space to select/unselect", console) 
    Message.accent("•  ↑/↓ to navigate options", console)
    Message.accent("•  Tab to select and move to next item", console)
    Message.accent("•  Shift+Tab to select and move to previous item", console)
    Message.accent("•  Ctrl+A to select all", console)
    Message.accent("•  Enter to confirm selection\n", console)


def collect_bag_files(directory: str) -> List[str]:
    """Recursively find all bag files in the given directory"""
    bag_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.bag'):
                bag_files.append(os.path.join(root, file))
    return sorted(bag_files)

def print_bag_info(console:Console, bag_path: str, topics: List[str], connections: dict, time_range: tuple, parser=None):
    """Show bag file information using rich panels"""
    # Calculate file info
    file_size = os.path.getsize(bag_path)
    file_size_mb = file_size / (1024 * 1024)
    
    # Create basic bag info text
    bag_info = Text()
    bag_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {get_color('accent')}")
    bag_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n",style=f"dim {get_color('primary')}")
    bag_info.append(f"Path: {os.path.abspath(bag_path)}\n",style=f"dim {get_color('primary')}")
    bag_info.append(f"Topics({len(topics)} in total):\n", style=get_color('accent'))
    
    # First, display all topics
    for topic in sorted(topics):
        bag_info.append(f"• {topic:<40}", style=f"{get_color('primary')}")
        bag_info.append(f"{connections[topic]}\n", style=f"dim {get_color('primary')}")
    
    panel = Panel(bag_info,
                  title=f"Bag Information",
                  border_style=get_color('accent'),
                  padding=(0, 1))
    
    console.print(panel)
    
    # Ask if user wants to filter topics
    while True:
        action = inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice(value="filter", name="1. show topics (fuzzy search)"),
                Choice(value="back", name="2. Back")
            ]
        ).execute()
        
        if action == "back":
            return
        elif action == "filter":
            # Use the new select_topics_with_fuzzy function
            filtered_topics = ask_topics(console, topics, parser=parser, bag_path=bag_path)
            
            if not filtered_topics:
                console.print("No topics selected. Showing all topics.", style=get_color('warning'))
                continue
            
            # Create filtered topics panel
            filtered_info = Text()
            filtered_info.append(f"File: {os.path.basename(bag_path)}\n", style=f"bold {get_color('accent')}")
            filtered_info.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)\n")
            filtered_info.append(f"Path: {os.path.abspath(bag_path)}\n")
            filtered_info.append(f"Filtered Topics({len(filtered_topics)} of {len(topics)}):\n", style="bold")
            
            for topic in sorted(filtered_topics):
                filtered_info.append(f"• {topic:<40}", style=get_color('primary'))
                filtered_info.append(f"{connections[topic]}\n", style="dim")
            
            filtered_panel = Panel(filtered_info,
                                  title=f"Filtered Bag Information",
                                  border_style=get_color('primary'),
                                  padding=(0, 1))
            
            console.print(filtered_panel)

def print_filter_stats(console:Console, input_bag: str, output_bag: str):
    """Show filtering statistics in a table format with headers and three rows"""
    # Check if files exist before trying to get their sizes
    if not os.path.exists(input_bag):
        ErrorMessage(f"Input bag file not found: {input_bag}").render(console)
        return
    
    if not os.path.exists(output_bag):
        WarningMessage(f"Output bag file not created: {output_bag}").render(console)
        WarningMessage("The filtering process may have failed or been interrupted.").render(console)
        return
    
    input_size = os.path.getsize(input_bag)
    output_size = os.path.getsize(output_bag)
    input_size_mb:float = input_size / (1024 * 1024)
    output_size_mb:float = output_size / (1024 * 1024)
    reduction_ratio = (1 - output_size / input_size) * 100
    
    # 创建无边框表格
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,  # 无边框
        padding=(0, 2),
        collapse_padding=True
    )
    
    # 添加三列，第一列较窄
    table.add_column("", style=f"{get_color('primary')}", width=4)  # 用于input/output标签
    table.add_column("file", style=f"{get_color('primary')}", justify="left")  # 文件名列
    table.add_column("size", style=f"{get_color('primary')}", justify="left", width=20)  # 增加size列宽度以适应额外信息
    
    # 添加input行
    table.add_row(
        "In",
        os.path.basename(input_bag),
        f"{input_size_mb:.0f}MB"
    )
    
    # 添加output行，包含缩小百分比，使用ACCENT颜色
    table.add_row(
        f"[{get_color('accent')}]Out[/{get_color('accent')}]",
        f"[{get_color('accent')}]{os.path.basename(output_bag)}[/{get_color('accent')}]", 
        f"[{get_color('accent')}]{output_size_mb:.0f}MB (↓{reduction_ratio:.0f}%)[/{get_color('accent')}]"  
    )
    
    # 将表格放在面板中显示
    console.print(Panel(table, title="Filter Results", border_style=f"bold {get_color('accent')}"))

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
        console.print(summary, style=get_color('success'))
    else:
        console.print(summary, style=get_color('accent'))

def ask_topics(console: Console, topics: List[str], parser=None, bag_path: Optional[str] = None) -> Optional[List[str]]:
    return ask_topics_with_fuzzy(
        console=console,
        topics=topics,
        message="Select topics:",
        require_selection=True,
        show_instructions=True,
        parser=parser,
        bag_path=bag_path
    )

def filter_topics(all_topics: List[str], patterns: List[str], topic_filter: Optional[str] = None) -> List[str]:
    """
    Filter topics based on patterns and optional topic filter with fuzzy matching support
    
    Args:
        all_topics: List of all available topics
        patterns: List of patterns to match (supports fuzzy matching)
        topic_filter: Optional additional filter pattern
        
    Returns:
        List of matching topics
        
    Examples:
        filter_topics(['/gps/fix', '/imu/data', '/camera/image'], ['gps']) -> ['/gps/fix']
        filter_topics(['/gps/fix', '/imu/data'], ['gps', 'imu']) -> ['/gps/fix', '/imu/data']
        filter_topics(['/tf', '/tf_static'], ['^/tf$']) -> ['/tf']  # regex exact match
    """
    if not patterns:
        return all_topics
    
    import re
    matching_topics = set()
    
    for pattern in patterns:
        # Exact match first (highest priority)
        if pattern in all_topics:
            matching_topics.add(pattern)
            continue
        
        # Fuzzy matching - if pattern is a substring of topic name (case insensitive)
        for topic in all_topics:
            if pattern.lower() in topic.lower():
                matching_topics.add(topic)
        
        # Regex matching if pattern looks like a regex (contains regex special chars)
        if any(char in pattern for char in ['^', '$', '*', '+', '?', '[', ']', '(', ')', '|', '\\']):
            try:
                regex = re.compile(pattern)
                for topic in all_topics:
                    if regex.search(topic):
                        matching_topics.add(topic)
            except re.error:
                # Not a valid regex, skip regex matching for this pattern
                pass
    
    # Apply additional topic filter if provided
    if topic_filter:
        filtered_topics = set()
        try:
            filter_regex = re.compile(topic_filter)
            for topic in matching_topics:
                if filter_regex.search(topic):
                    filtered_topics.add(topic)
            matching_topics = filtered_topics
        except re.error:
            # If regex is invalid, use substring matching
            filtered_topics = {topic for topic in matching_topics if topic_filter.lower() in topic.lower()}
            matching_topics = filtered_topics
    
    return sorted(list(matching_topics))


def ask_topics_with_fuzzy(
    console: Console, 
    topics: List[str], 
    message: str = "Select topics:",
    require_selection: bool = True,
    show_instructions: bool = True,
    preselected: Optional[List[str]] = None,
    parser=None,
    bag_path: Optional[str] = None
) -> List[str]:
    """Select topics using fuzzy search
    
    Args:
        console: Rich console instance for displaying messages
        topics: List of topics to select from
        message: Prompt message to display
        require_selection: Whether to require at least one topic to be selected
        show_instructions: Whether to show usage instructions
        preselected: List of topics to preselect
        parser: Parser instance for getting topic statistics
        bag_path: Path to bag file for getting topic statistics
        
    Returns:
        List of selected topics
    """
    # Helper function to format size
    def format_size(size_bytes: int) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    # Get topic statistics if parser and bag_path are provided
    topic_stats = {}
    if parser and bag_path:
        try:
            topic_stats = parser.get_topic_stats(bag_path)
        except Exception:
            # If getting stats fails, continue without them
            pass
    
    # Create enhanced topic choices with size information
    topic_choices = []
    for topic in sorted(topics):
        if topic in topic_stats:
            stats = topic_stats[topic]
            count = stats['count']
            size = stats['size']
            display_name = f"{topic:<35} ({count:>5} msgs, {format_size(size):>8})"
        else:
            display_name = topic
        
        topic_choices.append(Choice(value=topic, name=display_name))
    
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
        default=preselected
    ).execute()
    
    return selected_topics


class PanelProgress(Progress):
    def __init__(self, *columns, title: Optional[str] = None, **kwargs):
        self.title = title
        super().__init__(*columns, **kwargs)

    def get_renderables(self):
        yield Panel(self.make_tasks_table(self.tasks), title=self.title)

class TimedPanelProgress(PanelProgress):
    """Progress bar that measures and displays timing information"""
    
    def __init__(self, *columns, title: Optional[str] = None, **kwargs):
        super().__init__(*columns, title=title, **kwargs)
        self.start_time = None
        self.end_time = None
        self._external_console = Console()
        
    def __enter__(self):
        self.start_time = time.time()
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        result = super().__exit__(exc_type, exc_val, exc_tb)
        
        # Display loading time after completion
        if self.start_time and self.end_time:
            elapsed = self.end_time - self.start_time
            self._external_console.print(f"[{SUCCESS_COLOR}]✓ Bag file loaded in {elapsed:.2f}s[/{SUCCESS_COLOR}]")
        
        return result

def LoadingAnimation(title: Optional[str] = None, dismiss: bool = False):
    """Show a loading spinner with message in a panel
    
    Args:
        title (Optional[str], optional): The title of the panel. Defaults to None.
        dismiss (bool, optional): Whether to dismiss the panel after completion. Defaults to False.
    
    Returns:
        PanelProgress: A progress bar wrapped in a panel with optional title
    """
    return PanelProgress(
        TextColumn(f"[{get_color('primary')}][progress.description]{{task.description}}[/{get_color('primary')}]"),
        BarColumn(bar_width=None, complete_style=get_color('success'), finished_style=get_color('success')),  # 设置为 None 以自适应宽度
        TaskProgressColumn(),
        TimeRemainingColumn(),
        title=title,
        transient=dismiss,  # 设置为 False 以保持任务完成后的显示
    )

def LoadingAnimationWithTimer(title: Optional[str] = None, dismiss: bool = False):
    """Show a loading spinner with message in a panel and measure loading time
    
    Args:
        title (Optional[str], optional): The title of the panel. Defaults to None.
        dismiss (bool, optional): Whether to dismiss the panel after completion. Defaults to False.
    
    Returns:
        TimedPanelProgress: A progress bar wrapped in a panel with timing functionality
    """
    return TimedPanelProgress(
        TextColumn(f"[{get_color('primary')}][progress.description]{{task.description}}[/{get_color('primary')}]"),
        BarColumn(bar_width=None, complete_style=get_color('success'), finished_style=get_color('success')),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        title=title,
        transient=dismiss,
    )


def check_and_load_bag_cache(bag_path: Path, auto_load: bool = True, verbose: bool = False, build_index: bool = False, force_load: bool = False) -> bool:
    """
    Check if bag is in cache, and optionally prompt user to load it if not
    
    Args:
        bag_path: Path to the bag file
        auto_load: Whether to prompt user for auto-loading
        verbose: Whether to show verbose output
        build_index: Whether to build DataFrame index when loading
        force_load: Whether to force loading without prompting user
    
    Returns:
        bool: True if bag is available in cache (either was already cached or was loaded), False otherwise
    """
    from ..core.cache import create_bag_cache_manager
    from ..core.parser import BagParser
    import asyncio
    import typer
    
    # Check if bag is already loaded in cache
    cache_manager = create_bag_cache_manager()
    cached_entry = cache_manager.get_analysis(bag_path)
    
    if cached_entry and cached_entry.is_valid(bag_path):
        if verbose:
            console = Console()
            ui = CommonUI()
            ui.console = console
            Message.success(f"✓ Using cached bag analysis for {bag_path}", console)
        return True
    
    if not auto_load and not force_load:
        return False
    
    # Bag not in cache, ask user if they want to load it (unless force_load is True)
    ui = CommonUI()
    console = ui.console
    
    should_load = force_load
    if not force_load:
        Message.warning(f"⚠ Bag file {bag_path} is not loaded in cache.", console)
        
        # Different prompts based on build_index mode
        if build_index:
            Message.info("Note: Verbose mode enabled - will build DataFrame index for detailed statistics.", console)
            should_load = typer.confirm("Would you like to load it with DataFrame indexing now?", default=True)
        else:
            should_load = typer.confirm("Would you like to load it now?", default=True)
        
        if not should_load:
            Message.warning(f"Operation cancelled. Please load the bag first using: rose load {bag_path}", console)
            return False
    
    # Load the bag
    Message.info("Loading bag file into cache...", console)
    
    try:
        # Use async loading
        async def load_bag():
            parser = BagParser()
            
            # Create progress callback for loading
            def progress_callback(current, total, description="Loading"):
                # Simple progress indication
                if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
                    percentage = (current / total) * 100
                    console.print(f"Loading... {percentage:.1f}%", end="\r")
                else:
                    # Handle string descriptions
                    console.print(f"{current}", end="\r")
            
            bag_info, elapsed_time = await parser.load_bag_async(
                str(bag_path), 
                build_index=build_index,  # Use passed build_index parameter
                progress_callback=progress_callback if verbose else None
            )
            
            return bag_info, elapsed_time
        
        # Run the async loading
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        bag_info, elapsed_time = loop.run_until_complete(load_bag())
        
        if bag_info:
            Message.success(f"✓ Successfully loaded bag into cache in {elapsed_time:.2f}s", console)
            if verbose:
                console.print(f"  Topics: {len(bag_info.topics) if bag_info.topics else 0}")
                console.print(f"  Duration: {bag_info.duration_seconds:.2f}s" if bag_info.duration_seconds else "  Duration: Unknown")
            return True
        else:
            Message.error("✗ Failed to load bag into cache", console)
            return False
            
    except Exception as e:
        console.print(f"[red]✗[/red] Error loading bag: {e}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False

