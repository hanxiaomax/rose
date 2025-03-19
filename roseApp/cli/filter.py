import os
import time
import typer
from typing import List, Optional, Tuple
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console
from .theme import GREEN, YELLOW, BLUE, PURPLE, ORANGE


# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer()

@app.command("filter")
def filter_bag(
    input_path: str = typer.Argument(..., help="Input bag file path or directory containing bag files"),
    output_dir: Optional[str] = typer.Argument(None, help="Output directory for filtered bag files (required for directory input)"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="Topic whitelist file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="Topics to include (can be specified multiple times). Alternative to whitelist file."),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Process files in parallel when input is a directory"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Number of parallel workers (default: CPU count - 2)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter topics from one or more ROS bag files"""
    try:
        parser = create_parser(ParserType.PYTHON)
        
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
                # Use specified output directory with the original filename
                os.makedirs(output_dir, exist_ok=True)
                output_bag = os.path.join(output_dir, os.path.basename(os.path.splitext(input_path)[0]) + "_filtered.bag")
                
            # Process single file
            _process_single_bag(parser, input_path, output_bag, whitelist, topics, dry_run)
                
        else:
            # Directory processing
            if not os.path.isdir(input_path):
                typer.echo(f"Error: Input path '{input_path}' does not exist", err=True)
                raise typer.Exit(code=1)
                
            # Output directory is required for directory input
            if output_dir is None:
                typer.echo("Error: Output directory is required when input is a directory", err=True)
                raise typer.Exit(code=1)
                
            # Make sure output directory exists
            os.makedirs(output_dir, exist_ok=True)
                
            # Process directory
            _process_directory(parser, input_path, output_dir, whitelist, topics, parallel, workers, dry_run)
            
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _process_single_bag(parser, input_bag: str, output_bag: str, whitelist_file: Optional[str], topics: Optional[List[str]], dry_run: bool):
    """Process a single bag file"""
    # Get all topics from input bag
    all_topics, connections, _ = parser.load_bag(input_bag)
    
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
        
    # In dry run mode, show what would be done
    if dry_run:
        typer.secho("Dry run - no actual modifications will be made", fg=typer.colors.YELLOW, bold=True)
        typer.echo(f"Filtering {typer.style(input_bag, fg=typer.colors.GREEN)} to {typer.style(output_bag, fg=typer.colors.BLUE)}")
        
        # Show all topics and their selection status
        typer.echo("\nTopic selection:")
        typer.echo("─" * 80)
        for topic in sorted(all_topics):
            is_selected = topic in whitelist_topics
            status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
            topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
            msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
            topic_str = f"{topic:<40}"
            typer.echo(f"  {status_icon} {typer.style(topic_str, fg=topic_style)} "
                      f"{typer.style(connections[topic], fg=msg_type_style)}")
        
        selected_count = sum(1 for topic in all_topics if topic in whitelist_topics)
        typer.echo("─" * 80)
        typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
                  f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics")
        return
    
    # Print filtering information
    typer.secho("\nStarting to filter bag file:", bold=True)
    typer.echo(f"Input:  {typer.style(input_bag, fg=typer.colors.GREEN)}")
    typer.echo(f"Output: {typer.style(output_bag, fg=typer.colors.BLUE)}")
    
    # Show all topics and their selection status
    typer.echo("\nTopic selection:")
    typer.echo("─" * 80)
    selected_count = 0
    for topic in sorted(all_topics):
        is_selected = topic in whitelist_topics
        if is_selected:
            selected_count += 1
        status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
        topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
        msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
        topic_str = f"{topic:<40}"
        typer.echo(f"  {status_icon} {typer.style(topic_str, fg=topic_style)} "
                  f"{typer.style(connections[topic], fg=msg_type_style)}")
    
    # Show selection summary
    typer.echo("─" * 80)
    typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
              f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics")
    

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
            progress_callback=update_progress
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
                       parallel: bool, workers: Optional[int], dry_run: bool):
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
        _process_directory_parallel(parser, bag_files, input_dir, output_dir, list(whitelist_topics), workers)
    else:
        _process_directory_sequential(parser, bag_files, input_dir, output_dir, list(whitelist_topics))


def _process_directory_sequential(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str]):
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
                
            # Use LoadingAnimation for progress
            from .util import LoadingAnimation
            
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
                    progress_callback=update_progress
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


def _process_directory_parallel(parser, bag_files: List[str], input_dir: str, output_dir: str, whitelist: List[str], workers: Optional[int] = None):
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
                    style=f"{PURPLE}"
                )
                tasks[bag_file] = task
                active_files.add(bag_file)
            
            try:
                # Create parser instance for this thread if needed
                if not hasattr(thread_local, 'parser'):
                    thread_local.parser = create_parser(ParserType.PYTHON)
                
                # Initialize progress to 30% to indicate preparation complete
                progress.update(task, description=f"Processing: {display_path}", style=f"{PURPLE}", completed=30)
                
                # Define progress update callback function
                def update_progress(percent: int):
                    # Map percentage to 30%-100% range, as 30% indicates preparation work complete
                    mapped_percent = 30 + (percent * 0.7)
                    progress.update(task, 
                                  description=f"Processing: {display_path} ({percent}%)", 
                                  style=f"{PURPLE}", 
                                  completed=mapped_percent)
                
                # Execute filtering
                thread_local.parser.filter_bag(
                    bag_file, 
                    output_path, 
                    whitelist,
                    progress_callback=update_progress
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