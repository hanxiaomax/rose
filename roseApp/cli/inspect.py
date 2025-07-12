#!/usr/bin/env python3
"""
Inspect command for fast ROS bag analysis with caching support
"""

import os
import time
import pickle
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box
from textual.fuzzy import FuzzySearch

from ..core.parser import create_parser, ParserType
from ..core.util import set_app_mode, AppMode, get_logger, log_cli_error

app = typer.Typer(help="Fast ROS bag inspection and analysis")

# Cache directory for analysis results
CACHE_DIR = Path.home() / ".cache" / "rose" / "bag_analysis"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Global fuzzy search instance
fuzzy_search = FuzzySearch(case_sensitive=False)


def _get_cache_path(bag_path: str) -> Path:
    """Get cache file path for a bag file"""
    # Create hash of bag file path and modification time
    stat = os.stat(bag_path)
    cache_key = f"{bag_path}_{stat.st_mtime}_{stat.st_size}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    return CACHE_DIR / f"{cache_hash}.pkl"


def _load_cache(cache_path: Path) -> Optional[Dict]:
    """Load cached analysis results"""
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        # If cache is corrupted, remove it
        cache_path.unlink(missing_ok=True)
        return None


def _save_cache(cache_path: Path, data: Dict):
    """Save analysis results to cache"""
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception:
        # If we can't save cache, just continue without it
        pass


@app.command()
def inspect(
    input_path: str = typer.Argument(..., help="Input bag file path"),
    topics: List[str] = typer.Option([], "--topics", "-t", help="Filter topics by name or pattern (supports fuzzy matching). Multiple values: --topics topic1 --topics topic2 --topics pattern3"),
    show_as: str = typer.Option("table", "--show-as", "-f", help="Display format: table, list, summary (default: table)"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort by: name, type, count, size, frequency (default: size)"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output with detailed statistics")
):
    """
    Fast inspection of ROS bag files with flexible display options and caching
    
    The analysis results are cached to improve performance on subsequent runs.
    The cache is automatically invalidated when the bag file is modified.
    Use 'prune' command to manage cache files.
    
    Examples:
    
    # Show all topics in table format
    rose inspect demo.bag
    
    # Filter multiple topics by name or fuzzy pattern
    rose inspect demo.bag --topics dts --topics tf --topics velodyne
    
    # Show summary with compression info
    rose inspect demo.bag --show-as summary
    
    # Show detailed verbose output
    rose inspect demo.bag --verbose
    """
    try:
        # Initialize logging
        set_app_mode(AppMode.CLI)
        logger = get_logger("inspect")
        
        # Record start time for performance measurement
        start_time = time.time()
        
        # Validate input
        if not os.path.exists(input_path):
            typer.echo(f"Error: Input file '{input_path}' does not exist", err=True)
            raise typer.Exit(code=1)
        
        if not input_path.endswith('.bag'):
            typer.echo(f"Error: Input file '{input_path}' is not a bag file", err=True)
            raise typer.Exit(code=1)
        
        # Validate options
        if show_as not in ["table", "list", "summary"]:
            typer.echo(f"Error: --show-as must be one of: table, list, summary", err=True)
            raise typer.Exit(code=1)
        
        if sort_by not in ["name", "type", "count", "size", "frequency"]:
            typer.echo(f"Error: --sort-by must be one of: name, type, count, size, frequency", err=True)
            raise typer.Exit(code=1)
        
        # Initialize console
        console = Console()
        
        # Try to load from cache first
        cache_path = _get_cache_path(input_path)
        bag_info = _load_cache(cache_path)
        if bag_info:
            logger.debug(f"Loaded analysis from cache: {cache_path}")
            console.print(f"[dim]Using cached analysis results[/dim]")
        
        # If no cache, perform analysis
        if bag_info is None:
            parser = create_parser(ParserType.ROSBAGS)
            logger.debug(f"Analyzing bag file: {input_path}")
            bag_info = _analyze_bag_with_progress(parser, input_path, logger, console)
            
            # Save to cache
            _save_cache(cache_path, bag_info)
            logger.debug(f"Saved analysis to cache: {cache_path}")
        
        # Record analysis time
        analysis_time = time.time() - start_time
        bag_info['analysis_time'] = analysis_time
        
        # Apply filters and sorting  
        filtered_topics = _filter_topics(bag_info['topics'], topics if topics else None)
        # Default sorting is always large to small (reverse=True by default)
        actual_reverse = not reverse if reverse else True  # If user didn't specify reverse, default to True (large first)
        sorted_topics = _sort_topics(filtered_topics, bag_info['stats'], sort_by, actual_reverse)
        
        # Display results
        _display_bag_inspection(
            console=console,
            input_path=input_path,
            bag_info=bag_info,
            filtered_topics=sorted_topics,
            show_as=show_as,
            verbose=verbose
        )
        
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _analyze_bag_with_progress(parser, bag_path: str, logger, console: Console) -> Dict:
    """Fast analysis of bag file with progress indication"""
    try:
        # Step 1: Load basic bag info with timing
        from .util import LoadingAnimationWithTimer
        with LoadingAnimationWithTimer("Loading bag structure...", dismiss=True) as load_progress:
            load_progress.add_task(description="Loading bag structure...")
            topics, connections, time_range = parser.load_bag(bag_path)
        
        # Step 2: Continue with analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Analyzing topics...", total=70)
            
            # Get topic statistics (50%)
            progress.update(task, advance=0, description="Analyzing topics...")
            topic_stats = parser.get_topic_stats(bag_path)
            progress.update(task, advance=50, description="Analyzed topics")
            
            # Step 3: Get file size and calculate metrics (20%)
            progress.update(task, advance=0, description="Calculating metrics...")
            file_size = os.path.getsize(bag_path)
            progress.update(task, advance=20, description="Analysis complete")
            
            # Calculate duration
            duration = None
            start_time = None
            end_time = None
            
            if time_range and len(time_range) == 2:
                start_time = time_range[0]
                end_time = time_range[1]
                # Convert (seconds, nanoseconds) to total seconds
                start_seconds = start_time[0] + start_time[1] / 1_000_000_000
                end_seconds = end_time[0] + end_time[1] / 1_000_000_000
                duration = end_seconds - start_seconds
            
            # Calculate totals
            total_messages = sum(stats['count'] for stats in topic_stats.values())
            total_data_size = sum(stats['size'] for stats in topic_stats.values())
            
            return {
                'topics': topics,
                'connections': connections,
                'stats': topic_stats,
                'file_size': file_size,
                'total_messages': total_messages,
                'total_data_size': total_data_size,
                'duration': duration,
                'start_time': start_time,
                'end_time': end_time,
                'topic_count': len(topics)
            }
            
    except Exception as e:
        logger.error(f"Error analyzing bag: {e}")
        raise


