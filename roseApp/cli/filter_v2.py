import os
import asyncio
import time
import typer
from typing import List, Optional, Tuple, Dict, Any, Set
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box
from pathlib import Path

from roseApp.core.bag_engine import BagAnalysisEngine, AnalysisType
from roseApp.core.enhanced_cache import CacheLevel
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode
from roseApp.core.legacy_parser import LegacyParserWrapper
from ..core.theme import theme
from .util import LoadingAnimation, LoadingAnimationWithTimer
from .error_handling import ValidationError, validate_file_exists, validate_choice, handle_runtime_error

# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer()

class FilterConfig:
    """Configuration for filter operation"""
    def __init__(self, 
                 input_path: str,
                 output_path: str,
                 topics: Set[str],
                 compression: str = "none",
                 sort_by: str = "size",
                 overwrite: bool = True,
                 dry_run: bool = False,
                 parallel: bool = False,
                 workers: Optional[int] = None):
        self.input_path = input_path
        self.output_path = output_path
        self.topics = topics
        self.compression = compression
        self.sort_by = sort_by
        self.overwrite = overwrite
        self.dry_run = dry_run
        self.parallel = parallel
        self.workers = workers

class FilterResult:
    """Result of filter operation"""
    def __init__(self, 
                 success: bool,
                 input_size: int,
                 output_size: int,
                 elapsed_time: float,
                 topics_processed: int,
                 messages_processed: int,
                 error_message: Optional[str] = None):
        self.success = success
        self.input_size = input_size
        self.output_size = output_size
        self.elapsed_time = elapsed_time
        self.topics_processed = topics_processed
        self.messages_processed = messages_processed
        self.error_message = error_message

