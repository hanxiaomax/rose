#!/usr/bin/env python3
"""
Diagnostic command for ROS bag parser and performance issues.
"""

import os
import sys
import time
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core.util import get_logger, set_app_mode, AppMode
from ..core.parser_manager import get_parser_manager, diagnose_bag_parsers
from ..core.parser import ParserType
from .error_handling import ValidationError, validate_file_exists, handle_runtime_error

app = typer.Typer(name="diagnose", help="Diagnostic tools for parser and performance issues")


@app.command()
def system():
    """Run system diagnostics"""
    set_app_mode(AppMode.CLI)
    console = Console()
    
    console.print("[bold green]🔍 System Diagnostics[/bold green]")
    console.print()
    
    # Check Python
    console.print(f"Python Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check dependencies
    console.print("Dependencies:")
    try:
        import rosbags
        console.print(f"  ✅ rosbags: {getattr(rosbags, '__version__', 'unknown')}")
    except ImportError:
        console.print("  ❌ rosbags: Not installed")
    
    console.print("  ✅ rich: Available")
    console.print("  ✅ typer: Available")
    
    # Check ROS
    console.print(f"ROS Distro: {os.environ.get('ROS_DISTRO', 'Not set')}")
    
    console.print()
    console.print("[bold green]✅ System check complete[/bold green]")


@app.command()
def bag(bag_path: str = typer.Argument(..., help="Path to bag file")):
    """Diagnose bag file issues"""
    set_app_mode(AppMode.CLI)
    console = Console()
    
    console.print(f"[bold green]🔍 Bag Diagnostics: {bag_path}[/bold green]")
    console.print()
    
    try:
        validate_file_exists(bag_path, "bag file")
        
        # File info
        stat = os.stat(bag_path)
        size_mb = stat.st_size / (1024 * 1024)
        console.print(f"File Size: {size_mb:.1f} MB")
        
        # Parser diagnostics
        diagnostics = diagnose_bag_parsers(bag_path)
        
        console.print("Parser Status:")
        for parser_type, info in diagnostics.items():
            if info['available']:
                health = info['health'].value
                console.print(f"  {parser_type.name}: {health}")
            else:
                console.print(f"  {parser_type.name}: Not available")
        
        # Recommendations
        console.print("\nRecommendations:")
        if size_mb > 1024:
            console.print("  - Large file detected - use rosbags parser for best performance")
        
        rosbags_available = diagnostics.get(ParserType.ROSBAGS, {}).get('available', False)
        if not rosbags_available:
            console.print("  - Install rosbags library: pip install rosbags")
        
        console.print()
        console.print("[bold green]✅ Bag diagnostics complete[/bold green]")
        
    except Exception as e:
        handle_runtime_error(e, "Bag diagnostics")


if __name__ == "__main__":
    app() 