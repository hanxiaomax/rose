#!/usr/bin/env python3
"""
Inspect command for ROS bag files - Using ResultHandler for rendering and export
"""
import asyncio
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from ..core.bag_manager import BagManager, InspectOptions
from ..core.result_handler import OutputFormat, RenderOptions, ExportOptions
from ..core.util import ProgressManager

app = typer.Typer(help="Inspect ROS bag files")
console = Console()


@app.command()
def inspect(
    bag_path: Path = typer.Argument(..., help="Path to the ROS bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Filter specific topics"),
    topic_filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter topics by pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("name", "--sort", help="Sort topics by (name, count, frequency)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit number of topics shown"),
    as_format: str = typer.Option("table", "--as", help="Output format (table, list, summary, json, yaml, csv, xml, html, markdown)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """
    Inspect a ROS bag file and display comprehensive analysis
    
    This command uses the unified ResultHandler for all rendering and export operations.
    """
    # Validate bag file exists
    if not bag_path.exists():
        console.print(f"[red]Error: Bag file not found: {bag_path}[/red]")
        raise typer.Exit(1)
    
    # Convert string format to enum
    try:
        output_format = OutputFormat(as_format.lower())
    except ValueError:
        supported = ", ".join([fmt.value for fmt in OutputFormat])
        console.print(f"[red]Error: Unsupported output format '{as_format}'. Supported: {supported}[/red]")
        raise typer.Exit(1)
    
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
        verbose=verbose
    )
    
    # Run the async inspection
    asyncio.run(_run_inspect(bag_path, options))


async def _run_inspect(bag_path: Path, options: InspectOptions):
    """Run the bag inspection asynchronously using BagManager and ResultHandler"""
    
    # Create BagManager
    manager = BagManager()
    
    try:
        # Show progress during analysis
        with ProgressManager.analysis_progress(
            f"Analyzing bag file: {bag_path.name}...",
            console
        ) as (progress, task, progress_callback):
            # Note: inspect_bag doesn't support progress callback yet, but we prepare for it
            result = await manager.inspect_bag(bag_path, options)
        
        # Get result handler
        handler = manager.get_result_handler()
        
        # Determine if we should export to file or render to console
        if options.output_file:
            # Export to file
            export_options = ExportOptions(
                format=options.output_format,
                output_file=options.output_file,
                pretty=True,
                include_metadata=True
            )
            
            success = handler.export(result, export_options)
            if not success:
                console.print("[red]Export failed[/red]")
                raise typer.Exit(1)
        else:
            # Render to console
            render_options = RenderOptions(
                format=options.output_format,
                verbose=options.verbose,
                show_fields=options.show_fields,
                show_cache_stats=True,
                show_summary=True,
                color=True,
                title=f"Topics in {bag_path.name}"
            )
            
            handler.render(result, render_options)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        # Clean up resources
        manager.cleanup()


if __name__ == "__main__":
    app() 