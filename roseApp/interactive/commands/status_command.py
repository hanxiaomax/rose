#!/usr/bin/env python3
"""
Status Command - Internal status display
"""

from typing import Dict, Any
from .base_command import BaseCommand


class StatusCommand(BaseCommand):
    """Internal status command - shows workspace status and running tasks"""
    
    def __init__(self, cli_executor, runner_state=None):
        super().__init__(cli_executor)
        self.runner_state = runner_state
    
    def get_command_name(self) -> str:
        return "status"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute status command - display current status
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            self._show_status_display()
            return {
                'success': True,
                'message': 'Status displayed',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Status display failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _show_status_display(self):
        """Display current workspace status"""
        self.result_formatter.format_section_header("Rose Interactive Status")
        
        # Show workspace info
        if self.runner_state:
            workspace_info = {
                "Workspace": self.runner_state.workspace_path,
                "Loaded bags": len(self.runner_state.current_bags),
                "Selected topics": len(self.runner_state.selected_topics),
                "Session uptime": self._format_uptime()
            }
            self.result_formatter.format_status_info("Workspace", workspace_info)
            
            # Show loaded bags
            if self.runner_state.current_bags:
                self.result_formatter.format_list_items(
                    "Loaded Bags", 
                    self.runner_state.current_bags,
                    lambda bag: f"{bag} ({'cached' if bag in self.runner_state.loaded_bags else 'not cached'})"
                )
            
            # Show selected topics
            if self.runner_state.selected_topics:
                self.result_formatter.format_list_items("Selected Topics", self.runner_state.selected_topics)
        else:
            self.result_formatter.format_warning("Runner state not available")
    
    def _format_uptime(self) -> str:
        """Format session uptime"""
        if not self.runner_state or not hasattr(self.runner_state, 'created_at'):
            return "Unknown"
        
        import time
        uptime_seconds = time.time() - self.runner_state.created_at
        
        if uptime_seconds < 60:
            return f"{int(uptime_seconds)} seconds"
        elif uptime_seconds < 3600:
            return f"{int(uptime_seconds / 60)} minutes"
        else:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_help_text(self) -> str:
        return """Show workspace status and running tasks

Usage: /status

Shows:
- Current workspace information
- Loaded bag files and their status
- Selected topics for operations
- Session uptime and statistics
- Running background tasks (if any)

This is an internal command that displays current Rose interactive session state."""
