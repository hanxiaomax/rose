#!/usr/bin/env python3
"""
Plot command for ROS bag data visualization - Refactored to align with extract.py and inspect.py patterns
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import typer
from rich.console import Console

# Import unified theme system and UI control
from ..core.bag_manager import BagManager, InspectOptions
from ..core.ui_control import UIControl, OutputFormat, RenderOptions, ExportOptions, UITheme, DisplayConfig
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.parser import create_parser, ParserType

# Import plotting dependencies (will be checked at runtime)
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.offline as pyo
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Set to CLI mode
set_app_mode(AppMode.CLI)
logger = get_logger(__name__)

app = typer.Typer(name="plot", help="Generate data visualization plots from ROS bag files")
console = Console()

def await_sync(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

class PlotValidationError(Exception):
    """Exception raised for plotting-related validation errors"""
    pass

def check_plotting_dependencies():
    """Check if plotting dependencies are available"""
    missing = []
    if not MATPLOTLIB_AVAILABLE:
        missing.append("matplotlib")
    if not PLOTLY_AVAILABLE:
        missing.append("plotly")
    if not PANDAS_AVAILABLE:
        missing.append("pandas")
    
    if missing:
        missing_str = ", ".join(missing)
        install_cmd = f"pip install {' '.join(missing)}"
        error_msg = f"Missing plotting dependencies: {missing_str}. Install with: {install_cmd}"
        raise PlotValidationError(error_msg)

@app.command("plot")
def plot_cmd(
    bag_path: str = typer.Argument(..., help="Input bag file path"),
    series: List[str] = typer.Option(..., "--series", "-s", help="Plot series in format topic:field1,field2 (can be repeated)"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    plot_type: str = typer.Option("line", "--type", "-t", help="Plot type: line, scatter (default: line)"),
    as_format: str = typer.Option("png", "--as", "-a", help="Output format: png, svg, pdf, html (default: png)"),
    theme_mode: str = typer.Option("auto", "--theme", help="Theme mode: auto, light, dark (default: auto)")
):
    """
    Generate data visualization plots from ROS bag files
    
    The --series parameter specifies what data to plot in the format:
    topic:field1,field2,...
    
    Examples:
    
    # Plot single field from one topic
    rose plot demo.bag --series /odom:pose.pose.position.x --output pos_x.png
    
    # Plot multiple fields from one topic  
    rose plot demo.bag --series /odom:pose.pose.position.x,pose.pose.position.y --output pos_xy.png
    
    # Plot all numeric fields from a topic
    rose plot demo.bag --series /odom: --output odom_all.png
    
    # Compare multiple topics
    rose plot demo.bag --series /odom:pose.pose.position.x --series /tf:transform.translation.x --output comparison.png
    
    # Generate scatter plot
    rose plot demo.bag --series /odom:pose.pose.position.x,pose.pose.position.y --type scatter --output scatter.png
    
    # Generate interactive HTML plot
    rose plot demo.bag --series /odom:pose.pose.position.x --as html --output interactive.html
    """
    _plot_cmd_impl(bag_path, series, output, plot_type, as_format, theme_mode)

@app.command("frequency")
def frequency_plot(
    bag_path: str = typer.Argument(..., help="Input bag file path"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    as_format: str = typer.Option("png", "--as", "-a", help="Output format: png, svg, pdf, html (default: png)"),
    theme_mode: str = typer.Option("auto", "--theme", help="Theme mode: auto, light, dark (default: auto)")
):
    """Create frequency bar plot for topics"""
    _create_overview_plot(bag_path, "frequency", output, as_format, theme_mode)

@app.command("size")
def size_plot(
    bag_path: str = typer.Argument(..., help="Input bag file path"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    as_format: str = typer.Option("png", "--as", "-a", help="Output format: png, svg, pdf, html (default: png)"),
    theme_mode: str = typer.Option("auto", "--theme", help="Theme mode: auto, light, dark (default: auto)")
):
    """Create size distribution plot for topics"""
    _create_overview_plot(bag_path, "size", output, as_format, theme_mode)

@app.command("count")
def count_plot(
    bag_path: str = typer.Argument(..., help="Input bag file path"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    as_format: str = typer.Option("png", "--as", "-a", help="Output format: png, svg, pdf, html (default: png)"),
    theme_mode: str = typer.Option("auto", "--theme", help="Theme mode: auto, light, dark (default: auto)")
):
    """Create message count plot for topics"""
    _create_overview_plot(bag_path, "count", output, as_format, theme_mode)

@app.command("overview")
def overview_plot(
    bag_path: str = typer.Argument(..., help="Input bag file path"),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
    as_format: str = typer.Option("png", "--as", "-a", help="Output format: png, svg, pdf, html (default: png)"),
    theme_mode: str = typer.Option("auto", "--theme", help="Theme mode: auto, light, dark (default: auto)")
):
    """Create overview plot with multiple metrics"""
    _create_overview_plot(bag_path, "overview", output, as_format, theme_mode)

def _plot_cmd_impl(
    bag_path: str,
    series: List[str],
    output: str,
    plot_type: str,
    as_format: str,
    theme_mode: str
):
    """Implementation of plot command using unified patterns"""
    try:
        # Validate dependencies
        check_plotting_dependencies()
        
        # Validate input file
        input_path = Path(bag_path)
        if not input_path.exists():
            console.print(f"[red]Error: Input bag file not found: {bag_path}[/red]")
            raise typer.Exit(1)
        
        # Validate output path
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate format
        valid_formats = ["png", "svg", "pdf", "html"]
        if as_format not in valid_formats:
            console.print(f"[red]Error: Invalid format '{as_format}'. Valid options: {', '.join(valid_formats)}[/red]")
            raise typer.Exit(1)
        
        # Validate plot type
        valid_types = ["line", "scatter"]
        if plot_type not in valid_types:
            console.print(f"[red]Error: Invalid plot type '{plot_type}'. Valid options: {', '.join(valid_types)}[/red]")
            raise typer.Exit(1)
        
        # Parse series specifications
        parsed_series = []
        for s in series:
            if ':' not in s:
                console.print(f"[red]Error: Invalid series format '{s}'. Use format: topic:field1,field2[/red]")
                raise typer.Exit(1)
            
            topic, fields_str = s.split(':', 1)
            
            # Parse fields - empty string means all numeric fields
            if fields_str.strip():
                fields = [f.strip() for f in fields_str.split(',')]
            else:
                fields = []  # Empty means all numeric fields
            
            parsed_series.append({
                'topic': topic,
                'fields': fields
            })
        
        # Run the async plotting
        await_sync(_run_plot(input_path, parsed_series, output_path, plot_type, as_format, theme_mode))
        
    except Exception as e:
        console.print(f"[red]Error during plotting: {e}[/red]")
        logger.error(f"Plotting error: {e}", exc_info=True)
        raise typer.Exit(1)

def _create_overview_plot(
    bag_path: str,
    plot_type: str,
    output: str,
    as_format: str,
    theme_mode: str
):
    """Create overview plots using BagManager patterns"""
    try:
        # Validate dependencies
        check_plotting_dependencies()
        
        # Validate input file
        input_path = Path(bag_path)
        if not input_path.exists():
            console.print(f"[red]Error: Input bag file not found: {bag_path}[/red]")
            raise typer.Exit(1)
        
        # Validate output path
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate format
        valid_formats = ["png", "svg", "pdf", "html"]
        if as_format not in valid_formats:
            console.print(f"[red]Error: Invalid format '{as_format}'. Valid options: {', '.join(valid_formats)}[/red]")
            raise typer.Exit(1)
        
        # Configure theme
        UIControl.set_theme_mode(theme_mode)
        
        # Run the async plotting
        await_sync(_run_overview_plot(input_path, plot_type, output_path, as_format))
        
    except Exception as e:
        console.print(f"[red]Error during plotting: {e}[/red]")
        logger.error(f"Plotting error: {e}", exc_info=True)
        raise typer.Exit(1)

async def _run_plot(
    input_path: Path,
    parsed_series: List[Dict],
    output_path: Path,
    plot_type: str,
    as_format: str,
    theme_mode: str
):
    """Run the actual plotting with async processing"""
    
    # Configure theme
    UIControl.set_theme_mode(theme_mode)
    
    # Create BagManager
    manager = BagManager()
    
    try:
        # Show analysis progress
        with UIControl.todo_analysis_progress(input_path.name, False, console) as analysis_update:
            bag_info = await manager.inspect_bag(input_path, progress_callback=analysis_update)
        
        # Extract time series data with progress tracking
        console.print("[cyan]Extracting time series data...[/cyan]")
        
        time_series_data = {}
        
        # Use UIControl for progress tracking
        with UIControl.todo_extraction_progress(
            input_path.name,
            "Extracting data for plotting",
            console
        ) as update_progress:
            
            parser = create_parser(ParserType.ROSBAGS)
            topics, connections, time_range = parser.load_bag(str(input_path))
            
            available_topics = set(topics)
            
            total_series = len(parsed_series)
            processed_series = 0
            
            for series_idx, series in enumerate(parsed_series):
                topic = series['topic']
                fields = series['fields']
                
                if topic not in available_topics:
                    console.print(f"[yellow]Warning: Topic '{topic}' not found in bag file[/yellow]")
                    continue
                
                update_progress(
                    topic=f"Processing topic: {topic}",
                    progress=(series_idx / total_series) * 100,
                    topics_total=total_series,
                    topics_processed=series_idx
                )
                
                # Extract data for this topic
                messages = parser.read_messages(str(input_path), [topic])
                
                topic_data = {
                    'topic': topic,
                    'fields': fields,
                    'timestamps': [],
                    'data': {}
                }
                
                # Initialize field data containers
                if fields:
                    for field in fields:
                        topic_data['data'][field] = []
                
                # Process messages
                message_count = 0
                for msg_timestamp, msg_data in messages:
                    # Convert timestamp
                    if isinstance(msg_timestamp, tuple):
                        timestamp = msg_timestamp[0] + msg_timestamp[1] / 1_000_000_000
                    else:
                        timestamp = float(msg_timestamp)
                    
                    topic_data['timestamps'].append(timestamp)
                    
                    # Extract field data
                    if fields:
                        for field in fields:
                            value = _extract_field_value(msg_data, field)
                            topic_data['data'][field].append(value)
                    else:
                        # Extract all numeric fields
                        numeric_fields = _extract_numeric_fields(msg_data)
                        for field_name, value in numeric_fields.items():
                            if field_name not in topic_data['data']:
                                topic_data['data'][field_name] = []
                            topic_data['data'][field_name].append(value)
                    
                    message_count += 1
                
                processed_series += 1
                update_progress(
                    topic=f"Completed {topic} ({message_count} messages)",
                    progress=(processed_series / total_series) * 100,
                    topics_total=total_series,
                    topics_processed=processed_series
                )
                
                time_series_data[topic] = topic_data
        
        # Create the plot
        console.print(f"[cyan]Creating {plot_type} plot...[/cyan]")
        _create_time_series_plot(time_series_data, str(output_path), plot_type, as_format, console)
        
        console.print(f"[green]✓ Plot saved to: {output_path}[/green]")
        
    finally:
        manager.cleanup()

async def _run_overview_plot(
    input_path: Path,
    plot_type: str,
    output_path: Path,
    as_format: str
):
    """Run overview plot creation with async processing"""
    
    # Create BagManager
    manager = BagManager()
    
    try:
        # Show analysis progress
        with UIControl.todo_analysis_progress(input_path.name, True, console) as analysis_update:
            bag_info = await manager.inspect_bag(
                input_path, 
                InspectOptions(verbose=True),
                progress_callback=analysis_update
            )
        
        # Create overview plot
        console.print(f"[cyan]Creating {plot_type} overview plot...[/cyan]")
        
        # Convert bag_info to expected format
        plot_data = {
            'topics': [],
            'summary': {
                'file_name': input_path.name,
                'topic_count': len(bag_info.get('topics', [])),
                'total_messages': sum(t.get('message_count', 0) for t in bag_info.get('topics', [])),
                'file_size_formatted': _format_bytes(input_path.stat().st_size),
                'duration_formatted': _format_duration(
                    bag_info.get('bag_info', {}).get('duration', 0)
                ),
                'avg_rate_formatted': f"{bag_info.get('bag_info', {}).get('avg_rate', 0):.1f} Hz"
            }
        }
        
        # Build topics data
        for topic in bag_info.get('topics', []):
            plot_data['topics'].append({
                'topic': topic['name'],
                'count': topic.get('message_count', 0),
                'size': topic.get('estimated_size_bytes', 0),
                'frequency': topic.get('frequency', 0)
            })
        
        # Create the plot
        _create_plot(plot_data, plot_type, str(output_path), as_format)
        
        console.print(f"[green]✓ {plot_type.title()} plot saved to: {output_path}[/green]")
        
    finally:
        manager.cleanup()

def _format_bytes(bytes_val):
    """Format bytes value for display"""
    if bytes_val == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def _format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def _extract_field_value(msg_data: Any, field_path: str) -> float:
    """Extract a numeric value from a message using dot notation field path"""
    try:
        # Handle nested field access like "pose.pose.position.x"
        value = msg_data
        for field_name in field_path.split('.'):
            if hasattr(value, field_name):
                value = getattr(value, field_name)
            elif isinstance(value, dict) and field_name in value:
                value = value[field_name]
            else:
                return 0.0
        
        # Convert to float if possible
        if isinstance(value, (int, float)):
            return float(value)
        else:
            return 0.0
    except Exception:
        return 0.0

def _extract_numeric_fields(msg_data: Any, prefix: str = "", max_depth: int = 3) -> Dict[str, float]:
    """Extract all numeric fields from a message"""
    numeric_fields = {}
    
    if max_depth <= 0:
        return numeric_fields
    
    try:
        # Handle different message types
        if hasattr(msg_data, '__dict__'):
            # ROS message object
            for field_name in dir(msg_data):
                if field_name.startswith('_'):
                    continue
                    
                field_value = getattr(msg_data, field_name)
                full_name = f"{prefix}.{field_name}" if prefix else field_name
                
                if isinstance(field_value, (int, float)):
                    numeric_fields[full_name] = float(field_value)
                elif hasattr(field_value, '__dict__'):
                    # Nested object
                    nested_fields = _extract_numeric_fields(field_value, full_name, max_depth - 1)
                    numeric_fields.update(nested_fields)
        
        elif isinstance(msg_data, dict):
            # Dictionary
            for field_name, field_value in msg_data.items():
                full_name = f"{prefix}.{field_name}" if prefix else field_name
                
                if isinstance(field_value, (int, float)):
                    numeric_fields[full_name] = float(field_value)
                elif isinstance(field_value, dict):
                    nested_fields = _extract_numeric_fields(field_value, full_name, max_depth - 1)
                    numeric_fields.update(nested_fields)
    
    except Exception:
        pass
    
    return numeric_fields

def _create_time_series_plot(time_series_data: Dict[str, Any], output_path: str, plot_type: str, plot_format: str, console: Console):
    """Create time series plot using matplotlib or plotly"""
    import datetime
    
    if plot_format == "html":
        _create_time_series_plot_plotly(time_series_data, output_path, plot_type, console)
    else:
        _create_time_series_plot_matplotlib(time_series_data, output_path, plot_type, plot_format, console)

def _create_time_series_plot_matplotlib(time_series_data: Dict[str, Any], output_path: str, plot_type: str, plot_format: str, console: Console):
    """Create time series plot using matplotlib"""
    if not MATPLOTLIB_AVAILABLE:
        raise PlotValidationError("Missing matplotlib. Install with: pip install matplotlib")
    
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime, timezone
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot each topic's data
    for topic, data in time_series_data.items():
        timestamps = data['timestamps']
        
        # Convert timestamps to datetime objects
        datetime_stamps = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]
        
        # Plot each field
        for field_name, field_data in data['data'].items():
            if len(field_data) != len(datetime_stamps):
                continue
                
            label = f"{topic}:{field_name}"
            
            if plot_type == "scatter":
                ax.scatter(datetime_stamps, field_data, label=label, alpha=0.6)
            else:  # line plot
                ax.plot(datetime_stamps, field_data, label=label, linewidth=1.5)
    
    # Customize plot
    ax.set_xlabel('Time')
    ax.set_ylabel('Value')
    ax.set_title('Time Series Plot')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.SecondLocator(interval=60))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save plot
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()

def _create_time_series_plot_plotly(time_series_data: Dict[str, Any], output_path: str, plot_type: str, console: Console):
    """Create time series plot using plotly"""
    if not PLOTLY_AVAILABLE:
        raise PlotValidationError("Missing plotly. Install with: pip install plotly")
    
    import plotly.graph_objects as go
    from datetime import datetime, timezone
    
    # Create figure
    fig = go.Figure()
    
    # Plot each topic's data
    for topic, data in time_series_data.items():
        timestamps = data['timestamps']
        
        # Convert timestamps to datetime objects
        datetime_stamps = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]
        
        # Plot each field
        for field_name, field_data in data['data'].items():
            if len(field_data) != len(datetime_stamps):
                continue
                
            name = f"{topic}:{field_name}"
            
            if plot_type == "scatter":
                fig.add_trace(go.Scatter(
                    x=datetime_stamps,
                    y=field_data,
                    mode='markers',
                    name=name,
                    opacity=0.6
                ))
            else:  # line plot
                fig.add_trace(go.Scatter(
                    x=datetime_stamps,
                    y=field_data,
                    mode='lines',
                    name=name,
                    line=dict(width=2)
                ))
    
    # Customize layout
    fig.update_layout(
        title='Time Series Plot',
        xaxis_title='Time',
        yaxis_title='Value',
        hovermode='x unified',
        showlegend=True,
        width=1200,
        height=600
    )
    
    # Save plot
    fig.write_html(output_path)

def _create_plot(json_data: Dict[str, Any], plot_type: str, output_path: str, plot_format: str):
    """Create plot based on type using legacy format"""
    plot_functions = {
        'frequency': _create_frequency_plot,
        'size': _create_size_plot,
        'count': _create_count_plot,
        'overview': _create_overview_plot_legacy
    }
    
    if plot_type not in plot_functions:
        raise PlotValidationError(f"Unknown plot type: {plot_type}. Available types: {', '.join(plot_functions.keys())}")
    
    return plot_functions[plot_type](json_data, output_path, plot_format)

def _create_frequency_plot(json_data: Dict[str, Any], output_path: str, plot_format: str):
    """Create frequency plot"""
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with frequency data
    topics_with_freq = [t for t in topics_data if t.get('frequency') is not None]
    
    if not topics_with_freq:
        raise PlotValidationError("No frequency data available. Use --verbose to analyze message frequencies.")
    
    # Sort by frequency
    topics_with_freq.sort(key=lambda x: x['frequency'], reverse=True)
    
    if plot_format == "html":
        return _create_frequency_plot_plotly(topics_with_freq, summary, output_path)
    else:
        return _create_frequency_plot_matplotlib(topics_with_freq, summary, output_path, plot_format)

def _create_size_plot(json_data: Dict[str, Any], output_path: str, plot_format: str):
    """Create size plot"""
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with size data
    topics_with_size = [t for t in topics_data if t.get('size') is not None and t.get('size') > 0]
    
    if not topics_with_size:
        raise PlotValidationError("No size data available. Use --verbose to analyze message sizes.")
    
    # Sort by size
    topics_with_size.sort(key=lambda x: x['size'], reverse=True)
    
    if plot_format == "html":
        return _create_size_plot_plotly(topics_with_size, summary, output_path)
    else:
        return _create_size_plot_matplotlib(topics_with_size, summary, output_path, plot_format)

def _create_count_plot(json_data: Dict[str, Any], output_path: str, plot_format: str):
    """Create count plot"""
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with count data
    topics_with_count = [t for t in topics_data if t.get('count') is not None and t.get('count') > 0]
    
    if not topics_with_count:
        raise PlotValidationError("No message count data available. Use --verbose to analyze message counts.")
    
    # Sort by count
    topics_with_count.sort(key=lambda x: x['count'], reverse=True)
    
    if plot_format == "html":
        return _create_count_plot_plotly(topics_with_count, summary, output_path)
    else:
        return _create_count_plot_matplotlib(topics_with_count, summary, output_path, plot_format)

def _create_overview_plot_legacy(json_data: Dict[str, Any], output_path: str, plot_format: str):
    """Create overview plot"""
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with complete data
    complete_topics = [t for t in topics_data if 
                      t.get('count') is not None and 
                      t.get('size') is not None and 
                      t.get('frequency') is not None and
                      t.get('count') > 0]
    
    if not complete_topics:
        raise PlotValidationError("No complete data available. Use --verbose to analyze all metrics.")
    
    # Sort by total size
    complete_topics.sort(key=lambda x: x['size'], reverse=True)
    
    if plot_format == "html":
        return _create_overview_plot_plotly(complete_topics, summary, output_path)
    else:
        return _create_overview_plot_matplotlib(complete_topics, summary, output_path, plot_format)

# Legacy plot creation functions (simplified for compatibility)
def _create_frequency_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create frequency plot using matplotlib"""
    if not MATPLOTLIB_AVAILABLE:
        raise PlotValidationError("Missing matplotlib")
    
    import matplotlib.pyplot as plt
    
    topics = [t['topic'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), frequencies, alpha=0.8)
    
    ax.set_xlabel('Topics')
    ax.set_ylabel('Frequency (Hz)')
    ax.set_title(f'Topic Message Frequencies - {summary["file_name"]}')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, freq in zip(bars, frequencies):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{freq:.1f}', ha='center', va='bottom')
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path

