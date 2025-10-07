#!/usr/bin/env python3
"""
Compress Command - Delegates to: rose compress
"""

from typing import List, Dict, Any
from .base_command import BaseCommand


class CompressCommand(BaseCommand):
    """Delegates to: rose compress"""
    
    def get_command_name(self) -> str:
        return "compress"
    
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
            logger = get_logger("compress_command")
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
        Prompt user for bag files and execute compress command with default config support
        
        Returns:
            Execution result dictionary
        """
        try:
            from rich.console import Console
            from InquirerPy import inquirer
            from InquirerPy.base.control import Choice
            from ..components import InputPrompter, create_config_prompter
            from ...ui.common_ui import Message
            
            console = Console()
            prompter = InputPrompter(console)
            config_prompter = create_config_prompter(console)
            
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
            
            # Ask if user wants to use default configuration
            use_defaults = config_prompter.prompt_use_defaults('compress')
            
            args = [str(p) for p in bag_paths]
            
            if not use_defaults:
                # Prompt for each parameter
                compression = inquirer.select(
                    message="Select compression type:",
                    choices=[
                        Choice("lz4", "LZ4 compression (fast, good ratio)"),
                        Choice("bz2", "BZ2 compression (slower, best ratio)")
                    ],
                    default="lz4"
                ).execute()
                
                output_pattern = inquirer.text(
                    message="Output file pattern:",
                    default="{input}_{compression}_{timestamp}.bag"
                ).execute()
                
                # Add flags based on user choices
                args.extend(['--compression', compression])
                if output_pattern:
                    args.extend(['--output', output_pattern])
            else:
                # Use defaults from configuration
                defaults = config_prompter.get_command_defaults('compress')
                compression = defaults.get('compression', 'lz4')
                args.extend(['--compression', compression])
                output_pattern = defaults.get('output_pattern')
                if output_pattern:
                    args.extend(['--output', output_pattern])
            
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
            logger = get_logger("compress_command")
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
        Parse compress command arguments
        
        Examples:
            /compress @input --compression lz4 → rose compress /path/to/input.bag --compression lz4
            /compress data.bag -c bz2 → rose compress data.bag -c bz2
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Compress bag files

Usage: /compress <bag_file> [options]

Examples:
  /compress data.bag                           Compress with default settings
  /compress @input --compression lz4          Compress cached bag with LZ4
  /compress data.bag -c bz2                   Compress with BZ2
  /compress data.bag --output compressed.bag  Specify output file
  /compress --help                            Show detailed compress command help

The compress command supports:
- LZ4 compression (fast, good ratio)
- BZ2 compression (slower, best ratio)
- Custom output file specification
- @ references for input files
- All standard rose compress options"""
