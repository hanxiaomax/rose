#!/usr/bin/env python3
"""
Compress Command - Delegates to: rose compress
"""

from typing import List
from .base_command import BaseCommand


class CompressCommand(BaseCommand):
    """Delegates to: rose compress"""
    
    def get_command_name(self) -> str:
        return "compress"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse compress command arguments
        
        Examples:
            /compress @input --compression lz4 → rose compress /path/to/input.bag --compression lz4
            /compress data.bag -c bz2 → rose compress data.bag -c bz2
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Compress bag files

Usage: /compress <bag_file> [options]

Examples:
  /compress data.bag                           Compress with default settings
  /compress @input --compression lz4          Compress cached bag with LZ4
  /compress data.bag -c bz2                   Compress with BZ2
  /compress data.bag --output compressed.bag  Specify output file
  /compress --help                            Show detailed compress command help

The compress command supports:
- LZ4 compression (fast, good ratio)
- BZ2 compression (slower, best ratio)
- Custom output file specification
- @ references for input files
- All standard rose compress options"""