def _filter_topics(topics: List[str], topic_filter: Optional[List[str]]) -> List[str]:
    """Filter topics based on exact match or fuzzy search"""
    if not topic_filter:
        return topics
    
    filtered = []
    
    # For each filter pattern, find matching topics
    for pattern in topic_filter:
        # Try exact match first
        exact_matches = [topic for topic in topics if topic == pattern]
        if exact_matches:
            filtered.extend(exact_matches)
        else:
            # Try fuzzy search for this pattern
            fuzzy_matches = _fuzzy_search_topics(topics, pattern)
            filtered.extend(fuzzy_matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_filtered = []
    for topic in filtered:
        if topic not in seen:
            seen.add(topic)
            unique_filtered.append(topic)
    
    return unique_filtered


def _fuzzy_search_topics(topics: List[str], search_pattern: str) -> List[str]:
    """Perform fuzzy search on topics using textual.fuzzy only"""
    fuzzy_matches = []
    topic_scores = []
    
    for topic in topics:
        # Match against the full topic name
        score, offsets = fuzzy_search.match(search_pattern, topic)
        
        # Also try matching against just the topic name (after the last '/')
        topic_name = topic.split('/')[-1]
        name_score, name_offsets = fuzzy_search.match(search_pattern, topic_name)
        
        # Use the better score
        best_score = max(score, name_score)
        
        # Only include topics with reasonable scores
        if best_score > 0:
            topic_scores.append((topic, best_score))
    
    # Sort fuzzy matches by score (descending)
    topic_scores.sort(key=lambda x: x[1], reverse=True)
    fuzzy_matches = [topic for topic, score in topic_scores]
    
    return fuzzy_matches


def _sort_topics(topics: List[str], stats: Dict, sort_by: str, reverse: bool) -> List[str]:
    """Sort topics based on specified criteria"""
    def get_sort_key(topic: str):
        topic_stats = stats.get(topic, {'count': 0, 'size': 0})
        
        if sort_by == "name":
            return topic.lower()
        elif sort_by == "type":
            return topic.split('/')[-1].lower()  # Sort by topic name part
        elif sort_by == "count":
            return topic_stats['count']
        elif sort_by == "size":
            return topic_stats['size']
        elif sort_by == "frequency":
            # This will need duration calculation per topic, for now use count
            return topic_stats['count']
        else:
            return topic_stats['size']
    
    return sorted(topics, key=get_sort_key, reverse=reverse)


def _get_compression_info(bag_path: str) -> str:
    """Get compression information from bag file"""
    try:
        # Try to detect compression by reading bag file format
        with open(bag_path, 'rb') as f:
            # Skip bag header line
            f.readline()
            
            # Read first record to check for compression
            while True:
                try:
                    header_len_bytes = f.read(4)
                    if not header_len_bytes or len(header_len_bytes) < 4:
                        break
                    
                    header_len = int.from_bytes(header_len_bytes, 'little')
                    if header_len <= 0 or header_len > 1024*1024:  # Sanity check
                        break
                    
                    header_data = f.read(header_len)
                    if not header_data or len(header_data) < header_len:
                        break
                    
                    # Parse header fields
                    header_str = header_data.decode('utf-8', errors='ignore')
                    
                    # Look for compression field in chunk records
                    if 'compression=' in header_str:
                        # Extract compression value
                        for field in header_str.split('\x00'):
                            if field.startswith('compression='):
                                compression = field.split('=', 1)[1]
                                return compression if compression != 'none' else 'none'
                    
                    # Skip data section
                    data_len_bytes = f.read(4)
                    if not data_len_bytes or len(data_len_bytes) < 4:
                        break
                    
                    data_len = int.from_bytes(data_len_bytes, 'little')
                    if data_len < 0:
                        break
                    
                    f.seek(data_len, 1)  # Skip data
                    
                except Exception:
                    break
        
        return 'none'  # Default if no compression found
    except Exception:
        return 'unknown'


def _display_bag_inspection(console: Console, input_path: str, bag_info: Dict, 
                           filtered_topics: List[str], show_as: str, 
                           verbose: bool):
    """Display bag inspection results in specified format"""
    
    if show_as == "summary":
        _display_summary(console, input_path, bag_info, len(filtered_topics), verbose)
    elif show_as == "list":
        _display_list(console, input_path, bag_info, filtered_topics, verbose)
    else:  # table
        _display_table(console, input_path, bag_info, filtered_topics, verbose)


def _display_summary(console: Console, input_path: str, bag_info: Dict, filtered_count: int, verbose: bool):
    """Display summary information"""
    console.print(f"\n[bold cyan]Bag File Summary[/bold cyan]")
    
    if verbose:
        # Verbose mode shows full details
        console.print(f"[dim]Absolute Path:[/dim] {os.path.abspath(input_path)}")
        console.print(f"[dim]File Name:[/dim] {os.path.basename(input_path)}")
        console.print(f"[dim]Analysis Time:[/dim] {bag_info.get('analysis_time', 0):.3f}s")
        console.print("-" * 80)
    else:
        # Non-verbose mode still shows basic file info
        console.print(f"[dim]File:[/dim] {os.path.basename(input_path)}")
        console.print("-" * 60)
    
    summary_data = [
        f"[bold]Topics:[/bold] {bag_info['topic_count']}",
        f"[bold]Messages:[/bold] {bag_info['total_messages']:,}",
        f"[bold]File Size:[/bold] {_format_size(bag_info['file_size'])}",
        f"[bold]Data Size:[/bold] {_format_size(bag_info['total_data_size'])}",
    ]
    
    # Add compression information
    compression = _get_compression_info(input_path)
    compression_display = compression.upper() if compression != 'none' else 'None'
    summary_data.append(f"[bold]Compression:[/bold] {compression_display}")
    
    if bag_info['duration']:
        summary_data.append(f"[bold]Duration:[/bold] {_format_duration(bag_info['duration'])}")
        avg_rate = bag_info['total_messages'] / bag_info['duration']
        summary_data.append(f"[bold]Avg Rate:[/bold] {avg_rate:.1f} Hz")
    
    if filtered_count != bag_info['topic_count']:
        summary_data.append(f"[bold]Filtered:[/bold] {filtered_count} topics shown")
    
    # Always show as separate lines for summary
    for item in summary_data:
        console.print(item)
    
    if verbose and bag_info.get('start_time') and bag_info.get('end_time'):
        console.print(f"[dim]Start Time:[/dim] {bag_info['start_time']}")
        console.print(f"[dim]End Time:[/dim] {bag_info['end_time']}")


def _display_list(console: Console, input_path: str, bag_info: Dict, 
                  filtered_topics: List[str], verbose: bool):
    """Display topics in list format"""
    # Always show summary first
    _display_summary(console, input_path, bag_info, len(filtered_topics), verbose)
    console.print()
    
    # Show topics header in verbose mode
    if verbose:
        console.print(f"[bold cyan]Topics in {Path(input_path).name}[/bold cyan]")
        console.print(f"[dim]Total: {len(filtered_topics)} topics[/dim]")
        console.print("-" * 60)
    
    for topic in filtered_topics:
        stats = bag_info['stats'].get(topic, {'count': 0, 'size': 0})
        msg_type = bag_info['connections'].get(topic, 'Unknown')
        
        # Format message type
        formatted_type = _format_message_type(msg_type)
        
        # Default: show frequency but not type
        info_parts = [
            f"[bold]{topic}[/bold]",
            f"[cyan]{stats['count']:,} msgs[/cyan]",
            f"[green]{_format_size(stats['size'])}[/green]"
        ]
        
        # Add frequency for all modes
        if bag_info['duration'] and bag_info['duration'] > 0:
            frequency = stats['count'] / bag_info['duration']
            info_parts.append(f"[magenta]{frequency:.1f} Hz[/magenta]")
        
        # Add type only in verbose mode
        if verbose:
            info_parts.insert(1, f"[yellow]{formatted_type}[/yellow]")
        
        console.print(" | ".join(info_parts))


def _display_table(console: Console, input_path: str, bag_info: Dict, 
                   filtered_topics: List[str], verbose: bool):
    """Display topics in table format"""
    # Always show summary first, detailed in verbose mode
    _display_summary(console, input_path, bag_info, len(filtered_topics), verbose)
    console.print()
    
    # Create table with appropriate styling
    table = Table(
        box=box.ROUNDED if verbose else box.SIMPLE, 
        title="Topics" if verbose else None,
        title_style="bold cyan" if verbose else None
    )
    
    # Add columns based on mode
    table.add_column("Topic", justify="left", style="bold", min_width=20)
    
    # Show type only in verbose mode
    if verbose:
        table.add_column("Type", justify="left", style="yellow", min_width=20)
    
    table.add_column("Count", justify="right", style="cyan", min_width=8)
    table.add_column("Size", justify="right", style="green", min_width=8)
    
    # Always show frequency
    table.add_column("Frequency", justify="right", style="magenta", min_width=10)
    
    # Add rows
    for topic in filtered_topics:
        stats = bag_info['stats'].get(topic, {'count': 0, 'size': 0})
        msg_type = bag_info['connections'].get(topic, 'Unknown')
        
        # Format message type
        formatted_type = _format_message_type(msg_type)
        
        # Format frequency
        frequency_str = "N/A"
        if bag_info['duration'] and bag_info['duration'] > 0:
            frequency = stats['count'] / bag_info['duration']
            frequency_str = f"{frequency:.1f} Hz"
        
        # Build row data
        row_data = [topic]
        
        # Add type only in verbose mode
        if verbose:
            row_data.append(formatted_type)
        
        row_data.extend([
            f"{stats['count']:,}",
            _format_size(stats['size']),
            frequency_str
        ])
        
        table.add_row(*row_data)
    
    console.print(table)


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(size_bytes.bit_length() // 10)
    if i >= len(size_names):
        i = len(size_names) - 1
    
    size = size_bytes / (1024 ** i)
    return f"{size:.1f} {size_names[i]}"


def _format_duration(duration_seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    if duration_seconds < 60:
        return f"{duration_seconds:.1f}s"
    elif duration_seconds < 3600:
        minutes = int(duration_seconds // 60)
        seconds = duration_seconds % 60
        return f"{minutes}m {seconds:.1f}s"
    else:
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = duration_seconds % 60
        return f"{hours}h {minutes}m {seconds:.1f}s"


def _format_message_type(msg_type: str) -> str:
    """Format message type for display"""
    if not msg_type or msg_type == "Unknown":
        return "Unknown"
    
    # Remove package prefix if present
    if "/" in msg_type:
        msg_type = msg_type.split("/")[-1]
    
    # Limit length and add ellipsis if needed
    if len(msg_type) > 25:
        msg_type = msg_type[:22] + "..."
    
    return msg_type


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 