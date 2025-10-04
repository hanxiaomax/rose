#!/usr/bin/env python3
"""
Theme Display Test Script

Displays all typical Rose theme components and their colors for visual verification.
This script helps developers and users preview theme colors and ensure proper rendering.

Usage:
    python tests/test_theme_display.py
    python tests/test_theme_display.py --theme rose.theme.custom.yaml
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from roseApp.ui.theme import get_color


def display_banner():
    """Display Rose banner"""
    console = Console()
    banner = """
    ██████╗  ██████╗ ███████╗███████╗
    ██╔══██╗██╔═══██╗██╔════╝██╔════╝
    ██████╔╝██║   ██║███████╗█████╗  
    ██╔══██╗██║   ██║╚════██║██╔══╝  
    ██║  ██║╚██████╔╝███████║███████╗
    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝
    ROSE Theme Display Test
    """
    console.print(Panel(banner, border_style=get_color('primary'), title="Rose Theme Test"))


def display_basic_colors(console: Console):
    """Display basic color palette"""
    console.print("\n[bold]Basic Color Palette[/bold]\n")
    
    colors = [
        ('primary', 'Primary accent color'),
        ('accent', 'Secondary accent color'),
        ('success', 'Success messages'),
        ('warning', 'Warning messages'),
        ('error', 'Error messages'),
        ('info', 'Information messages'),
        ('muted', 'Muted/dimmed text'),
        ('highlight', 'Highlighted text'),
    ]
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Color Name", style="cyan", width=20)
    table.add_column("Sample Text", width=30)
    table.add_column("Description", width=40)
    
    for color_name, description in colors:
        color = get_color(color_name)
        sample = Text("The quick brown fox", style=color)
        table.add_row(color_name, sample, description)
    
    console.print(table)


def display_semantic_colors(console: Console):
    """Display semantic colors"""
    console.print("\n[bold]Semantic Colors[/bold]\n")
    
    colors = [
        ('path', 'File and directory paths'),
    ]
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Color Name", style="cyan", width=20)
    table.add_column("Sample Text", width=30)
    table.add_column("Usage", width=40)
    
    for color_name, usage in colors:
        color = get_color(color_name)
        sample = Text(f"example_{color_name}.bag", style=color)
        table.add_row(color_name, sample, usage)
    
    console.print(table)


def display_message_examples(console: Console):
    """Display different message types"""
    console.print("\n[bold]Message Type Examples[/bold]\n")
    
    console.print(f"[{get_color('success')}]SUCCESS: Operation completed successfully[/{get_color('success')}]")
    console.print(f"[{get_color('warning')}]WARNING: Memory usage is high[/{get_color('warning')}]")
    console.print(f"[{get_color('error')}]ERROR: File not found[/{get_color('error')}]")
    console.print(f"[{get_color('info')}]INFO: Loading bag file...[/{get_color('info')}]")
    console.print(f"[{get_color('muted')}]Debug: Verbose output enabled[/{get_color('muted')}]")
    console.print(f"[{get_color('highlight')}]IMPORTANT: Action required[/{get_color('highlight')}]")


def display_ui_components(console: Console):
    """Display typical UI components"""
    console.print("\n[bold]UI Component Examples[/bold]\n")
    
    # Status items
    console.print(f"[bold {get_color('info')}]Status Items:[/bold {get_color('info')}]")
    console.print(f"  [{get_color('muted')}]Working Directory:[/{get_color('muted')}] [{get_color('accent')}]/workspaces/rose[/{get_color('accent')}]")
    console.print(f"  [{get_color('muted')}]Configuration:[/{get_color('muted')}] [{get_color('accent')}]rose.config.yaml[/{get_color('accent')}]")
    console.print(f"  [{get_color('muted')}]Cache:[/{get_color('muted')}] [{get_color('accent')}]5 entries, 10.5 MB[/{get_color('accent')}]")
    
    console.print()
    
    # Command help
    console.print(f"[bold {get_color('primary')}]Command Help:[/bold {get_color('primary')}]")
    console.print(f"  [{get_color('accent')}]/load[/{get_color('accent')}]           - Load bag files")
    console.print(f"  [{get_color('accent')}]/extract[/{get_color('accent')}]        - Extract topics from bags")
    console.print(f"  [{get_color('accent')}]/inspect[/{get_color('accent')}]        - Inspect bag contents")
    
    console.print()
    
    # File and directory items
    console.print(f"[bold {get_color('info')}]Path Listings:[/bold {get_color('info')}]")
    console.print(f"  [{get_color('path')}]demo.bag[/{get_color('path')}] [{get_color('muted')}](1.2 GB)[/{get_color('muted')}]")
    console.print(f"  [{get_color('path')}]sensor_data.bag[/{get_color('path')}] [{get_color('muted')}](500 MB)[/{get_color('muted')}]")
    console.print(f"  [{get_color('path')}]output/[/{get_color('path')}]")
    
    console.print()
    
    # Topics
    console.print(f"[bold {get_color('info')}]Topic Listings:[/bold {get_color('info')}]")
    console.print(f"  [{get_color('accent')}]/camera/image_raw[/{get_color('accent')}] [{get_color('muted')}](sensor_msgs/Image)[/{get_color('muted')}]")
    console.print(f"  [{get_color('accent')}]/imu/data[/{get_color('accent')}] [{get_color('muted')}](sensor_msgs/Imu)[/{get_color('muted')}]")
    console.print(f"  [{get_color('accent')}]/gps/fix[/{get_color('accent')}] [{get_color('muted')}](sensor_msgs/NavSatFix)[/{get_color('muted')}]")


def display_panel_example(console: Console):
    """Display panel example"""
    console.print("\n[bold]Panel Example[/bold]\n")
    
    content = Text()
    content.append("Interactive Environment\n\n", style=f"bold {get_color('primary')}")
    
    content.append("Workspace Status:\n", style=f"bold {get_color('info')}")
    content.append("  Working Directory: ", style=get_color('muted'))
    content.append("/workspaces/rose\n", style=get_color('accent'))
    content.append("  Configuration: ", style=get_color('muted'))
    content.append("rose.config.yaml\n", style=get_color('accent'))
    content.append("  Cache: ", style=get_color('muted'))
    content.append("3 entries, 2.5 MB\n\n", style=get_color('accent'))
    
    content.append("Available commands:\n", style="bold")
    content.append("/load        - Load bag files\n", style=get_color('muted'))
    content.append("/extract     - Extract topics\n", style=get_color('muted'))
    content.append("/inspect     - Inspect contents\n\n", style=get_color('muted'))
    
    content.append("Features:\n", style=f"bold {get_color('success')}")
    content.append("  • Tab completion\n", style=get_color('muted'))
    content.append("  • Background tasks\n", style=get_color('muted'))
    content.append("  • Smart caching\n", style=get_color('muted'))
    
    panel = Panel(content, title="Interactive Environment", border_style=get_color('primary'))
    console.print(panel)


def display_table_example(console: Console):
    """Display table example"""
    console.print("\n[bold]Table Example[/bold]\n")
    
    table = Table(
        title="Bag File Analysis",
        show_header=True,
        header_style=f"bold {get_color('primary')}",
        border_style=get_color('accent')
    )
    
    table.add_column("Topic", style=get_color('accent'))
    table.add_column("Type", style=get_color('muted'))
    table.add_column("Count", style=get_color('info'), justify="right")
    table.add_column("Status", justify="center")
    
    table.add_row(
        "/camera/image_raw",
        "sensor_msgs/Image",
        "1,234",
        f"[{get_color('success')}]✓[/{get_color('success')}]"
    )
    table.add_row(
        "/imu/data",
        "sensor_msgs/Imu",
        "5,678",
        f"[{get_color('success')}]✓[/{get_color('success')}]"
    )
    table.add_row(
        "/gps/fix",
        "sensor_msgs/NavSatFix",
        "890",
        f"[{get_color('warning')}]![/{get_color('warning')}]"
    )
    
    console.print(table)


def display_progress_examples(console: Console):
    """Display progress and status indicators"""
    console.print("\n[bold]Progress and Status Indicators[/bold]\n")
    
    console.print(f"[{get_color('info')}]🔄 Loading bag file...[/{get_color('info')}]")
    console.print(f"[{get_color('success')}]✓ Bag loaded successfully[/{get_color('success')}]")
    console.print(f"[{get_color('warning')}]⚠ Cache size exceeds 1GB[/{get_color('warning')}]")
    console.print(f"[{get_color('error')}]✗ Failed to load bag file[/{get_color('error')}]")
    console.print(f"[{get_color('accent')}]→ Processing 1,234 messages...[/{get_color('accent')}]")
    console.print(f"[{get_color('muted')}]  Elapsed: 2.5s[/{get_color('muted')}]")


def display_color_grid(console: Console):
    """Display color grid for visual comparison"""
    console.print("\n[bold]Color Comparison Grid[/bold]\n")
    
    color_names = [
        'primary', 'accent', 'success', 'warning', 'error', 'info',
        'muted', 'highlight', 'path'
    ]
    
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Name", style="cyan", width=15)
    table.add_column("Block", width=10)
    table.add_column("Text", width=30)
    table.add_column("Bold", width=30)
    
    for color_name in color_names:
        color = get_color(color_name)
        block = f"[on {color}]          [/on {color}]"
        text = Text("Sample Text", style=color)
        bold_text = Text("Sample Text", style=f"bold {color}")
        table.add_row(color_name, block, text, bold_text)
    
    console.print(table)


def display_theme_info(console: Console, theme_file: Optional[str] = None):
    """Display theme information"""
    console.print("\n[bold]Theme Information[/bold]\n")
    
    if theme_file:
        console.print(f"Theme File: [{get_color('path')}]{theme_file}[/{get_color('path')}]")
    else:
        console.print(f"Theme File: [{get_color('muted')}]Default (rose.theme.default.yaml)[/{get_color('muted')}]")
    
    console.print(f"Terminal: [{get_color('info')}]{console.legacy_windows}[/{get_color('info')}]")
    console.print(f"Color System: [{get_color('info')}]{console.color_system}[/{get_color('info')}]")


def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Display Rose theme components and colors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_theme_display.py
  python tests/test_theme_display.py --theme rose.theme.custom.yaml
  python tests/test_theme_display.py --no-banner
        """
    )
    parser.add_argument(
        '--theme',
        type=str,
        help='Path to theme file to test'
    )
    parser.add_argument(
        '--no-banner',
        action='store_true',
        help='Skip banner display'
    )
    parser.add_argument(
        '--section',
        type=str,
        choices=['colors', 'semantic', 'messages', 'ui', 'panel', 'table', 'progress', 'grid', 'all'],
        default='all',
        help='Display specific section only'
    )
    
    args = parser.parse_args()
    
    # Load custom theme if specified
    if args.theme:
        try:
            # Set theme file in configuration
            from roseApp.core.config import get_config, update_config
            update_config(theme_file=args.theme)
            print(f"Loaded theme: {args.theme}")
        except Exception as e:
            print(f"Error loading theme: {e}")
            return 1
    
    console = Console()
    
    # Display banner
    if not args.no_banner:
        display_banner()
    
    # Display theme info
    display_theme_info(console, args.theme)
    
    # Display sections
    sections = {
        'colors': display_basic_colors,
        'semantic': display_semantic_colors,
        'messages': display_message_examples,
        'ui': display_ui_components,
        'panel': display_panel_example,
        'table': display_table_example,
        'progress': display_progress_examples,
        'grid': display_color_grid,
    }
    
    if args.section == 'all':
        for func in sections.values():
            func(console)
    else:
        sections[args.section](console)
    
    console.print(f"\n[{get_color('muted')}]Theme test complete. Press Ctrl+C to exit.[/{get_color('muted')}]\n")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

