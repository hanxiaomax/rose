#!/usr/bin/env python3
"""
Extract command for ROS bag topic extraction
Extract specific topics from ROS bag files using fuzzy matching
"""

import os
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
import typer
from rich.console import Console
from ..core.bag_manager import BagManager, ExtractOptions
from ..core.ui_control import UIControl, OutputFormat, RenderOptions, ExportOptions, UITheme, DisplayConfig
from ..core.util import set_app_mode, AppMode, get_logger


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


@app.command()
def extract(
    input_bag: str = typer.Argument(..., help="Path to input bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output bag file path (default: input_filtered_timestamp.bag)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be extracted without doing it"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed extraction information"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache and reparse the bag file")
):
    """
    Extract specific topics from a ROS bag file
    
    Examples:
        rose extract input.bag --topics gps imu                    # Keep topics matching 'gps' or 'imu'
        rose extract input.bag --topics /gps/fix -o output.bag     # Keep exact topic /gps/fix
        rose extract input.bag --topics tf --reverse               # Remove topics matching 'tf' 
        rose extract input.bag --topics gps --compression lz4      # Use LZ4 compression
        rose extract input.bag --topics gps --dry-run              # Preview without extraction
    """
    _extract_topics_impl(input_bag, topics, output, reverse, compression, dry_run, yes, verbose, no_cache)


