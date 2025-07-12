#!/usr/bin/env python3
"""
Inspect command for fast ROS bag analysis with caching support
"""

import os
import time
import pickle
import hashlib
import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
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
    as_format: str = typer.Option("table", "--as", "-a", help="Output format: table, list, summary, csv, html (default: table)"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort by: name, type, count, size, frequency (default: size)"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output with detailed statistics"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (for csv/html formats)")
):
    """
    Fast inspection of ROS bag files with flexible display options and caching
    
    The analysis results are cached to improve performance on subsequent runs.
    The cache is automatically invalidated when the bag file is modified.
    Use 'prune' command to manage cache files.
    
    By default, only lightweight metadata is analyzed for faster performance.
    Use --verbose to parse all messages and show detailed statistics.
    
    Examples:
    
    # Show basic topics information (fast)
    rose inspect demo.bag
    
    # Show detailed statistics with message counts and sizes
    rose inspect demo.bag --verbose
    
    # Filter multiple topics by name or fuzzy pattern
    rose inspect demo.bag --topics dts --topics tf --topics velodyne
    
    # Export to CSV
    rose inspect demo.bag --as csv --output topics.csv
    
    # Export to HTML
    rose inspect demo.bag --as html --output report.html
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
        if as_format not in ["table", "list", "summary", "csv", "html"]:
            typer.echo(f"Error: --as must be one of: table, list, summary, csv, html", err=True)
            raise typer.Exit(code=1)
        
        if sort_by not in ["name", "type", "count", "size", "frequency"]:
            typer.echo(f"Error: --sort-by must be one of: name, type, count, size, frequency", err=True)
            raise typer.Exit(code=1)
        
        # Validate output file for export formats
        if as_format in ["csv", "html"] and not output:
            typer.echo(f"Error: --output is required for {as_format} format", err=True)
            raise typer.Exit(code=1)
        
        # Initialize console
        console = Console()
        
        # Determine analysis mode
        use_full_analysis = verbose
        
        # Show top info message for lite mode
        if not use_full_analysis:
            console.print(f"[yellow]INFO: Using lightweight analysis. Use --verbose for detailed statistics.[/yellow]")
        
        # Try to load from cache first
        cache_path = _get_cache_path(input_path)
        cached_bag_info = _load_cache(cache_path)
        
        if cached_bag_info:
            logger.debug(f"Loaded analysis from cache: {cache_path}")
            console.print(f"[dim]Using cached analysis results[/dim]")
            bag_info = cached_bag_info
            # If we have cached data, we can show full information even without --verbose
            use_full_analysis = True
        else:
            # No cache available, perform analysis
            parser = create_parser(ParserType.ROSBAGS)
            logger.debug(f"Analyzing bag file: {input_path}")
            
            if use_full_analysis:
                # Full analysis: get complete statistics
                bag_info = _analyze_bag_full(parser, input_path, logger, console)
                # Save to cache for future use
                _save_cache(cache_path, bag_info)
                logger.debug(f"Saved analysis to cache: {cache_path}")
            else:
                # Lite analysis: only metadata
                bag_info = _analyze_bag_lite(parser, input_path, logger, console)
        
        # Record analysis time
        analysis_time = time.time() - start_time
        bag_info['analysis_time'] = analysis_time
        
        # Apply filters and sorting
        filtered_topics = _filter_topics(bag_info['topics'], topics if topics else None)
        
        # Convert to JSON structure for unified processing
        json_data = _create_json_structure(
            input_path=input_path,
            bag_info=bag_info,
            filtered_topics=filtered_topics,
            is_lite_mode=not use_full_analysis
        )
        
        # Apply sorting to topic details
        if 'stats' in bag_info and bag_info['stats']:
            # We have detailed stats, can sort properly
            actual_reverse = not reverse if reverse else True
            json_data['topics'] = _sort_topic_details(json_data['topics'], sort_by, actual_reverse)
        else:
            # No detailed stats, can only sort by name
            if sort_by != "name":
                console.print(f"[yellow]Warning: Sorting by '{sort_by}' requires --verbose mode, using name sorting instead[/yellow]")
                sort_by = "name"
            json_data['topics'] = sorted(json_data['topics'], key=lambda x: x['topic'].lower(), reverse=reverse)
        
        # Display or export results
        if as_format in ["csv", "html"]:
            _export_data(json_data, as_format, output, console)
        else:
            _display_data(json_data, as_format, verbose, console)
        
        # Show bottom info message for lite mode
        if not use_full_analysis and as_format not in ["csv", "html"]:
            console.print(f"[yellow]INFO: Use --verbose to analyze all messages and show detailed statistics.[/yellow]")
        
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _analyze_bag_lite(parser, bag_path: str, logger, console: Console) -> Dict:
    """Fast lite analysis of bag file - only metadata, no message iteration"""
    try:
        # Only load basic bag info without iterating through messages
        from .util import LoadingAnimationWithTimer
        with LoadingAnimationWithTimer("Loading bag metadata...", dismiss=True) as load_progress:
            load_progress.add_task(description="Loading bag metadata...")
            topics, connections, time_range = parser.load_bag(bag_path)
        
        # Get file size
        file_size = os.path.getsize(bag_path)
        
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
        
        return {
            'topics': topics,
            'connections': connections,
            'stats': {},  # Empty stats for lite mode
            'file_size': file_size,
            'total_messages': None,  # Unknown in lite mode
            'total_data_size': None,  # Unknown in lite mode
            'duration': duration,
            'start_time': start_time,
            'end_time': end_time,
            'topic_count': len(topics),
            'is_lite_mode': True
        }
        
    except Exception as e:
        logger.error(f"Error analyzing bag (lite mode): {e}")
        raise


def _analyze_bag_full(parser, bag_path: str, logger, console: Console) -> Dict:
    """Full analysis of bag file with progress indication - includes message iteration"""
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
                'topic_count': len(topics),
                'is_lite_mode': False
            }
            
    except Exception as e:
        logger.error(f"Error analyzing bag (full mode): {e}")
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


def _create_json_structure(input_path: str, bag_info: Dict, filtered_topics: List[str], is_lite_mode: bool) -> Dict[str, Any]:
    """Create unified JSON structure for all output formats"""
    
    # Calculate compression info
    compression = _get_compression_info(input_path)
    compression_display = compression.upper() if compression != 'none' else 'None'
    
    # Build topic details
    topic_details = []
    for topic in filtered_topics:
        stats = bag_info['stats'].get(topic, {'count': 0, 'size': 0}) if bag_info['stats'] else {}
        msg_type = bag_info['connections'].get(topic, 'Unknown')
        
        # Calculate frequency
        frequency = None
        if bag_info['duration'] and bag_info['duration'] > 0 and stats.get('count') is not None:
            frequency = stats['count'] / bag_info['duration']
        
        topic_details.append({
            'topic': topic,
            'message_type': msg_type,
            'count': stats.get('count'),
            'size': stats.get('size'),
            'frequency': frequency,
            'size_formatted': _format_size(stats['size']) if stats.get('size') is not None else None,
            'frequency_formatted': f"{frequency:.1f} Hz" if frequency is not None else None
        })
    
    # Build summary data
    summary = {
        'file_path': input_path,
        'file_name': os.path.basename(input_path),
        'absolute_path': os.path.abspath(input_path),
        'topic_count': bag_info['topic_count'],
        'total_messages': bag_info['total_messages'],
        'file_size': bag_info['file_size'],
        'total_data_size': bag_info['total_data_size'],
        'compression': compression_display,
        'duration': bag_info['duration'],
        'start_time': bag_info['start_time'],
        'end_time': bag_info['end_time'],
        'analysis_time': bag_info['analysis_time'],
        'filtered_count': len(filtered_topics),
        'is_lite_mode': is_lite_mode,
        # Formatted versions
        'file_size_formatted': _format_size(bag_info['file_size']),
        'total_data_size_formatted': _format_size(bag_info['total_data_size']) if bag_info['total_data_size'] is not None else None,
        'duration_formatted': _format_duration(bag_info['duration']) if bag_info['duration'] is not None else None,
        'avg_rate': bag_info['total_messages'] / bag_info['duration'] if bag_info['total_messages'] is not None and bag_info['duration'] and bag_info['duration'] > 0 else None,
        'avg_rate_formatted': f"{bag_info['total_messages'] / bag_info['duration']:.1f} Hz" if bag_info['total_messages'] is not None and bag_info['duration'] and bag_info['duration'] > 0 else None
    }
    
    return {
        'summary': summary,
        'topics': topic_details,
        'metadata': {
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'generator': 'rose-cli',
            'version': '1.0'
        }
    }


def _display_data(json_data: Dict[str, Any], as_format: str, verbose: bool, console: Console):
    """Display bag inspection results in specified format"""
    
    if as_format == "summary":
        _display_summary(console, json_data['summary']['file_path'], json_data, len(json_data['topics']), verbose, json_data['summary']['is_lite_mode'])
    elif as_format == "list":
        _display_list(console, json_data['summary']['file_path'], json_data, json_data['topics'], verbose, json_data['summary']['is_lite_mode'])
    else:  # table
        _display_table(console, json_data['summary']['file_path'], json_data, json_data['topics'], verbose, json_data['summary']['is_lite_mode'])


def _export_data(json_data: Dict[str, Any], as_format: str, output: str, console: Console):
    """Export bag inspection results to CSV or HTML"""
    try:
        if as_format == "csv":
            _export_to_csv(json_data, output)
            console.print(f"\n[green]Data exported to {output}[/green]")
        elif as_format == "html":
            _export_to_html(json_data, output)
            console.print(f"\n[green]Data exported to {output}[/green]")
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error exporting data: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _export_to_csv(json_data: Dict[str, Any], output_path: str):
    """Export JSON data to CSV file"""
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['topic', 'message_type', 'count', 'size', 'frequency', 'size_formatted', 'frequency_formatted']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for topic_data in json_data['topics']:
            writer.writerow(topic_data)


def _export_to_html(json_data: Dict[str, Any], output_path: str):
    """Export JSON data to HTML file"""
    summary = json_data['summary']
    
    with open(output_path, 'w') as f:
        f.write("<!DOCTYPE html>\n")
        f.write("<html>\n")
        f.write("<head>\n")
        f.write("<title>ROS Bag Inspection Report</title>\n")
        f.write("<style>\n")
        f.write("body { font-family: Arial, sans-serif; margin: 20px; }\n")
        f.write("h1 { color: #333; }\n")
        f.write("table { border-collapse: collapse; width: 100%; margin-top: 20px; }\n")
        f.write("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n")
        f.write("th { background-color: #f2f2f2; }\n")
        f.write("tr:hover { background-color: #f5f5f5; }\n")
        f.write("</style>\n")
        f.write("</head>\n")
        f.write("<body>\n")
        f.write(f"<h1>ROS Bag Inspection Report for {summary['file_name']}</h1>\n")
        f.write(f"<p>Generated on: {json_data['metadata']['generated_at']}</p>\n")
        f.write("<h2>Summary</h2>\n")
        f.write(f"<p>File: {summary['absolute_path']}</p>\n")
        f.write(f"<p>Total Topics: {summary['topic_count']}</p>\n")
        f.write(f"<p>Total Messages: {summary['total_messages']:,}</p>\n" if summary['total_messages'] is not None else "<p>Total Messages: -</p>\n")
        f.write(f"<p>File Size: {summary['file_size_formatted']}</p>\n")
        f.write(f"<p>Data Size: {summary['total_data_size_formatted']}</p>\n" if summary['total_data_size_formatted'] is not None else "<p>Data Size: -</p>\n")
        f.write(f"<p>Compression: {summary['compression']}</p>\n")
        f.write(f"<p>Duration: {summary['duration_formatted']}</p>\n" if summary['duration_formatted'] is not None else "<p>Duration: -</p>\n")
        f.write(f"<p>Average Rate: {summary['avg_rate_formatted']}</p>\n" if summary['avg_rate_formatted'] is not None else "<p>Average Rate: -</p>\n")
        
        f.write("<h2>Topics</h2>\n")
        f.write("<table>\n")
        f.write("<tr><th>Topic</th><th>Message Type</th><th>Count</th><th>Size</th><th>Frequency</th></tr>\n")
        for topic_data in json_data['topics']:
            count_str = f"{topic_data['count']:,}" if topic_data['count'] is not None else "-"
            size_str = topic_data['size_formatted'] if topic_data['size_formatted'] is not None else "-"
            freq_str = topic_data['frequency_formatted'] if topic_data['frequency_formatted'] is not None else "-"
            f.write(f"<tr><td>{topic_data['topic']}</td><td>{topic_data['message_type']}</td><td>{count_str}</td><td>{size_str}</td><td>{freq_str}</td></tr>\n")
        f.write("</table>\n")
        f.write("</body>\n")
        f.write("</html>\n")


def _display_summary(console: Console, input_path: str, json_data: Dict[str, Any], filtered_count: int, verbose: bool, is_lite_mode: bool):
    """Display summary information"""
    summary = json_data['summary']
    
    console.print(f"\n[bold cyan]Bag File Summary[/bold cyan]")
    
    if verbose:
        # Verbose mode shows full details
        console.print(f"[dim]Absolute Path:[/dim] {summary['absolute_path']}")
        console.print(f"[dim]File Name:[/dim] {summary['file_name']}")
        console.print(f"[dim]Analysis Time:[/dim] {summary['analysis_time']:.3f}s")
        console.print("-" * 80)
    else:
        # Non-verbose mode still shows basic file info
        console.print(f"[dim]File:[/dim] {summary['file_name']}")
        console.print("-" * 60)
    
    summary_data = [
        f"[bold]Topics:[/bold] {summary['topic_count']}",
    ]
    
    # Add message and data size info if available
    if summary['total_messages'] is not None:
        summary_data.append(f"[bold]Messages:[/bold] {summary['total_messages']:,}")
    else:
        summary_data.append(f"[bold]Messages:[/bold] -")
    
    summary_data.append(f"[bold]File Size:[/bold] {summary['file_size_formatted']}")
    
    if summary['total_data_size_formatted'] is not None:
        summary_data.append(f"[bold]Data Size:[/bold] {summary['total_data_size_formatted']}")
    else:
        summary_data.append(f"[bold]Data Size:[/bold] -")
    
    # Add compression information
    summary_data.append(f"[bold]Compression:[/bold] {summary['compression']}")
    
    if summary['duration_formatted']:
        summary_data.append(f"[bold]Duration:[/bold] {summary['duration_formatted']}")
        if summary['avg_rate_formatted']:
            summary_data.append(f"[bold]Avg Rate:[/bold] {summary['avg_rate_formatted']}")
        else:
            summary_data.append(f"[bold]Avg Rate:[/bold] -")
    
    if filtered_count != summary['topic_count']:
        summary_data.append(f"[bold]Filtered:[/bold] {filtered_count} topics shown")
    
    # Always show as separate lines for summary
    for item in summary_data:
        console.print(item)
    
    if verbose and summary['start_time'] and summary['end_time']:
        console.print(f"[dim]Start Time:[/dim] {summary['start_time']}")
        console.print(f"[dim]End Time:[/dim] {summary['end_time']}")


def _display_list(console: Console, input_path: str, json_data: Dict[str, Any], 
                  filtered_topics: List[Dict[str, Any]], verbose: bool, is_lite_mode: bool):
    """Display topics in list format"""
    # Always show summary first
    _display_summary(console, input_path, json_data, len(filtered_topics), verbose, is_lite_mode)
    console.print()
    
    # Show topics header in verbose mode
    if verbose:
        console.print(f"[bold cyan]Topics in {Path(input_path).name}[/bold cyan]")
        console.print(f"[dim]Total: {len(filtered_topics)} topics[/dim]")
        console.print("-" * 60)
    
    # Show topics
    for topic_data in filtered_topics:
        if is_lite_mode:
            # In lite mode, only show topic name and message type
            console.print(f"[bold]{topic_data['topic']}[/bold] | [cyan]{_format_message_type(topic_data['message_type'])}[/cyan]")
        else:
            # In full mode, show all statistics
            info_parts = [
                f"[bold]{topic_data['topic']}[/bold]",
                f"[cyan]{topic_data['count']:,} msgs[/cyan]",
                f"[green]{topic_data['size_formatted']}[/green]"
            ]
            
            # Add frequency if available
            if topic_data['frequency_formatted']:
                info_parts.append(f"[magenta]{topic_data['frequency_formatted']}[/magenta]")
            
            console.print(" | ".join(info_parts))


def _display_table(console: Console, input_path: str, json_data: Dict[str, Any], 
                   filtered_topics: List[Dict[str, Any]], verbose: bool, is_lite_mode: bool):
    """Display topics in table format"""
    # Always show summary first
    _display_summary(console, input_path, json_data, len(filtered_topics), verbose, is_lite_mode)
    console.print()
    
    # Create table
    if is_lite_mode:
        # Lite mode: only show topic and message type
        table = Table(title=f"Topics in {Path(input_path).name}", box=box.SIMPLE)
        table.add_column("Topic", style="bold", min_width=25)
        table.add_column("Message Type", style="cyan", min_width=30)
        
        for topic_data in filtered_topics:
            table.add_row(topic_data['topic'], _format_message_type(topic_data['message_type']))
        
        console.print(table)
    else:
        # Full mode: show all statistics
        table = Table(title=f"Topics in {Path(input_path).name}", box=box.SIMPLE)
        table.add_column("Topic", style="bold", min_width=25)
        table.add_column("Message Type", style="cyan", min_width=30)
        table.add_column("Count", justify="right", style="green")
        table.add_column("Size", justify="right", style="magenta")
        table.add_column("Frequency", justify="right", style="blue")
        
        for topic_data in filtered_topics:
            table.add_row(
                topic_data['topic'],
                _format_message_type(topic_data['message_type']),
                f"{topic_data['count']:,}" if topic_data['count'] is not None else "N/A",
                topic_data['size_formatted'] if topic_data['size_formatted'] is not None else "N/A",
                topic_data['frequency_formatted'] if topic_data['frequency_formatted'] is not None else "N/A"
            )
        
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


def _sort_topic_details(topic_details: List[Dict[str, Any]], sort_by: str, reverse: bool) -> List[Dict[str, Any]]:
    """Sort topic details based on specified criteria"""
    def get_sort_key(topic_data: Dict[str, Any]):
        if sort_by == "name":
            return topic_data['topic'].lower()
        elif sort_by == "type":
            return topic_data['topic'].split('/')[-1].lower()  # Sort by topic name part
        elif sort_by == "count":
            return topic_data['count'] if topic_data['count'] is not None else 0
        elif sort_by == "size":
            return topic_data['size'] if topic_data['size'] is not None else 0
        elif sort_by == "frequency":
            return topic_data['frequency'] if topic_data['frequency'] is not None else 0
        else:
            return topic_data['size'] if topic_data['size'] is not None else 0
    
    return sorted(topic_details, key=get_sort_key, reverse=reverse)


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 