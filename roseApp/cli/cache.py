#!/usr/bin/env python3
"""
Cache command for ROS bag analysis utilities
Provides comprehensive cache management, viewing, and export functionality
"""

import os
import sys
import json
import yaml
import pickle
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.json import JSON

from ..core.cache import get_cache, BagCacheEntry
from ..core.ui_control import UIControl
from ..core.theme_config import UnifiedThemeManager, ComponentType
from ..core.model import ComprehensiveBagInfo

app = typer.Typer(name="cache", help="Cache management and analysis commands")


# =============================================================================
# Main Cache Commands
# =============================================================================

@app.command("status")
def cache_status():
    """Show cache status and basic information"""
    console = Console()
    
    try:
        cache = get_cache()
        _show_cache_status_and_info(cache, console)
    except Exception as e:
        console.print(f"[red]Error showing cache status: {e}[/red]")


@app.command("list")
def cache_list(
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml")
):
    """
    List all cache entries
    
    Examples:
        rose cache list                    # List all cache entries
        rose cache list --content          # Show detailed content
        rose cache list --format json     # Output as JSON
    """
    console = Console()
    
    try:
        cache = get_cache()
        _print_cache_entries(cache, console, None, None, show_content, format)
    except Exception as e:
        console.print(f"[red]Error listing cache: {e}[/red]")


