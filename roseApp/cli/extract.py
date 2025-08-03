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
from ..core.parser import BagParser, ExtractOption
from ..core.ui_control import UIControl, Message
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.cache import create_bag_cache_manager
from .util import filter_topics


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


# filter_topics function is now imported from .util


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

):
    """
    Extract specific topics from a ROS bag file
    
    NOTE: The bag file must be loaded into cache first using 'rose load <bag_file>'
    
    Examples:
        rose load input.bag                                         # Load bag into cache first
        rose extract input.bag --topics gps imu                    # Keep topics matching 'gps' or 'imu'
        rose extract input.bag --topics /gps/fix -o output.bag     # Keep exact topic /gps/fix
        rose extract input.bag --topics tf --reverse               # Remove topics matching 'tf' 
        rose extract input.bag --topics gps --compression lz4      # Use LZ4 compression
        rose extract input.bag --topics gps --dry-run              # Preview without extraction
    """
    _extract_topics_impl(input_bag, topics, output, reverse, compression, dry_run, yes, verbose)


def _extract_topics_impl(
    input_bag: str,
    topics: Optional[List[str]],
    output: Optional[str],
    reverse: bool,
    compression: str,
    dry_run: bool,
    yes: bool,
    verbose: bool
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
        
        # Check if bag is loaded in cache
        cache_manager = create_bag_cache_manager()
        cached_entry = cache_manager.get_analysis(input_path)
        
        if not cached_entry or not cached_entry.is_valid(input_path):
            ui.show_error(f"Bag file '{input_bag}' is not loaded in cache.")
            console.print(f"[yellow]Please load the bag first using:[/yellow] [bold]rose load {input_bag}[/bold]")
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
        should_overwrite = yes  # Start with the --yes flag value
        if output_path.exists() and not yes:
            if not typer.confirm(f"Output file '{output_path}' already exists. Overwrite?"):
                ui.show_operation_cancelled()
                raise typer.Exit(0)
            else:
                should_overwrite = True  # User confirmed overwrite
        
        # Get topic list from cached bag info
        ui.show_operation_status("Using cached bag analysis...")
        
        # Extract topic list from cached bag info
        bag_info = cached_entry.bag_info
        if bag_info and hasattr(bag_info, 'topics') and bag_info.topics:
            all_topics = bag_info.topics if isinstance(bag_info.topics[0], str) else [topic.name for topic in bag_info.topics]
        else:
            ui.show_error("No topics found in cached bag analysis")
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
            ui.show_no_matching_items(topics, all_topics, reverse, "topics")
            raise typer.Exit(1)
        
        # Show operation description using unified UI
        ui.show_operation_description(operation_desc, topics_to_extract, "topics")
        
        # If dry run, show preview and return
        if dry_run:
            ui.show_dry_run_preview(len(topics_to_extract), topics_to_extract, output_path, "extract")
            return
        
        # Perform the actual extraction using parser
        extract_option = ExtractOption(
            topics=topics_to_extract,
            compression=compression,
            overwrite=should_overwrite
        )
        
        # Track extraction timing
        extraction_start_time = time.time()
        
        # Initialize parser for extraction
        parser = BagParser()
        
        # Show extraction progress
        console.print(f"Extracting {len(topics_to_extract)} topic(s) to {output_path}...")
        
        try:
            # Execute extraction using parser
            result_message, extraction_time = parser.extract(
                str(input_path),
                str(output_path),
                extract_option
            )
            
            success = True
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            result_message = str(e)
            extraction_time = time.time() - extraction_start_time
            success = False
        
        # Check if extraction was successful
        if not success:
            ui.show_error(f"Extraction failed: {result_message}")
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
                excluded_topics = [t for t in all_topics if t in filter_topics(all_topics, topics, None)]
                excluded_count = len(excluded_topics)
            else:
                excluded_topics = [t for t in all_topics if t not in topics_to_extract]
                excluded_count = len(excluded_topics)
            
            ui.show_items_selection_summary(len(all_topics), len(topics_to_extract), excluded_count, "topics")
            
            # Show topic lists
            if reverse:
                excluded_topics_matching = [t for t in all_topics if t in filter_topics(all_topics, topics, None)]
                ui.show_items_lists(topics_to_extract, excluded_topics_matching, reverse_mode=True, item_type="topics")
            else:
                excluded_topics_non_matching = [t for t in all_topics if t not in topics_to_extract]
                ui.show_items_lists(topics_to_extract, excluded_topics_non_matching, reverse_mode=False, item_type="topics")
            
            # Show pattern matching summary
            ui.show_pattern_matching_summary(topics, reverse, all_topics, "topics")
        
    except Exception as e:
        ui.show_error(f"Error during extraction: {e}")
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)



# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app() 