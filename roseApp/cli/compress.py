#!/usr/bin/env python3
"""
Compress command for ROS bag file compression
Compress ROS bag files with different compression algorithms
"""

import os
import asyncio
import concurrent.futures
import glob
import re
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn, TimeElapsedColumn
from ..core.parser import BagParser, ExtractOption
from ..ui.common_ui import (
    CommonUI, Message
)
from ..ui.theme import get_color
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.cache import create_bag_cache_manager
from .util import check_and_load_bag_cache


# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="compress", help="Compress ROS bag files with different compression algorithms")


def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


def find_bag_files(input_patterns: List[str]) -> List[Path]:
    """Find bag files using glob patterns and regex"""
    bag_files = []
    
    for pattern in input_patterns:
        # First try as glob pattern
        if any(char in pattern for char in ['*', '?', '[']):
            expanded = glob.glob(pattern, recursive=True)
            bag_files.extend([Path(f) for f in expanded if f.endswith('.bag')])
        else:
            # Try as direct file path
            path = Path(pattern)
            if path.exists() and path.suffix == '.bag':
                bag_files.append(path)
            else:
                # Try as regex pattern
                try:
                    regex = re.compile(pattern)
                    # Search in current directory and subdirectories
                    for root, dirs, files in os.walk('.'):
                        for file in files:
                            if file.endswith('.bag') and regex.search(file):
                                bag_files.append(Path(root) / file)
                except re.error:
                    # Not a valid regex, skip
                    pass
    
    # Remove duplicates and sort
    unique_bags = list(set(bag_files))
    unique_bags.sort()
    
    return unique_bags


async def validate_bag_file(bag_path: Path) -> dict:
    """Validate that a bag file can be read correctly"""
    try:
        parser = BagParser()
        
        # Try to load the bag file
        bag_info, _ = await parser.load_bag_async(str(bag_path), build_index=False)
        
        # Check if we got valid bag info
        if not bag_info or not bag_info.topics:
            return {
                'valid': False,
                'error': 'No topics found in bag file',
                'topics_count': 0,
                'messages_count': 0
            }
        
        # Get basic statistics
        topics_count = len(bag_info.get_topic_names())
        
        # Count messages by actually reading the bag file
        messages_count = 0
        try:
            from rosbags.rosbag1 import Reader as ROS1Reader
            from rosbags.rosbag2 import Reader as ROS2Reader
            
            # Try ROS1 format first (most common for compressed bags)
            try:
                with ROS1Reader(str(bag_path)) as reader:
                    # Count all messages and validate first few
                    validation_count = 0
                    for connection, timestamp, rawdata in reader.messages():
                        # Validate first 10 messages
                        if validation_count < 10:
                            # Just check that we can read the raw data
                            if rawdata is None or len(rawdata) == 0:
                                return {
                                    'valid': False,
                                    'error': 'Empty message data found',
                                    'topics_count': topics_count,
                                    'messages_count': messages_count
                                }
                            validation_count += 1
                        messages_count += 1
            except Exception:
                # If ROS1 fails, try ROS2 format
                try:
                    with ROS2Reader(str(bag_path)) as reader:
                        # Count all messages and validate first few
                        validation_count = 0
                        for connection, timestamp, rawdata in reader.messages():
                            # Validate first 10 messages
                            if validation_count < 10:
                                # Just check that we can read the raw data
                                if rawdata is None or len(rawdata) == 0:
                                    return {
                                        'valid': False,
                                        'error': 'Empty message data found',
                                        'topics_count': topics_count,
                                        'messages_count': messages_count
                                    }
                                validation_count += 1
                            messages_count += 1
                except Exception as e2:
                    return {
                        'valid': False,
                        'error': f'Failed to read bag file with both ROS1 and ROS2 readers: {str(e2)}',
                        'topics_count': topics_count,
                        'messages_count': messages_count
                    }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Failed to read bag file: {str(e)}',
                'topics_count': topics_count,
                'messages_count': messages_count
            }
        
        return {
            'valid': True,
            'error': None,
            'topics_count': topics_count,
            'messages_count': messages_count
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'topics_count': 0,
            'messages_count': 0
        }


