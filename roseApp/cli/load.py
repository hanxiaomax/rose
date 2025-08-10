#!/usr/bin/env python3
"""
Load command for ROS bag files - Load bags into cache for faster operations
"""

import asyncio
import concurrent.futures
import glob
import re
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn, TimeElapsedColumn
from rich.table import Table

from ..core.parser import BagParser
from ..core.cache import get_cache, create_bag_cache_manager
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.ui_control import UIControl, Message

# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(help="Load ROS bag files into cache for faster operations")


def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


async def load_single_bag(bag_path: Path, parser, verbose: bool = False, build_index: bool = False, progress_callback=None) -> dict:
    """Load a single bag file into cache using parser directly"""
    try:
        # Check if already cached
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(bag_path)
        
        if cached_entry and cached_entry.is_valid(bag_path):
            if verbose:
                logger.info(f"Bag {bag_path} already cached, skipping")
            return {
                'path': str(bag_path),
                'status': 'already_cached',
                'message': 'Already in cache'
            }
        
        # Load bag using parser's async load function
        bag_info, elapsed_time = await parser.load_bag_async(
            str(bag_path), 
            build_index=build_index,
            progress_callback=progress_callback
        )
        
        if verbose:
            logger.info(f"Successfully loaded {bag_path} into cache in {elapsed_time:.3f}s")
        
        return {
            'path': str(bag_path),
            'status': 'loaded',
            'message': 'Successfully loaded into cache',
            'topics_count': len(bag_info.topics) if bag_info.topics else 0,
            'duration': bag_info.duration_seconds if bag_info.duration_seconds else 0,
            'elapsed_time': elapsed_time
        }
        
    except Exception as e:
        logger.error(f"Failed to load {bag_path}: {e}")
        return {
            'path': str(bag_path),
            'status': 'error',
            'message': str(e)
        }


def find_bag_files(input_patterns: List[str]) -> List[Path]:
    """Find bag files using glob patterns and regex"""
    bag_files = []
    
    for pattern in input_patterns:
        # First try as glob pattern
        glob_matches = glob.glob(pattern)
        if glob_matches:
            for match in glob_matches:
                path = Path(match)
                if path.exists() and path.suffix == '.bag':
                    bag_files.append(path)
        else:
            # Try as regex pattern in current directory
            try:
                regex = re.compile(pattern)
                current_dir = Path('.')
                for bag_file in current_dir.glob('*.bag'):
                    if regex.search(bag_file.name):
                        bag_files.append(bag_file)
            except re.error:
                # If regex is invalid, treat as literal filename
                path = Path(pattern)
                if path.exists() and path.suffix == '.bag':
                    bag_files.append(path)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_bags = []
    for bag in bag_files:
        if bag not in seen:
            seen.add(bag)
            unique_bags.append(bag)
    
    return unique_bags


