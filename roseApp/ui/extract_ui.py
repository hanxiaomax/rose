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
from .interactive_common import InteractiveCommon, BagLoader, TopicSelector, OutputManager
from .command_builder import CommandBuilder, InteractiveWizard


class ExtractUI:
    """UI components specifically for the extract command."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.common_ui = CommonUI()
        self.progress_ui = ProgressUI()
        self.table_ui = TableUI()
        self.interactive = InteractiveCommon(self.console)
        self.bag_loader = BagLoader(self.console)
        self.topic_selector = TopicSelector(self.console)
        self.output_manager = OutputManager(self.console)
        self.wizard = InteractiveWizard("extract", self.console)
    
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
        # Handle both old format (success/input_file) and new format (status/path)
        successful = []
        failed = []
        
        for r in results:
            # New format from extract.py
            if 'status' in r:
                if r['status'] == 'extracted':
                    successful.append(r)
                else:
                    failed.append(r)
            # Old format (fallback)
            elif r.get('success', False):
                successful.append(r)
            else:
                failed.append(r)
        
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
            
        self.table_ui.display_compression_summary_list(results)
    
    def display_failed_files(self, failed_results: List[Dict[str, Any]]) -> None:
        """Display failed extraction files."""
        if not failed_results:
            return
            
        Message.error(f"Failed to extract {len(failed_results)} file(s):")
        for result in failed_results:
            # Handle both old and new result formats
            if 'path' in result:
                # New format from extract.py
                file_path = result.get('path', '')
                error_msg = result.get('message', 'Unknown error')
            else:
                # Old format (fallback)
                file_path = result.get('input_file', '')
                error_msg = result.get('error', 'Unknown error')
            
            # Extract filename from path
            if file_path:
                file_name = Path(file_path).name
            else:
                file_name = 'Unknown file'
                
            self.console.print(f"  • {file_name}: {error_msg}")
    
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
            "Topics Count": len(command_data.get('topics')),
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
            topics_count = len(cmd.get('topics'))
            
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
    
    def run_interactive(self) -> None:
        """Run interactive extract command wizard - builds and executes extract commands"""
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
        import os
        import time
        import subprocess
        import sys
        
        self.wizard.show_welcome("Extract specific topics from ROS bag files")
        
        while True:
            # Step 1: Select input bags
            input_source = inquirer.select(
                message="Select input source:",
                choices=[
                    Choice(value="file", name="Single bag file"),
                    Choice(value="directory", name="Directory with bag files"),
                    Choice(value="pattern", name="File pattern (glob/regex)"),
                    Choice(value="exit", name="Exit")
                ]
            ).execute()
            
            if input_source == "exit" or input_source is None:
                break
            
            # Get bag files based on selection
            bag_files = []
            
            if input_source == "file":
                bag_file = self.interactive.ask_for_bag_file("Select bag file to extract from:")
                if bag_file:
                    bag_files = [bag_file]
            
            elif input_source == "directory":
                directory = inquirer.filepath(
                    message="Select directory containing bag files:",
                    validate=lambda x: os.path.isdir(x) or "Must be a valid directory"
                ).execute()
                
                if directory:
                    selected_files = self.interactive.ask_for_bag_files_from_directory(directory)
                    if selected_files:
                        bag_files = selected_files
            
            elif input_source == "pattern":
                pattern = inquirer.text(
                    message="Enter file pattern (supports glob and regex):",
                    default="*.bag",
                    validate=lambda x: len(x.strip()) > 0 or "Pattern cannot be empty"
                ).execute()
                
                if pattern:
                    from ..cli.extract import find_bag_files
                    bag_files = find_bag_files([pattern])
                    
                    if not bag_files:
                        Message.warning("No files found matching pattern", self.console)
                        continue
                    
                    # Show found files and ask for confirmation
                    Message.info(f"Found {len(bag_files)} bag file(s):", self.console)
                    for bag_file in bag_files:
                        self.console.print(f"  • {bag_file}")
                    
                    if not self.interactive.confirm_operation("Use these files?"):
                        continue
            
            if not bag_files:
                continue
            
            # Step 2: Load bag files and get topics
            self.console.print("\nLoading bag files to analyze topics...")
            all_topics = set()
            
            try:
                with self.interactive.create_loading_context("Loading bag files...") as progress:
                    for i, bag_file in enumerate(bag_files):
                        progress.console.print(f"Loading {i+1}/{len(bag_files)}: {os.path.basename(bag_file)}")
                        topics, _, _ = self.bag_loader.load_bag_sync(bag_file)
                        all_topics.update(topics)
                
                if not all_topics:
                    Message.error("No topics found in selected bag files", self.console)
                    continue
                
                Message.success(f"Found {len(all_topics)} unique topics across {len(bag_files)} bag files", self.console)
                
            except Exception as e:
                Message.error(f"Error loading bag files: {str(e)}", self.console)
                continue
            
            # Step 3: Topic selection method
            filter_method = self.interactive.ask_for_filter_method()
            if not filter_method:
                continue
            
            selected_topics = []
            reverse_selection = False
            
            if filter_method == "whitelist":
                selected_topics = self.interactive.ask_for_topics_from_whitelist()
                if not selected_topics:
                    continue
            
            elif filter_method == "manual":
                # Ask for selection mode (include/exclude)
                selection_mode = inquirer.select(
                    message="Topic selection mode:",
                    choices=[
                        Choice(value="include", name="Include selected topics (default)"),
                        Choice(value="exclude", name="Exclude selected topics")
                    ],
                    default="include"
                ).execute()
                
                reverse_selection = (selection_mode == "exclude")
                
                # Show mode to user
                mode_text = "EXCLUDE" if reverse_selection else "INCLUDE"
                self.console.print(f"\nSelect topics to {mode_text}:", style=get_color("info"))
                
                selected_topics = self.topic_selector.select_topics_interactive(
                    list(all_topics), bag_files[0] if bag_files else None
                )
                
                if not selected_topics:
                    continue
            
            # Step 4: Output configuration
            self.console.print("\nOutput Configuration:")
            
            # Output pattern
            default_pattern = "{input}_extracted_{timestamp}.bag"
            output_pattern = inquirer.text(
                message="Enter output pattern (use {input} for input filename, {timestamp} for timestamp):",
                default=default_pattern,
                validate=lambda x: len(x.strip()) > 0 or "Pattern cannot be empty"
            ).execute()
            
            if not output_pattern:
                continue
            
            # Compression
            compression = self.interactive.ask_for_compression_type()
            if not compression:
                compression = "none"
            
            # Step 5: Processing options
            self.console.print("\nProcessing Options:")
            
            # Workers
            workers = self.interactive.ask_for_workers_count()
            
            # Verbose
            verbose = inquirer.confirm(
                message="Show detailed extraction information?",
                default=True
            ).execute()
            
            # Dry run
            dry_run = inquirer.confirm(
                message="Dry run (preview only, don't actually extract)?",
                default=False
            ).execute()
            
            # Step 6: Show summary and confirm
            summary = {
                "Input files": len(bag_files),
                "Topics": f"{len(selected_topics)} ({'excluded' if reverse_selection else 'included'})",
                "Output pattern": output_pattern,
                "Compression": compression,
                "Workers": workers or "Default",
                "Dry run": "Yes" if dry_run else "No"
            }
            self.wizard.show_summary(summary)
            
            if not self.interactive.confirm_operation("Start extraction?"):
                continue
            
            # Step 7: Build and execute command
            options = {
                "output": output_pattern,
                "workers": workers,
                "reverse": reverse_selection,
                "compression": compression,
                "dry_run": dry_run,
                "verbose": verbose
            }
            
            success = self.wizard.command_builder.build_and_execute_command(
                "extract", bag_files, options, selected_topics
            )
            
            # Ask if user wants to continue
            if not inquirer.confirm(
                message="Extract more files?",
                default=False
            ).execute():
                break
        
        self.wizard.show_exit_message()