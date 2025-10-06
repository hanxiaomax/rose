#!/usr/bin/env python3
"""
Inspect Command - Delegates to: rose inspect
"""

from typing import List, Dict, Any
from .base_command import BaseCommand


class InspectCommand(BaseCommand):
    """Delegates to: rose inspect"""
    
    def get_command_name(self) -> str:
        return "inspect"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute command: handle empty args specially for interactive mode
        
        Args:
            interactive_args: Arguments from interactive input
            
        Returns:
            Execution result dictionary
        """
        try:
            # If no arguments provided, prompt user in interactive environment
            if not interactive_args.strip():
                return self._prompt_and_execute()
            
            # Otherwise, use normal execution flow
            return super().execute(interactive_args)
            
        except Exception as e:
            from ...core.util import get_logger
            logger = get_logger("inspect_command")
            logger.error(f"Command execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Command execution failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _prompt_and_execute(self) -> Dict[str, Any]:
        """
        Prompt user for bag files and execute inspect command with default config support
        
        Returns:
            Execution result dictionary
        """
        try:
            from rich.console import Console
            from InquirerPy import inquirer
            from ..components import InputPrompter, create_config_prompter
            from ...ui.common_ui import Message
            
            console = Console()
            prompter = InputPrompter(console)
            config_prompter = create_config_prompter(console)
            
            Message.info("No input bag files specified. Please select bag file:", console)
            bag_paths = prompter.prompt_for_bag_files(
                message="Enter bag file path:",
                allow_multiple=False,
                required=True
            )
            
            if not bag_paths:
                Message.warning("No bag file selected. Operation cancelled.", console)
                return {
                    'success': False,
                    'error': 'No file selected',
                    'stdout': '',
                    'stderr': '',
                    'returncode': 0
                }
            
            # Ask if user wants to use default configuration
            use_defaults = config_prompter.prompt_use_defaults('inspect')
            
            args = [str(bag_paths[0])]
            
            if not use_defaults:
                # Prompt for each parameter
                verbose = inquirer.confirm(
                    message="Enable verbose output with detailed statistics?",
                    default=True
                ).execute()
                
                # Add flags based on user choices
                if verbose:
                    args.append('--verbose')
            else:
                # Use defaults from configuration
                defaults = config_prompter.get_command_defaults('inspect')
                if defaults.get('verbose', True):
                    args.append('--verbose')
            
            # Use interactive execution to allow real-time output
            result = self.cli_executor.execute_command_interactive(self.get_command_name(), args)
            
            return result
            
        except KeyboardInterrupt:
            from rich.console import Console
            console = Console()
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            return {
                'success': False,
                'error': 'Cancelled by user',
                'stdout': '',
                'stderr': '',
                'returncode': 130
            }
        except Exception as e:
            from ...core.util import get_logger
            logger = get_logger("inspect_command")
            logger.error(f"Error in prompt and execute: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Interactive prompt failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse inspect command arguments
        
        Examples:
            /inspect @test → rose inspect /actual/path/to/test.bag
            /inspect data.bag --topics → rose inspect data.bag --topics
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Inspect bag contents and statistics

Usage: /inspect <bag_file> [options]

Examples:
  /inspect data.bag                    Show basic bag information
  /inspect @test --topics              Show topics in cached bag @test
  /inspect data.bag --messages         Show message counts
  /inspect data.bag --duration         Show time range information
  /inspect --help                      Show detailed inspect command help

The inspect command supports:
- Basic bag information (default)
- Topic listing with --topics
- Message statistics with --messages
- Duration and time range with --duration
- @ references for bag files
- All standard rose inspect options"""
