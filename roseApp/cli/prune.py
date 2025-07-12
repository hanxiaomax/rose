"""
Cache management command for ROS bag analysis results.
This module provides cache cleaning functionality.
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
            files.append({
                'path': cache_file,
                'name': cache_file.name,
                'size': stat.st_size,
                'modified': stat.st_mtime
            })
            total_size += stat.st_size
        except OSError:
            # Skip files that can't be accessed
            continue
    
    # Sort by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be cleaned without actually doing it"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """
    Clean analysis cache files
    
    Examples:
        # Show cache status
        python -m roseApp.rose prune clean
        
        # Clean all cache files
        python -m roseApp.rose prune clean --all
        
        # Clean cache files older than 7 days
        python -m roseApp.rose prune clean --older-than 7
        
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
    else:
        # Just show status, don't clean anything
        if verbose:
            _show_cache_details(console, cache_info)
        else:
            console.print("Use --all to clean all files or --older-than N to clean files older than N days")
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
        table = Table(show_header=True, header_style="bold")
        table.add_column("File", style=theme.PRIMARY)
        table.add_column("Size", justify="right")
        table.add_column("Age", justify="right")
        
        for file_info in files_to_clean:
            table.add_row(
                file_info['name'][:50] + ("..." if len(file_info['name']) > 50 else ""),
                _format_size(file_info['size']),
                _format_age(file_info['modified'])
            )
        
        console.print(table)
    
    if dry_run:
        return
    
    # Actually clean the files
    cleaned_count = 0
    failed_count = 0
    
    for file_info in files_to_clean:
        try:
            file_info['path'].unlink()
            cleaned_count += 1
        except OSError as e:
            if verbose:
                console.print(f"[red]Failed to remove {file_info['name']}: {e}[/red]")
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
    
    if verbose:
        console.print()
        _show_cache_details(console, cache_info)


def _show_cache_details(console: Console, cache_info: dict):
    """Show detailed information about cache files"""
    if not cache_info['files']:
        return
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("File", style=theme.PRIMARY)
    table.add_column("Size", justify="right")
    table.add_column("Age", justify="right", style="dim")
    
    for file_info in cache_info['files']:
        # Truncate long filenames
        display_name = file_info['name']
        if len(display_name) > 60:
            display_name = display_name[:30] + "..." + display_name[-27:]
        
        table.add_row(
            display_name,
            _format_size(file_info['size']),
            _format_age(file_info['modified'])
        )
    
    console.print(table)


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


def main():
    """Entry point for the prune command"""
    app()


if __name__ == "__main__":
    main() 