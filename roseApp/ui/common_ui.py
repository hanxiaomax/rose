"""
Common UI utilities and formatters for Rose CLI commands (v2.0).

Simplified Message interface that works with both NDJSON and Prettify modes.
No longer depends on Rich - uses OutputEngine for all output.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class DisplayConfig:
    """Configuration for result display"""
    show_summary: bool = True
    show_details: bool = True
    show_cache_stats: bool = True
    show_performance: bool = True
    verbose: bool = False
    full_width: bool = True


class Message:
    """
    Unified message interface - automatically adapts to output mode.
    
    This class works with the OutputEngine to provide consistent messaging
    across both NDJSON (default) and Prettify modes.
    
    Usage:
        Message.success("Operation complete")
        Message.error("Something went wrong")
        Message.info(f"Found {count} files")
    
    The console parameter is deprecated and ignored.
    """
    
    @staticmethod
    def success(text: str, console: Optional[Any] = None) -> None:
        """Display success message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.SUCCESS)
    
    @staticmethod
    def error(text: str, console: Optional[Any] = None) -> None:
        """Display error message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.ERROR)
    
    @staticmethod
    def warning(text: str, console: Optional[Any] = None) -> None:
        """Display warning message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.WARNING)
    
    @staticmethod
    def info(text: str, console: Optional[Any] = None) -> None:
        """Display info message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.INFO)
    
    @staticmethod
    def primary(text: str, console: Optional[Any] = None) -> None:
        """Display primary message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.PRIMARY)
    
    @staticmethod
    def accent(text: str, console: Optional[Any] = None) -> None:
        """Display accent message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.ACCENT)
    
    @staticmethod
    def muted(text: str, console: Optional[Any] = None) -> None:
        """Display muted message"""
        from roseApp.core.output_engine import get_engine, MessageLevel
        engine = get_engine()
        engine.print_message(text, MessageLevel.MUTED)


class CommonUI:
    """
    Shared UI utilities for consistent display across CLI commands.
    
    Note: Many methods are deprecated in v2.0 as they depend on Rich.
    Use Message class for output instead.
    """
    
    def __init__(self):
        # Console is deprecated, but kept for backward compatibility
        pass
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_mb = size_bytes / 1024 / 1024
        if size_mb >= 1.0:
            return f"{size_mb:.1f} MB"
        else:
            size_kb = size_bytes / 1024
            return f"{size_kb:.1f} KB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    @staticmethod
    def format_compression_ratio(original_size: int, compressed_size: int) -> str:
        """Calculate and format compression ratio."""
        if original_size == 0:
            return "0.0%"
        
        ratio = (1 - compressed_size / original_size) * 100
        return f"{ratio:.1f}%"
    
    def display_file_list(self, files: List[Path], title: str = "Files") -> None:
        """
        Display a list of files with sizes.
        
        Simplified version using Message interface.
        """
        if not files:
            Message.info("No files found.")
            return
        
        Message.info(f"{title} ({len(files)}):")
        for file in files:
            if file.exists():
                size = self.format_file_size(file.stat().st_size)
                Message.accent(f"  • {file} ({size})")
            else:
                Message.warning(f"  • {file} (not found)")
    
    def display_summary_table(self, data: Dict[str, Any], title: str = "Summary") -> None:
        """
        Display key-value data in simple format.
        
        v2.0: Simplified to text output, no Rich tables.
        """
        Message.primary(f"{title}:")
        for key, value in data.items():
            Message.info(f"  {key}: {value}")
    
    def display_topics_list(self, topics: List[str], message_types: Optional[Dict[str, str]] = None) -> None:
        """Display topics in a clean list format."""
        if not topics:
            Message.info("No topics found.")
            return
        
        Message.info(f"Topics ({len(topics)}):")
        for topic in sorted(topics):
            if message_types and topic in message_types:
                Message.accent(f"  • {topic} ({message_types[topic]})")
            else:
                Message.accent(f"  • {topic}")


class ProgressUI:
    """
    Progress display utilities (v2.0 - simplified).
    
    Note: Complex progress bars are deprecated.
    Use engine.emit_progress() for progress updates.
    """
    
    def __init__(self, console: Optional[Any] = None):
        pass
    
    def show_processing_summary(self, total_files: int, workers: int, operation: str) -> None:
        """Display processing summary."""
        Message.info(f"Processing {total_files} file(s) with {workers} worker(s) ({operation})...")
    
    def show_batch_results(self, success_count: int, fail_count: int, total_time: float) -> None:
        """Display batch processing results."""
        Message.primary("Processing Summary:")
        
        if success_count > 0:
            Message.success(f"  Successful: {success_count}")
        if fail_count > 0:
            Message.error(f"  Failed: {fail_count}")
        
        Message.info(f"  Total Time: {total_time:.2f}s")


class TableUI:
    """
    Table display utilities (v2.0 - simplified).
    
    Note: Rich tables are deprecated. Use simple text lists instead.
    """
    
    def __init__(self, console: Optional[Any] = None):
        pass
    
    def create_topics_list(self, topics_data: List[Dict[str, Any]], verbose: bool = False) -> None:
        """Display topics as a list."""
        if not topics_data:
            return
            
        Message.primary("Topics:")
        
        for i, topic in enumerate(topics_data, 1):
            name = topic.get('name', '')
            msg_type = topic.get('message_type', '')
            
            if verbose:
                messages = topic.get('message_count', 0)
                frequency = topic.get('frequency', 0)
                size = CommonUI.format_file_size(topic.get('size_bytes', 0))
                Message.info(
                    f"  {i:2d}. {name} ({msg_type}) - {messages} messages @ {frequency:.1f} Hz ({size})"
                )
            else:
                Message.accent(f"  {i:2d}. {name} ({msg_type})")
    
    def display_compression_summary_list(self, results: List[Dict[str, Any]]) -> None:
        """Display compression results as a list."""
        if not results:
            return
            
        Message.primary("Compression Results:")
        
        total_original = 0
        total_compressed = 0
        
        for i, result in enumerate(results, 1):
            if result.get('success'):
                original_size = Path(result['input_file']).stat().st_size
                compressed_size = Path(result['output_file']).stat().st_size
                
                filename = Path(result['input_file']).name
                original_str = CommonUI.format_file_size(original_size)
                compressed_str = CommonUI.format_file_size(compressed_size)
                reduction = CommonUI.format_compression_ratio(original_size, compressed_size)
                
                Message.success(
                    f"  {i:2d}. {filename}: {original_str} → {compressed_str} ({reduction})"
                )
                
                total_original += original_size
                total_compressed += compressed_size
        
        if len(results) > 1:
            total_original_str = CommonUI.format_file_size(total_original)
            total_compressed_str = CommonUI.format_file_size(total_compressed)
            total_reduction = CommonUI.format_compression_ratio(total_original, total_compressed)
            
            Message.success(
                f"  TOTAL: {total_original_str} → {total_compressed_str} ({total_reduction})"
            )
