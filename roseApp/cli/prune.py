"""
Cache management command for ROS bag analysis results.
This module provides cache cleaning functionality for both legacy and async caches.
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from ..core.theme import theme

# Import async analyzer for cache management
try:
    from ..core.async_analyzer import get_async_analyzer
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

# Create app instance
app = typer.Typer(name="prune", help="Manage analysis cache")

# Cache directory for analysis results
CACHE_DIR = Path.home() / ".cache" / "rose" / "bag_analysis"


def _get_cache_info():
    """Get information about the cache directory"""
    if not CACHE_DIR.exists():
        return {
            'exists': False,
            'total_files': 0,
            'total_size': 0,
            'files': []
        }
    
    files = []
    total_size = 0
    
    for cache_file in CACHE_DIR.glob("*.pkl"):
        try:
            stat = cache_file.stat()
            
            # Try to read original bag path from cache file
            original_bag_path = "Unknown"
            try:
                import pickle
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    original_bag_path = cache_data.get('original_bag_path', 'Unknown')
            except Exception:
                # If can't read cache file, use "Unknown"
                pass
            
            files.append({
                'path': cache_file,
                'name': cache_file.name,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'original_bag_path': original_bag_path
            })
            total_size += stat.st_size
        except OSError:
            # Skip files that can't be accessed
            continue
    
    # Sort by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    
    # Add index numbers to each file
    for i, file_info in enumerate(files, 1):
        file_info['index'] = i
    
    return {
        'exists': True,
        'total_files': len(files),
        'total_size': total_size,
        'files': files
    }


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def _format_age(timestamp: float) -> str:
    """Format timestamp to human readable age"""
    import time
    age_seconds = time.time() - timestamp
    
    if age_seconds < 60:
        return f"{int(age_seconds)}s ago"
    elif age_seconds < 3600:
        return f"{int(age_seconds / 60)}m ago"
    elif age_seconds < 86400:
        return f"{int(age_seconds / 3600)}h ago"
    else:
        return f"{int(age_seconds / 86400)}d ago"


@app.command()
def clean(
    all: bool = typer.Option(False, "--all", "-a", help="Clean all cache files"),
    older_than: Optional[int] = typer.Option(None, "--older-than", "-o", help="Clean cache files older than N days"),
    ids: Optional[str] = typer.Option(None, "--ids", "-i", help="Clean cache files by ID numbers (comma-separated, e.g., 1,3,5)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be cleaned without actually doing it"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """
    Clean analysis cache files
    
    You must specify either --ids or --all option.
    
    Examples:
        # Clean all cache files
        python -m roseApp.rose prune clean --all
        
        # Clean cache files older than 7 days
        python -m roseApp.rose prune clean --older-than 7
        
        # Clean specific cache files by ID
        python -m roseApp.rose prune clean --ids 1,3,5
        
        # Dry run to see what would be cleaned
        python -m roseApp.rose prune clean --all --dry-run
    """
    console = Console()
    
    # Get cache information
    cache_info = _get_cache_info()
    
    if not cache_info['exists'] or cache_info['total_files'] == 0:
        console.print("[yellow]No cache files found[/yellow]")
        console.print(f"Cache directory: {CACHE_DIR}")
        return
    
    # Show current cache status
    console.print(f"[bold]Cache Status[/bold]")
    console.print(f"Directory: {CACHE_DIR}")
    console.print(f"Files: {cache_info['total_files']}")
    console.print(f"Total size: {_format_size(cache_info['total_size'])}")
    console.print()
    
    # Determine files to clean
    files_to_clean = []
    
    if all:
        files_to_clean = cache_info['files']
    elif older_than is not None:
        import time
        cutoff_time = time.time() - (older_than * 24 * 3600)  # Convert days to seconds
        files_to_clean = [f for f in cache_info['files'] if f['modified'] < cutoff_time]
    elif ids is not None:
        # Parse IDs and find matching files
        try:
            id_list = [int(x.strip()) for x in ids.split(',') if x.strip()]
            id_set = set(id_list)
            files_to_clean = [f for f in cache_info['files'] if f['index'] in id_set]
            
            # Check for invalid IDs
            found_ids = {f['index'] for f in files_to_clean}
            invalid_ids = id_set - found_ids
            if invalid_ids:
                console.print(f"[red]Warning: Invalid cache IDs: {', '.join(map(str, sorted(invalid_ids)))}[/red]")
                console.print(f"[dim]Valid IDs are: 1-{cache_info['total_files']}[/dim]")
                
        except ValueError:
            console.print("[red]Error: Invalid ID format. Use comma-separated numbers (e.g., 1,3,5)[/red]")
            return
    else:
        # Must specify --ids or --all
        console.print("[red]Error: Must specify --ids or --all to clean cache files[/red]")
        console.print("\nAvailable cache files:")
        _show_cache_details(console, cache_info)
        console.print(f"[dim]Use 'clean --ids 1,2,3' to clean specific files or 'clean --all' to clean all files[/dim]")
        return
    
    if not files_to_clean:
        console.print("[green]No files match the cleaning criteria[/green]")
        return
    
    # Show what will be cleaned
    total_clean_size = sum(f['size'] for f in files_to_clean)
    
    if dry_run:
        console.print(f"[bold yellow]Dry Run - Would clean {len(files_to_clean)} files ({_format_size(total_clean_size)})[/bold yellow]")
    else:
        console.print(f"[bold]Cleaning {len(files_to_clean)} files ({_format_size(total_clean_size)})[/bold]")
    
    if verbose or dry_run:
        console.print("\nFiles to clean:")
        for file_info in files_to_clean:
            console.print(f"[{theme.ACCENT}]{file_info['index']}.[/{theme.ACCENT}] [bold]{file_info['original_bag_path']}[/bold]")
            console.print(f"   Size: {_format_size(file_info['size'])}")
            console.print(f"   Modified: {_format_age(file_info['modified'])}")
            console.print(f"   Cache: {file_info['name']}")
            console.print()
    
    if dry_run:
        return
    
    # Actually clean the files
    cleaned_count = 0
    failed_count = 0
    
    for file_info in files_to_clean:
        try:
            file_info['path'].unlink()
            cleaned_count += 1
            if verbose:
                console.print(f"[{theme.SUCCESS}]✓ Removed cache file #{file_info['index']}: {file_info['name']}[/{theme.SUCCESS}]")
        except OSError as e:
            if verbose:
                console.print(f"[red]✗ Failed to remove {file_info['name']}: {e}[/red]")
            failed_count += 1
    
    # Show results
    if cleaned_count > 0:
        console.print(f"[{theme.SUCCESS}]✓ Successfully cleaned {cleaned_count} files ({_format_size(total_clean_size)})[/{theme.SUCCESS}]")
    
    if failed_count > 0:
        console.print(f"[red]✗ Failed to clean {failed_count} files[/red]")


@app.command()
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information about each cache file")
):
    """
    Show cache status and statistics
    
    Examples:
        # Show basic cache status
        python -m roseApp.rose prune status
        
        # Show detailed information about each cache file
        python -m roseApp.rose prune status --verbose
    """
    console = Console()
    
    cache_info = _get_cache_info()
    
    if not cache_info['exists']:
        console.print("[yellow]Cache directory does not exist[/yellow]")
        console.print(f"Directory: {CACHE_DIR}")
        return
    
    if cache_info['total_files'] == 0:
        console.print("[yellow]No cache files found[/yellow]")
        console.print(f"Directory: {CACHE_DIR}")
        return
    
    # Show summary
    panel_content = Text()
    panel_content.append(f"Directory: {CACHE_DIR}\n")
    panel_content.append(f"Files: {cache_info['total_files']}\n", style=f"bold {theme.ACCENT}")
    panel_content.append(f"Total size: {_format_size(cache_info['total_size'])}", style=f"bold {theme.ACCENT}")
    
    panel = Panel(
        panel_content,
        title="Cache Status",
        border_style=theme.ACCENT
    )
    console.print(panel)
    
    # Always show cache details with ID numbers
    console.print()
    _show_cache_details(console, cache_info)
    
    if not verbose:
        console.print(f"\n[dim]Use 'clean --ids 1,2,3' to clean specific files or 'clean --all' to clean all files[/dim]")


def _show_cache_details(console: Console, cache_info: dict):
    """Show detailed information about cache files in list format"""
    if not cache_info['files']:
        return
    
    for file_info in cache_info['files']:
        console.print(f"[{theme.ACCENT}]{file_info['index']}.[/{theme.ACCENT}] [bold]{file_info['original_bag_path']}[/bold]")
        console.print(f"   Size: {_format_size(file_info['size'])}")
        console.print(f"   Modified: {_format_age(file_info['modified'])}")
        console.print(f"   Cache: {file_info['name']}")
        console.print()  # Empty line between entries


@app.command()
def clear(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Clear all cache files (alias for clean --all)
    
    This is a convenience command that removes all cache files.
    
    Examples:
        # Clear all cache files (with confirmation)
        python -m roseApp.rose prune clear
        
        # Clear all cache files (skip confirmation)
        python -m roseApp.rose prune clear --yes
    """
    console = Console()
    
    cache_info = _get_cache_info()
    
    if not cache_info['exists'] or cache_info['total_files'] == 0:
        console.print("[yellow]No cache files to clear[/yellow]")
        return
    
    # Show what will be cleared
    console.print(f"[bold]Found {cache_info['total_files']} cache files ({_format_size(cache_info['total_size'])})[/bold]")
    
    if not confirm:
        result = typer.confirm("Do you want to clear all cache files?")
        if not result:
            console.print("Operation cancelled")
            return
    
    # Clear all files
    try:
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        console.print(f"[{theme.SUCCESS}]✓ Successfully cleared all cache files[/{theme.SUCCESS}]")
    except Exception as e:
        console.print(f"[red]✗ Failed to clear cache: {e}[/red]")


