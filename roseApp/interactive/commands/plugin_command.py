#!/usr/bin/env python3
"""
Plugin Command - Delegates to: rose plugin
"""

from typing import List
from .base_command import BaseCommand


class PluginCommand(BaseCommand):
    """Delegates to: rose plugin"""
    
    def get_command_name(self) -> str:
        return "plugin"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse plugin command arguments
        
        Examples:
            /plugin → rose plugin list (default)
            /plugin list → rose plugin list
            /plugin install my_plugin → rose plugin install my_plugin
            /plugin run my_plugin @input → rose plugin run my_plugin /path/to/input.bag
        """
        if not interactive_args.strip():
            # Default to 'list' when no arguments provided
            return ['list']
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Plugin system operations

Usage: /plugin [operation] [options]

Examples:
  /plugin                         List all available plugins (default)
  /plugin list                    List all available plugins
  /plugin info my_plugin          Show plugin information
  /plugin install my_plugin       Install a new plugin
  /plugin run my_plugin @input    Run plugin on cached bag
  /plugin enable my_plugin        Enable a plugin
  /plugin disable my_plugin       Disable a plugin
  /plugin uninstall my_plugin     Uninstall a plugin
  /plugin --help                  Show detailed plugin command help

The plugin command supports:
- List available and installed plugins
- Install, enable, disable and uninstall plugins
- Run plugins on bag data
- Show plugin information and help
- @ references for plugin input files
- All standard rose plugin options"""
