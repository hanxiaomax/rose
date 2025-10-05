#!/usr/bin/env python3
"""
Load Command - Delegates to: rose load
"""

from typing import List
from .base_command import BaseCommand


class LoadCommand(BaseCommand):
    """Delegates to: rose load"""
    
    def get_command_name(self) -> str:
        return "load"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse load command arguments
        
        Examples:
            /load *.bag @test → rose load *.bag /actual/path/to/test.bag
            /load data/test.bag → rose load data/test.bag
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Load bag files into Rose workspace

Usage: /load <bag_files...>

Examples:
  /load data.bag              Load single bag file
  /load *.bag                 Load all bag files in current directory
  /load @test data/*.bag      Load cached bag @test and all bags in data/
  /load --help                Show detailed load command help

The load command supports:
- Glob patterns (*.bag, data/*.bag)
- @ references to cached bags (@test.bag)
- Multiple file arguments
- All standard rose load options"""