def _create_size_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create size plot using matplotlib"""
    if not MATPLOTLIB_AVAILABLE:
        raise PlotValidationError("Missing matplotlib")
    
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    
    topics = [t['topic'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), sizes, alpha=0.8)
    
    ax.set_xlabel('Topics')
    ax.set_ylabel('Total Size (Bytes)')
    ax.set_title(f'Topic Message Sizes - {summary["file_name"]}')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Format y-axis to show human readable sizes
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: _format_bytes(x)))
    
    # Add value labels on bars
    for bar, size in zip(bars, sizes):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                _format_bytes(size), ha='center', va='bottom')
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path

def _create_count_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create count plot using matplotlib"""
    if not MATPLOTLIB_AVAILABLE:
        raise PlotValidationError("Missing matplotlib")
    
    import matplotlib.pyplot as plt
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), counts, alpha=0.8)
    
    ax.set_xlabel('Topics')
    ax.set_ylabel('Message Count')
    ax.set_title(f'Topic Message Counts - {summary["file_name"]}')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{count:,}', ha='center', va='bottom')
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path

def _create_overview_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create overview plot using matplotlib"""
    if not MATPLOTLIB_AVAILABLE:
        raise PlotValidationError("Missing matplotlib")
    
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:25] + "..." if len(t) > 25 else t for t in topics]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Message counts
    bars1 = ax1.bar(range(len(topics)), counts, alpha=0.8)
    ax1.set_title('Message Counts')
    ax1.set_ylabel('Count')
    ax1.set_xticks(range(len(topics)))
    ax1.set_xticklabels(display_topics, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3)
    
    # Sizes
    bars2 = ax2.bar(range(len(topics)), sizes, alpha=0.8)
    ax2.set_title('Total Sizes')
    ax2.set_ylabel('Size (Bytes)')
    ax2.set_xticks(range(len(topics)))
    ax2.set_xticklabels(display_topics, rotation=45, ha='right')
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: _format_bytes(x)))
    ax2.grid(True, alpha=0.3)
    
    # Frequencies
    bars3 = ax3.bar(range(len(topics)), frequencies, alpha=0.8)
    ax3.set_title('Frequencies')
    ax3.set_ylabel('Frequency (Hz)')
    ax3.set_xticks(range(len(topics)))
    ax3.set_xticklabels(display_topics, rotation=45, ha='right')
    ax3.grid(True, alpha=0.3)
    
    # Summary stats
    ax4.axis('off')
    stats_text = f"""
