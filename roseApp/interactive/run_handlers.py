#!/usr/bin/env python3
"""
Command handlers for Rose interactive run environment
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit.shortcuts import confirm
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
import typer

from roseApp.ui.theme import get_color
from roseApp.ui.common_ui import Message
from roseApp.core.util import get_logger
from roseApp.cli.util import check_and_load_bag_cache
# CLIAdapter removed - commands now handled directly
from .interactive_ui import InteractiveUI

logger = get_logger("run_handlers")


class RunCommandHandlers:
    """Command handlers for the interactive run environment"""
    
    def __init__(self, runner):
        self.runner = runner
        self.console = runner.console
        self.ui = runner.ui  # Use the UI from runner
        self.state = runner.state
        # CLIAdapter removed - commands now handled directly
        self.cache_manager = runner.cache_manager
        self.task_queue = runner.task_queue
        self.running_tasks = runner.running_tasks
        self.rose_dirs = runner.rose_dirs
    
    # =============================================================================
    # Core Command Handlers
    # =============================================================================
    

    def handle_run(self, operation: str):
        """Handle background task execution"""
        if not operation:
            self._show_run_help()
            return
        
        # Parse operation
        parts = operation.split()
        if not parts:
            self.console.print("[red]No operation specified[/red]")
            return
        
        op_type = parts[0]
        
        if op_type == "load":
            self._run_load_operation(parts[1:])
        elif op_type == "extract":
            self._run_extract_operation(parts[1:])
        elif op_type == "inspect":
            self._run_inspect_operation(parts[1:])
        elif op_type == "compress":
            self._run_compress_operation(parts[1:])
        elif op_type == "data":
            self._run_data_operation(parts[1:])
        elif op_type == "cache":
            self._run_cache_operation(parts[1:])
        elif op_type == "plugin":
            self._run_plugin_operation(parts[1:])
        else:
            self.ui.msg.error(f"Unknown operation: {op_type}")
            self._show_run_help()
    
    
    def handle_configuration(self, args: str):
        """Handle configuration management - open config file in editor"""
        self._open_rose_config()
    
    
    def handle_help(self, args: str):
        """Show detailed help"""
        self._show_detailed_help()
    
    def handle_clear(self, args: str):
        """Clear console"""
        self.console.clear()
        self.runner._show_welcome()
    
    
    
    
    def handle_exit(self, args: str):
        """Handle exit command"""
        if self.running_tasks:
            self.console.print(f"[yellow]Warning: {len(self.running_tasks)} tasks still running[/yellow]")
            if not confirm("Exit anyway?"):
                return
        
        self.console.print("[cyan]Goodbye![/cyan]")
        raise typer.Exit(0)
    
    # =============================================================================
    # Operation Handlers
    # =============================================================================
    
    def _run_load_operation(self, args: List[str]):
        """Handle load operation in background"""
        if not args:
            # Interactive file selection
            bag_path = self._select_bag_file()
            if not bag_path:
                return
        else:
            bag_path = args[0]
        
        if not Path(bag_path).exists():
            self.console.print(f"[red]Bag file not found: {bag_path}[/red]")
            return
        
        task_id = f"load_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'load',
            {'bag_path': bag_path, 'build_index': True},
            self.runner._on_load_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started loading {Path(bag_path).name} in background (task: {task_id})[/cyan]")
    
    def _run_extract_operation(self, args: List[str]):
        """Handle extract operation in background"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Interactive parameter collection
        topics = self._select_topics_for_operation("extract")
        if not topics:
            return
        
        output_path = inquirer.text(
            message="Output file pattern:",
            default="{input}_extracted_{timestamp}.bag"
        ).execute()
        
        if not output_path:
            return
        
        task_id = f"extract_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'extract',
            {
                'bags': self.state.current_bags.copy(),
                'topics': topics,
                'output_pattern': output_path
            },
            self.runner._on_extract_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started extracting {len(topics)} topics from {len(self.state.current_bags)} bags (task: {task_id})[/cyan]")
    
    def _run_inspect_operation(self, args: List[str]):
        """Handle inspect operation"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Select bag to inspect
        if len(self.state.current_bags) == 1:
            bag_path = self.state.current_bags[0]
        else:
            choices = [Choice(value=bag, name=Path(bag).name) for bag in self.state.current_bags]
            bag_path = inquirer.select(
                message="Select bag to inspect:",
                choices=choices
            ).execute()
            
            if not bag_path:
                return
        
        task_id = f"inspect_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'inspect',
            {'bag_path': bag_path, 'verbose': True},
            self.runner._on_inspect_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started inspecting {Path(bag_path).name} (task: {task_id})[/cyan]")
    
    def _run_compress_operation(self, args: List[str]):
        """Handle compress operation in background"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Select compression type
        compression = inquirer.select(
            message="Select compression type:",
            choices=[
                Choice(value="lz4", name="LZ4 (fast, good compression)"),
                Choice(value="bz2", name="BZ2 (slower, better compression)")
            ]
        ).execute()
        
        if not compression:
            return
        
        task_id = f"compress_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'compress',
            {
                'bags': self.state.current_bags.copy(),
                'compression': compression,
                'output_pattern': "{input}_{compression}_{timestamp}.bag"
            },
            self.runner._on_compress_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started compressing {len(self.state.current_bags)} bags with {compression} (task: {task_id})[/cyan]")
    
    def _run_data_operation(self, args: List[str]):
        """Handle data export operation"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Interactive data export configuration
        topics = self._select_topics_for_operation("export")
        if not topics:
            return
        
        output_path = inquirer.text(
            message="Output CSV file:",
            default="bag_data_{timestamp}.csv"
        ).execute()
        
        if not output_path:
            return
        
        task_id = f"data_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'data',
            {
                'bags': self.state.current_bags.copy(),
                'topics': topics,
                'output_path': output_path
            },
            self.runner._on_data_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started exporting data for {len(topics)} topics (task: {task_id})[/cyan]")
    
    def _run_cache_operation(self, args: List[str]):
        """Handle cache operation"""
        if not args:
            self._show_cache_menu()
        else:
            subcommand = args[0]
            if subcommand == "clear":
                self._cache_clear()
            elif subcommand == "info":
                self._cache_info()
            elif subcommand == "list":
                self._cache_list()
            else:
                self._show_cache_menu()
    
    def _run_plugin_operation(self, args: List[str]):
        """Handle plugin operation"""
        if not args:
            self._show_plugin_menu()
        else:
            subcommand = args[0]
            if subcommand == "list":
                self._plugin_list()
            elif subcommand == "info":
                self._plugin_info(args[1:])
            elif subcommand == "run":
                self._plugin_run(args[1:])
            else:
                self._show_plugin_menu()
    
    def _show_cache_menu(self):
        """Show cache management menu"""
        choices = [
            Choice(value='info', name='ℹ️  Info - Show cache information'),
            Choice(value='list', name='📋 List - List cached bags'),
            Choice(value='clear', name='🗑️  Clear - Clear cache')
        ]
        
        selected = inquirer.select(
            message="Select cache operation:",
            choices=choices
        ).execute()
        
        if selected:
            getattr(self, f'_cache_{selected}')()
    
    def _show_plugin_menu(self):
        """Show plugin management menu"""
        choices = [
            Choice(value='list', name='📋 List - List available plugins'),
            Choice(value='info', name='ℹ️  Info - Show plugin information'),
            Choice(value='run', name='▶️  Run - Execute a plugin')
        ]
        
        selected = inquirer.select(
            message="Select plugin operation:",
            choices=choices
        ).execute()
        
        if selected == 'list':
            self._plugin_list()
        elif selected == 'info':
            self._plugin_info([])
        elif selected == 'run':
            self._plugin_run([])
    
    def _cache_clear(self):
        """Clear cache interactively"""
        try:
            from roseApp.cli.cache import clear as cache_clear_cmd
            
            if inquirer.confirm("Clear all cache data?", default=False).execute():
                cache_clear_cmd(yes=True)
                self.ui.msg.success("Cache cleared")
            else:
                self.ui.msg.warning("Operation cancelled")
        except Exception as e:
            self.ui.msg.error(f"Cache clear error: {e}")
    
    def _cache_info(self):
        """Show cache info"""
        try:
            from roseApp.cli.cache import info as cache_info_cmd
            cache_info_cmd()
        except Exception as e:
            self.ui.msg.error(f"Cache info error: {e}")
    
    def _cache_list(self):
        """List cached bags"""
        try:
            from roseApp.cli.cache import list_cache as cache_list_cmd
            cache_list_cmd()
        except Exception as e:
            self.ui.msg.error(f"Cache list error: {e}")
    
    def _plugin_list(self):
        """List available plugins"""
        try:
            from roseApp.cli.plugin import list_plugins as plugin_list_cmd
            plugin_list_cmd()
        except Exception as e:
            self.ui.msg.error(f"Plugin list error: {e}")
    
    def _plugin_info(self, args: List[str]):
        """Show plugin info"""
        try:
            from roseApp.cli.plugin import info as plugin_info_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name for info:"
                ).execute()
                if not plugin_name:
                    self.ui.msg.warning("No plugin specified")
                    return
                args = [plugin_name]
            
            plugin_info_cmd(plugin_name=args[0])
        except Exception as e:
            self.ui.msg.error(f"Plugin info error: {e}")
    
    def _plugin_run(self, args: List[str]):
        """Run plugin interactively"""
        try:
            from roseApp.cli.plugin import run as plugin_run_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name to run:"
                ).execute()
                if not plugin_name:
                    self.ui.msg.warning("No plugin specified")
                    return
                args = [plugin_name]
            
            # For simplicity, run with current bags if available
            bag_files = self.state.current_bags if self.state.current_bags else []
            
            plugin_run_cmd(
                plugin_name=args[0],
                input=bag_files,
                verbose=False
            )
        except Exception as e:
            self.ui.msg.error(f"Plugin run error: {e}")
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def _analyze_query_and_suggest(self, query: str) -> List[Dict[str, str]]:
        """Analyze user query and suggest relevant commands"""
        query_lower = query.lower()
        suggestions = []
        
        # Bag file operations
        if any(word in query_lower for word in ['load', 'open', 'bag', 'file']):
            suggestions.append({
                'description': 'Load a bag file into workspace',
                'command': '/run load',
                'example': '/run load data.bag'
            })
        
        if any(word in query_lower for word in ['extract', 'filter', 'topic']):
            suggestions.append({
                'description': 'Extract specific topics from bags',
                'command': '/run extract',
                'example': 'Will prompt for topics and output settings'
            })
        
        if any(word in query_lower for word in ['inspect', 'analyze', 'info', 'statistics']):
            suggestions.append({
                'description': 'Inspect bag file contents and statistics',
                'command': '/run inspect',
                'example': 'Shows detailed bag analysis'
            })
        
        if any(word in query_lower for word in ['compress', 'shrink', 'reduce']):
            suggestions.append({
                'description': 'Compress bag files to reduce size',
                'command': '/run compress',
                'example': 'Will prompt for compression type'
            })
        
        if any(word in query_lower for word in ['export', 'csv', 'data']):
            suggestions.append({
                'description': 'Export bag data to CSV format',
                'command': '/run data',
                'example': 'Will prompt for topics and export settings'
            })
        
        
        if any(word in query_lower for word in ['note', 'remember', 'write']):
            suggestions.append({
                'description': 'Add a note to current session',
                'command': '/note',
                'example': '/note Remember to check GPS data quality'
            })
        
        # If no specific suggestions, provide general help
        if not suggestions:
            suggestions.append({
                'description': 'Show all available commands',
                'command': '/help',
                'example': 'Lists all slash commands and their usage'
            })
        
        return suggestions[:3]  # Limit to top 3 suggestions
    
    def _get_file_size_str(self, file_path: str) -> str:
        """Get human-readable file size string"""
        try:
            size = Path(file_path).stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f}{unit}"
                size /= 1024
            return f"{size:.1f}TB"
        except Exception:
            return "Unknown"
    
    def _get_cache_size_info(self) -> str:
        """Get cache directory size information"""
        try:
            total_size = 0
            cache_path = Path(self.rose_dirs.cache_dir)
            if cache_path.exists():
                for file_path in cache_path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            
            # Convert to human readable
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024:
                    return f"{total_size:.1f}{unit}"
                total_size /= 1024
            return f"{total_size:.1f}TB"
        except Exception:
            return "Unknown"
    
    def _count_cached_bags(self) -> int:
        """Count number of cached bag analyses"""
        try:
            cache_path = Path(self.rose_dirs.cache_dir)
            if cache_path.exists():
                # Count .json files in cache directory (assuming each represents a cached bag analysis)
                return len(list(cache_path.rglob('*.json')))
            return 0
        except Exception:
            return 0
    
    def _show_run_help(self):
        """Show help for /run command with actual CLI command support"""
        help_text = """[bold]Available /run operations:[/bold]

