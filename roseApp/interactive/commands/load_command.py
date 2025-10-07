#!/usr/bin/env python3
"""
Load Command - Delegates to: rose load
"""

from typing import List, Dict, Any
from .base_command import BaseCommand


class LoadCommand(BaseCommand):
    """Delegates to: rose load"""
    
    def get_command_name(self) -> str:
        return "load"
    
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
            logger = get_logger("load_command")
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
        Prompt user for bag files and execute load command with interactive parameter selection
        
        Returns:
            Execution result dictionary
        """
        try:
            from rich.console import Console
            from ..components import InputPrompter, ParameterDefinition, create_parameter_selector
            from ...ui.common_ui import Message
            
            console = Console()
            prompter = InputPrompter(console)
            
            Message.info("No input bag files specified. Please select bag files:", console)
            bag_paths = prompter.prompt_for_bag_files(
                message="Enter bag file pattern or path:",
                allow_multiple=True,
                required=True
            )
            
            if not bag_paths:
                Message.warning("No bag files selected. Operation cancelled.", console)
                return {
                    'success': False,
                    'error': 'No files selected',
                    'stdout': '',
                    'stderr': '',
                    'returncode': 0
                }
            
            # Define load command parameters
            parameters = {
                'build_index': ParameterDefinition(
                    name='build_index',
                    display_name='Build Index',
                    param_type='bool',
                    default=False,
                    message="Build DataFrame index for detailed statistics?",
                    help_text="Creates detailed statistics with DataFrame indexing"
                ),
                'verbose': ParameterDefinition(
                    name='verbose',
                    display_name='Verbose Output',
                    param_type='bool',
                    default=False,
                    message="Enable verbose output?",
                    help_text="Shows detailed processing information"
                ),
                'auto_cache': ParameterDefinition(
                    name='auto_cache',
                    display_name='Auto Cache',
                    param_type='bool',
                    default=True,
                    message="Enable automatic caching?",
                    help_text="Automatically cache bag metadata for faster loading"
                )
            }
            
            # Create parameter selector (no bag_info needed for load command)
            param_selector = create_parameter_selector(console, bag_info=None)
            
            # Interactive parameter selection
            selected_params = param_selector.select_parameters('load', parameters)
            
            # Build command arguments
            args = [str(p) for p in bag_paths]
            
            if selected_params.get('build_index', False):
                args.append('--build-index')
            if selected_params.get('verbose', False):
                args.append('--verbose')
            if not selected_params.get('auto_cache', True):
                args.append('--no-cache')
            
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
            logger = get_logger("load_command")
            logger.error(f"Error in prompt and execute: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Failed to prompt for files: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse load command arguments
        
        Examples:
            /load *.bag @test → rose load *.bag /actual/path/to/test.bag
            /load data/test.bag → rose load data/test.bag
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Load bag files into Rose workspace

Usage: /load <bag_files...>

Examples:
  /load data.bag              Load single bag file
  /load *.bag                 Load all bag files in current directory
  /load @test data/*.bag      Load cached bag @test and all bags in data/
  /load --help                Show detailed load command help

The load command supports:
- Glob patterns (*.bag, data/*.bag)
- @ references to cached bags (@test.bag)
- Multiple file arguments
- All standard rose load options"""
