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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn

from ..core.parser import BagParser
from ..core.cache import get_cache, create_bag_cache_manager
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.plugins import get_plugin_manager, HookType
from ..core.errors import (
    RoseError,
    BagFileError,
    ErrorCode,
    handle_cli_error,
    validate_bag_file,
    ErrorContext
)
from ..core.config import get_config
from ..ui.common_ui import CommonUI, Message

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
        # Execute before_load hooks
        plugin_manager = get_plugin_manager()
        before_context = plugin_manager.create_plugin_context(
            bag_path, 'load', 
            verbose=verbose, 
            build_index=build_index
        )
        plugin_manager.execute_hooks(HookType.BEFORE_LOAD, before_context)
        
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
        
        # Execute after_load hooks
        after_context = plugin_manager.create_plugin_context(
            bag_path, 'load',
            bag_info=bag_info,
            elapsed_time=elapsed_time,
            verbose=verbose,
            build_index=build_index
        )
        plugin_manager.execute_hooks(HookType.AFTER_LOAD, after_context)
        
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
    
    If bag files are not provided, you will be prompted to select them interactively.
    
    Examples:
        rose load "*.bag"                       # Load all bag files in current directory
        rose load bag1.bag bag2.bag             # Load specific bag files
        rose load "test_.*\.bag"                # Load bags matching regex pattern
        rose load "*.bag" --workers 4           # Use 4 parallel workers
        rose load "*.bag" --force               # Force reload even if cached
        rose load "*.bag" --dry-run             # Preview what would be loaded
        rose load "*.bag" --build-index         # Build message index for data analysis
    """
    try:
        # Get output engine for dual-mode support
        from ..core.output_engine import get_engine
        engine = get_engine()
        console = Console()
        
        # Get configuration with defaults
        config = get_config()
        
        # Auto-prompt for input bags if not provided
        if not input:
            # Check if we're in a TTY (interactive terminal)
            import sys
        # v2.0: No interactive mode
        if not input:
            error = RoseError(
                code=ErrorCode.INVALID_ARGUMENT,
                message="No bag files specified",
                details="At least one bag file pattern must be provided",
                suggestions=[
                    "Provide bag file patterns as arguments: rose load '*.bag'",
                    "Use specific file paths: rose load input.bag",
                ]
            )
            raise error
        
        # Apply config defaults if not provided
        if verbose is None:
            verbose = config.verbose_default
        if build_index is None:
            build_index = config.build_index_default
        if workers is None:
            workers = config.parallel_workers
        
        # Initialize UI
        ui = CommonUI()
        ui.console = console
        
        # Find bag files using patterns
        valid_bags = find_bag_files(input)
        
        if not valid_bags:
            raise BagFileError(
                ErrorCode.BAG_NOT_FOUND,
                ', '.join(input),
                details=f"No valid bag files found matching the provided patterns: {', '.join(input)}"
            )
    
        # Show found files
        Message.info(f"Found {len(valid_bags)} bag file(s):")
        for bag in valid_bags:
            Message.muted(f"  {bag}")
        
        # Handle dry run
        if dry_run:
            Message.warning(f"DRY RUN - Would load {len(valid_bags)} bag file(s)")
            Message.info(f"Build index: {build_index}", console)
            Message.info(f"Workers: {workers}", console)
            return
        
        # Use config workers if not overridden
        import os
        if workers is None or workers <= 0:
            workers = max(1, (os.cpu_count() or 2) - 2)
        
        # Limit workers to number of bags
        workers = min(workers, len(valid_bags))
        
        analysis_type = "with index building" if build_index else "quick"
        Message.info(f"Loading {len(valid_bags)} bag file(s) with {workers} worker(s) ({analysis_type})...")
        
        # Initialize parser
        parser = BagParser()
        
        # If force reload, clear cache for these bags
        if force:
            cache_manager = create_bag_cache_manager()
            Message.warning("Force reload enabled - clearing cache for these bags")
            for bag_path in valid_bags:
                cache_manager.clear(bag_path)
        
        # Load bags with plain text output
        results = []
        
        # Simple progress tracking without progress bars
        total_bags = len(valid_bags)
        completed_count = 0
        
        # Use ThreadPoolExecutor for parallel loading
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks with simple progress callbacks
            future_to_bag = {}
            for i, bag_path in enumerate(valid_bags, 1):
                Message.info(f"[{i}/{total_bags}] Loading {bag_path.name}...")
                
                # Simple progress callback that just prints updates
                def create_progress_callback(bag_name):
                    def progress_callback(phase: str = "", progress_pct: float = 0.0, **kwargs):
                        if phase:
                            Message.muted(f"  {bag_name}: {phase}")
                    return progress_callback
                
                progress_callback = create_progress_callback(bag_path.name)
                future = executor.submit(
                    await_sync, 
                    load_single_bag(bag_path, parser, verbose, build_index, progress_callback)
                )
                future_to_bag[future] = bag_path
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_bag):
                bag_path = future_to_bag[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed_count += 1
                    
                    # Show completion status
                    status_msg = {
                        'loaded': f"✓ Loaded {bag_path.name}",
                        'already_cached': f"✓ {bag_path.name} (cached)",
                        'error': f"✗ Failed {bag_path.name}"
                    }.get(result['status'], f"? {bag_path.name}")
                    Message.muted(status_msg)
                    
                    if verbose:
                        Message.info(f"{result['path']}: {result['message']}")
                        
                except Exception as e:
                    logger.error(f"Unexpected error loading {bag_path}: {e}")
                    results.append({
                        'path': str(bag_path),
                        'status': 'error',
                        'message': f"Unexpected error: {e}"
                    })
                    Message.error(f"Failed to load {bag_path.name}: {e}")
        
        # Calculate summary (headless: emit structured data, not console print)
        loaded_count = sum(1 for r in results if r['status'] == 'loaded')
        cached_count = sum(1 for r in results if r['status'] == 'already_cached')
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_ready = loaded_count + cached_count
        
        # Emit summary as status messages (simple info, not complex formatting)
        if loaded_count > 0:
            Message.info(f"{loaded_count} bag(s) newly loaded into cache")
        if cached_count > 0:
            Message.info(f"{cached_count} bag(s) already in cache")
        if error_count > 0:
            Message.warning(f"{error_count} bag(s) failed to load")
        
        # Emit errors as individual messages
        if error_count > 0:
            for result in results:
                if result['status'] == 'error':
                    Message.error(f"{result['path']}: {result['message']}")
        
        # Success message
        if total_ready > 0:
            Message.success(f"Ready: {total_ready} bag(s) available for inspect and extract commands")
        
        # Emit completion event for headless mode
        engine.emit_done({
            "loaded_files": loaded_count,
            "cached_files": cached_count,
            "failed_files": error_count,
            "total_ready": total_ready
        })
        
        if error_count > 0:
            raise typer.Exit(1)
    
    except RoseError as e:
        # Emit error event for headless mode
        from ..core.output_engine import get_engine
        engine = get_engine()
        
        # Get error code name - error_code is the enum, code is the int
        error_code_name = e.error_code.name if hasattr(e, 'error_code') else 'ROSE_ERROR'
        
        engine.emit_error(
            code=error_code_name,
            message=str(e),
            details={'verbose': verbose or False}
        )
        
        # Use unified error handler for Rose errors
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)
    
    except Exception as e:
        # Emit error event for headless mode
        from ..core.output_engine import get_engine
        engine = get_engine()
        engine.emit_error(
            code=type(e).__name__.upper(),
            message=str(e),
            details={'verbose': verbose or False}
        )
        
        # Use unified error handler for unexpected errors
        exit_code = handle_cli_error(e, verbose=verbose or False)
        raise typer.Exit(exit_code)


# Register load as the default command
app.command()(load)

if __name__ == "__main__":
    app()