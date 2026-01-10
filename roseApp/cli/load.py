#!/usr/bin/env python3
"""
Load command for ROS bag files - Load bags into cache for faster operations.
"""

import os
import time
from typing import List, Optional
import typer

from ..core.pipeline import load_orchestrator
from ..core.events import LogEvent, ProgressEvent, ResultEvent
from ..core.logging import get_logger
from ..core.errors import RoseError, handle_cli_error
from ..core.config import get_config
from ..core.output import get_output
from ..core.output import get_output, StepManager

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(help="Load ROS bag files into cache for faster operations")


@app.command()
def load(
    input: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: from config) (NOTE: Currently runs sequentially in new architecture)"),
    verbose: Optional[bool] = typer.Option(None, "--verbose", "-v", help="Show detailed loading information (default: from config)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reload even if already cached"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be loaded without actually loading"),
    build_index: Optional[bool] = typer.Option(None, "--build-index", help="Build message index as pandas DataFrame (default: from config)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive file selection with path completion")
):
    """
    Load ROS bag files into cache for faster operations.
    
    This command processes bag files and stores their analysis in cache,
    making subsequent inspect and extract operations much faster.
    """
    start_total_time = time.time()
    out = get_output()
    steps = StepManager()
    
    try:
        # Get configuration with defaults
        config = get_config()
        
        # Auto-enable interactive if no input provided
        if not input and not interactive:
            interactive = True

        # Interactive selection
        if interactive:
            from .interactive import select_bags_interactive
            selected_files, idx_choice = select_bags_interactive(input, build_index, ignore_cache=True)
            input = selected_files
            if idx_choice:
                build_index = True
        
        # Check for input
        if not input:
            out.error(
                "No bag files specified",
                details="Provide bag file patterns: rose load '*.bag' or use --interactive"
            )
            raise typer.Exit(1)
        
        # Apply config defaults if not provided
        if verbose is None:
            verbose = config.verbose_default
        if build_index is None:
            build_index = config.build_index_default
        
        # Handle dry run
        if dry_run:
            steps.section("Load plan (dry-run)")
            out.print(f"  Build index: {build_index}")
            out.print(f"  Force reload: {force}")
            out.newline()
            out.success(f"Would attempt to load bags matching: {input}")
            return

        # Initialize Orchestrator
        # Note: We are ignoring 'workers' for now as the current SDK implementation is sequential.
        pipeline = load_orchestrator(input, build_index=build_index, force=force)
        
        results = []
        loaded_count = 0
        cached_count = 0
        error_count = 0
        
        # We will use a simple status display since we are consuming events
        # We can try to map events to the existing StepManager sections
        
        current_bag = None
        
        # Start the pipeline
        with out.spinner("Initializing...") as sp:
            for event in pipeline:
                if isinstance(event, LogEvent):
                    if event.level == "INFO":
                        sp.update(event.message)
                        # Heuristic to detect section changes or major steps
                        if "Scanning directories" in event.message:
                            steps.section("Finding bag files")
                            steps.add_item("scan", event.message)
                        elif "Found" in event.message and "bag file(s)" in event.message:
                            steps.complete_item("scan", event.message)
                        elif "Processing" in event.message and "/" not in event.message: 
                            # "Processing bag_name..."
                            pass
                        else:
                            if verbose:
                                logger.info(event.message)
                                
                    elif event.level == "WARN":
                        logger.warning(event.message)
                    elif event.level == "ERROR":
                        logger.error(event.message)
                        
                elif isinstance(event, ProgressEvent):
                    if event.description:
                        sp.update(event.description)
                    # Update progress
                    # If we have a current bag, update its status
                    if event.description and "Processing" in event.description and "/" in event.description:
                         # Overall progress
                         pass
                    elif "Loading" in event.description:
                        pass
                
                elif isinstance(event, ResultEvent):
                    if isinstance(event.data, list):
                        # This might be the list of found bags from find_bags step
                        if event.data and isinstance(event.data[0], (str, os.PathLike)): # It returns Path objects
                             # Found bags
                             steps.section(f"Loading bags (sequential, build_index: {build_index})")
                             
                    elif isinstance(event.data, dict):
                        # Single bag result
                        res = event.data
                        bag_path = res.get('path', 'unknown')
                        status = res.get('status')
                        msg = res.get('message')
                        elapsed = res.get('elapsed', 0)
                        
                        if status == 'loaded' or status == 'success':
                            loaded = res.get('loaded', False)
                            cached = res.get('cached', False)
                            
                            if loaded:
                                loaded_count += 1
                                level = res.get('level', 'unknown')
                                steps.complete_item(bag_path, f"Loaded {out.format_path(bag_path)}", status="done", details=f"({level}, {elapsed:.2f}s)")
                            elif cached:
                                cached_count += 1
                                steps.complete_item(bag_path, f"Skipped {out.format_path(bag_path)}", status="skip", details="(already cached)")
                            else:
                                # Fallback
                                loaded_count += 1
                                steps.complete_item(bag_path, f"Processed {out.format_path(bag_path)}", status="done")
                        else:
                            error_count += 1
                            steps.error_item(bag_path, f"Failed {out.format_path(bag_path)}", error=msg)
                        
                        results.append(res)
        
        total_time = time.time() - start_total_time
        total_ready = loaded_count + cached_count
        
        # Show summary
        if error_count == 0:
            steps.section("Load complete")
        else:
            steps.section("Load complete (with errors)")
        
        out.print(f"  Loaded        : {loaded_count}")
        out.print(f"  Already cached: {cached_count}")
        out.print(f"  Failed        : {error_count}")
        out.print(f"  Total ready   : {total_ready}")
        out.print(f"  Time          : {total_time:.2f}s")
        
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
