#!/usr/bin/env python3
"""
Help Command - Internal help display
"""

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
                self._show_general_help()
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
    
    def _show_general_help(self):
        """Display general help information"""
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
        self.result_formatter.console.print("• Use '/status' to check current workspace state")
    
    def _show_command_categories(self):
        """Display command categories"""
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
                "/status": "Show workspace status and running tasks",
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
            self.result_formatter.console.print(f"\n[bold cyan]{category}:[/bold cyan]")
            for cmd, desc in commands.items():
                self.result_formatter.format_command_help(cmd, desc)
    
    def _show_usage_examples(self):
        """Display usage examples"""
        self.result_formatter.format_section_header("Usage Examples")
        
        examples = [
            ("Load bag files", "/load data.bag", "Load single bag file"),
            ("Use glob patterns", "/load *.bag", "Load all bag files in current directory"),
            ("Use @ references", "/load @test data/*.bag", "Load cached bag @test and all bags in data/"),
            ("Extract topics", "/extract input.bag output.bag -t /camera/image", "Extract specific topic"),
            ("Inspect bag", "/inspect @test --topics", "Show topics in cached bag"),
            ("Run shell command", "!ls -la *.bag", "List bag files using shell"),
            ("Get command help", "/load --help", "Show detailed load command options"),
            ("Check status", "/status", "Show current workspace state")
        ]
        
        for description, command, explanation in examples:
            self.result_formatter.console.print(f"  [green]{command:<35}[/green] {explanation}")
    
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
