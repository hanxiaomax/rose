#!/usr/bin/env python3
"""
Exit Command - Internal exit handling
"""

from typing import Dict, Any
from .base_command import BaseCommand


class ExitCommand(BaseCommand):
    """Internal exit command - exits interactive mode"""
    
    def get_command_name(self) -> str:
        return "exit"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute exit command - exit interactive mode
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            self.result_formatter.format_info("Goodbye!")
            
            # Signal exit by raising EOFError
            raise EOFError("User requested exit")
            
        except EOFError:
            # Re-raise EOFError to exit the REPL loop
            raise
        except Exception as e:
            return {
                'success': False,
                'error': f"Exit command failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def get_help_text(self) -> str:
        return """Exit interactive mode

Usage: /exit or /quit

Exits the Rose interactive environment and returns to the shell.

This command:
- Performs cleanup of resources
- Saves session state if configured
- Terminates background tasks gracefully
- Returns to the shell prompt

Aliases: /exit, /quit"""
