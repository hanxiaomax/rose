#!/usr/bin/env python3
"""
Tools command for ROS bag analysis utilities
Provides cache management, diagnostics, and other utility functions
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.bag_manager import BagManager, DiagnoseOptions
from ..core.result_handler import ResultHandler, OutputFormat, RenderOptions
from ..core.cache import get_cache
from ..core.theme import get_current_colors

app = typer.Typer(name="tools", help="Utility tools for cache management, diagnostics, and system info")


# =============================================================================
# Cache Management Commands
# =============================================================================

@app.command()
def cache_status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed cache information")
):
    """
    Show cache status and statistics
    
    Examples:
        rose tools cache-status
        rose tools cache-status --verbose
    """
    console = Console()
    
    try:
        cache = get_cache()
        
        # Get cache statistics
        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
            
            # Extract unified stats from the complex structure
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
            
            if verbose:
                console.print("\nDetailed Cache Information:")
                console.print(f"  Memory Entries: {memory_stats.get('entry_count', 0):,}")
                console.print(f"  File Entries: {file_stats.get('entry_count', 0):,}")
                console.print(f"  Total Entries: {unified_stats.get('entry_count', 0):,}")
                console.print(f"  Evictions: {unified_stats.get('evictions', 0):,}")
        else:
            console.print("[yellow]Cache statistics not available for this cache type[/yellow]")
            console.print(f"Cache Type: {type(cache).__name__}")
            
    except Exception as e:
        console.print(f"[red]Error getting cache status: {e}[/red]")


@app.command()
def cache_clear(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
):
    """
    Clear all cache data
    
    Examples:
        rose tools cache-clear
        rose tools cache-clear --yes
    """
    console = Console()
    
    try:
        cache = get_cache()
        
        # Get current cache info before clearing
        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
            unified_stats = stats.get('unified', {})
            total_requests = unified_stats.get('hits', 0) + unified_stats.get('misses', 0)
            entry_count = unified_stats.get('entry_count', 0)
            
            if entry_count == 0:
                console.print("[yellow]No cache data to clear[/yellow]")
                return
            
            console.print(f"[bold]Found cache data with {entry_count:,} entries and {total_requests:,} total requests[/bold]")
        else:
            console.print("[bold]Found cache data[/bold]")
        
        if not confirm:
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
            
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


@app.command()
def cache_info():
    """
    Show detailed cache information and keys
    
    Examples:
        rose tools cache-info
    """
    console = Console()
    
    try:
        cache = get_cache()
        
        # Show basic cache info
        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
            unified_stats = stats.get('unified', {})
            memory_stats = stats.get('memory', {})
            file_stats = stats.get('file', {})
            
            console.print("[bold]Cache Information[/bold]")
            console.print(f"Cache Type: {type(cache).__name__}")
            console.print(f"Hit Rate: {unified_stats.get('hit_rate', 0) * 100:.1f}%")
            console.print(f"Total Entries: {unified_stats.get('entry_count', 0):,}")
            console.print(f"Memory Entries: {memory_stats.get('entry_count', 0):,}")
            console.print(f"File Entries: {file_stats.get('entry_count', 0):,}")
            
            # Show cache keys if available
            if hasattr(cache.memory_cache, 'keys'):
                memory_keys = cache.memory_cache.keys()
                if memory_keys:
                    console.print(f"\nMemory Cache Keys ({len(memory_keys)}):")
                    for i, key in enumerate(memory_keys[:10], 1):  # Show first 10
                        console.print(f"  {i}. {key[:60]}...")
                    if len(memory_keys) > 10:
                        console.print(f"  ... and {len(memory_keys) - 10} more")
            
            if hasattr(cache.file_cache, 'keys'):
                file_keys = cache.file_cache.keys()
                if file_keys:
                    console.print(f"\nFile Cache Keys ({len(file_keys)}):")
                    for i, key in enumerate(file_keys[:10], 1):  # Show first 10
                        console.print(f"  {i}. {key[:60]}...")
                    if len(file_keys) > 10:
                        console.print(f"  ... and {len(file_keys) - 10} more")
        else:
            console.print("[yellow]Cache information not available[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error getting cache info: {e}[/red]")


# =============================================================================
# Diagnostic Commands
# =============================================================================

@app.command()
def diagnose_system():
    """
    Run system diagnostics to check environment and dependencies
    
    Examples:
        rose tools diagnose-system
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


@app.command()
def diagnose_bag(
    bag_path: str = typer.Argument(..., help="Path to bag file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed diagnostic information"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save diagnostic report to file"),
    format: str = typer.Option("table", "--format", help="Output format (table, json, yaml, html)")
):
    """
    Diagnose bag file for potential issues and problems
    
    Examples:
        rose tools diagnose-bag /path/to/bag.bag
        rose tools diagnose-bag /path/to/bag.bag --verbose
        rose tools diagnose-bag /path/to/bag.bag --output report.html --format html
    """
    console = Console()
    
    # Validate bag file exists
    bag_path_obj = Path(bag_path)
    if not bag_path_obj.exists():
        console.print(f"[red]Error: Bag file not found: {bag_path}[/red]")
        raise typer.Exit(1)
    
    # Convert format string to enum
    try:
        output_format = OutputFormat(format.lower())
    except ValueError:
        supported = ", ".join([fmt.value for fmt in OutputFormat])
        console.print(f"[red]Error: Unsupported format '{format}'. Supported: {supported}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[bold green]🔍 Bag Diagnostics: {bag_path}[/bold green]")
    
    try:
        # Create BagManager and run diagnostics
        manager = BagManager()
        
        # Show progress
        with console.status("Running bag diagnostics..."):
            options = DiagnoseOptions(
                check_integrity=True,
                check_timestamps=True,
                check_message_counts=True,
                detailed=verbose
            )
            
            result = await_sync(manager.diagnose_bag(bag_path_obj, options))
        
        # Get result handler and display/export results
        handler = manager.get_result_handler()
        
        if output:
            # Export to file
            from ..core.result_handler import ExportOptions
            export_options = ExportOptions(
                format=output_format,
                output_file=output,
                pretty=True
            )
            success = handler.export(result, export_options)
            if success:
                console.print(f"[green]Diagnostic report saved to: {output}[/green]")
            else:
                console.print("[red]Failed to save diagnostic report[/red]")
                raise typer.Exit(1)
        else:
            # Display to console
            render_options = RenderOptions(
                format=output_format,
                verbose=verbose,
                show_summary=True,
                color=True,
                title=f"Diagnostic Report for {bag_path_obj.name}"
            )
            handler.render(result, render_options)
        
        # Show summary
        summary = result['summary']
        console.print()
        if summary['failed_checks'] == 0:
            console.print("[bold green]✅ All diagnostic checks passed[/bold green]")
        else:
            console.print(f"[bold red]❌ {summary['failed_checks']} diagnostic checks failed[/bold red]")
            
        if summary['warnings_count'] > 0:
            console.print(f"[bold yellow]⚠️  {summary['warnings_count']} warnings found[/bold yellow]")
        
        manager.cleanup()
        
    except Exception as e:
        console.print(f"[red]Error during bag diagnostics: {e}[/red]")
        raise typer.Exit(1)


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


def await_sync(coro):
    """Helper to run async function in sync context"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Entry point for the tools command"""
    app()


if __name__ == "__main__":
    main() 