[cyan]/run load [patterns][/cyan]      - Load bag files (supports glob: *.bag, regex patterns)
[cyan]/run extract[/cyan]              - Extract specific topics from bags (interactive selection)
[cyan]/run inspect topics[/cyan]       - Show topic information and statistics
[cyan]/run inspect info[/cyan]         - Show comprehensive bag file information  
[cyan]/run inspect timeline[/cyan]     - Show message timeline and frequency
[cyan]/run compress[/cyan]             - Compress bags with bz2/lz4 (interactive options)
[cyan]/run data export[/cyan]          - Export topic data to CSV/JSON
[cyan]/run data convert[/cyan]         - Convert between data formats
[cyan]/run cache clear[/cyan]          - Clear analysis cache
[cyan]/run cache info[/cyan]           - Show cache statistics
[cyan]/run cache list[/cyan]           - List cached bag files
[cyan]/run plugin list[/cyan]          - List available plugins
[cyan]/run plugin info <name>[/cyan]   - Show plugin information
[cyan]/run plugin run <name>[/cyan]    - Execute plugin on loaded bags

[bold]Examples:[/bold]
  /run load *.bag                      # Load all bags in directory
  /run extract                         # Interactive topic extraction
  /run inspect topics                  # Show topic details
  /run data export                     # Export to CSV with interactive options

