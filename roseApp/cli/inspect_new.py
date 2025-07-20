"""
Simplified inspect command using the BagManager abstraction layer
"""
import asyncio
import json
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core.bag_manager import BagManager, InspectOptions, OutputFormat


app = typer.Typer(help="Inspect ROS bag files using simplified interface")
console = Console()


@app.command()
def inspect(
    bag_path: Path = typer.Argument(..., help="Path to the ROS bag file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Filter specific topics"),
    topic_filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter topics by pattern"),
    show_fields: bool = typer.Option(False, "--show-fields", help="Show field analysis for messages"),
    sort_by: str = typer.Option("name", "--sort", help="Sort topics by (name)"),
    reverse_sort: bool = typer.Option(False, "--reverse", help="Reverse sort order"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit number of topics shown"),
    as_format: str = typer.Option("table", "--as", help="Output format (table, json, yaml, csv, xml)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """
    Inspect a ROS bag file using the simplified BagManager interface
    
    This demonstrates how CLI commands can be dramatically simplified
    by using the high-level BagManager abstraction.
    """
    # Convert string format to enum
    try:
        output_format = OutputFormat(as_format.lower())
    except ValueError:
        console.print(f"[red]Error: Unsupported output format '{as_format}'[/red]")
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
    """Run the bag inspection asynchronously"""
    
    # Create BagManager instance - this is the only core import needed!
    manager = BagManager()
    
    try:
        # Show progress during analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            
            # Analysis phase
            progress.add_task("Analyzing bag file...", total=None)
            result = await manager.inspect_bag(bag_path, options)
            
            # Field analysis phase (if requested)
            if options.show_fields:
                progress.add_task("Analyzing field information...", total=None)
        
        # Display results based on output format
        if options.output_format == OutputFormat.TABLE:
            _display_table_format(result, options)
        elif options.output_format == OutputFormat.JSON:
            _display_json_format(result, options)
        else:
            console.print(f"[yellow]Output format {options.output_format.value} not yet implemented[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        # Clean up resources
        manager.cleanup()


def _display_table_format(result: dict, options: InspectOptions):
    """Display results in table format"""
    
    # Display bag summary
    bag_info = result['bag_info']
    if options.verbose:
        console.print("\n[bold]Bag File Summary[/bold]")
        console.print(f"File: {bag_info['file_name']}")
        console.print(f"Path: {bag_info['file_path']}")
        console.print(f"Analysis Time: {bag_info['analysis_time']:.3f}s")
        console.print(f"Total Time: {bag_info.get('total_time', 'N/A')}")
        console.print(f"Cached: {'Yes' if bag_info['cached'] else 'No'}")
        console.print("-" * 60)
    
    console.print(f"Topics: {bag_info['topics_count']}")
    console.print(f"Messages: {bag_info['total_messages']:,}")
    console.print(f"File Size: {_format_size(bag_info['file_size'])}")
    console.print(f"Duration: {bag_info['duration_seconds']:.1f}s")
    
    if bag_info['total_messages'] > 0 and bag_info['duration_seconds'] > 0:
        avg_rate = bag_info['total_messages'] / bag_info['duration_seconds']
        console.print(f"Avg Rate: {avg_rate:.1f} Hz")
    
    if options.topics or options.topic_filter:
        console.print(f"Filtered: {len(result['topics'])} topics shown")
    
    console.print()
    
    # Display topics table
    table = Table(title=f"Topics in {bag_info['file_name']}")
    table.add_column("Topic", style="cyan", no_wrap=True)
    table.add_column("Message Type", style="magenta")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Frequency", justify="right", style="blue")
    
    for topic_info in result['topics']:
        frequency_str = f"{topic_info['frequency']:.1f} Hz" if topic_info['frequency'] > 0 else "0 Hz"
        table.add_row(
            topic_info['name'],
            topic_info['message_type'],
            f"{topic_info['message_count']:,}",
            frequency_str
        )
    
    console.print(table)
    
    # Display field analysis if available
    if result['field_analysis']:
        console.print()
        for topic, analysis in result['field_analysis'].items():
            console.print(f"\n[bold]Fields for {topic}[/bold]")
            console.print(f"Message Type: {analysis['message_type']}")
            console.print(f"Samples Analyzed: {analysis['samples_analyzed']}")
            console.print()
            console.print("Available Fields:")
            
            for field_path in analysis['field_paths']:
                console.print(f"  • {field_path}")
    
    # Display cache performance
    cache_stats = result['cache_stats']
    if cache_stats['total_requests'] > 0:
        hit_rate = cache_stats['hit_rate'] * 100
        console.print(f"\nCache Performance: {hit_rate:.1f}% hit rate ({cache_stats['total_requests']} requests)")


def _display_json_format(result: dict, options: InspectOptions):
    """Display results in JSON format"""
    
    # Convert result to JSON-serializable format
    json_result = _prepare_json_result(result)
    
    if options.output_file:
        # Write to file
        with open(options.output_file, 'w') as f:
            json.dump(json_result, f, indent=2, default=str)
        console.print(f"Results exported to {options.output_file}")
    else:
        # Print to console
        console.print_json(data=json_result)


def _prepare_json_result(result: dict) -> dict:
    """Prepare result for JSON serialization"""
    # Convert Path objects and other non-serializable types to strings
    json_result = {}
    
    for key, value in result.items():
        if isinstance(value, dict):
            json_result[key] = _prepare_json_result(value)
        elif isinstance(value, list):
            json_result[key] = [_prepare_json_result(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, Path):
            json_result[key] = str(value)
        else:
            json_result[key] = value
    
    return json_result


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


if __name__ == "__main__":
    app() 