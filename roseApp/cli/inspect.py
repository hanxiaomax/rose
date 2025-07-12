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
from ..core.theme import theme

# Import plotting module with error handling
try:
    from .plot import create_plot, PlottingError
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False

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
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (for csv/html formats)"),
    plot: bool = typer.Option(False, "--plot", "-p", help="Generate visualization plots"),
    plot_type: str = typer.Option("overview", "--plot-type", help="Plot type: frequency, size, count, overview (default: overview)"),
    plot_format: str = typer.Option("png", "--plot-format", help="Plot format: png, svg, pdf, html (default: png)"),
    plot_output: Optional[str] = typer.Option(None, "--plot-output", help="Plot output file path (auto-generated if not specified)")
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
    
    # Generate plots
    rose inspect demo.bag --plot --verbose
    
    # Generate specific plot type
    rose inspect demo.bag --plot --plot-type frequency --plot-format html --verbose
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
        
        # Validate plot options
        if plot:
            if not PLOTTING_AVAILABLE:
                typer.echo(f"Error: Plotting functionality requires additional dependencies.", err=True)
                typer.echo(f"Install with: pip install rose-bag[plot]", err=True)
                raise typer.Exit(code=1)
            
            if plot_type not in ["frequency", "size", "count", "overview"]:
                typer.echo(f"Error: --plot-type must be one of: frequency, size, count, overview", err=True)
                raise typer.Exit(code=1)
            
            if plot_format not in ["png", "svg", "pdf", "html"]:
                typer.echo(f"Error: --plot-format must be one of: png, svg, pdf, html", err=True)
                raise typer.Exit(code=1)
        
        # Validate output file for export formats
        if as_format in ["csv", "html"] and not output:
            typer.echo(f"Error: --output is required for {as_format} format", err=True)
            raise typer.Exit(code=1)
        
        # Initialize console
        console = Console()
        
        # Determine analysis mode - plotting requires verbose mode for statistics
        use_full_analysis = verbose or plot
        
        # Show top info message for lite mode
        if not use_full_analysis:
            console.print(f"[{theme.WARNING}]INFO: Using lightweight analysis. Use --verbose for detailed statistics.[/{theme.WARNING}]")
        
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
                console.print(f"[{theme.WARNING}]Warning: Sorting by '{sort_by}' requires --verbose mode, using name sorting instead[/{theme.WARNING}]")
                sort_by = "name"
            json_data['topics'] = sorted(json_data['topics'], key=lambda x: x['topic'].lower(), reverse=reverse)
        
        # Display or export results
        if as_format in ["csv", "html"]:
            _export_data(json_data, as_format, output, console)
        else:
            _display_data(json_data, as_format, verbose, console)
        
        # Generate plots if requested
        if plot:
            _generate_plots(json_data, plot_type, plot_format, plot_output, input_path, console)
        
        # Show bottom info message for lite mode
        if not use_full_analysis and as_format not in ["csv", "html"] and not plot:
            console.print(f"[{theme.WARNING}]INFO: Use --verbose to analyze all messages and show detailed statistics.[/{theme.WARNING}]")
        
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
    """Export topics data to HTML file with Tailwind CSS CDN - minimal, clean, compact design"""
    import time
    
    summary = json_data['summary']
    topics = json_data['topics']
    
    # Get theme colors for custom properties
    from roseApp.core.theme_parser import get_html_colors
    html_colors = get_html_colors()
    
    # Minimal HTML with Tailwind CSS CDN
    html_content = f"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROS Bag Report - {summary['file_name']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        'rose': {{
                            50: '{html_colors['background']}',
                            500: '{html_colors['primary']}',
                            600: '{html_colors['accent']}',
                            900: '{html_colors['foreground']}'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        body {{ font-family: 'Inter', sans-serif; }}
        .mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="min-h-full bg-rose-50 text-rose-900">
    <div class="max-w-7xl mx-auto p-4 sm:p-6">
        <!-- Header -->
        <div class="border-b-2 border-rose-500 pb-4 mb-6">
            <h1 class="text-2xl sm:text-3xl font-bold text-rose-500">ROS Bag Analysis</h1>
            <p class="text-sm text-gray-600 mt-1">
                <span class="font-medium">{summary['file_name']}</span> • 
                Generated {time.strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>

        <!-- Summary Table -->
        <div class="mb-8">
            <h2 class="text-lg font-semibold text-rose-500 mb-3">Summary</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white border border-gray-200 rounded-lg shadow-sm">
                    <tbody class="divide-y divide-gray-200">
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Topics</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary['topic_count']}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Messages</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary['total_messages']:,}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">File Size</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary['file_size_formatted']}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Duration</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary.get('duration_formatted', 'N/A')}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Avg Rate</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary.get('avg_rate_formatted', 'N/A')}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Compression</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{summary.get('compression', 'N/A')}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Topics Table -->
        <div>
            <h2 class="text-lg font-semibold text-rose-500 mb-3">Topics ({len(topics)})</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white border border-gray-200 rounded-lg shadow-sm">
                    <thead class="bg-rose-500">
                        <tr>
                            <th class="px-3 py-3 text-left text-xs font-semibold text-white uppercase tracking-wider">Topic</th>
                            <th class="px-3 py-3 text-left text-xs font-semibold text-white uppercase tracking-wider">Type</th>
                            <th class="px-3 py-3 text-right text-xs font-semibold text-white uppercase tracking-wider">Count</th>
                            <th class="px-3 py-3 text-right text-xs font-semibold text-white uppercase tracking-wider">Size</th>
                            <th class="px-3 py-3 text-right text-xs font-semibold text-white uppercase tracking-wider">Rate</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">"""
    
    # Add topic rows with alternating colors
    for i, topic in enumerate(topics):
        row_class = "bg-white" if i % 2 == 0 else "bg-gray-50"
        html_content += f"""
                        <tr class="{row_class} hover:bg-rose-50 transition-colors">
                            <td class="px-3 py-2 text-sm font-medium text-rose-600 mono">{topic['topic']}</td>
                            <td class="px-3 py-2 text-sm text-gray-700 mono">{topic['message_type']}</td>
                            <td class="px-3 py-2 text-sm text-right font-semibold text-gray-900">{topic['count']:,}</td>
                            <td class="px-3 py-2 text-sm text-right font-semibold text-gray-900">{topic['size_formatted']}</td>
                            <td class="px-3 py-2 text-sm text-right font-semibold text-gray-900">{topic.get('frequency_formatted', 'N/A')}</td>
                        </tr>"""
    
    html_content += f"""
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Footer -->
        <div class="mt-8 pt-6 border-t border-gray-200 text-center">
            <p class="text-xs text-gray-500">Generated by Rose ROS Bag Tool • Tailwind CSS</p>
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


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
        console.print(f"[bold {theme.INFO}]Topics in {Path(input_path).name}[/bold {theme.INFO}]")
        console.print(f"[dim]Total: {len(filtered_topics)} topics[/dim]")
        console.print("-" * 60)
    
    # Show topics
    for topic_data in filtered_topics:
        if is_lite_mode:
            # In lite mode, only show topic name and message type
            console.print(f"[bold]{topic_data['topic']}[/bold] | [{theme.INFO}]{_format_message_type(topic_data['message_type'])}[/{theme.INFO}]")
        else:
            # In full mode, show all statistics
            info_parts = [
                f"[bold]{topic_data['topic']}[/bold]",
                f"[{theme.INFO}]{topic_data['count']:,} msgs[/{theme.INFO}]",
                f"[{theme.SUCCESS}]{topic_data['size_formatted']}[/{theme.SUCCESS}]"
            ]
            
            # Add frequency if available
            if topic_data['frequency_formatted']:
                info_parts.append(f"[{theme.ACCENT}]{topic_data['frequency_formatted']}[/{theme.ACCENT}]")
            
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
        table.add_column("Message Type", style=theme.INFO, min_width=30)
        
        for topic_data in filtered_topics:
            table.add_row(topic_data['topic'], _format_message_type(topic_data['message_type']))
        
        console.print(table)
    else:
        # Full mode: show all statistics
        table = Table(title=f"Topics in {Path(input_path).name}", box=box.SIMPLE)
        table.add_column("Topic", style="bold", min_width=25)
        table.add_column("Message Type", style=theme.INFO, min_width=30)
        table.add_column("Count", justify="right", style=theme.SUCCESS)
        table.add_column("Size", justify="right", style=theme.ACCENT)
        table.add_column("Frequency", justify="right", style=theme.SECONDARY)
        
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


def _generate_plots(json_data: Dict[str, Any], plot_type: str, plot_format: str, 
                   plot_output: Optional[str], input_path: str, console: Console):
    """Generate visualization plots"""
    try:
        # Auto-generate output path if not specified
        if not plot_output:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            extension = "html" if plot_format == "html" else plot_format
            plot_output = f"{base_name}_{plot_type}_plot.{extension}"
        
        console.print(f"\n[cyan]Generating {plot_type} plot...[/cyan]")
        
        # Create the plot
        output_file = create_plot(json_data, plot_type, plot_output, plot_format)
        
        console.print(f"[green]Plot saved to: {output_file}[/green]")
        
        # Show additional info for HTML plots
        if plot_format == "html":
            console.print(f"[dim]Open the HTML file in your browser to view the interactive plot[/dim]")
        
    except PlottingError as e:
        console.print(f"[red]Plot generation failed: {str(e)}[/red]")
        # Don't exit, just continue without plotting
    except Exception as e:
        console.print(f"[red]Unexpected error during plot generation: {str(e)}[/red]")
        # Don't exit, just continue without plotting


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 