#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Optional
import typer

from ..core.pipeline import extract_orchestrator
from ..core.events import LogEvent, ProgressEvent, ResultEvent
from ..core.logging import get_logger
from ..core.output import get_output, create_step_manager

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer(name="extract", help="Extract specific topics from ROS bag files")


@app.command()
def extract(
    input_bags: Optional[List[str]] = typer.Argument(None, help="Bag file patterns (supports glob and regex)"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output pattern (use {input} for input filename, {timestamp} for timestamp)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of parallel workers (default: CPU count - 2) (NOTE: Currently runs sequentially in new architecture)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information"),
    load: bool = typer.Option(False, "--load", help="Load bags if not cached (without building index)"),
    load_index: bool = typer.Option(False, "--load-index", help="Load bags with index building if not cached"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive topic selection"),
):
    """
    Extract specific topics from ROS bag files (supports multiple files and patterns).
    
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
        # Validate input arguments
        if not input_bags and not interactive:
             interactive = True

        if interactive:
            from .interactive import select_bags_interactive
            # Interactive mode for bags
            if not input_bags:
                # If no bag provided, select bag first
                # Default build_index is False for extract usually, unless user wants it?
                # Extract doesn't strictly need index usually unless using complex queries?
                # Actually extract orchestrator reads messages. 
                # We pass None for default_build_index
                selected_files, idx_choice = select_bags_interactive(input_bags, load_index)
                input_bags = selected_files
                if idx_choice:
                    load_index = True
            
            # If still no bags, error handled below
            
            # Interactive topic selection logic follows...
            from ..core.cache import create_bag_cache_manager
            from glob import glob
            from rosbags.highlevel import AnyReader
            
            # Resolve files from input_bags (which might have come from interactive or args)
            files = []
            if input_bags:
                for pattern in input_bags:
                    if Path(pattern).exists():
                        files.append(Path(pattern))
                    else:
                        files.extend([Path(p) for p in glob(pattern)])
            
            # De-duplicate
            files = list(set(files))
            
            if not files:
                out.error("No bag files found matching input patterns")
                raise typer.Exit(1)
                
            all_topics = set()
            manager = create_bag_cache_manager()
            
            # Resolve all files to absolute paths for consistent cache lookup
            files = [f.resolve() for f in files]
            
            with out.spinner("Scanning bags for topics..."):
                for f in files:
                    try:
                        # Try cache first (using absolute path)
                        info = manager.get_analysis(f)
                        if info and info.topics:
                            for t in info.topics:
                                all_topics.add(t.name)
                        else:
                            # Fallback to direct read
                            with AnyReader([f]) as reader:
                                for c in reader.connections:
                                    all_topics.add(c.topic)
                    except Exception as e:
                        out.warning(f"Could not read topics from {f.name}: {e}")
            
            if not all_topics:
                out.error("No topics found in specified bags.")
                raise typer.Exit(1)
                
            # Interactive Selection
            sorted_topics = sorted(list(all_topics))
            
            from ..tui.dialogs import ask_multi_selection
            from ..tui.widgets.question import Answer
            
            selection_items = [Answer(t, t) for t in sorted_topics]
            
            out.print("Select topics (Type to filter, Space to toggle, Enter to confirm):")
            
            selected_answers = ask_multi_selection(
                question="Select topics to extract:",
                options=selection_items
            )
            
            if not selected_answers:
                out.info("No topics selected.")
                raise typer.Exit(0)
            
            topics = [a.id for a in selected_answers]
        
        # Run Orchestrator
        pipeline = extract_orchestrator(
            input_bags, 
            topics, 
            output, 
            compression, 
            overwrite=yes,
            reverse=reverse,
            load_if_missing=(load or load_index)
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
                         elif "Analyzing topics" in event.message:
                             steps.section("Analyzing topics")
                             steps.add_item("analyze", "Scanning topics from cached data", "processing")
                         elif "Selected" in event.message and "topics for extraction" in event.message:
                             steps.complete_item("analyze", event.message)
                         
                         # Handling extraction start
                         elif "Extracting from" in event.message:
                             # This is yielded by step_extract_bag
                             # If live status is not active, activate it
                             if not live_status:
                                 # We are in extraction phase
                                 steps.section(f"Extracting topics")
                                 live_status = stack.enter_context(out.live_status("Processing", total=len(found_bags)))
                                 # Populate pending
                                 for bg in found_bags:
                                     live_status.add_item(bg.name, bg.name, "pending")
                             
                             # Update current item
                             # The message is "Extracting from {bag_name}..."
                             # Extract bag name
                             parts = event.message.replace("Extracting from ", "").replace("...", "")
                             bag_name = parts.strip()
                             live_status.update_item(bag_name, "processing")
                         
                         elif "Extracted to" in event.message:
                             # Handled by ResultEvent usually, but log event comes before result
                             pass
                         elif "Reading metadata" in event.message:
                             # Implicit loading log
                             steps.add_item("implicit_load", event.message, "processing")

                         else:
                            if verbose:
                                logger.info(event.message)
                    elif event.level == "WARN":
                        logger.warning(event.message)
                        out.warning(event.message)
                    elif event.level == "ERROR":
                        logger.error(event.message)
                        out.error(event.message)
                        if "No matching topics" in event.message or "No valid bag files" in event.message or "No topics found" in event.message:
                             raise typer.Exit(1)

                elif isinstance(event, ProgressEvent):
                    pass
                
                elif isinstance(event, ResultEvent):
                    if isinstance(event.data, list):
                        # This happens for step_find_bags result
                        # We should check if the list contains paths (checking first item type)
                        if event.data and isinstance(event.data[0], Path):
                            found_bags = event.data
                            # Display found bags
                            for bag in found_bags:
                                size_mb = bag.stat().st_size / 1024 / 1024
                                out.print(f"  {bag.name} ({size_mb:.1f} MB)")
                            
                    if isinstance(event.data, dict):
                        res = event.data
                        bag_path_str = res.get('path', 'unknown')
                        bag_name = os.path.basename(bag_path_str)
                        status = res.get('status')
                        
                        if live_status:
                            if status == 'extracted':
                                success_count += 1
                                output_path = res.get('output_path')
                                output_name = os.path.basename(output_path) if output_path else "unknown"
                                elapsed = res.get('elapsed_time', 0)
                                size_mb = res.get('output_size', 0) / 1024 / 1024
                                live_status.update_item(bag_name, "done", f"→ {output_name} ({size_mb:.1f} MB, {elapsed:.1f}s)")
                                
                                if verbose:
                                    # Print detailed info if verbose
                                    topics_list = res.get('topics_list', [])
                                    out.info(f"  Extracted {len(topics_list)} topics to {output_name}:")
                                    for t in topics_list:
                                        out.print(f"    - {t}")
                                    out.print(f"  Size: {size_mb:.2f} MB")
                            elif status == 'loaded':
                                # Implicit load result
                                steps.complete_item("implicit_load", "Metadata loaded")
                            else:
                                error_count += 1
                                msg = res.get('message', 'error')
                                live_status.update_item(bag_name, "error", f"· {msg}")
                        else:
                            # Fallback if live status not active (should not happen for extraction)
                            pass
                        
                        results.append(res)
        
        total_time = time.time() - start_total_time
        
        if error_count == 0:
            steps.section("Extraction complete")
        else:
            steps.section("Extraction complete (with errors)")
        
        out.print(f"  Extracted : {success_count}")
        out.print(f"  Failed    : {error_count}")
        out.print(f"  Time      : {total_time:.2f}s")
        
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
