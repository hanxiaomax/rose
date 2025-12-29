#!/usr/bin/env python3
"""
Compress command for ROS bag file compression.
"""

import os
import asyncio
import concurrent.futures
import glob
import re
import sys
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.parser import BagParser, ExtractOption
from ..core.logging import get_logger
from ..core.cache import create_bag_cache_manager
from ..core.output import get_output
from ..core.steps import StepManager

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


def _load_bag_into_cache(bag_path: Path, out, build_index: bool = False, verbose: bool = False):
    """Load a bag file into cache"""
    try:
        parser = BagParser()
        
        load_msg = f"Loading {bag_path.name}" + (" (building index)" if build_index else "")
        with out.spinner(load_msg):
            bag_info, elapsed_time = await_sync(
                parser.load_bag_async(str(bag_path), build_index=build_index)
            )
        
        if verbose:
            out.success(f"Loaded in {elapsed_time:.2f}s")
        else:
            out.success("Loaded successfully")
        
        return True
    except Exception as e:
        out.error(f"Failed to load: {str(e)}")
        logger.error(f"Error loading bag {bag_path}: {e}")
        return False


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
                    pass
    
    # Remove duplicates and sort
    unique_bags = list(set(bag_files))
    unique_bags.sort()
    
    return unique_bags


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
        extract_option = ExtractOption(
            topics=all_topics,
            compression=compression,
            overwrite=overwrite,
            memory_limit_mb=256
        )
        
        # Progress callback wrapper
        def progress_wrapper(percent):
            if progress_callback:
                progress_callback(percent)
        
        # Create a new parser instance for each compression
        parser = BagParser()
        
        # Perform the compression using extract functionality
        result_message, elapsed_time = parser.extract(
            str(bag_path), 
            str(output_path), 
            extract_option,
            progress_callback=progress_wrapper
        )
        
        # Get file sizes for compression ratio
        input_size = bag_path.stat().st_size
        output_size = output_path.stat().st_size if output_path.exists() else 0
        compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
        
        return {
            'status': 'compressed',
            'input_file': str(bag_path),
            'output_file': str(output_path),
            'compression': compression,
            'elapsed_time': elapsed_time,
            'message': result_message,
            'topics_count': len(all_topics),
            'input_size_mb': input_size / 1024 / 1024,
            'output_size_mb': output_size / 1024 / 1024,
            'compression_ratio': compression_ratio
        }
        
    except Exception as e:
        logger.error(f"Error compressing {bag_path}: {str(e)}")
        return {
            'status': 'error',
            'input_file': str(bag_path),
            'output_file': None,
            'error': str(e),
            'message': str(e)
        }


