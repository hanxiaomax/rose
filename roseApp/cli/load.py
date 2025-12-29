#!/usr/bin/env python3
"""
Load command for ROS bag files - Load bags into cache for faster operations.
"""

import asyncio
import concurrent.futures
import glob
import os
import re
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.parser import BagParser
from ..core.cache import create_bag_cache_manager
from ..core.logging import get_logger
from ..core.errors import (
    RoseError,
    BagFileError,
    handle_cli_error,
    validate_bag_file,
)
from ..core.config import get_config
from ..core.output import get_output
from ..core.steps import StepManager

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


async def load_single_bag(
    bag_path: Path, 
    parser, 
    verbose: bool = False, 
    build_index: bool = False, 
    progress_callback=None
) -> dict:
    """
    Load a single bag file into cache using parser directly.
    
    Args:
        bag_path: Path to the bag file
        parser: BagParser instance
        verbose: Enable verbose logging
        build_index: Build message index
        progress_callback: Callback for progress updates
    
    Returns:
        Dict with loading results
    """
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
                'message': 'Already in cache',
                'elapsed': 0.0
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
            'elapsed': elapsed_time
        }
        
    except Exception as e:
        logger.error(f"Failed to load {bag_path}: {e}")
        return {
            'path': str(bag_path),
            'status': 'error',
            'message': str(e),
            'elapsed': 0.0
        }


