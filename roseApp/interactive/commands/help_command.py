#!/usr/bin/env python3
"""
Help Command - Shows help information using TUI
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any
from .base_command import BaseCommand


class HelpCommand(BaseCommand):
    """Internal help command - shows detailed help documentation"""
    
    def __init__(self, cli_executor, command_registry=None):
        super().__init__(cli_executor)
        self.command_registry = command_registry or {}
    
    def get_command_name(self) -> str:
        return "help"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute help command - display help information
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            args = interactive_args.strip().split() if interactive_args.strip() else []
            
            if not args:
                self._show_help_tui()
            else:
                command_name = args[0]
                if command_name.startswith('/'):
                    command_name = command_name[1:]  # Remove leading slash
                self._show_command_help(command_name)
            
            return {
                'success': True,
                'message': 'Help displayed',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Help display failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _show_help_tui(self):
        """Display help.md using Textual TUI viewer"""
        # Get the path to help.md
        help_file = Path(__file__).parent.parent / "help.md"
        
        if not help_file.exists():
            self.result_formatter.format_error("", f"Help file not found: {help_file}")
            return
            
        try:
            # Read the Markdown content
            with open(help_file, 'r', encoding='utf-8') as f:
                help_content = f.read()
            
            # Display with Textual Markdown rendering and paging
            self._display_markdown_with_textual(help_content)
            
        except Exception as e:
            self.result_formatter.format_error("", f"Failed to display help: {e}")
            self._show_help_fallback(help_file)
    
    def _show_help_fallback(self, help_file: Path):
        """Fallback method to display help content directly"""
        try:
            with open(help_file, 'r') as f:
                content = f.read()
            
            # Display content with basic formatting
            from rich.markdown import Markdown
            md = Markdown(content)
            self.result_formatter.console.print(md)
            
        except Exception as e:
            self.result_formatter.format_error("", f"Could not read help file: {e}")
    
    def _display_markdown_with_textual(self, markdown_content: str):
        """Display markdown content using Textual with paging support"""
        try:
            # Try to use Textual for better markdown rendering and paging
            import asyncio
            from textual.app import App
            from textual.widgets import Markdown as TextualMarkdown, Footer
            from textual.containers import Vertical
            from textual.binding import Binding
            
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
                self.result_formatter.format_info("Help documentation displayed")
            except KeyboardInterrupt:
                pass  # User pressed Ctrl+C, exit gracefully
                
        except ImportError:
            from ...core.util import get_logger
            logger = get_logger("help_command")
            logger.debug("Textual not available, falling back to Rich")
            self._show_help_fallback(Path(__file__).parent.parent / "help.md")
        except Exception as e:
            from ...core.util import get_logger
            logger = get_logger("help_command")
            logger.warning(f"Textual markdown viewer failed: {e}")
            self._show_help_fallback(Path(__file__).parent.parent / "help.md")

    def _show_general_help(self):
        """Display general help information (legacy method)"""
        self.result_formatter.format_section_header("Rose Interactive Environment Help")
        
        # Overview
        overview = """Rose Interactive Environment provides a powerful REPL-style interface for ROS bag operations.
All commands start with '/' and support tab completion, @ references, and background execution.

Key Features:
• Tab completion for commands and file paths
• @ symbol for cached bags (@test.bag → /full/path/to/test.bag)
• ! symbol for shell commands (!ls -la)
• Background task execution for long operations
• Session state management with undo/redo support"""
        
        self.result_formatter.console.print(overview)
        
        # Command categories
        self._show_command_categories()
        
        # Usage examples
        self._show_usage_examples()
        
        # Additional help
        self.result_formatter.format_section_header("Getting More Help")
        self.result_formatter.console.print("• Use '/help <command>' for detailed command help")
        self.result_formatter.console.print("• Use '<command> --help' to see CLI options")
        self.result_formatter.console.print("• Use '/bags' or '/topics' to manage your workspace")
    
    def _show_command_categories(self):
        """Display command categories with rich formatting"""
        from ...ui.theme import get_color
        
        self.result_formatter.format_section_header("Available Commands")
        
        categories = {
            "Core Operations": {
                "/load": "Load bag files (supports glob patterns, @ references)",
                "/extract": "Extract topics from bags with filtering",
                "/inspect": "Inspect bag contents and statistics",
                "/compress": "Compress bag files (lz4/bz2 options)"
            },
            "Data Operations": {
                "/data": "Data operations with CSV/JSON export",
                "/cache": "Cache management operations",
                "/plugin": "Plugin system operations"
            },
            "Session Management": {
                "/bags": "Manage loaded bags in workspace",
                "/topics": "Manage topic selection for operations",
                "/configuration": "Open Rose configuration file in editor"
            },
            "System Operations": {
                "/clear": "Clear console screen",
                "/help": "Show this help or command-specific help",
                "/exit": "Exit interactive mode"
            }
        }
        
        for category, commands in categories.items():
            self.result_formatter.console.print(f"\n[bold {get_color('info')}]{category}:[/bold {get_color('info')}]")
            for cmd, desc in commands.items():
                self.result_formatter.format_command_help(cmd, desc)
    
    def _show_usage_examples(self):
        """Display usage examples with rich formatting"""
        from ...ui.theme import get_color
        
        self.result_formatter.format_section_header("Usage Examples")
        
        examples = [
            ("Load bag files", "/load data.bag", "Load single bag file"),
            ("Use glob patterns", "/load *.bag", "Load all bag files in current directory"),
            ("Use @ references", "/load @test data/*.bag", "Load cached bag @test and all bags in data/"),
            ("Extract topics", "/extract input.bag output.bag -t /camera/image", "Extract specific topic"),
            ("Inspect bag", "/inspect @test --topics", "Show topics in cached bag"),
            ("Run shell command", "!ls -la *.bag", "List bag files using shell"),
            ("Get command help", "/load --help", "Show detailed load command options"),
        ]
        
        for description, command, explanation in examples:
            self.result_formatter.console.print(f"  [{get_color('accent')}]{command:<35}[/{get_color('accent')}] {explanation}")
    
    def _show_command_help(self, command_name: str):
        """Display help for specific command"""
        # Try to find command in registry
        command_key = f"/{command_name}"
        
        if command_key in self.command_registry:
            command_instance = self.command_registry[command_key]
            if hasattr(command_instance, 'get_help_text'):
                self.result_formatter.format_section_header(f"Help: {command_key}")
                help_text = command_instance.get_help_text()
                self.result_formatter.console.print(help_text)
            else:
                self.result_formatter.format_warning(f"No detailed help available for {command_key}")
        else:
            self.result_formatter.format_warning(f"Unknown command: {command_name}")
            self.result_formatter.format_info("Use '/help' to see all available commands")
    
    def get_help_text(self) -> str:
        return """Show comprehensive help documentation

Usage: /help [command]

Examples:
  /help                Show general help and command overview
  /help load           Show detailed help for load command
  /help extract        Show detailed help for extract command

The help command provides:
- Overview of Rose Interactive Environment
- List of all available commands with descriptions
- Usage examples and best practices
- Detailed help for specific commands when requested"""