@app.command()
def filter_bag(
    input_path: str = typer.Argument(..., help="Input bag file path or directory containing bag files"),
    output_dir: Optional[str] = typer.Argument(None, help="Output directory for filtered bag files (required for directory input)"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="Topic whitelist file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="Topics to include (can be specified multiple times). Alternative to whitelist file."),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression type: none, bz2, lz4 (default: none)"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Process files in parallel when input is a directory"),
    workers: Optional[int] = typer.Option(None, "--workers", help="Number of parallel workers (default: CPU count - 2)"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort topics by: topic, count, size (default: size)"),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing output files (default: True)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter ROS bag files by topics using enhanced infrastructure"""
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("filter_v2")
        
        console = Console()
        
        # Validate parameter values
        try:
            validate_file_exists(input_path, "bag file")
            validate_choice(compression, ["none", "bz2", "lz4"], "--compression")
            validate_choice(sort_by, ["topic", "count", "size"], "--sort-by")
        except ValidationError as e:
            handle_runtime_error(e, "Parameter validation")
        
        # Parse topics from whitelist and command line
        topic_set = set()
        if whitelist:
            if not os.path.exists(whitelist):
                typer.echo(f"Error: Whitelist file '{whitelist}' does not exist", err=True)
                raise typer.Exit(code=1)
            topic_set.update(_load_whitelist(whitelist))
        
        if topics:
            topic_set.update(topics)
        
        if not topic_set:
            typer.echo("Error: No topics specified. Use --whitelist or --topics to specify", err=True)
            raise typer.Exit(code=1)
        
        # Process based on input type
        if os.path.isfile(input_path):
            # Single file processing
            output_path = _determine_output_path(input_path, output_dir)
            config = FilterConfig(
                input_path=input_path,
                output_path=output_path,
                topics=topic_set,
                compression=compression,
                sort_by=sort_by,
                overwrite=overwrite,
                dry_run=dry_run
            )
            
            # Run async filter
            result = asyncio.run(_filter_single_bag_async(config))
            _display_result(result, console)
            
        elif os.path.isdir(input_path):
            # Directory processing
            if not output_dir:
                typer.echo("Error: Output directory is required when input is a directory", err=True)
                raise typer.Exit(code=1)
            
            config = FilterConfig(
                input_path=input_path,
                output_path=output_dir,
                topics=topic_set,
                compression=compression,
                sort_by=sort_by,
                overwrite=overwrite,
                dry_run=dry_run,
                parallel=parallel,
                workers=workers
            )
            
            # Run async directory processing
            results = asyncio.run(_filter_directory_async(config))
            _display_batch_results(results, console)
            
        else:
            typer.echo(f"Error: Input path '{input_path}' does not exist", err=True)
            raise typer.Exit(code=1)
            
    except typer.Exit:
        # Re-raise typer.Exit cleanly
        raise
    except Exception as e:
        # Handle runtime errors without stack trace
        handle_runtime_error(e, "Bag filtering operation")

async def _filter_single_bag_async(config: FilterConfig) -> FilterResult:
    """Filter a single bag file using the enhanced infrastructure"""
    console = Console()
    
    # Initialize BagAnalysisEngine
    engine = BagAnalysisEngine()
    
    try:
        # Get bag analysis for topic validation
        with LoadingAnimationWithTimer("Analyzing bag file...", dismiss=True):
            analysis = await engine.analyze_bag(
                config.input_path,
                analysis_type=AnalysisType.FILTER,
                level=CacheLevel.METADATA
            )
        
        # Validate topics exist in bag
        available_topics = set(analysis.topics.keys())
        invalid_topics = config.topics - available_topics
        
        if invalid_topics:
            typer.echo(f"Warning: Topics not found in bag: {', '.join(invalid_topics)}", err=True)
            
        valid_topics = config.topics & available_topics
        if not valid_topics:
            return FilterResult(
                success=False,
                input_size=0,
                output_size=0,
                elapsed_time=0,
                topics_processed=0,
                messages_processed=0,
                error_message="No valid topics found in bag file"
            )
        
        # Display topic selection table
        _display_topic_selection_table(analysis, valid_topics, console, config.sort_by)
        
        if config.dry_run:
            console.print("[bold yellow]Dry run - no actual modifications will be made[/bold yellow]")
            input_size = os.path.getsize(config.input_path)
            return FilterResult(
                success=True,
                input_size=input_size,
                output_size=0,
                elapsed_time=0,
                topics_processed=len(valid_topics),
                messages_processed=0,
                error_message=None
            )
        
        # Perform filtering
        console.print(f"\n[bold]Starting to filter bag file:[/bold]")
        console.print(f"Input:  [green]{config.input_path}[/green]")
        console.print(f"Output: [blue]{config.output_path}[/blue]")
        console.print()
        
        start_time = time.time()
        
        # Use enhanced filter operation
        with LoadingAnimation("Filtering bag file...") as progress:
            task_id = progress.add_task("Filtering...", total=100)
            
            def update_progress(percent: int):
                progress.update(task_id, completed=percent)
            
            filter_result = await engine.filter_bag(
                config.input_path,
                config.output_path,
                list(valid_topics),
                compression=config.compression,
                progress_callback=update_progress,
                overwrite=config.overwrite
            )
            
            progress.update(task_id, description="[green]✓ Complete[/green]", completed=100)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Get file sizes for result
        input_size = os.path.getsize(config.input_path)
        output_size = os.path.getsize(config.output_path) if os.path.exists(config.output_path) else 0
        
        return FilterResult(
            success=True,
            input_size=input_size,
            output_size=output_size,
            elapsed_time=elapsed_time,
            topics_processed=len(valid_topics),
            messages_processed=filter_result.get('messages_processed', 0),
            error_message=None
        )
        
    except Exception as e:
        return FilterResult(
            success=False,
            input_size=0,
            output_size=0,
            elapsed_time=0,
            topics_processed=0,
            messages_processed=0,
            error_message=str(e)
        )

async def _filter_directory_async(config: FilterConfig) -> List[FilterResult]:
    """Filter multiple bag files in a directory"""
    console = Console()
    
    # Find all bag files in directory
    bag_files = []
    for root, dirs, files in os.walk(config.input_path):
        for file in files:
            if file.endswith('.bag'):
                bag_files.append(os.path.join(root, file))
    
    if not bag_files:
        typer.echo(f"No bag files found in directory: {config.input_path}", err=True)
        raise typer.Exit(code=1)
    
    console.print(f"Found {len(bag_files)} bag files to process")
    
    # Create output directory
    os.makedirs(config.output_path, exist_ok=True)
    
    results = []
    
    if config.parallel:
        # Parallel processing
        import concurrent.futures
        
        semaphore = asyncio.Semaphore(config.workers or 4)
        
        async def process_with_semaphore(bag_file):
            async with semaphore:
                output_file = os.path.join(
                    config.output_path,
                    os.path.basename(bag_file).replace('.bag', '_filtered.bag')
                )
                
                file_config = FilterConfig(
                    input_path=bag_file,
                    output_path=output_file,
                    topics=config.topics,
                    compression=config.compression,
                    sort_by=config.sort_by,
                    overwrite=config.overwrite,
                    dry_run=config.dry_run
                )
                
                return await _filter_single_bag_async(file_config)
        
        # Process all files concurrently
        results = await asyncio.gather(
            *[process_with_semaphore(bag_file) for bag_file in bag_files],
            return_exceptions=True
        )
        
    else:
        # Sequential processing
        for bag_file in bag_files:
            output_file = os.path.join(
                config.output_path,
                os.path.basename(bag_file).replace('.bag', '_filtered.bag')
            )
            
            file_config = FilterConfig(
                input_path=bag_file,
                output_path=output_file,
                topics=config.topics,
                compression=config.compression,
                sort_by=config.sort_by,
                overwrite=config.overwrite,
                dry_run=config.dry_run
            )
            
            result = await _filter_single_bag_async(file_config)
            results.append(result)
    
    return results

def _determine_output_path(input_path: str, output_dir: Optional[str]) -> str:
    """Determine output path based on input and output directory"""
    if output_dir is None:
        # Use same directory as input with _filtered suffix
        return os.path.splitext(input_path)[0] + "_filtered.bag"
    
    if output_dir.endswith('.bag'):
        # User provided output file path
        parent_dir = os.path.dirname(output_dir)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        return output_dir
    
    if os.path.isfile(output_dir):
        typer.echo(f"Error: '{output_dir}' is an existing file, not a directory", err=True)
        raise typer.Exit(code=1)
    
    # Create output directory and generate filename
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(os.path.splitext(input_path)[0]) + "_filtered.bag"
    return os.path.join(output_dir, filename)

def _load_whitelist(whitelist_path: str) -> List[str]:
    """Load topics from whitelist file"""
    topics = []
    try:
        with open(whitelist_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    topics.append(line)
    except Exception as e:
        typer.echo(f"Error reading whitelist file: {e}", err=True)
        raise typer.Exit(code=1)
    
    return topics

def _display_topic_selection_table(analysis, selected_topics: Set[str], console: Console, sort_by: str):
    """Display topic selection table"""
    def format_size(size_bytes: int) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    # Create table
    table = Table(box=box.SIMPLE, title="Topic Selection", title_style="bold cyan")
    
    # Get terminal width for responsive layout
    terminal_width = console.width
    
    # Add columns based on terminal width
    table.add_column("Topic", style="cyan", min_width=20)
    table.add_column("Type", style="magenta", min_width=15)
    table.add_column("Count", justify="right", style="yellow", min_width=8)
    
    if terminal_width > 100:
        table.add_column("Size", justify="right", style="green", min_width=10)
    
    table.add_column("Selected", justify="center", style="bold", min_width=8)
    
    # Sort topics
    all_topics = list(analysis.topics.keys())
    if sort_by == "topic":
        all_topics.sort()
    elif sort_by == "count":
        all_topics.sort(key=lambda t: analysis.topics[t].get('count', 0), reverse=True)
    elif sort_by == "size":
        all_topics.sort(key=lambda t: analysis.topics[t].get('size', 0), reverse=True)
    
    # Add rows
    selected_count = 0
    selected_size = 0
    total_size = 0
    
    for topic in all_topics:
        topic_info = analysis.topics[topic]
        count = topic_info.get('count', 0)
        size = topic_info.get('size', 0)
        msg_type = topic_info.get('type', 'unknown')
        
        is_selected = topic in selected_topics
        
        if is_selected:
            selected_count += 1
            selected_size += size
        
        total_size += size
        
        # Create row data
        row_data = [
            topic,
            msg_type,
            str(count),
        ]
        
        if terminal_width > 100:
            row_data.append(format_size(size))
        
        row_data.append("✓" if is_selected else "✗")
        
        # Add row with appropriate styling
        if is_selected:
            table.add_row(*row_data, style="bold")
        else:
            table.add_row(*row_data, style="dim")
    
    console.print(table)
    
    # Show selection summary
    console.print(f"\n[bold]Selected:[/bold] [green]{selected_count}[/green] / "
                 f"[white]{len(all_topics)}[/white] topics, "
                 f"[green]{format_size(selected_size)}[/green] / "
                 f"[white]{format_size(total_size)}[/white] data")

def _display_result(result: FilterResult, console: Console):
    """Display single filter result"""
    def format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    if not result.success:
        console.print(f"\n[bold red]Filtering failed:[/bold red]")
        console.print(f"Error: {result.error_message}")
        raise typer.Exit(code=1)
    
    if result.output_size > 0:
        size_reduction = (1 - result.output_size/result.input_size) * 100
        
        console.print(f"\n[bold green]Filtering completed successfully:[/bold green]")
        console.print("─" * 80)
        console.print(f"Time: {int(result.elapsed_time//60)} minutes {result.elapsed_time%60:.2f} seconds")
        console.print(f"Topics processed: {result.topics_processed}")
        console.print(f"Input size:  {format_size(result.input_size)}")
        console.print(f"Output size: {format_size(result.output_size)}")
        console.print(f"Size reduction: {size_reduction:.1f}%")
    else:
        console.print(f"\n[bold yellow]Dry run completed[/bold yellow]")
        console.print(f"Would process: {result.topics_processed} topics")
        console.print(f"Input size: {format_size(result.input_size)}")

def _display_batch_results(results: List[FilterResult], console: Console):
    """Display batch processing results"""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    console.print(f"\n[bold]Batch processing completed:[/bold]")
    console.print(f"Successful: [green]{len(successful)}[/green]")
    console.print(f"Failed: [red]{len(failed)}[/red]")
    
    if failed:
        console.print(f"\n[bold red]Failed operations:[/bold red]")
        for result in failed:
            console.print(f"  • {result.error_message}")

if __name__ == "__main__":
    app() 