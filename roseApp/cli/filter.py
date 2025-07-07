import os
import time
import typer
from typing import List, Optional, Tuple
from roseApp.core.parser import create_parser, ParserType, FileExistsError
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error, get_preferred_parser_type
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console
from .theme import SUCCESS, INFO, ACCENT, PRIMARY
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter topics from one or more ROS bag files"""
    try:
        # Validate compression type
        from roseApp.core.util import validate_compression_type
        is_valid, error_message = validate_compression_type(compression)
        if not is_valid:
            typer.echo(f"Error: {error_message}", err=True)
            raise typer.Exit(code=1)
        
        # Auto-select best parser
        preferred_type = get_preferred_parser_type()
        if preferred_type == 'rosbags':
            parser = create_parser(ParserType.ROSBAGS)
            console = Console()
            console.print(f"[green]Using rosbags parser for enhanced performance and LZ4 support[/green]")
        else:
            parser = create_parser(ParserType.PYTHON)
            console = Console()
            console.print(f"[yellow]Using legacy rosbag parser (rosbags not available)[/yellow]")
        
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
            _process_single_bag(parser, input_path, output_bag, whitelist, topics, compression, dry_run)
                
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
            _process_directory(parser, input_path, output_dir, whitelist, topics, compression, parallel, workers, dry_run)
            
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _process_single_bag(parser, input_bag: str, output_bag: str, whitelist_file: Optional[str], topics: Optional[List[str]], compression: str, dry_run: bool):
    """Process a single bag file"""
    # Get connections info
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
        typer.secho("Dry run - no actual modifications will be made", fg=typer.colors.YELLOW, bold=True)
        typer.echo(f"Filtering {typer.style(input_bag, fg=typer.colors.GREEN)} to {typer.style(output_bag, fg=typer.colors.BLUE)}")
        
        # Show all topics and their selection status
        typer.echo("\nTopic selection:")
        typer.echo("─" * 120)
        typer.echo(f"{'Status':<6} {'Topic':<35} {'Message Type':<35} {'Count':<10} {'Size':<10}")
        typer.echo("─" * 120)
        
        for topic in sorted(all_topics):
            is_selected = topic in whitelist_topics
            status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
            topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
            msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
            
            # Get topic statistics
            stats = topic_stats.get(topic, {'count': 0, 'size': 0})
            count = stats['count']
            size = stats['size']
            
            typer.echo(f"{status_icon:<6} {typer.style(topic[:33], fg=topic_style):<35} "
                      f"{typer.style(connections[topic][:33], fg=msg_type_style):<35} "
                      f"{typer.style(str(count), fg=typer.colors.CYAN):<10} "
                      f"{typer.style(format_size(size), fg=typer.colors.YELLOW):<10}")
        
        selected_count = sum(1 for topic in all_topics if topic in whitelist_topics)
        selected_size = sum(topic_stats.get(topic, {'size': 0})['size'] for topic in all_topics if topic in whitelist_topics)
        total_size = sum(topic_stats.get(topic, {'size': 0})['size'] for topic in all_topics)
        
        typer.echo("─" * 120)
        typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
                  f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics, "
                  f"{typer.style(format_size(selected_size), fg=typer.colors.GREEN)} / "
                  f"{typer.style(format_size(total_size), fg=typer.colors.WHITE)} data")
        return
    
    # Print filtering information
    typer.secho("\nStarting to filter bag file:", bold=True)
    typer.echo(f"Input:  {typer.style(input_bag, fg=typer.colors.GREEN)}")
    typer.echo(f"Output: {typer.style(output_bag, fg=typer.colors.BLUE)}")
    
    # Show all topics and their selection status
    typer.echo("\nTopic selection:")
    typer.echo("─" * 120)
    typer.echo(f"{'Status':<6} {'Topic':<35} {'Message Type':<35} {'Count':<10} {'Size':<10}")
    typer.echo("─" * 120)
    
    selected_count = 0
    selected_size = 0
    total_size = 0
    
    for topic in sorted(all_topics):
        is_selected = topic in whitelist_topics
        if is_selected:
            selected_count += 1
            selected_size += topic_stats.get(topic, {'size': 0})['size']
        
        total_size += topic_stats.get(topic, {'size': 0})['size']
        
        status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
        topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
        msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
        
        # Get topic statistics
        stats = topic_stats.get(topic, {'count': 0, 'size': 0})
        count = stats['count']
        size = stats['size']
        
        typer.echo(f"{status_icon:<6} {typer.style(topic[:33], fg=topic_style):<35} "
                  f"{typer.style(connections[topic][:33], fg=msg_type_style):<35} "
                  f"{typer.style(str(count), fg=typer.colors.CYAN):<10} "
                  f"{typer.style(format_size(size), fg=typer.colors.YELLOW):<10}")
    
    # Show selection summary
    typer.echo("─" * 120)
    typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
              f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics, "
              f"{typer.style(format_size(selected_size), fg=typer.colors.GREEN)} / "
              f"{typer.style(format_size(total_size), fg=typer.colors.WHITE)} data")
    

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
        try:
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                progress_callback=update_progress,
                compression=compression
            )
        except FileExistsError:
            # For CLI command, always overwrite (similar to standard CLI behavior)
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                progress_callback=update_progress,
                compression=compression,
                overwrite=True
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
                       compression: str, parallel: bool, workers: Optional[int], dry_run: bool):
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
        _process_directory_parallel(parser, bag_files, input_dir, output_dir, list(whitelist_topics), compression, workers)
    else:
        _process_directory_sequential(parser, bag_files, input_dir, output_dir, list(whitelist_topics), compression)


def _process_directory_sequential(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str], compression: str):
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
                try:
                    result = parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression
                    )
                except FileExistsError:
                    # For CLI command, always overwrite (similar to standard CLI behavior)
                    result = parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression,
                        overwrite=True
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


def _process_directory_parallel(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str], compression: str, workers: Optional[int] = None):
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
                    style=f"{ACCENT}"
                )
                tasks[bag_file] = task
                active_files.add(bag_file)
            
            try:
                # Create parser instance for this thread if needed
                if not hasattr(thread_local, 'parser'):
                    # Use same parser type as main parser
                    preferred_type = get_preferred_parser_type()
                    if preferred_type == 'rosbags':
                        thread_local.parser = create_parser(ParserType.ROSBAGS)
                    else:
                        thread_local.parser = create_parser(ParserType.PYTHON)
                
                # Initialize progress to 30% to indicate preparation complete
                progress.update(task, description=f"Processing: {display_path}", style=f"{ACCENT}", completed=30)
                
                # Define progress update callback function
                def update_progress(percent: int):
                    # Map percentage to 30%-100% range, as 30% indicates preparation work complete
                    mapped_percent = 30 + (percent * 0.7)
                    progress.update(task, 
                                  description=f"Processing: {display_path} ({percent}%)", 
                                  style=f"{ACCENT}", 
                                  completed=mapped_percent)
                
                # Execute filtering
                try:
                    thread_local.parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression,
                        overwrite=True  # For parallel processing, always overwrite
                    )
                except FileExistsError:
                    # This should not happen since we use overwrite=True
                    # but handle it just in case
                    thread_local.parser.filter_bag(
                        bag_file, 
                        output_path, 
                        whitelist,
                        progress_callback=update_progress,
                        compression=compression,
                        overwrite=True
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