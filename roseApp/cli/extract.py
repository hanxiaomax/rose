#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction.
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
from ..core.steps import create_step_manager

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


def filter_topics(all_topics: List[str], topic_patterns: List[str], exclude_pattern=None):
    """Filter topics using regex patterns"""
    matched_topics = set()
    
    for pattern in topic_patterns:
        try:
            regex = re.compile(pattern)
            for topic in all_topics:
                if regex.search(topic):
                    matched_topics.add(topic)
        except re.error:
            # If not valid regex, try exact match
            if pattern in all_topics:
                matched_topics.add(pattern)
    
    result = list(matched_topics)
    
    if exclude_pattern:
        exclude_regex = re.compile(exclude_pattern)
        result = [t for t in result if not exclude_regex.search(t)]
    
    return result


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
        logger.error(f"Failed to extract from {bag_path}: {e}", exc_info=True)
        return {
            'path': str(bag_path),
            'output_path': None,
            'status': 'error',
            'message': str(e),
            'elapsed_time': 0.0
        }


@app.command()
def extract(
    input_bags: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information"),
    load: bool = typer.Option(False, "--load", help="Load bags if not cached (without building index)"),
    load_index: bool = typer.Option(False, "--load-index", help="Load bags with index building if not cached"),
):
    """
    Extract specific topics from ROS bag files (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load' or use --load option.
    
    Examples:
        rose extract "*.bag" --topics gps imu                                    # Extract from all bag files
        rose extract input.bag --topics /gps/fix -o "{input}_filtered.bag"      # Single file with pattern
        rose extract bag1.bag bag2.bag --topics tf --reverse                    # Multiple files, exclude tf
        rose extract "*.bag" --topics gps --compression lz4 --workers 4         # Parallel extraction with compression
        rose extract "*.bag" --topics gps --load                                 # Auto load if not cached
    """
    start_total_time = time.time()
    out = get_output()
    steps = create_step_manager()
    
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
        # Validate input arguments
        if not input_bags:
            out.error(
                "No bag files specified",
                details="Provide bag file patterns: rose extract '*.bag' --topics gps"
            )
            raise typer.Exit(1)
        
        if not topics:
            out.error(
                "No topics specified",
                details="Use --topics to specify topics: rose extract demo.bag --topics gps imu"
            )
            raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
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
        
        # Stage 2: Cache check and auto-load if needed
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
            output_pattern = "{input}_filtered_{timestamp}.bag"
        else:
            output_pattern = output
        
        # Stage 3: Topic analysis
        steps.section("Analyzing topics")
        steps.add_item("analyze", "Scanning topics from cached data", "processing")
        
        all_topics_set = set()
        for bag_path in valid_bags:
            cached_entry = cache_manager.get_analysis(bag_path)
            bag_info = cached_entry.bag_info
            if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
                bag_topics = bag_info.topics if isinstance(bag_info.topics[0], str) else [topic.name for topic in bag_info.topics]
                all_topics_set.update(bag_topics)
        
        all_topics = list(all_topics_set)
        if not all_topics:
            steps.error_item("analyze", "No topics found in cached bag analysis")
            raise typer.Exit(1)
        
        steps.complete_item("analyze", f"Found {len(all_topics)} unique topics")
        
        # Apply topic filtering
        steps.section("Filtering topics")
        steps.add_item("filter", f"Applying pattern: {', '.join(topics)}", "processing")
        
        if reverse:
            # Reverse selection: exclude topics that match the patterns
            topics_to_exclude = filter_topics(all_topics, topics, None)
            topics_to_extract = [t for t in all_topics if t not in topics_to_exclude]
            operation = "excluding"
        else:
            # Normal selection: include topics that match the patterns
            topics_to_extract = filter_topics(all_topics, topics, None)
            operation = "including"
        
        if not topics_to_extract:
            steps.error_item("filter", f"No topics match: {', '.join(topics)}")
            raise typer.Exit(1)
        
        steps.complete_item("filter", f"Selected {len(topics_to_extract)} of {len(all_topics)} topics ({operation})")
        
        # Show selected topics directly (not as items)
        out.print(f"  Topics to extract:")
        for topic in sorted(topics_to_extract):
            out.print(f"    {topic}")
        
        # Show extraction plan
        steps.section("Extraction plan")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        for bag_path in valid_bags:
            preview_output = output_pattern
            if '{input}' in preview_output:
                preview_output = preview_output.replace('{input}', bag_path.stem)
            if '{timestamp}' in preview_output:
                preview_output = preview_output.replace('{timestamp}', timestamp)
            else:
                if '{input}' not in output_pattern and '{timestamp}' not in output_pattern:
                    preview_output = f"{bag_path.stem}_{output_pattern}_{timestamp}.bag"
            out.print(f"  {bag_path.name} → {preview_output}")
        
        # Ask for confirmation
        if not yes:
            out.newline()
            try:
                sys.stdout.write(f"Extract {len(topics_to_extract)} topics from {len(valid_bags)} bag(s)? (y/N): ")
                sys.stdout.flush()
                response = input().strip().lower()
                if response not in ['y', 'yes']:
                    out.info("Cancelled")
                    return
            except (EOFError, KeyboardInterrupt):
                out.newline()
                out.info("Cancelled")
                return
        
        # Determine number of workers
        if workers is None:
            workers = max(1, (os.cpu_count() or 2) - 2)
        workers = min(workers, len(valid_bags))
        
        if verbose:
            out.newline()
            compression_display = "None" if compression == "none" else compression.upper()
            out.key_value({
                "Total bags": len(valid_bags),
                "Workers": workers,
                "Compression": compression_display,
                "Topics": len(topics_to_extract),
                "Output pattern": output_pattern
            }, title="Extraction Details")
        
        # Stage 4: Extraction
        results = []
        total_bags = len(valid_bags)
        bag_list = list(valid_bags)  # Convert to list for indexing
        
        # Determine number of workers
        if workers is None:
            workers = max(1, (os.cpu_count() or 2) - 2)
        workers = min(workers, len(valid_bags))
        
        # Show extraction settings
        compression_display = "None" if compression == "none" else compression.upper()
        is_parallel = workers > 1
        mode_str = f"parallel, {workers} workers" if is_parallel else "serial"
        steps.section(f"Extracting topics ({mode_str}, compression: {compression_display})")
        
        # Process bags with live status
        with out.live_status(f"Processing", total=total_bags) as status:
            # Add all bags as pending first
            for bag_path in bag_list:
                status.add_item(bag_path.name, bag_path.name, "pending")
            
            # Process bags
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_bag = {}
                
                def create_progress_callback(bag_name):
                    def callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                        if phase and verbose:
                            logger.debug(f"{bag_name}: {phase}")
                    return callback
                
                # Submit all tasks
                for i, bag_path in enumerate(bag_list):
                    # Only mark first `workers` items as processing initially
                    if i < workers:
                        status.update_item(bag_path.name, "processing")
                    
                    cb = create_progress_callback(bag_path.name)
                    future = executor.submit(
                        await_sync, 
                        extract_single_bag(bag_path, topics_to_extract, output_pattern, compression, yes, verbose, cb)
                    )
                    future_to_bag[future] = (i, bag_path)
                
                # Track completed count
                completed_count = 0
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_bag):
                    idx, bag_path = future_to_bag[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # Update status based on result
                        result_status = result['status']
                        if result_status == 'extracted':
                            output_name = Path(result['output_path']).name if result.get('output_path') else 'N/A'
                            elapsed = result.get('elapsed_time', 0)
                            status.update_item(
                                bag_path.name, "done",
                                f"→ {output_name} ({elapsed:.1f}s)"
                            )
                        else:
                            error_msg = result.get('message', 'Unknown error')
                            status.update_item(
                                bag_path.name, "error",
                                f"· {error_msg}"
                            )
                        
                    except Exception as e:
                        logger.error(f"Unexpected error extracting {bag_path}: {e}")
                        results.append({
                            'path': str(bag_path),
                            'output_path': None,
                            'status': 'error',
                            'message': f"Unexpected error: {e}",
                            'elapsed_time': 0.0
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
        
        # Calculate summary
        success_count = sum(1 for r in results if r['status'] == 'extracted')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_time = time.time() - start_total_time
        
        # Show summary as step
        if error_count == 0:
            steps.section("Extraction complete")
        else:
            steps.section("Extraction complete (with errors)")
        
        out.print(f"  Extracted : {success_count}")
        out.print(f"  Failed    : {error_count}")
        out.print(f"  Topics    : {len(topics_to_extract)}")
        out.print(f"  Compression: {compression}")
        out.print(f"  Time      : {total_time:.2f}s")
        
        # Exit with error if any extractions failed
        if error_count > 0:
            raise typer.Exit(1)
        
    except typer.Exit:
        raise
    except Exception as e:
        out.error(str(e))
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)


# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app()
