#!/usr/bin/env python3
"""
Cache command for ROS bag analysis utilities
Provides cache management, viewing, and export functionality
"""

import json
import yaml
import pickle
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.json import JSON

from ..core.cache import get_cache, BagCacheEntry
from ..core.theme_config import UnifiedThemeManager, ComponentType

app = typer.Typer(name="cache", help="Cache management commands")


# =============================================================================
# Main Cache Commands
# =============================================================================


@app.callback(invoke_without_command=True)
def cache_default(
    ctx: typer.Context,
    show_content: bool = typer.Option(False, "--content", "-c", help="Show detailed cache content"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """
    Show cache information (default command when no subcommand is provided)
    
    Examples:
        rose cache                    # Show all cache entries
        rose cache --content          # Show detailed content
        rose cache --verbose          # Show verbose information
    """
    if ctx.invoked_subcommand is None:
        console = Console()
        
        try:
            cache = get_cache()
            _show_cache_info(cache, console, show_content, verbose)
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
    bag_path: Optional[str] = typer.Option(None, "--bag", "-b", help="Clear cache for specific bag file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Clear cache data
    
    Examples:
        rose cache clear                      # Clear all cache
        rose cache clear --bag /path/to.bag   # Clear bag cache
        rose cache clear -y                   # Clear without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        _clear_cache_entries(cache, console, bag_path, yes)
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


# =============================================================================
# Helper Functions
# =============================================================================

def _show_cache_info(cache, console, show_content, verbose):
    """Show cache information and entries"""
    try:
        stats = cache.get_stats()
        
        # Display cache summary
        panel_content = Text()
        panel_content.append(f"Cache Type: {type(cache).__name__}\n")
        panel_content.append(f"Cache Directory: {stats.get('cache_dir', 'N/A')}\n")
        panel_content.append(f"Total Entries: {stats.get('entry_count', 0):,}\n")
        panel_content.append(f"Memory Entries: {stats.get('memory_entries', 0):,}\n")
        panel_content.append(f"Total Size: {_format_size(stats.get('total_size_bytes', 0))}")
        
        cache_panel = Panel(
            panel_content,
            title="Cache Information",
            border_style=UnifiedThemeManager.get_color(ComponentType.CLI, 'info')
        )
        console.print(cache_panel)
        
        # Show cache entries
        _show_cache_entries(cache, console, show_content, verbose)
        
    except Exception as e:
        console.print(f"[red]Error getting cache info: {e}[/red]")


def _show_cache_entries(cache, console, show_content, verbose):
    """Show all cache entries"""
    try:
        # Get memory cache entries
        memory_entries = cache._memory_cache.items() if hasattr(cache, '_memory_cache') else []
        
        # Get file cache entries
        file_entries = []
        seen_keys = set()
        if hasattr(cache, 'cache_dir'):
            for file_path in cache.cache_dir.glob("*.pkl"):
                try:
                    with open(file_path, 'rb') as f:
                        value = pickle.load(f)
                    # Use filename as key (without .pkl extension)
                    key = file_path.stem
                    if key not in seen_keys:
                        file_entries.append((key, value))
                        seen_keys.add(key)
                except Exception:
                    continue
        
        total_entries = len(memory_entries) + len(file_entries)
        
        if total_entries == 0:
            console.print("\n[yellow]No cache entries found[/yellow]")
            return
        
        console.print(f"\n[bold]Cache Entries ({total_entries} total)[/bold]")
        
        # Show memory cache entries
        if memory_entries:
            console.print(f"\n[cyan]Memory Cache ({len(memory_entries)} entries):[/cyan]")
            for key, entry in memory_entries:
                _display_cache_entry(console, key, entry.value if hasattr(entry, 'value') else entry, 
                                   'memory', show_content, verbose)
        
        # Show file cache entries  
        if file_entries:
            console.print(f"\n[cyan]File Cache ({len(file_entries)} entries):[/cyan]")
            for key, value in file_entries:
                _display_cache_entry(console, key, value, 'file', show_content, verbose)
        
        console.print(f"\n[dim]Use 'rose cache clear' to delete all entries or 'rose cache clear --bag <path>' for specific bag[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error showing cache entries: {e}[/red]")


def _display_cache_entry(console, key, value, cache_type, show_content, verbose):
    """Display a single cache entry"""
    try:
        # Format key display
        key_display = key[:60] + "..." if len(key) > 60 else key
        
        if isinstance(value, BagCacheEntry):
            # Display bag cache entry
            bag_info = value.bag_info
            file_path = getattr(bag_info, 'file_path', 'Unknown')
            topics_count = len(getattr(bag_info, 'topics', []))
            duration = getattr(bag_info, 'duration_seconds', 0)
            
            console.print(f"  • [{cache_type}] {key_display}")
            console.print(f"    File: {file_path}")
            console.print(f"    Topics: {topics_count}, Duration: {duration:.1f}s")
            
            if show_content or verbose:
                console.print(f"    Cache Time: {time.ctime(value.cache_timestamp)}")
                console.print(f"    File Size: {_format_size(value.file_size)}")
                
                if verbose and hasattr(bag_info, 'topics') and bag_info.topics:
                    # Handle different topic formats
                    try:
                        topic_names = []
                        topics = bag_info.topics
                        
                        if isinstance(topics, list):
                            # List of strings or TopicInfo objects
                            for topic in topics[:5]:
                                if isinstance(topic, str):
                                    topic_names.append(topic)
                                elif hasattr(topic, 'name'):
                                    topic_names.append(topic.name)
                                else:
                                    topic_names.append(str(topic))
                        elif isinstance(topics, dict):
                            # Dictionary of topics
                            topic_names = list(topics.keys())[:5]
                        else:
                            # Single topic or other format
                            if hasattr(topics, 'name'):
                                topic_names = [topics.name]
                            else:
                                topic_names = [str(topics)]
                        
                        console.print(f"    Topics: {', '.join(topic_names)}" + 
                                    ("..." if len(getattr(bag_info, 'topics', [])) > 5 else ""))
                    except Exception as e:
                        console.print(f"    Topics: [Error displaying topics: {e}]")
        else:
            # Display generic cache entry
            content_preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            console.print(f"  • [{cache_type}] {key_display}")
            console.print(f"    Content: {content_preview}")
            
    except Exception as e:
        console.print(f"  • [{cache_type}] {key_display} [red](Error: {e})[/red]")


def _clear_cache_entries(cache, console, bag_path, skip_confirm):
    """Clear cache entries with optional bag path filtering"""
    try:
        stats = cache.get_stats()
        total_entries = stats.get('entry_count', 0) + stats.get('memory_entries', 0)
        
        if total_entries == 0:
            console.print("[yellow]No cache data to clear[/yellow]")
            return
        
        if bag_path:
            # Clear specific bag cache
            bag_path_obj = Path(bag_path)
            cache_key = cache.get_bag_cache_key(bag_path_obj)
            
            # Check if cache exists
            cached_data = cache.get(cache_key)
            if not cached_data:
                console.print(f"[yellow]No cache found for bag: {bag_path}[/yellow]")
                return
            
            console.print(f"[bold]Found cache for bag: {bag_path}[/bold]")
            
            if not skip_confirm:
                result = typer.confirm("Clear cache for this bag?")
                if not result:
                    console.print("Operation cancelled")
                    return
            
            # Clear specific bag cache
            success = cache.delete(cache_key)
            if success:
                console.print(f"[green]✓ Successfully cleared cache for {bag_path}[/green]")
            else:
                console.print(f"[red]✗ Failed to clear cache for {bag_path}[/red]")
        else:
            # Clear all cache
            console.print(f"[bold]Found {total_entries:,} cache entries[/bold]")
            
            if not skip_confirm:
                result = typer.confirm("Clear all cache data?")
                if not result:
                    console.print("Operation cancelled")
                    return
            
            # Clear all cache
            cache.clear()
            console.print("[green]✓ Successfully cleared all cache data[/green]")
            
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


def _export_cache_entries(cache, console, output_file, name, bag_path, format, include_messages):
    """Export cache entries to file"""
    try:
        # Get all cache entries
        all_entries = []
        
        # Get memory cache entries
        if hasattr(cache, '_memory_cache'):
            memory_entries = [(key, entry.value if hasattr(entry, 'value') else entry, 'memory') 
                            for key, entry in cache._memory_cache.items()]
            all_entries.extend(memory_entries)
        
        # Get file cache entries
        seen_keys = set()
        if hasattr(cache, 'cache_dir'):
            for file_path in cache.cache_dir.glob("*.pkl"):
                try:
                    with open(file_path, 'rb') as f:
                        value = pickle.load(f)
                    key = file_path.stem
                    if key not in seen_keys:
                        all_entries.append((key, value, 'file'))
                        seen_keys.add(key)
                except Exception:
                    continue
        
        if not all_entries:
            console.print("[yellow]No cache entries to export[/yellow]")
            return
        
        # Filter entries if criteria provided
        if name or bag_path:
            filtered_entries = []
            for key, value, cache_type in all_entries:
                match = False
                
                if name and name.lower() in key.lower():
                    match = True
                
                if bag_path and not match:
                    # Try to match bag path by generating expected cache key
                    try:
                        bag_path_obj = Path(bag_path)
                        expected_key = cache.get_bag_cache_key(bag_path_obj)
                        if key == expected_key:
                            match = True
                    except:
                        # Fallback to simple string matching
                        if bag_path.lower() in key.lower():
                            match = True
                
                if match:
                    filtered_entries.append((key, value, cache_type))
            
            if not filtered_entries:
                console.print("[yellow]No matching cache entries found[/yellow]")
                return
            all_entries = filtered_entries
        
        # Prepare export data
        export_data = _prepare_export_data(all_entries, include_messages)
        
        # Export to file
        output_path = Path(output_file)
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


def _prepare_export_data(all_entries, include_messages):
    """Prepare cache data for export"""
    export_data = {
        'metadata': {
            'export_time': time.time(),
            'total_entries': len(all_entries),
            'include_messages': include_messages
        },
        'entries': []
    }
    
    for key, value, cache_type in all_entries:
        try:
            entry_data = {
                'key': key,
                'type': cache_type,
                'timestamp': time.time()
            }
            
            # Add content based on type
            if isinstance(value, BagCacheEntry):
                entry_data['content'] = _bag_cache_to_dict(value, include_messages)
            else:
                content_str = str(value)
                entry_data['content'] = content_str[:200] + "..." if len(content_str) > 200 else content_str
            
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
            'file_path': getattr(bag_info, 'file_path', 'Unknown'),
            'topics_count': len(getattr(bag_info, 'topics', [])),
            'duration_seconds': getattr(bag_info, 'duration_seconds', 0),
            'cache_timestamp': bag_cache_entry.cache_timestamp,
            'file_mtime': bag_cache_entry.file_mtime,
            'file_size': bag_cache_entry.file_size
        }
        
        if hasattr(bag_info, 'topics') and bag_info.topics:
            result['topics'] = bag_info.topics
        
        if hasattr(bag_info, 'message_counts') and bag_info.message_counts:
            result['message_counts'] = bag_info.message_counts
            result['total_messages'] = sum(bag_info.message_counts.values())
        
        if include_messages and hasattr(bag_cache_entry, 'cached_messages') and bag_cache_entry.cached_messages:
            result['cached_messages'] = {
                topic: len(messages) for topic, messages in bag_cache_entry.cached_messages.items()
            }
        
        return result
        
    except Exception as e:
        return {'error': f'Failed to convert bag cache entry: {e}'}


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