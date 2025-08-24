"""
UI components for the cache command.
Handles display formatting for cache management operations.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from .common_ui import Message
from .common_ui import CommonUI, TableUI
from .theme import get_color


class CacheUI:
    """UI components specifically for the cache command."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
        self.table_ui = TableUI()
    
    def display_cache_list(self, cache_entries: List[Dict[str, Any]]) -> None:
        """Display list of cache entries."""
        if not cache_entries:
            Message.info("No cache entries found", self.console)
            return
            
        table = Table(title="Cache Entries")
        table.add_column("File", style="cyan")
        table.add_column("Size", style="green", justify="right")
        table.add_column("Topics", style="blue", justify="right")
        table.add_column("Messages", style="magenta", justify="right")
        table.add_column("Duration", style="yellow", justify="right")
        table.add_column("Modified", style="dim")
        
        for entry in cache_entries:
            file_path = entry.get('file_path', '')
            file_name = Path(file_path).name
            
            table.add_row(
                file_name,
                self.common_ui.format_file_size(entry.get('size_bytes', 0)),
                str(entry.get('topics_count', 0)),
                str(entry.get('messages_count', 0)),
                f"{entry.get('duration_seconds', 0):.1f}s",
                entry.get('modified_time', 'Unknown')
            )
        
        self.console.print(table)
        
        # Show summary
        total_size = sum(entry.get('size_bytes', 0) for entry in cache_entries)
        total_files = len(cache_entries)
        
        Message.muted(f"\nTotal: {total_files} files, {self.common_ui.format_file_size(total_size)}")
    
    def display_cache_stats(self, stats: Dict[str, Any]) -> None:
        """Display cache statistics."""
        table = Table(title="Cache Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in stats.items():
            if key.endswith('_bytes'):
                value = self.common_ui.format_file_size(value)
            elif key.endswith('_count'):
                value = str(value)
            table.add_row(key.replace('_', ' ').title(), str(value))
        
        self.console.print(table)
    
    def display_cache_clear_confirmation(self, entries: List[str]) -> bool:
        """Display cache clear confirmation."""
        return self.common_ui.ask_confirmation(
            f"Clear {len(entries)} cache entries?",
            default=False
        )
    
    def display_cache_clear_success(self, cleared_count: int) -> None:
        """Display cache clear success."""
        Message.success(f"Cleared {cleared_count} cache entries", self.console)
    
    def display_cache_clear_all_confirmation(self) -> bool:
        """Display confirmation for clearing all cache."""
        return self.common_ui.ask_confirmation(
            "Clear all cache entries? This action cannot be undone.",
            default=False
        )
    
    def display_cache_clear_all_success(self, cleared_count: int) -> None:
        """Display success for clearing all cache."""
        Message.success(f"Cleared all {cleared_count} cache entries", self.console)
    
    def display_cache_entry_details(self, entry: Dict[str, Any]) -> None:
        """Display detailed cache entry information."""
        if not entry:
            Message.warning("Cache entry not found", self.console)
            return
            
        table = Table(title=f"Cache Entry: {Path(entry.get('file_path', '')).name}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        details = [
            ("File Path", entry.get('file_path', '')),
            ("File Size", self.common_ui.format_file_size(entry.get('size_bytes', 0))),
            ("Topics Count", str(entry.get('topics_count', 0))),
            ("Messages Count", str(entry.get('messages_count', 0))),
            ("Duration", f"{entry.get('duration_seconds', 0):.1f}s"),
            ("Created", entry.get('created_time', 'Unknown')),
            ("Modified", entry.get('modified_time', 'Unknown')),
            ("Valid", "Yes" if entry.get('is_valid', True) else "No"),
        ]
        
        for prop, value in details:
            table.add_row(prop, value)
        
        self.console.print(table)
        
        # Show topics if available
        topics = entry.get('topics', [])
        if topics:
            self.common_ui.print_bold(f"\nTopics ({len(topics)}):")
            for topic in topics[:10]:  # Show first 10 topics
                self.console.print(f"  • {topic}")
            if len(topics) > 10:
                self.console.print(f"  ... and {len(topics) - 10} more")
    
    def display_cache_rebuild_confirmation(self, file_path: str) -> bool:
        """Display cache rebuild confirmation."""
        return self.common_ui.ask_confirmation(
            f"Rebuild cache for {Path(file_path).name}?",
            default=True
        )
    
    def display_cache_rebuild_success(self, file_path: str) -> None:
        """Display cache rebuild success."""
        Message.success(f"Rebuilt cache for {Path(file_path, self.console).name}")
    
    def display_cache_rebuild_failed(self, file_path: str, error: str) -> None:
        """Display cache rebuild failure."""
        Message.error(f"Failed to rebuild cache for {Path(file_path, self.console).name}: {error}")
    
    def display_cache_status(self, file_path: str, is_cached: bool, is_valid: bool) -> None:
        """Display cache status for a file."""
        file_name = Path(file_path).name
        
        if is_cached and is_valid:
            Message.success(f"✓ {file_name} is cached and valid", self.console)
        elif is_cached and not is_valid:
            Message.warning(f"⚠ {file_name} is cached but invalid (needs rebuild, self.console)")
        else:
            Message.info(f"○ {file_name} is not cached", self.console)
    
    def display_cache_size_info(self, total_size: int, entry_count: int) -> None:
        """Display cache size information."""
        self.common_ui.print_bold("\nCache Size Information:")
        self.console.print(f"  Total Size: {self.common_ui.format_file_size(total_size)}")
        self.console.print(f"  Entry Count: {entry_count}")
        
        if total_size > 1024 * 1024 * 100:  # > 100MB
            Message.warning("  Warning: Large cache size", self.console)
    
    def display_cache_optimization_summary(self, removed_count: int, freed_space: int) -> None:
        """Display cache optimization summary."""
        Message.success(
            f"Optimized cache: removed {removed_count} entries, freed {self.common_ui.format_file_size(freed_space)}"
        )
    
    def display_cache_validation_results(self, results: List[Dict[str, Any]]) -> None:
        """Display cache validation results."""
        valid = [r for r in results if r.get('valid', True)]
        invalid = [r for r in results if not r.get('valid', True)]
        
        self.common_ui.print_bold("\nCache Validation Results:")
        self.console.print(f"  Valid entries: {len(valid)}")
        self.console.print(f"  Invalid entries: {len(invalid)}")
        
        if invalid:
            Message.error("\nInvalid entries:", self.console)
            for entry in invalid[:5]:  # Show first 5 invalid entries
                file_path = entry.get('file_path', 'Unknown')
                error = entry.get('error', 'Unknown error')
                self.console.print(f"  • {Path(file_path).name}: {error}")
            
            if len(invalid) > 5:
                self.console.print(f"  ... and {len(invalid) - 5} more")
    
    def display_cache_export_success(self, export_path: str, entry_count: int) -> None:
        """Display cache export success."""
        Message.success(
            f"Exported {entry_count} cache entries to {export_path}"
        , self.console)
    
    def display_cache_import_success(self, import_path: str, entry_count: int) -> None:
        """Display cache import success."""
        Message.success(
            f"Imported {entry_count} cache entries from {import_path}"
        , self.console)
    
    def display_cache_import_failed(self, import_path: str, error: str) -> None:
        """Display cache import failure."""
        Message.error(f"Failed to import cache from {import_path}: {error}", self.console)
    
    def ask_cache_entry_selection(self, entries: List[str]) -> Optional[List[str]]:
        """Ask user to select cache entries."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        if not entries:
            Message.warning("No cache entries available", self.console)
            return None
        
        choices = [Choice(value=e, name=Path(e).name) for e in entries]
        
        selected = inquirer.checkbox(
            message="Select cache entries:",
            choices=choices,
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one entry"
        ).execute()
        
        return selected
    
    def display_cache_empty(self) -> None:
        """Display empty cache message."""
        Message.info("Cache is empty", self.console)
    
    def display_cache_loading_progress(self, current: int, total: int, file_path: str) -> None:
        """Display cache loading progress."""
        file_name = Path(file_path).name
        self.console.print(f"  Loading {current}/{total}: {file_name}")
    
    def display_cache_corrupted_warning(self, file_path: str) -> None:
        """Display corrupted cache warning."""
        Message.warning(
            f"Corrupted cache entry detected: {Path(file_path, self.console).name}"
        )
    
    def ask_cache_action(self, available_actions: List[str]) -> str:
        """Ask user to select cache action."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        choices = [Choice(value=action, name=action.replace('_', ' ').title()) 
                  for action in available_actions]
        
        return inquirer.select(
            message="Select cache action:",
            choices=choices
        ).execute()