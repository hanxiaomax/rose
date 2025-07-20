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
from ..core.result_handler import OutputFormat
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


@app.command()
def extract_topics(
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
        rose extract extract-topics input.bag --topics gps imu                    # Keep topics matching 'gps' or 'imu'
        rose extract extract-topics input.bag --topics /gps/fix -o output.bag     # Keep exact topic /gps/fix
        rose extract extract-topics input.bag --topics tf --reverse               # Remove topics matching 'tf' 
        rose extract extract-topics input.bag --topics gps --compression lz4      # Use LZ4 compression
        rose extract extract-topics input.bag --topics gps --dry-run              # Preview without extraction
    """
    _extract_topics_impl(input_bag, topics, output, reverse, compression, dry_run, yes, verbose)


@app.command()
def list_topics(
    bag_file: str = typer.Argument(..., help="Path to bag file"),
    patterns: Optional[List[str]] = typer.Option(None, "--patterns", "-p", help="Filter topics by patterns (supports fuzzy matching)"),
    exact_match: bool = typer.Option(False, "--exact", help="Use exact matching instead of fuzzy matching"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed topic information")
):
    """
    List available topics in a ROS bag file
    
    Examples:
        rose extract list-topics demo.bag                    # List all topics
        rose extract list-topics demo.bag -p gps            # List topics containing 'gps'
        rose extract list-topics demo.bag -p gps imu        # List topics containing 'gps' OR 'imu'
        rose extract list-topics demo.bag -p /gps/fix --exact # Exact match for '/gps/fix'
    """
    console = Console()
    
    try:
        # Validate input arguments
        bag_path = Path(bag_file)
        if not bag_path.exists():
            console.print(f"[red]Error: Bag file not found: {bag_file}[/red]")
            raise typer.Exit(1)
        
        # Validate output format
        try:
            output_fmt = OutputFormat(output_format.lower())
        except ValueError:
            supported = ", ".join([fmt.value for fmt in OutputFormat])
            console.print(f"[red]Error: Invalid format '{output_format}'. Supported: {supported}[/red]")
            raise typer.Exit(1)
        
        # Create BagManager and get topics
        manager = BagManager()
        
        with console.status("Analyzing bag file..."):
            result = await_sync(manager.get_topics(bag_path, patterns, exact_match))
        
        # Display results
        _display_topics_list(console, result, output_fmt, verbose)
        
        manager.cleanup()
        
    except Exception as e:
        console.print(f"[red]Error listing topics: {e}[/red]")
        logger.error(f"Topic listing error: {e}", exc_info=True)
        raise typer.Exit(1)


def _display_topics_list(console: Console, result: Dict[str, Any], output_format: OutputFormat, verbose: bool):
    """Display topics list in the specified format"""
    
    if output_format == OutputFormat.JSON:
        import json
        console.print(json.dumps(result, indent=2))
        return
    elif output_format == OutputFormat.YAML:
        try:
            import yaml
            console.print(yaml.dump(result, default_flow_style=False))
        except ImportError:
            console.print("[yellow]YAML output requires pyyaml package. Falling back to table format.[/yellow]")
            output_format = OutputFormat.TABLE
    
    if output_format == OutputFormat.TABLE:
        _display_topics_table(console, result, verbose)


def _display_topics_table(console: Console, result: Dict[str, Any], verbose: bool):
    """Display topics list in table format"""
    
    bag_info = result.get('bag_info', {})
    topics = result.get('topics', [])
    patterns = result.get('patterns', [])
    exact_match = result.get('exact_match', False)
    
    # Show summary
    summary_text = Text()
    summary_text.append(f"Bag File: {bag_info.get('file_name', 'Unknown')}\n")
    summary_text.append(f"Total Topics: {bag_info.get('total_topics', 0)}\n")
    
    if patterns:
        match_type = "exact" if exact_match else "fuzzy"
        summary_text.append(f"Patterns: {', '.join(patterns)} ({match_type} matching)\n")
        summary_text.append(f"Matched Topics: {bag_info.get('filtered_topics', 0)}\n")
    else:
        summary_text.append(f"Showing: All topics\n")
    
    summary_text.append(f"Duration: {bag_info.get('duration_seconds', 0):.1f}s")
    
    if verbose:
        summary_text.append(f"\nAnalysis Time: {bag_info.get('analysis_time', 0):.2f}s")
        summary_text.append(f"\nCached: {'Yes' if bag_info.get('cached', False) else 'No'}")
    
    panel = Panel(
        summary_text,
        title="Bag Topics",
        border_style="blue"
    )
    console.print(panel)
    
    # Show topics table if topics were found
    if topics:
        console.print(f"\n[bold]Available Topics ({len(topics)})[/bold]")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Topic", style="white", width=40)
        table.add_column("Message Type", style="blue", width=30)
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Frequency", justify="right", style="yellow")
        
        if verbose:
            table.add_column("% of Total", justify="right", style="green")
        
        total_messages = sum(topic.get('message_count', 0) for topic in topics)
        
        for topic_info in topics:
            row = [
                topic_info.get('name', ''),
                topic_info.get('message_type', ''),
                f"{topic_info.get('message_count', 0):,}",
                f"{topic_info.get('frequency', 0):.1f} Hz"
            ]
            
            if verbose:
                percentage = (topic_info.get('message_count', 0) / total_messages * 100) if total_messages > 0 else 0
                row.append(f"{percentage:.1f}%")
            
            table.add_row(*row)
        
        console.print(table)
        
        # Show usage hint
        if patterns:
            console.print(f"\n[dim]Use these topic names with: rose extract extract-topics input.bag output.bag --topics {' '.join([t['name'] for t in topics[:3]])}...[/dim]")
        else:
            console.print(f"\n[dim]Use --patterns to filter topics, e.g.: rose extract list-topics {bag_info.get('file_name', 'demo.bag')} -p gps[/dim]")
    else:
        if patterns:
            console.print(f"\n[yellow]No topics found matching patterns: {', '.join(patterns)}[/yellow]")
            console.print(f"[dim]Try using fuzzy matching (default) or different patterns[/dim]")
        else:
            console.print(f"\n[yellow]No topics found in the bag file[/yellow]")


def _display_topics_extraction_table(console: Console, all_topics: List[Dict[str, Any]], topics_to_extract: List[str], reverse: bool):
    """Display a comprehensive table showing all topics with extraction status"""
    
    # Create table
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Status", justify="center", style="bold", width=6)
    table.add_column("Topic", style="white", width=45)
    table.add_column("Count", justify="right", style="cyan", width=10)
    table.add_column("Size Est.", justify="right", style="magenta", width=12)
    
    # Sort topics by name for consistent display
    sorted_topics = sorted(all_topics, key=lambda x: x['name'])
    
    # Helper function to format size estimate
    def format_size_estimate(message_count: int) -> str:
        """Estimate size based on message count (rough approximation)"""
        size_bytes = message_count * 100  # Rough estimate: 100 bytes per message
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f}GB"
    
    # Calculate totals for statistics
    total_messages = sum(t['message_count'] for t in all_topics)
    keep_count = 0
    exclude_count = 0
    
    for topic_info in sorted_topics:
        topic_name = topic_info['name']
        message_count = topic_info['message_count']
        
        # Determine if this topic will be kept or excluded
        will_be_kept = topic_name in topics_to_extract
        
        if will_be_kept:
            # Solid circle for topics to keep
            status_icon = Text("●", style="bold green")
            topic_style = "green"
            count_style = "cyan"
            size_style = "magenta"
            keep_count += 1
        else:
            # Empty circle for topics to drop
            status_icon = Text("○", style="bold red")
            topic_style = "red dim"  # Use dim style for removed topics
            count_style = "red dim"
            size_style = "red dim"
            exclude_count += 1
        
        # Create styled topic name
        topic_text = Text(topic_name, style=topic_style)
        
        # Format values
        count_text = Text(f"{message_count:,}", style=count_style)
        size_text = Text(format_size_estimate(message_count), style=size_style)
        
        # Add row to table
        table.add_row(
            status_icon,
            topic_text,
            count_text,
            size_text
        )
    
    # Add simple title
    title = "Topics Overview"
    title_style = "bold cyan"
    
    console.print(f"\n[{title_style}]{title}[/{title_style}]")
    console.print(table)
    
    # Add legend
    legend_text = Text()
    legend_text.append("Legend: ")
    legend_text.append("●", style="bold green")
    legend_text.append(" = Keep (included in output)  ")
    legend_text.append("○", style="bold red")
    legend_text.append(" = Drop (excluded from output)")
    
    console.print(f"\n{legend_text}")


def _display_verbose_info(console: Console, topics_result: Dict[str, Any], manager):
    """Display verbose information about analysis, cache, and system details"""
    
    bag_info = topics_result.get('bag_info', {})
    cache_stats = topics_result.get('cache_stats', {})
    
    verbose_text = Text()
    
    # Analysis information
    verbose_text.append("Analysis Details:\n", style="bold cyan")
    verbose_text.append(f"  • Analysis Time: {bag_info.get('analysis_time', 0):.3f}s\n")
    verbose_text.append(f"  • Cached Result: {'Yes' if bag_info.get('cached', False) else 'No'}\n")
    verbose_text.append(f"  • Parser Type: rosbags (high-performance)\n")
    
    # Cache performance
    if cache_stats:
        hit_rate = cache_stats.get('hit_rate', 0) * 100
        total_requests = cache_stats.get('total_requests', 0)
        cache_hits = cache_stats.get('cache_hits', 0)
        cache_misses = cache_stats.get('cache_misses', 0)
        
        verbose_text.append("\nCache Performance:\n", style="bold cyan")
        verbose_text.append(f"  • Hit Rate: {hit_rate:.1f}%\n")
        verbose_text.append(f"  • Total Requests: {total_requests}\n")
        verbose_text.append(f"  • Cache Hits: {cache_hits}\n")
        verbose_text.append(f"  • Cache Misses: {cache_misses}\n")
    
    # System information
    verbose_text.append("\nSystem Information:\n", style="bold cyan")
    verbose_text.append(f"  • Cache Type: {type(manager.cache).__name__}\n")
    
    # Bag file details
    duration = bag_info.get('duration_seconds', 0)
    verbose_text.append(f"  • Bag Duration: {duration:.1f}s\n")
    
    if duration > 0:
        total_topics = bag_info.get('total_topics', 0)
        total_messages = sum(t['message_count'] for t in topics_result['topics'])
        avg_rate = total_messages / duration if duration > 0 else 0
        verbose_text.append(f"  • Average Message Rate: {avg_rate:.1f} Hz\n")
    
    panel = Panel(
        verbose_text,
        title="Verbose Information",
        border_style="blue"
    )
    console.print(panel)


def _display_unified_summary(console: Console, topics_result: Dict[str, Any], input_path, 
                           output_path, compression: str, topics_to_extract: List[str], 
                           reverse: bool, verbose: bool, manager, result = None, 
                           extraction_time = None):
    """Display unified summary panel (works for both dry run and actual extraction)"""
    
    bag_info = topics_result.get('bag_info', {})
    all_topics = topics_result['topics']
    
    # Calculate statistics
    total_topics = len(all_topics)
    total_messages = sum(t['message_count'] for t in all_topics)
    total_size_bytes = sum(t.get('estimated_size_bytes', 0) for t in all_topics)
    
    # Filter topics to get kept ones
    kept_topics = []
    for topic in all_topics:
        topic_name = topic['name']
        matches = any(
            topic_name == pattern or 
            (not pattern.startswith('/') and pattern in topic_name) or
            (pattern.startswith('/') and topic_name.startswith(pattern))
            for pattern in topics_to_extract
        )
        
        should_keep = matches if not reverse else not matches
        if should_keep:
            kept_topics.append(topic)
    
    kept_topic_count = len(kept_topics)
    kept_messages = sum(t['message_count'] for t in kept_topics)
    kept_size_bytes = sum(t.get('estimated_size_bytes', 0) for t in kept_topics)
    
    # Get actual file stats if extraction was performed
    if result and 'file_stats' in result:
        file_stats = result['file_stats']
        actual_input_size = file_stats.get('input_size_bytes', total_size_bytes)
        actual_output_size = file_stats.get('output_size_bytes', kept_size_bytes)
        size_reduction_percent = file_stats.get('size_reduction_percent', 0)
        is_actual_extraction = True
    else:
        actual_input_size = total_size_bytes
        actual_output_size = kept_size_bytes
        size_reduction_percent = 0
        is_actual_extraction = False
    
    # Calculate percentages
    topic_percent = (kept_topic_count / total_topics * 100) if total_topics > 0 else 0
    message_percent = (kept_messages / total_messages * 100) if total_messages > 0 else 0
    
    # Create summary text
    summary_text = Text()
    
    # File information
    summary_text.append("File Information:\n", style="bold cyan")
    summary_text.append(f"  Input:  {input_path}\n", style="green")
    summary_text.append(f"  Output: {output_path}\n", style="blue")
    summary_text.append(f"  Compression: {compression}\n")
    
    # Statistics
    duration = bag_info.get('duration_seconds', 0)
    summary_text.append("\nStatistics:\n", style="bold cyan")
    
    if is_actual_extraction:
        # Show actual results with before → after format
        summary_text.append(f"  Topics: {total_topics} → {kept_topic_count} ({topic_percent:.1f}%)\n")
        summary_text.append(f"  Messages: {total_messages:,} → {kept_messages:,} ({message_percent:.1f}%)\n")
        summary_text.append(f"  Size: {actual_input_size / 1024 / 1024:.1f} MB → {actual_output_size / 1024 / 1024:.1f} MB ({100 - size_reduction_percent:.1f}%)\n")
    else:
        # Show preview/estimation format
        summary_text.append(f"  Topics: {total_topics} total, {kept_topic_count} selected ({topic_percent:.1f}%)\n")
        summary_text.append(f"  Messages: {total_messages:,} total, {kept_messages:,} selected ({message_percent:.1f}%)\n")
        summary_text.append(f"  Estimated Size: {kept_size_bytes / 1024 / 1024:.1f} MB of {total_size_bytes / 1024 / 1024:.1f} MB\n")
    
    if duration > 0:
        summary_text.append(f"  Duration: {duration:.1f}s\n")
    
    # Performance information
    if extraction_time is not None:
        summary_text.append(f"\nPerformance:\n", style="bold cyan")
        summary_text.append(f"  Extraction Time: {extraction_time:.3f}s\n")
        if extraction_time > 0:
            messages_per_sec = kept_messages / extraction_time
            summary_text.append(f"  Processing Rate: {messages_per_sec:.0f} messages/sec\n")
    
    # Add verbose information if requested
    if verbose:
        cache_stats = topics_result.get('cache_stats', {})
        analysis_time = bag_info.get('analysis_time', 0)
        cached = bag_info.get('cached', False)
        
        summary_text.append("\nDetailed Information:\n", style="bold cyan")
        summary_text.append(f"  Analysis Time: {analysis_time:.3f}s\n")
        summary_text.append(f"  Cached Result: {'Yes' if cached else 'No'}\n")
        summary_text.append(f"  Parser: rosbags (high-performance)\n")
        summary_text.append(f"  Cache Type: {type(manager.cache).__name__}\n")
        
        if cache_stats:
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            summary_text.append(f"  Cache Hit Rate: {hit_rate:.1f}%\n")
        
        if extraction_time is not None and analysis_time > 0:
            total_time = analysis_time + extraction_time
            efficiency = (analysis_time / total_time) * 100
            summary_text.append(f"  Total Time: {total_time:.3f}s\n")
            summary_text.append(f"  Analysis Efficiency: {efficiency:.1f}%\n")
        
        if duration > 0:
            avg_rate = total_messages / duration
            summary_text.append(f"  Avg Message Rate: {avg_rate:.1f} Hz\n")
    
    # Add topics overview as final section
    summary_text.append("\nTopics Overview:\n", style="bold cyan")
    excluded_count = total_topics - kept_topic_count
    summary_text.append(f"  Keeping {kept_topic_count}, Excluding {excluded_count}\n")
    
    # Add topics table within the summary
    summary_text.append("\n")
    
    # Create topics table
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Status", style="bold", width=8, justify="center")
    table.add_column("Topic", style="cyan", min_width=30)
    table.add_column("Count", style="yellow", justify="right", width=10)
    table.add_column("Size Est.", style="green", justify="right", width=12)
    
    for topic in all_topics:
        topic_name = topic['name']
        message_count = topic['message_count']
        size_estimate = topic.get('estimated_size_bytes', 0)
        
        # Check if this topic should be kept
        matches = any(
            topic_name == pattern or 
            (not pattern.startswith('/') and pattern in topic_name) or
            (pattern.startswith('/') and topic_name.startswith(pattern))
            for pattern in topics_to_extract
        )
        
        should_keep = matches if not reverse else not matches
        
        if should_keep:
            status = "●"
            status_style = "green"
        else:
            status = "○"
            status_style = "red dim"
            topic_name = f"[dim]{topic_name}[/dim]"
        
        # Format size
        if size_estimate > 1024 * 1024:
            size_str = f"{size_estimate / 1024 / 1024:.1f}MB"
        elif size_estimate > 1024:
            size_str = f"{size_estimate / 1024:.1f}KB"
        else:
            size_str = f"{size_estimate}B"
        
        table.add_row(
            f"[{status_style}]{status}[/{status_style}]",
            topic_name,
            f"{message_count:,}",
            size_str
        )
    
    # Create combined content
    # Create legend
    legend_text = Text()
    legend_text.append("● = Keep (included in output)  ", style="green")
    legend_text.append("○ = Drop (excluded from output)", style="red dim")
    
    combined_content = Group(
        summary_text,
        Align.center(table),
        "",
        Align.center(legend_text)
    )
    
    # Create panel
    panel_title = "Summary"
    if verbose:
        panel_title += " (Verbose)"
    
    panel = Panel(
        combined_content,
        title=panel_title,
        border_style="cyan"
    )
    console.print(panel)


def _display_extraction_result_summary(console: Console, topics_result: Dict[str, Any], input_path, 
                                      output_path, compression: str, topics_to_extract: List[str], 
                                      reverse: bool, verbose: bool, manager, result: Dict[str, Any], 
                                      extraction_time: float):
    """Display unified extraction result summary panel after successful extraction"""
    
    bag_info = topics_result.get('bag_info', {})
    all_topics = topics_result['topics']
    
    # Calculate statistics
    total_topics = len(all_topics)
    total_messages = sum(t['message_count'] for t in all_topics)
    total_size_bytes = sum(t.get('estimated_size_bytes', 0) for t in all_topics)
    
    # Filter topics to get kept ones
    kept_topics = []
    for topic in all_topics:
        topic_name = topic['name']
        matches = any(
            topic_name == pattern or 
            (not pattern.startswith('/') and pattern in topic_name) or
            (pattern.startswith('/') and topic_name.startswith(pattern))
            for pattern in topics_to_extract
        )
        
        should_keep = matches if not reverse else not matches
        if should_keep:
            kept_topics.append(topic)
    
    kept_topic_count = len(kept_topics)
    kept_messages = sum(t['message_count'] for t in kept_topics)
    kept_size_bytes = sum(t.get('estimated_size_bytes', 0) for t in kept_topics)
    
    # Get actual file stats if available
    file_stats = result.get('file_stats', {})
    actual_input_size = file_stats.get('input_size_bytes', total_size_bytes)
    actual_output_size = file_stats.get('output_size_bytes', kept_size_bytes)
    
    # Calculate percentages
    topic_percent = (kept_topic_count / total_topics * 100) if total_topics > 0 else 0
    message_percent = (kept_messages / total_messages * 100) if total_messages > 0 else 0
    size_reduction = file_stats.get('size_reduction_percent', 0)
    
    # Create summary text
    summary_text = Text()
    
    # File information
    summary_text.append("Extraction Complete:\n", style="bold green")
    summary_text.append(f"  Input:  {input_path}\n", style="white")
    summary_text.append(f"  Output: {output_path}\n", style="green")
    summary_text.append(f"  Compression: {compression}\n")
    
    # Statistics comparison
    summary_text.append("\nOriginal → Filtered:\n", style="bold cyan")
    summary_text.append(f"  Topics: {total_topics:,} → {kept_topic_count:,} ({topic_percent:.1f}%)\n")
    summary_text.append(f"  Messages: {total_messages:,} → {kept_messages:,} ({message_percent:.1f}%)\n")
    summary_text.append(f"  Size: {actual_input_size / 1024 / 1024:.1f} MB → {actual_output_size / 1024 / 1024:.1f} MB ({100 - size_reduction:.1f}%)\n")
    

    
    # Timing information
    summary_text.append("\nPerformance:\n", style="bold cyan")
    summary_text.append(f"  Extraction Time: {extraction_time:.3f}s\n")
    
    if extraction_time > 0:
        messages_per_sec = kept_messages / extraction_time
        summary_text.append(f"  Processing Rate: {messages_per_sec:.0f} messages/sec\n")
    
    # Add verbose information if requested
    if verbose:
        cache_stats = topics_result.get('cache_stats', {})
        analysis_time = bag_info.get('analysis_time', 0)
        cached = bag_info.get('cached', False)
        
        total_time = analysis_time + extraction_time
        
        summary_text.append("\nDetailed Performance:\n", style="bold cyan")
        summary_text.append(f"  Analysis Time: {analysis_time:.3f}s\n")
        summary_text.append(f"  Total Time: {total_time:.3f}s\n")
        summary_text.append(f"  Cached Analysis: {'Yes' if cached else 'No'}\n")
        summary_text.append(f"  Parser: rosbags (high-performance)\n")
        summary_text.append(f"  Cache Type: {type(manager.cache).__name__}\n")
        
        if cache_stats:
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            summary_text.append(f"  Cache Hit Rate: {hit_rate:.1f}%\n")
        
        if total_time > 0:
            efficiency = (analysis_time / total_time) * 100
            summary_text.append(f"  Analysis Efficiency: {efficiency:.1f}%\n")
    
    # Create panel
    panel_title = "Extraction Results"
    if verbose:
        panel_title += " (Verbose)"
    
    panel = Panel(
        summary_text,
        title=panel_title,
        border_style="green"
    )
    console.print(panel)


def _display_extraction_timing(console: Console, topics_result: Dict[str, Any], extraction_time: float):
    """Display detailed timing breakdown for verbose mode"""
    
    bag_info = topics_result.get('bag_info', {})
    analysis_time = bag_info.get('analysis_time', 0)
    
    timing_text = Text()
    timing_text.append("Timing Breakdown:\n", style="bold yellow")
    timing_text.append(f"  • Bag Analysis: {analysis_time:.3f}s\n")
    timing_text.append(f"  • Topic Extraction: {extraction_time:.3f}s\n")
    
    total_time = analysis_time + extraction_time
    timing_text.append(f"  • Total Time: {total_time:.3f}s\n")
    
    # Calculate performance metrics
    total_messages = sum(t['message_count'] for t in topics_result['topics'])
    if extraction_time > 0:
        messages_per_sec = total_messages / extraction_time
        timing_text.append(f"  • Processing Rate: {messages_per_sec:.0f} messages/sec\n")
    
    # Show efficiency metrics
    if total_time > 0:
        efficiency = (analysis_time / total_time) * 100
        timing_text.append(f"  • Analysis Efficiency: {efficiency:.1f}% (cached analysis saves time)")
    
    panel = Panel(
        timing_text,
        title="Performance Metrics",
        border_style="yellow"
    )
    console.print(panel)


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
    Extract specific topics from a ROS bag file using the new simplified format
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
        
        with console.status("Analyzing bag file..."):
            topics_result = await_sync(manager.get_topics(input_path))
        
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
        
        # Show extraction overview with unified format
        console.print(f"\n[bold]{operation_desc}[/bold]")
        
        # Topics table will be included in the summary panel
        
        # If dry run, show summary and return without actual extraction
        if dry_run:
            _display_unified_summary(console, topics_result, input_path, output_path, compression, topics_to_extract, reverse, verbose, manager)
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
        
        with console.status("Extracting topics..."):
            result = await_sync(manager.extract_bag(input_path, options))
        
        extraction_end_time = time.time()
        extraction_time = extraction_end_time - extraction_start_time
        
        # Check if extraction was successful
        if not result.get('success', False):
            console.print(f"\n[red]Extraction failed: {result.get('error', 'Unknown error')}[/red]")
            raise typer.Exit(1)
        
        # Show success message
        console.print(f"\n[green]✓ Successfully extracted to: {output_path}[/green]")
        
        # Create unified summary panel (with extraction results)
        _display_unified_summary(console, topics_result, input_path, output_path, compression, 
                                topics_to_extract, reverse, verbose, manager, result, extraction_time)
        
        manager.cleanup()
        
    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise typer.Exit(1)


def _display_extraction_results(console: Console, result: Dict[str, Any], output_format: OutputFormat, verbose: bool):
    """Display extraction results in the specified format"""
    
    if output_format == OutputFormat.JSON:
        import json
        console.print(json.dumps(result, indent=2))
        return
    elif output_format == OutputFormat.YAML:
        try:
            import yaml
            console.print(yaml.dump(result, default_flow_style=False))
        except ImportError:
            console.print("[yellow]YAML output requires pyyaml package. Falling back to table format.[/yellow]")
            output_format = OutputFormat.TABLE
    
    if output_format == OutputFormat.TABLE:
        _display_table_results(console, result, verbose)


def _display_table_results(console: Console, result: Dict[str, Any], verbose: bool):
    """Display extraction results in table format"""
    
    bag_info = result.get('bag_info', {})
    topics = result.get('topics', [])
    
    # Show extraction summary
    if result.get('dry_run', False):
        title_style = "yellow"
        title = "Extraction Preview (Dry Run)"
    elif result.get('success', False):
        title_style = "green"
        title = "Extraction Results"
    else:
        title_style = "red"
        title = "Extraction Failed"
    
    # Create summary panel
    summary_text = Text()
    summary_text.append(f"Input File: {bag_info.get('input_file', 'Unknown')}\n")
    summary_text.append(f"Output File: {bag_info.get('output_file', 'Unknown')}\n")
    summary_text.append(f"Topics: {bag_info.get('extracted_topics', 0)} / {bag_info.get('total_topics', 0)}\n")
    summary_text.append(f"Messages: {bag_info.get('extracted_messages', 0):,} / {bag_info.get('total_messages', 0):,}\n")
    summary_text.append(f"Extraction: {bag_info.get('extraction_percentage', 0):.1f}% of data\n")
    summary_text.append(f"Duration: {bag_info.get('duration_seconds', 0):.1f}s\n")
    summary_text.append(f"Compression: {bag_info.get('compression', 'none')}")
    
    # Add file size info if available
    if 'file_stats' in result:
        file_stats = result['file_stats']
        input_size_mb = file_stats.get('input_size_bytes', 0) / 1024 / 1024
        output_size_mb = file_stats.get('output_size_bytes', 0) / 1024 / 1024
        size_reduction = file_stats.get('size_reduction_percent', 0)
        
        summary_text.append(f"\nInput Size: {input_size_mb:.1f} MB")
        summary_text.append(f"\nOutput Size: {output_size_mb:.1f} MB")
        summary_text.append(f"\nSize Reduction: {size_reduction:.1f}%")
    
    panel = Panel(
        summary_text,
        title=title,
        border_style=title_style
    )
    console.print(panel)
    
    # Show topics table if topics were found
    if topics:
        console.print(f"\n[bold]Extracted Topics ({len(topics)})[/bold]")
        
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Topic", style="white", width=40)
        table.add_column("Message Type", style="blue", width=30)
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Frequency", justify="right", style="yellow")
        
        if verbose:
            table.add_column("% of Extract", justify="right", style="green")
        
        for topic_info in topics:
            row = [
                topic_info.get('name', ''),
                topic_info.get('message_type', ''),
                f"{topic_info.get('message_count', 0):,}",
                f"{topic_info.get('frequency', 0):.1f} Hz"
            ]
            
            if verbose:
                row.append(f"{topic_info.get('size_percentage', 0):.1f}%")
            
            table.add_row(*row)
        
        console.print(table)


def main():
    """CLI tool entry point"""
    app()


if __name__ == "__main__":
    main() 