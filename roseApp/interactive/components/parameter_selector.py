#!/usr/bin/env python3
"""
Parameter Selector - Interactive parameter configuration with selective modification
"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from rich.console import Console
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from roseApp.core.config import get_config
from roseApp.ui.theme import get_color


class ParameterDefinition:
    """Definition of a command parameter"""
    
    def __init__(
        self,
        name: str,
        display_name: str,
        param_type: str,
        default: Any = None,
        choices: Optional[List[Any]] = None,
        message: Optional[str] = None,
        validator: Optional[Callable] = None,
        help_text: Optional[str] = None
    ):
        """
        Initialize parameter definition
        
        Args:
            name: Parameter name (internal)
            display_name: Display name for UI
            param_type: Type of parameter ('bool', 'select', 'text', 'filepath', 'topics')
            default: Default value
            choices: Choices for select type
            message: Prompt message
            validator: Validation function
            help_text: Help text for parameter
        """
        self.name = name
        self.display_name = display_name
        self.param_type = param_type
        self.default = default
        self.choices = choices or []
        self.message = message or f"Enter {display_name}:"
        self.validator = validator
        self.help_text = help_text or ""


class ParameterSelector:
    """Interactive parameter selector with list-based configuration"""
    
    def __init__(self, console: Console, bag_info=None):
        """
        Initialize parameter selector
        
        Args:
            console: Rich console instance
            bag_info: Loaded bag information (ComprehensiveBagInfo) for topic selection
        """
        self.console = console
        self.bag_info = bag_info
        self.config = get_config()
        self._bag_info_callback = None
    
    def set_bag_info_callback(self, callback):
        """
        Set callback for when bag info is updated.
        Useful for updating parent context when new bag is loaded.
        
        Args:
            callback: Function(bag_info) -> None
        """
        self._bag_info_callback = callback
    
    def get_command_defaults(self, command_name: str) -> Dict[str, Any]:
        """Get default configuration for a command"""
        try:
            interactive_defaults = getattr(self.config, 'interactive_defaults', {})
            if isinstance(interactive_defaults, dict):
                return interactive_defaults.get(command_name, {})
            return {}
        except Exception:
            return {}
    
    def format_value_display(self, value: Any) -> tuple[str, str]:
        """
        Format value for display
        
        Returns:
            Tuple of (formatted_value, color_style)
        """
        if isinstance(value, bool):
            display = "Yes" if value else "No"
            style = get_color('success') if value else get_color('warning')
        elif isinstance(value, (list, tuple)):
            if len(value) == 0:
                display = "Not set"
                style = get_color('muted')
            else:
                items = ', '.join(str(v) for v in value[:3])
                if len(value) > 3:
                    display = f"{items}, ... ({len(value)} total)"
                else:
                    display = items
                style = get_color('accent')
        elif value is None or value == '':
            display = "Not set"
            style = get_color('muted')
        else:
            display = str(value)
            style = get_color('accent')
        
        return display, style
    
    def show_parameters_list(
        self, 
        parameters: Dict[str, ParameterDefinition],
        current_values: Dict[str, Any]
    ) -> None:
        """
        Display parameters in a list format
        
        Args:
            parameters: Parameter definitions
            current_values: Current parameter values
        """
        self.console.print()
        self.console.print(f"[bold {get_color('primary')}]Current Configuration:[/bold {get_color('primary')}]")
        self.console.print()
        
        for param_name, param_def in parameters.items():
            value = current_values.get(param_name, param_def.default)
            value_display, value_style = self.format_value_display(value)
            
            # Simple list format: parameter name + value
            self.console.print(
                f"  [{get_color('muted')}]{param_def.display_name}:[/{get_color('muted')}] "
                f"[{value_style}]{value_display}[/{value_style}]"
            )
        
        self.console.print()
    
    def prompt_parameter_selection(
        self,
        parameters: Dict[str, ParameterDefinition],
        current_values: Dict[str, Any]
    ) -> Optional[str]:
        """
        Prompt user to select which parameter to modify
        
        Args:
            parameters: Parameter definitions
            current_values: Current parameter values
            
        Returns:
            Selected parameter name or None to confirm all
        """
        choices = []
        
        # Add option to confirm current configuration
        choices.append(Choice(
            value=None,
            name="✓ Confirm and continue"
        ))
        
        # Add each parameter as a choice - only show parameter name
        for param_name, param_def in parameters.items():
            choices.append(Choice(
                value=param_name, 
                name=param_def.display_name
            ))
        
        selected = inquirer.select(
            message="Select parameter to modify (or confirm to proceed):",
            choices=choices,
            default=None,
            pointer="→"
        ).execute()
        
        return selected
    
    def prompt_for_parameter(
        self,
        param_def: ParameterDefinition,
        current_value: Any
    ) -> Any:
        """
        Prompt user to modify a specific parameter
        
        Args:
            param_def: Parameter definition
            current_value: Current value
            
        Returns:
            New parameter value
        """
        message = param_def.message
        default = current_value if current_value is not None else param_def.default
        
        # Handle different parameter types
        if param_def.param_type == 'bool':
            return inquirer.confirm(
                message=message,
                default=default if default is not None else False
            ).execute()
        
        elif param_def.param_type == 'select':
            return inquirer.select(
                message=message,
                choices=param_def.choices,
                default=default
            ).execute()
        
        elif param_def.param_type == 'bag_filepath':
            # Special handling for bag file input with automatic loading
            from .input_prompter import InputPrompter
            from .bag_loader import create_bag_loader
            
            prompter = InputPrompter(self.console)
            
            # Prompt for bag file
            bag_path = prompter.prompt_for_single_file(
                message=message,
                validator=lambda path: Path(path).suffix == '.bag',
                default=str(default) if default else None
            )
            
            if not bag_path:
                return current_value
            
            # Immediately load bag with cache check
            bag_loader = create_bag_loader(self.console)
            bag_info = bag_loader.load_bag_interactive(bag_path, force_reload=False)
            
            if bag_info:
                # Update internal bag_info for topic selection
                self.bag_info = bag_info
                
                # Notify parent context if callback is set
                if self._bag_info_callback:
                    self._bag_info_callback(bag_info)
            
            return bag_path
        
        elif param_def.param_type == 'topics':
            # Use topic selector for topic selection
            if not self.bag_info:
                self.console.print(f"[{get_color('error')}]Error: No bag information available for topic selection[/{get_color('error')}]")
                return current_value
            
            try:
                # Get topics from already loaded bag_info
                if not self.bag_info.topics:
                    self.console.print(f"[{get_color('warning')}]No topics found in bag file[/{get_color('warning')}]")
                    return []
                
                all_topics = [topic.name for topic in self.bag_info.topics]
                
                # Use topic selector
                from .topic_selector import select_topics_interactive
                selected_topics = select_topics_interactive(
                    console=self.console,
                    topics=all_topics,
                    message=message,
                    require_selection=False,
                    preselected=current_value if isinstance(current_value, list) else []
                )
                return selected_topics
                
            except Exception as e:
                from ...core.util import get_logger
                logger = get_logger('parameter_selector')
                logger.error(f"Error selecting topics: {e}", exc_info=True)
                self.console.print(f"[{get_color('error')}]Error selecting topics: {e}[/{get_color('error')}]")
                return current_value
        
        elif param_def.param_type == 'filepath':
            return inquirer.filepath(
                message=message,
                default=str(default) if default else None,
                validate=param_def.validator
            ).execute()
        
        elif param_def.param_type == 'text':
            return inquirer.text(
                message=message,
                default=str(default) if default else '',
                validate=param_def.validator
            ).execute()
        
        else:
            # Default to text input
            return inquirer.text(
                message=message,
                default=str(default) if default else ''
            ).execute()
    
    def select_parameters(
        self,
        command_name: str,
        parameters: Dict[str, ParameterDefinition]
    ) -> Dict[str, Any]:
        """
        Interactive parameter selection with list-based modification
        
        Workflow:
        1. Load defaults from configuration
        2. Show all parameters in a table
        3. User can:
           - Press Enter to confirm all defaults
           - Select a parameter to modify
        4. If parameter selected, prompt for new value
        5. Repeat until user confirms
        
        Args:
            command_name: Name of the command
            parameters: Parameter definitions
            
        Returns:
            Dictionary of final parameter values
        """
        # Initialize with defaults
        defaults = self.get_command_defaults(command_name)
        current_values = {}
        
        for param_name, param_def in parameters.items():
            # Use config default if available, otherwise use parameter default
            current_values[param_name] = defaults.get(param_name, param_def.default)
        
        # Interactive loop
        while True:
            # Show current configuration
            self.show_parameters_list(parameters, current_values)
            
            # Prompt for parameter selection
            selected_param = self.prompt_parameter_selection(parameters, current_values)
            
            # If None (confirm), break the loop
            if selected_param is None:
                break
            
            # Get parameter definition
            param_def = parameters[selected_param]
            
            # Prompt for new value
            try:
                new_value = self.prompt_for_parameter(
                    param_def,
                    current_values[selected_param]
                )
                current_values[selected_param] = new_value
                
                from ...ui.common_ui import Message
                Message.success(
                    f"Updated {param_def.display_name} to: {new_value}",
                    self.console
                )
                
            except KeyboardInterrupt:
                self.console.print(f"\n[{get_color('warning')}]Parameter modification cancelled[/{get_color('warning')}]")
                continue
            except Exception as e:
                self.console.print(f"[{get_color('error')}]Error setting parameter: {e}[/{get_color('error')}]")
                continue
        
        return current_values


def create_parameter_selector(
    console: Console,
    bag_info=None
) -> ParameterSelector:
    """
    Create a ParameterSelector instance
    
    Args:
        console: Rich console instance
        bag_info: Loaded bag information (ComprehensiveBagInfo) for topic selection
        
    Returns:
        ParameterSelector instance
    """
    return ParameterSelector(console, bag_info)

