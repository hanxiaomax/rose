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
        Prompt user for bag files and execute extract command with interactive parameter selection
        
        Returns:
            Execution result dictionary
        """
        try:
            from rich.console import Console
            from InquirerPy.base.control import Choice
            from ..components import InputPrompter, ParameterDefinition, create_parameter_selector
            from ..components.bag_loader import create_bag_loader
            from ...ui.common_ui import Message
            from pathlib import Path
            
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
            
            # Load first bag to get topics (for topic selection)
            bag_loader = create_bag_loader(console)
            bag_info = bag_loader.load_bag_interactive(Path(bag_paths[0]))
            
            if not bag_info:
                Message.error("Failed to load bag file for topic selection", console)
                return {
                    'success': False,
                    'error': 'Bag loading failed',
                    'stdout': '',
                    'stderr': '',
                    'returncode': 1
                }
            
            # Define extract command parameters
            parameters = {
                'topics': ParameterDefinition(
                    name='topics',
                    display_name='Topics to Extract',
                    param_type='topics',
                    default=[],
                    message="Select topics to extract:",
                    help_text="Choose which topics to include in extracted bag"
                ),
                'compression': ParameterDefinition(
                    name='compression',
                    display_name='Compression Type',
                    param_type='select',
                    default='none',
                    choices=[
                        Choice("none", "No compression (fastest)"),
                        Choice("lz4", "LZ4 compression (balanced)"),
                        Choice("bz2", "BZ2 compression (best ratio)")
                    ],
                    message="Select compression type:",
                    help_text="Compression algorithm for output bag"
                ),
                'output_pattern': ParameterDefinition(
                    name='output_pattern',
                    display_name='Output Pattern',
                    param_type='text',
                    default="{input}_extracted_{timestamp}.bag",
                    message="Output file pattern:",
                    help_text="Pattern for output filename (supports {input}, {timestamp})"
                ),
                'verbose': ParameterDefinition(
                    name='verbose',
                    display_name='Verbose Output',
                    param_type='bool',
                    default=False,
                    message="Enable verbose output?",
                    help_text="Shows detailed processing information"
                ),
                'workers': ParameterDefinition(
                    name='workers',
                    display_name='Parallel Workers',
                    param_type='text',
                    default='',
                    message="Number of parallel workers (leave empty for default):",
                    help_text="Number of parallel workers for processing multiple bags (default: CPU count - 2)",
                    validator=lambda x: x == '' or (x.isdigit() and int(x) > 0)
                )
            }
            
            # Create parameter selector with loaded bag_info
            param_selector = create_parameter_selector(console, bag_info)
            
            # Interactive parameter selection
            selected_params = param_selector.select_parameters('extract', parameters)
            
            # Build command arguments
            args = [str(p) for p in bag_paths]
            
            # Add topics if specified
            topics = selected_params.get('topics', [])
            if topics:
                args.extend(['--topics'] + topics)
            
            # Add compression if not none
            compression = selected_params.get('compression', 'none')
            if compression != 'none':
                args.extend(['--compression', compression])
            
            # Add output pattern
            output_pattern = selected_params.get('output_pattern')
            if output_pattern:
                args.extend(['--output', output_pattern])
            
            # Add flags
            if selected_params.get('verbose', False):
                args.append('--verbose')
            
            # Add workers if specified
            workers = selected_params.get('workers', '')
            if workers and workers.strip():
                args.extend(['--workers', workers.strip()])
            
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
