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
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

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

class PlotConfig:
    """Configuration for plot operation"""
    def __init__(self,
                 bag_path: str,
                 series: List[str],
                 output_path: Optional[str] = None,
                 time_range: Optional[Tuple[float, float]] = None,
                 plot_type: str = "line",
                 title: Optional[str] = None,
                 width: int = 12,
                 height: int = 8,
                 dpi: int = 100,
                 format: str = "png",
                 show_grid: bool = True,
                 show_legend: bool = True):
        self.bag_path = bag_path
        self.series = series
        self.output_path = output_path
        self.time_range = time_range
        self.plot_type = plot_type
        self.title = title
        self.width = width
        self.height = height
        self.dpi = dpi
        self.format = format
        self.show_grid = show_grid
        self.show_legend = show_legend

class PlotResult:
    """Result of plot operation"""
    def __init__(self,
                 success: bool,
                 output_path: Optional[str] = None,
                 data_points: int = 0,
                 time_range: Optional[Tuple[float, float]] = None,
                 elapsed_time: float = 0,
                 error_message: Optional[str] = None):
        self.success = success
        self.output_path = output_path
        self.data_points = data_points
        self.time_range = time_range
        self.elapsed_time = elapsed_time
        self.error_message = error_message

@app.command()
def plot_bag(
    bag_path: str = typer.Argument(..., help="Path to the bag file"),
    series: List[str] = typer.Option(..., "--series", "-s", help="Data series to plot in format 'topic.field' (can be specified multiple times)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: auto-generated)"),
    time_range: Optional[str] = typer.Option(None, "--time-range", "-t", help="Time range to plot in format 'start:end' (seconds)"),
    plot_type: str = typer.Option("line", "--type", help="Plot type: line, scatter, bar (default: line)"),
    title: Optional[str] = typer.Option(None, "--title", help="Plot title"),
    width: int = typer.Option(12, "--width", "-w", help="Plot width in inches (default: 12)"),
    height: int = typer.Option(8, "--height", "-h", help="Plot height in inches (default: 8)"),
    dpi: int = typer.Option(100, "--dpi", help="Plot resolution (default: 100)"),
    format: str = typer.Option("png", "--format", "-f", help="Output format: png, pdf, svg (default: png)"),
    no_grid: bool = typer.Option(False, "--no-grid", help="Disable grid lines"),
    no_legend: bool = typer.Option(False, "--no-legend", help="Disable legend"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be plotted without creating the plot")
):
    """Plot data from ROS bag files using enhanced infrastructure"""
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("plot_v2")
        
        console = Console()
        
        # Validate inputs
        try:
            validate_file_exists(bag_path, "bag file")
        except ValidationError as e:
            handle_runtime_error(e, "Parameter validation")
        
        # Parse time range
        time_range_tuple = None
        if time_range:
            try:
                start_str, end_str = time_range.split(':')
                time_range_tuple = (float(start_str), float(end_str))
            except ValueError:
                typer.echo("Error: Invalid time range format. Use 'start:end' format", err=True)
                raise typer.Exit(code=1)
        
        # Create plot configuration
        config = PlotConfig(
            bag_path=bag_path,
            series=series,
            output_path=output,
            time_range=time_range_tuple,
            plot_type=plot_type,
            title=title,
            width=width,
            height=height,
            dpi=dpi,
            format=format,
            show_grid=not no_grid,
            show_legend=not no_legend
        )
        
        # Run async plotting
        result = asyncio.run(_plot_bag_async(config, dry_run))
        _display_plot_result(result, console)
        
    except typer.Exit:
        # Re-raise typer.Exit cleanly
        raise
    except Exception as e:
        # Handle runtime errors without stack trace
        handle_runtime_error(e, "Bag plotting operation")

async def _plot_bag_async(config: PlotConfig, dry_run: bool = False) -> PlotResult:
    """Plot bag data using the enhanced infrastructure"""
    console = Console()
    
    # Initialize BagAnalysisEngine
    engine = BagAnalysisEngine()
    
    try:
        # Get bag analysis for field validation
        with LoadingAnimationWithTimer("Analyzing bag file...", dismiss=True):
            analysis = await engine.analyze_bag(
                config.bag_path,
                analysis_type=AnalysisType.PLOT,
                level=CacheLevel.FIELDS
            )
        
        # Validate series exist in bag
        validated_series = await _validate_series(analysis, config.series)
        
        if not validated_series:
            return PlotResult(
                success=False,
                error_message="No valid series found in bag file"
            )
        
        # Display series information
        _display_series_info(analysis, validated_series, console)
        
        if dry_run:
            console.print("[bold yellow]Dry run - no actual plot will be created[/bold yellow]")
            return PlotResult(
                success=True,
                data_points=0,
                elapsed_time=0
            )
        
        # Extract data for plotting
        start_time = time.time()
        
        console.print(f"\n[bold]Starting to plot data:[/bold]")
        console.print(f"Input:  [green]{config.bag_path}[/green]")
        
        plot_data = {}
        
        with LoadingAnimation("Extracting plot data...") as progress:
            for i, series in enumerate(validated_series):
                task_id = progress.add_task(f"Extracting: {series}", total=100)
                
                # Extract data for this series
                data = await engine.extract_field_data(
                    config.bag_path,
                    series,
                    time_range=config.time_range,
                    progress_callback=lambda p: progress.update(task_id, completed=p)
                )
                
                plot_data[series] = data
                progress.update(task_id, description=f"[green]✓ {series}[/green]", completed=100)
        
        # Generate plot
        output_path = _determine_plot_output_path(config)
        
        with LoadingAnimation("Generating plot...") as progress:
            task_id = progress.add_task("Creating plot...", total=100)
            
            plot_result = await _create_plot(config, plot_data, output_path)
            
            progress.update(task_id, description="[green]✓ Plot created[/green]", completed=100)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Count total data points
        total_points = sum(len(data.get('values', [])) for data in plot_data.values())
        
        # Determine time range from data
        all_times = []
        for data in plot_data.values():
            all_times.extend(data.get('timestamps', []))
        
        time_range = None
        if all_times:
            time_range = (min(all_times), max(all_times))
        
        return PlotResult(
            success=True,
            output_path=output_path,
            data_points=total_points,
            time_range=time_range,
            elapsed_time=elapsed_time
        )
        
    except Exception as e:
        return PlotResult(
            success=False,
            error_message=str(e)
        )

async def _validate_series(analysis, series_list: List[str]) -> List[str]:
    """Validate that series exist in the bag analysis"""
    validated_series = []
    
    for series in series_list:
        if '.' not in series:
            typer.echo(f"Warning: Invalid series format '{series}'. Use 'topic.field' format", err=True)
            continue
        
        topic, field = series.split('.', 1)
        
        if topic not in analysis.topics:
            typer.echo(f"Warning: Topic '{topic}' not found in bag", err=True)
            continue
        
        # Check if field exists in topic (simplified check)
        # In a real implementation, you'd check the message structure
        validated_series.append(series)
    
    return validated_series

def _display_series_info(analysis, series_list: List[str], console: Console):
    """Display information about the series to be plotted"""
    table = Table(box=box.SIMPLE, title="Plot Series", title_style="bold cyan")
    
    table.add_column("Series", style="cyan", min_width=20)
    table.add_column("Topic", style="magenta", min_width=15)
    table.add_column("Field", style="yellow", min_width=10)
    table.add_column("Type", style="green", min_width=10)
    table.add_column("Messages", justify="right", style="white", min_width=8)
    
    for series in series_list:
        topic, field = series.split('.', 1)
        topic_info = analysis.topics.get(topic, {})
        
        table.add_row(
            series,
            topic,
            field,
            topic_info.get('type', 'unknown'),
            str(topic_info.get('count', 0))
        )
    
    console.print(table)

def _determine_plot_output_path(config: PlotConfig) -> str:
    """Determine the output path for the plot"""
    if config.output_path:
        return config.output_path
    
    # Generate default output path
    base_name = os.path.splitext(os.path.basename(config.bag_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{base_name}_plot_{timestamp}.{config.format}"

async def _create_plot(config: PlotConfig, plot_data: Dict[str, Any], output_path: str) -> bool:
    """Create the actual plot using matplotlib"""
    # Set up the plot
    plt.figure(figsize=(config.width, config.height), dpi=config.dpi)
    
    # Plot each series
    for series, data in plot_data.items():
        timestamps = data.get('timestamps', [])
        values = data.get('values', [])
        
        if not timestamps or not values:
            continue
        
        # Convert timestamps to datetime objects
        times = [datetime.fromtimestamp(t) for t in timestamps]
        
        if config.plot_type == "line":
            plt.plot(times, values, label=series, marker='o', markersize=2)
        elif config.plot_type == "scatter":
            plt.scatter(times, values, label=series, alpha=0.7)
        elif config.plot_type == "bar":
            plt.bar(times, values, label=series, alpha=0.7)
    
    # Customize the plot
    if config.title:
        plt.title(config.title, fontsize=16, fontweight='bold')
    else:
        plt.title(f"ROS Bag Data Plot", fontsize=16, fontweight='bold')
    
    plt.xlabel("Time", fontsize=12)
    plt.ylabel("Value", fontsize=12)
    
    if config.show_grid:
        plt.grid(True, alpha=0.3)
    
    if config.show_legend and len(plot_data) > 1:
        plt.legend()
    
    # Format time axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.gca().xaxis.set_major_locator(mdates.SecondLocator(interval=60))
    plt.xticks(rotation=45)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save the plot
    plt.savefig(output_path, format=config.format, dpi=config.dpi, bbox_inches='tight')
    plt.close()
    
    return True

def _display_plot_result(result: PlotResult, console: Console):
    """Display plot operation result"""
    if not result.success:
        console.print(f"\n[bold red]Plot generation failed:[/bold red]")
        console.print(f"Error: {result.error_message}")
        raise typer.Exit(code=1)
    
    console.print(f"\n[bold green]Plot generated successfully:[/bold green]")
    console.print("─" * 80)
    
    if result.output_path:
        console.print(f"Output: [blue]{result.output_path}[/blue]")
        console.print(f"Data points: {result.data_points}")
    
    if result.time_range:
        start_time = datetime.fromtimestamp(result.time_range[0])
        end_time = datetime.fromtimestamp(result.time_range[1])
        duration = result.time_range[1] - result.time_range[0]
        
        console.print(f"Time range: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}")
        console.print(f"Duration: {duration:.2f} seconds")
    
    console.print(f"Processing time: {result.elapsed_time:.2f} seconds")

if __name__ == "__main__":
    app() 