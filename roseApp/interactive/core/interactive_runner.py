#!/usr/bin/env python3
"""
Interactive Runner - Main runner (lightweight)
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter

from .command_router import CommandRouter
from ..components import CLIExecutor, PathCompleter, ResultFormatter
from ..commands.load_command import LoadCommand
from ..commands.extract_command import ExtractCommand
from ..commands.inspect_command import InspectCommand
from ..commands.compress_command import CompressCommand
from ..commands.data_command import DataCommand
from ..commands.cache_command import CacheCommand
from ..commands.plugin_command import PluginCommand
from ..commands.status_command import StatusCommand
from ..commands.bags_command import BagsCommand
from ..commands.topics_command import TopicsCommand
from ..commands.configuration_command import ConfigurationCommand
from ..commands.help_command import HelpCommand
from ..commands.clear_command import ClearCommand
from ..commands.exit_command import ExitCommand
from ...core.directories import get_rose_directories
from ...core.util import get_logger
from roseApp.cli.util import build_banner

logger = get_logger("interactive_runner")


@dataclass
class SessionState:
    """Current session state including workspace and loaded data"""
    workspace_path: str
    current_bags: list
    loaded_bags: Dict[str, Dict[str, Any]]
    selected_topics: list
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InteractiveRunner:
    """Main runner - only responsible for routing and display"""
    
    def __init__(self):
        self.console = Console()
        self.rose_dirs = get_rose_directories()
        
        # Session state
        self.state = SessionState(
            workspace_path=os.getcwd(),
            current_bags=[],
            loaded_bags={},
            selected_topics=[],
            created_at=time.time()
        )
        
        # Core components
        self.cli_executor = CLIExecutor()
        self.path_completer = PathCompleter()
        self.result_formatter = ResultFormatter(self.console)
        
        # Command router and registry
        self.router = CommandRouter()
        self._setup_commands()
        
        # Setup prompt session
        self._setup_prompt_session()
    
    def _setup_commands(self):
        """Setup command registry mapping"""
        # CLI delegated commands
        self.router.register_command('/load', LoadCommand(self.cli_executor))
        self.router.register_command('/extract', ExtractCommand(self.cli_executor))
        self.router.register_command('/inspect', InspectCommand(self.cli_executor))
        self.router.register_command('/compress', CompressCommand(self.cli_executor))
        self.router.register_command('/data', DataCommand(self.cli_executor))
        self.router.register_command('/cache', CacheCommand(self.cli_executor))
        self.router.register_command('/plugin', PluginCommand(self.cli_executor))
        
        # Internal commands
        self.router.register_command('/status', StatusCommand(self.cli_executor, self.state))
        self.router.register_command('/bags', BagsCommand(self.cli_executor, self.state))
        self.router.register_command('/topics', TopicsCommand(self.cli_executor, self.state))
        self.router.register_command('/configuration', ConfigurationCommand(self.cli_executor))
        
        # Get command registry for help command
        command_registry = self.router.get_available_commands()
        self.router.register_command('/help', HelpCommand(self.cli_executor, command_registry))
        
        self.router.register_command('/clear', ClearCommand(self.cli_executor))
        self.router.register_command('/exit', ExitCommand(self.cli_executor))
        self.router.register_command('/quit', ExitCommand(self.cli_executor))  # Alias
    
    def _setup_prompt_session(self):
        """Setup intelligent prompt session with history and completion"""
        try:
            history_file = self.rose_dirs.get_config_file('run_history.txt')
            
            # Create simple completer
            command_list = list(self.router.get_available_commands().keys())
            completer = WordCompleter(command_list, ignore_case=True)
            
            # Create session with safe configuration
            session_kwargs = {
                'multiline': False,
                'complete_style': 'column',
                'completer': completer
            }
            
            # Add optional features safely
            try:
                session_kwargs['history'] = FileHistory(str(history_file))
                session_kwargs['auto_suggest'] = AutoSuggestFromHistory()
            except Exception as e:
                logger.warning(f"Could not setup advanced prompt features: {e}")
            
            self.session = PromptSession(**session_kwargs)
            logger.debug("Prompt session initialized")
        except Exception as e:
            logger.warning(f"Could not setup prompt session: {e}")
            # Fallback to basic prompt
            self.session = None
    
    def run_interactive(self):
        """Main interactive loop - routes commands and displays results"""
        try:
            self._show_welcome()
            
            while True:
                try:
                    # Show prompt with current context
                    prompt_text = self._get_prompt_text()
                    
                    # Get user input with fallback
                    try:
                        if self.session:
                            user_input = self.session.prompt(prompt_text).strip()
                        else:
                            user_input = input(prompt_text).strip()
                    except Exception as e:
                        logger.warning(f"Prompt error, using basic input: {e}")
                        user_input = input(prompt_text).strip()
                    
                    if not user_input:
                        continue
                    
                    # Dispatch command
                    self._dispatch_command(user_input)
                    
                except KeyboardInterrupt:
                    self.result_formatter.format_warning("Use /exit to quit")
                    continue
                except EOFError:
                    self.result_formatter.format_info("Goodbye!")
                    break
        
        except Exception as e:
            self.result_formatter.format_error("", f"Unexpected error: {e}")
            logger.error(f"Interactive runner error: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _show_welcome(self):
        """Show welcome message and interface overview"""
        # Display the beautiful ROSE banner first
        self.console.print(build_banner())
        
        # Define command descriptions
        command_descriptions = {
            # Core bag operations
            "/load": "Load bag files (supports glob patterns, Tab completion)",
            "/extract": "Extract topics from bags (interactive selection)", 
            "/inspect": "Inspect bag contents and statistics",
            "/compress": "Compress bag files (bz2/lz4 options)",
            
            # Data operations
            "/data": "Data operations with CSV/JSON export",
            "/cache": "Cache management operations",
            "/plugin": "Plugin system operations",
            
            # Session management
            "/status": "Show workspace status and running tasks",
            "/bags": "Manage loaded bags",
            "/topics": "Manage topic selection",
            "/configuration": "Open Rose configuration file in editor",
            
            # System operations
            "/clear": "Clear console",
            "/help": "Show comprehensive help",
            "/exit": "Exit interactive mode",
        }
        
        # Features list
        features = [
            "Tab completion for commands and file paths",
            "@ symbol for cached bags (@test.bag)",
            "! symbol for shell commands (!ls -la)",
            "Background task execution"
        ]
        
        # Show welcome with command descriptions
        self._show_welcome_display("Interactive Environment", command_descriptions, features)
        self.result_formatter.format_muted("Try: '/help' for detailed documentation")
    
    def _show_welcome_display(self, title: str, commands: Dict[str, str], features: list):
        """Display welcome information"""
        self.result_formatter.format_section_header(f"Rose {title}")
        
        # Show commands by category
        categories = {
            "Core Operations": ["/load", "/extract", "/inspect", "/compress"],
            "Data Operations": ["/data", "/cache", "/plugin"],
            "Session Management": ["/status", "/bags", "/topics", "/configuration"],
            "System Operations": ["/clear", "/help", "/exit"]
        }
        
        for category, cmd_list in categories.items():
            self.console.print(f"\n[bold cyan]{category}:[/bold cyan]")
            for cmd in cmd_list:
                if cmd in commands:
                    self.result_formatter.format_command_help(cmd, commands[cmd])
        
        # Show features
        if features:
            self.result_formatter.format_section_header("Features")
            for feature in features:
                self.console.print(f"  • {feature}")
    
    def _get_prompt_text(self) -> str:
        """Generate context-aware prompt"""
        # Build context indicators
        indicators = []
        
        if self.state.current_bags:
            indicators.append(f"{len(self.state.current_bags)} bags")
        
        if self.state.selected_topics:
            indicators.append(f"{len(self.state.selected_topics)} topics")
        
        context = f"[{', '.join(indicators)}]" if indicators else ""
        
        return f"rose{context}> "
    
    def _dispatch_command(self, user_input: str):
        """Dispatch user input to appropriate handler"""
        # Handle native shell commands with ! prefix
        if user_input.startswith('!'):
            self._handle_shell_command(user_input[1:].strip())
            return
        
        # Resolve @ symbols to full paths before processing commands
        resolved_input = self.path_completer.resolve_at_references(user_input)
        
        # Route command through router
        command_instance = self.router.route_command(resolved_input)
        
        if command_instance:
            # Extract command arguments
            command_prefix = None
            for cmd_prefix in self.router.get_available_commands().keys():
                if resolved_input.startswith(cmd_prefix):
                    command_prefix = cmd_prefix
                    break
            
            if command_prefix:
                args = self.router.get_command_args(resolved_input, command_prefix)
                try:
                    # Execute command
                    result = command_instance.execute(args)
                    self._show_command_result(command_prefix, result)
                except EOFError:
                    # Exit command raises EOFError to exit the loop - this is expected
                    raise
                except Exception as e:
                    self.result_formatter.format_error("", f"Command error: {e}")
                    logger.error(f"Command {command_prefix} error: {e}", exc_info=True)
        else:
            # Handle non-slash commands with helpful message
            if not resolved_input.startswith('/'):
                self._handle_non_slash_input(resolved_input)
            else:
                self.result_formatter.format_warning(f"Unknown command: {resolved_input}")
                self.result_formatter.format_info("Use '/help' to see available commands")
    
    def _show_command_result(self, command: str, result: Dict[str, Any]):
        """Display command execution result"""
        success = result.get('success', False)
        
        if success:
            if result.get('stdout'):
                self.console.print(result['stdout'])
            elif result.get('message'):
                self.result_formatter.format_success(result['message'])
        else:
            error_msg = result.get('error', 'Unknown error')
            self.result_formatter.format_error(result.get('stderr', ''), error_msg)
    
    def _handle_non_slash_input(self, user_input: str):
        """Handle non-slash input with helpful guidance"""
        self.result_formatter.format_warning(f"'{user_input}' is not recognized as a command.")
        self.result_formatter.format_info("Rose Interactive Environment only supports commands starting with '/'")
        
        # Show some basic commands
        self.console.print("\n[bold]Try these commands:[/bold]")
        self.result_formatter.format_command_help("/help", "Show all available commands")
        self.result_formatter.format_command_help("/load", "Load bag files")
        self.result_formatter.format_command_help("/status", "Check system status")
    
    def _handle_shell_command(self, command: str):
        """Handle native shell command execution"""
        if not command:
            self.result_formatter.format_warning("Usage: !<command>")
            self.result_formatter.format_muted("Example: !ls -la")
            return
        
        try:
            import subprocess
            
            # Show what command we're executing
            self.console.print(f"[dim]$ {command}[/dim]")
            
            # Execute command in native shell
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=None  # Use current working directory
            )
            
            # Display output
            if result.stdout:
                self.console.print(result.stdout.rstrip())
            
            if result.stderr:
                self.result_formatter.format_error("", result.stderr.rstrip())
            
            # Show exit code if non-zero
            if result.returncode != 0:
                self.result_formatter.format_error("", f"Command exited with code {result.returncode}")
                
        except Exception as e:
            self.result_formatter.format_error("", f"Shell command error: {e}")
            logger.error(f"Shell command error: {e}", exc_info=True)
    
    def _cleanup(self):
        """Cleanup resources"""
        logger.debug("Cleaning up interactive runner")
        # Add any cleanup logic here
