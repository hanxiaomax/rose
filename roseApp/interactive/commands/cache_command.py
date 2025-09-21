#!/usr/bin/env python3
"""
Cache Command - Delegates to: rose cache
"""

from typing import List
from .base_command import BaseCommand


class CacheCommand(BaseCommand):
    """Delegates to: rose cache"""
    
    def get_command_name(self) -> str:
        return "cache"
    
    def _parse_args(self, interactive_args: str) -> List[str]:
        """
        Parse cache command arguments
        
        Examples:
            /cache → rose cache (show cache status, default)
            /cache clear → rose cache clear
            /cache export → rose cache export
        """
        if not interactive_args.strip():
            # Default to showing cache status when no arguments provided
            return []
        
        # Resolve @ references to actual paths
        resolved_args = self.path_completer.resolve_at_references(interactive_args)
        
        # Split into arguments
        return resolved_args.split()
    
    def get_help_text(self) -> str:
        return """Cache management operations

Usage: /cache [operation] [options]

Examples:
  /cache                          Show cache status (default)
  /cache clear                    Clear all cache
  /cache export                   Export cache entries to file
  /cache --help                   Show detailed cache command help

The cache command supports:
- Show cache status and statistics
- Clear cache completely
- Export cache entries to file
- All standard rose cache options"""
