#!/usr/bin/env python3
"""
Tools command for ROS bag analysis utilities
Provides cache management, diagnostics, and other utility functions
"""

import os
import sys
import shutil
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

app = typer.Typer(name="tools", help="Utility tools for cache management, diagnostics, and system info")


# =============================================================================
# Cache Management Command
# =============================================================================

# Create cache subcommand group
cache_app = typer.Typer(name="cache", help="Cache management commands")
app.add_typer(cache_app, name="cache")

@cache_app.command("status")
def cache_status():
    """Show cache status and basic information"""
    console = Console()
    
    try:
        cache = get_cache()
        _show_cache_status_and_info(cache, console)
    except Exception as e:
        console.print(f"[red]Error showing cache status: {e}[/red]")

@cache_app.command("print")
def cache_print(
    name: Optional[str] = typer.Argument(None, help="Cache key or bag file name to print"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Original bag file path to find cache for"),
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, yaml")
):
    """
    Print cache entries and their content
    
    Examples:
        rose tools cache print                      # List all cache entries
        rose tools cache print cache_key           # Print specific cache entry
        rose tools cache print --bag /path/to.bag  # Print cache for specific bag
        rose tools cache print --content           # Show detailed content
        rose tools cache print --format json       # Output as JSON
    """
    console = Console()
    
    try:
        cache = get_cache()
        _print_cache_entries(cache, console, name, bag_path, show_content, format)
    except Exception as e:
        console.print(f"[red]Error printing cache: {e}[/red]")

@cache_app.command("export")
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
        rose tools cache export cache_data.json                    # Export all cache
        rose tools cache export cache.json --name cache_key        # Export specific entry
        rose tools cache export data.json --bag /path/to.bag       # Export bag cache
        rose tools cache export data.pkl --format pickle --messages # Export with messages
    """
    console = Console()
    
    try:
        cache = get_cache()
        _export_cache_entries(cache, console, output_file, name, bag_path, format, include_messages)
    except Exception as e:
        console.print(f"[red]Error exporting cache: {e}[/red]")

@cache_app.command("clear")
def cache_clear(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Specific cache key to clear"),
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Clear cache data
    
    Examples:
        rose tools cache clear                      # Clear all cache
        rose tools cache clear --name cache_key    # Clear specific entry
        rose tools cache clear --bag /path/to.bag  # Clear bag cache
        rose tools cache clear -y                  # Clear without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        _clear_cache_entries(cache, console, name, bag_path, yes)
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")

@cache_app.command("delete")
def cache_delete(
    indices: List[int] = typer.Argument(..., help="Cache entry indices to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Delete specific cache entries by index
    
    Examples:
        rose tools cache delete 1 3 5      # Delete entries 1, 3, and 5
        rose tools cache delete 2 -y       # Delete entry 2 without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        _delete_cache_entries(cache, console, indices, yes)
    except Exception as e:
        console.print(f"[red]Error deleting cache entries: {e}[/red]")

# Keep the old cache command for backward compatibility
@app.command("cache")
def cache_legacy(
    delete: Optional[List[int]] = typer.Option(None, "--delete", "-D", help="Delete cache entries by index numbers"),
    clear: bool = typer.Option(False, "--clear", help="Clear all cache data"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    [DEPRECATED] Legacy cache command - use 'rose tools cache status|print|export|clear|delete' instead
    
    Manage cache data - show status, info, and perform operations
    
    Examples:
        rose tools cache                    # Show cache status and info
        rose tools cache -D 1,3,5         # Delete specific cache entries
        rose tools cache --clear           # Clear all cache data
        rose tools cache --clear -y       # Clear without confirmation
    """
    console = Console()
    console.print("[yellow]Warning: This command is deprecated. Use 'rose tools cache status|print|export|clear|delete' instead.[/yellow]")
    
    try:
        cache = get_cache()
        
        if clear:
            # Clear all cache data
            _clear_cache_entries(cache, console, None, None, yes)
        elif delete:
            # Delete specific cache entries
            _delete_cache_entries(cache, console, delete, yes)
        else:
            # Show cache status and info (default behavior)
            _show_cache_status_and_info(cache, console)
            
    except Exception as e:
        console.print(f"[red]Error managing cache: {e}[/red]")


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
        
        console.print(f"\n[dim]Use 'cache -D 1,2,3' to delete specific entries or 'cache --clear' to delete all[/dim]")
    else:
        console.print("\n[yellow]No cache entries found[/yellow]")


def _clear_cache(cache, console, skip_confirm):
    """Clear all cache data"""
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


# =============================================================================
# Diagnostic Command
# =============================================================================

@app.command()
def diagnose():
    """
    Run system diagnostics to check environment and dependencies
    
    Examples:
        rose tools diagnose
    """
    console = Console()
    
    console.print("[bold green]🔍 System Diagnostics[/bold green]")
    console.print()
    
    # Check Python version
    console.print(f"Python Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check dependencies
    console.print("\nDependencies:")
    
    # Check rosbags
    try:
        import rosbags
        version = getattr(rosbags, '__version__', 'unknown')
        console.print(f"  ✅ rosbags: {version}")
    except ImportError:
        console.print("  ❌ rosbags: Not installed")
        console.print("     Install with: pip install rosbags")
    
    # Check rich
    try:
        import rich
        console.print(f"  ✅ rich: Available")
    except ImportError:
        console.print("  ❌ rich: Not available")
    
    # Check typer
    try:
        import typer
        console.print(f"  ✅ typer: Available")
    except ImportError:
        console.print("  ❌ typer: Not available")
    
    # Check optional dependencies
    try:
        import yaml
        console.print(f"  ✅ pyyaml: Available (YAML export supported)")
    except ImportError:
        console.print("  ⚠️  pyyaml: Not installed (YAML export not available)")
        console.print("     Install with: pip install pyyaml")
    
    # Check ROS environment
    console.print(f"\nROS Environment:")
    ros_distro = os.environ.get('ROS_DISTRO', 'Not set')
    console.print(f"  ROS Distro: {ros_distro}")
    
    if ros_distro != 'Not set':
        console.print("  ✅ ROS environment detected")
    else:
        console.print("  ⚠️  No ROS environment detected")
    
    # Check cache system
    console.print(f"\nCache System:")
    try:
        cache = get_cache()
        console.print(f"  ✅ Cache system: {type(cache).__name__}")
        
        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
            unified_stats = stats.get('unified', {})
            total_requests = unified_stats.get('hits', 0) + unified_stats.get('misses', 0)
            console.print(f"  Cache requests: {total_requests:,}")
            console.print(f"  Hit rate: {unified_stats.get('hit_rate', 0) * 100:.1f}%")
    except Exception as e:
        console.print(f"  ❌ Cache system error: {e}")
    
    console.print()
    console.print("[bold green]✅ System diagnostics complete[/bold green]")


# =============================================================================
# Utility Commands
# =============================================================================

@app.command()
def version():
    """
    Show version information for rose and its dependencies
    
    Examples:
        rose tools version
    """
    console = Console()
    
    # Rose version (if available)
    try:
        from .. import __version__
        console.print(f"Rose: {__version__}")
    except ImportError:
        console.print("Rose: Development version")
    
    # Python version
    console.print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Key dependencies
    deps = [
        ('rosbags', 'rosbags'),
        ('rich', 'rich'),
        ('typer', 'typer'),
        ('pyyaml', 'yaml'),
    ]
    
    console.print("\nDependencies:")
    for name, import_name in deps:
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            console.print(f"  {name}: {version}")
        except ImportError:
            console.print(f"  {name}: Not installed")





# =============================================================================
# Helper Functions
# =============================================================================

def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"





# =============================================================================
# New Cache Management Functions
# =============================================================================

def _print_cache_entries(cache, console, name, bag_path, show_content, format):
    """Print cache entries with detailed information"""
    
    # Get all cache entries
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        console.print("[yellow]No cache entries found[/yellow]")
        return
    
    # Filter entries if specific name or bag_path is provided
    if name or bag_path:
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        if not filtered_entries:
            if bag_path:
                console.print(f"[yellow]No cache entries found for bag: {bag_path}[/yellow]")
            else:
                console.print(f"[yellow]No cache entries found matching: {name}[/yellow]")
            return
        all_entries = filtered_entries
    
    # Output based on format
    if format.lower() == "json":
        _print_cache_as_json(cache, console, all_entries, show_content)
    elif format.lower() == "yaml":
        _print_cache_as_yaml(cache, console, all_entries, show_content)
    else:
        _print_cache_as_table(cache, console, all_entries, show_content)


def _export_cache_entries(cache, console, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    
    # Get all cache entries
    all_entries = _get_all_cache_entries(cache)
    
    if not all_entries:
        console.print("[yellow]No cache entries found to export[/yellow]")
        return
    
    # Filter entries if specific name or bag_path is provided
    if name or bag_path:
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        if not filtered_entries:
            console.print(f"[yellow]No cache entries found to export[/yellow]")
            return
        all_entries = filtered_entries
    
    # Prepare export data
    export_data = _prepare_export_data(cache, all_entries, include_messages)
    
    # Export based on format
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if format.lower() == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
        elif format.lower() == "yaml":
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
        elif format.lower() == "pickle":
            with open(output_path, 'wb') as f:
                pickle.dump(export_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            console.print(f"[red]Unsupported export format: {format}[/red]")
            return
        
        console.print(f"[green]✓ Exported {len(all_entries)} cache entries to {output_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error exporting cache: {e}[/red]")


def _clear_cache_entries(cache, console, name, bag_path, skip_confirm):
    """Clear cache entries with optional filtering"""
    
    if name or bag_path:
        # Clear specific entries
        all_entries = _get_all_cache_entries(cache)
        filtered_entries = _filter_cache_entries(cache, all_entries, name, bag_path)
        
        if not filtered_entries:
            console.print("[yellow]No matching cache entries found to clear[/yellow]")
            return
        
        console.print(f"[bold]Found {len(filtered_entries)} matching cache entries[/bold]")
        
        if not skip_confirm:
            if bag_path:
                result = typer.confirm(f"Do you want to clear cache for bag: {bag_path}?")
            else:
                result = typer.confirm(f"Do you want to clear cache entries matching: {name}?")
            if not result:
                console.print("Operation cancelled")
                return
        
        # Delete specific entries
        deleted_count = 0
        for key, location in filtered_entries:
            if cache.delete(key):
                deleted_count += 1
        
        console.print(f"[green]✓ Cleared {deleted_count} cache entries[/green]")
        
    else:
        # Clear all cache - use existing function
        _clear_cache(cache, console, skip_confirm)


def _get_all_cache_entries(cache):
    """Get all cache entries from both memory and file cache"""
    all_entries = []
    
    # Get memory cache entries
    if hasattr(cache.memory_cache, 'keys'):
        memory_keys = cache.memory_cache.keys()
        all_entries.extend([(key, 'memory') for key in memory_keys])
    
    # Get file cache entries
    if hasattr(cache.file_cache, 'keys'):
        file_keys = cache.file_cache.keys()
        all_entries.extend([(key, 'file') for key in file_keys])
    
    return all_entries


def _filter_cache_entries(cache, all_entries, name, bag_path):
    """Filter cache entries based on name or bag_path"""
    filtered_entries = []
    
    if bag_path:
        # Convert bag_path to cache key
        bag_path_obj = Path(bag_path)
        if bag_path_obj.exists():
            bag_cache_key = cache.get_bag_cache_key(bag_path_obj)
            filtered_entries = [(key, loc) for key, loc in all_entries if key == bag_cache_key]
        else:
            # Try to find by filename
            bag_filename = bag_path_obj.name
            for key, location in all_entries:
                # Check if this is a bag cache entry and try to match filename
                if key.startswith('bag_'):
                    cached_data = cache.get(key)
                    if cached_data and isinstance(cached_data, BagCacheEntry):
                        if bag_filename in cached_data.bag_info.file_path:
                            filtered_entries.append((key, location))
    
    elif name:
        # Filter by name (can be exact key or partial match)
        for key, location in all_entries:
            if name == key or name in key:
                filtered_entries.append((key, location))
    
    return filtered_entries


def _print_cache_as_table(cache, console, all_entries, show_content):
    """Print cache entries as a table"""
    
    table = Table(title="Cache Entries")
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Key", style="green")
    table.add_column("Location", style="blue")
    table.add_column("Type", style="yellow")
    table.add_column("Size", style="magenta")
    
    if show_content:
        table.add_column("Content Preview", style="white")
    
    for index, (key, location) in enumerate(all_entries, 1):
        # Get cache entry details
        cached_data = cache.get(key)
        data_type = type(cached_data).__name__ if cached_data else "Unknown"
        
        # Calculate size
        try:
            size_bytes = len(pickle.dumps(cached_data)) if cached_data else 0
            size_str = _format_size(size_bytes)
        except:
            size_str = "Unknown"
        
        # Prepare row data
        row = [
            str(index),
            key[:50] + "..." if len(key) > 50 else key,
            location,
            data_type,
            size_str
        ]
        
        if show_content:
            content_preview = _get_content_preview(cached_data)
            row.append(content_preview)
        
        table.add_row(*row)
    
    console.print(table)
    
    # Show detailed content for bag cache entries if requested
    if show_content:
        for key, location in all_entries:
            cached_data = cache.get(key)
            if isinstance(cached_data, BagCacheEntry):
                _print_bag_cache_details(console, key, cached_data)


def _print_cache_as_json(cache, console, all_entries, show_content):
    """Print cache entries as JSON"""
    
    json_data = {}
    
    for key, location in all_entries:
        cached_data = cache.get(key)
        
        entry_info = {
            "location": location,
            "type": type(cached_data).__name__ if cached_data else "Unknown"
        }
        
        if show_content and cached_data:
            if isinstance(cached_data, BagCacheEntry):
                entry_info["content"] = _bag_cache_to_dict(cached_data)
            else:
                try:
                    entry_info["content"] = str(cached_data)[:200] + "..." if len(str(cached_data)) > 200 else str(cached_data)
                except:
                    entry_info["content"] = "Unable to serialize"
        
        json_data[key] = entry_info
    
    console.print(JSON.from_data(json_data))


def _print_cache_as_yaml(cache, console, all_entries, show_content):
    """Print cache entries as YAML"""
    
    yaml_data = {}
    
    for key, location in all_entries:
        cached_data = cache.get(key)
        
        entry_info = {
            "location": location,
            "type": type(cached_data).__name__ if cached_data else "Unknown"
        }
        
        if show_content and cached_data:
            if isinstance(cached_data, BagCacheEntry):
                entry_info["content"] = _bag_cache_to_dict(cached_data)
            else:
                try:
                    entry_info["content"] = str(cached_data)[:200] + "..." if len(str(cached_data)) > 200 else str(cached_data)
                except:
                    entry_info["content"] = "Unable to serialize"
        
        yaml_data[key] = entry_info
    
    console.print(yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True))


def _prepare_export_data(cache, all_entries, include_messages):
    """Prepare cache data for export"""
    
    export_data = {
        "export_timestamp": time.time(),
        "cache_entries": {}
    }
    
    for key, location in all_entries:
        cached_data = cache.get(key)
        
        entry_data = {
            "location": location,
            "type": type(cached_data).__name__ if cached_data else "Unknown",
            "timestamp": time.time()
        }
        
        if cached_data:
            if isinstance(cached_data, BagCacheEntry):
                entry_data["bag_info"] = _bag_cache_to_dict(cached_data, include_messages)
            else:
                try:
                    entry_data["data"] = cached_data
                except:
                    entry_data["data"] = str(cached_data)
        
        export_data["cache_entries"][key] = entry_data
    
    return export_data


def _bag_cache_to_dict(bag_cache_entry, include_messages=False):
    """Convert BagCacheEntry to dictionary for serialization"""
    
    data = {
        "cache_timestamp": bag_cache_entry.cache_timestamp,
        "file_mtime": bag_cache_entry.file_mtime,
        "file_size": bag_cache_entry.file_size,
        "bag_info": {
            "file_path": bag_cache_entry.bag_info.file_path,
            "analysis_level": bag_cache_entry.bag_info.analysis_level.value,
            "last_updated": bag_cache_entry.bag_info.last_updated,
            "topics": bag_cache_entry.bag_info.topics,
            "connections": bag_cache_entry.bag_info.connections,
            "time_range": bag_cache_entry.bag_info.time_range,
            "duration_seconds": bag_cache_entry.bag_info.duration_seconds,
            "total_messages": bag_cache_entry.bag_info.total_messages,
            "total_size": bag_cache_entry.bag_info.total_size,
            "message_counts": bag_cache_entry.bag_info.message_counts,
            "topic_sizes": bag_cache_entry.bag_info.topic_sizes
        }
    }
    
    if include_messages and bag_cache_entry.cached_messages:
        data["cached_messages"] = {
            topic: [{"timestamp": msg.timestamp, "message_data": msg.message_data} 
                   for msg in messages[:10]]  # Limit to first 10 messages per topic
            for topic, messages in bag_cache_entry.cached_messages.items()
        }
    
    return data


def _print_bag_cache_details(console, key, bag_cache_entry):
    """Print detailed information for a bag cache entry"""
    
    console.print(f"\n[bold cyan]Bag Cache Details: {key}[/bold cyan]")
    
    # Create tree structure for bag info
    tree = Tree("Bag Information")
    
    # Basic info
    basic_tree = tree.add("Basic Information")
    basic_tree.add(f"File Path: {bag_cache_entry.bag_info.file_path}")
    basic_tree.add(f"Analysis Level: {bag_cache_entry.bag_info.analysis_level.value}")
    basic_tree.add(f"Last Updated: {bag_cache_entry.bag_info.last_updated}")
    basic_tree.add(f"Cache Timestamp: {bag_cache_entry.cache_timestamp}")
    
    # Topics info
    if bag_cache_entry.bag_info.topics:
        topics_tree = tree.add(f"Topics ({len(bag_cache_entry.bag_info.topics)})")
        for topic in bag_cache_entry.bag_info.topics[:10]:  # Show first 10
            msg_type = bag_cache_entry.bag_info.connections.get(topic, "Unknown") if bag_cache_entry.bag_info.connections else "Unknown"
            topics_tree.add(f"{topic} ({msg_type})")
        if len(bag_cache_entry.bag_info.topics) > 10:
            topics_tree.add(f"... and {len(bag_cache_entry.bag_info.topics) - 10} more")
    
    # Statistics
    if bag_cache_entry.bag_info.total_messages:
        stats_tree = tree.add("Statistics")
        stats_tree.add(f"Total Messages: {bag_cache_entry.bag_info.total_messages:,}")
        if bag_cache_entry.bag_info.total_size:
            stats_tree.add(f"Total Size: {_format_size(bag_cache_entry.bag_info.total_size)}")
        if bag_cache_entry.bag_info.duration_seconds:
            stats_tree.add(f"Duration: {bag_cache_entry.bag_info.duration_seconds:.2f} seconds")
    
    # Cached messages
    if bag_cache_entry.cached_messages:
        msg_tree = tree.add(f"Cached Messages ({len(bag_cache_entry.cached_messages)} topics)")
        for topic, messages in bag_cache_entry.cached_messages.items():
            msg_tree.add(f"{topic}: {len(messages)} messages")
    
    console.print(tree)


def _get_content_preview(cached_data):
    """Get a preview of cache content"""
    
    if cached_data is None:
        return "None"
    
    if isinstance(cached_data, BagCacheEntry):
        bag_info = cached_data.bag_info
        topics_count = len(bag_info.topics) if bag_info.topics else 0
        messages_count = bag_info.total_messages or 0
        return f"Bag: {topics_count} topics, {messages_count} messages"
    
    try:
        content_str = str(cached_data)
        return content_str[:50] + "..." if len(content_str) > 50 else content_str
    except:
        return "Unable to preview"


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Entry point for the tools command"""
    app()


if __name__ == "__main__":
    main() 