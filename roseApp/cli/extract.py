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
    console = Console()
    
    try:
        # Validate input arguments
        input_path = Path(input_bag)
        if not input_path.exists():
            console.print(f"[red]Error: Input bag file not found: {input_bag}[/red]")
            raise typer.Exit(1)
        
        if not topics:
            console.print("[red]Error: No topics specified. Use --topics to specify topics[/red]")
            raise typer.Exit(1)
        
        # Validate compression option
        valid_compression = ["none", "bz2", "lz4"]
        if compression not in valid_compression:
            console.print(f"[red]Error: Invalid compression '{compression}'. Valid options: {', '.join(valid_compression)}[/red]")
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
                console.print("Operation cancelled.")
                raise typer.Exit(0)
        
        # Create BagManager
        manager = BagManager()
        
        # Get topic list using lightweight method
        console.print(f"[dim]Analyzing bag file...[/dim]")
        
        # Use parser.get_bag_summary for lightweight topic discovery
        bag_info, _ = manager.parser.get_bag_summary(str(input_path))
        
        # Get topic list
        if bag_info and bag_info.topics:
            all_topics = bag_info.topics
        else:
            console.print("[red]Error: Unable to read topics from bag file[/red]")
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
            if reverse:
                console.print(f"[yellow]All topics would be excluded. No topics to extract.[/yellow]")
            else:
                console.print(f"[yellow]No matching topics found.[/yellow]")
                console.print(f"Available topics: {', '.join(all_topics[:5])}{'...' if len(all_topics) > 5 else ''}")
                console.print(f"Requested patterns: {', '.join(topics)}")
            raise typer.Exit(1)
        
        # Show operation description
        console.print(f"\n[bold]{operation_desc}[/bold]")
        console.print(f"Topics to extract: {', '.join(topics_to_extract)}")
        
        # If dry run, show preview and return
        if dry_run:
            console.print(f"\n[yellow]Dry run - would extract {len(topics_to_extract)} topics:[/yellow]")
            for topic in topics_to_extract:
                console.print(f"  • {topic}")
            console.print(f"\n[dim]Output would be saved to: {output_path}[/dim]")
            console.print(f"[yellow]Dry run completed - no files were created[/yellow]")
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
            console.print(f"\n[red]Extraction failed: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)
        
        # Show simple success message
        console.print(f"\n[green]✓[/green] Successfully extracted {len(topics_to_extract)} topics")
        console.print(f"[dim]Output saved to: {output_path}[/dim]")
        console.print(f"[dim]Extraction completed in {extraction_time:.2f}s[/dim]")
        
        # Show verbose details if requested
        if verbose:
            console.print(f"\n[bold]Extraction Details:[/bold]")
            console.print(f"  Input file: {input_path}")
            console.print(f"  Output file: {output_path}")
            console.print(f"  Compression: {compression}")
            console.print(f"  Extraction time: {extraction_time:.2f}s")
            
            if output_path.exists():
                output_size = output_path.stat().st_size
                console.print(f"  Output size: {output_size / 1024 / 1024:.1f} MB")
            
            # Show topic selection details
            console.print(f"\n[bold]Topic Selection:[/bold]")
            console.print(f"  Total topics in bag: {len(all_topics)}")
            console.print(f"  Topics extracted: {len(topics_to_extract)}")
            
            if reverse:
                excluded_topics = [t for t in all_topics if t in manager._filter_topics(all_topics, topics, None)]
                kept_topics = topics_to_extract
                console.print(f"  Topics excluded: {len(excluded_topics)}")
                
                console.print(f"\n[bold]Excluded Topics (matching patterns):[/bold]")
                for topic in excluded_topics:
                    console.print(f"    [red]✗[/red] {topic}")
                
                console.print(f"\n[bold]Kept Topics (remaining):[/bold]")
                for topic in kept_topics:
                    console.print(f"    [green]✓[/green] {topic}")
            else:
                kept_topics = topics_to_extract
                excluded_topics = [t for t in all_topics if t not in topics_to_extract]
                
                console.print(f"\n[bold]Kept Topics (matching patterns):[/bold]")
                for topic in kept_topics:
                    console.print(f"    [green]✓[/green] {topic}")
                
                if excluded_topics:
                    console.print(f"\n[bold]Excluded Topics (not matching):[/bold]")
                    for topic in excluded_topics:
                        console.print(f"    [dim]○[/dim] {topic}")
        
            # Show pattern matching summary
            console.print(f"\n[bold]Pattern Matching:[/bold]")
            console.print(f"  Requested patterns: {', '.join(topics)}")
            console.print(f"  Matching mode: {'Exclude matching' if reverse else 'Include matching'}")
            
            # Show which patterns matched which topics
            for pattern in topics:
                # Use more precise matching logic similar to _filter_topics
                exact_matches = [t for t in all_topics if t == pattern]
                if exact_matches:
                    matched_topics = exact_matches
                else:
                    # Fall back to fuzzy matching
                    matched_topics = [t for t in all_topics if pattern.lower() in t.lower()]
                
                if matched_topics:
                    console.print(f"  Pattern '{pattern}' matched: {', '.join(matched_topics)}")
                else:
                    console.print(f"  Pattern '{pattern}' matched: [dim]none[/dim]")
        
        manager.cleanup()
        
    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)



# Register extract as the default command with empty name
app.command(name="")(extract)

if __name__ == "__main__":
    app() 