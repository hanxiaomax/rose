#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction
Extract specific topics from ROS bag files using fuzzy matching
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
from ..core.ui_control import UIControl, Message
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.cache import create_bag_cache_manager
from .util import filter_topics, check_and_load_bag_cache


# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="extract", help="Extract specific topics from ROS bag files")


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


async def extract_single_bag(
    bag_path: Path, 
    topics_to_extract: List[str], 
    output_pattern: str, 
    compression: str, 
    overwrite: bool, 
    verbose: bool = False, 
    progress_callback=None
) -> dict:
    """Extract topics from a single bag file"""
    try:
        # Generate output path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_str = output_pattern
        
        # Replace placeholders
        if '{input}' in output_str:
            output_str = output_str.replace('{input}', bag_path.stem)
        if '{timestamp}' in output_str:
            output_str = output_str.replace('{timestamp}', timestamp)
        
        # If no placeholders were found, create a default pattern
        if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
            output_str = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
        
        output_path = Path(output_str)
        
        # Create ExtractOption
        extract_option = ExtractOption(
            topics=topics_to_extract,
            compression=compression,
            overwrite=overwrite
        )
        
        # Initialize parser
        parser = BagParser()
        
        # Execute extraction
        if progress_callback:
            progress_callback("Extracting topics...", 50.0)
        
        result_message, extraction_time = parser.extract(
            str(bag_path),
            str(output_path),
            extract_option
        )
        
        if progress_callback:
            progress_callback("Complete", 100.0)
        
        if verbose:
            logger.info(f"Successfully extracted {len(topics_to_extract)} topics from {bag_path} in {extraction_time:.3f}s")
        
        return {
            'path': str(bag_path),
            'output_path': str(output_path),
            'status': 'extracted',
            'message': 'Successfully extracted topics',
            'topics_count': len(topics_to_extract),
            'elapsed_time': extraction_time
        }
        
    except Exception as e:
        logger.error(f"Failed to extract from {bag_path}: {e}")
        return {
            'path': str(bag_path),
            'output_path': None,
            'status': 'error',
            'message': str(e)
        }


# filter_topics function is now imported from .util


@app.command()
def extract(
    input_bags: List[str] = typer.Argument(..., help="Bag file patterns (supports glob and regex)"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be extracted without doing it"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information"),

):
    """
    Extract specific topics from ROS bag files (supports multiple files and patterns)
    
    If bag files are not in cache, you will be prompted to load them automatically.
    
    Examples:
        rose extract "*.bag" --topics gps imu                                    # Extract from all bag files
        rose extract input.bag --topics /gps/fix -o "{input}_filtered.bag"      # Single file with pattern
        rose extract bag1.bag bag2.bag --topics tf --reverse                    # Multiple files, exclude tf
        rose extract "*.bag" --topics gps --compression lz4 --workers 4         # Parallel extraction with compression
        rose extract "*.bag" --topics gps --dry-run                             # Preview without extraction
    """
    _extract_topics_impl(input_bags, topics, output, workers, reverse, compression, dry_run, yes, verbose)