@app.command()
def load(
    input: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed loading information"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reload even if already cached"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be loaded without actually loading"),
    build_index: bool = typer.Option(False, "--build-index", help="Build message index as pandas DataFrame for data analysis")
):
    """
    Load ROS bag files into cache for faster operations.
    
    This command processes bag files and stores their analysis in cache,
    making subsequent inspect and extract operations much faster.
    
    Examples:
        rose load "*.bag"                       # Load all bag files in current directory
        rose load bag1.bag bag2.bag             # Load specific bag files
        rose load "test_.*\.bag"                # Load bags matching regex pattern
        rose load "*.bag" --workers 4           # Use 4 parallel workers
        rose load "*.bag" --force               # Force reload even if cached
        rose load "*.bag" --dry-run             # Preview what would be loaded
        rose load "*.bag" --build-index         # Build message index for data analysis
    """
    console = Console()
    

    # Check if input patterns are provided when not using --list
    if not input:
        Message("Error: No bag files specified. Provide bag file patterns", "error").render(console)
        raise typer.Exit(1)
    
    # Find bag files using patterns
    valid_bags = find_bag_files(input)
    
    if not valid_bags:
        Message("No bag files found matching the specified patterns", "error").render(console)  
        for pattern in input:
            Message(f"  Pattern: {pattern}", "info").render(console)
        raise typer.Exit(1)
    
    # Show found files
    Message(f"Found {len(valid_bags)} bag file(s):", "info").render(console)
    for bag in valid_bags:
        Message(f"  {bag}", "info").render(console)
    
    # Handle dry run
    if dry_run:
        Message(f"DRY RUN - Would load {len(valid_bags)} bag file(s)", "warning").render(console)

        return
    
    # Determine number of workers
    import os
    if workers is None:
        workers = max(1, os.cpu_count() - 2)
    
    analysis_type = "with index building" if build_index else "quick"
    Message(f"Loading {len(valid_bags)} bag file(s) with {workers} worker(s) ({analysis_type})...", "info").render(console)
    
    # Initialize parser
    parser = BagParser()
    
    # If force reload, clear cache for these bags
    if force:
        cache_manager = create_bag_cache_manager()
        for bag_path in valid_bags:
            cache_manager.clear(bag_path)
    
    # Load bags with individual progress bars
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        # Create individual progress tasks for each bag
        bag_tasks = {}
        for bag in valid_bags:
            task_id = progress.add_task(f"Loading {bag.name}...", total=100)
            bag_tasks[bag] = task_id
        
        # Function to create progress callback for individual bags
        def create_progress_callback(bag_path: Path, task_id):
            def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                if progress_pct > 0:
                    progress.update(task_id, completed=min(progress_pct, 100))
                if phase:
                    progress.update(task_id, description=f"Loading {bag_path.name}: {phase}")
            return progress_callback
        
        # Use ThreadPoolExecutor for parallel loading
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks with individual progress callbacks
            future_to_bag = {}
            for bag_path in valid_bags:
                task_id = bag_tasks[bag_path]
                progress_callback = create_progress_callback(bag_path, task_id)
                future = executor.submit(
                    await_sync, 
                    load_single_bag(bag_path, parser, verbose, build_index, progress_callback)
                )
                future_to_bag[future] = bag_path
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_bag):
                bag_path = future_to_bag[future]
                task_id = bag_tasks[bag_path]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Complete the progress bar
                    progress.update(task_id, completed=100)
                    
                    # Update description based on result
                    status_desc = {
                        'loaded': f"{bag_path.name} - Loaded",
                        'already_cached': f"{bag_path.name} - Already cached",
                        'error': f"{bag_path.name} - Error"
                    }.get(result['status'], f"{bag_path.name} - Unknown")
                    
                    progress.update(task_id, description=status_desc)
                    
                    if verbose:
                        status_color = {
                            'loaded': 'green',
                            'already_cached': 'yellow', 
                            'error': 'red'
                        }.get(result['status'], 'white')
                        console.print(f"[{status_color}]{result['path']}: {result['message']}[/{status_color}]")
                        
                except Exception as e:
                    logger.error(f"Unexpected error loading {bag_path}: {e}")
                    results.append({
                        'path': str(bag_path),
                        'status': 'error',
                        'message': f"Unexpected error: {e}"
                    })
                    progress.update(task_id, completed=100, description=f"{bag_path.name} - Error")
    
    # Show summary
    loaded_count = sum(1 for r in results if r['status'] == 'loaded')
    cached_count = sum(1 for r in results if r['status'] == 'already_cached')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    Message("Loading Summary", "info").render(console)
    
    # Simple text-based summary
    summary_lines = []
    if loaded_count > 0:
        summary_lines.append(f"{loaded_count} bag(s) newly loaded into cache")
    if cached_count > 0:
        summary_lines.append(f"{cached_count} bag(s) already in cache")
    if error_count > 0:
        summary_lines.append(f"{error_count} bag(s) failed to load")
    
    for line in summary_lines:
        console.print(f"  {line}")
    
    # Show errors if any
    if error_count > 0:
        Message("Errors:", "error").render(console)
        for result in results:
            if result['status'] == 'error':
                Message(f"  {result['path']}: {result['message']}", "error").render(console)
    
    # Show success message
    total_ready = loaded_count + cached_count
    if total_ready > 0:
        Message(f"Ready: {total_ready} bag(s) available for inspect and extract commands", "success").render(console)
    
    if error_count > 0:
        raise typer.Exit(1)


# Register load as the default command
app.command()(load)

if __name__ == "__main__":
    app()