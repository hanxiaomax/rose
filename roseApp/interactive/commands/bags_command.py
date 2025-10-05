#!/usr/bin/env python3
"""
Bags Command - Internal bag management
"""

from pathlib import Path
from typing import Dict, Any
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from prompt_toolkit.shortcuts import confirm
from .base_command import BaseCommand


class BagsCommand(BaseCommand):
    """Internal bags command - manages loaded bag files in workspace"""
    
    def __init__(self, cli_executor, runner_state=None):
        super().__init__(cli_executor)
        self.runner_state = runner_state
    
    def get_command_name(self) -> str:
        return "bags"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute bags command - manage loaded bags
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            args = interactive_args.strip().split() if interactive_args.strip() else []
            
            if not args:
                # No arguments - show interactive interface
                self._show_bags_interactive()
            elif args[0] == "list":
                self._list_current_bags()
            elif args[0] == "clear":
                self._clear_bags()
            elif args[0] == "add" and len(args) > 1:
                self._add_bag_to_workspace(args[1])
            elif args[0] == "remove" and len(args) > 1:
                self._remove_bag(args[1])
            else:
                self._show_bags_help()
            
            return {
                'success': True,
                'message': 'Bags command completed',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Bags command failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _show_bags_interactive(self):
        """Interactive bag management interface"""
        while True:
            action = inquirer.select(
                message="Bag Management:",
                choices=[
                    Choice(value="list", name="1. List loaded bags"),
                    Choice(value="add", name="2. Add bag file"),
                    Choice(value="remove", name="3. Remove bag file"),
                    Choice(value="clear", name="4. Clear all bags"),
                    Choice(value="back", name="5. Back")
                ]
            ).execute()
            
            if action == "back":
                break
            elif action == "list":
                self._list_current_bags()
            elif action == "add":
                bag_path = self._select_bag_file()
                if bag_path:
                    self._add_bag_to_workspace(bag_path)
            elif action == "remove":
                self._remove_bag_interactive()
            elif action == "clear":
                if confirm("Clear all bags from workspace?"):
                    self._clear_bags()
    
    def _list_current_bags(self):
        """List currently loaded bags with enhanced display"""
        from ...ui.theme import get_color
        
        if not self.runner_state or not self.runner_state.current_bags:
            self.result_formatter.format_warning("No bags loaded in workspace")
            return
        
        self.result_formatter.console.print()
        self.result_formatter.format_section_header("Loaded Bags")
        
        for i, bag_path in enumerate(self.runner_state.current_bags, 1):
            bag_name = Path(bag_path).name
            
            if bag_path in (self.runner_state.loaded_bags or {}):
                bag_info = self.runner_state.loaded_bags[bag_path]
                topics_count = len(bag_info.get('topics', []))
                size_mb = bag_info.get('file_size_mb', 0)
                size_str = f"{size_mb:.1f} MB"
                details = f"✓ Cached ({topics_count} topics, {size_str})"
                
                self.result_formatter.console.print(
                    f"  {i:2d}. [{get_color('file')}]{bag_name}[/{get_color('file')}] - [{get_color('success')}]{details}[/{get_color('success')}]"
                )
            else:
                self.result_formatter.console.print(
                    f"  {i:2d}. [{get_color('file')}]{bag_name}[/{get_color('file')}] - [{get_color('warning')}]⏳ Loading...[/{get_color('warning')}]"
                )
    
    def _show_bags_list(self):
        """Legacy method - delegates to _list_current_bags"""
        self._list_current_bags()
    
    def _clear_bags(self):
        """Clear all loaded bags"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        if not self.runner_state.current_bags:
            self.result_formatter.format_info("No bags to clear")
            return
        
        count = len(self.runner_state.current_bags)
        self.runner_state.current_bags.clear()
        self.runner_state.loaded_bags.clear()
        self.runner_state.selected_topics.clear()
        
        self.result_formatter.console.print(f"[green]✓[/green] Cleared {count} bag(s) from workspace")
    
    def _remove_bag(self, bag_identifier: str):
        """Remove specific bag from workspace"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        # Try to find bag by path or index
        bag_to_remove = None
        
        # Try as index first
        if bag_identifier.isdigit():
            index = int(bag_identifier) - 1
            if 0 <= index < len(self.runner_state.current_bags):
                bag_to_remove = self.runner_state.current_bags[index]
        
        # Try as path
        if not bag_to_remove:
            for bag in self.runner_state.current_bags:
                if bag_identifier in bag:
                    bag_to_remove = bag
                    break
        
        if bag_to_remove:
            self.runner_state.current_bags.remove(bag_to_remove)
            if bag_to_remove in self.runner_state.loaded_bags:
                del self.runner_state.loaded_bags[bag_to_remove]
            
            self.result_formatter.console.print(f"[green]✓[/green] Removed bag: {bag_to_remove}")
        else:
            self.result_formatter.format_warning(f"Bag not found: {bag_identifier}")
    
    def _show_bags_help(self):
        """Show bags command help"""
        self.result_formatter.format_section_header("Bags Command Help")
        
        help_text = """Available operations:
  /bags list              List all loaded bags (default)
  /bags clear             Clear all loaded bags from workspace
  /bags remove <bag>      Remove specific bag (by path or index)

Examples:
  /bags                   Show loaded bags
  /bags clear             Clear all bags
  /bags remove 1          Remove first bag
  /bags remove test.bag   Remove bag containing 'test.bag'"""
        
        self.result_formatter.console.print(help_text)
    
    def _select_bag_file(self) -> str:
        """Interactive bag file selection"""
        # Look for bag files in current directory
        current_dir = Path('.')
        bag_files = list(current_dir.glob('*.bag'))
        
        if not bag_files:
            # Ask user for file path
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag'),
                invalid_message="Please select a valid .bag file"
            ).execute()
            return bag_path
        
        # Show available files
        choices = [Choice(value=str(bag), name=f"{bag.name} ({bag.stat().st_size // (1024*1024)} MB)") 
                  for bag in bag_files]
        choices.append(Choice(value="browse", name="Browse for other file..."))
        
        selected = inquirer.select(
            message="Select bag file:",
            choices=choices
        ).execute()
        
        if selected == "browse":
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag'),
                invalid_message="Please select a valid .bag file"
            ).execute()
            return bag_path
        
        return selected
    
    def _add_bag_to_workspace(self, bag_path: str):
        """Add bag file to workspace"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
            
        if bag_path in self.runner_state.current_bags:
            self.result_formatter.format_warning(f"Bag already in workspace: {Path(bag_path).name}")
            return
        
        self.runner_state.current_bags.append(bag_path)
        self.result_formatter.format_info(f"Added bag to workspace: {Path(bag_path).name}")
        
        # Suggest loading if not cached
        if hasattr(self.runner_state, 'loaded_bags') and bag_path not in (self.runner_state.loaded_bags or {}):
            self.result_formatter.format_info(f"💡 Tip: Use '/load {bag_path}' to load it into cache")
    
    def _remove_bag_interactive(self):
        """Remove bag file interactively"""
        if not self.runner_state or not self.runner_state.current_bags:
            self.result_formatter.format_warning("No bags to remove")
            return
        
        choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner_state.current_bags]
        
        selected = inquirer.select(
            message="Select bag to remove:",
            choices=choices
        ).execute()
        
        if selected:
            self.runner_state.current_bags.remove(selected)
            if hasattr(self.runner_state, 'loaded_bags') and selected in (self.runner_state.loaded_bags or {}):
                del self.runner_state.loaded_bags[selected]
            self.result_formatter.format_info(f"Removed bag: {Path(selected).name}")
    
    def get_help_text(self) -> str:
        return """Manage loaded bag files in workspace

Usage: /bags [operation] [args]

Operations:
  list    - List all loaded bags (default)
  clear   - Clear all loaded bags from workspace  
  remove  - Remove specific bag by path or index

This is an internal command for workspace bag management."""
