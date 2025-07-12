import os
import time
import typer
from typing import List, Optional, Tuple, Dict, Any
from roseApp.core.parser import create_parser, ParserType, IBagParser
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error, get_preferred_parser_type
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box
from ..core.theme import theme
from .util import LoadingAnimation


# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer()

@app.command()
def filter_bag(
    input_path: str = typer.Argument(..., help="Input bag file path or directory containing bag files"),
    output_dir: Optional[str] = typer.Argument(None, help="Output directory for filtered bag files (required for directory input)"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="Topic whitelist file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="Topics to include (can be specified multiple times). Alternative to whitelist file."),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4 (default: none)"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Process files in parallel when input is a directory"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Number of parallel workers (default: CPU count - 2)"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort topics by: topic, count, size (default: size)"),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing output files (default: True)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter ROS bag files by topics"""
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("filter")
        
        # Auto-select best parser (always RosbagsBagParser)
        parser = create_parser(ParserType.ROSBAGS)
        console = Console()
        # Show parser info only when explicitly requested or in debug mode
        logger.debug("Using rosbags parser for enhanced performance and LZ4 support")
        
        # Validate compression type
        from roseApp.core.util import validate_compression_type
        is_valid, error_message = validate_compression_type(compression)
        if not is_valid:
            typer.echo(f"Error: {error_message}", err=True)
            raise typer.Exit(code=1)
        
        # Validate sort_by parameter
        valid_sort_options = ["topic", "count", "size"]
        if sort_by not in valid_sort_options:
            typer.echo(f"Error: Invalid sort option '{sort_by}'. Valid options: {', '.join(valid_sort_options)}", err=True)
            raise typer.Exit(code=1)
        
        # Check if input is a file or directory
        if os.path.isfile(input_path):
            # Single file processing
            if not input_path.endswith('.bag'):
                typer.echo(f"Error: Input file '{input_path}' is not a bag file", err=True)
                raise typer.Exit(code=1)
                
            if output_dir is None:
                # Use output directory as the same as input file if not specified
                output_bag = os.path.splitext(input_path)[0] + "_filtered.bag"
            else:
                # Check if output_dir is actually a file path (common user mistake)
                if output_dir.endswith('.bag'):
                    # User probably provided output file path instead of directory
                    output_bag = output_dir
                    # Create parent directory if needed
                    parent_dir = os.path.dirname(output_bag)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                else:
                    # Check if output_dir is an existing file
                    if os.path.isfile(output_dir):
                        typer.echo(f"Error: '{output_dir}' is an existing file, not a directory. ", err=True)
                        typer.echo("Either specify a directory path or use a .bag extension for output file.", err=True)
                        raise typer.Exit(code=1)
                    
                    # Use specified output directory with the original filename
                    os.makedirs(output_dir, exist_ok=True)
                    output_bag = os.path.join(output_dir, os.path.basename(os.path.splitext(input_path)[0]) + "_filtered.bag")
                
            # Process single file
            _process_single_bag(parser, input_path, output_bag, whitelist, topics, compression, sort_by, overwrite, dry_run)
                
        else:
            # Directory processing
            if not os.path.isdir(input_path):
                typer.echo(f"Error: Input path '{input_path}' does not exist", err=True)
                raise typer.Exit(code=1)
                
            # Output directory is required for directory input
            if output_dir is None:
                typer.echo("Error: Output directory is required when input is a directory", err=True)
                raise typer.Exit(code=1)
                
            # Check if output_dir is an existing file
            if os.path.isfile(output_dir):
                typer.echo(f"Error: '{output_dir}' is an existing file, not a directory.", err=True)
                typer.echo("Please specify a directory path for batch processing.", err=True)
                raise typer.Exit(code=1)
            
            # Make sure output directory exists
            os.makedirs(output_dir, exist_ok=True)
                
            # Process directory
            _process_directory(parser, input_path, output_dir, whitelist, topics, compression, parallel, workers, sort_by, overwrite, dry_run)
            
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def create_responsive_topic_table(all_topics: List[str], connections: Dict[str, str], topic_stats: Dict[str, Dict[str, Any]], 
                                  whitelist_topics: set, console: Console, sort_by: str = "size") -> Tuple[Table, int, int, int]:
    """Create a responsive table for topic display based on terminal width"""
    # Helper function to format size
    def format_size(size_bytes: int) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    # Sort topics based on sort_by parameter
    def sort_topics(topics: List[str]) -> List[str]:
        if sort_by == "topic":
            return sorted(topics)
        elif sort_by == "count":
            return sorted(topics, key=lambda t: topic_stats.get(t, {'count': 0})['count'], reverse=True)
        elif sort_by == "size":
            return sorted(topics, key=lambda t: topic_stats.get(t, {'size': 0})['size'], reverse=True)
        else:
            # Default to size sorting if invalid sort_by
            return sorted(topics, key=lambda t: topic_stats.get(t, {'size': 0})['size'], reverse=True)
    
    # Get terminal width for responsive layout
    terminal_width = console.width
    
    # Create table with responsive columns
    table = Table(box=box.SIMPLE, title="Topic Selection", title_style="bold cyan")
    
    # Calculate column widths based on terminal width (without Message Type column)
    status_width = 6
    count_width = 10
    size_width = 10
    fixed_width = status_width + count_width + size_width + 6  # 6 for borders and padding
    
    # Available width for topic column
    available_width = terminal_width - fixed_width
    topic_width = max(20, available_width)  # Use all available width for topic column
        
    # Add columns with responsive widths
    table.add_column("Status", justify="center", style="bold", width=status_width)
    table.add_column("Topic", justify="left", style="bold", width=topic_width, 
                    overflow="ellipsis", no_wrap=False)
    table.add_column("Count", justify="right", style="cyan", width=count_width)
    table.add_column("Size", justify="right", style=theme.WARNING, width=size_width)
    
    # Calculate summary statistics
    selected_count = 0
    selected_size = 0
    total_size = 0
    
    # Sort topics
    sorted_topics = sort_topics(all_topics)
    
    # Add rows
    for topic in sorted_topics:
        is_selected = topic in whitelist_topics
        if is_selected:
            selected_count += 1
            selected_size += topic_stats.get(topic, {'size': 0})['size']
        
        total_size += topic_stats.get(topic, {'size': 0})['size']
        
        # Create status icon
        status_icon = Text("✓", style="green") if is_selected else Text("○", style=theme.WARNING)
        
        # Create topic text with appropriate styling and word wrapping
        topic_text = Text(topic, style="green" if is_selected else "white")
        
        # Get topic statistics
        stats = topic_stats.get(topic, {'count': 0, 'size': 0})
        count = stats['count']
        size = stats['size']
        
        # Format count and size
        count_text = Text(f"{count:,}", style="cyan")
        size_text = Text(format_size(size), style=theme.WARNING)
        
        # Add row to table
        table.add_row(status_icon, topic_text, count_text, size_text)
    
    return table, selected_count, selected_size, total_size


def create_test_report_table(test_results: List[Dict[str, Any]], console: Console) -> Table:
    """Create a responsive table for test report display with three columns"""
    # Get terminal width for responsive layout
    terminal_width = console.width
    
    # Create table with responsive columns
    table = Table(box=box.SIMPLE, title="Test Report", title_style="bold cyan")
    
    # Calculate column widths based on terminal width
    test_item_width = 25
    status_width = 10
    fixed_width = test_item_width + status_width + 6  # 6 for borders and padding
    
    # Available width for details column
    details_width = terminal_width - fixed_width
    
    # Ensure minimum width for details column
    if details_width < 30:
        test_item_width = 20
        details_width = terminal_width - test_item_width - status_width - 6
        
    # Add columns with responsive widths
    table.add_column("Test Item", justify="left", style="bold", width=test_item_width)
    table.add_column("Status", justify="center", style="bold", width=status_width)
    table.add_column("Details", justify="left", style="white", width=details_width, 
                    overflow="fold", no_wrap=False)
    
    # Add rows
    for result in test_results:
        test_item = result.get('test_item', 'Unknown')
        status = result.get('status', 'Unknown')
        details = result.get('details', 'No details available')
        
        # Create test item text
        test_item_text = Text(test_item, style="cyan")
        
        # Create status text with appropriate styling
        if status.lower() in ['pass', 'passed', 'success', 'ok']:
            status_text = Text("✓ PASS", style="green")
        elif status.lower() in ['fail', 'failed', 'error', 'failed']:
            status_text = Text("✗ FAIL", style="red")
        elif status.lower() in ['skip', 'skipped', 'pending']:
            status_text = Text("○ SKIP", style=theme.WARNING)
        else:
            status_text = Text(status, style="white")
        
        # Create details text with word wrapping
        details_text = Text(details, style="white")
        
        # Add row to table
        table.add_row(test_item_text, status_text, details_text)
    
    return table


def _process_single_bag(parser, input_bag: str, output_bag: str, whitelist_file: Optional[str], topics: Optional[List[str]], compression: str, sort_by: str, overwrite: bool, dry_run: bool):
    """Process a single bag file"""
    # Get connections info with progress bar
    from .util import LoadingAnimationWithTimer
    with LoadingAnimationWithTimer("Loading bag file...", dismiss=True) as progress:
        progress.add_task(description="Loading...")
    all_topics, connections, _ = parser.load_bag(input_bag)
    
    # Get topic statistics (count and size)
    topic_stats = parser.get_topic_stats(input_bag)
    
    # Get whitelist topics from file or command line arguments
    whitelist_topics = set()
    if whitelist_file:
        if not os.path.exists(whitelist_file):
            typer.echo(f"Error: Whitelist file '{whitelist_file}' does not exist", err=True)
            raise typer.Exit(code=1)
        
        whitelist_topics.update(parser.load_whitelist(whitelist_file))
    
    if topics:
        whitelist_topics.update(topics)
    
    if not whitelist_topics:
        typer.echo("Error: No topics specified. Use --whitelist or --topics to specify", err=True)
        raise typer.Exit(code=1)
        
    # Helper function to format size
    def format_size(size_bytes: int) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
        
    # In dry run mode, show what would be done
    if dry_run:
        console = Console()
        console.print("[bold yellow]Dry run - no actual modifications will be made[/bold yellow]")
        console.print(f"Filtering [green]{input_bag}[/green] to [blue]{output_bag}[/blue]")
        console.print()
        
        # Create and display responsive table
        table, selected_count, selected_size, total_size = create_responsive_topic_table(
            all_topics, connections, topic_stats, whitelist_topics, console, sort_by
        )
        
        console.print(table)
        
        # Show selection summary
        console.print(f"\n[bold]Selected:[/bold] [green]{selected_count}[/green] / "
                     f"[white]{len(all_topics)}[/white] topics, "
                     f"[green]{format_size(selected_size)}[/green] / "
                     f"[white]{format_size(total_size)}[/white] data")
        return
    
    # Print filtering information
    console = Console()
    console.print("\n[bold]Starting to filter bag file:[/bold]")
    console.print(f"Input:  [green]{input_bag}[/green]")
    console.print(f"Output: [blue]{output_bag}[/blue]")
    console.print()
    
    # Create and display responsive table
    table, selected_count, selected_size, total_size = create_responsive_topic_table(
        all_topics, connections, topic_stats, whitelist_topics, console, sort_by
    )
    
    console.print(table)
    
    # Show selection summary
    console.print(f"\n[bold]Selected:[/bold] [green]{selected_count}[/green] / "
                 f"[white]{len(all_topics)}[/white] topics, "
                 f"[green]{format_size(selected_size)}[/green] / "
                 f"[white]{format_size(total_size)}[/white] data")
    

    # Use progress bar for filtering
    typer.echo("\nProcessing:")
    start_time = time.time()
    
    # 获取要显示的文件名，对较长的文件名进行处理
    input_basename = os.path.basename(input_bag)
    display_name = input_basename
    if len(input_basename) > 40:
        display_name = f"{input_basename[:15]}...{input_basename[-20:]}"
        
    # Use LoadingAnimation from util.py for consistent progress display
    from .util import LoadingAnimation
    
    with LoadingAnimation("Filtering bag file...") as progress:
        # Create progress task
        task_id = progress.add_task(f"Filtering: {display_name}", total=100)
        
        # Define progress update callback function
        def update_progress(percent: int):
            progress.update(task_id, description=f"Filtering: {display_name}", completed=percent)
        
        # Execute filtering
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                progress_callback=update_progress,
                compression=compression,
            overwrite=overwrite
            )
        
        # Update final status
        progress.update(task_id, description=f"[green]✓ Complete: {display_name}[/green]", completed=100)
    
    # Add some extra space to ensure progress bar is fully visible
    typer.echo("\n\n")
    
    # Show filtering result
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Calculate size reduction
    input_size = os.path.getsize(input_bag)
    output_size = os.path.getsize(output_bag)
    size_reduction = (1 - output_size/input_size) * 100
    
    typer.secho("\nFiltering result:", fg=typer.colors.GREEN, bold=True)
    typer.echo("─" * 80)
    typer.echo(f"Time: {int(elapsed//60)} minutes {elapsed%60:.2f} seconds")
    typer.echo(f"Input size:  {typer.style(f'{input_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
    typer.echo(f"Output size: {typer.style(f'{output_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
    typer.echo(f"Size reduction:   {typer.style(f'{size_reduction:.1f}%', fg=typer.colors.GREEN)}")
    typer.echo(result)


def _process_directory(parser, input_dir: str, output_dir: str, whitelist_file: Optional[str], topics: Optional[List[str]], 
                       compression: str, parallel: bool, workers: Optional[int], sort_by: str, overwrite: bool, dry_run: bool):
    """Process all bag files in a directory"""
    # Get all bag files in the directory (recursive)
    from .util import collect_bag_files
    
    bag_files = collect_bag_files(input_dir)
    if not bag_files:
        typer.echo("No bag files found in directory", style="red")
        return
    
    # Get whitelist topics from file or command line arguments
    whitelist_topics = set()
    if whitelist_file:
        if not os.path.exists(whitelist_file):
            typer.echo(f"Error: Whitelist file '{whitelist_file}' does not exist", err=True)
            raise typer.Exit(code=1)
        
        whitelist_topics.update(parser.load_whitelist(whitelist_file))
    
    if topics:
        whitelist_topics.update(topics)
    
    if not whitelist_topics:
        typer.echo("Error: No topics specified. Use --whitelist or --topics to specify", err=True)
        raise typer.Exit(code=1)

    if dry_run:
        typer.secho(f"Would process {len(bag_files)} bag files from {input_dir}", fg=typer.colors.YELLOW, bold=True)
        for bag_file in bag_files:
            rel_path = os.path.relpath(bag_file, input_dir)
            output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + "_filtered.bag")
            typer.echo(f"  {typer.style(rel_path, fg=typer.colors.GREEN)} -> {typer.style(output_path, fg=typer.colors.BLUE)}")
        return

    # Process files
    if parallel:
        _process_directory_parallel(parser, bag_files, input_dir, output_dir, list(whitelist_topics), compression, workers, sort_by, overwrite)
    else:
        _process_directory_sequential(parser, bag_files, input_dir, output_dir, list(whitelist_topics), compression, sort_by, overwrite)


def _process_directory_sequential(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str], compression: str, sort_by: str, overwrite: bool):
    """Process bag files sequentially"""
    typer.secho(f"\nProcessing {len(bag_files)} bag files sequentially", fg=typer.colors.BLUE, bold=True)
    
    success_count = 0
    fail_count = 0
    
    for i, bag_file in enumerate(bag_files):
        rel_path = os.path.relpath(bag_file, input_dir)
        typer.echo(f"\nProcessing file {i+1}/{len(bag_files)}: {rel_path}")
        
        # Create output path based on input path
        # Preserve directory structure under output_dir
        rel_dir = os.path.dirname(rel_path)
        output_subdir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
        os.makedirs(output_subdir, exist_ok=True)
        
        output_basename = os.path.basename(os.path.splitext(bag_file)[0]) + "_filtered.bag"
        output_path = os.path.join(output_subdir, output_basename)
        
        try:
            # Process this file
            typer.echo(f"Output: {output_path}")
            
            # 获取要显示的文件名，对较长的文件名进行处理
            display_name = rel_path
            if len(rel_path) > 40:
                display_name = f"{rel_path[:15]}...{rel_path[-20:]}"
                
            
            with LoadingAnimation("Filtering bag file...") as progress:
                # Create progress task
                task_id = progress.add_task(f"Filtering: {display_name}", total=100)
                
                # Define progress update callback function
                def update_progress(percent: int):
                    progress.update(task_id, description=f"Filtering: {display_name} ({percent}%)", completed=percent)
                
                # Execute filtering
                    result = parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression,
                    overwrite=overwrite
                    )
                
                # Update final status
                progress.update(task_id, description=f"[green]✓ Complete: {display_name}[/green]", completed=100)
            
            # Add some extra space to ensure progress bar is fully visible
            typer.echo("\n\n")
            
            # Calculate and show file statistics
            from .util import print_filter_stats
            print_filter_stats(Console(), bag_file, output_path)
            
            success_count += 1
            
        except Exception as e:
            typer.echo(f"Error processing {rel_path}: {str(e)}", err=True)
            logger.error(f"Error processing {bag_file}: {str(e)}", exc_info=True)
            fail_count += 1
    
    # Show summary
    from .util import print_batch_filter_summary
    print_batch_filter_summary(Console(), success_count, fail_count)