@app.command("async-status")
def async_status():
    """
    Show async cache status and performance information
    
    Examples:
        # Show async cache status
        python -m roseApp.rose prune async-status
    """
    console = Console()
    
    if not ASYNC_AVAILABLE:
        console.print("[red]Async analyzer not available[/red]")
        return
    
    try:
        analyzer = get_async_analyzer()
        cache_info = analyzer.get_cache_info()
        
        if cache_info["cached_bags"] == 0:
            console.print("[yellow]No async cache data found[/yellow]")
            return
        
        # Show summary
        panel_content = Text()
        panel_content.append(f"Cached Bags: {cache_info['cached_bags']}\n", style=f"bold {theme.ACCENT}")
        panel_content.append("Memory-based intelligent caching active", style=f"bold {theme.SUCCESS}")
        
        panel = Panel(
            panel_content,
            title="Async Cache Status",
            border_style=theme.ACCENT
        )
        console.print(panel)
        
        # Show detailed information
        console.print()
        for i, (key, details) in enumerate(cache_info['cache_details'].items(), 1):
            console.print(f"[{theme.ACCENT}]{i}.[/{theme.ACCENT}] [bold]{details['bag_path']}[/bold]")
            console.print(f"   Cache Level: {details['cache_level']} ({'complete' if details['is_complete'] else 'partial'})")
            console.print(f"   Topics: {details['topics']}")
            console.print(f"   Messages: {details['total_messages']:,}")
            console.print(f"   Cache Key: {key[:16]}...")
            console.print()
            
        console.print(f"[dim]Async cache uses intelligent memory-based storage for optimal performance[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error getting async cache status: {e}[/red]")


@app.command("clear-async")
def clear_async():
    """
    Clear async cache (memory-based cache)
    
    Examples:
        # Clear async cache
        python -m roseApp.rose prune clear-async
    """
    console = Console()
    
    if not ASYNC_AVAILABLE:
        console.print("[red]Async analyzer not available[/red]")
        return
    
    try:
        analyzer = get_async_analyzer()
        cache_info = analyzer.get_cache_info()
        
        if cache_info["cached_bags"] == 0:
            console.print("[yellow]No async cache to clear[/yellow]")
            return
        
        cached_count = cache_info["cached_bags"]
        analyzer.clear_cache()
        
        console.print(f"[{theme.SUCCESS}]✓ Cleared async cache for {cached_count} bags[/{theme.SUCCESS}]")
        
    except Exception as e:
        console.print(f"[red]Error clearing async cache: {e}[/red]")


def main():
    """Entry point for the prune command"""
    app()


if __name__ == "__main__":
    main() 