#!/usr/bin/env python3
"""
Status Command - Internal status display
"""

import os
import time
from pathlib import Path
from typing import Dict, Any
from .base_command import BaseCommand


class StatusCommand(BaseCommand):
    """Internal status command - shows workspace status and running tasks"""
    
    def __init__(self, cli_executor, runner_state=None, rose_dirs=None, cache_manager=None, running_tasks=None):
        super().__init__(cli_executor)
        self.runner_state = runner_state
        self.rose_dirs = rose_dirs
        self.cache_manager = cache_manager
        self.running_tasks = running_tasks or {}
    
    def get_command_name(self) -> str:
        return "status"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute status command - display current status
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            self._show_status_summary()
            
            # Show running tasks
            if self.running_tasks:
                self.result_formatter.format_section_header("Running Tasks")
                for task_id, task in self.running_tasks.items():
                    elapsed = time.time() - (getattr(task, 'start_time', time.time()) or time.time())
                    self.result_formatter.console.print(f"  {task_id}: {getattr(task, 'command', 'Unknown')} ([yellow]{elapsed:.1f}s[/yellow])")
            
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
    
    def _show_status_summary(self):
        """Show comprehensive status summary with command recommendations"""
        from ...ui.theme import get_color
        
        self.result_formatter.format_section_header("Rose Interactive Environment Status")
        self.result_formatter.console.print()  # Empty line
        
        # System Paths
        if self.rose_dirs:
            self.result_formatter.format_section_header("System Paths")
            system_paths = {
                "Rose Directory": str(self.rose_dirs.rose_dir),
                "Config Directory": str(self.rose_dirs.config_dir),
                "Cache Directory": str(self.rose_dirs.cache_dir),
                "Logs Directory": str(self.rose_dirs.logs_dir)
            }
            self.result_formatter.format_status_info("System", system_paths)
            self.result_formatter.format_info("💡 Use /configuration to edit settings")
            self.result_formatter.console.print()
        
        # Workspace info
        self.result_formatter.format_section_header("Workspace")
        workspace_info = {
            "Current Directory": str(Path.cwd())
        }
        self.result_formatter.format_status_info("Current", workspace_info)
        self.result_formatter.console.print()
        
        # Loaded Bags
        self.result_formatter.format_section_header("Loaded Bags")
        if self.runner_state and self.runner_state.current_bags:
            bags_info = {
                "Count": len(self.runner_state.current_bags)
            }
            self.result_formatter.format_status_info("Bags", bags_info)
            
            for i, bag_path in enumerate(self.runner_state.current_bags, 1):
                bag_size = self._get_file_size_str(bag_path)
                cached_status = "✓ Cached" if bag_path in (self.runner_state.loaded_bags or {}) else "⏳ Loading..."
                bag_name = Path(bag_path).name
                
                self.result_formatter.console.print(
                    f"  {i:2d}. [{get_color('file')}]{bag_name}[/{get_color('file')}] - [{get_color('success') if 'Cached' in cached_status else get_color('warning')}]{cached_status}[/{get_color('success') if 'Cached' in cached_status else get_color('warning')}] ({bag_size})"
                )
            self.result_formatter.format_info("💡 Use /data info to view bag details")
        else:
            self.result_formatter.format_warning("No bags loaded")
            self.result_formatter.format_info("💡 Use /load to load bag files")
        self.result_formatter.console.print()
        
        # Selected Topics
        self.result_formatter.format_section_header("Selected Topics")
        if self.runner_state and self.runner_state.selected_topics:
            topics_info = {
                "Count": len(self.runner_state.selected_topics)
            }
            self.result_formatter.format_status_info("Topics", topics_info)
            
            for i, topic in enumerate(self.runner_state.selected_topics, 1):
                self.result_formatter.console.print(f"  {i:2d}. [{get_color('accent')}]{topic}[/{get_color('accent')}]")
            self.result_formatter.format_info("💡 Use /data export to export topic data")
        else:
            self.result_formatter.format_warning("No topics selected")
            self.result_formatter.format_info("💡 Load bags first, then use /extract to select topics")
        self.result_formatter.console.print()
        
        # Cache Information
        if self.rose_dirs:
            self.result_formatter.format_section_header("Cache Information")
            try:
                cache_size = self._get_cache_size_info()
                cache_entries = self._count_cached_bags()
                
                cache_info = {
                    "Cache Size": cache_size,
                    "Cached Bags": cache_entries
                }
                self.result_formatter.format_status_info("Cache", cache_info)
                
                if cache_entries > 0:
                    self.result_formatter.format_info("💡 Use /cache list to view cached bags, /cache clear to clean up")
                else:
                    self.result_formatter.format_info("💡 Cache will be populated as you analyze bags")
            except Exception as e:
                self.result_formatter.format_warning(f"Error reading cache: {e}")
            self.result_formatter.console.print()
        
        # Configuration Status
        if self.rose_dirs:
            self.result_formatter.format_section_header("Configuration")
            config_files = [
                self.rose_dirs.rose_dir / "config.json",
                self.rose_dirs.rose_dir / "config.yaml",
                self.rose_dirs.rose_dir / "config.yml"
            ]
            
            config_found = False
            for config_file in config_files:
                if config_file.exists():
                    config_info = {"Config File": str(config_file)}
                    self.result_formatter.format_status_info("Found", config_info)
                    config_found = True
                    break
            
            if not config_found:
                self.result_formatter.format_warning("Config file not found (using defaults)")
            
            self.result_formatter.format_info("💡 Use /configuration to edit configuration")
            self.result_formatter.console.print()
        
        # Quick Actions Summary
        self.result_formatter.format_section_header("Quick Actions")
        if not self.runner_state or not self.runner_state.current_bags:
            self.result_formatter.format_command_help("/load *.bag", "Load bag files from current directory")
        else:
            self.result_formatter.format_command_help("/data info", "View detailed bag information")
            if not self.runner_state.selected_topics:
                self.result_formatter.format_command_help("/extract", "Select topics for analysis")
            else:
                self.result_formatter.format_command_help("/data export", "Export selected topic data")
        
        self.result_formatter.format_command_help("/help", "Show detailed help documentation")
        self.result_formatter.format_muted("Type any command for more options")
    
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
    
    def _get_file_size_str(self, file_path: str) -> str:
        """Get human-readable file size string"""
        try:
            size = Path(file_path).stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f}{unit}"
                size /= 1024
            return f"{size:.1f}TB"
        except Exception:
            return "Unknown"
    
    def _get_cache_size_info(self) -> str:
        """Get cache directory size information"""
        try:
            total_size = 0
            if self.rose_dirs:
                cache_path = Path(self.rose_dirs.cache_dir)
                if cache_path.exists():
                    for file_path in cache_path.rglob('*'):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
            
            # Convert to human readable
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024:
                    return f"{total_size:.1f}{unit}"
                total_size /= 1024
            return f"{total_size:.1f}TB"
        except Exception:
            return "Unknown"
    
    def _count_cached_bags(self) -> int:
        """Count number of cached bag analyses"""
        try:
            if self.rose_dirs:
                cache_path = Path(self.rose_dirs.cache_dir)
                if cache_path.exists():
                    # Count .json files in cache directory (assuming each represents a cached bag analysis)
                    return len(list(cache_path.rglob('*.json')))
            return 0
        except Exception:
            return 0
    
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
