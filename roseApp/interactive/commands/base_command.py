#!/usr/bin/env python3
"""
Base command class for interactive CLI commands
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any

from ..components import CLIExecutor, PathCompleter, ResultFormatter
from ...core.util import get_logger

logger = get_logger("base_command")


class BaseCommand(ABC):
    """Base command - only does parameter conversion and result formatting"""
    
    def __init__(self, cli_executor: CLIExecutor):
        self.cli_executor = cli_executor
        self.path_completer = PathCompleter()
        self.result_formatter = ResultFormatter()
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute command: convert args → call CLI → format result
        
        Args:
            interactive_args: Arguments from interactive input
            
        Returns:
            Execution result dictionary
        """
        try:
            # 1. Parse interactive arguments
            cli_args = self._parse_args(interactive_args)
            
            # 2. Execute actual CLI command
            result = self.cli_executor.execute_command(self.get_command_name(), cli_args)
            
            # 3. Post-process result if needed
            processed_result = self._post_process_result(result)
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Command execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Command execution failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def execute_interactive(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute command with interactive output (no capture)
        
        Args:
            interactive_args: Arguments from interactive input
            
        Returns:
            Execution result dictionary
        """
        try:
            # 1. Parse interactive arguments
            cli_args = self._parse_args(interactive_args)
            
            # 2. Execute actual CLI command interactively
            result = self.cli_executor.execute_command_interactive(self.get_command_name(), cli_args)
            
            return result
            
        except Exception as e:
            logger.error(f"Interactive command execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Interactive command execution failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    @abstractmethod
    def get_command_name(self) -> str:
        """
        Get the CLI command name
        
        Returns:
            Command name (e.g., 'load', 'extract')
        """
        pass
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse interactive arguments into CLI arguments
        
        Default implementation: resolve @ references and split by whitespace
        Subclasses can override for custom parsing logic
        
        Args:
            interactive_args: Raw interactive arguments
            
        Returns:
            List of CLI arguments
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def _post_process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process CLI result before returning
        
        Default implementation: return result as-is
        Subclasses can override for custom processing
        
        Args:
            result: Raw CLI execution result
            
        Returns:
            Processed result
        """
        return result
    
    def get_help_text(self) -> str:
        """
        Get help text for this command
        
        Returns:
            Help text string
        """
        return f"Execute {self.get_command_name()} command"
