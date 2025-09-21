#!/usr/bin/env python3
"""
Clear Command - Internal console clear
"""

from typing import Dict, Any
from .base_command import BaseCommand


class ClearCommand(BaseCommand):
    """Internal clear command - clears console screen"""
    
    def get_command_name(self) -> str:
        return "clear"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute clear command - clear console screen
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            # Clear the console
            self.result_formatter.console.clear()
            
            return {
                'success': True,
                'message': 'Console cleared',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Clear command failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def get_help_text(self) -> str:
        return """Clear console screen

Usage: /clear

Clears the console screen in the interactive environment.
This is equivalent to the 'clear' or 'cls' command in most terminals.

No arguments are accepted for this command."""
