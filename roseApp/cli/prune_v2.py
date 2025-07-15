import os
import asyncio
import time
import typer
from typing import List, Optional, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich import box
from pathlib import Path
from datetime import datetime, timedelta

from roseApp.core.bag_engine import BagAnalysisEngine, AnalysisType
from roseApp.core.enhanced_cache import CacheLevel
from roseApp.core.util import get_logger, set_app_mode, AppMode
from roseApp.core.legacy_parser import LegacyParserWrapper
from ..core.theme import theme
from .util import LoadingAnimation, LoadingAnimationWithTimer
from .error_handling import ValidationError, validate_file_exists, handle_runtime_error

# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer()

class PruneConfig:
    """Configuration for prune operation"""
    def __init__(self,
                 bag_path: str,
                 output_path: Optional[str] = None,
                 time_start: Optional[float] = None,
                 time_end: Optional[float] = None,
                 duration: Optional[float] = None,
                 skip_first: Optional[float] = None,
                 skip_last: Optional[float] = None,
                 topics: Optional[List[str]] = None,
                 exclude_topics: Optional[List[str]] = None,
                 compression: str = "none",
                 overwrite: bool = True):
        self.bag_path = bag_path
        self.output_path = output_path
        self.time_start = time_start
        self.time_end = time_end
        self.duration = duration
        self.skip_first = skip_first
        self.skip_last = skip_last
        self.topics = topics or []
        self.exclude_topics = exclude_topics or []
        self.compression = compression
        self.overwrite = overwrite

class PruneResult:
    """Result of prune operation"""
    def __init__(self,
                 success: bool,
                 input_size: int = 0,
                 output_size: int = 0,
                 original_duration: float = 0,
                 pruned_duration: float = 0,
                 messages_removed: int = 0,
                 topics_processed: int = 0,
                 elapsed_time: float = 0,
                 error_message: Optional[str] = None):
        self.success = success
        self.input_size = input_size
        self.output_size = output_size
        self.original_duration = original_duration
        self.pruned_duration = pruned_duration
        self.messages_removed = messages_removed
        self.topics_processed = topics_processed
        self.elapsed_time = elapsed_time
        self.error_message = error_message