def find_bag_files(input_patterns: List[str]) -> List[Path]:
    """
    Find bag files using glob patterns and regex.
    
    Uses unified error handling to validate bag files.
    """
    bag_files = []
    
    for pattern in input_patterns:
        # First try as glob pattern
        glob_matches = glob.glob(pattern)
        if glob_matches:
            for match in glob_matches:
                path = Path(match)
                try:
                    # Validate bag file using unified validation
                    validate_bag_file(path)
                    bag_files.append(path)
                except BagFileError as e:
                    # Skip invalid files silently during discovery
                    logger.debug(f"Skipping invalid file {path}: {e.message}")
                    continue
        else:
            # Try as regex pattern in current directory
            try:
                regex = re.compile(pattern)
                current_dir = Path('.')
                for bag_file in current_dir.glob('*.bag'):
                    if regex.search(bag_file.name):
                        try:
                            validate_bag_file(bag_file)
                            bag_files.append(bag_file)
                        except BagFileError:
                            continue
            except re.error:
                # If regex is invalid, treat as literal filename
                path = Path(pattern)
                try:
                    validate_bag_file(path)
                    bag_files.append(path)
                except BagFileError:
                    pass
    
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
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: from config)"),
    verbose: Optional[bool] = typer.Option(None, "--verbose", "-v", help="Show detailed loading information (default: from config)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reload even if already cached"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be loaded without actually loading"),
    build_index: Optional[bool] = typer.Option(None, "--build-index", help="Build message index as pandas DataFrame (default: from config)")
):
    """
    Load ROS bag files into cache for faster operations.
    
    This command processes bag files and stores their analysis in cache,
    making subsequent inspect and extract operations much faster.
    
    Examples:
        rose load "*.bag"                       # Load all bag files in current directory
        rose load bag1.bag bag2.bag             # Load specific bag files
        rose load "test_.*\\.bag"                # Load bags matching regex pattern
        rose load "*.bag" --workers 4           # Use 4 parallel workers
        rose load "*.bag" --force               # Force reload even if cached
        rose load "*.bag" --dry-run             # Preview what would be loaded
        rose load "*.bag" --build-index         # Build message index for data analysis
    """
    start_total_time = time.time()
    out = get_output()
    steps = StepManager()
    
    try:
        # Get configuration with defaults
        config = get_config()
        
        # Check for input
        if not input:
            out.error(
                "No bag files specified",
                details="Provide bag file patterns: rose load '*.bag'"
            )
            raise typer.Exit(1)
        
        # Apply config defaults if not provided
        if verbose is None:
            verbose = config.verbose_default
        if build_index is None:
            build_index = config.build_index_default
        if workers is None:
            workers = config.parallel_workers
        
        # Stage 1: Discovery
        steps.section("Finding bag files")
        steps.add_item("scan", "Scanning directories", "processing")
        
        # Find bag files using patterns
        valid_bags = find_bag_files(input)
        
        if not valid_bags:
            steps.error_item("scan", "No valid bag files found")
            raise typer.Exit(1)
        
        steps.complete_item("scan", f"Found {len(valid_bags)} bag file(s)")
        
        # Display found bags directly
        for bag in valid_bags:
            size_mb = bag.stat().st_size / 1024 / 1024 if bag.exists() else 0
            out.print(f"  {bag.name} ({size_mb:.1f} MB)")
        
        # Handle dry run
        if dry_run:
            steps.section("Load plan (dry-run)")
            out.print(f"  Build index: {build_index}")
            out.print(f"  Workers: {workers}")
            out.print(f"  Force reload: {force}")
            out.newline()
            out.success(f"Would load {len(valid_bags)} bag(s)")
            return
        
        # Adjust workers
        if workers is None or workers <= 0:
            workers = max(1, (os.cpu_count() or 2) - 2)
        
        # Limit workers to number of bags
        workers = min(workers, len(valid_bags))
        
        # Show loading plan with mode info
        is_parallel = workers > 1
        mode_str = f"parallel, {workers} workers" if is_parallel else "serial"
        steps.section(f"Loading bags ({mode_str}, build_index: {build_index})")
        
        # Initialize parser
        parser = BagParser()
        
        # If force reload, clear cache for these bags
        if force:
            cache_manager = create_bag_cache_manager()
            for bag_path in valid_bags:
                cache_manager.clear(bag_path)
        
        # Load bags with live status
        results = []
        total_bags = len(valid_bags)
        bag_list = list(valid_bags)  # Convert to list for indexing
        
        # Process bags with live status
        with out.live_status(f"Processing", total=total_bags) as status:
            # Add all bags as pending first
            for bag_path in bag_list:
                status.add_item(bag_path.name, bag_path.name, "pending")
            
            # Progress callback factory
            def create_progress_callback(bag_name):
                def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                    if phase and verbose:
                        logger.debug(f"{bag_name}: {phase}")
                return progress_callback
            
            # Use ThreadPoolExecutor for parallel loading
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_bag = {}
                
                # Submit all tasks
                for i, bag_path in enumerate(bag_list):
                    # Only mark first `workers` items as processing initially
                    if i < workers:
                        status.update_item(bag_path.name, "processing")
                    
                    cb = create_progress_callback(bag_path.name)
                    future = executor.submit(
                        await_sync, 
                        load_single_bag(bag_path, parser, verbose, build_index, cb)
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
                        elapsed = result.get('elapsed', 0)
                        
                        if result_status == 'loaded':
                            status.update_item(
                                bag_path.name, "done",
                                f"· loaded ({elapsed:.2f}s)"
                            )
                        elif result_status == 'already_cached':
                            status.update_item(
                                bag_path.name, "skip",
                                f"· already cached"
                            )
                        else:
                            status.update_item(
                                bag_path.name, "error",
                                f"· {result.get('message', 'error')}"
                            )
                        
                    except Exception as e:
                        logger.error(f"Unexpected error loading {bag_path}: {e}")
                        results.append({
                            'path': str(bag_path),
                            'status': 'error',
                            'message': f"Unexpected error: {e}",
                            'elapsed': 0.0
                        })
                        status.update_item(
                            bag_path.name, "error",
                            f"· error: {e}"
                        )
                    
                    completed_count += 1
                    
                    # Mark next pending item as processing (if any)
                    next_processing_idx = workers + completed_count - 1
                    if next_processing_idx < total_bags:
                        next_bag = bag_list[next_processing_idx]
                        status.update_item(next_bag.name, "processing")
        
        # Calculate summary
        loaded_count = sum(1 for r in results if r['status'] == 'loaded')
        cached_count = sum(1 for r in results if r['status'] == 'already_cached')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_ready = loaded_count + cached_count
        total_time = time.time() - start_total_time
        
        # Show summary as step
        if error_count == 0:
            steps.section("Load complete")
        else:
            steps.section("Load complete (with errors)")
        
        out.print(f"  Loaded        : {loaded_count}")
        out.print(f"  Already cached: {cached_count}")
        out.print(f"  Failed        : {error_count}")
        out.print(f"  Total ready   : {total_ready}")
        out.print(f"  Time          : {total_time:.2f}s")
        
        # Exit with error if any bags failed
        if error_count > 0:
            raise typer.Exit(1)
    
    except typer.Exit:
        raise
    except RoseError as e:
        out.error(str(e))
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)
    
    except Exception as e:
        out.error(str(e))
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)


# Register load as the default command
app.command()(load)

if __name__ == "__main__":
    app()