def _process_directory_parallel(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str], compression: str, workers: Optional[int] = None, sort_by: str = "size", overwrite: bool = True):
    """Process bag files in parallel"""
    import concurrent.futures
    import threading
    import queue
    
    # Determine the number of workers
    if workers is None:
        import os
        max_workers = max(os.cpu_count() - 2, 1)  # Don't use all CPUs
    else:
        max_workers = workers
    
    max_workers = min(max_workers, len(bag_files))  # Don't create more workers than files
    
    typer.secho(f"\nProcessing {len(bag_files)} bag files with {max_workers} parallel workers", fg=typer.colors.BLUE, bold=True)
    
    # Create progress display for all files
    from .util import LoadingAnimation
    
    with LoadingAnimation("Processing bag files...") as progress:
        # Track tasks and counts
        tasks = {}
        success_count = 0
        fail_count = 0
        
        # Thread synchronization
        success_fail_lock = threading.Lock()
        active_files_lock = threading.Lock()
        active_files = set()
        
        # Thread-local storage for parser instances
        thread_local = threading.local()
        
        # Create a queue for files to process
        file_queue = queue.Queue()
        for bag_file in bag_files:
            file_queue.put(bag_file)
        
        # Generate a timestamp for this batch
        batch_timestamp = time.strftime("%H%M%S")
        
        def _process_bag_file(bag_file):
            rel_path = os.path.relpath(bag_file, input_dir)
            
            # Create output path based on input path
            # Preserve directory structure under output_dir
            rel_dir = os.path.dirname(rel_path)
            output_subdir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
            os.makedirs(output_subdir, exist_ok=True)
            
            output_basename = os.path.basename(os.path.splitext(bag_file)[0]) + f"_filtered_{batch_timestamp}.bag"
            output_path = os.path.join(output_subdir, output_basename)
            
            # 对较长的文件路径进行处理，确保显示合适
            display_path = rel_path
            if len(rel_path) > 40:
                display_path = f"{rel_path[:15]}...{rel_path[-20:]}"
            
            # Create task for this file at the start of processing
            with active_files_lock:
                task = progress.add_task(
                    f"Processing: {display_path}",
                    total=100,
                    completed=0,
                    style=f"{theme.ACCENT}"
                )
                tasks[bag_file] = task
                active_files.add(bag_file)
            
            try:
                # Create parser instance for this thread if needed
                if not hasattr(thread_local, 'parser'):
                    # Use RosbagsBagParser for all threads
                        thread_local.parser = create_parser(ParserType.ROSBAGS)
                
                # Initialize progress to 30% to indicate preparation complete
                progress.update(task, description=f"Processing: {display_path}", style=f"{theme.ACCENT}", completed=30)
                
                # Define progress update callback function
                def update_progress(percent: int):
                    # Map percentage to 30%-100% range, as 30% indicates preparation work complete
                    mapped_percent = 30 + (percent * 0.7)
                    progress.update(task, 
                                  description=f"Processing: {display_path} ({percent}%)", 
                                  style=f"{theme.ACCENT}", 
                                  completed=mapped_percent)
                
                # Execute filtering
                    thread_local.parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression,
                    overwrite=overwrite
                    )
                
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
        
        # Space for the progress bars that will be created
        typer.echo(f"\n"*(min(len(bag_files), max_workers)))
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                        # This should not happen as exceptions are caught in _process_bag_file
                        logger.error(f"Unexpected error processing {bag_file}: {str(e)}", exc_info=True)
    
    # Show final summary with color-coded results
    # 添加一些额外空行以确保进度条完整显示
    typer.echo("\n\n")
    from .util import print_batch_filter_summary
    print_batch_filter_summary(Console(), success_count, fail_count)

def main():
    """CLI tool entry point"""
    app()

if __name__ == "__main__":
    main() 