#!/usr/bin/env python3
"""
Bags Command - Internal bag management
"""

from typing import Dict, Any
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
            
            if not args or args[0] == "list":
                self._show_bags_list()
            elif args[0] == "clear":
                self._clear_bags()
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
    
    def _show_bags_list(self):
        """Display list of loaded bags"""
        self.result_formatter.format_section_header("Loaded Bag Files")
        
        if not self.runner_state or not self.runner_state.current_bags:
            self.result_formatter.format_info("No bags currently loaded")
            self.result_formatter.format_muted("Use '/load <bag_files>' to load bags")
            return
        
        for i, bag_path in enumerate(self.runner_state.current_bags, 1):
            status = "cached" if bag_path in self.runner_state.loaded_bags else "loaded"
            self.result_formatter.console.print(f"  {i}. [cyan]{bag_path}[/cyan] ({status})")
    
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
    
    def get_help_text(self) -> str:
        return """Manage loaded bag files in workspace

Usage: /bags [operation] [args]

Operations:
  list    - List all loaded bags (default)
  clear   - Clear all loaded bags from workspace  
  remove  - Remove specific bag by path or index

This is an internal command for workspace bag management."""
