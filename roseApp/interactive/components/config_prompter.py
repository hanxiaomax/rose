#!/usr/bin/env python3
"""
Configuration Prompter - Handle default configuration prompts for interactive commands
"""

from typing import Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from roseApp.core.config import get_config
from roseApp.ui.theme import get_color


class ConfigPrompter:
    """Handle configuration prompts for interactive commands"""
    
    def __init__(self, console: Console):
        self.console = console
        self.config = get_config()
    
    def get_command_defaults(self, command_name: str) -> Dict[str, Any]:
        """
        Get default configuration for a command
        
        Args:
            command_name: Name of the command (e.g., 'load', 'extract')
            
        Returns:
            Dictionary of default configuration values
        """
        try:
            interactive_defaults = getattr(self.config, 'interactive_defaults', {})
            if isinstance(interactive_defaults, dict):
                return interactive_defaults.get(command_name, {})
            return {}
        except Exception:
            return {}
    
    def show_defaults(self, command_name: str, defaults: Dict[str, Any]) -> None:
        """
        Display default configuration as a formatted list (dynamically parsed from YAML)
        
        Args:
            command_name: Name of the command
            defaults: Dictionary of default values from YAML
        """
        if not defaults:
            return
        
        from ...ui.common_ui import Message
        
        # Display header
        Message.info(f"Default configuration for '{command_name}':", self.console)
        
        # Display each configuration item as a list
        for key, value in defaults.items():
            # Convert key to readable format (e.g., build_index -> Build Index)
            key_display = key.replace('_', ' ').title()
            
            # Format value based on type (dynamic formatting)
            if isinstance(value, bool):
                value_display = "Yes" if value else "No"
                style = get_color('success') if value else get_color('warning')
            elif isinstance(value, (list, tuple)):
                # Escape brackets for Rich markup
                value_display = f"\\[{', '.join(str(v) for v in value)}\\]"
                style = get_color('accent')
            elif isinstance(value, dict):
                value_display = f"{len(value)} items"
                style = get_color('accent')
            elif value is None:
                value_display = "Not set"
                style = get_color('muted')
            else:
                value_display = str(value)
                style = get_color('accent')
            
            # Print as list item with bullet
            self.console.print(
                f"  • [{get_color('muted')}]{key_display}:[/{get_color('muted')}] "
                f"[{style}]{value_display}[/{style}]"
            )
    
    def prompt_use_defaults(self, command_name: str) -> bool:
        """
        Ask user if they want to use default configuration (dynamically from YAML)
        
        Args:
            command_name: Name of the command
            
        Returns:
            True if user wants to use defaults, False otherwise
        """
        defaults = self.get_command_defaults(command_name)
        
        if not defaults:
            # No defaults configured in YAML, skip prompt
            return False
        
        # Show defaults (dynamically parsed from YAML)
        self.console.print()  # Add spacing
        self.show_defaults(command_name, defaults)
        self.console.print()  # Add spacing
        
        # Ask if user wants to use them
        use_defaults = inquirer.confirm(
            message="Use default configuration?",
            default=True
        ).execute()
        
        return use_defaults
    
    def merge_with_defaults(
        self, 
        command_name: str, 
        user_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge user parameters with default configuration
        
        Args:
            command_name: Name of the command
            user_params: User-provided parameters
            
        Returns:
            Merged configuration with user params taking precedence
        """
        defaults = self.get_command_defaults(command_name)
        
        # Start with defaults
        merged = defaults.copy()
        
        # Override with user params (only non-None values)
        for key, value in user_params.items():
            if value is not None:
                merged[key] = value
        
        return merged
    
    def prompt_for_parameters(
        self,
        command_name: str,
        parameter_prompts: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Prompt user for command parameters with defaults
        
        Args:
            command_name: Name of the command
            parameter_prompts: Dictionary of parameter definitions
                Format: {
                    'param_name': {
                        'type': 'select'|'confirm'|'text'|'filepath',
                        'message': 'Prompt message',
                        'choices': [...],  # For select type
                        'default': value,  # Optional default
                        'validate': callable  # Optional validation
                    }
                }
        
        Returns:
            Dictionary of parameter values
        """
        defaults = self.get_command_defaults(command_name)
        params = {}
        
        for param_name, prompt_config in parameter_prompts.items():
            prompt_type = prompt_config.get('type', 'text')
            message = prompt_config.get('message', f'Enter {param_name}:')
            default = prompt_config.get('default', defaults.get(param_name))
            
            if prompt_type == 'select':
                choices = prompt_config.get('choices', [])
                value = inquirer.select(
                    message=message,
                    choices=choices,
                    default=default
                ).execute()
            elif prompt_type == 'confirm':
                value = inquirer.confirm(
                    message=message,
                    default=default if default is not None else True
                ).execute()
            elif prompt_type == 'filepath':
                validate = prompt_config.get('validate')
                value = inquirer.filepath(
                    message=message,
                    default=str(default) if default else None,
                    validate=validate
                ).execute()
            else:  # text
                validate = prompt_config.get('validate')
                value = inquirer.text(
                    message=message,
                    default=str(default) if default else '',
                    validate=validate
                ).execute()
            
            params[param_name] = value
        
        return params


def create_config_prompter(console: Console) -> ConfigPrompter:
    """
    Create a ConfigPrompter instance
    
    Args:
        console: Rich console instance
        
    Returns:
        ConfigPrompter instance
    """
    return ConfigPrompter(console)