def _extract_topics_impl(
    input_bag: str,
    topics: Optional[List[str]],
    output: Optional[str],
    reverse: bool,
    compression: str,
    dry_run: bool,
    yes: bool,
    verbose: bool,
    no_cache: bool
):
    """
    Simplified topic extraction - focus on core functionality
    """
    import time
    
    # Use UIControl for unified output management
    ui = UIControl()
    console = ui.get_console()
    
    try:
        # Validate input arguments
        input_path = Path(input_bag)
        if not input_path.exists():
            ui.show_error(f"Input bag file not found: {input_bag}")
            raise typer.Exit(1)
        
        if not topics:
            ui.show_error("No topics specified. Use --topics to specify topics")
            raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            ui.show_error(f"Invalid compression '{compression}'. Valid options: {', '.join(valid_compression)}")
            raise typer.Exit(1)
        
        # Generate output path if not specified
        if not output:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            input_stem = input_path.stem
            output_path = input_path.parent / f"{input_stem}_filtered_{timestamp}.bag"
        else:
            output_path = Path(output)
        
        # Check if output file exists and handle overwrite
        if output_path.exists() and not yes:
            if not typer.confirm(f"Output file '{output_path}' already exists. Overwrite?"):
                ui.show_operation_cancelled()
                raise typer.Exit(0)
        
        # Create BagManager
        manager = BagManager()
        
        # Get topic list using lightweight method
        ui.show_operation_status("Analyzing bag file...")
        
        # Use parser.get_bag_summary for lightweight topic discovery
        bag_info, _ = manager.parser.get_bag_summary(str(input_path))
        
        # Get topic list
        if bag_info and bag_info.topics:
            all_topics = bag_info.topics
        else:
            ui.show_error("Unable to read topics from bag file")
            raise typer.Exit(1)
        
        # Apply topic filtering using BagManager's _filter_topics method
        if reverse:
            # Reverse selection: exclude topics that match the patterns
            topics_to_exclude = manager._filter_topics(all_topics, topics, None)
            topics_to_extract = [t for t in all_topics if t not in topics_to_exclude]
            operation_desc = f"Excluding topics matching: {', '.join(topics)}"
        else:
            # Normal selection: include topics that match the patterns
            topics_to_extract = manager._filter_topics(all_topics, topics, None)
            operation_desc = f"Including topics matching: {', '.join(topics)}"
        
        if not topics_to_extract:
            ui.show_no_matching_items(topics, all_topics, reverse, "topics")
            raise typer.Exit(1)
        
        # Show operation description using unified UI
        ui.show_operation_description(operation_desc, topics_to_extract, "topics")
        
        # If dry run, show preview and return
        if dry_run:
            ui.show_dry_run_preview(len(topics_to_extract), topics_to_extract, output_path, "extract")
            return
        
        # Perform the actual extraction
        options = ExtractOptions(
            topics=topics_to_extract,
            output_path=output_path,
            compression=compression,
            overwrite=yes,
            dry_run=dry_run,
            reverse=reverse,
            no_cache=no_cache
        )
        
        # Track extraction timing
        extraction_start_time = time.time()
        
        # Show realistic extraction progress with actual phases
        with UIControl.todo_extraction_progress(
            input_path.name,
            "Extracting from",
            console
        ) as update_progress:
            
            # Phase tracking
            phase_start_time = extraction_start_time
            
            # Phase 1: Initialize extraction
            update_progress(
                topic="Initializing extraction...",
                progress=0.0,
                bag_format=compression.upper() if compression != "none" else "Uncompressed"
            )
            
            # Create enhanced progress callback that tracks real phases
            def realistic_progress_callback(topic_index: int, topic: str, messages_processed: int = 0,
                                       total_messages_in_topic: int = 0, phase: str = "processing"):
                nonlocal phase_start_time
                current_time = time.time()
                phase_duration = current_time - phase_start_time
                
                # Calculate overall progress based on actual extraction phases
                if phase == "analyzing":
                    # Phase 1: Reading bag metadata (5%)
                    progress = 5.0
                    current_topic = f"Reading bag metadata... ({phase_duration:.1f}s)"
                elif phase == "filtering":
                    # Phase 2: Filtering connections (10%)
                    progress = 10.0
                    phase_start_time = current_time  # Reset for next phase
                    current_topic = f"Filtering connections for {len(topics_to_extract)} topics... ({phase_duration:.1f}s)"
                elif phase == "collecting":
                    # Phase 3: Collecting messages (10-60%)
                    base_progress = 10.0
                    collect_progress = 50.0 * (messages_processed / max(total_messages_in_topic, 1))
                    progress = base_progress + collect_progress
                    current_topic = f"Collecting messages ({messages_processed:,} collected)... ({phase_duration:.1f}s)"
                elif phase == "sorting":
                    # Phase 4: Sorting chronologically (60-70%)
                    progress = 70.0
                    phase_start_time = current_time  # Reset for next phase
                    current_topic = f"Sorting {messages_processed:,} messages chronologically... ({phase_duration:.1f}s)"
                elif phase == "writing":
                    # Phase 5: Writing to output (70-95%)
                    base_progress = 70.0
                    write_progress = 25.0 * (messages_processed / max(total_messages_in_topic, 1))
                    progress = base_progress + write_progress
                    current_topic = f"Writing messages to output ({messages_processed:,} written)... ({phase_duration:.1f}s)"
                elif phase == "finalizing":
                    # Phase 6: Finalizing (95-100%)
                    progress = 95.0
                    phase_start_time = current_time  # Reset for final phase
                    current_topic = f"Finalizing output file... ({phase_duration:.1f}s)"
                elif phase == "completed":
                    # Phase 7: Completed (100%)
                    progress = 100.0
                    total_duration = current_time - extraction_start_time
                    current_topic = f"Extraction completed ({messages_processed:,} messages in {total_duration:.2f}s)"
                else:
                    # Default processing
                    progress = 50.0 + (topic_index / len(topics_to_extract)) * 40.0
                    current_topic = f"Processing {topic}... ({phase_duration:.1f}s)"
                
                # Calculate topics processed based on phase and progress
                if phase == "analyzing":
                    topics_processed_count = 0
                elif phase == "filtering":
                    topics_processed_count = 0
                elif phase == "collecting":
                    # During collection, we're processing topics
                    topics_processed_count = min(1, len(topics_to_extract))
                elif phase == "sorting":
                    # During sorting, we've collected all topics
                    topics_processed_count = len(topics_to_extract)
                elif phase == "writing":
                    # During writing, we're processing all topics
                    topics_processed_count = len(topics_to_extract)
                elif phase == "finalizing" or phase == "completed":
                    # All topics processed
                    topics_processed_count = len(topics_to_extract)
                else:
                    # Default based on progress
                    topics_processed_count = min(int(progress / 100 * len(topics_to_extract)), len(topics_to_extract))
                
                # Update the display with realistic information
                update_progress(
                    topic=current_topic,
                    progress=progress,
                    topics_total=len(topics_to_extract),
                    topics_processed=topics_processed_count,
                    bag_format=compression.upper() if compression != "none" else "Uncompressed"
                )
            
            # Execute extraction with realistic progress tracking
            result = await_sync(manager.extract_bag(input_path, options, progress_callback=realistic_progress_callback))
        
        # Calculate extraction timing
        extraction_end_time = time.time()
        extraction_time = extraction_end_time - extraction_start_time
        
        # Check if extraction was successful
        if not result.get('success', False):
            ui.show_error(f"Extraction failed: {result.get('error', 'Unknown error')}")
            raise typer.Exit(1)
        
        # Show success message using unified UI
        ui.show_operation_success("extracted", len(topics_to_extract), output_path, extraction_time)
        
        # Show verbose details if requested
        if verbose:
            # Show extraction details
            output_size = output_path.stat().st_size if output_path.exists() else None
            additional_info = {"Compression": compression}
            if output_size is not None:
                additional_info["Output size"] = f"{output_size / 1024 / 1024:.1f} MB"
            ui.show_operation_details("extraction", input_path, output_path, extraction_time, additional_info)
            
            # Show topic selection summary
            if reverse:
                excluded_topics = [t for t in all_topics if t in manager._filter_topics(all_topics, topics, None)]
                excluded_count = len(excluded_topics)
            else:
                excluded_topics = [t for t in all_topics if t not in topics_to_extract]
                excluded_count = len(excluded_topics)
            
            ui.show_items_selection_summary(len(all_topics), len(topics_to_extract), excluded_count, "topics")
            
            # Show topic lists
            if reverse:
                excluded_topics_matching = [t for t in all_topics if t in manager._filter_topics(all_topics, topics, None)]
                ui.show_items_lists(topics_to_extract, excluded_topics_matching, reverse_mode=True, item_type="topics")
            else:
                excluded_topics_non_matching = [t for t in all_topics if t not in topics_to_extract]
                ui.show_items_lists(topics_to_extract, excluded_topics_non_matching, reverse_mode=False, item_type="topics")
            
            # Show pattern matching summary
            ui.show_pattern_matching_summary(topics, reverse, all_topics, "topics")
        
        manager.cleanup()
        
    except Exception as e:
        ui.show_error(f"Error during extraction: {e}")
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)



# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app() 