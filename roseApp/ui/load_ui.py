"""
UI components for the load command.
Handles display formatting for bag file loading operations.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from .common_ui import Message
from .common_ui import CommonUI, ProgressUI


class LoadUI:
    """UI components specifically for the load command."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
        self.progress_ui = ProgressUI()
    
    def display_loading_started(self, file_count: int, build_index: bool) -> None:
        """Display loading started message."""
        index_text = "with DataFrame indexing" if build_index else "without indexing"
        Message.info(f"Loading {file_count} bag file(s, self.console) {index_text}...")
    
    def display_loading_progress(self, current: int, total: int, file_path: str) -> None:
        """Display loading progress for individual file."""
        file_name = Path(file_path).name
        if len(file_name) > 30:
            file_name = f"{file_name[:15]}...{file_name[-12:]}"
        
        self.console.print(f"  [{current}/{total}] Loading {file_name}...")
    
    def display_loading_success(self, file_path: str, elapsed_time: float, 
                              topics_count: int = 0, messages_count: int = 0) -> None:
        """Display successful file loading."""
        file_name = Path(file_path).name
        details = f"{topics_count} topics, {messages_count} messages" if topics_count > 0 else ""
        Message.success(
            f"✓ Loaded {file_name} in {elapsed_time:.2f}s {details}"
        , self.console)
    
    def display_loading_failed(self, file_path: str, error: str) -> None:
        """Display failed file loading."""
        file_name = Path(file_path).name
        Message.error(f"✗ Failed to load {file_name}: {error}", self.console)
    
    def display_batch_results(self, results: List[Dict[str, Any]], total_time: float) -> None:
        """Display batch loading results."""
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        # Show summary
        self.progress_ui.show_batch_results(len(successful), len(failed), total_time)
        
        # Show details
        if successful:
            self.display_success_summary(successful)
        
        if failed:
            self.display_failed_summary(failed)
    
    def display_success_summary(self, successful: List[Dict[str, Any]]) -> None:
        """Display successful loading summary."""
        total_topics = sum(r.get('topics_count', 0) for r in successful)
        total_messages = sum(r.get('messages_count', 0) for r in successful)
        total_size = sum(r.get('size_bytes', 0) for r in successful)
        
        if len(successful) == 1:
            result = successful[0]
            self.console.print(
                f"Loaded: {result.get('topics_count', 0)} topics, "
                f"{result.get('messages_count', 0)} messages, "
                f"{self.common_ui.format_file_size(result.get('size_bytes', 0))}"
            )
        else:
            self.console.print(
                f"Loaded {len(successful)} files: "
                f"{total_topics} topics, {total_messages} messages, "
                f"{self.common_ui.format_file_size(total_size)} total"
            )
    
    def display_failed_summary(self, failed: List[Dict[str, Any]]) -> None:
        """Display failed loading summary."""
        Message.error(f"Failed to load {len(failed, self.console)} file(s):")
        for result in failed:
            file_name = Path(result.get('file_path', '')).name
            error = result.get('error', 'Unknown error')
            self.console.print(f"  • {file_name}: {error}")
    
    def display_found_files(self, files: List[str], patterns: List[str]) -> None:
        """Display found files."""
        if not files:
            Message.warning("No bag files found matching patterns", self.console)
            for pattern in patterns:
                self.console.print(f"  Pattern: {pattern}")
            return
        
        Message.info(f"Found {len(files, self.console)} bag file(s):")
        for file_path in files:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                size = self.common_ui.format_file_size(file_path_obj.stat().st_size)
                self.console.print(f"  • {file_path} ({size})")
            else:
                self.console.print(f"  • {file_path} (not found)")
    
    def display_already_cached(self, file_path: str, is_valid: bool) -> None:
        """Display already cached file status."""
        file_name = Path(file_path).name
        if is_valid:
            Message.info(f"{file_name} is already cached and valid", self.console)
        else:
            Message.warning(f"{file_name} is cached but invalid - will reload", self.console)
    
    def display_reload_confirmation(self, file_path: str) -> bool:
        """Display reload confirmation."""
        file_name = Path(file_path).name
        return self.common_ui.ask_confirmation(
            f"{file_name} is already cached. Reload anyway?",
            default=False
        )
    
    def display_force_reload_info(self, count: int) -> None:
        """Display force reload information."""
        Message.info(f"Force reloading {count} file(s, self.console)...")
    
    def display_indexing_info(self, enabled: bool) -> None:
        """Display indexing configuration."""
        if enabled:
            Message.info("Building DataFrame indexes for enhanced analysis", self.console)
        else:
            Message.info("Loading without DataFrame indexing (faster, self.console)")
    
    def display_progress_header(self, total_files: int, build_index: bool) -> None:
        """Display progress header."""
        index_text = "with indexing" if build_index else "without indexing"
        self.progress_ui.show_processing_summary(total_files, 1, f"loading {index_text}")
    
    def display_loading_status(self, current: int, total: int, file_path: str, 
                             elapsed: float = 0.0) -> None:
        """Display detailed loading status."""
        file_name = Path(file_path).name
        if len(file_name) > 25:
            file_name = f"{file_name[:12]}...{file_name[-10:]}"
        
        status = f"[{current:3d}/{total:3d}] {file_name}"
        if elapsed > 0:
            status += f" ({elapsed:.1f}s)"
        
        self.console.print(status)
    
    def display_cache_miss(self, file_path: str) -> None:
        """Display cache miss information."""
        file_name = Path(file_path).name
        Message.info(f"Loading {file_name} into cache", self.console)
    
    def display_cache_hit(self, file_path: str, is_valid: bool) -> None:
        """Display cache hit information."""
        file_name = Path(file_path).name
        if is_valid:
            self.console.print(f"  [dim]Using cached {file_name}[/dim]")
        else:
            self.console.print(f"  [dim]Reloading cached {file_name} (invalid)[/dim]")
    
    def display_size_summary(self, total_size: int, file_count: int) -> None:
        """Display total size summary."""
        self.console.print(
            f"\nTotal: {file_count} file(s), "
            f"{self.common_ui.format_file_size(total_size)}"
        )
    
    def display_loading_cancelled(self) -> None:
        """Display loading cancelled message."""
        Message.warning("Loading cancelled by user", self.console)
    
    def display_validation_start(self, file_count: int) -> None:
        """Display validation start message."""
        Message.info(f"Validating {file_count} bag file(s, self.console)...")
    
    def display_validation_result(self, file_path: str, is_valid: bool, error: str = None) -> None:
        """Display validation result."""
        file_name = Path(file_path).name
        if is_valid:
            self.console.print(f"  ✓ {file_name}")
        else:
            self.console.print(f"  ✗ {file_name}: {error}")
    
    def display_validation_summary(self, valid_count: int, invalid_count: int) -> None:
        """Display validation summary."""
        total = valid_count + invalid_count
        self.console.print(f"\nValidation complete: {valid_count}/{total} files valid")
        
        if invalid_count > 0:
            Message.warning(f"{invalid_count} file(s, self.console) failed validation")
    
    def display_cleanup_info(self, removed_count: int, freed_space: int) -> None:
        """Display cleanup information."""
        if removed_count > 0:
            Message.info(
                f"Cleanup: removed {removed_count} invalid entries, "
                f"freed {self.common_ui.format_file_size(freed_space)}"
            )
    
    def display_memory_warning(self, estimated_memory: int) -> None:
        """Display memory usage warning."""
        Message.warning(
            f"Estimated memory usage: {self.common_ui.format_file_size(estimated_memory, self.console)}. "
            f"Consider using --no-index for large files."
        )
    
    def display_parallel_loading_info(self, file_count: int, workers: int) -> None:
        """Display parallel loading information."""
        self.progress_ui.show_processing_summary(file_count, workers, "parallel loading")
    
    def display_loading_error_summary(self, errors: List[str]) -> None:
        """Display loading error summary."""
        if errors:
            Message.error("Loading errors:", self.console)
            for error in errors[:5]:  # Show first 5 errors
                self.console.print(f"  • {error}")
            if len(errors) > 5:
                self.console.print(f"  ... and {len(errors) - 5} more")
    
    def ask_file_selection(self, files: List[str]) -> List[str]:
        """Ask user to select files for loading."""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        
        if not files:
            return []
        
        choices = [Choice(value=f, name=Path(f).name) for f in files]
        
        selected = inquirer.checkbox(
            message="Select files to load:",
            choices=choices,
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one file"
        ).execute()
        
        return selected
    
    def display_file_already_loaded(self, file_path: str) -> None:
        """Display file already loaded message."""
        file_name = Path(file_path).name
        Message.info(f"{file_name} is already loaded", self.console)
    
    def display_loading_start(self, file_path: str, build_index: bool) -> None:
        """Display loading start message."""
        file_name = Path(file_path).name
        index_text = " with indexing" if build_index else ""
        Message.info(f"Loading {file_name}{index_text}", self.console)