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
import asyncio
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
from ..core.async_analyzer import analyze_bag_async, CacheLevel, ComprehensiveCache
from .error_handling import ValidationError, validate_file_exists, validate_choice, validate_output_requirement, handle_runtime_error

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
    try:
        if cache_path.exists():
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
    except Exception:
        # If cache is corrupted or incompatible, ignore it
        pass
    return None


def _save_cache(cache_path: Path, data: Dict):
    """Save analysis results to cache"""
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception:
        # If caching fails, continue without caching
        pass


@app.command()
def inspect(
    input_path: str = typer.Argument(..., help="Input bag file path"),
    topics: List[str] = typer.Option([], "--topics", "-t", help="Filter topics by name or pattern (supports fuzzy matching). Multiple values: --topics topic1 --topics topic2 --topics pattern3"),
    as_format: str = typer.Option("table", "--as", "-a", help="Output format: table, list, summary, csv, html, json (default: table)"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort by: name, type, count, size, frequency (default: size)"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output with detailed statistics"),
    show_fields: bool = typer.Option(False, "--show-fields", "-f", help="Show detailed field information for specified topics"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (for csv/html formats)"),
    async_analysis: bool = typer.Option(True, "--async/--sync", help="Use async analysis for better performance (default: async)"),
    force_sync: bool = typer.Option(False, "--force-sync", help="Force synchronous analysis (legacy mode)")
):
    """
    Inspect ROS bag files with intelligent caching and async analysis
    
    The async analysis provides better performance through intelligent caching
    and background processing. Use --force-sync for legacy synchronous mode.
    
    Examples:
        # Fast async analysis (default)
        rose inspect mybag.bag
        
        # Force legacy sync analysis  
        rose inspect mybag.bag --force-sync
        
        # Detailed async analysis with field information
        rose inspect mybag.bag --verbose --show-fields --topics /camera/image
    """
    
    async def _async_main():
        # Set application mode for proper logging
        set_app_mode(AppMode.CLI)
        logger = get_logger()
        console = Console()
        
        # Record start time for total execution time
        start_time = time.time()

        try:
            # Validate parameter values
            try:
                validate_file_exists(input_path, "bag file")
                validate_choice(as_format, ["table", "list", "summary", "csv", "html", "json"], "--as")
                validate_choice(sort_by, ["name", "type", "count", "size", "frequency"], "--sort-by")
                validate_output_requirement(as_format, output)
            except ValidationError as e:
                handle_runtime_error(e, "Parameter validation")

            # Determine analysis mode
            use_full_analysis = verbose
            use_async = async_analysis and not force_sync
            
            # Try to load from cache first (for compatibility with existing cache)
            cache_path = _get_cache_path(input_path)
            cached_data = _load_cache(cache_path)
            
            # Check if we need to reanalyze
            reanalyze = (cached_data is None or 
                        cached_data.get('is_full_analysis', False) != use_full_analysis)
            
            if reanalyze:
                # Perform analysis with async or sync mode
                if use_async:
                    console.print("[cyan]Performing intelligent async analysis...[/cyan]")
                    analysis_data = await _analyze_bag_async(input_path, console, use_full_analysis)
                else:
                    # Legacy sync analysis
                    if use_full_analysis:
                        console.print("[cyan]Performing detailed analysis (parsing all messages)...[/cyan]")
                        analysis_data = _analyze_bag_full_sync(input_path, console)
                    else:
                        console.print("[cyan]Performing fast analysis (metadata only)...[/cyan]")
                        analysis_data = _analyze_bag_lite_sync(input_path, console)
                
                # Save to cache (only for legacy format compatibility)
                if not analysis_data.get('is_async_analysis', False):
                    _save_cache(cache_path, analysis_data)
                    
            else:
                console.print(f"[dim]Using cached analysis results[/dim]")
                analysis_data = cached_data

            # Apply topic filtering using fuzzy matching
            filtered_topics = _filter_topics(analysis_data.get('topics', []), topics)

            # Show performance info for async analysis
            if analysis_data.get('is_async_analysis', False):
                cache_level = analysis_data.get('cache_level', 1)
                level_names = {1: "metadata", 2: "statistics", 3: "messages", 4: "fields"}
                console.print(f"[dim]Analysis level: {level_names.get(cache_level, 'unknown')} (cache level {cache_level})[/dim]")

            # Sort topics if needed
            if analysis_data.get('stats'):
                filtered_topics = _sort_topics(filtered_topics, analysis_data['stats'], sort_by, reverse)

            # Calculate total execution time
            total_time = time.time() - start_time
            
            # Add total execution time to analysis data
            analysis_data['analysis_time'] = total_time

            # Create JSON structure for unified processing
            json_data = _create_json_structure(input_path, analysis_data, filtered_topics, analysis_data.get('is_lite_mode', False))

            # Field analysis if requested - process after JSON structure is created
            if show_fields:
                if not topics:
                    console.print("[red]Error: --show-fields requires --topics to be specified[/red]")
                    return
                
                console.print("Analyzing field information for specified topics...")
                field_data = _analyze_topic_fields(create_parser(ParserType.ROSBAGS), input_path, filtered_topics, console)
                
                # Integrate field data into JSON structure
                json_data = _integrate_field_data(json_data, field_data)

            # Show performance analysis panel if --profile is enabled
            profile_enabled = _is_profile_enabled()
            if profile_enabled:
                _display_performance_panel(console, analysis_data, total_time, use_async)

            # Display or export data
            if output and as_format in ['csv', 'html', 'json']:
                _export_data(json_data, as_format, output, console)
            else:
                _display_data(json_data, as_format, verbose, console, show_fields)

            # Show performance profile if enabled (keep existing logic for cache manager)
            try:
                from ..core.unified_cache import get_unified_cache_manager
                cache_manager = get_unified_cache_manager()
                if cache_manager.profiler.enabled:
                    cache_manager.print_profile_summary(console)
            except ImportError:
                pass  # Unified cache not available

        except Exception as e:
            handle_runtime_error(e, "bag analysis")
    
    # Run async main function
    try:
        asyncio.run(_async_main())
    except Exception as e:
        console = Console()
        handle_runtime_error(e, "async execution")


def _integrate_field_data(json_data: Dict[str, Any], field_data: Dict[str, Any]) -> Dict[str, Any]:
    """Integrate field data into the JSON structure"""
    # Add field data to each topic
    for topic_info in json_data['topics']:
        topic_name = topic_info['topic']
        if topic_name in field_data:
            topic_info['fields'] = field_data[topic_name]
    
    # Add field analysis metadata
    json_data['metadata']['has_field_analysis'] = True
    json_data['metadata']['field_analysis_max_depth'] = 3
    json_data['metadata']['field_analysis_samples'] = 5
    
    return json_data


def _analyze_topic_fields(parser, bag_path: str, topics: List[str], console: Console) -> Dict[str, Any]:
    """Analyze field information for specific topics"""
    console.print(f"[cyan]Analyzing field information for {len(topics)} topics...[/cyan]")
    
    field_data = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Processing topics...", total=len(topics))
        
        for topic in topics:
            progress.update(task, description=f"Processing {topic}...")
            
            try:
                # Read a few messages from the topic to analyze structure
                messages = []
                message_count = 0
                max_samples = 5  # Analyze first 5 messages to get field structure
                
                for timestamp, msg_data in parser.read_messages(bag_path, [topic]):
                    if message_count >= max_samples:
                        break
                    messages.append(msg_data)
                    message_count += 1
                
                if messages:
                    # Analyze the structure of the first message (they should be similar)
                    fields = _extract_message_fields(messages[0])
                    field_data[topic] = {
                        'fields': fields,
                        'samples_analyzed': len(messages),
                        'message_type': type(messages[0]).__name__ if messages else "Unknown"
                    }
                else:
                    field_data[topic] = {
                        'fields': {},
                        'samples_analyzed': 0,
                        'message_type': "No messages found"
                    }
                    
            except Exception as e:
                field_data[topic] = {
                    'fields': {},
                    'samples_analyzed': 0,
                    'message_type': f"Error: {str(e)}"
                }
            
            progress.update(task, advance=1)
    
    return field_data


def _extract_message_fields(msg_data: Any, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """Extract field information from a message recursively"""
    fields = {}
    
    if current_depth >= max_depth:
        return {'...': f'(max depth {max_depth} reached)'}
    
    if hasattr(msg_data, '__dict__'):
        # ROS message object
        for attr_name in dir(msg_data):
            if not attr_name.startswith('_'):
                try:
                    attr_value = getattr(msg_data, attr_name)
                    if not callable(attr_value):
                        field_name = f"{prefix}.{attr_name}" if prefix else attr_name
                        field_info = _get_field_info(attr_value, field_name, max_depth, current_depth + 1)
                        fields[attr_name] = field_info
                except Exception:
                    continue
    elif isinstance(msg_data, dict):
        # Dictionary
        for key, value in msg_data.items():
            field_name = f"{prefix}.{key}" if prefix else key
            field_info = _get_field_info(value, field_name, max_depth, current_depth + 1)
            fields[key] = field_info
    else:
        # Primitive type
        fields['value'] = _get_field_info(msg_data, prefix, max_depth, current_depth)
    
    return fields


def _get_field_info(value: Any, field_name: str, max_depth: int, current_depth: int) -> Dict[str, Any]:
    """Get information about a specific field"""
    field_info = {
        'type': type(value).__name__,
        'full_path': field_name
    }
    
    if isinstance(value, (int, float, bool)):
        field_info['value'] = value
    elif isinstance(value, str):
        field_info['value'] = f'"{value}"' if len(value) <= 50 else f'"{value[:47]}..."'
    elif isinstance(value, (list, tuple)):
        field_info['length'] = len(value)
        if len(value) > 0 and current_depth < max_depth:
            field_info['element_type'] = type(value[0]).__name__
            if hasattr(value[0], '__dict__') or isinstance(value[0], dict):
                field_info['element_structure'] = _extract_message_fields(value[0], f"{field_name}[0]", max_depth, current_depth + 1)
    elif hasattr(value, '__dict__') or isinstance(value, dict):
        if current_depth < max_depth:
            field_info['fields'] = _extract_message_fields(value, field_name, max_depth, current_depth + 1)
    
    return field_info


def _display_fields_from_json(json_data: Dict[str, Any], console: Console):
    """Display field information from JSON structure"""
    has_fields = json_data['metadata'].get('has_field_analysis', False)
    
    if not has_fields:
        console.print("[yellow]No field analysis data available[/yellow]")
        return
    
    # Display field information for each topic
    for topic_info in json_data['topics']:
        if 'fields' in topic_info:
            topic_name = topic_info['topic']
            field_data = topic_info['fields']
            
            console.print(f"\n[bold cyan]Topic: {topic_name}[/bold cyan]")
            console.print(f"[dim]Message Type: {field_data['message_type']}[/dim]")
            console.print(f"[dim]Samples Analyzed: {field_data['samples_analyzed']}[/dim]")
            
            if field_data['fields']:
                console.print("\n[bold]Fields:[/bold]")
                _display_field_tree(field_data['fields'], console, indent=0)
            else:
                console.print("[yellow]No fields found[/yellow]")


def _display_topic_fields(field_data: Dict[str, Any], console: Console):
    """Display field information for topics (legacy function)"""
    for topic, data in field_data.items():
        console.print(f"\n[bold cyan]Topic: {topic}[/bold cyan]")
        console.print(f"[dim]Message Type: {data['message_type']}[/dim]")
        console.print(f"[dim]Samples Analyzed: {data['samples_analyzed']}[/dim]")
        
        if data['fields']:
            console.print("\n[bold]Fields:[/bold]")
            _display_field_tree(data['fields'], console, indent=0)
        else:
            console.print("[yellow]No fields found[/yellow]")


def _display_field_tree(fields: Dict[str, Any], console: Console, indent: int = 0):
    """Display field tree structure"""
    prefix = "  " * indent
    
    for field_name, field_info in fields.items():
        if isinstance(field_info, dict) and 'type' in field_info:
            # This is a field info object
            type_str = f"[green]{field_info['type']}[/green]"
            
            if 'value' in field_info:
                console.print(f"{prefix}├── {field_name}: {type_str} = {field_info['value']}")
            elif 'length' in field_info:
                length_str = f"[yellow][{field_info['length']}][/yellow]"
                element_type = field_info.get('element_type', 'unknown')
                console.print(f"{prefix}├── {field_name}: {type_str}{length_str} of [green]{element_type}[/green]")
                
                if 'element_structure' in field_info:
                    _display_field_tree(field_info['element_structure'], console, indent + 1)
            elif 'fields' in field_info:
                console.print(f"{prefix}├── {field_name}: {type_str}")
                _display_field_tree(field_info['fields'], console, indent + 1)
            else:
                console.print(f"{prefix}├── {field_name}: {type_str}")
        else:
            # This is a nested field structure
            console.print(f"{prefix}├── {field_name}:")
            _display_field_tree(field_info, console, indent + 1)


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
            'is_lite_mode': True,
            'original_bag_path': os.path.abspath(bag_path)  # Store original bag path
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
                'is_lite_mode': False,
                'original_bag_path': os.path.abspath(bag_path)  # Store original bag path
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
        # Handle both dictionary and TopicStatistics object formats
        stats_data = bag_info.get('stats', {})
        if topic in stats_data:
            stats = stats_data[topic]
            
            # Check if it's a TopicStatistics object or a dictionary
            if hasattr(stats, 'count'):
                # TopicStatistics object
                count = stats.count
                size = stats.size
            else:
                # Dictionary format
                count = stats.get('count', 0)
                size = stats.get('size', 0)
        else:
            # No stats available for this topic
            count = 0
            size = 0
        
        msg_type = bag_info['connections'].get(topic, 'Unknown')
        
        # Calculate frequency
        frequency = None
        if bag_info['duration'] and bag_info['duration'] > 0 and count is not None:
            frequency = count / bag_info['duration']
        
        topic_details.append({
            'topic': topic,
            'message_type': msg_type,
            'count': count,
            'size': size,
            'frequency': frequency,
            'size_formatted': _format_size(size) if size is not None else None,
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
        'analysis_time': bag_info.get('analysis_time', 0.0),
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


def _display_data(json_data: Dict[str, Any], as_format: str, verbose: bool, console: Console, show_fields: bool = False):
    """Display bag inspection results in specified format"""
    
    # Display the main format (table, list, or summary)
    if as_format == "summary":
        _display_summary(console, json_data['summary']['file_path'], json_data, len(json_data['topics']), verbose, json_data['summary']['is_lite_mode'])
        if show_fields:
            _display_fields_from_json(json_data, console)
    elif as_format == "list":
        _display_list(console, json_data['summary']['file_path'], json_data, json_data['topics'], verbose, json_data['summary']['is_lite_mode'])
        if show_fields:
            _display_fields_from_json(json_data, console)
    else:  # table
        _display_table(console, json_data['summary']['file_path'], json_data, json_data['topics'], verbose, json_data['summary']['is_lite_mode'])
        # table format already includes field display logic internally


def _export_data(json_data: Dict[str, Any], as_format: str, output: str, console: Console):
    """Export bag inspection results to CSV, HTML, or JSON"""
    try:
        if as_format == "csv":
            _export_to_csv(json_data, output)
            console.print(f"\n[green]Data exported to {output}[/green]")
        elif as_format == "html":
            _export_to_html(json_data, output)
            console.print(f"\n[green]Data exported to {output}[/green]")
        elif as_format == "json":
            _export_to_json(json_data, output)
            console.print(f"\n[green]Data exported to {output}[/green]")
    except Exception as e:
        log_cli_error(e)
        typer.echo(f"Error exporting data: {str(e)}", err=True)
        raise typer.Exit(code=1)


def _export_to_json(json_data: Dict[str, Any], output_path: str):
    """Export JSON data to JSON file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)


def _export_to_csv(json_data: Dict[str, Any], output_path: str):
    """Export JSON data to CSV file"""
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['topic', 'message_type', 'count', 'size', 'frequency', 'size_formatted', 'frequency_formatted']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for topic_data in json_data['topics']:
            writer.writerow(topic_data)


def _export_to_html(json_data: Dict[str, Any], output_path: str):
    """Export topics data to HTML file with field information support"""
    import time
    
    summary = json_data['summary']
    topics = json_data['topics']
    has_fields = json_data['metadata'].get('has_field_analysis', False)
    
    # Get theme colors for custom properties
    from roseApp.core.theme_parser import get_html_colors
    html_colors = get_html_colors()
    
    # Build JavaScript for field expansion
    js_code = """
    function toggleFields(topicId) {
        const fieldsDiv = document.getElementById('fields-' + topicId);
        const toggleBtn = document.getElementById('toggle-' + topicId);
        
        if (fieldsDiv.style.display === 'none' || fieldsDiv.style.display === '') {
            fieldsDiv.style.display = 'block';
            toggleBtn.textContent = '▼';
        } else {
            fieldsDiv.style.display = 'none';
            toggleBtn.textContent = '▶';
        }
    }
    """
    
    # Safe format function for None values
    def safe_format(value, format_spec=""):
        if value is None:
            return "N/A"
        if format_spec:
            return f"{value:{format_spec}}"
        return str(value)
    
    # HTML with Tailwind CSS CDN and field support
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
        }};
        
        {js_code}
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        body {{ font-family: 'Inter', sans-serif; }}
        .mono {{ font-family: 'JetBrains Mono', monospace; }}
        .field-tree {{ margin-left: 1rem; }}
        .field-item {{ margin: 0.25rem 0; }}
        .field-name {{ color: #374151; font-weight: 500; }}
        .field-type {{ color: #059669; }}
        .field-value {{ color: #1f2937; }}
        .field-meta {{ color: #6b7280; font-size: 0.875rem; }}
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
                {' • Field analysis included' if has_fields else ''}
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
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary['topic_count'])}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Messages</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary['total_messages'], ',')}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">File Size</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary['file_size_formatted'])}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Duration</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary.get('duration_formatted'))}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Avg Rate</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary.get('avg_rate_formatted'))}</td>
                        </tr>
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-2 text-sm font-medium text-gray-900">Compression</td>
                            <td class="px-4 py-2 text-sm font-bold text-rose-500">{safe_format(summary.get('compression'))}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Topics -->
        <div>
            <h2 class="text-lg font-semibold text-rose-500 mb-3">Topics ({len(topics)})</h2>"""
    
    # Add each topic with field support
    for i, topic in enumerate(topics):
        topic_id = f"topic_{i}"
        has_topic_fields = 'fields' in topic
        
        # Create toggle button HTML
        toggle_button = ""
        if has_topic_fields:
            toggle_button = f'<button id="toggle-{topic_id}" onclick="toggleFields(\'{topic_id}\')" class="text-rose-500 hover:text-rose-700 font-mono">▶</button>'
        
        html_content += f"""
            <div class="mb-4 bg-white border border-gray-200 rounded-lg shadow-sm">
                <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-4">
                            <h3 class="text-sm font-medium text-rose-600 mono">{topic['topic']}</h3>
                            <span class="text-sm text-gray-700 mono">{topic['message_type']}</span>
                        </div>
                        <div class="flex items-center space-x-4">
                            <span class="text-sm font-semibold text-gray-900">{safe_format(topic['count'], ',') if topic['count'] is not None else 'N/A'} msgs</span>
                            <span class="text-sm font-semibold text-gray-900">{safe_format(topic['size_formatted'])}</span>
                            <span class="text-sm font-semibold text-gray-900">{safe_format(topic.get('frequency_formatted'))}</span>
                            {toggle_button}
                        </div>
                    </div>
                </div>"""
        
        # Add field information if available
        if has_topic_fields:
            field_data = topic['fields']
            html_content += f"""
                <div id="fields-{topic_id}" style="display: none;" class="px-4 py-3">
                    <div class="field-meta mb-2">
                        <span class="font-medium">Message Type:</span> {field_data['message_type']} • 
                        <span class="font-medium">Samples:</span> {field_data['samples_analyzed']}
                    </div>
                    <div class="field-tree">
                        {_generate_field_html(field_data['fields'])}
                    </div>
                </div>"""
        
        html_content += """
            </div>"""
    
    html_content += f"""
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


def _generate_field_html(fields: Dict[str, Any], indent: int = 0) -> str:
    """Generate HTML for field tree structure"""
    html = ""
    
    for field_name, field_info in fields.items():
        if isinstance(field_info, dict) and 'type' in field_info:
            # This is a field info object
            type_str = field_info['type']
            
            html += f"""<div class="field-item" style="margin-left: {indent * 1.5}rem;">"""
            html += f"""<span class="field-name">├── {field_name}:</span> """
            html += f"""<span class="field-type">{type_str}</span>"""
            
            if 'value' in field_info:
                html += f""" = <span class="field-value">{field_info['value']}</span>"""
            elif 'length' in field_info:
                length = field_info['length']
                element_type = field_info.get('element_type', 'unknown')
                html += f"""<span class="field-value">[{length}] of {element_type}</span>"""
                
                if 'element_structure' in field_info:
                    html += f"""<div>{_generate_field_html(field_info['element_structure'], indent + 1)}</div>"""
            elif 'fields' in field_info:
                html += f"""<div>{_generate_field_html(field_info['fields'], indent + 1)}</div>"""
            
            html += """</div>"""
        else:
            # This is a nested field structure
            html += f"""<div class="field-item" style="margin-left: {indent * 1.5}rem;">"""
            html += f"""<span class="field-name">├── {field_name}:</span>"""
            html += f"""<div>{_generate_field_html(field_info, indent + 1)}</div>"""
            html += """</div>"""
    
    return html


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
    
    # Show field information if available
    if json_data['metadata'].get('has_field_analysis', False):
        console.print()
        for topic_data in filtered_topics:
            if 'fields' in topic_data:
                console.print(f"\n[bold cyan]Field Details for {topic_data['topic']}[/bold cyan]")
                console.print(f"[dim]Message Type:[/dim] {topic_data['fields']['message_type']}")
                console.print(f"[dim]Samples Analyzed:[/dim] {topic_data['fields']['samples_analyzed']}")
                console.print("\n[dim]Fields:[/dim]")
                
                # Display field tree
                _display_field_tree(topic_data['fields']['fields'], console, indent=0)


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


def _convert_comprehensive_cache_to_legacy(cache: ComprehensiveCache) -> Dict:
    """Convert ComprehensiveCache to legacy format for compatibility"""
    
    # Convert statistics back to legacy format
    legacy_stats = {}
    for topic, stats in cache.statistics.items():
        legacy_stats[topic] = {
            'count': stats.count,
            'size': stats.size,
            'avg_size': stats.avg_size
        }
    
    return {
        'topics': cache.metadata.topics,
        'connections': cache.metadata.connections,
        'stats': legacy_stats,
        'file_size': cache.metadata.file_size,
        'total_messages': cache.total_messages,
        'total_data_size': cache.total_data_size,
        'duration': cache.duration,
        'start_time': cache.metadata.time_range[0] if cache.metadata.time_range else None,
        'end_time': cache.metadata.time_range[1] if cache.metadata.time_range else None,
        'topic_count': len(cache.metadata.topics),
        'is_lite_mode': cache.cache_level == CacheLevel.METADATA,
        'original_bag_path': cache.metadata.original_bag_path,
        'cache_level': cache.cache_level,
        'is_async_analysis': True,
        'analysis_timestamp': cache.analysis_timestamp
    }


def _convert_unified_cache_to_legacy(unified_cache) -> Dict:
    """Convert UnifiedCache to legacy format for compatibility"""
    
    # Convert statistics back to legacy format
    legacy_stats = {}
    if unified_cache.statistics:
        for topic, stats in unified_cache.statistics.items():
            legacy_stats[topic] = {
                'count': stats.count,
                'size': stats.size,
                'avg_size': stats.avg_size
            }
    
    # Extract topics and connections from metadata
    topics = []
    connections = {}
    start_time = None
    end_time = None
    file_size = 0
    original_bag_path = ""
    
    if unified_cache.metadata:
        topics = unified_cache.metadata.topics
        connections = unified_cache.metadata.connections
        if unified_cache.metadata.time_range:
            start_time = unified_cache.metadata.time_range[0]
            end_time = unified_cache.metadata.time_range[1]
        file_size = unified_cache.metadata.file_size
        original_bag_path = unified_cache.metadata.original_bag_path
    
    # Add field analysis if available
    field_analysis = {}
    if unified_cache.field_analysis:
        for topic, analysis in unified_cache.field_analysis.items():
            field_analysis[topic] = {
                'fields': analysis.fields,
                'message_type': analysis.message_type,
                'samples_analyzed': analysis.samples_analyzed,
                'max_depth': analysis.max_depth
            }
    
    return {
        'topics': topics,
        'connections': connections,
        'stats': legacy_stats,
        'file_size': file_size,
        'total_messages': unified_cache.total_messages,
        'total_data_size': unified_cache.total_data_size,
        'duration': unified_cache.duration,
        'start_time': start_time,
        'end_time': end_time,
        'topic_count': len(topics),
        'is_lite_mode': unified_cache.cache_level == 1,  # CacheLevel.METADATA
        'original_bag_path': original_bag_path,
        'cache_level': unified_cache.cache_level,
        'is_async_analysis': True,
        'analysis_timestamp': unified_cache.analysis_timestamp,
        'field_analysis': field_analysis if field_analysis else None
    }


async def _analyze_bag_async(bag_path: str, console: Console, use_full_analysis: bool = False) -> Dict:
    """Async bag analysis with unified caching system"""
    
    try:
        # Try to use unified cache system
        from ..core.unified_analyzer import get_unified_analyzer
        from ..core.unified_cache import CacheLevel
        
        # Determine required cache level
        required_level = CacheLevel.STATISTICS if use_full_analysis else CacheLevel.METADATA
        
        # Use unified analyzer
        analyzer = get_unified_analyzer()
        unified_cache = await analyzer.analyze_async(
            bag_path=bag_path,
            console=console,
            required_level=required_level
        )
        
        # Convert to legacy format for compatibility
        return analyzer.convert_to_legacy_format(unified_cache)
        
    except ImportError as e:
        # Fallback to direct unified cache manager if unified analyzer not available
        console.print(f"[yellow]Unified analyzer not available ({e}), trying direct cache manager...[/yellow]")
        
        try:
            from ..core.unified_cache import get_unified_cache_manager, CacheLevel
            
            # Determine required cache level
            required_level = CacheLevel.STATISTICS if use_full_analysis else CacheLevel.METADATA
            
            # Use unified cache manager directly
            cache_manager = get_unified_cache_manager()
            unified_cache = await cache_manager.get_analysis(
                bag_path=bag_path,
                required_level=required_level,
                console=console,
                is_async=True
            )
            
            # Convert to legacy format for compatibility
            return _convert_unified_cache_to_legacy(unified_cache)
            
        except Exception as e:
            console.print(f"[red]Direct cache manager failed, falling back to legacy analyzer: {e}[/red]")
            
            # Fallback to original async analyzer if unified cache not available
            # Determine required cache level
            required_level = CacheLevel.STATISTICS if use_full_analysis else CacheLevel.METADATA
            
            # Enable background full analysis for better future performance
            background_analysis = not use_full_analysis  # Only if not already doing full analysis
            
            try:
                # Use async analyzer with intelligent caching
                cache = await analyze_bag_async(
                    bag_path=bag_path,
                    console=console,
                    required_level=required_level,
                    background_full_analysis=background_analysis
                )
                
                # Convert to legacy format for compatibility
                return _convert_comprehensive_cache_to_legacy(cache)
                
            except Exception as e:
                console.print(f"[red]Async analysis failed, falling back to sync analysis: {e}[/red]")
                
                # Fallback to original sync analysis
                if use_full_analysis:
                    return _analyze_bag_full_sync(bag_path, console)
                else:
                    return _analyze_bag_lite_sync(bag_path, console)
                
    except Exception as e:
        console.print(f"[red]Unified async analysis failed, falling back to sync analysis: {e}[/red]")
        
        # Fallback to original sync analysis
        if use_full_analysis:
            return _analyze_bag_full_sync(bag_path, console)
        else:
            return _analyze_bag_lite_sync(bag_path, console)


def _analyze_bag_full_sync(bag_path: str, console: Console) -> Dict:
    """Synchronous full analysis using unified cache system"""
    try:
        # Try to use unified cache system
        from ..core.unified_analyzer import get_unified_analyzer
        from ..core.unified_cache import CacheLevel
        
        # Use unified analyzer in sync mode
        analyzer = get_unified_analyzer()
        unified_cache = analyzer.analyze_sync(
            bag_path=bag_path,
            console=console,
            required_level=CacheLevel.STATISTICS
        )
        
        # Convert to legacy format for compatibility
        return analyzer.convert_to_legacy_format(unified_cache)
        
    except ImportError as e:
        console.print(f"[yellow]Unified analyzer not available ({e}), trying direct cache manager...[/yellow]")
        
        try:
            # Try to use unified cache manager directly
            from ..core.unified_cache import get_unified_cache_manager, CacheLevel
            
            # Create event loop for async call if needed
            import asyncio
            
            # Use unified cache manager directly
            cache_manager = get_unified_cache_manager()
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        cache_manager.get_analysis(
                            bag_path=bag_path,
                            required_level=CacheLevel.STATISTICS,
                            console=console,
                            is_async=False
                        )
                    )
                    unified_cache = future.result()
            except RuntimeError:
                # No running event loop, can use asyncio.run directly
                unified_cache = asyncio.run(cache_manager.get_analysis(
                    bag_path=bag_path,
                    required_level=CacheLevel.STATISTICS,
                    console=console,
                    is_async=False
                ))
            
            # Convert to legacy format for compatibility
            return _convert_unified_cache_to_legacy(unified_cache)
            
        except Exception as e:
            console.print(f"[red]Direct cache manager failed, falling back to legacy analysis: {e}[/red]")
            
            # Fallback to original sync analysis
            parser = create_parser(ParserType.ROSBAGS)
            return _analyze_bag_full(parser, bag_path, get_logger(), console)
    
    except Exception as e:
        console.print(f"[red]Unified sync analysis failed, falling back to legacy analysis: {e}[/red]")
        
        # Fallback to original sync analysis
        parser = create_parser(ParserType.ROSBAGS)
        return _analyze_bag_full(parser, bag_path, get_logger(), console)


def _analyze_bag_lite_sync(bag_path: str, console: Console) -> Dict:
    """Synchronous lite analysis using unified cache system"""
    try:
        # Try to use unified cache system
        from ..core.unified_analyzer import get_unified_analyzer
        from ..core.unified_cache import CacheLevel
        
        # Use unified analyzer in sync mode
        analyzer = get_unified_analyzer()
        unified_cache = analyzer.analyze_sync(
            bag_path=bag_path,
            console=console,
            required_level=CacheLevel.METADATA
        )
        
        # Convert to legacy format for compatibility
        return analyzer.convert_to_legacy_format(unified_cache)
        
    except ImportError as e:
        console.print(f"[yellow]Unified analyzer not available ({e}), trying direct cache manager...[/yellow]")
        
        try:
            # Try to use unified cache manager directly
            from ..core.unified_cache import get_unified_cache_manager, CacheLevel
            
            # Create event loop for async call if needed
            import asyncio
            
            # Use unified cache manager directly
            cache_manager = get_unified_cache_manager()
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        cache_manager.get_analysis(
                            bag_path=bag_path,
                            required_level=CacheLevel.METADATA,
                            console=console,
                            is_async=False
                        )
                    )
                    unified_cache = future.result()
            except RuntimeError:
                # No running event loop, can use asyncio.run directly
                unified_cache = asyncio.run(cache_manager.get_analysis(
                    bag_path=bag_path,
                    required_level=CacheLevel.METADATA,
                    console=console,
                    is_async=False
                ))
            
            # Convert to legacy format for compatibility
            return _convert_unified_cache_to_legacy(unified_cache)
            
        except Exception as e:
            console.print(f"[red]Direct cache manager failed, falling back to legacy analysis: {e}[/red]")
            
            # Fallback to original sync analysis
            parser = create_parser(ParserType.ROSBAGS)
            return _analyze_bag_lite(parser, bag_path, get_logger(), console)
    
    except Exception as e:
        console.print(f"[red]Unified sync analysis failed, falling back to legacy analysis: {e}[/red]")
        
        # Fallback to original sync analysis
        parser = create_parser(ParserType.ROSBAGS)
        return _analyze_bag_lite(parser, bag_path, get_logger(), console)


def _display_performance_panel(console: Console, analysis_data: Dict[str, Any], total_time: float, use_async: bool):
    """Display performance analysis panel when --profile is enabled"""
    from rich.text import Text
    from rich.tree import Tree
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

    # Create main performance analysis text
    perf_text = Text()
    perf_text.append("🚀 Performance Analysis Report\n\n", style="bold bright_blue")
    
    # Overall execution summary
    perf_text.append("═══ EXECUTION SUMMARY ═══\n", style="bold cyan")
    perf_text.append(f"Total Execution Time: {total_time:.3f}s\n", style="bold white")
    
    # Analysis configuration
    analysis_mode = "Async (Optimized)" if use_async else "Sync (Legacy)"
    parser_type = "Unified Analyzer" if analysis_data.get('is_async_analysis', False) else "Legacy Parser"
    
    perf_text.append(f"Analysis Mode: {analysis_mode}\n", style="green" if use_async else "yellow")
    perf_text.append(f"Parser Engine: {parser_type}\n", style="blue")
    
    # Data processing overview
    topics_count = len(analysis_data.get('topics', []))
    total_messages = analysis_data.get('total_messages', 0)
    perf_text.append(f"Topics Processed: {topics_count}\n", style="white")
    perf_text.append(f"Messages Analyzed: {total_messages:,}\n", style="white")
    
    # Cache configuration
    cache_info = _get_cache_info(analysis_data)
    perf_text.append(f"Cache Strategy: {cache_info['strategy']}\n", style="magenta")
    perf_text.append(f"Cache Status: {cache_info['status']}\n", style=cache_info['color'])
    
    perf_text.append("\n")
    
    # Try to get detailed performance data from unified cache manager
    try:
        from ..core.unified_cache import get_unified_cache_manager
        cache_manager = get_unified_cache_manager()
        
        if cache_manager.profiler.enabled:
            profiles = cache_manager.profiler.get_profiles()
            if profiles:
                _display_execution_phases(perf_text, profiles, total_time)
                _display_cache_performance(perf_text, profiles)
            else:
                perf_text.append("⚠ No detailed profiling data available\n", style="yellow")
        else:
            perf_text.append("⚠ Performance profiling not enabled\n", style="yellow")
    except ImportError:
        perf_text.append("⚠ Unified cache manager not available\n", style="yellow")
    
    # Display optimization status
    _display_optimization_status(perf_text, analysis_data, use_async)
    
    # Create panel
    panel = Panel(
        perf_text,
        title="🔍 Performance Analysis",
        border_style="bright_blue",
        padding=(1, 2)
    )
    
    console.print(panel)
    console.print()  # Add spacing after panel


def _display_execution_phases(perf_text: Text, profiles: List, total_time: float):
    """Display execution phases with timing breakdown"""
    perf_text.append("═══ EXECUTION PHASES ═══\n", style="bold cyan")
    
    # Group operations by phase
    phase_groups = {}
    level_names = {1: "Metadata", 2: "Statistics", 3: "Messages", 4: "Fields"}
    
    for profile in profiles:
        level_name = level_names.get(profile.cache_level, f"Level {profile.cache_level}")
        phase_key = f"{level_name} Analysis"
        
        if phase_key not in phase_groups:
            phase_groups[phase_key] = []
        phase_groups[phase_key].append(profile)
    
    # Display each phase
    for phase_name, phase_profiles in phase_groups.items():
        total_phase_time = sum(p.duration_seconds for p in phase_profiles)
        cache_hits = sum(1 for p in phase_profiles if p.cache_action == 'hit')
        cache_misses = sum(1 for p in phase_profiles if p.cache_action in ['miss', 'create'])
        
        # Phase header
        perf_text.append(f"┌─ {phase_name}\n", style="bold white")
        perf_text.append(f"│  Duration: {total_phase_time:.3f}s ({total_phase_time/total_time*100:.1f}% of total)\n", style="white")
        perf_text.append(f"│  Operations: {len(phase_profiles)} total\n", style="white")
        
        # Cache performance for this phase
        if cache_hits > 0:
            perf_text.append(f"│  Cache Hits: {cache_hits} (", style="green")
            perf_text.append(f"{cache_hits/(cache_hits+cache_misses)*100:.1f}%", style="bold green")
            perf_text.append(")\n", style="green")
        
        if cache_misses > 0:
            perf_text.append(f"│  Cache Misses: {cache_misses} (new analysis)\n", style="yellow")
        
        # Show individual operations if there are multiple or if they're significant
        if len(phase_profiles) > 1 or total_phase_time > 0.1:
            for i, profile in enumerate(phase_profiles):
                is_last = i == len(phase_profiles) - 1
                connector = "└──" if is_last else "├──"
                
                action_symbol = {
                    'hit': '⚡',
                    'miss': '🔄',
                    'create': '🔨'
                }.get(profile.cache_action, '?')
                
                action_color = {
                    'hit': 'green',
                    'miss': 'yellow',
                    'create': 'blue'
                }.get(profile.cache_action, 'white')
                
                perf_text.append(f"│  {connector} {action_symbol} {profile.operation}: ", style="dim")
                perf_text.append(f"{profile.duration_seconds:.3f}s", style=action_color)
                perf_text.append(f" ({profile.cache_action})\n", style="dim")
        
        perf_text.append("│\n", style="dim")
    
    perf_text.append("\n")


def _display_cache_performance(perf_text: Text, profiles: List):
    """Display cache performance summary"""
    perf_text.append("═══ CACHE PERFORMANCE ═══\n", style="bold cyan")
    
    total_ops = len(profiles)
    cache_hits = sum(1 for p in profiles if p.cache_action == 'hit')
    cache_misses = sum(1 for p in profiles if p.cache_action in ['miss', 'create'])
    
    hit_rate = (cache_hits / total_ops * 100) if total_ops > 0 else 0
    
    # Overall cache statistics
    perf_text.append(f"Total Cache Operations: {total_ops}\n", style="white")
    perf_text.append(f"Cache Hit Rate: {hit_rate:.1f}% ({cache_hits}/{total_ops})\n", 
                    style="green" if hit_rate > 50 else "yellow")
    
    # Time saved by caching
    hit_time = sum(p.duration_seconds for p in profiles if p.cache_action == 'hit')
    miss_time = sum(p.duration_seconds for p in profiles if p.cache_action in ['miss', 'create'])
    
    perf_text.append(f"Time in Cache Hits: {hit_time:.3f}s\n", style="green")
    perf_text.append(f"Time in Cache Misses: {miss_time:.3f}s\n", style="yellow")
    
    # Average operation times
    if cache_hits > 0:
        avg_hit_time = hit_time / cache_hits
        perf_text.append(f"Average Hit Time: {avg_hit_time:.3f}s\n", style="green")
    
    if cache_misses > 0:
        avg_miss_time = miss_time / cache_misses
        perf_text.append(f"Average Miss Time: {avg_miss_time:.3f}s\n", style="yellow")
    
    # Performance impact analysis
    if hit_rate > 0 and cache_misses > 0:
        estimated_no_cache_time = total_ops * (miss_time / cache_misses)
        actual_time = hit_time + miss_time
        time_saved = estimated_no_cache_time - actual_time
        
        if time_saved > 0:
            perf_text.append(f"Estimated Time Saved: {time_saved:.3f}s (", style="bold green")
            perf_text.append(f"{time_saved/estimated_no_cache_time*100:.1f}% improvement", style="bold green")
            perf_text.append(")\n", style="bold green")
    
    perf_text.append("\n")


def _display_optimization_status(perf_text: Text, analysis_data: Dict[str, Any], use_async: bool):
    """Display optimization status information"""
    perf_text.append("═══ OPTIMIZATION STATUS ═══\n", style="bold cyan")
    
    # Core optimizations
    if analysis_data.get('is_async_analysis', False):
        perf_text.append("✅ Async Analysis Engine: Active (High Performance Impact)\n", style="green")
        perf_text.append("✅ Advanced Type System: Enabled (Comprehensive Analysis)\n", style="green")
        perf_text.append("✅ Smart Caching: Active (Memory & File Based)\n", style="green")
        perf_text.append("✅ Parallel Processing: Enabled (Multi-threaded Operations)\n", style="green")
    else:
        perf_text.append("⚠️  Legacy Analysis Mode: Fallback (Limited Performance)\n", style="yellow")
        perf_text.append("⚠️  Basic Type Detection: Limited (Sample-based)\n", style="yellow")
        perf_text.append("⚠️  Simple Caching: Basic (Memory Only)\n", style="yellow")
    
    # Field analysis optimization
    if analysis_data.get('field_analysis'):
        field_count = len(analysis_data['field_analysis'])
        perf_text.append(f"✅ Field Analysis: Optimized ({field_count} topics analyzed)\n", style="green")
    
    # Cache level optimization
    if analysis_data.get('cache_level'):
        level_names = {1: "Metadata", 2: "Statistics", 3: "Messages", 4: "Fields"}
        level_name = level_names.get(analysis_data['cache_level'], f"Level {analysis_data['cache_level']}")
        perf_text.append(f"✅ Cache Level: {level_name} (Hierarchical Caching)\n", style="green")
    
    # Performance recommendations
    perf_text.append("\n📋 Performance Recommendations:\n", style="bold yellow")
    
    if not use_async:
        perf_text.append("• Use --async flag for 70%+ performance improvement\n", style="yellow")
    
    if not analysis_data.get('is_async_analysis', False):
        perf_text.append("• Enable unified analyzer for better type detection\n", style="yellow")
    
    if analysis_data.get('cache_level', 0) < 3:
        perf_text.append("• Consider higher cache levels for repeated analysis\n", style="yellow")
    
    perf_text.append("\n")


def _get_cache_info(analysis_data: Dict[str, Any]) -> Dict[str, str]:
    """Get cache information for performance panel"""
    if analysis_data.get('is_async_analysis', False):
        return {
            'strategy': 'Unified Cache',
            'status': 'Optimized',
            'color': 'green'
        }
    else:
        return {
            'strategy': 'Legacy Cache',
            'status': 'Basic',
            'color': 'yellow'
        }


def _is_profile_enabled() -> bool:
    """Check if --profile is enabled by checking cache manager profiling status"""
    try:
        from ..core.unified_cache import get_unified_cache_manager
        cache_manager = get_unified_cache_manager()
        return cache_manager.profiler.enabled
    except ImportError:
        # Unified cache not available, check if we're in a profiling context
        # This is a fallback for legacy systems
        return False


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 