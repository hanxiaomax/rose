#!/usr/bin/env python3
"""
Plotting utilities for ROS bag visualization
Uses index.css based theme system for consistent styling
"""

import os
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Import unified theme system
from ..core.theme import theme

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


class PlottingError(Exception):
    """Exception raised for plotting-related errors"""
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
        raise PlottingError(
            f"Missing plotting dependencies: {missing_str}\n"
            f"Install with: pip install 'rose-bag[plot]' or pip install {' '.join(missing)}"
        )


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


def create_frequency_plot(json_data: Dict[str, Any], output_path: str, plot_format: str = "png"):
    """Create frequency bar plot for topics"""
    check_plotting_dependencies()
    
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with frequency data
    topics_with_freq = [t for t in topics_data if t['frequency'] is not None]
    
    if not topics_with_freq:
        raise PlottingError("No frequency data available. Use --verbose to analyze message frequencies.")
    
    # Sort by frequency
    topics_with_freq.sort(key=lambda x: x['frequency'], reverse=True)
    
    if plot_format == "html":
        return _create_frequency_plot_plotly(topics_with_freq, summary, output_path)
    else:
        return _create_frequency_plot_matplotlib(topics_with_freq, summary, output_path, plot_format)


def _create_frequency_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create frequency plot using matplotlib with theme"""
    # Apply theme
    theme.apply_matplotlib_style()
    
    topics = [t['topic'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), frequencies, color=theme.get_plot_color(0), alpha=0.8)
    
    ax.set_xlabel('Topics', fontsize=12)
    ax.set_ylabel('Frequency (Hz)', fontsize=12)
    ax.set_title(f'Topic Message Frequencies - {summary["file_name"]}', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, freq in zip(bars, frequencies):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + max(frequencies)*0.01,
                f'{freq:.1f}', ha='center', va='bottom', color=theme.TEXT_PRIMARY, fontsize=10)
    
    # Customize grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path


def _create_frequency_plot_plotly(topics_data, summary, output_path):
    """Create frequency plot using plotly with theme"""
    topics = [t['topic'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Apply theme template
    template = theme.get_plotly_template()
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=frequencies,
            marker_color=theme.get_plot_color(0),
            text=[f'{f:.1f} Hz' for f in frequencies],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Frequency: %{y:.1f} Hz<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title={
            'text': f'Topic Message Frequencies - {summary["file_name"]}',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis_title='Topics',
        yaxis_title='Frequency (Hz)',
        xaxis_tickangle=-45,
        showlegend=False,
        **template['layout']
    )
    
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path


def create_size_distribution_plot(json_data: Dict[str, Any], output_path: str, plot_format: str = "png"):
    """Create size distribution plot for topics"""
    check_plotting_dependencies()
    
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with size data
    topics_with_size = [t for t in topics_data if t['size'] is not None and t['size'] > 0]
    
    if not topics_with_size:
        raise PlottingError("No size data available. Use --verbose to analyze message sizes.")
    
    # Sort by size
    topics_with_size.sort(key=lambda x: x['size'], reverse=True)
    
    if plot_format == "html":
        return _create_size_plot_plotly(topics_with_size, summary, output_path)
    else:
        return _create_size_plot_matplotlib(topics_with_size, summary, output_path, plot_format)


def _create_size_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create size distribution plot using matplotlib with theme"""
    # Apply theme
    theme.apply_matplotlib_style()
    
    topics = [t['topic'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), sizes, color=theme.get_plot_color(2), alpha=0.8)
    
    ax.set_xlabel('Topics', fontsize=12)
    ax.set_ylabel('Total Size (Bytes)', fontsize=12)
    ax.set_title(f'Topic Message Sizes - {summary["file_name"]}', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Format y-axis to show human readable sizes
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: _format_bytes(x)))
    
    # Add value labels on bars
    for bar, size in zip(bars, sizes):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + max(sizes)*0.01,
                _format_bytes(size), ha='center', va='bottom', color=theme.TEXT_PRIMARY, fontsize=10)
    
    # Customize grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path