@app.command("show")
def cache_show(
    name: Optional[str] = typer.Argument(None, help="Cache key or bag file name to show"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Original bag file path to find cache for"),
    show_content: bool = typer.Option(True, "--content/--no-content", help="Show detailed cache content"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml")
):
    """
    Show specific cache entry details
    
    Examples:
        rose cache show cache_key           # Show specific cache entry
        rose cache show --bag /path/to.bag  # Show cache for specific bag
        rose cache show --format json       # Output as JSON
    """
    console = Console()
    
    try:
        cache = get_cache()
        _print_cache_entries(cache, console, name, bag_path, show_content, format)
    except Exception as e:
        console.print(f"[red]Error showing cache: {e}[/red]")


@app.command("export")
def cache_export(
    output_file: str = typer.Argument(..., help="Output file path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Cache key or bag file name to export"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Original bag file path to find cache for"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, yaml, pickle"),
    include_messages: bool = typer.Option(False, "--messages", "-m", help="Include cached message data")
):
    """
    Export cache entries to file
    
    Examples:
        rose cache export cache_data.json                    # Export all cache
        rose cache export cache.json --name cache_key        # Export specific entry
        rose cache export data.json --bag /path/to.bag       # Export bag cache
        rose cache export data.pkl --format pickle --messages # Export with messages
    """
    console = Console()
    
    try:
        cache = get_cache()
        _export_cache_entries(cache, console, output_file, name, bag_path, format, include_messages)
    except Exception as e:
        console.print(f"[red]Error exporting cache: {e}[/red]")


@app.command("clear")
def cache_clear(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Specific cache key to clear"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Clear cache data
    
    Examples:
        rose cache clear                      # Clear all cache
        rose cache clear --name cache_key     # Clear specific entry
        rose cache clear --bag /path/to.bag   # Clear bag cache
        rose cache clear -y                   # Clear without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        _clear_cache_entries(cache, console, name, bag_path, yes)
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


@app.command("delete")
def cache_delete(
    indices: List[int] = typer.Argument(..., help="Cache entry indices to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Delete specific cache entries by index
    
    Examples:
        rose cache delete 1 3 5      # Delete entries 1, 3, and 5
        rose cache delete 2 -y       # Delete entry 2 without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        _delete_cache_entries(cache, console, indices, yes)
    except Exception as e:
        console.print(f"[red]Error deleting cache entries: {e}[/red]")


@app.command("stats")
def cache_stats(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed statistics"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json")
):
    """
    Show detailed cache statistics and performance metrics
    
    Examples:
        rose cache stats                # Show basic statistics
        rose cache stats --detailed     # Show detailed statistics
        rose cache stats --format json  # Output as JSON
    """
    console = Console()
    
    try:
        cache = get_cache()
        _show_cache_statistics(cache, console, detailed, format)
    except Exception as e:
        console.print(f"[red]Error showing cache statistics: {e}[/red]")


@app.command("analyze")
def cache_analyze(
    show_duplicates: bool = typer.Option(True, "--duplicates/--no-duplicates", help="Show duplicate analysis"),
    show_sizes: bool = typer.Option(True, "--sizes/--no-sizes", help="Show size analysis"),
    show_access: bool = typer.Option(True, "--access/--no-access", help="Show access pattern analysis")
):
    """
    Analyze cache usage patterns and provide optimization recommendations
    
    Examples:
        rose cache analyze                     # Full analysis
        rose cache analyze --no-duplicates    # Skip duplicate analysis
        rose cache analyze --sizes             # Focus on size analysis
    """
    console = Console()
    
    try:
        cache = get_cache()
        _analyze_cache_usage(cache, console, show_duplicates, show_sizes, show_access)
    except Exception as e:
        console.print(f"[red]Error analyzing cache: {e}[/red]")


# =============================================================================
# Helper Functions
# =============================================================================

def _show_cache_status_and_info(cache, console):
    """Show cache status and detailed information"""
    if not hasattr(cache, 'get_stats'):
        console.print("[yellow]Cache statistics not available for this cache type[/yellow]")
        console.print(f"Cache Type: {type(cache).__name__}")
        return
    
    stats = cache.get_stats()
    unified_stats = stats.get('unified', {})
    memory_stats = stats.get('memory', {})
    file_stats = stats.get('file', {})
    
    # Display cache summary
    panel_content = Text()
    panel_content.append(f"Cache Type: {type(cache).__name__}\n")
    # Display cache statistics using unified colors
    panel_content.append(f"Hit Rate: {unified_stats.get('hit_rate', 0) * 100:.1f}%\n", style=UnifiedThemeManager.get_color(ComponentType.CLI, 'success', 'bold'))
    
    total_requests = unified_stats.get('hits', 0) + unified_stats.get('misses', 0)
    panel_content.append(f"Total Requests: {total_requests:,}\n")
    panel_content.append(f"Cache Hits: {unified_stats.get('hits', 0):,}\n")
    panel_content.append(f"Cache Misses: {unified_stats.get('misses', 0):,}")
    
    if memory_stats:
        panel_content.append(f"\nMemory Usage: {_format_size(memory_stats.get('size_bytes', 0))}")
        panel_content.append(f" / {_format_size(memory_stats.get('max_size', 0))}")
    if file_stats:
        panel_content.append(f"\nDisk Usage: {_format_size(file_stats.get('size_bytes', 0))}")
        panel_content.append(f" / {_format_size(file_stats.get('max_size', 0))}")
    
    cache_panel = Panel(
        panel_content,
        title="Cache Statistics",
        border_style=UnifiedThemeManager.get_color(ComponentType.CLI, 'info')
    )
    console.print(cache_panel)
    
    # Show cache entries with index numbers
    memory_entries = memory_stats.get('entry_count', 0)
    file_entries = file_stats.get('entry_count', 0)
    total_entries = memory_entries + file_entries
    
    if total_entries > 0:
        console.print(f"\n[bold]Cache Entries ({total_entries} total)[/bold]")
        
        index = 1
        
        # Show memory cache entries
        if hasattr(cache.memory_cache, 'keys'):
            memory_keys = cache.memory_cache.keys()
            if memory_keys:
                console.print(f"\nMemory Cache ({len(memory_keys)} entries):")
                for key in memory_keys:
                    console.print(f"  [{index}] {key[:70]}...")
                    index += 1
        
        # Show file cache entries
        if hasattr(cache.file_cache, 'keys'):
            file_keys = cache.file_cache.keys()
            if file_keys:
                console.print(f"\nFile Cache ({len(file_keys)} entries):")
                for key in file_keys:
                    console.print(f"  [{index}] {key[:70]}...")
                    index += 1
        
        console.print(f"\n[dim]Use 'rose cache delete 1 2 3' to delete specific entries or 'rose cache clear' to delete all[/dim]")
    else:
        console.print("\n[yellow]No cache entries found[/yellow]")


def _show_cache_statistics(cache, console, detailed, format):
    """Show detailed cache statistics"""
    if not hasattr(cache, 'get_stats'):
        console.print("[yellow]Cache statistics not available for this cache type[/yellow]")
        return
    
    stats = cache.get_stats()
    
    if format == "json":
        console.print(JSON.from_data(stats))
        return
    
    # Create detailed statistics table
    table = Table(title="Cache Performance Statistics")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold")
    table.add_column("Details", style="dim")
    
    unified_stats = stats.get('unified', {})
    memory_stats = stats.get('memory', {})
    file_stats = stats.get('file', {})
    
    # Overall statistics
    hit_rate = unified_stats.get('hit_rate', 0) * 100
    total_requests = unified_stats.get('hits', 0) + unified_stats.get('misses', 0)
    
    table.add_row("Hit Rate", f"{hit_rate:.1f}%", "Cache efficiency")
    table.add_row("Total Requests", f"{total_requests:,}", "All cache operations")
    table.add_row("Cache Hits", f"{unified_stats.get('hits', 0):,}", "Successful cache retrievals")
    table.add_row("Cache Misses", f"{unified_stats.get('misses', 0):,}", "Failed cache retrievals")
    
    # Memory cache statistics
    if memory_stats:
        table.add_row("Memory Entries", f"{memory_stats.get('entry_count', 0):,}", "In-memory cached items")
        table.add_row("Memory Usage", _format_size(memory_stats.get('size_bytes', 0)), f"Max: {_format_size(memory_stats.get('max_size', 0))}")
    
    # File cache statistics
    if file_stats:
        table.add_row("File Entries", f"{file_stats.get('entry_count', 0):,}", "Persistent cached items")
        table.add_row("Disk Usage", _format_size(file_stats.get('size_bytes', 0)), f"Max: {_format_size(file_stats.get('max_size', 0))}")
    
    console.print(table)
    
    if detailed:
        # Show additional detailed information
        console.print("\n[bold]Detailed Analysis[/bold]")
        
        # Cache efficiency analysis
        if total_requests > 0:
            efficiency_text = Text()
            if hit_rate >= 80:
                efficiency_text.append("Excellent", style="green bold")
                efficiency_text.append(" - Cache is highly effective")
            elif hit_rate >= 60:
                efficiency_text.append("Good", style="yellow bold")
                efficiency_text.append(" - Cache is working well")
            elif hit_rate >= 40:
                efficiency_text.append("Fair", style="orange bold")
                efficiency_text.append(" - Cache could be improved")
            else:
                efficiency_text.append("Poor", style="red bold")
                efficiency_text.append(" - Cache needs optimization")
            
            console.print(f"Cache Efficiency: ", end="")
            console.print(efficiency_text)


def _analyze_cache_usage(cache, console, show_duplicates, show_sizes, show_access):
    """Analyze cache usage patterns and provide recommendations"""
    console.print("[bold cyan]Cache Usage Analysis[/bold cyan]\n")
    
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        console.print("[yellow]No cache entries to analyze[/yellow]")
        return
    
    # Basic statistics
    total_entries = len(all_entries)
    bag_entries = sum(1 for entry in all_entries if entry[0].startswith('bag_'))
    other_entries = total_entries - bag_entries
    
    console.print(f"Total Entries: {total_entries}")
    console.print(f"Bag Analysis Entries: {bag_entries}")
    console.print(f"Other Entries: {other_entries}\n")
    
    if show_sizes:
        _analyze_cache_sizes(cache, console, all_entries)
    
    if show_duplicates:
        _analyze_cache_duplicates(cache, console, all_entries)
    
    if show_access:
        _analyze_access_patterns(cache, console, all_entries)
    
    # Provide recommendations
    _provide_cache_recommendations(cache, console, all_entries)


def _analyze_cache_sizes(cache, console, all_entries):
    """Analyze cache size distribution"""
    console.print("[bold]Size Analysis[/bold]")
    
    sizes = []
    for key, cache_type in all_entries:
        try:
            if cache_type == 'memory':
                entry = cache.memory_cache.get(key)
            else:
                entry = cache.file_cache.get(key)
            
            if entry and hasattr(entry, 'size'):
                sizes.append(entry.size)
        except:
            pass
    
    if sizes:
        total_size = sum(sizes)
        avg_size = total_size / len(sizes)
        max_size = max(sizes)
        min_size = min(sizes)
        
        console.print(f"Average Entry Size: {_format_size(avg_size)}")
        console.print(f"Largest Entry: {_format_size(max_size)}")
        console.print(f"Smallest Entry: {_format_size(min_size)}")
        console.print(f"Total Size: {_format_size(total_size)}")
    else:
        console.print("Size information not available")
    
    console.print()


def _analyze_cache_duplicates(cache, console, all_entries):
    """Analyze potential duplicate cache entries"""
    console.print("[bold]Duplicate Analysis[/bold]")
    
    # Group entries by content hash (simplified)
    content_hashes = {}
    for key, cache_type in all_entries:
        # Simple duplicate detection based on key patterns
        if key.startswith('bag_'):
            # Extract potential file path information
            simplified_key = key.replace('bag_', '').split('_')[0]
            if simplified_key in content_hashes:
                content_hashes[simplified_key].append(key)
            else:
                content_hashes[simplified_key] = [key]
    
    duplicates = {k: v for k, v in content_hashes.items() if len(v) > 1}
    
    if duplicates:
        console.print(f"Found {len(duplicates)} potential duplicate groups:")
        for group, keys in duplicates.items():
            console.print(f"  {group}: {len(keys)} entries")
    else:
        console.print("No obvious duplicates found")
    
    console.print()


def _analyze_access_patterns(cache, console, all_entries):
    """Analyze cache access patterns"""
    console.print("[bold]Access Pattern Analysis[/bold]")
    
    # This is a simplified analysis - in a real implementation,
    # you would track access times and frequencies
    memory_count = sum(1 for _, cache_type in all_entries if cache_type == 'memory')
    file_count = sum(1 for _, cache_type in all_entries if cache_type == 'file')
    
    console.print(f"Memory Cache Usage: {memory_count} entries")
    console.print(f"File Cache Usage: {file_count} entries")
    
    if memory_count > 0 and file_count > 0:
        ratio = memory_count / file_count
        if ratio > 2:
            console.print("High memory cache usage - good for performance")
        elif ratio < 0.5:
            console.print("High file cache usage - good for persistence")
        else:
            console.print("Balanced cache usage")
    
    console.print()


def _provide_cache_recommendations(cache, console, all_entries):
    """Provide cache optimization recommendations"""
    console.print("[bold green]Recommendations[/bold green]")
    
    stats = cache.get_stats() if hasattr(cache, 'get_stats') else {}
    unified_stats = stats.get('unified', {})
    hit_rate = unified_stats.get('hit_rate', 0) * 100
    
    recommendations = []
    
    if hit_rate < 50:
        recommendations.append("Consider increasing cache size limits for better hit rates")
    
    if len(all_entries) > 100:
        recommendations.append("Large number of cache entries - consider periodic cleanup")
    
    memory_entries = sum(1 for _, cache_type in all_entries if cache_type == 'memory')
    if memory_entries > 50:
        recommendations.append("High memory cache usage - monitor memory consumption")
    
    if not recommendations:
        recommendations.append("Cache appears to be well-optimized")
    
    for i, rec in enumerate(recommendations, 1):
        console.print(f"{i}. {rec}")


def _clear_cache_entries(cache, console, name, bag_path, skip_confirm):
    """Clear cache entries with filtering support"""
    if name or bag_path:
        # Clear specific entries
        all_entries = _get_all_cache_entries(cache)
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        
        if not filtered_entries:
            console.print("[yellow]No matching cache entries found[/yellow]")
            return
        
        console.print(f"[bold]Found {len(filtered_entries)} matching entries to clear[/bold]")
        for key, cache_type in filtered_entries:
            console.print(f"  ({cache_type}) {key[:70]}...")
        
        if not skip_confirm:
            result = typer.confirm(f"Clear {len(filtered_entries)} cache entries?")
            if not result:
                console.print("Operation cancelled")
                return
        
        # Clear specific entries
        cleared_count = 0
        for key, cache_type in filtered_entries:
            try:
                if cache_type == 'memory':
                    success = cache.memory_cache.delete(key)
                else:
                    success = cache.file_cache.delete(key)
                
                if success:
                    cleared_count += 1
            except Exception as e:
                console.print(f"[red]Failed to clear {key[:50]}...: {e}[/red]")
        
        console.print(f"[green]✓ Successfully cleared {cleared_count} cache entries[/green]")
    else:
        # Clear all cache
        if not hasattr(cache, 'get_stats'):
            console.print("[yellow]Cache information not available[/yellow]")
            return
        
        stats = cache.get_stats()
        memory_stats = stats.get('memory', {})
        file_stats = stats.get('file', {})
        
        memory_entries = memory_stats.get('entry_count', 0)
        file_entries = file_stats.get('entry_count', 0)
        total_entries = memory_entries + file_entries
        
        if total_entries == 0:
            console.print("[yellow]No cache data to clear[/yellow]")
            return
        
        console.print(f"[bold]Found cache data with {total_entries:,} entries ({memory_entries} memory, {file_entries} file)[/bold]")
        
        if not skip_confirm:
            result = typer.confirm("Do you want to clear all cache data?")
            if not result:
                console.print("Operation cancelled")
                return
        
        # Clear the cache
        if hasattr(cache, 'clear'):
            cache.clear()
            console.print("[green]✓ Successfully cleared all cache data[/green]")
        else:
            console.print("[yellow]Cache clearing not supported for this cache type[/yellow]")


def _delete_cache_entries(cache, console, indices, skip_confirm):
    """Delete specific cache entries by index"""
    if not hasattr(cache, 'get_stats'):
        console.print("[yellow]Cache information not available[/yellow]")
        return
    
    # Get all cache keys with their indices
    all_keys = []
    
    if hasattr(cache.memory_cache, 'keys'):
        memory_keys = cache.memory_cache.keys()
        all_keys.extend([(key, 'memory') for key in memory_keys])
    
    if hasattr(cache.file_cache, 'keys'):
        file_keys = cache.file_cache.keys()
        all_keys.extend([(key, 'file') for key in file_keys])
    
    if not all_keys:
        console.print("[yellow]No cache entries to delete[/yellow]")
        return
    
    # Validate indices
    valid_indices = []
    invalid_indices = []
    
    for idx in indices:
        if 1 <= idx <= len(all_keys):
            valid_indices.append(idx)
        else:
            invalid_indices.append(idx)
    
    if invalid_indices:
        console.print(f"[red]Invalid indices: {', '.join(map(str, invalid_indices))}[/red]")
        console.print(f"[dim]Valid range: 1-{len(all_keys)}[/dim]")
        if not valid_indices:
            return
    
    # Show entries to be deleted
    console.print(f"[bold]Entries to delete ({len(valid_indices)})[/bold]")
    keys_to_delete = []
    for idx in valid_indices:
        key, cache_type = all_keys[idx - 1]
        console.print(f"  [{idx}] ({cache_type}) {key[:70]}...")
        keys_to_delete.append((key, cache_type))
    
    if not skip_confirm:
        result = typer.confirm(f"Delete {len(keys_to_delete)} cache entries?")
        if not result:
            console.print("Operation cancelled")
            return
    
    # Delete the entries
    deleted_count = 0
    failed_count = 0
    
    for key, cache_type in keys_to_delete:
        try:
            if cache_type == 'memory':
                success = cache.memory_cache.delete(key)
            else:  # file
                success = cache.file_cache.delete(key)
            
            if success:
                deleted_count += 1
            else:
                failed_count += 1
        except Exception as e:
            console.print(f"[red]Failed to delete {key[:50]}...: {e}[/red]")
            failed_count += 1
    
    if deleted_count > 0:
        console.print(f"[green]✓ Successfully deleted {deleted_count} cache entries[/green]")
    
    if failed_count > 0:
        console.print(f"[red]✗ Failed to delete {failed_count} cache entries[/red]")


def _print_cache_entries(cache, console, name, bag_path, show_content, format):
    """Print cache entries with filtering and formatting options"""
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        console.print("[yellow]No cache entries found[/yellow]")
        return
    
    # Filter entries if criteria provided
    if name or bag_path:
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        if not filtered_entries:
            console.print("[yellow]No matching cache entries found[/yellow]")
            return
        all_entries = filtered_entries
    
    # Output in requested format
    if format == "json":
        _print_cache_as_json(cache, console, all_entries, show_content)
    elif format == "yaml":
        _print_cache_as_yaml(cache, console, all_entries, show_content)
    else:
        _print_cache_as_table(cache, console, all_entries, show_content)


def _export_cache_entries(cache, console, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        console.print("[yellow]No cache entries to export[/yellow]")
        return
    
    # Filter entries if criteria provided
    if name or bag_path:
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        if not filtered_entries:
            console.print("[yellow]No matching cache entries found[/yellow]")
            return
        all_entries = filtered_entries
    
    # Prepare export data
    export_data = _prepare_export_data(cache, all_entries, include_messages)
    
    # Export to file
    output_path = Path(output_file)
    try:
        if format == "json":
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
        elif format == "yaml":
            with open(output_path, 'w') as f:
                yaml.dump(export_data, f, default_flow_style=False)
        elif format == "pickle":
            with open(output_path, 'wb') as f:
                pickle.dump(export_data, f)
        else:
            console.print(f"[red]Unsupported export format: {format}[/red]")
            return
        
        console.print(f"[green]✓ Successfully exported {len(all_entries)} cache entries to {output_path}[/green]")
        console.print(f"[dim]Format: {format}, Messages included: {include_messages}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error exporting cache: {e}[/red]")


def _get_all_cache_entries(cache):
    """Get all cache entries from both memory and file caches"""
    all_entries = []
    
    # Get memory cache entries
    if hasattr(cache, 'memory_cache') and hasattr(cache.memory_cache, 'keys'):
        memory_keys = cache.memory_cache.keys()
        all_entries.extend([(key, 'memory') for key in memory_keys])
    
    # Get file cache entries
    if hasattr(cache, 'file_cache') and hasattr(cache.file_cache, 'keys'):
        file_keys = cache.file_cache.keys()
        all_entries.extend([(key, 'file') for key in file_keys])
    
    return all_entries


def _filter_cache_entries(cache, all_entries, name, bag_path):
    """Filter cache entries based on name or bag path"""
    if not name and not bag_path:
        return all_entries
    
    filtered = []
    
    for key, cache_type in all_entries:
        match = False
        
        if name and name.lower() in key.lower():
            match = True
        
        if bag_path and not match:
            # Try to match bag path by generating expected cache key
            try:
                from pathlib import Path
                import hashlib
                bag_path_obj = Path(bag_path)
                expected_key = f"bag_{hashlib.md5(str(bag_path_obj.absolute()).encode()).hexdigest()}"
                if key == expected_key:
                    match = True
            except:
                # Fallback to simple string matching
                if bag_path.lower() in key.lower():
                    match = True
        
        if match:
            filtered.append((key, cache_type))
    
    return filtered


def _print_cache_as_table(cache, console, all_entries, show_content):
    """Print cache entries as a formatted table"""
    table = Table(title=f"Cache Entries ({len(all_entries)} total)")
    table.add_column("Index", style="dim", width=6)
    table.add_column("Type", style="cyan", width=8)
    table.add_column("Key", style="bold")
    table.add_column("Size", style="green", width=10)
    
    if show_content:
        table.add_column("Content Preview", style="dim")
    
    for i, (key, cache_type) in enumerate(all_entries, 1):
        try:
            # Get cache entry
            if cache_type == 'memory':
                entry = cache.memory_cache.get(key)
            else:
                entry = cache.file_cache.get(key)
            
            # Format size
            size_str = "Unknown"
            if entry and hasattr(entry, 'size'):
                size_str = _format_size(entry.size)
            
            # Prepare row data
            row_data = [str(i), cache_type, key[:50] + "..." if len(key) > 50 else key, size_str]
            
            if show_content:
                content_preview = _get_content_preview(entry.value if entry else None)
                row_data.append(content_preview)
            
            table.add_row(*row_data)
            
        except Exception as e:
            row_data = [str(i), cache_type, key[:50] + "..." if len(key) > 50 else key, "Error"]
            if show_content:
                row_data.append(f"Error: {e}")
            table.add_row(*row_data)
    
    console.print(table)


def _print_cache_as_json(cache, console, all_entries, show_content):
    """Print cache entries as JSON"""
    export_data = _prepare_export_data(cache, all_entries, show_content)
    console.print(JSON.from_data(export_data))


def _print_cache_as_yaml(cache, console, all_entries, show_content):
    """Print cache entries as YAML"""
    export_data = _prepare_export_data(cache, all_entries, show_content)
    yaml_str = yaml.dump(export_data, default_flow_style=False)
    console.print(yaml_str)


def _prepare_export_data(cache, all_entries, include_messages):
    """Prepare cache data for export"""
    export_data = {
        'metadata': {
            'export_time': time.time(),
            'total_entries': len(all_entries),
            'include_messages': include_messages
        },
        'entries': []
    }
    
    for key, cache_type in all_entries:
        try:
            # Get cache entry
            if cache_type == 'memory':
                entry = cache.memory_cache.get(key)
            else:
                entry = cache.file_cache.get(key)
            
            if entry:
                entry_data = {
                    'key': key,
                    'type': cache_type,
                    'timestamp': getattr(entry, 'timestamp', 0),
                    'size': getattr(entry, 'size', 0)
                }
                
                # Add content based on type
                if isinstance(entry.value, BagCacheEntry):
                    entry_data['content'] = _bag_cache_to_dict(entry.value, include_messages)
                else:
                    entry_data['content'] = str(entry.value)[:200] + "..." if len(str(entry.value)) > 200 else str(entry.value)
                
                export_data['entries'].append(entry_data)
                
        except Exception as e:
            export_data['entries'].append({
                'key': key,
                'type': cache_type,
                'error': str(e)
            })
    
    return export_data


def _bag_cache_to_dict(bag_cache_entry, include_messages=False):
    """Convert BagCacheEntry to dictionary for export"""
    try:
        bag_info = bag_cache_entry.bag_info
        result = {
            'file_path': bag_info.file_path,
            'analysis_level': bag_info.analysis_level.value if bag_info.analysis_level else 'none',
            'topics_count': len(bag_info.topics) if bag_info.topics else 0,
            'total_messages': sum(bag_info.message_counts.values()) if bag_info.message_counts else 0,
            'duration_seconds': bag_info.duration_seconds,
            'cache_timestamp': bag_cache_entry.cache_timestamp,
            'file_mtime': bag_cache_entry.file_mtime,
            'file_size': bag_cache_entry.file_size
        }
        
        if bag_info.topics:
            result['topics'] = bag_info.topics
        
        if bag_info.connections:
            result['connections'] = bag_info.connections
        
        if bag_info.message_counts:
            result['message_counts'] = bag_info.message_counts
        
        if include_messages and bag_cache_entry.cached_messages:
            result['cached_messages'] = {
                topic: len(messages) for topic, messages in bag_cache_entry.cached_messages.items()
            }
        
        return result
        
    except Exception as e:
        return {'error': f'Failed to convert bag cache entry: {e}'}


def _get_content_preview(cached_data):
    """Get a preview of cached data content"""
    if cached_data is None:
        return "None"
    
    if isinstance(cached_data, BagCacheEntry):
        bag_info = cached_data.bag_info
        topics_count = len(bag_info.topics) if bag_info.topics else 0
        return f"Bag: {topics_count} topics, {bag_info.duration_seconds:.1f}s"
    
    content_str = str(cached_data)
    if len(content_str) > 50:
        return content_str[:47] + "..."
    return content_str


def _format_size(size_bytes):
    """Format size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


if __name__ == "__main__":
    app()