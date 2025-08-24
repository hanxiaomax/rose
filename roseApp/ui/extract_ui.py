"""
UI components for the extract command.
Handles display formatting for ROS bag data extraction.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from .common_ui import Message
from .common_ui import CommonUI, ProgressUI, TableUI
from .theme import get_color


class ExtractUI:
    """UI components specifically for the extract command."""
    
    def __init__(self):
        self.console = Console()
        self.common_ui = CommonUI()
        self.progress_ui = ProgressUI()
        self.table_ui = TableUI()
    
    def display_extraction_summary(self, input_file: str, output_file: str, topics: List[str], 
                                 compression: str, success: bool, elapsed_time: float) -> None:
        """Display extraction summary after completion."""
        if success:
            Message.success(f"Extraction completed in {elapsed_time:.2f}s", self.console)
            summary_data = {
                "Input": Path(input_file).name,
                "Output": Path(output_file).name,
                "Topics": len(topics),
                "Compression": compression.upper(),
                "Elapsed": f"{elapsed_time:.2f}s"
            }
            self.common_ui.display_summary_table(summary_data, "Extraction Summary")
        else:
            Message.error("Extraction failed", self.console)
    
    def display_extraction_progress(self, input_file: str, progress_callback=None) -> None:
        """Display extraction progress with progress bar."""
        file_name = Path(input_file).name
        if len(file_name) > 40:
            file_name = f"{file_name[:15]}...{file_name[-20:]}"
        
        if progress_callback:
            return lambda percent: progress_callback(percent)
        
        return None
    
    def display_batch_progress_header(self, total_files: int, workers: int, operation: str) -> None:
        """Display header for batch processing."""
        self.progress_ui.show_processing_summary(total_files, workers, operation)
    
    def display_batch_results(self, results: List[Dict[str, Any]], total_time: float) -> None:
        """Display batch extraction results."""
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        # Show progress summary
        self.progress_ui.show_batch_results(len(successful), len(failed), total_time)
        
        # Show detailed results if there are any
        if successful:
            self.display_compression_summary(successful)
        
        if failed:
            self.display_failed_files(failed)
    
    def display_compression_summary(self, results: List[Dict[str, Any]]) -> None:
        """Display compression size summary for extracted files."""
        if not results:
            return
            
        table = self.table_ui.create_compression_summary_table(results)
        self.console.print(table)
    
    def display_failed_files(self, failed_results: List[Dict[str, Any]]) -> None:
        """Display failed extraction files."""
        if not failed_results:
            return
            
        Message.error(f"Failed to extract {len(failed_results, self.console)} file(s):")
        for result in failed_results:
            file_name = Path(result.get('input_file', '')).name
            error = result.get('error', 'Unknown error')
            self.console.print(f"  • {file_name}: {error}")
    
    def display_topics_selection(self, topics: List[str], selected_topics: List[str]) -> None:
        """Display topic selection summary."""
        if not topics:
            Message.info("No topics found in bag file", self.console)
            return
            
        Message.info(f"Found {len(topics)} topics, selected {len(selected_topics)}")
        
        # Show selected topics
        if selected_topics:
            self.common_ui.display_topics_list(selected_topics)
        else:
            Message.warning("No topics selected for extraction", self.console)
    
    def display_time_range_info(self, start_time: Optional[float], end_time: Optional[float], 
                              bag_start: float, bag_end: float) -> None:
        """Display time range selection information."""
        if start_time is not None and end_time is not None:
            Message.info(f"Time range: {start_time:.3f}s - {end_time:.3f}s", self.console)
            Message.info(f"Bag range: {bag_start:.3f}s - {bag_end:.3f}s", self.console)
        else:
            Message.info("Using full bag duration", self.console)
    
    def display_dry_run_preview(self, input_files: List[str], output_pattern: str, 
                              topics: List[str], compression: str) -> None:
        """Display dry run preview of extraction operations."""
        Message.warning("DRY RUN - Preview of extraction operations:", self.console)
        
        for input_file in input_files:
            input_path = Path(input_file)
            output_name = self._generate_output_name(input_path, output_pattern, compression)
            self.console.print(f"  {input_path.name} -> {output_name}")
        
        self.console.print(f"Topics: {len(topics)} selected")
        self.console.print(f"Compression: {compression}")
    
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
            output = f"{input_path.stem}_extracted_{compression}_{timestamp}.bag"
            
        return output
    
    def display_loading_message(self, file_path: str) -> None:
        """Display loading message for bag files."""
        Message.info(f"Loading bag file: {file_path}", self.console)
    
    def display_cache_status(self, cached_files: int, total_files: int) -> None:
        """Display cache loading status."""
        if cached_files == total_files:
            Message.success(f"All {total_files} file(s, self.console) loaded from cache")
        else:
            Message.info(f"Loaded {cached_files}/{total_files} file(s, self.console) from cache")
    
    def display_extraction_command(self, command_data: Dict[str, Any]) -> None:
        """Display saved extraction command details."""
        self.console.print("\n[bold cyan]Command Summary:[/bold cyan]")
        self.console.print("─" * 50)
        
        summary_data = {
            "Name": command_data.get('name', ''),
            "Output Pattern": command_data.get('output_pattern', ''),
            "Topic Mode": command_data.get('topic_mode', 'include'),
            "Topics Count": len(command_data.get('topics', [])),
            "Compression": command_data.get('compression', 'none')
        }
        
        if command_data.get('start_time') is not None:
            summary_data["Time Range"] = f"{command_data['start_time']:.3f}s - {command_data['end_time']:.3f}s"
            
        self.common_ui.display_summary_table(summary_data)
        
        # Show equivalent CLI command
        topics = command_data.get('topics', [])
        topics_str = ' '.join([f'"{topic}"' for topic in topics])
        cmd = f"rose extract --input \"{{input_bag}}\" --output \"{command_data.get('output_pattern', '')}\" --topics {topics_str}"
        
        if command_data.get('topic_mode') == 'exclude':
            cmd += " --reverse"
            
        if command_data.get('start_time') is not None:
            cmd += f" --start-time {command_data['start_time']:.3f} --end-time {command_data['end_time']:.3f}"
            
        if command_data.get('compression') != "none":
            cmd += f" --compression {command_data['compression']}"
            
        self.console.print(f"\n[dim]Equivalent command:[/dim]")
        self.console.print(f"  {cmd}", style="info")
    
    def display_extract_commands_list(self, commands: List[Dict[str, Any]]) -> None:
        """Display list of saved extraction commands."""
        if not commands:
            Message.info("No saved extract commands found", self.console)
            return
            
        self.console.print(f"\n[bold]Saved Extract Commands ({len(commands)}):[/bold]")
        
        for i, cmd in enumerate(commands, 1):
            name = cmd.get('name', f'command_{i}')
            description = cmd.get('description', 'No description')
            created = cmd.get('created', 'Unknown')
            topics_count = len(cmd.get('topics', []))
            
            Message.primary(f"  {i}. {name} - {description} ({created}, self.console)")
            self.console.print(f"     Topics: {topics_count}, Compression: {cmd.get('compression', 'none')}")
    
    def confirm_overwrite(self, output_file: str) -> bool:
        """Ask for confirmation to overwrite existing file."""
        return self.common_ui.ask_confirmation(
            f"Output file '{output_file}' already exists. Overwrite?",
            default=False
        )
    
    def confirm_operation(self, total_files: int, topics: List[str]) -> bool:
        """Confirm extraction operation."""
        return self.common_ui.ask_confirmation(
            f"Extract {len(topics)} topics from {total_files} file(s)?",
            default=False
        )