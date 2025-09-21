#!/usr/bin/env python3
"""
Extract Command - Delegates to: rose extract
"""

from typing import List
from .base_command import BaseCommand


class ExtractCommand(BaseCommand):
    """Delegates to: rose extract"""
    
    def get_command_name(self) -> str:
        return "extract"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse extract command arguments
        
        Examples:
            /extract @input @output -t /camera/image → rose extract /path/to/input.bag /path/to/output.bag -t /camera/image
            /extract input.bag output.bag --topics /gps → rose extract input.bag output.bag --topics /gps
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Extract topics from bag files

Usage: /extract <input_bag> <output_bag> [options]

Examples:
  /extract input.bag output.bag                    Extract all topics
  /extract @input @output -t /camera/image         Extract specific topic using @ references
  /extract input.bag output.bag --topics /gps     Extract GPS topic
  /extract input.bag output.bag --whitelist w.txt Extract using whitelist file
  /extract --help                                  Show detailed extract command help

The extract command supports:
- Topic filtering with -t/--topics
- Whitelist files with --whitelist
- Time range filtering
- @ references for input/output files
- All standard rose extract options"""
