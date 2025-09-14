"""
UI components for the compress command.
Handles display formatting for ROS bag file compression.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from .common_ui import Message
from .common_ui import CommonUI, ProgressUI, TableUI
from .theme import get_color


class CompressUI:
    """UI components specifically for the compress command."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
        self.progress_ui = ProgressUI()
        self.table_ui = TableUI()
    
    def display_compression_summary(self, results: List[Dict[str, Any]], compression_type: str) -> None:
        """Display compression results summary."""
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        if successful:
            Message.success("\n✓ Compression completed successfully", self.console)
            
            # Create compression results table
            self.table_ui.display_compression_summary_list(successful)
            
        if failed:
            self.display_failed_compressions(failed)
    
    def display_failed_compressions(self, failed_results: List[Dict[str, Any]]) -> None:
        """Display failed compression files."""
        if not failed_results:
            return
            
        Message.error(f"Failed to compress {len(failed_results)} file(s):")
        for result in failed_results:
            file_name = Path(result.get('input_file', '')).name
            error = result.get('error', 'Unknown error')
            self.console.print(f"  • {file_name}: {error}")
    
    def display_compression_progress(self, file_name: str, progress_callback=None) -> Optional[callable]:
        """Display compression progress for individual file."""
        display_name = file_name
        if len(file_name) > 40:
            display_name = f"{file_name[:15]}...{file_name[-20:]}"
        
        if progress_callback:
            return lambda percent: progress_callback(percent)
        return None
    
    def display_batch_header(self, total_files: int, workers: int, compression: str) -> None:
        """Display batch compression header."""
        self.progress_ui.show_processing_summary(total_files, workers, f"{compression.upper()} compression")
    
    def display_batch_results(self, results: List[Dict[str, Any]], total_time: float) -> None:
        """Display batch compression results."""
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        # Show processing summary
        self.progress_ui.show_batch_results(len(successful), len(failed), total_time)
        
        # Show compression details
        if successful:
            self.display_compression_summary(successful, "compression")
    
    def display_dry_run_preview(self, files: List[str], output_pattern: str, compression: str) -> None:
        """Display dry run preview of compression operations."""
        Message.warning("DRY RUN - Preview of compression operations:", self.console)
        
        for file_path in files:
            input_path = Path(file_path)
            output_name = self._generate_output_name(input_path, output_pattern, compression)
            self.console.print(f"  {input_path.name} -> {output_name}")
        
        self.console.print(f"Compression: {compression.upper()}")
    
    def _generate_output_name(self, input_path: Path, pattern: str, compression: str) -> str:
        """Generate output filename based on pattern."""
        import time
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output = pattern
        
        # Replace placeholders
        output = output.replace('{input}', input_path.stem)
        output = output.replace('{timestamp}', timestamp)
        output = output.replace('{compression}', compression)
        
        # If no placeholders, create default
        if output == pattern:
            output = f"{input_path.stem}_{compression}_{timestamp}.bag"
            
        return output
    
    def display_validation_summary(self, validation_results: List[Dict[str, Any]]) -> None:
        """Display validation results for compressed files."""
        valid_files = [v for v in validation_results if v.get('valid', False)]
        invalid_files = [v for v in validation_results if not v.get('valid', False)]
        
        self.console.print(f"\n[bold]Validation Summary[/bold]")
        
        if valid_files:
            Message.success(f"  {len(valid_files)} bag(s) passed validation")
            
        if invalid_files:
            Message.error(f"  {len(invalid_files)} bag(s) failed validation")
            for v in invalid_files:
                file_name = Path(v.get('file', '')).name
                error = v.get('error', 'Unknown error')
                self.console.print(f"    {file_name}: {error}")
    
    def display_found_files(self, files: List[Path]) -> None:
        """Display found bag files."""
        if not files:
            Message.info("No bag files found", self.console)
            return
            
        Message.info(f"Found {len(files)} bag file(s):")
        for file in files:
            if file.exists():
                size = self.common_ui.format_file_size(file.stat().st_size)
                self.console.print(f"  • {file} ({size})")
            else:
                self.console.print(f"  • {file} (not found)")
    
    def display_cache_loading(self, uncached_files: List[Path]) -> None:
        """Display cache loading status."""
        if uncached_files:
            Message.warning(f"{len(uncached_files)} bag(s) not in cache. Loading...")
            for file in uncached_files:
                self.console.print(f"  Loading: {file.name}")
    
    def display_loading_complete(self, file_path: str, elapsed_time: float) -> None:
        """Display successful cache loading."""
        Message.success(f"✓ Successfully loaded {Path(file_path, self.console).name} into cache in {elapsed_time:.2f}s")
    
    def display_loading_failed(self, file_path: str, error: str) -> None:
        """Display failed cache loading."""
        Message.error(f"✗ Failed to load {Path(file_path, self.console).name}: {error}")
    
    def confirm_compression(self, total_files: int, compression: str) -> bool:
        """Confirm compression operation."""
        return self.common_ui.ask_confirmation(
            f"Compress {total_files} file(s) with {compression.upper()} compression?",
            default=False
        )
    
    def confirm_load_cache(self, count: int) -> bool:
        """Confirm loading uncached files."""
        return self.common_ui.ask_confirmation(
            f"Load {count} uncached bag(s) automatically?",
            default=True
        )
    
    def display_compression_options(self, available: List[str]) -> None:
        """Display available compression options."""
        Message.info("Available compression types:", self.console)
        for comp in available:
            self.console.print(f"  • {comp.upper()}")
    
    def display_invalid_compression(self, compression: str, valid: List[str]) -> None:
        """Display invalid compression error."""
        Message.error(
            f"Invalid compression '{compression}'. Valid options: {', '.join(valid)}"
        )
    
    def display_file_not_found(self, patterns: List[str]) -> None:
        """Display file not found message."""
        Message.error("No bag files found matching the specified patterns", self.console)
        for pattern in patterns:
            self.console.print(f"  Pattern: {pattern}")
    
    def display_compression_started(self, files: List[str], workers: int, compression: str) -> None:
        """Display compression start message."""
        Message.info(
            f"Compressing {len(files)} bag file(s) with {workers} worker(s) (using {compression.upper()} compression)..."
        )
    
    def display_single_file_compression(self, input_file: str, output_file: str, compression: str) -> None:
        """Display single file compression details."""
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if input_path.exists() and output_path.exists():
            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size
            ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            
            self.console.print(f"\n[bold]Compression Result:[/bold]")
            self.console.print(f"  Input:  {input_path.name} ({self.common_ui.format_file_size(input_size)})")
            self.console.print(f"  Output: {output_path.name} ({self.common_ui.format_file_size(output_size)})")
            self.console.print(f"  Reduction: {ratio:.1f}%")
    
    def display_final_summary(self, successful: int, failed: int, compression: str) -> None:
        """Display final compression summary."""
        if successful > 0:
            Message.success(
                f"Success: {successful} bag(s, self.console) compressed with {compression.upper()} compression"
            )
        
        if failed > 0:
            Message.error(f"Failed: {failed} bag(s, self.console) could not be compressed")