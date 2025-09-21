#!/usr/bin/env python3
"""
Command Router - Routes commands to appropriate handlers
"""

from typing import Dict, Optional
from ..commands.base_command import BaseCommand
from ...core.util import get_logger

logger = get_logger("command_router")


class CommandRouter:
    """Command routing system"""
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
    
    def register_command(self, command_prefix: str, command_instance: BaseCommand):
        """
        Register a command with the router
        
        Args:
            command_prefix: Command prefix (e.g., '/load')
            command_instance: Command instance to handle the command
        """
        self.commands[command_prefix] = command_instance
        logger.debug(f"Registered command: {command_prefix}")
    
    def route_command(self, user_input: str) -> Optional[BaseCommand]:
        """
        Route user input to appropriate command
        
        Args:
            user_input: User input string
            
        Returns:
            Command instance if found, None otherwise
        """
        # Check for slash commands
        for cmd_prefix, command_instance in self.commands.items():
            if user_input.startswith(cmd_prefix):
                return command_instance
        
        return None
    
    def get_command_args(self, user_input: str, command_prefix: str) -> str:
        """
        Extract command arguments from user input
        
        Args:
            user_input: Full user input
            command_prefix: Command prefix to remove
            
        Returns:
            Arguments string after removing command prefix
        """
        return user_input[len(command_prefix):].strip()
    
    def get_available_commands(self) -> Dict[str, BaseCommand]:
        """
        Get all available commands
        
        Returns:
            Dictionary of command prefix to command instance
        """
        return self.commands.copy()
    
    def get_command_suggestions(self, partial_input: str) -> list:
        """
        Get command suggestions for partial input
        
        Args:
            partial_input: Partial command input
            
        Returns:
            List of matching command suggestions
        """
        if not partial_input.startswith('/'):
            return []
        
        suggestions = []
        for cmd_prefix in self.commands.keys():
            if cmd_prefix.startswith(partial_input):
                suggestions.append(cmd_prefix)
        
        return sorted(suggestions)
