#!/usr/bin/env python3
"""
Load command for ROS bag files - Load bags into cache for faster operations.
Headless NDJSON mode - pure event emission.
"""

import asyncio
import concurrent.futures
import glob
import re
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.parser import BagParser
from ..core.cache import get_cache, create_bag_cache_manager
from ..core.logging import get_logger
from ..core.errors import (
    RoseError,
    BagFileError,
    ErrorCode,
    handle_cli_error,
    validate_bag_file,
    ErrorContext
)
from ..core.config import get_config
from ..core.event_emitter import get_emitter

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
                'message': 'Already in cache',
                'elapsed': 0.0
            }
        
        # Load bag using parser's async load function
        start_time = time.time()
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
        rose load "test_.*\.bag"                # Load bags matching regex pattern
        rose load "*.bag" --workers 4           # Use 4 parallel workers
        rose load "*.bag" --force               # Force reload even if cached
        rose load "*.bag" --dry-run             # Preview what would be loaded
        rose load "*.bag" --build-index         # Build message index for data analysis
    """
    start_total_time = time.time()
    
    try:
        # Get event emitter
        emitter = get_emitter()
        emitter.set_context("load")
        
        # Get configuration with defaults
        config = get_config()
        
        # Check for input
        if not input:
            emitter.emit_error(
                "INVALID_ARGUMENT",
                "No bag files specified",
                details={
                    "suggestions": [
                        "Provide bag file patterns as arguments: rose load '*.bag'",
                        "Use specific file paths: rose load input.bag"
                    ]
                }
            )
            raise typer.Exit(1)
        
        # Apply config defaults if not provided
        if verbose is None:
            verbose = config.verbose_default
        if build_index is None:
            build_index = config.build_index_default
        if workers is None:
            workers = config.parallel_workers
        
        # Find bag files using patterns
        valid_bags = find_bag_files(input)
        
        if not valid_bags:
            emitter.emit_error(
                "BAG_NOT_FOUND",
                "No valid bag files found",
                details={
                    "patterns": input,
                    "suggestions": [
                        "Check the file path",
                        "Ensure files have .bag extension",
                        "Try using absolute paths"
                    ]
                }
            )
            raise typer.Exit(1)
        
        # Emit discovered bags
        emitter.emit_data(
            data=[
                {
                    "path": str(bag),
                    "size_mb": bag.stat().st_size / 1024 / 1024 if bag.exists() else 0,
                    "exists": bag.exists()
                }
                for bag in valid_bags
            ],
            label="found_bags",
            count=len(valid_bags)
        )
        
        # Handle dry run
        if dry_run:
            emitter.emit_data(
                data={
                    "build_index": build_index,
                    "workers": workers,
                    "force": force,
                    "mode": "dry_run"
                },
                label="load_plan"
            )
            emitter.emit_done({
                "dry_run": True,
                "would_load": len(valid_bags)
            })
            return
        
        # Adjust workers
        import os
        if workers is None or workers <= 0:
            workers = max(1, (os.cpu_count() or 2) - 2)
        
        # Limit workers to number of bags
        workers = min(workers, len(valid_bags))
        
        # Emit loading plan
        emitter.emit_data(
            data={
                "total_bags": len(valid_bags),
                "workers": workers,
                "build_index": build_index,
                "force": force,
                "analysis_type": "with index building" if build_index else "quick"
            },
            label="load_plan"
        )
        
        # Initialize parser
        parser = BagParser()
        
        # If force reload, clear cache for these bags
        if force:
            cache_manager = create_bag_cache_manager()
            for bag_path in valid_bags:
                cache_manager.clear(bag_path)
        
        # Load bags
        results = []
        total_bags = len(valid_bags)
        
        # Use ThreadPoolExecutor for parallel loading
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_bag = {}
            for i, bag_path in enumerate(valid_bags):
                # Emit progress for submission
                percent = (i / total_bags) * 100
                emitter.emit_progress(
                    percent,
                    f"Submitting {bag_path.name}",
                    step=i+1,
                    total_steps=total_bags
                )
                
                # Progress callback (silent in headless mode)
                def create_progress_callback(bag_name):
                    def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                        if phase and verbose:
                            logger.debug(f"{bag_name}: {phase}")
                    return progress_callback
                
                progress_callback = create_progress_callback(bag_path.name)
                future = executor.submit(
                    await_sync, 
                    load_single_bag(bag_path, parser, verbose, build_index, progress_callback)
                )
                future_to_bag[future] = bag_path
            
            # Collect results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(future_to_bag):
                bag_path = future_to_bag[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Emit progress
                    percent = (completed / total_bags) * 100
                    emitter.emit_progress(
                        percent,
                        f"Loaded {bag_path.name}",
                        step=completed,
                        total_steps=total_bags
                    )
                    
                except Exception as e:
                    logger.error(f"Unexpected error loading {bag_path}: {e}")
                    results.append({
                        'path': str(bag_path),
                        'status': 'error',
                        'message': f"Unexpected error: {e}",
                        'elapsed': 0.0
                    })
                    completed += 1
        
        # Calculate summary
        loaded_count = sum(1 for r in results if r['status'] == 'loaded')
        cached_count = sum(1 for r in results if r['status'] == 'already_cached')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_ready = loaded_count + cached_count
        total_time = time.time() - start_total_time
        
        # Emit detailed results
        emitter.emit_data(
            data=[
                {
                    "path": r['path'],
                    "status": r['status'],
                    "message": r.get('message', ''),
                    "elapsed": r.get('elapsed', 0.0),
                    "topics_count": r.get('topics_count', 0)
                }
                for r in results
            ],
            label="results",
            count=len(results)
        )
        
        # Emit done event
        emitter.emit_done({
            "loaded_files": loaded_count,
            "cached_files": cached_count,
            "failed_files": error_count,
            "total_ready": total_ready,
            "elapsed_time": total_time,
            "build_index": build_index,
            "workers": workers
        })
        
        # Exit with error if any bags failed
        if error_count > 0:
            raise typer.Exit(1)
    
    except typer.Exit:
        raise
    except RoseError as e:
        # Emit error event for headless mode
        emitter = get_emitter()
        
        # Get error code name
        error_code_name = e.error_code.name if hasattr(e, 'error_code') else 'ROSE_ERROR'
        
        emitter.emit_error(
            code=error_code_name,
            message=str(e),
            details={'verbose': verbose or False}
        )
        
        # Use unified error handler for Rose errors
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)
    
    except Exception as e:
        # Emit error event for unexpected errors
        emitter = get_emitter()
        emitter.emit_error(
            code=type(e).__name__.upper(),
            message=str(e),
            details={'verbose': verbose or False}
        )
        
        # Use unified error handler
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)


# Register load as the default command
app.command()(load)

if __name__ == "__main__":
    app()
