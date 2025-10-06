#!/usr/bin/env python3
"""
Extract Command - Delegates to: rose extract
"""

from typing import List, Dict, Any
from .base_command import BaseCommand


class ExtractCommand(BaseCommand):
    """Delegates to: rose extract"""
    
    def get_command_name(self) -> str:
        return "extract"
    
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
            
            # Otherwise, use interactive execution (don't capture output)
            cli_args = self._parse_args(interactive_args)
            result = self.cli_executor.execute_command_interactive(self.get_command_name(), cli_args)
            return result
            
        except Exception as e:
            from ...core.util import get_logger
            logger = get_logger("extract_command")
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
        Prompt user for bag files and execute extract command
        
        Returns:
            Execution result dictionary
        """
        try:
            from rich.console import Console
            from ..components import InputPrompter
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
            
            # Convert Path objects to strings and execute
            # Extract command needs topics, so just pass the bag files
            # The CLI will prompt for topics
            args = [str(p) for p in bag_paths]
            
            # Use interactive execution to allow real-time output and prompts
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
            logger = get_logger("extract_command")
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
        Parse extract command arguments
        
        Examples:
            /extract @input @output -t /camera/image → rose extract /path/to/input.bag /path/to/output.bag -t /camera/image
            /extract input.bag output.bag --topics /gps → rose extract input.bag output.bag --topics /gps
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Extract topics from bag files

Usage: /extract <input_bags...> [options]

Examples:
  /extract input.bag --topics gps                  Extract specific topics
  /extract @input -t /camera/image                 Extract using @ reference
  /extract *.bag --topics /gps                     Extract from multiple bags
  /extract input.bag --topics /gps --reverse       Exclude GPS topic
  /extract --help                                  Show detailed extract command help

The extract command supports:
- Topic filtering with -t/--topics
- Reverse selection with --reverse
- Time range filtering
- @ references for input files
- All standard rose extract options"""
