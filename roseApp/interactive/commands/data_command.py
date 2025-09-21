#!/usr/bin/env python3
"""
Data Command - Delegates to: rose data
"""

from typing import List
from .base_command import BaseCommand


class DataCommand(BaseCommand):
    """Delegates to: rose data"""
    
    def get_command_name(self) -> str:
        return "data"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse data command arguments
        
        Examples:
            /data → rose data --help (show help, default)
            /data info bag.bag → rose data info bag.bag
            /data export @input → rose data export /path/to/input.bag
        """
        if not interactive_args.strip():
            # Default to showing help when no arguments provided
            return ['--help']
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Data operations and export

Usage: /data [operation] [options]

Examples:
  /data                                       Show data command help (default)
  /data info bag_file.bag                     Show data information for bag
  /data export @input                         Export cached bag data
  /data data bag_file.bag                     Process specific bag file
  /data --help                                Show detailed data command help

The data command supports:
- Show data information and available DataFrames
- Export bag data to various formats
- Data manipulation and analysis
- @ references for input files
- All standard rose data options"""
