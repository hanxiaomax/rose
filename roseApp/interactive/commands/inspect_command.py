#!/usr/bin/env python3
"""
Inspect Command - Delegates to: rose inspect
"""

from typing import List
from .base_command import BaseCommand


class InspectCommand(BaseCommand):
    """Delegates to: rose inspect"""
    
    def get_command_name(self) -> str:
        return "inspect"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse inspect command arguments
        
        Examples:
            /inspect @test → rose inspect /actual/path/to/test.bag
            /inspect data.bag --topics → rose inspect data.bag --topics
        """
        if not interactive_args.strip():
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Inspect bag contents and statistics

Usage: /inspect <bag_file> [options]

Examples:
  /inspect data.bag                    Show basic bag information
  /inspect @test --topics              Show topics in cached bag @test
  /inspect data.bag --messages         Show message counts
  /inspect data.bag --duration         Show time range information
  /inspect --help                      Show detailed inspect command help

The inspect command supports:
- Basic bag information (default)
- Topic listing with --topics
- Message statistics with --messages
- Duration and time range with --duration
- @ references for bag files
- All standard rose inspect options"""