@app.command()
def compress(
    input_bags: List[str] = typer.Argument(..., help="Bag file patterns (supports glob and regex)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp, {compression} for compression type)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count / 2, max 4)"),
    compression: str = typer.Option("lz4", "--compression", "-c", help="Compression type: bz2, lz4"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed compression information"),
    load: bool = typer.Option(False, "--load", help="Load bags if not cached (without building index)"),
    load_index: bool = typer.Option(False, "--load-index", help="Load bags with index building if not cached"),
):
    """
    Compress ROS bag files with different compression algorithms (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load' or use --load option.
    
    Examples:
        rose compress "*.bag" --compression lz4                                      # Compress all bag files with LZ4
        rose compress input.bag --compression bz2 -o "{input}_{compression}.bag"    # Single file with pattern
        rose compress bag1.bag bag2.bag --compression lz4 --workers 4               # Multiple files, parallel compression
        rose compress "*.bag" --compression bz2 --load                               # Auto load if not cached
    """
    start_total_time = time.time()
    out = get_output()
    steps = StepManager()
    
    # Check mutually exclusive options
    if load and load_index:
        out.error(
            "Options --load and --load-index are mutually exclusive",
            details="Use --load for quick load without index, or --load-index to build index"
        )
        raise typer.Exit(1)
    
    # Determine effective load mode
    should_load = load or load_index
    build_index = load_index
    
    try:
        # Validate compression option
        valid_compression = ["bz2", "lz4"]
        if compression not in valid_compression:
            out.error(
                f"Invalid compression: {compression}",
                details=f"Valid options: {', '.join(valid_compression)}"
            )
            raise typer.Exit(1)
        
        # Stage 1: Discovery
        steps.section("Finding bag files")
        steps.add_item("scan", "Scanning directories", "processing")
        valid_bags = find_bag_files(input_bags)
        
        if not valid_bags:
            steps.error_item("scan", "No bag files found")
            raise typer.Exit(1)
        
        steps.complete_item("scan", f"Found {len(valid_bags)} bag file(s)")
        
        # Display found bags directly (not as items)
        for bag in valid_bags:
            size_mb = bag.stat().st_size / 1024 / 1024
            out.print(f"  {bag.name} ({size_mb:.1f} MB)")
        
        # Stage 2: Cache check
        steps.section("Checking cache")
        cache_manager = create_bag_cache_manager()
        uncached_bags = []
        
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            if not cached_entry or not cached_entry.is_valid(bag_path):
                uncached_bags.append(bag_path)
        
        if uncached_bags:
            if should_load:
                # Auto-load uncached bags
                steps.add_item("load", f"Loading {len(uncached_bags)} bag(s)", "processing")
                
                # Show uncached bags directly
                for bag in uncached_bags:
                    out.print(f"  {bag.name}")
                
                for bag_path in uncached_bags:
                    if not _load_bag_into_cache(bag_path, out, build_index=build_index, verbose=verbose):
                        steps.error_item("load", "Failed to load bags")
                        raise typer.Exit(1)
                
                steps.complete_item("load", f"Loaded {len(uncached_bags)} bag(s)")
            else:
                # Ask user if they want to load
                steps.add_item("cache_check", f"{len(uncached_bags)} bag(s) not in cache", "error")
                
                # Show uncached bags directly
                for bag in uncached_bags:
                    out.print(f"  {bag.name}")
                
                try:
                    out.newline()
                    sys.stdout.write(f"Load {len(uncached_bags)} bag(s) now? (y/N): ")
                    sys.stdout.flush()
                    response = input().strip().lower()
                    if response in ['y', 'yes']:
                        steps.update_item("cache_check", f"Loading {len(uncached_bags)} bag(s)", "processing")
                        for bag_path in uncached_bags:
                            if not _load_bag_into_cache(bag_path, out, build_index=False, verbose=verbose):
                                steps.error_item("cache_check", "Failed to load bags")
                                raise typer.Exit(1)
                        steps.complete_item("cache_check", f"Loaded {len(uncached_bags)} bag(s)")
                    else:
                        out.info("Cancelled")
                        raise typer.Exit(0)
                except (EOFError, KeyboardInterrupt):
                    out.newline()
                    out.info("Cancelled")
                    raise typer.Exit(0)
        else:
            steps.add_item("cache_check", "All bags cached", "done")
        
        # Set default output pattern if not specified
        if not output:
            output_pattern = "{input}_{compression}_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Determine number of workers - be conservative for compression
        if workers is None:
            # For compression, use fewer workers to avoid memory issues
            workers = max(1, min(4, (os.cpu_count() // 2) if os.cpu_count() else 1))
        else:
            workers = max(1, min(workers, len(valid_bags), 6))  # Cap at 6 workers max
        
        # Stage 3: Show compression plan
        steps.section(f"Compression plan (Algorithm: {compression.upper()}, Workers: {workers})")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        for bag_path in valid_bags:
            preview_output = output_pattern
            if '{input}' in preview_output:
                preview_output = preview_output.replace('{input}', bag_path.stem)
            if '{compression}' in preview_output:
                preview_output = preview_output.replace('{compression}', compression)
            if '{timestamp}' in preview_output:
                preview_output = preview_output.replace('{timestamp}', timestamp)
            else:
                if '{input}' not in output_pattern and '{compression}' not in output_pattern and '{timestamp}' not in output_pattern:
                    preview_output = f"{bag_path.stem}_{compression}_{timestamp}.bag"
            out.print(f"  {bag_path.name} → {preview_output}")
        
        # Ask for confirmation if not yes
        if not yes:
            try:
                out.newline()
                sys.stdout.write("Proceed with compression? (y/N): ")
                sys.stdout.flush()
                response = input().strip().lower()
                if response not in ['y', 'yes']:
                    out.info("Cancelled")
                    raise typer.Exit(0)
            except (EOFError, KeyboardInterrupt):
                out.newline()
                out.info("Cancelled")
                raise typer.Exit(0)
        
        # Stage 4: Perform compression with real-time status
        # Determine processing mode
        is_parallel = workers > 1
        mode_str = f"parallel, {workers} workers" if is_parallel else "serial"
        steps.section(f"Compressing bags ({mode_str})")
        
        results = []
        total_bags = len(valid_bags)
        bag_list = list(valid_bags)  # Convert to list for indexing
        
        # Process bags with live status
        with out.live_status(f"Processing", total=total_bags) as status:
            # Add all bags as pending first
            for bag_path in bag_list:
                status.add_item(bag_path.name, bag_path.name, "pending")
            
            # Process bags
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {}
                
                def create_progress_callback(bag_name):
                    def callback(percent):
                        if verbose:
                            logger.debug(f"{bag_name}: {percent:.1f}%")
                    return callback
                
                # Submit all tasks
                for i, bag_path in enumerate(bag_list):
                    # Only mark first `workers` items as processing initially
                    if i < workers:
                        status.update_item(bag_path.name, "processing")
                    
                    cb = create_progress_callback(bag_path.name)
                    future = executor.submit(
                        await_sync,
                        compress_single_bag(
                            bag_path, 
                            output_pattern, 
                            compression, 
                            overwrite=yes, 
                            verbose=verbose, 
                            progress_callback=cb,
                            cache_manager=cache_manager
                        )
                    )
                    futures[future] = (i, bag_path)
                
                # Track completed count to know when to mark next as processing
                completed_count = 0
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    idx, bag_path = futures[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # Update status based on result
                        result_status = result['status']
                        if result_status == 'compressed':
                            ratio = result.get('compression_ratio', 0)
                            output_name = Path(result['output_file']).name if result.get('output_file') else 'N/A'
                            elapsed = result.get('elapsed_time', 0)
                            status.update_item(
                                bag_path.name, "done",
                                f"→ {output_name} (ratio: {ratio:.1f}%, {elapsed:.1f}s)"
                            )
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            status.update_item(
                                bag_path.name, "error",
                                f"· {error_msg}"
                            )
                        
                    except Exception as e:
                        logger.error(f"Unexpected error compressing {bag_path}: {str(e)}")
                        results.append({
                            'status': 'error',
                            'input_file': str(bag_path),
                            'output_file': None,
                            'error': str(e),
                            'message': str(e)
                        })
                        status.update_item(
                            bag_path.name, "error",
                            f"· Unexpected error"
                        )
                    
                    completed_count += 1
                    
                    # Mark next pending item as processing (if any)
                    next_processing_idx = workers + completed_count - 1
                    if next_processing_idx < total_bags:
                        next_bag = bag_list[next_processing_idx]
                        status.update_item(next_bag.name, "processing")
        
        # Stage 5: Summary
        # Calculate summary
        success_count = sum(1 for r in results if r['status'] == 'compressed')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_time = time.time() - start_total_time
        
        # Calculate average compression ratio
        successful_results = [r for r in results if r['status'] == 'compressed']
        avg_compression_ratio = (
            sum(r['compression_ratio'] for r in successful_results) / len(successful_results)
            if successful_results else 0
        )
        
        # Show summary as step
        if error_count == 0:
            steps.section("Compression complete")
        else:
            steps.section("Compression complete (with errors)")
        
        out.print(f"  Compressed: {success_count}")
        out.print(f"  Failed    : {error_count}")
        out.print(f"  Algorithm : {compression.upper()}")
        out.print(f"  Avg ratio : {avg_compression_ratio:.1f}%")
        out.print(f"  Time      : {total_time:.2f}s")
        
        # Exit with error if any compressions failed
        if error_count > 0:
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        out.error(str(e))
        logger.error(f"Compression error: {e}", exc_info=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
