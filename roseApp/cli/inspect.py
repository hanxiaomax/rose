#!/usr/bin/env python3
"""
Inspect command for fast ROS bag analysis with intelligent caching
"""

import os
import time
import json
import csv
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box
from textual.fuzzy import FuzzySearch

# Core module imports - clean and minimal
from ..core.analyzer import analyze_bag_async, AnalysisType
from ..core.cache import get_cache_stats
from ..core.util import set_app_mode, AppMode, get_logger
from ..core.theme import get_current_colors
from .error_handling import ValidationError, validate_file_exists, validate_choice, validate_output_requirement, handle_runtime_error

app = typer.Typer(help="Fast ROS bag inspection and analysis")

# Global fuzzy search instance
fuzzy_search = FuzzySearch(case_sensitive=False)


@app.command()
def inspect(
    input_path: str = typer.Argument(..., help="Input bag file path"),
    topics: List[str] = typer.Option([], "--topics", "-t", help="Filter topics by name or pattern (supports fuzzy matching)"),
    as_format: str = typer.Option("table", "--as", "-a", help="Output format: table, list, summary, csv, html, json"),
    sort_by: str = typer.Option("size", "--sort-by", "-s", help="Sort by: name, type, count, size, frequency"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse sort order"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output with detailed statistics"),
    show_fields: bool = typer.Option(False, "--show-fields", "-f", help="Show detailed field information for specified topics"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (for csv/html formats)")
):
    """
    Inspect ROS bag files with intelligent caching and async analysis
    
    Examples:
        # Basic analysis
        rose inspect mybag.bag
        
        # Detailed analysis with field information
        rose inspect mybag.bag --verbose --show-fields --topics /camera/image
        
        # Export to different formats
        rose inspect mybag.bag --as csv --output report.csv
    """
    
    async def _main():
        # Set application mode
        set_app_mode(AppMode.CLI)
        logger = get_logger()
        console = Console()
        
        start_time = time.time()

        try:
            # Validate inputs
            validate_file_exists(input_path, "bag file")
            validate_choice(as_format, ["table", "list", "summary", "csv", "html", "json"], "--as")
            validate_choice(sort_by, ["name", "type", "count", "size", "frequency"], "--sort-by")
            validate_output_requirement(as_format, output)

            # Determine analysis type
            analysis_type = AnalysisType.FULL_ANALYSIS if verbose else AnalysisType.METADATA

            # Progress callback
            def progress_callback(progress: float):
                if 0 < progress < 100:
                    console.print(f"[dim]Analysis progress: {progress:.1f}%[/dim]", end="\r")

            # Perform analysis using core analyzer
            console.print("[cyan]Analyzing bag file...[/cyan]")
            result = await analyze_bag_async(
                bag_path=Path(input_path),
                analysis_type=analysis_type,
                progress_callback=progress_callback
            )

            # Filter topics
            available_topics = list(result.bag_info.topics)
            filtered_topics = _filter_topics(available_topics, topics)

            # Sort topics if needed
            if result.bag_info.message_counts:
                filtered_topics = _sort_topics(filtered_topics, result, sort_by, reverse)

            # Create display data
            display_data = _create_display_data(input_path, result, filtered_topics)

            # Add field analysis if requested
            if show_fields:
                if not topics:
                    console.print("[red]Error: --show-fields requires --topics to be specified[/red]")
                    return
                
                console.print("Analyzing field information...")
                field_data = await _analyze_fields(result, filtered_topics, console)
                display_data = _integrate_field_data(display_data, field_data)

            # Calculate total time
            total_time = time.time() - start_time
            display_data['summary']['analysis_time'] = total_time

            # Display or export
            if output and as_format in ['csv', 'html', 'json']:
                _export_data(display_data, as_format, output, console)
            else:
                _display_data(display_data, as_format, verbose, console, show_fields)

            # Show cache performance if available
            _show_cache_performance(console)

        except ValidationError as e:
            handle_runtime_error(e, "Parameter validation")
        except Exception as e:
            handle_runtime_error(e, "bag analysis")
    
    # Run async analysis
    try:
        asyncio.run(_main())
    except Exception as e:
        console = Console()
        handle_runtime_error(e, "execution")


async def _analyze_fields(result, topics: List[str], console: Console) -> Dict[str, Any]:
    """Analyze field information for topics using message type analysis"""
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
            
            # Get field paths from analysis result
            if hasattr(result, 'get_topic_field_paths'):
                field_paths = result.get_topic_field_paths(topic)
                message_type = result.bag_info.connections.get(topic, 'unknown')
                
                field_data[topic] = {
                    'message_type': message_type,
                    'field_paths': field_paths,
                    'samples_analyzed': 1  # From message type analysis
                }
            else:
                field_data[topic] = {
                    'message_type': 'unknown',
                    'field_paths': [],
                    'samples_analyzed': 0
                }
            
            progress.update(task, advance=1)
    
    return field_data


def _create_display_data(input_path: str, result, filtered_topics: List[str]) -> Dict[str, Any]:
    """Create display data structure from analysis result"""
    bag_info = result.bag_info
    
    # Build topic details
    topic_details = []
    for topic in filtered_topics:
        count = bag_info.message_counts.get(topic, 0)
        msg_type = bag_info.connections.get(topic, 'unknown')
        frequency = count / bag_info.duration_seconds if bag_info.duration_seconds > 0 else 0.0
        
        topic_details.append({
            'topic': topic,
            'message_type': msg_type,
            'count': count,
            'frequency': frequency,
            'frequency_formatted': f"{frequency:.1f} Hz" if frequency > 0 else None
        })
    
    # Build summary
    summary = {
        'file_path': input_path,
        'file_name': os.path.basename(input_path),
        'absolute_path': str(bag_info.path),
        'topic_count': len(bag_info.topics),
        'total_messages': sum(bag_info.message_counts.values()) if bag_info.message_counts else 0,
        'file_size': bag_info.size_bytes,
        'duration': bag_info.duration_seconds,
        'start_time': bag_info.time_range[0] if bag_info.time_range else None,
        'end_time': bag_info.time_range[1] if bag_info.time_range else None,
        'filtered_count': len(filtered_topics),
        'is_cached': result.cached,
        'analysis_time': result.analysis_time,
        # Formatted versions
        'file_size_formatted': _format_size(bag_info.size_bytes),
        'duration_formatted': _format_duration(bag_info.duration_seconds) if bag_info.duration_seconds else None,
        'avg_rate_formatted': f"{sum(bag_info.message_counts.values()) / bag_info.duration_seconds:.1f} Hz" if bag_info.duration_seconds > 0 and bag_info.message_counts else None
    }
    
    return {
        'summary': summary,
        'topics': topic_details,
        'metadata': {
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'generator': 'rose-cli',
            'version': '2.0',
            'analysis_type': result.analysis_type.value if hasattr(result.analysis_type, 'value') else str(result.analysis_type)
        }
    }


def _filter_topics(topics: List[str], topic_filter: Optional[List[str]]) -> List[str]:
    """Filter topics using fuzzy matching"""
    if not topic_filter:
        return topics
    
    filtered = []
    for pattern in topic_filter:
        # Exact match first
        exact_matches = [topic for topic in topics if topic == pattern]
        if exact_matches:
            filtered.extend(exact_matches)
        else:
            # Fuzzy search
            fuzzy_matches = []
            for topic in topics:
                score, _ = fuzzy_search.match(pattern, topic)
                name_score, _ = fuzzy_search.match(pattern, topic.split('/')[-1])
                if max(score, name_score) > 0:
                    fuzzy_matches.append((topic, max(score, name_score)))
            
            # Sort by score and add to filtered
            fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
            filtered.extend([topic for topic, _ in fuzzy_matches])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_filtered = []
    for topic in filtered:
        if topic not in seen:
            seen.add(topic)
            unique_filtered.append(topic)
    
    return unique_filtered


def _sort_topics(topics: List[str], result, sort_by: str, reverse: bool) -> List[str]:
    """Sort topics based on criteria"""
    def get_sort_key(topic: str):
        if sort_by == "name":
            return topic.lower()
        elif sort_by == "type":
            return topic.split('/')[-1].lower()
        elif sort_by == "count":
            return result.bag_info.message_counts.get(topic, 0)
        elif sort_by == "frequency":
            count = result.bag_info.message_counts.get(topic, 0)
            return count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
        else:  # size - not available in new format, use count
            return result.bag_info.message_counts.get(topic, 0)
    
    return sorted(topics, key=get_sort_key, reverse=reverse)


def _integrate_field_data(display_data: Dict[str, Any], field_data: Dict[str, Any]) -> Dict[str, Any]:
    """Integrate field analysis data"""
    for topic_info in display_data['topics']:
        topic_name = topic_info['topic']
        if topic_name in field_data:
            topic_info['fields'] = field_data[topic_name]
    
    display_data['metadata']['has_field_analysis'] = True
    return display_data


def _display_data(display_data: Dict[str, Any], as_format: str, verbose: bool, console: Console, show_fields: bool = False):
    """Display data in specified format"""
    if as_format == "summary":
        _display_summary(display_data, console, verbose)
    elif as_format == "list":
        _display_list(display_data, console, verbose)
    else:  # table
        _display_table(display_data, console, verbose)
    
    if show_fields and display_data['metadata'].get('has_field_analysis'):
        _display_fields(display_data, console)


def _display_summary(display_data: Dict[str, Any], console: Console, verbose: bool):
    """Display summary format"""
    summary = display_data['summary']
    
    console.print(f"\n[bold cyan]Bag File Summary[/bold cyan]")
    console.print(f"[dim]File:[/dim] {summary['file_name']}")
    
    if verbose:
        console.print(f"[dim]Path:[/dim] {summary['absolute_path']}")
        console.print(f"[dim]Analysis Time:[/dim] {summary['analysis_time']:.3f}s")
        console.print(f"[dim]Cached:[/dim] {'Yes' if summary['is_cached'] else 'No'}")
    
    console.print("-" * 60)
    
    info_items = [
        f"[bold]Topics:[/bold] {summary['topic_count']}",
        f"[bold]Messages:[/bold] {summary['total_messages']:,}",
        f"[bold]File Size:[/bold] {summary['file_size_formatted']}",
    ]
    
    if summary['duration_formatted']:
        info_items.append(f"[bold]Duration:[/bold] {summary['duration_formatted']}")
    
    if summary['avg_rate_formatted']:
        info_items.append(f"[bold]Avg Rate:[/bold] {summary['avg_rate_formatted']}")
    
    if summary['filtered_count'] != summary['topic_count']:
        info_items.append(f"[bold]Filtered:[/bold] {summary['filtered_count']} topics shown")
    
    for item in info_items:
        console.print(item)


def _display_list(display_data: Dict[str, Any], console: Console, verbose: bool):
    """Display list format"""
    _display_summary(display_data, console, verbose)
    console.print()
    
    colors = get_current_colors()
    
    for topic_data in display_data['topics']:
        parts = [f"[bold]{topic_data['topic']}[/bold]"]
        parts.append(f"[{colors.primary}]{topic_data['count']:,} msgs[/{colors.primary}]")
        
        if topic_data['frequency_formatted']:
            parts.append(f"[{colors.accent}]{topic_data['frequency_formatted']}[/{colors.accent}]")
        
        console.print(" | ".join(parts))


def _display_table(display_data: Dict[str, Any], console: Console, verbose: bool):
    """Display table format"""
    _display_summary(display_data, console, verbose)
    console.print()
    
    colors = get_current_colors()
    table = Table(title=f"Topics in {display_data['summary']['file_name']}", box=box.SIMPLE)
    
    table.add_column("Topic", style="bold", min_width=25)
    table.add_column("Message Type", style=colors.primary, min_width=30)
    table.add_column("Count", justify="right", style=colors.success)
    table.add_column("Frequency", justify="right", style=colors.accent)
    
    for topic_data in display_data['topics']:
        table.add_row(
            topic_data['topic'],
            _format_message_type(topic_data['message_type']),
            f"{topic_data['count']:,}",
            topic_data['frequency_formatted'] or "N/A"
        )
    
    console.print(table)


def _display_fields(display_data: Dict[str, Any], console: Console):
    """Display field information"""
    for topic_data in display_data['topics']:
        if 'fields' in topic_data:
            topic_name = topic_data['topic']
            field_info = topic_data['fields']
            
            console.print(f"\n[bold cyan]Fields for {topic_name}[/bold cyan]")
            console.print(f"[dim]Message Type:[/dim] {field_info['message_type']}")
            
            if field_info['field_paths']:
                console.print("\n[dim]Available Fields:[/dim]")
                for path in field_info['field_paths']:
                    console.print(f"  • {path}")
            else:
                console.print("[yellow]No field paths available[/yellow]")


def _export_data(display_data: Dict[str, Any], as_format: str, output: str, console: Console):
    """Export data to file"""
    try:
        if as_format == "csv":
            _export_csv(display_data, output)
        elif as_format == "html":
            _export_html(display_data, output)
        elif as_format == "json":
            _export_json(display_data, output)
        
        console.print(f"\n[green]Data exported to {output}[/green]")
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")
        raise typer.Exit(code=1)


def _export_json(display_data: Dict[str, Any], output_path: str):
    """Export to JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(display_data, f, indent=2, ensure_ascii=False, default=str)


def _export_csv(display_data: Dict[str, Any], output_path: str):
    """Export to CSV"""
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['topic', 'message_type', 'count', 'frequency']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for topic_data in display_data['topics']:
            writer.writerow({
                'topic': topic_data['topic'],
                'message_type': topic_data['message_type'],
                'count': topic_data['count'],
                'frequency': topic_data['frequency']
            })


def _export_html(display_data: Dict[str, Any], output_path: str):
    """Export to HTML"""
    colors = get_current_colors()
    summary = display_data['summary']
    topics = display_data['topics']
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROS Bag Report - {summary['file_name']}</title>
    <style>
        body {{ font-family: 'Inter', sans-serif; margin: 2rem; }}
        .header {{ border-bottom: 2px solid {colors.primary}; padding-bottom: 1rem; margin-bottom: 2rem; }}
        .summary {{ margin-bottom: 2rem; }}
        .topics {{ margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: {colors.background}; font-weight: 600; }}
        .topic {{ font-family: monospace; }}
        .count {{ text-align: right; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ROS Bag Analysis Report</h1>
        <p>{summary['file_name']} • Generated {display_data['metadata']['generated_at']}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Topics:</strong> {summary['topic_count']}</p>
        <p><strong>Messages:</strong> {summary['total_messages']:,}</p>
        <p><strong>File Size:</strong> {summary['file_size_formatted']}</p>
        <p><strong>Duration:</strong> {summary['duration_formatted'] or 'N/A'}</p>
    </div>
    
    <div class="topics">
        <h2>Topics ({len(topics)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Topic</th>
                    <th>Message Type</th>
                    <th>Count</th>
                    <th>Frequency</th>
                </tr>
            </thead>
            <tbody>"""
    
    for topic in topics:
        html_content += f"""
                <tr>
                    <td class="topic">{topic['topic']}</td>
                    <td>{topic['message_type']}</td>
                    <td class="count">{topic['count']:,}</td>
                    <td class="count">{topic['frequency_formatted'] or 'N/A'}</td>
                </tr>"""
    
    html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def _show_cache_performance(console: Console):
    """Show cache performance if available"""
    try:
        stats = get_cache_stats()
        if stats and stats.get('unified', {}).get('enabled'):
            unified_stats = stats['unified']
            hit_rate = unified_stats.get('hit_rate', 0.0)
            total_requests = unified_stats.get('total_requests', 0)
            
            if total_requests > 0:
                console.print(f"\n[dim]Cache Performance: {hit_rate:.1%} hit rate ({total_requests} requests)[/dim]")
    except Exception:
        pass  # Ignore cache performance errors


def _format_size(size_bytes: int) -> str:
    """Format bytes to human readable"""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    
    return f"{size:.1f} {units[i]}"


def _format_duration(seconds: float) -> str:
    """Format duration to human readable"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"


def _format_message_type(msg_type: str) -> str:
    """Format message type for display"""
    if not msg_type or msg_type == "unknown":
        return "Unknown"
    
    # Remove package prefix if present
    if "/" in msg_type:
        msg_type = msg_type.split("/")[-1]
    
    # Limit length
    if len(msg_type) > 25:
        msg_type = msg_type[:22] + "..."
    
    return msg_type


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main() 