All operations use interactive prompts for parameter collection.
"""
        self.console.print(Markdown(help_text))
    
    def _show_detailed_help(self):
        """Show comprehensive help from Markdown file with Textual paging"""
        try:
            # Get the help file path
            help_file = Path(__file__).parent / "help.md"
            
            if help_file.exists():
                # Read the Markdown content
                with open(help_file, 'r', encoding='utf-8') as f:
                    help_content = f.read()
                
                # Display with Textual Markdown rendering and paging
                self._display_markdown_with_textual(help_content)
            else:
                # Fallback if help file doesn't exist
                self.console.print("[red]Help file not found. Using basic help.[/red]")
                self._show_basic_help()
                
        except Exception as e:
            logger.warning(f"Could not load help file: {e}")
            self.console.print(f"[yellow]Could not load help file: {e}[/yellow]")
            self._show_basic_help()
    
    def _display_markdown_with_textual(self, markdown_content: str):
        """Display markdown content using Textual with paging support"""
        try:
            # Try to use Textual for better markdown rendering and paging
            import asyncio
            from textual.app import App
            from textual.widgets import Markdown as TextualMarkdown, Footer
            from textual.containers import Vertical, Horizontal
            from textual.binding import Binding
            from textual import on
            
            # Ensure we have an event loop for Textual
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop exists, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            class MarkdownViewer(App):
                """A Textual app for viewing Markdown with paging support"""
                
                CSS = """
                MarkdownViewer {
                    background: $background;
                }
                
                #markdown {
                    scrollbar-background: $primary-background;
                    scrollbar-color: $accent;
                    scrollbar-corner-color: $primary-background;
                    scrollbar-size: 2 1;
                    padding: 1 2;
                    height: 100%;
                    overflow-y: auto;
                    overflow-x: auto;
                }
                
                Footer {
                    background: $primary;
                    color: $text;
                }
                """
                
                BINDINGS = [
                    Binding("q", "quit", "Quit", priority=True),
                    Binding("escape", "quit", "Quit", priority=True),
                    # Vim-style navigation
                    Binding("j", "scroll_down", "Scroll Down", show=False),
                    Binding("k", "scroll_up", "Scroll Up", show=False),
                    Binding("h", "scroll_left", "Scroll Left", show=False),
                    Binding("l", "scroll_right", "Scroll Right", show=False),
                    # Arrow keys
                    Binding("down", "scroll_down", "Scroll Down", show=False),
                    Binding("up", "scroll_up", "Scroll Up", show=False),
                    Binding("left", "scroll_left", "Scroll Left", show=False),
                    Binding("right", "scroll_right", "Scroll Right", show=False),
                    # Page navigation
                    Binding("d", "page_down", "Page Down"),
                    Binding("u", "page_up", "Page Up"),
                    Binding("pagedown", "page_down", "Page Down", show=False),
                    Binding("pageup", "page_up", "Page Up", show=False),
                    Binding("space", "page_down", "Page Down", show=False),
                    Binding("b", "page_up", "Page Up", show=False),
                    # Home/End navigation
                    Binding("g", "scroll_home", "Go to Top", show=False),
                    Binding("G", "scroll_end", "Go to Bottom", show=False),
                    Binding("home", "scroll_home", "Go to Top", show=False),
                    Binding("end", "scroll_end", "Go to Bottom", show=False),
                ]
                
                def __init__(self, markdown_content: str):
                    super().__init__()
                    self.markdown_content = markdown_content
                    self.title = "🌹 Rose Help - Interactive Documentation"
                    self.sub_title = "Navigate: ↑↓=scroll, PgUp/PgDn=page, Home/End=top/bottom, q=quit"
                
                def compose(self):
                    """Create child widgets for the app."""
                    with Vertical():
                        yield TextualMarkdown(self.markdown_content, id="markdown")
                        yield Footer()
                
                def action_scroll_down(self):
                    """Scroll down one line."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_down(animate=True)
                
                def action_scroll_up(self):
                    """Scroll up one line."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_up(animate=True)
                
                def action_scroll_left(self):
                    """Scroll left."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_left(animate=True)
                
                def action_scroll_right(self):
                    """Scroll right."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_right(animate=True)
                
                def action_page_down(self):
                    """Scroll down one page."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_page_down(animate=True)
                
                def action_page_up(self):
                    """Scroll up one page."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_page_up(animate=True)
                
                def action_scroll_home(self):
                    """Scroll to the top."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_home(animate=True)
                
                def action_scroll_end(self):
                    """Scroll to the bottom."""
                    markdown_widget = self.query_one("#markdown")
                    markdown_widget.scroll_end(animate=True)
            
            # Create and run the Textual app
            app = MarkdownViewer(markdown_content)
            
            # Run the app synchronously
            try:
                app.run()
            except KeyboardInterrupt:
                pass  # User pressed Ctrl+C, exit gracefully
                
        except ImportError:
            logger.debug("Textual not available, falling back to Rich")
            self._display_markdown_with_rich_pager(markdown_content)
        except Exception as e:
            logger.warning(f"Textual markdown viewer failed: {e}")
            self._display_markdown_with_rich_pager(markdown_content)
    
    def _display_markdown_with_rich_pager(self, markdown_content: str):
        """Fallback: Display markdown with Rich and simple paging"""
        try:
            # Check if content is long enough to need paging
            lines = markdown_content.split('\n')
            terminal_height = getattr(self.console.size, 'height', 25)
            
            if len(lines) <= terminal_height - 5:
                # Content fits on screen, display directly
                self.console.print(Markdown(markdown_content))
            else:
                # Use Rich's built-in pager if available
                try:
                    with self.console.pager(styles=True):
                        self.console.print(Markdown(markdown_content))
                except Exception:
                    # Final fallback: direct display with scroll hint
                    self.console.print(Markdown(markdown_content))
                    self.console.print("\n[dim]Tip: Use your terminal's scroll functionality to navigate[/dim]")
                    
        except Exception as e:
            logger.warning(f"Rich pager failed: {e}")
            # Ultimate fallback
            self.console.print(Markdown(markdown_content))
    
    def _show_basic_help(self):
        """Show basic help as fallback"""
        basic_help = Text()
        basic_help.append("Rose Interactive Environment - Basic Help\n\n", style="bold cyan")
        basic_help.append("Core Commands:\n", style="bold")
        
        # Show available commands dynamically
        for cmd in sorted(self.runner.commands.keys()):
            if cmd in ['/help', '/exit', '/clear']:
                basic_help.append(f"  {cmd}\n", style=get_color('muted'))
        
        basic_help.append("\nFor comprehensive help, ensure help.md file is available.\n", style="yellow")
        basic_help.append("Try: '/help' to see all commands or ask questions directly.", style="green")
        
        panel = Panel(basic_help, title="Basic Help", border_style=get_color('primary'))
        self.console.print(panel)
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def _select_bag_file(self) -> Optional[str]:
        """Interactive bag file selection"""
        # Look for bag files in current directory
        current_dir = Path('.')
        bag_files = list(current_dir.glob('*.bag'))
        
        if not bag_files:
            # Ask user for file path
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag')
            ).execute()
            return bag_path
        
        # Show available files
        choices = [Choice(value=str(bag), name=f"{bag.name} ({bag.stat().st_size // (1024*1024)} MB)") 
                  for bag in bag_files]
        choices.append(Choice(value="browse", name="Browse for other file..."))
        
        selected = inquirer.select(
            message="Select bag file:",
            choices=choices
        ).execute()
        
        if selected == "browse":
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag')
            ).execute()
            return bag_path
        
        return selected
    
    def _select_topics_for_operation(self, operation: str) -> Optional[List[str]]:
        """Interactive topic selection for operations"""
        if not self.state.current_bags:
            return None
        
        # Get all available topics from loaded bags
        all_topics = set()
        for bag_path in self.state.current_bags:
            if bag_path in self.state.loaded_bags:
                bag_info = self.state.loaded_bags[bag_path]
                bag_topics = bag_info.get('topics', [])
                all_topics.update(bag_topics)
        
        if not all_topics:
            self.ui.msg.warning("No topics available. Load bags first.")
            return None
        
        topics_list = sorted(list(all_topics))
        
        # Use fuzzy selector
        from roseApp.util import ask_topics_with_fuzzy
        
        selected_topics = ask_topics_with_fuzzy(
            console=self.console,
            topics=topics_list,
            message=f"Select topics for {operation}:",
            require_selection=True,
            show_instructions=True
        )
        
        if selected_topics:
            self.state.selected_topics = selected_topics
        
        return selected_topics
    
    
    
    
    # =============================================================================
    # Configuration Management Functions
    # =============================================================================
    
    def _open_rose_config(self):
        """Open Rose configuration file in default editor"""
        import subprocess
        import shutil
        from pathlib import Path
        
        # Look for existing config files  
        config_files = [
            Path("rose.config.yaml"),  # New unified config file
        ]
        
        # Use the first existing config file
        config_file = None
        for cf in config_files:
            if cf.exists():
                config_file = cf
                break
        
        # If no config file exists, create default config
        if config_file is None:
            config_file = Path("rose.config.yaml")
            self._create_default_config(config_file)
        
        # Try to find a suitable editor
        editors = ['nano', 'vim', 'vi', 'code', 'notepad']
        editor = None
        
        for ed in editors:
            if shutil.which(ed):
                editor = ed
                break
        
        if not editor:
            self.ui.msg.error("No suitable editor found. Please install nano, vim, or code")
            self.ui.msg.warning(f"Configuration file location: {config_file}")
            return
        
        try:
            self.ui.msg.info(f"Opening Rose configuration with {editor}...")
            subprocess.run([editor, str(config_file)], check=True)
            self.ui.msg.completion_message("Configuration file edited")
        except subprocess.CalledProcessError:
            self.ui.msg.error("Failed to open editor")
        except KeyboardInterrupt:
            self.ui.msg.warning("Editor cancelled")
    
    def _create_default_config(self, config_file: Path):
        """Create default configuration file"""
        import yaml
        
        # Copy from example if available, otherwise create basic config
        example_path = Path("rose.config.yaml.example")
        
        if example_path.exists():
            # Copy from example
            import shutil
            shutil.copy2(example_path, config_file)
            self.ui.msg.info(f"Created configuration file from example: {config_file}")
        else:
            # Create basic configuration using YAML format
            default_config_content = """# Rose Configuration File
# Basic configuration for Rose ROS Bag Processing Tool

# Performance settings
parallel_workers: 4
cache_ttl_seconds: 300
memory_limit_mb: 512

# Default behaviors
verbose_default: false
build_index_default: false
auto_cache_default: true
compression_default: none

# File settings
output_directory: "output"

# Feature flags
enable_plugins: true

# Logging
log_level: "INFO"
log_to_file: true

# UI settings
theme_file: "rose.theme.default.yaml"
enable_colors: true
"""
            
            try:
                with open(config_file, 'w') as f:
                    f.write(default_config_content)
                self.ui.msg.completion_message(f"Created default configuration: {config_file}")
            except Exception as e:
                self.ui.msg.warning(f"Could not create config file: {e}")

    # =============================================================================
    # Export Functions
    # =============================================================================
    
