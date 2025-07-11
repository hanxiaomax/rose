#!/usr/bin/env python3
"""
Plot command for visualizing ROS bag topic data as time series graphs
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import plotext as plt

from ..core.parser import create_parser, ParserType
from ..core.util import set_app_mode, AppMode, get_logger, log_cli_error

app = typer.Typer(help="Plot ROS bag topic data as time series graphs")


@app.command()
def plot(
    input_path: str = typer.Argument(..., help="Input bag file path"),
    topic: str = typer.Argument(..., help="Topic to plot"),
    field: Optional[str] = typer.Option(None, "--field", "-f", help="Specific field to plot (e.g., 'x', 'position.x')"),
    max_points: int = typer.Option(1000, "--max-points", "-n", help="Maximum number of points to plot (for performance)"),
    width: int = typer.Option(80, "--width", "-w", help="Plot width in characters"),
    height: int = typer.Option(20, "--height", "-h", help="Plot height in characters"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Custom plot title"),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save plot to file (HTML format)"),
    list_fields: bool = typer.Option(False, "--list-fields", "-l", help="List available fields for the topic"),
    plot_type: str = typer.Option("scatter", "--plot-type", "-p", help="Plot type: 'line' or 'scatter'"),
    marker: str = typer.Option("sd", "--marker", "-m", help="Marker style for scatter plot: 'dot', 'sd', 'hd', 'braille', etc."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output")
):
    """
    Plot time series data from a ROS bag topic as scatter plot or line plot
    
    Examples:
        # Plot all numeric fields as scatter plot (default)
        python -m roseApp.rose plot data.bag /odom
        
        # Plot specific field as scatter plot
        python -m roseApp.rose plot data.bag /odom --field pose.pose.position.x
        
        # Use line plot instead of scatter plot
        python -m roseApp.rose plot data.bag /odom --plot-type line
        
        # Use different marker styles for scatter plot
        python -m roseApp.rose plot data.bag /odom --marker dot
        
        # List available fields
        python -m roseApp.rose plot data.bag /odom --list-fields
        
        # Custom plot size and title with scatter plot
        python -m roseApp.rose plot data.bag /odom -f x -w 100 -h 30 -t "Odometry X Position"
        
        # Save plot to HTML file
        python -m roseApp.rose plot data.bag /odom --save plot.html
    """
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("plot")
        console = Console()
        
        # Validate input
        if not os.path.exists(input_path):
            typer.echo(f"Error: Input file '{input_path}' does not exist", err=True)
            raise typer.Exit(code=1)
        
        if not input_path.endswith('.bag'):
            typer.echo(f"Error: Input file '{input_path}' is not a bag file", err=True)
            raise typer.Exit(code=1)
        
        # Initialize parser
        parser = create_parser(ParserType.ROSBAGS)
        logger.debug(f"Parsing bag file: {input_path}")
        
        # Load bag information
        topics, connections, time_range = parser.load_bag(input_path)
        
        # Check if topic exists
        if topic not in topics:
            available_topics = "\n".join(f"  - {t}" for t in topics[:10])
            if len(topics) > 10:
                available_topics += f"\n  ... and {len(topics) - 10} more"
            
            typer.echo(f"Error: Topic '{topic}' not found in bag file.", err=True)
            typer.echo(f"Available topics:")
            typer.echo(available_topics)
            raise typer.Exit(code=1)
        
        # Extract messages from the topic
        console.print(f"[dim]Extracting messages from topic: {topic}[/dim]")
        
        messages_data = _extract_topic_messages(parser, input_path, topic, max_points, logger)
        
        if not messages_data:
            typer.echo(f"Error: No messages found for topic '{topic}'", err=True)
            raise typer.Exit(code=1)
        
        # Get message structure to understand available fields
        sample_msg = messages_data[0]['message']
        available_fields = _get_numeric_fields(sample_msg)
        
        if list_fields:
            _display_available_fields(console, topic, available_fields, sample_msg)
            return
        
        if not available_fields:
            typer.echo(f"Error: No numeric fields found in topic '{topic}'", err=True)
            typer.echo("Use --list-fields to see the message structure")
            raise typer.Exit(code=1)
        
        # Determine which field(s) to plot
        fields_to_plot = []
        if field:
            if field in available_fields:
                fields_to_plot = [field]
            else:
                typer.echo(f"Error: Field '{field}' not found in topic '{topic}'", err=True)
                typer.echo(f"Available numeric fields: {', '.join(available_fields)}")
                raise typer.Exit(code=1)
        else:
            # Plot all numeric fields (up to 5 for readability)
            fields_to_plot = available_fields[:5]
            if len(available_fields) > 5:
                console.print(f"[yellow]Note: Only plotting first 5 fields. Use --field to specify a single field.[/yellow]")
        
        # Create the plot
        _create_plot(
            messages_data=messages_data,
            fields_to_plot=fields_to_plot,
            topic=topic,
            width=width,
            height=height,
            title=title,
            save=save,
            plot_type=plot_type,
            marker=marker,
            verbose=verbose,
            console=console
        )
        
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _extract_topic_messages(parser, bag_path: str, topic: str, max_points: int, logger) -> List[Dict]:
    """Extract messages from a specific topic"""
    messages = []
    
    try:
        # Use the parser to get messages from the specific topic
        message_count = 0
        
        # Get topic statistics to estimate total messages
        topic_stats = parser.get_topic_stats(bag_path)
        total_messages = topic_stats.get(topic, {}).get('count', 0)
        
        # Calculate step size to sample messages evenly
        step_size = max(1, total_messages // max_points) if total_messages > max_points else 1
        
        # Read messages from the bag
        for timestamp, msg in parser.read_messages(bag_path, [topic]):
            if message_count % step_size == 0:
                # Convert timestamp to seconds since start
                time_seconds = timestamp[0] + timestamp[1] / 1_000_000_000
                
                messages.append({
                    'timestamp': time_seconds,
                    'message': msg
                })
                
                if len(messages) >= max_points:
                    break
            
            message_count += 1
        
        # Normalize timestamps to start from 0
        if messages:
            start_time = messages[0]['timestamp']
            for msg_data in messages:
                msg_data['timestamp'] -= start_time
        
        logger.debug(f"Extracted {len(messages)} messages from {total_messages} total")
        
    except Exception as e:
        logger.error(f"Error extracting messages: {e}")
        raise
    
    return messages


def _get_numeric_fields(msg: Any, prefix: str = "") -> List[str]:
    """Recursively find all numeric fields in a message"""
    fields = []
    
    try:
        if hasattr(msg, '__dict__'):
            # ROS message object
            for attr_name in dir(msg):
                if not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(msg, attr_name)
                        field_name = f"{prefix}.{attr_name}" if prefix else attr_name
                        
                        if isinstance(attr_value, (int, float)):
                            fields.append(field_name)
                        elif hasattr(attr_value, '__dict__') and not callable(attr_value):
                            # Nested object
                            fields.extend(_get_numeric_fields(attr_value, field_name))
                    except:
                        pass
        elif isinstance(msg, dict):
            # Dictionary-like message
            for key, value in msg.items():
                field_name = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, (int, float)):
                    fields.append(field_name)
                elif isinstance(value, dict):
                    fields.extend(_get_numeric_fields(value, field_name))
        elif isinstance(msg, (int, float)):
            # Single numeric value
            if prefix:
                fields.append(prefix)
    except Exception:
        # If we can't introspect the message, return empty list
        pass
    
    return fields


def _get_field_value(msg: Any, field_path: str) -> Optional[float]:
    """Get value from a nested field path like 'pose.position.x'"""
    try:
        parts = field_path.split('.')
        current = msg
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        if isinstance(current, (int, float)):
            return float(current)
        
    except Exception:
        pass
    
    return None


def _display_available_fields(console: Console, topic: str, fields: List[str], sample_msg: Any):
    """Display available fields in a nice format"""
    console.print(f"\n[bold cyan]Available numeric fields for topic: {topic}[/bold cyan]")
    
    if not fields:
        console.print("[yellow]No numeric fields found in this topic[/yellow]")
        
        # Try to show message structure
        console.print(f"\n[dim]Sample message structure:[/dim]")
        try:
            if hasattr(sample_msg, '__str__'):
                msg_str = str(sample_msg)[:500]
                if len(str(sample_msg)) > 500:
                    msg_str += "..."
                console.print(f"[dim]{msg_str}[/dim]")
        except:
            console.print("[dim]Unable to display message structure[/dim]")
        return
    
    # Group fields by their parent
    field_groups = {}
    for field in fields:
        if '.' in field:
            parent = field.split('.')[0]
            field_groups.setdefault(parent, []).append(field)
        else:
            field_groups.setdefault('root', []).append(field)
    
    for group, group_fields in field_groups.items():
        if group == 'root':
            console.print(f"[green]Root fields:[/green]")
        else:
            console.print(f"[green]{group}.*:[/green]")
        
        for field in sorted(group_fields):
            # Show sample value
            sample_value = _get_field_value(sample_msg, field)
            value_str = f" (sample: {sample_value})" if sample_value is not None else ""
            console.print(f"  [cyan]{field}[/cyan]{value_str}")
        
        console.print()


def _create_plot(
    messages_data: List[Dict],
    fields_to_plot: List[str],
    topic: str,
    width: int,
    height: int,
    title: Optional[str],
    save: Optional[str],
    plot_type: str,
    marker: str,
    verbose: bool,
    console: Console
):
    """Create and display the plot"""
    
    # Set plot size
    plt.plotsize(width, height)
    
    # Extract time series data
    times = [msg['timestamp'] for msg in messages_data]
    
    if verbose:
        console.print(f"[dim]Plotting {len(messages_data)} data points[/dim]")
        console.print(f"[dim]Time range: {times[0]:.2f}s to {times[-1]:.2f}s[/dim]")
    
    # Plot each field
    colors = ['red', 'blue', 'green', 'yellow', 'magenta', 'cyan']
    
    for i, field in enumerate(fields_to_plot):
        values = []
        for msg_data in messages_data:
            value = _get_field_value(msg_data['message'], field)
            if value is not None:
                values.append(value)
            else:
                values.append(float('nan'))  # Handle missing values
        
        # Remove NaN values for plotting
        clean_times = []
        clean_values = []
        for t, v in zip(times, values):
            if not (isinstance(v, float) and v != v):  # Check for NaN
                clean_times.append(t)
                clean_values.append(v)
        
        if clean_values:
            color = colors[i % len(colors)]
            
            if plot_type == "scatter":
                plt.scatter(clean_times, clean_values, label=field, color=color, marker=marker)
            else:
                plt.plot(clean_times, clean_values, label=field, color=color)
            
            if verbose:
                min_val, max_val = min(clean_values), max(clean_values)
                console.print(f"[dim]{field}: {len(clean_values)} points, range [{min_val:.3f}, {max_val:.3f}][/dim]")
    
    # Set labels and title
    plt.xlabel("Time (seconds)")
    if len(fields_to_plot) == 1:
        plt.ylabel(fields_to_plot[0])
    else:
        plt.ylabel("Value")
    
    plot_title = title or f"Topic: {topic}"
    plt.title(plot_title)
    
    # Note: plotext may not support legends, so we skip legend functionality
    
    # Save to file if requested
    if save:
        try:
            plt.savefig(save)
            console.print(f"[green]Plot saved to: {save}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving plot: {e}[/red]")
    
    # Display the plot
    plot_type_str = "Scatter Plot" if plot_type == "scatter" else "Line Plot"
    console.print(f"\n[bold green]Time Series {plot_type_str} for {topic}[/bold green]")
    plt.show()


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 