def _create_size_plot_plotly(topics_data, summary, output_path):
    """Create size distribution plot using plotly with theme"""
    topics = [t['topic'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    size_labels = [_format_bytes(s) for s in sizes]
    
    # Apply theme template
    template = theme.get_plotly_template()
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=sizes,
            marker_color=theme.get_plot_color(2),
            text=size_labels,
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Size: %{text}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title={
            'text': f'Topic Message Sizes - {summary["file_name"]}',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis_title='Topics',
        yaxis_title='Total Size (Bytes)',
        xaxis_tickangle=-45,
        showlegend=False,
        **template['layout']
    )
    
    # Format y-axis
    fig.update_yaxis(tickformat='.2s')
    
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path


def create_message_count_plot(json_data: Dict[str, Any], output_path: str, plot_format: str = "png"):
    """Create message count plot for topics"""
    check_plotting_dependencies()
    
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with count data
    topics_with_count = [t for t in topics_data if t['count'] is not None and t['count'] > 0]
    
    if not topics_with_count:
        raise PlottingError("No message count data available. Use --verbose to analyze message counts.")
    
    # Sort by count
    topics_with_count.sort(key=lambda x: x['count'], reverse=True)
    
    if plot_format == "html":
        return _create_count_plot_plotly(topics_with_count, summary, output_path)
    else:
        return _create_count_plot_matplotlib(topics_with_count, summary, output_path, plot_format)


def _create_count_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create message count plot using matplotlib with theme"""
    # Apply theme
    theme.apply_matplotlib_style()
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:30] + "..." if len(t) > 30 else t for t in topics]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.bar(range(len(topics)), counts, color=theme.get_plot_color(3), alpha=0.8)
    
    ax.set_xlabel('Topics', fontsize=12)
    ax.set_ylabel('Message Count', fontsize=12)
    ax.set_title(f'Topic Message Counts - {summary["file_name"]}', fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(topics)))
    ax.set_xticklabels(display_topics, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + max(counts)*0.01,
                f'{count:,}', ha='center', va='bottom', color=theme.TEXT_PRIMARY, fontsize=10)
    
    # Customize grid
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path


def _create_count_plot_plotly(topics_data, summary, output_path):
    """Create message count plot using plotly with theme"""
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    
    # Apply theme template
    template = theme.get_plotly_template()
    
    fig = go.Figure(data=[
        go.Bar(
            x=topics,
            y=counts,
            marker_color=theme.get_plot_color(3),
            text=[f'{c:,}' for c in counts],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title={
            'text': f'Topic Message Counts - {summary["file_name"]}',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis_title='Topics',
        yaxis_title='Message Count',
        xaxis_tickangle=-45,
        showlegend=False,
        **template['layout']
    )
    
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path


def create_overview_plot(json_data: Dict[str, Any], output_path: str, plot_format: str = "png"):
    """Create overview plot with multiple metrics"""
    check_plotting_dependencies()
    
    topics_data = json_data['topics']
    summary = json_data['summary']
    
    # Filter topics with complete data
    complete_topics = [t for t in topics_data if 
                      t['count'] is not None and t['size'] is not None and t['frequency'] is not None
                      and t['count'] > 0]
    
    if not complete_topics:
        raise PlottingError("No complete data available. Use --verbose to analyze all metrics.")
    
    # Sort by total size
    complete_topics.sort(key=lambda x: x['size'], reverse=True)
    
    if plot_format == "html":
        return _create_overview_plot_plotly(complete_topics, summary, output_path)
    else:
        return _create_overview_plot_matplotlib(complete_topics, summary, output_path, plot_format)


def _create_overview_plot_matplotlib(topics_data, summary, output_path, plot_format):
    """Create overview plot using matplotlib with theme"""
    # Apply theme
    theme.apply_matplotlib_style()
    
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Truncate long topic names for display
    display_topics = [t[:25] + "..." if len(t) > 25 else t for t in topics]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Message counts
    bars1 = ax1.bar(range(len(topics)), counts, color=theme.get_plot_color(3), alpha=0.8)
    ax1.set_title('Message Counts', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Count', fontsize=12)
    ax1.set_xticks(range(len(topics)))
    ax1.set_xticklabels(display_topics, rotation=45, ha='right')
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.set_axisbelow(True)
    
    # Sizes
    bars2 = ax2.bar(range(len(topics)), sizes, color=theme.get_plot_color(2), alpha=0.8)
    ax2.set_title('Total Sizes', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Size (Bytes)', fontsize=12)
    ax2.set_xticks(range(len(topics)))
    ax2.set_xticklabels(display_topics, rotation=45, ha='right')
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: _format_bytes(x)))
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax2.set_axisbelow(True)
    
    # Frequencies
    bars3 = ax3.bar(range(len(topics)), frequencies, color=theme.get_plot_color(0), alpha=0.8)
    ax3.set_title('Frequencies', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Frequency (Hz)', fontsize=12)
    ax3.set_xticks(range(len(topics)))
    ax3.set_xticklabels(display_topics, rotation=45, ha='right')
    ax3.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax3.set_axisbelow(True)
    
    # Summary stats
    ax4.axis('off')
    stats_text = f"""
Bag File: {summary['file_name']}
Total Topics: {summary['topic_count']}
Total Messages: {summary['total_messages']:,}
File Size: {summary['file_size_formatted']}
Duration: {summary['duration_formatted']}
Avg Rate: {summary['avg_rate_formatted']}
Theme: {'Dark' if theme.dark_mode else 'Light'} mode
    """.strip()
    ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes, fontsize=12,
             verticalalignment='center', color=theme.TEXT_PRIMARY,
             bbox=dict(boxstyle='round', facecolor=theme.SURFACE, alpha=0.8))
    ax4.set_title('Summary Statistics', fontsize=14, fontweight='bold')
    
    plt.suptitle(f'ROS Bag Overview - {summary["file_name"]}', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, format=plot_format, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path


def _create_overview_plot_plotly(topics_data, summary, output_path):
    """Create overview plot using plotly with theme"""
    topics = [t['topic'] for t in topics_data]
    counts = [t['count'] for t in topics_data]
    sizes = [t['size'] for t in topics_data]
    frequencies = [t['frequency'] for t in topics_data]
    
    # Apply theme template
    template = theme.get_plotly_template()
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Message Counts', 'Total Sizes', 'Frequencies', 'Summary'),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "table"}]]
    )
    
    # Message counts
    fig.add_trace(
        go.Bar(
            x=topics, 
            y=counts, 
            name='Count', 
            marker_color=theme.get_plot_color(3),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        ),
        row=1, col=1
    )
    
    # Sizes
    fig.add_trace(
        go.Bar(
            x=topics, 
            y=sizes, 
            name='Size', 
            marker_color=theme.get_plot_color(2),
            hovertemplate='<b>%{x}</b><br>Size: %{y}<extra></extra>'
        ),
        row=1, col=2
    )
    
    # Frequencies
    fig.add_trace(
        go.Bar(
            x=topics, 
            y=frequencies, 
            name='Frequency', 
            marker_color=theme.get_plot_color(0),
            hovertemplate='<b>%{x}</b><br>Frequency: %{y:.1f} Hz<extra></extra>'
        ),
        row=2, col=1
    )
    
    # Summary table
    fig.add_trace(
        go.Table(
            header=dict(
                values=['Metric', 'Value'],
                fill_color=theme.SURFACE,
                font=dict(color=theme.TEXT_PRIMARY, size=14),
                align='left'
            ),
            cells=dict(
                values=[
                    ['File', 'Topics', 'Messages', 'File Size', 'Duration', 'Avg Rate', 'Theme'],
                    [
                        summary['file_name'], 
                        summary['topic_count'], 
                        f"{summary['total_messages']:,}",
                        summary['file_size_formatted'], 
                        summary['duration_formatted'], 
                        summary['avg_rate_formatted'],
                        f"{'Dark' if theme.dark_mode else 'Light'} mode"
                    ]
                ],
                fill_color=theme.BACKGROUND,
                font=dict(color=theme.TEXT_PRIMARY, size=12),
                align='left'
            )
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        title={
            'text': f"ROS Bag Overview - {summary['file_name']}",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        showlegend=False,
        height=800,
        **template['layout']
    )
    
    # Update x-axes for better readability
    fig.update_xaxes(tickangle=-45, row=1, col=1)
    fig.update_xaxes(tickangle=-45, row=1, col=2)
    fig.update_xaxes(tickangle=-45, row=2, col=1)
    
    pyo.plot(fig, filename=output_path, auto_open=False)
    return output_path


def create_plot(json_data: Dict[str, Any], plot_type: str, output_path: str, plot_format: str = "png"):
    """Create plot based on type"""
    plot_functions = {
        'frequency': create_frequency_plot,
        'size': create_size_distribution_plot,
        'count': create_message_count_plot,
        'overview': create_overview_plot
    }
    
    if plot_type not in plot_functions:
        raise PlottingError(f"Unknown plot type: {plot_type}. Available types: {', '.join(plot_functions.keys())}")
    
    return plot_functions[plot_type](json_data, output_path, plot_format) 