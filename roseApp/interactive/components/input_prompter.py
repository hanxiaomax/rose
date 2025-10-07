#!/usr/bin/env python3
"""
Input Prompter - Interactive input handler with auto-completion for bag files

Provides a unified interface for prompting users for bag file inputs when
they are not provided via command line arguments. Supports tab completion
and validation.
"""

from pathlib import Path
from typing import List, Optional, Callable, Union, TYPE_CHECKING
from InquirerPy import inquirer
from InquirerPy.validator import PathValidator
from rich.console import Console

from ...core.util import get_logger
from ...ui.theme import get_color

if TYPE_CHECKING:
    from ...core.model import ComprehensiveBagInfo

logger = get_logger("input_prompter")


class InputPrompter:
    """
    Interactive input prompter with auto-completion support.
    
    This component provides a consistent way to prompt users for bag file
    inputs across all CLI commands when running in interactive mode.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def prompt_for_bag_files(
        self, 
        message: str = "Select bag file(s):",
        allow_multiple: bool = False,
        required: bool = True
    ) -> List[Path]:
        """
        Prompt user to select bag file(s) with auto-completion.
        
        Args:
            message: Prompt message to display
            allow_multiple: Whether to allow multiple file selection
            required: Whether at least one file is required
            
        Returns:
            List of selected bag file paths
        """
        try:
            if allow_multiple:
                return self._prompt_multiple_bags(message, required)
            else:
                bag_path = self._prompt_single_bag(message, required)
                return [bag_path] if bag_path else []
                
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled by user[/{get_color('warning')}]")
            return []
        except Exception as e:
            logger.error(f"Error prompting for bag files: {e}", exc_info=True)
            self.console.print(f"[{get_color('error')}]Error: {e}[/{get_color('error')}]")
            return []
    
    def prompt_for_single_file(
        self,
        message: str = "Select file:",
        validator: Optional[Callable] = None,
        default: Optional[str] = None
    ) -> Optional[Path]:
        """
        Prompt user to select a single file with auto-completion.
        
        Args:
            message: Prompt message to display
            validator: Optional validation function
            default: Default value
            
        Returns:
            Selected file path or None
        """
        try:
            result = inquirer.filepath(
                message=message,
                default=default or "",
                validate=validator or PathValidator(is_file=True, message="File does not exist"),
                only_files=True
            ).execute()
            
            return Path(result) if result else None
            
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled by user[/{get_color('warning')}]")
            return None
        except Exception as e:
            logger.error(f"Error prompting for file: {e}", exc_info=True)
            return None
    
    def prompt_for_directory(
        self,
        message: str = "Select directory:",
        default: Optional[str] = None,
        create_if_not_exists: bool = False
    ) -> Optional[Path]:
        """
        Prompt user to select a directory.
        
        Args:
            message: Prompt message to display
            default: Default directory path
            create_if_not_exists: Whether to create directory if it doesn't exist
            
        Returns:
            Selected directory path or None
        """
        try:
            result = inquirer.filepath(
                message=message,
                default=default or "",
                only_directories=True
            ).execute()
            
            if result:
                dir_path = Path(result)
                if create_if_not_exists and not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.console.print(f"[{get_color('success')}]Created directory: {dir_path}[/{get_color('success')}]")
                return dir_path
            
            return None
            
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled by user[/{get_color('warning')}]")
            return None
        except Exception as e:
            logger.error(f"Error prompting for directory: {e}", exc_info=True)
            return None
    
    def prompt_for_text(
        self,
        message: str,
        default: Optional[str] = None,
        validator: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Prompt user for text input.
        
        Args:
            message: Prompt message to display
            default: Default value
            validator: Optional validation function
            
        Returns:
            User input text or None
        """
        try:
            result = inquirer.text(
                message=message,
                default=default or "",
                validate=validator
            ).execute()
            
            return result if result else None
            
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled by user[/{get_color('warning')}]")
            return None
        except Exception as e:
            logger.error(f"Error prompting for text: {e}", exc_info=True)
            return None
    
    def confirm(
        self,
        message: str,
        default: bool = False
    ) -> bool:
        """
        Prompt user for yes/no confirmation.
        
        Args:
            message: Confirmation message
            default: Default answer
            
        Returns:
            True if user confirms, False otherwise
        """
        try:
            return inquirer.confirm(
                message=message,
                default=default
            ).execute()
            
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled by user[/{get_color('warning')}]")
            return False
        except Exception as e:
            logger.error(f"Error prompting for confirmation: {e}", exc_info=True)
            return False
    
    def _prompt_single_bag(
        self,
        message: str,
        required: bool
    ) -> Optional[Path]:
        """
        Prompt for a single bag file with simple path building.
        
        Args:
            message: Prompt message
            required: Whether input is required
            
        Returns:
            Selected bag file path or None
        """
        return self._simple_path_builder(message, required, allow_multiple=False)
    
    def _prompt_multiple_bags(
        self,
        message: str,
        required: bool
    ) -> List[Path]:
        """
        Prompt for multiple bag files with simple path building.
        
        Args:
            message: Prompt message
            required: Whether at least one file is required
            
        Returns:
            List of selected bag file paths
        """
        result = self._simple_path_builder(message, required, allow_multiple=True)
        return result if isinstance(result, list) else ([result] if result else [])
    
    def _simple_path_builder(
        self,
        message: str,
        required: bool,
        allow_multiple: bool = False
    ) -> Union[Optional[Path], List[Path]]:
        """
        Simple path builder: continue if directory, process if file.
        
        Args:
            message: Prompt message
            required: Whether input is required
            allow_multiple: Whether to allow multiple files
            
        Returns:
            Single Path, List of Paths, or None
        """
        try:
            current_path = ""
            
            while True:
                # Build prompt message
                if current_path:
                    prompt_msg = f"{message} (current: {current_path})"
                else:
                    prompt_msg = message
                
                # Get user input
                user_input = inquirer.filepath(
                    message=prompt_msg,
                    default=current_path,
                    only_files=False,
                    multicolumn_complete=True,
                    validate=lambda x: True,
                    mandatory=required
                ).execute()
                
                if not user_input:
                    return [] if allow_multiple else None
                
                user_input = user_input.strip()
                path = Path(user_input)
                
                # If it's a glob pattern, process immediately
                if '*' in user_input or '?' in user_input:
                    import glob
                    matches = glob.glob(user_input)
                    bag_files = [Path(p) for p in matches if Path(p).suffix == '.bag']
                    
                    if not bag_files:
                        self.console.print(f"[{get_color('warning')}]No bag files found matching: {user_input}[/{get_color('warning')}]")
                        current_path = ""
                        continue
                    
                    if allow_multiple:
                        return bag_files
                    else:
                        if len(bag_files) == 1:
                            return bag_files[0]
                        else:
                            choice = inquirer.select(
                                message="Select a bag file:",
                                choices=[str(bag) for bag in bag_files]
                            ).execute()
                            return Path(choice) if choice else None
                
                # If path exists
                if path.exists():
                    if path.is_dir():
                        # Directory: continue building path
                        current_path = str(path) + "/" if not user_input.endswith('/') else user_input
                        continue
                    elif path.is_file():
                        # File: check if it's a bag file and process
                        if path.suffix == '.bag':
                            return [path] if allow_multiple else path
                        else:
                            self.console.print(f"[{get_color('warning')}]Not a bag file: {path}[/{get_color('warning')}]")
                            current_path = ""
                            continue
                else:
                    # Path doesn't exist, might be partial - continue building
                    current_path = user_input
                    continue
            
        except KeyboardInterrupt:
            self.console.print(f"\n[{get_color('warning')}]Operation cancelled[/{get_color('warning')}]")
            return [] if allow_multiple else None
        except Exception as e:
            logger.error(f"Error in path builder: {e}", exc_info=True)
            return [] if allow_multiple else None
    
    def show_missing_input_help(self, command_name: str):
        """
        Show helpful message when required input is missing.
        
        Args:
            command_name: Name of the command that needs input
        """
        self.console.print(f"\n[{get_color('warning')}]No input files specified[/{get_color('warning')}]")
        self.console.print(f"\n[{get_color('info')}]You can provide input in several ways:[/{get_color('info')}]")
        self.console.print(f"  1. [{get_color('accent')}]rose {command_name} *.bag[/{get_color('accent')}] - Use glob patterns")
        self.console.print(f"  2. [{get_color('accent')}]rose {command_name} file.bag[/{get_color('accent')}] - Specify file directly")
        self.console.print(f"  3. [{get_color('accent')}]rose {command_name} --help[/{get_color('accent')}] - Show full usage information")
    
    def prompt_and_load_bag(
        self,
        message: str = "Select bag file:",
        allow_multiple: bool = False,
        auto_load: bool = True
    ) -> Union[Optional['ComprehensiveBagInfo'], List['ComprehensiveBagInfo']]:
        """
        Unified workflow: prompt for bag file(s) and load with cache check.
        
        This is the recommended way to handle bag input in interactive commands.
        
        Workflow:
        1. Prompt user to select bag file(s)
        2. For each bag:
           a. Check if in cache
           b. If cached: Load from cache
           c. If not cached: Ask user to load (with/without index)
        3. Return loaded bag info
        
        Args:
            message: Prompt message for file selection
            allow_multiple: Whether to allow multiple file selection
            auto_load: Whether to automatically load bags (prompt user for options)
            
        Returns:
            Single ComprehensiveBagInfo, List of ComprehensiveBagInfo, or None
        """
        from .bag_loader import create_bag_loader
        from roseApp.core.model import ComprehensiveBagInfo
        
        # Step 1: Prompt for bag files
        bag_paths = self.prompt_for_bag_files(
            message=message,
            allow_multiple=allow_multiple,
            required=True
        )
        
        if not bag_paths:
            return [] if allow_multiple else None
        
        # Step 2: Load bags with cache check
        bag_loader = create_bag_loader(self.console)
        loaded_bags = []
        
        for bag_path in bag_paths:
            if auto_load:
                # Interactive load with cache check
                bag_info = bag_loader.load_bag_interactive(bag_path, force_reload=False)
                if bag_info:
                    loaded_bags.append(bag_info)
                else:
                    from ...ui.common_ui import Message
                    Message.warning(f"Skipping bag: {bag_path.name}", self.console)
            else:
                # Just return paths without loading
                loaded_bags.append(bag_path)
        
        if not loaded_bags:
            from ...ui.common_ui import Message
            Message.error("No bags were successfully loaded", self.console)
            return [] if allow_multiple else None
        
        # Return single or list based on allow_multiple
        if allow_multiple:
            return loaded_bags
        else:
            return loaded_bags[0] if loaded_bags else None