def _extract_topics_impl(
    input_bags: List[str],
    topics: Optional[List[str]],
    output: Optional[str],
    workers: Optional[int],
    reverse: bool,
    compression: str,
    dry_run: bool,
    yes: bool,
    verbose: bool
):
    """
    Multi-file topic extraction with parallel processing
    """
    console = Console()
    
    try:
        # Validate input arguments
        if not topics:
            Message("No topics specified. Use --topics to specify topics", "error").render(console)
            raise typer.Exit(1)
        
        # Find bag files using patterns
        valid_bags = find_bag_files(input_bags)
        
        if not valid_bags:
            Message("No bag files found matching the specified patterns", "error").render(console)
            for pattern in input_bags:
                Message(f"  Pattern: {pattern}", "info").render(console)
            raise typer.Exit(1)
        
        # Show found files
        Message(f"Found {len(valid_bags)} bag file(s):", "info").render(console)
        for bag in valid_bags:
            Message(f"  {bag}", "info").render(console)
        
        # Check if bags are loaded in cache
        cache_manager = create_bag_cache_manager()
        uncached_bags = []
        
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            if not cached_entry or not cached_entry.is_valid(bag_path):
                uncached_bags.append(bag_path)
        
        if uncached_bags:
            Message(f"{len(uncached_bags)} bag(s) not in cache. They need to be loaded first.", "warning").render(console)
            if not yes and not typer.confirm("Load uncached bags automatically?"):
                Message("Operation cancelled", "warning").render(console)
                raise typer.Exit(0)
            
            # Load uncached bags directly without additional prompts (could be done in parallel, but for simplicity doing sequentially)
            from ..core.parser import create_parser
            
            for bag_path in uncached_bags:
                Message(f"Loading bag file into cache: {bag_path}", "info").render(console)
                start_time = time.time()
                parser = create_parser()
                try:
                    # Run async function in event loop
                    asyncio.run(parser.load_bag_async(bag_path, build_index=False))
                    elapsed = time.time() - start_time
                    Message(f"✓ Successfully loaded bag into cache in {elapsed:.2f}s", "success").render(console)
                except Exception as e:
                    Message(f"✗ Failed to load bag: {e}", "error").render(console)
                    Message(f"Failed to load bag: {bag_path}", "error").render(console)
                    raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            Message(f"Invalid compression '{compression}'. Valid options: {', '.join(valid_compression)}", "error").render(console)
            raise typer.Exit(1)
        
        # Set default output pattern if not specified
        if not output:
            output_pattern = "{input}_filtered_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Determine topic filtering from first bag (assuming all bags have similar topics)
        Message("Analyzing topics from bag files...", "info").render(console)
        
        # Get all unique topics from all bags
        all_topics_set = set()
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                bag_topics = bag_info.topics if isinstance(bag_info.topics[0], str) else [topic.name for topic in bag_info.topics]
                all_topics_set.update(bag_topics)
        
        all_topics = list(all_topics_set)
        if not all_topics:
            Message("No topics found in cached bag analysis", "error").render(console)
            raise typer.Exit(1)
        
        # Apply topic filtering using our filter function
        if reverse:
            # Reverse selection: exclude topics that match the patterns
            topics_to_exclude = filter_topics(all_topics, topics, None)
            topics_to_extract = [t for t in all_topics if t not in topics_to_exclude]
            operation_desc = f"Excluding topics matching: {', '.join(topics)}"
        else:
            # Normal selection: include topics that match the patterns
            topics_to_extract = filter_topics(all_topics, topics, None)
            operation_desc = f"Including topics matching: {', '.join(topics)}"
        
        if not topics_to_extract:
            Message(f"No topics match the patterns: {', '.join(topics)}", "error").render(console)
            Message(f"Available topics: {', '.join(all_topics[:10])}{'...' if len(all_topics) > 10 else ''}", "info").render(console)
            raise typer.Exit(1)
        
        # Show operation description
        Message(operation_desc, "info").render(console)
        Message(f"Will extract {len(topics_to_extract)} topic(s): {', '.join(topics_to_extract[:5])}{'...' if len(topics_to_extract) > 5 else ''}", "success").render(console)
        
        # If dry run, show preview and return
        if dry_run:
            Message(f"DRY RUN - Would extract from {len(valid_bags)} bag file(s):", "warning").render(console)
            for bag_path in valid_bags:
                # Generate output path for preview
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                if '{input}' in output_pattern:
                    preview_output = output_pattern.replace('{input}', bag_path.stem)
                elif '{timestamp}' in output_pattern:
                    preview_output = output_pattern.replace('{timestamp}', timestamp)
                else:
                    preview_output = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
                
                Message(f"  {bag_path} -> {preview_output}", "info").render(console)
            Message(f"Topics to extract: {', '.join(topics_to_extract)}", "info").render(console)
            return
        
        # Determine number of workers
        if workers is None:
            workers = max(1, os.cpu_count() - 2)
        
        analysis_type = f"with {compression} compression" if compression != "none" else "without compression"
        Message(f"Extracting from {len(valid_bags)} bag file(s) with {workers} worker(s) ({analysis_type})...", "info").render(console)
        
        # Extract bags with individual progress bars
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
                task_id = progress.add_task(f"Extracting {bag.name}...", total=100)
                bag_tasks[bag] = task_id
            
            # Function to create progress callback for individual bags
            def create_progress_callback(bag_path: Path, task_id):
                def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                    if progress_pct > 0:
                        progress.update(task_id, completed=min(progress_pct, 100))
                    if phase:
                        progress.update(task_id, description=f"Extracting {bag_path.name}: {phase}")
                return progress_callback
            
            # Use ThreadPoolExecutor for parallel extraction
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                # Submit all tasks with individual progress callbacks
                future_to_bag = {}
                for bag_path in valid_bags:
                    task_id = bag_tasks[bag_path]
                    progress_callback = create_progress_callback(bag_path, task_id)
                    future = executor.submit(
                        await_sync, 
                        extract_single_bag(bag_path, topics_to_extract, output_pattern, compression, yes, verbose, progress_callback)
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
                            'extracted': f"{bag_path.name} - Extracted",
                            'error': f"{bag_path.name} - Error"
                        }.get(result['status'], f"{bag_path.name} - Unknown")
                        
                        progress.update(task_id, description=status_desc)
                        
                        if verbose:
                            status_color = {
                                'extracted': 'green',
                                'error': 'red'
                            }.get(result['status'], 'white')
                            console.print(f"[{status_color}]{result['path']}: {result['message']}[/{status_color}]")
                            
                    except Exception as e:
                        logger.error(f"Unexpected error extracting {bag_path}: {e}")
                        results.append({
                            'path': str(bag_path),
                            'output_path': None,
                            'status': 'error',
                            'message': f"Unexpected error: {e}"
                        })
                        progress.update(task_id, completed=100, description=f"{bag_path.name} - Error")
        
        # Show summary
        extracted_count = sum(1 for r in results if r['status'] == 'extracted')
        error_count = sum(1 for r in results if r['status'] == 'error')
        
        Message("Extraction Summary", "info").render(console)
        
        # Simple text-based summary
        summary_lines = []
        if extracted_count > 0:
            summary_lines.append(f"{extracted_count} bag(s) successfully extracted")
        if error_count > 0:
            summary_lines.append(f"{error_count} bag(s) failed to extract")
        
        for line in summary_lines:
            console.print(f"  {line}")
        
        # Show errors if any
        if error_count > 0:
            Message("Errors:", "error").render(console)
            for result in results:
                if result['status'] == 'error':
                    Message(f"  {result['path']}: {result['message']}", "error").render(console)
        
        # Show success message
        if extracted_count > 0:
            Message(f"Success: {extracted_count} bag(s) extracted with {len(topics_to_extract)} topic(s) each", "success").render(console)
            
            if verbose:
                Message("Output files:", "info").render(console)
                for result in results:
                    if result['status'] == 'extracted' and result['output_path']:
                        output_path = Path(result['output_path'])
                        if output_path.exists():
                            size_mb = output_path.stat().st_size / 1024 / 1024
                            elapsed = result.get('elapsed_time', 0)
                            Message(f"  {result['output_path']} ({size_mb:.1f} MB, {elapsed:.2f}s)", "info").render(console)
        
        if error_count > 0:
            raise typer.Exit(1)
        
    except Exception as e:
        Message(f"Error during extraction: {e}", "error").render(console)
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)



# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app() 