Bag File: {summary['file_name']}
Total Topics: {summary['topic_count']}
Total Messages: {summary['total_messages']:,}
File Size: {summary['file_size_formatted']}
Duration: {summary['duration_formatted']}
Avg Rate: {summary['avg_rate_formatted']}
    """.strip()
    ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes, fontsize=12,
             verticalalignment='center', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax4.set_title('Summary Statistics')
    
    plt.suptitle(f'ROS Bag Overview - {summary["file_name"]}')
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path

# Plotly functions

def _create_frequency_plot_plotly(topics_data, summary, output_path):
    """Create frequency plot using plotly"""
    if not PLOTLY_AVAILABLE:
        raise PlotValidationError("Missing plotly")
    
    import plotly.graph_objects as go
    
    topics = [t['topic'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=frequencies,
            text=[f'{f:.1f} Hz' for f in frequencies],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Frequency: %{y:.1f} Hz<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title=f'Topic Message Frequencies - {summary["file_name"]}',
        xaxis_title='Topics',
        yaxis_title='Frequency (Hz)',
        xaxis_tickangle=-45,
        showlegend=False
    )
    
    import plotly.offline as pyo
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path

def _create_size_plot_plotly(topics_data, summary, output_path):
    """Create size plot using plotly"""
    if not PLOTLY_AVAILABLE:
        raise PlotValidationError("Missing plotly")
    
    import plotly.graph_objects as go
    
    topics = [t['topic'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    size_labels = [_format_bytes(s) for s in sizes]
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=sizes,
            text=size_labels,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Size: %{text}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title=f'Topic Message Sizes - {summary["file_name"]}',
        xaxis_title='Topics',
        yaxis_title='Total Size (Bytes)',
        xaxis_tickangle=-45,
        showlegend=False
    )
    
    # Format y-axis
    fig.update_yaxis(tickformat='.2s')
    
    import plotly.offline as pyo
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path

def _create_count_plot_plotly(topics_data, summary, output_path):
    """Create count plot using plotly"""
    if not PLOTLY_AVAILABLE:
        raise PlotValidationError("Missing plotly")
    
    import plotly.graph_objects as go
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=counts,
            text=[f'{c:,}' for c in counts],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title=f'Topic Message Counts - {summary["file_name"]}',
        xaxis_title='Topics',
        yaxis_title='Message Count',
        xaxis_tickangle=-45,
        showlegend=False
    )
    
    import plotly.offline as pyo
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path

def _create_overview_plot_plotly(topics_data, summary, output_path):
    """Create overview plot using plotly"""
    if not PLOTLY_AVAILABLE:
        raise PlotValidationError("Missing plotly")
    
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Message Counts', 'Total Sizes', 'Frequencies', 'Summary'),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "table"}]]
    )
    
    # Message counts
    fig.add_trace(
        go.Bar(x=topics, y=counts, name='Count'),
        row=1, col=1
    )
    
    # Sizes
    fig.add_trace(
        go.Bar(x=topics, y=sizes, name='Size'),
        row=1, col=2
    )
    
    # Frequencies
    fig.add_trace(
        go.Bar(x=topics, y=frequencies, name='Frequency'),
        row=2, col=1
    )
    
    # Summary table
    fig.add_trace(
        go.Table(
            header=dict(values=['Metric', 'Value']),
            cells=dict(values=[
                ['File', 'Topics', 'Messages', 'File Size', 'Duration', 'Avg Rate'],
                [
                    summary['file_name'], 
                    summary['topic_count'], 
                    f"{summary['total_messages']:,}",
                    summary['file_size_formatted'], 
                    summary['duration_formatted'], 
                    summary['avg_rate_formatted']
                ]
            ])
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        title=f"ROS Bag Overview - {summary['file_name']}",
        showlegend=False,
        height=800
    )
    
    # Update x-axes for better readability
    fig.update_xaxes(tickangle=-45, row=1, col=1)
    fig.update_xaxes(tickangle=-45, row=1, col=2)
    fig.update_xaxes(tickangle=-45, row=2, col=1)
    
    import plotly.offline as pyo
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path

# Register plot as the default command with empty name
app.command(name="")(plot_cmd)

if __name__ == "__main__":
    app()