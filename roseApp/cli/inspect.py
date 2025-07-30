#!/usr/bin/env python3
"""
Inspect command for ROS bag files - Using ResultHandler for rendering and export
"""
import asyncio
from pathlib import Path
from typing import Optional, List

import typer
from ..core.bag_manager import BagManager, InspectOptions
from ..core.ui_control import UIControl, OutputFormat, RenderOptions, ExportOptions, UITheme, DisplayConfig
from ..core.util import set_app_mode, AppMode, get_logger

app = typer.Typer(help="Inspect ROS bag files")


@app.command()
def inspect(
    bag_path: Path = typer.Argument(..., help="Path to the ROS bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Filter specific topics"),
    topic_filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter topics by pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("size", "--sort", help="Sort topics by (name, count, frequency, size)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit number of topics shown"),
    as_format: str = typer.Option("table", "--as", help="Output format (table, list, summary, json, yaml, csv, xml, html, markdown)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Show debug logs"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Skip cache and reparse the bag file")
):
    """
    Inspect a ROS bag file and display comprehensive analysis
    
    This command uses the unified ResultHandler for all rendering and export operations.
    """
    # Use UIControl for unified output management
    ui = UIControl()
    console = ui.get_console()
    
    # Validate bag file exists
    if not bag_path.exists():
        ui.show_error(f"Bag file not found: {bag_path}")
        raise typer.Exit(1)
    
    # Convert string format to enum
    try:
        output_format = OutputFormat(as_format.lower())
    except ValueError:
        supported = [fmt.value for fmt in OutputFormat]
        ui.show_unsupported_format_error(as_format, supported)
        raise typer.Exit(1)
    
    # Configure logging based on debug flag
    if not debug:
        # Suppress logs in standard output unless debug mode
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger('cache').setLevel(logging.CRITICAL)
        logging.getLogger('root').setLevel(logging.CRITICAL)
    
    # Create options object
    options = InspectOptions(
        topics=topics,
        topic_filter=topic_filter,
        show_fields=show_fields,
        sort_by=sort_by,
        reverse_sort=reverse_sort,
        limit=limit,
        output_format=output_format,
        output_file=output,
        verbose=verbose,
        no_cache=no_cache
    )
    
    # Run the async inspection
    asyncio.run(_run_inspect(bag_path, options, debug))


async def _run_inspect(bag_path: Path, options: InspectOptions, debug: bool = False):
    """Run the bag inspection asynchronously using BagManager and ResultHandler"""
    
    # Use UIControl for unified output management
    ui = UIControl()
    console = ui.get_console()
    
    # Create BagManager
    manager = BagManager()
    
    try:
        # Show responsive real-time analysis status using UIControl
        with UIControl.todo_analysis_progress(bag_path.name, options.show_fields, console) as update_progress:
            result = await manager.inspect_bag(bag_path, options, progress_callback=update_progress)
        
        # Determine if we should export to file or render to console
        if options.output_file:
            # Export to file
            export_options = ExportOptions(
                format=options.output_format,
                output_file=options.output_file,
                pretty=True,
                include_metadata=True
            )
            
            success = UIControl.export_result(result, export_options)
            if not success:
                ui.show_export_failed_error()
                raise typer.Exit(1)
        else:
            # Display results in panel
            display_config = DisplayConfig(
                show_summary=True,
                show_details=True,
                show_cache_stats=True,
                verbose=options.verbose,
                full_width=True
            )
            UIControl.display_inspection_result(result, display_config, console)
            
            # Handle fields display separately if requested
            if options.show_fields:
                field_analysis = result.get('field_analysis', {})
                topics = result.get('topics', [])
                if field_analysis or any('field_paths' in topic for topic in topics):
                    # Use unified UI method for field panel display
                    ui.show_fields_panel(field_analysis, topics)
            
    except Exception as e:
        ui.show_error(f"Error during bag inspection: {e}")
        raise typer.Exit(1)
    finally:
        pass


if __name__ == "__main__":
    app() 