async def compress_single_bag(
    bag_path: Path, 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    verbose: bool = False, 
    progress_callback=None,
    cache_manager=None
) -> dict:
    """Compress a single bag file"""
    try:
        # Generate output path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_str = output_pattern
        
        # Replace placeholders
        if '{input}' in output_str:
            output_str = output_str.replace('{input}', bag_path.stem)
        if '{timestamp}' in output_str:
            output_str = output_str.replace('{timestamp}', timestamp)
        if '{compression}' in output_str:
            output_str = output_str.replace('{compression}', compression)
        
        # If no placeholders were found, create a default pattern
        if '{input}' not in output_pattern and '{timestamp}' not in output_pattern and '{compression}' not in output_pattern:
            output_str = f"{bag_path.stem}_{compression}_{timestamp}.bag"
        
        output_path = Path(output_str)
        
        # Get all topics from cache if available, otherwise load
        all_topics = []
        if cache_manager:
            cached_entry = cache_manager.get_analysis(bag_path)
            if cached_entry and cached_entry.is_valid(bag_path):
                all_topics = cached_entry.bag_info.get_topic_names()
        
        # If not in cache, load bag info
        if not all_topics:
            parser = BagParser()
            bag_info, _ = await parser.load_bag_async(str(bag_path), build_index=False)
            all_topics = bag_info.get_topic_names()
        
        # Create ExtractOption for compression (include all topics)
        # Reduce memory limit for compression to avoid OOM
        extract_option = ExtractOption(
            topics=all_topics,
            compression=compression,
            overwrite=overwrite,
            memory_limit_mb=256  # Reduce memory limit for compression
        )
        
        # Progress callback wrapper
        def progress_wrapper(percent):
            if progress_callback:
                progress_callback(percent)
        
        # Create a new parser instance for each compression to avoid memory issues
        parser = BagParser()
        
        # Perform the compression using extract functionality
        result_message, elapsed_time = parser.extract(
            str(bag_path), 
            str(output_path), 
            extract_option,
            progress_callback=progress_wrapper
        )
        
        return {
            'success': True,
            'input_file': str(bag_path),
            'output_file': str(output_path),
            'compression': compression,
            'elapsed_time': elapsed_time,
            'message': result_message,
            'topics_count': len(all_topics)
        }
        
    except Exception as e:
        logger.error(f"Error compressing {bag_path}: {str(e)}")
        return {
            'success': False,
            'input_file': str(bag_path),
            'output_file': None,
            'error': str(e),
            'message': str(e)
        }