@app.command()
def prune_bag(
    bag_path: str = typer.Argument(..., help="Path to the bag file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: auto-generated)"),
    time_start: Optional[str] = typer.Option(None, "--start", "-s", help="Start time (format: HH:MM:SS or seconds)"),
    time_end: Optional[str] = typer.Option(None, "--end", "-e", help="End time (format: HH:MM:SS or seconds)"),
    duration: Optional[str] = typer.Option(None, "--duration", "-d", help="Duration to keep (format: HH:MM:SS or seconds)"),
    skip_first: Optional[str] = typer.Option(None, "--skip-first", help="Skip first N seconds/time"),
    skip_last: Optional[str] = typer.Option(None, "--skip-last", help="Skip last N seconds/time"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Topics to include (can be specified multiple times)"),
    exclude_topics: Optional[List[str]] = typer.Option(None, "--exclude", "-x", help="Topics to exclude (can be specified multiple times)"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4 (default: none)"),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing output files (default: True)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be pruned without actually doing it")
):
    """Prune ROS bag files by time range and topics using enhanced infrastructure"""
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("prune_v2")
        
        console = Console()
        
        # Validate inputs
        try:
            validate_file_exists(bag_path, "bag file")
        except ValidationError as e:
            handle_runtime_error(e, "Parameter validation")
        
        # Parse time parameters
        time_start_sec = _parse_time_parameter(time_start, "start time") if time_start else None
        time_end_sec = _parse_time_parameter(time_end, "end time") if time_end else None
        duration_sec = _parse_time_parameter(duration, "duration") if duration else None
        skip_first_sec = _parse_time_parameter(skip_first, "skip first") if skip_first else None
        skip_last_sec = _parse_time_parameter(skip_last, "skip last") if skip_last else None
        
        # Validate time parameters
        if time_start_sec and time_end_sec and time_start_sec >= time_end_sec:
            typer.echo("Error: Start time must be before end time", err=True)
            raise typer.Exit(code=1)
        
        # Create prune configuration
        config = PruneConfig(
            bag_path=bag_path,
            output_path=output,
            time_start=time_start_sec,
            time_end=time_end_sec,
            duration=duration_sec,
            skip_first=skip_first_sec,
            skip_last=skip_last_sec,
            topics=topics,
            exclude_topics=exclude_topics,
            compression=compression,
            overwrite=overwrite
        )
        
        # Run async pruning
        result = asyncio.run(_prune_bag_async(config, dry_run))
        _display_prune_result(result, console)
        
    except typer.Exit:
        # Re-raise typer.Exit cleanly
        raise
    except Exception as e:
        # Handle runtime errors without stack trace
        handle_runtime_error(e, "Bag pruning operation")

async def _prune_bag_async(config: PruneConfig, dry_run: bool = False) -> PruneResult:
    """Prune bag file using the enhanced infrastructure"""
    console = Console()
    
    # Initialize BagAnalysisEngine
    engine = BagAnalysisEngine()
    
    try:
        # Get bag analysis
        with LoadingAnimationWithTimer("Analyzing bag file...", dismiss=True):
            analysis = await engine.analyze_bag(
                config.bag_path,
                analysis_type=AnalysisType.PRUNE,
                level=CacheLevel.STATISTICS
            )
        
        # Calculate actual time range based on bag content
        bag_start_time = analysis.start_time
        bag_end_time = analysis.end_time
        bag_duration = bag_end_time - bag_start_time
        
        # Determine pruning parameters
        prune_start, prune_end = _calculate_prune_range(
            config, bag_start_time, bag_end_time, bag_duration
        )
        
        # Validate topic filters
        available_topics = set(analysis.topics.keys())
        
        if config.topics:
            invalid_topics = set(config.topics) - available_topics
            if invalid_topics:
                typer.echo(f"Warning: Topics not found in bag: {', '.join(invalid_topics)}", err=True)
            valid_topics = set(config.topics) & available_topics
        else:
            valid_topics = available_topics
        
        if config.exclude_topics:
            valid_topics = valid_topics - set(config.exclude_topics)
        
        if not valid_topics:
            return PruneResult(
                success=False,
                error_message="No valid topics remain after filtering"
            )
        
        # Display pruning plan
        _display_pruning_plan(analysis, config, prune_start, prune_end, valid_topics, console)
        
        if dry_run:
            console.print("[bold yellow]Dry run - no actual pruning will be performed[/bold yellow]")
            
            # Calculate estimated results
            pruned_duration = prune_end - prune_start
            estimated_messages = _estimate_messages_in_range(analysis, prune_start, prune_end, valid_topics)
            
            return PruneResult(
                success=True,
                input_size=os.path.getsize(config.bag_path),
                output_size=0,
                original_duration=bag_duration,
                pruned_duration=pruned_duration,
                messages_removed=0,
                topics_processed=len(valid_topics),
                elapsed_time=0
            )
        
        # Perform actual pruning
        start_time = time.time()
        
        console.print(f"\n[bold]Starting to prune bag file:[/bold]")
        console.print(f"Input:  [green]{config.bag_path}[/green]")
        
        output_path = _determine_prune_output_path(config)
        console.print(f"Output: [blue]{output_path}[/blue]")
        
        with LoadingAnimation("Pruning bag file...") as progress:
            task_id = progress.add_task("Pruning...", total=100)
            
            def update_progress(percent: int):
                progress.update(task_id, completed=percent)
            
            prune_result = await engine.prune_bag(
                config.bag_path,
                output_path,
                start_time=prune_start,
                end_time=prune_end,
                topics=list(valid_topics),
                compression=config.compression,
                progress_callback=update_progress,
                overwrite=config.overwrite
            )
            
            progress.update(task_id, description="[green]✓ Complete[/green]", completed=100)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Get file sizes for result
        input_size = os.path.getsize(config.bag_path)
        output_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return PruneResult(
            success=True,
            input_size=input_size,
            output_size=output_size,
            original_duration=bag_duration,
            pruned_duration=prune_end - prune_start,
            messages_removed=prune_result.get('messages_removed', 0),
            topics_processed=len(valid_topics),
            elapsed_time=elapsed_time
        )
        
    except Exception as e:
        return PruneResult(
            success=False,
            error_message=str(e)
        )

def _parse_time_parameter(time_str: str, param_name: str) -> float:
    """Parse time parameter (HH:MM:SS or seconds)"""
    if not time_str:
        return None
    
    # Try to parse as seconds first
    try:
        return float(time_str)
    except ValueError:
        pass
    
    # Try to parse as HH:MM:SS
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        else:
            raise ValueError("Invalid time format")
    except ValueError:
        typer.echo(f"Error: Invalid {param_name} format. Use HH:MM:SS or seconds", err=True)
        raise typer.Exit(code=1)

def _calculate_prune_range(config: PruneConfig, bag_start: float, bag_end: float, bag_duration: float) -> Tuple[float, float]:
    """Calculate the actual time range to prune"""
    prune_start = bag_start
    prune_end = bag_end
    
    # Apply skip_first
    if config.skip_first:
        prune_start = max(prune_start, bag_start + config.skip_first)
    
    # Apply skip_last
    if config.skip_last:
        prune_end = min(prune_end, bag_end - config.skip_last)
    
    # Apply absolute start time
    if config.time_start:
        prune_start = max(prune_start, bag_start + config.time_start)
    
    # Apply absolute end time
    if config.time_end:
        prune_end = min(prune_end, bag_start + config.time_end)
    
    # Apply duration
    if config.duration:
        if config.time_start:
            prune_end = min(prune_end, prune_start + config.duration)
        else:
            # If no start time, keep last N seconds
            prune_start = max(prune_start, prune_end - config.duration)
    
    # Ensure valid range
    if prune_start >= prune_end:
        raise ValueError("Invalid time range: start time must be before end time")
    
    return prune_start, prune_end

def _estimate_messages_in_range(analysis, start_time: float, end_time: float, topics: set) -> int:
    """Estimate number of messages in time range"""
    total_messages = 0
    duration_ratio = (end_time - start_time) / (analysis.end_time - analysis.start_time)
    
    for topic in topics:
        if topic in analysis.topics:
            topic_messages = analysis.topics[topic].get('count', 0)
            total_messages += int(topic_messages * duration_ratio)
    
    return total_messages

def _display_pruning_plan(analysis, config: PruneConfig, prune_start: float, prune_end: float, valid_topics: set, console: Console):
    """Display the pruning plan"""
    bag_start = analysis.start_time
    bag_end = analysis.end_time
    bag_duration = bag_end - bag_start
    pruned_duration = prune_end - prune_start
    
    # Create summary table
    table = Table(box=box.SIMPLE, title="Pruning Plan", title_style="bold cyan")
    table.add_column("Parameter", style="cyan", min_width=20)
    table.add_column("Value", style="white", min_width=20)
    
    # Format times
    start_datetime = datetime.fromtimestamp(prune_start)
    end_datetime = datetime.fromtimestamp(prune_end)
    
    table.add_row("Original Duration", f"{bag_duration:.2f} seconds")
    table.add_row("Pruned Duration", f"{pruned_duration:.2f} seconds")
    table.add_row("Start Time", start_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("End Time", end_datetime.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Topics Selected", str(len(valid_topics)))
    table.add_row("Time Reduction", f"{(1 - pruned_duration/bag_duration)*100:.1f}%")
    
    console.print(table)
    
    # Show topic selection if filtered
    if config.topics or config.exclude_topics:
        console.print(f"\n[bold]Selected Topics:[/bold]")
        for topic in sorted(valid_topics):
            topic_info = analysis.topics.get(topic, {})
            console.print(f"  • {topic} ({topic_info.get('count', 0)} messages)")

def _determine_prune_output_path(config: PruneConfig) -> str:
    """Determine the output path for the pruned bag"""
    if config.output_path:
        return config.output_path
    
    # Generate default output path
    base_path = os.path.splitext(config.bag_path)[0]
    return f"{base_path}_pruned.bag"

def _display_prune_result(result: PruneResult, console: Console):
    """Display prune operation result"""
    def format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    if not result.success:
        console.print(f"\n[bold red]Pruning failed:[/bold red]")
        console.print(f"Error: {result.error_message}")
        raise typer.Exit(code=1)
    
    console.print(f"\n[bold green]Pruning completed successfully:[/bold green]")
    console.print("─" * 80)
    
    if result.output_size > 0:
        size_reduction = (1 - result.output_size/result.input_size) * 100
        time_reduction = (1 - result.pruned_duration/result.original_duration) * 100
        
        console.print(f"Processing time: {result.elapsed_time:.2f} seconds")
        console.print(f"Topics processed: {result.topics_processed}")
        console.print(f"Original duration: {result.original_duration:.2f} seconds")
        console.print(f"Pruned duration: {result.pruned_duration:.2f} seconds")
        console.print(f"Time reduction: {time_reduction:.1f}%")
        console.print(f"Input size:  {format_size(result.input_size)}")
        console.print(f"Output size: {format_size(result.output_size)}")
        console.print(f"Size reduction: {size_reduction:.1f}%")
        
        if result.messages_removed > 0:
            console.print(f"Messages removed: {result.messages_removed}")
    else:
        console.print(f"Dry run completed")
        console.print(f"Would process: {result.topics_processed} topics")
        console.print(f"Original duration: {result.original_duration:.2f} seconds")
        console.print(f"Pruned duration: {result.pruned_duration:.2f} seconds")
        console.print(f"Input size: {format_size(result.input_size)}")

if __name__ == "__main__":
    app() 