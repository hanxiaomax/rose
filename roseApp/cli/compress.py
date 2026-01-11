#!/usr/bin/env python3
"""
Compress command for ROS bag file compression.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.pipeline import compress_orchestrator
from ..core.events import LogEvent, ProgressEvent, ResultEvent
from ..core.logging import get_logger
from ..core.output import get_output, create_step_manager

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="compress", help="Compress ROS bag files with different compression algorithms")


@app.command()
def compress(
    input_bags: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp, {compression} for compression type)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count / 2, max 4) (NOTE: Currently runs sequentially in new architecture)"),
    compression: str = typer.Option("lz4", "--compression", "-c", help="Compression type: bz2, lz4"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed compression information"),
    load: bool = typer.Option(False, "--load", help="Load bags if not cached (without building index)"),
    load_index: bool = typer.Option(False, "--load-index", help="Load bags with index building if not cached"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive file selection"),
):
    """
    Compress ROS bag files with different compression algorithms (supports multiple files and patterns).
    
    Bags must be loaded into cache first using 'rose load' or use --load option.
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
        
    try:
        # Auto-enable interactive if no input provided
        if not input_bags and not interactive:
            interactive = True

        # Interactive selection
        if interactive:
            from .interactive import select_bags_interactive
            from ..tui.dialogs import ask_question
            from ..tui.widgets.question import Answer
            from ..core.config import get_config
            
            if not input_bags:
                 # If no bag provided, select bag first
                 selected_files, idx_choice = select_bags_interactive(input_bags, load_index)
                 input_bags = selected_files
                 if idx_choice:
                     load_index = True
            
            # Ask for compression algorithm
            config = get_config()
            default_algo = getattr(config, 'compression_default', 'lz4') or 'lz4'
            
            # Build options with default first
            valid_algorithms = ["lz4", "bz2", "none"]
            algo_descriptions = {
                "lz4": "LZ4 (Fast, good compression)",
                "bz2": "BZ2 (Slower, better compression)",
                "none": "No compression (uncompressed)"
            }
            
            options = []
            # Add default first
            if default_algo in valid_algorithms:
                options.append(Answer(
                    f"{algo_descriptions.get(default_algo, default_algo)} [default]", 
                    default_algo
                ))
            
            # Add other options
            for algo in valid_algorithms:
                if algo != default_algo:
                    options.append(Answer(algo_descriptions.get(algo, algo), algo))
            
            # Add cancel option
            options.append(Answer("Cancel", "cancel"))
            
            out.newline()
            algo_answer = ask_question(
                question="Select compression algorithm:",
                options=options
            )
            
            if not algo_answer or algo_answer.id == "cancel":
                out.info("Cancelled")
                raise typer.Exit(0)
            
            compression = algo_answer.id

        if not input_bags:
            out.error("No bag files specified. Use arguments or --interactive.")
            raise typer.Exit(1)

        # Validate compression option
        valid_compression = ["bz2", "lz4", "none"]
        if compression not in valid_compression:
            out.error(
                f"Invalid compression: {compression}",
                details=f"Valid options: {', '.join(valid_compression)}"
            )
            raise typer.Exit(1)
            
        # Run Orchestrator
        pipeline = compress_orchestrator(
            input_bags, 
            output, 
            compression, 
            overwrite=yes
        )
        
        results = []
        success_count = 0
        error_count = 0
        
        # To track bags for live status
        found_bags = []
        
        from contextlib import ExitStack
        with ExitStack() as stack:
            live_status = None

            for event in pipeline:
                if isinstance(event, LogEvent):
                    if event.level == "INFO":
                         if "Scanning directories" in event.message:
                             steps.section("Finding bag files")
                             steps.add_item("scan", event.message, "processing")
                         elif "Found" in event.message and "bag file(s)" in event.message:
                             steps.complete_item("scan", event.message)
                         elif "Compressing" in event.message and "..." in event.message:
                             # This is yielded by step_compress_bag
                             # If live status is not active, activate it
                             if not live_status:
                                 # We are in compression phase
                                 steps.section(f"Compressing bags ({compression.upper()})")
                                 live_status = stack.enter_context(out.live_status("Processing", total=len(found_bags)))
                                 # Populate pending
                                 for bg in found_bags:
                                     live_status.add_item(bg.name, bg.name, "pending")
                             
                             # Update current item
                             # The message is "Compressing {bag_name}..."
                             parts = event.message.replace("Compressing ", "").replace("...", "")
                             bag_name = parts.strip()
                             live_status.update_item(bag_name, "processing")
                             
                         elif "Compressed to" in event.message:
                             pass
                         else:
                             if verbose:
                                logger.info(event.message)
                    elif event.level == "WARN":
                        logger.warning(event.message)
                        out.warning(event.message)
                    elif event.level == "ERROR":
                        logger.error(event.message)
                        out.error(event.message)
                        if "No valid bag files" in event.message:
                            raise typer.Exit(1)

                elif isinstance(event, ProgressEvent):
                    pass
                
                elif isinstance(event, ResultEvent):
                    if isinstance(event.data, list):
                        # This happens for step_find_bags result
                        if event.data and isinstance(event.data[0], Path):
                            found_bags = event.data
                            # Display found bags
                            for bag in found_bags:
                                size_mb = bag.stat().st_size / 1024 / 1024
                                out.print(f"  {bag.name} ({size_mb:.1f} MB)")
                                
                    if isinstance(event.data, dict):
                        res = event.data
                        bag_path_str = res.get('input_file', 'unknown')
                        bag_name = os.path.basename(bag_path_str)
                        status = res.get('status')
                        
                        if live_status:
                            if status == 'compressed':
                                success_count += 1
                                ratio = res.get('compression_ratio', 0)
                                output_path = res.get('output_file')
                                output_name = os.path.basename(output_path) if output_path else "unknown"
                                elapsed = res.get('elapsed_time', 0)
                                live_status.update_item(bag_name, "done", f"→ {output_name} (ratio: {ratio:.1f}%, {elapsed:.1f}s)")
                            else:
                                error_count += 1
                                msg = res.get('message', 'error')
                                live_status.update_item(bag_name, "error", f"· {msg}")
                        else:
                             # Fallback if somehow not active
                             pass
                        
                        results.append(res)
        
        # Summary
        total_time = time.time() - start_total_time
        successful_results = [r for r in results if r['status'] == 'compressed']
        avg_compression_ratio = (
            sum(r['compression_ratio'] for r in successful_results) / len(successful_results)
            if successful_results else 0
        )
        
        if error_count == 0:
            steps.section("Compression complete")
        else:
            steps.section("Compression complete (with errors)")
        
        out.print(f"  Compressed: {success_count}")
        out.print(f"  Failed    : {error_count}")
        out.print(f"  Algorithm : {compression.upper()}")
        out.print(f"  Avg ratio : {avg_compression_ratio:.1f}%")
        out.print(f"  Time      : {total_time:.2f}s")
        
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
