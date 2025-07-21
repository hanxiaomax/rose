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
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
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


def main(
    input_bag: str = typer.Argument(..., help="Path to input bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", help="Topics to keep (supports fuzzy matching, can be used multiple times)"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="Output bag file path (default: input_filtered_timestamp.bag)"),
    reverse: bool = typer.Option(False, "--reverse", help="Reverse selection - exclude specified topics instead of including them"),
    compression: str = typer.Option("none", "-c", "--compression", help="Compression type: none, bz2, lz4"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be extracted without doing it"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Answer yes to all questions (overwrite, etc.)"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed extraction information")
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
    Extract specific topics from a ROS bag file using ResultHandler for unified output
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
        
        # Create BagManager and get available topics
        manager = BagManager()
        
        # Show progress during bag analysis
        with UIControl.responsive_progress(
            f"Analyzing bag file: {input_path.name}...",
            show_speed=False,
            theme=UITheme.ANALYSIS,
            console=console
        ) as (progress, task, progress_callback, update_description):
            # Create enhanced callback for analysis
            def analysis_callback(percent: float):
                progress_callback(percent)
                if percent > 50:
                    update_description(f"Analyzing bag file: {input_path.name}... (reading topics)")
                elif percent > 80:
                    update_description(f"Analyzing bag file: {input_path.name}... (finalizing)")
            
            topics_result = await_sync(manager.get_topics(input_path, progress_callback=analysis_callback))
        
        all_topics = [t['name'] for t in topics_result['topics']]
        
        # Apply topic filtering
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
        
        # Prepare extraction result data structure
        extraction_result = {
            'operation': 'extract_topics',
            'input_file': str(input_path),
            'output_file': str(output_path),
            'compression': compression,
            'dry_run': dry_run,
            'reverse': reverse,
            'topic_patterns': topics,
            'topics_to_extract': topics_to_extract,
            'bag_info': topics_result.get('bag_info', {}),
            'cache_stats': topics_result.get('cache_stats', {}),
            'all_topics': topics_result['topics'],
            'filtered_topics': [t for t in topics_result['topics'] if t['name'] in topics_to_extract],
            'excluded_topics': [t for t in topics_result['topics'] if t['name'] not in topics_to_extract],
            'statistics': {
                'total_topics': len(all_topics),
                'selected_topics': len(topics_to_extract),
                'excluded_topics': len(all_topics) - len(topics_to_extract),
                'total_messages': sum(t['message_count'] for t in topics_result['topics']),
                'selected_messages': sum(t['message_count'] for t in topics_result['topics'] if t['name'] in topics_to_extract),
                'selection_percentage': (len(topics_to_extract) / len(all_topics) * 100) if all_topics else 0,
                'message_percentage': 0  # Will be calculated below
            }
        }
        
        # Calculate message percentage
        if extraction_result['statistics']['total_messages'] > 0:
            extraction_result['statistics']['message_percentage'] = (
                extraction_result['statistics']['selected_messages'] / 
                extraction_result['statistics']['total_messages'] * 100
            )
        
        # If dry run, show preview and return
        if dry_run:
            extraction_result['success'] = True
            extraction_result['message'] = "Dry run completed - no files were created"
            
            # Use ResultHandler to render the result
            handler = ResultHandler(console)
            
            # Render to console using default summary format
            render_options = RenderOptions(
                format=OutputFormat.SUMMARY,
                verbose=verbose,
                show_summary=True,
                color=True,
                title=f"Extraction Preview - {input_path.name}"
            )
            handler.render(extraction_result, render_options)
            
            console.print(f"\n[yellow]Dry run completed - no files were created[/yellow]")
            return
        
        # Perform the actual extraction
        options = ExtractOptions(
            topics=topics_to_extract,
            output_path=output_path,
            compression=compression,
            overwrite=True,  # We already handled overwrite confirmation above
            dry_run=False
        )
        
        # Track extraction timing
        extraction_start_time = time.time()
        
        # Show progress during extraction with topic-level detail
        with UIControl.topic_progress(
            f"Extracting {len(topics_to_extract)} topics",
            topics_to_extract,
            theme=UITheme.EXTRACTION,
            console=console
        ) as (progress, task, topic_callback):
            # Create enhanced topic progress callback
            def enhanced_topic_callback(topic_index: int, topic: str, messages_processed: int, 
                                       total_messages: int, phase: str):
                topic_callback(topic_index, topic, messages_processed, total_messages, phase)
            
            result = await_sync(manager.extract_bag(input_path, options, progress_callback=enhanced_topic_callback))
        
        extraction_end_time = time.time()
        extraction_time = extraction_end_time - extraction_start_time
        
        # Check if extraction was successful
        if not result.get('success', False):
            console.print(f"\n[red]Extraction failed: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)
        
        # Display results using UIControl
        if result.get('success'):
            UIControl.show_success(f"Successfully extracted to: {options.output_path}", console)
        else:
            UIControl.show_error(f"Extraction failed: {result.get('error', 'Unknown error')}", console)
        
        # Display extraction summary
        display_config = DisplayConfig(
            show_summary=True,
            show_details=True,
            show_cache_stats=True,
            show_performance=True,
            verbose=verbose,
            full_width=True
        )
        UIControl.display_extraction_result(extraction_result, display_config, console)
        
        manager.cleanup()
        
    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)



# Register main as the default command with empty name
app.command(name="")(main)

if __name__ == "__main__":
    typer.run(main) 