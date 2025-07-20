#!/usr/bin/env python3
"""
Tools command for ROS bag analysis utilities
Provides cache management, diagnostics, and other utility functions
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.cache import get_cache

app = typer.Typer(name="tools", help="Utility tools for cache management, diagnostics, and system info")


# =============================================================================
# Cache Management Command
# =============================================================================

@app.command()
def cache(
    delete: Optional[List[int]] = typer.Option(None, "--delete", "-D", help="Delete cache entries by index numbers"),
    clear: bool = typer.Option(False, "--clear", help="Clear all cache data"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Manage cache data - show status, info, and perform operations
    
    Examples:
        rose tools cache                    # Show cache status and info
        rose tools cache -D 1,3,5         # Delete specific cache entries
        rose tools cache --clear           # Clear all cache data
        rose tools cache --clear -y       # Clear without confirmation
    """
    console = Console()
    
    try:
        cache = get_cache()
        
        if clear:
            # Clear all cache data
            _clear_cache(cache, console, yes)
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
    panel_content.append(f"Hit Rate: {unified_stats.get('hit_rate', 0) * 100:.1f}%\n", style="bold green")
    
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
    
    panel = Panel(
        panel_content,
        title="Cache Status",
        border_style="blue"
    )
    console.print(panel)
    
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
# Main Entry Point
# =============================================================================

def main():
    """Entry point for the tools command"""
    app()


if __name__ == "__main__":
    main() 