@app.command()
def compress(
    input_bags: List[str] = typer.Argument(..., help="Bag file patterns (supports glob and regex)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp, {compression} for compression type)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    compression: str = typer.Option("lz4", "--compression", "-c", help="Compression type: bz2, lz4"),
    validate: bool = typer.Option(False, "--validate", help="Validate compressed bag files after compression"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be compressed without doing it"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed compression information"),

):
    """
    Compress ROS bag files with different compression algorithms (supports multiple files and patterns)
    
    If bag files are not in cache, you will be prompted to load them automatically.
    
    Examples:
        rose compress "*.bag" --compression lz4                                      # Compress all bag files with LZ4
        rose compress input.bag --compression bz2 -o "{input}_{compression}.bag"    # Single file with pattern
        rose compress bag1.bag bag2.bag --compression lz4 --workers 4               # Multiple files, parallel compression
        rose compress "*.bag" --compression bz2 --dry-run                           # Preview compression without doing it
    """
    await_sync(_compress_bags_impl(input_bags, output, workers, compression, validate, dry_run, yes, verbose))


async def _compress_bags_impl(
    input_bags: List[str],
    output: Optional[str],
    workers: Optional[int],
    compression: str,
    validate: bool,
    dry_run: bool,
    yes: bool,
    verbose: bool
):
    """Implementation of compress command"""
    console = Console()
    
    # Find bag files using patterns
    valid_bags = find_bag_files(input_bags)
    
    if not valid_bags:
        Message.error("No bag files found matching the specified patterns", console)
        for pattern in input_bags:
            Message.info(f"  Pattern: {pattern}", console)
        raise typer.Exit(1)
    
    # Show found files
    Message.info(f"Found {len(valid_bags)} bag file(s):", console)
    for bag in valid_bags:
        Message.primary(f"  {bag}", console)
    
    # Check if bags are loaded in cache
    cache_manager = create_bag_cache_manager()
    uncached_bags = []
    
    for bag_path in valid_bags:
        cached_entry = cache_manager.get_analysis(bag_path)
        if not cached_entry or not cached_entry.is_valid(bag_path):
            uncached_bags.append(bag_path)
    
    if uncached_bags:
        Message.warning(f"{len(uncached_bags)} bag(s) not in cache. They need to be loaded first.", console)
        if not yes and not typer.confirm("Load uncached bags automatically?"):
            Message.warning("Operation cancelled", console)
            raise typer.Exit(0)
        
        # Load uncached bags directly without additional prompts
        from ..core.parser import create_parser
        
        for bag_path in uncached_bags:
            Message.info(f"Loading bag file into cache: {bag_path}", console)
            start_time = time.time()
            parser = create_parser()
            try:
                # Use await since we're already in an async function
                await parser.load_bag_async(bag_path, build_index=False)
                elapsed = time.time() - start_time
                Message.success(f"Successfully loaded bag into cache in {elapsed:.2f}s", console)
            except Exception as e:
                Message.error(f"Failed to load bag: {e}", console)
                Message.error(f"Failed to load bag: {bag_path}", console)
                raise typer.Exit(1)
    
    # Validate compression option
    valid_compression = ["bz2", "lz4"]
    if compression not in valid_compression:
        Message.error(f"Invalid compression '{compression}'. Valid options: {', '.join(valid_compression)}", console)
        raise typer.Exit(1)
    
    # Set default output pattern if not specified
    if not output:
        output_pattern = "{input}_{compression}_{timestamp}.bag"
    else:
        output_pattern = output
    
    # Dry run preview
    if dry_run:
        Message.warning(f"DRY RUN - Would compress {len(valid_bags)} bag file(s) with {compression}:", console)
        for bag_path in valid_bags:
            # Generate output path for preview
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            preview_output = output_pattern
            if '{input}' in preview_output:
                preview_output = preview_output.replace('{input}', bag_path.stem)
            if '{timestamp}' in preview_output:
                preview_output = preview_output.replace('{timestamp}', timestamp)
            if '{compression}' in preview_output:
                preview_output = preview_output.replace('{compression}', compression)
            else:
                if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
                    preview_output = f"{bag_path.stem}_{compression}_{timestamp}.bag"
            
            Message.primary(f"  {bag_path} -> {preview_output}", console)
        
        Message.info(f"Compression: {compression}", console)
        return
    
    # Determine number of workers - be more conservative for compression
    if workers is None:
        # For compression, use fewer workers to avoid memory issues
        workers = max(1, min(4, (os.cpu_count() // 2) if os.cpu_count() else 1))
    else:
        workers = max(1, min(workers, len(valid_bags), 6))  # Cap at 6 workers max
    
    # Perform compression
    Message.info(f"Compressing {len(valid_bags)} bag file(s) with {workers} worker(s) (using {compression} compression)...", console)
    
    # Track timing and results
    compression_start_time = time.time()
    results = []
    
    # Use ThreadPoolExecutor for parallel processing
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[{get_color('primary')}][progress.description]{{task.description}}[/{get_color('primary')}]"),
        BarColumn(complete_style=get_color('success'), finished_style=get_color('success')),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        refresh_per_second=10
    ) as progress:
        
        # Create tasks for each bag
        tasks = {}
        for bag_path in valid_bags:
            task_id = progress.add_task(f"{bag_path.name} - Compressing", total=100)
            tasks[bag_path] = task_id
        
        def create_progress_callback(task_id):
            def callback(percent):
                progress.update(task_id, completed=percent)
            return callback
        
        # Execute compression in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all compression tasks
            futures = {}
            for bag_path in valid_bags:
                progress_callback = create_progress_callback(tasks[bag_path])
                future = executor.submit(
                    await_sync,
                    compress_single_bag(
                        bag_path, 
                        output_pattern, 
                        compression, 
                        overwrite=yes, 
                        verbose=verbose, 
                        progress_callback=progress_callback,
                        cache_manager=cache_manager
                    )
                )
                futures[future] = bag_path
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                bag_path = futures[future]
                task_id = tasks[bag_path]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        progress.update(task_id, description=f"[green]✓ {bag_path.name} - Compressed[/green]", completed=100)
                    else:
                        progress.update(task_id, description=f"[red]✗ {bag_path.name} - Failed[/red]", completed=100)
                        
                except Exception as e:
                    logger.error(f"Unexpected error compressing {bag_path}: {str(e)}")
                    results.append({
                        'success': False,
                        'input_file': str(bag_path),
                        'output_file': None,
                        'error': str(e),
                        'message': str(e)
                    })
                    progress.update(task_id, description=f"[red]✗ {bag_path.name} - Error[/red]", completed=100)
    
    # Validate compressed files if requested
    if validate and results:
        successful_results = [r for r in results if r['success']]
        if successful_results:
            console.print()
            Message.info("Validating compressed bag files...", console)
            
            validation_results = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}", style=get_color('primary')),
                BarColumn(complete_style=get_color('success'), finished_style=get_color('success')),
                TaskProgressColumn(style=get_color('info')),
                TimeElapsedColumn(style=get_color('muted')),
                console=console,
                refresh_per_second=10
            ) as progress:
                
                # Create validation tasks
                validation_tasks = {}
                for result in successful_results:
                    output_path = Path(result['output_file'])
                    task_id = progress.add_task(f"Validating {output_path.name}", total=100)
                    validation_tasks[result['output_file']] = task_id
                
                # Validate files in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(successful_results))) as executor:
                    validation_futures = {}
                    for result in successful_results:
                        output_path = Path(result['output_file'])
                        future = executor.submit(await_sync, validate_bag_file(output_path))
                        validation_futures[future] = result
                    
                    # Collect validation results
                    for future in concurrent.futures.as_completed(validation_futures):
                        result = validation_futures[future]
                        task_id = validation_tasks[result['output_file']]
                        
                        try:
                            validation_result = future.result()
                            validation_results.append({
                                'file': result['output_file'],
                                'original_result': result,
                                **validation_result
                            })
                            
                            if validation_result['valid']:
                                progress.update(task_id, description=f"[green]✓ {Path(result['output_file']).name} - Valid[/green]", completed=100)
                            else:
                                progress.update(task_id, description=f"[red]✗ {Path(result['output_file']).name} - Invalid[/red]", completed=100)
                                
                        except Exception as e:
                            logger.error(f"Validation error for {result['output_file']}: {str(e)}")
                            validation_results.append({
                                'file': result['output_file'],
                                'original_result': result,
                                'valid': False,
                                'error': str(e),
                                'topics_count': 0,
                                'messages_count': 0
                            })
                            progress.update(task_id, description=f"[red]✗ {Path(result['output_file']).name} - Error[/red]", completed=100)
            
            # Show validation summary
            console.print()
            valid_files = [v for v in validation_results if v['valid']]
            invalid_files = [v for v in validation_results if not v['valid']]
            
            Message.primary("Validation Summary", console)
            if valid_files:
                Message.success(f"  {len(valid_files)} bag(s) passed validation", console)
                if verbose:
                    for v in valid_files:
                        Message.info(f"    {Path(v['file']).name}: {v['topics_count']} topics, {v['messages_count']} messages", console)
            
            if invalid_files:
                Message.error(f"  {len(invalid_files)} bag(s) failed validation", console)
                for v in invalid_files:
                    Message.error(f"    {Path(v['file']).name}: {v['error']}", console)
    
    # Calculate total time
    total_time = time.time() - compression_start_time
    
    # Use new UI components for display
    from ..ui.compress_ui import CompressUI
    
    compress_ui = CompressUI()
    compress_ui.display_batch_results(results, total_time)


if __name__ == "__main__":
    app()
