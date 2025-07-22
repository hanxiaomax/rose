"""
UI Control - Unified interface for all UI operations including progress bars, result display, and theme management
Provides static methods for consistent UI operations across the application
"""

import asyncio
import time
import json
import csv
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
import logging
from datetime import datetime

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from rich.console import Console, Group
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, 
    BarColumn, TaskProgressColumn, MofNCompleteColumn, TransferSpeedColumn
)
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.markdown import Markdown
from rich.live import Live

from .util import get_logger

_logger = get_logger("ui_control")


# ============================================================================
# Theme System
# ============================================================================

class ThemeMode(Enum):
    """Theme mode options"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


@dataclass
class ThemeColors:
    """Theme color definitions"""
    # Core colors
    background: str = "#ffffff"
    foreground: str = "#000000"
    primary: str = "#4f46e5"
    secondary: str = "#14b8a6"
    accent: str = "#f59e0b"
    
    # Status colors
    success: str = "#22c55e"
    warning: str = "#f59e0b"
    error: str = "#ef4444"
    info: str = "#3b82f6"
    
    # UI colors
    border: str = "#e5e7eb"
    input: str = "#f3f4f6"
    muted: str = "#6b7280"
    
    # Chart colors
    chart_colors: List[str] = field(default_factory=lambda: [
        "#4f46e5", "#14b8a6", "#f59e0b", "#ec4899", "#22c55e"
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'background': self.background,
            'foreground': self.foreground,
            'primary': self.primary,
            'secondary': self.secondary,
            'accent': self.accent,
            'success': self.success,
            'warning': self.warning,
            'error': self.error,
            'info': self.info,
            'border': self.border,
            'input': self.input,
            'muted': self.muted,
            'chart_colors': self.chart_colors
        }


@dataclass
class ThemeTypography:
    """Typography settings"""
    font_family: str = "system-ui, sans-serif"
    font_size_base: str = "14px"
    font_size_small: str = "12px"
    font_size_large: str = "16px"
    font_weight_normal: str = "400"
    font_weight_bold: str = "600"
    line_height: str = "1.5"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {
            'font_family': self.font_family,
            'font_size_base': self.font_size_base,
            'font_size_small': self.font_size_small,
            'font_size_large': self.font_size_large,
            'font_weight_normal': self.font_weight_normal,
            'font_weight_bold': self.font_weight_bold,
            'line_height': self.line_height
        }


@dataclass
class ThemeSpacing:
    """Spacing and layout settings"""
    base_unit: str = "4px"
    small: str = "8px"
    medium: str = "16px"
    large: str = "24px"
    xlarge: str = "32px"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {
            'base_unit': self.base_unit,
            'small': self.small,
            'medium': self.medium,
            'large': self.large,
            'xlarge': self.xlarge
        }


# ============================================================================
# Output Formats and Options
# ============================================================================

class OutputFormat(Enum):
    """Supported output formats"""
    TABLE = "table"
    LIST = "list"
    SUMMARY = "summary"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"
    XML = "xml"
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass
class RenderOptions:
    """Options for result rendering"""
    format: OutputFormat = OutputFormat.TABLE
    verbose: bool = False
    show_fields: bool = False
    show_cache_stats: bool = True
    show_summary: bool = True
    color: bool = True
    width: Optional[int] = None
    title: Optional[str] = None


@dataclass
class ExportOptions:
    """Options for result export"""
    format: OutputFormat = OutputFormat.JSON
    output_file: Optional[Path] = None
    pretty: bool = True
    include_metadata: bool = True
    compress: bool = False


# ============================================================================
# UI Control Enums and Configurations
# ============================================================================

class ProgressType(Enum):
    """Types of progress bars available"""
    ANALYSIS = "analysis"
    EXTRACTION = "extraction"
    TOPIC_LEVEL = "topic_level"
    RESPONSIVE = "responsive"


class UITheme(Enum):
    """UI color themes for different operations"""
    ANALYSIS = "cyan"
    EXTRACTION = "green"
    INSPECTION = "blue"
    CUSTOM = "magenta"


@dataclass
class ProgressConfig:
    """Configuration for progress bars"""
    description: str
    progress_type: ProgressType
    theme: UITheme = UITheme.ANALYSIS
    show_speed: bool = False
    show_count: bool = True
    refresh_rate: int = 10
    topics: Optional[List[str]] = None
    total_items: Optional[int] = None


@dataclass
class DisplayConfig:
    """Configuration for result display"""
    show_summary: bool = True
    show_details: bool = True
    show_cache_stats: bool = True
    show_performance: bool = True
    verbose: bool = False
    full_width: bool = True


# ============================================================================
# Main UI Control Class
# ============================================================================

class UIControl:
    """
    Unified UI Control class for all interface operations
    
    Provides static methods for:
    - Progress bars (analysis, extraction, topic-level, responsive)
    - Result display (inspection, extraction results)
    - Result export (JSON, YAML, CSV, XML, HTML, Markdown)
    - Theme management (colors, typography, spacing)
    - Consistent theming and styling
    - Error and status messages
    """
    
    _default_console = None
    _theme_colors = ThemeColors()
    _theme_typography = ThemeTypography()
    _theme_spacing = ThemeSpacing()
    _current_theme_mode = ThemeMode.LIGHT
    
    @classmethod
    def get_console(cls) -> Console:
        """Get or create default console instance"""
        if cls._default_console is None:
            cls._default_console = Console()
        return cls._default_console
    
    @classmethod
    def set_console(cls, console: Console):
        """Set custom console instance"""
        cls._default_console = console
    
    # ========================================================================
    # Theme Management Methods
    # ========================================================================
    
    @classmethod
    def set_theme_mode(cls, mode: ThemeMode):
        """Set current theme mode"""
        cls._current_theme_mode = mode
        
        if mode == ThemeMode.DARK:
            cls._theme_colors = ThemeColors(
                background="#1a1a1a",
                foreground="#ffffff",
                primary="#818cf8",
                secondary="#2dd4bf",
                accent="#fcd34d",
                success="#4ade80",
                warning="#fcd34d",
                error="#f87171",
                info="#60a5fa",
                border="#374151",
                input="#374151",
                muted="#9ca3af"
            )
        else:
            cls._theme_colors = ThemeColors()  # Default light theme
    
    @classmethod
    def get_theme_colors(cls) -> ThemeColors:
        """Get current theme colors"""
        return cls._theme_colors
    
    @classmethod
    def get_theme_typography(cls) -> ThemeTypography:
        """Get current theme typography"""
        return cls._theme_typography
    
    @classmethod
    def get_theme_spacing(cls) -> ThemeSpacing:
        """Get current theme spacing"""
        return cls._theme_spacing
    
    @classmethod
    def get_inquirer_style(cls) -> Dict[str, str]:
        """Get InquirerPy style configuration"""
        colors = cls._theme_colors
        return {
            "questionmark": f"fg:{colors.accent} bold",
            "question": "bold",
            "answer": f"fg:{colors.primary} bold",
            "pointer": f"fg:{colors.accent} bold",
            "highlighted": f"fg:{colors.accent} bold",
            "selected": f"fg:{colors.success}",
            "separator": f"fg:{colors.muted}",
            "instruction": f"fg:{colors.muted}",
            "text": "",
            "disabled": f"fg:{colors.muted} italic"
        }
    
    # ========================================================================
    # Progress Bar Methods
    # ========================================================================
    
    @classmethod
    @contextmanager
    def progress_bar(cls, config: ProgressConfig, console: Optional[Console] = None):
        """
        Create a progress bar based on configuration
        
        Args:
            config: Progress configuration
            console: Optional console instance
            
        Yields:
            Tuple containing progress components based on progress type
        """
        if console is None:
            console = cls.get_console()
        
        if config.progress_type == ProgressType.ANALYSIS:
            with cls._create_analysis_progress(config, console) as result:
                yield result
        elif config.progress_type == ProgressType.EXTRACTION:
            with cls._create_extraction_progress(config, console) as result:
                yield result
        elif config.progress_type == ProgressType.TOPIC_LEVEL:
            with cls._create_topic_progress(config, console) as result:
                yield result
        elif config.progress_type == ProgressType.RESPONSIVE:
            with cls._create_responsive_progress(config, console) as result:
                yield result
        else:
            raise ValueError(f"Unknown progress type: {config.progress_type}")
    
    @classmethod
    @contextmanager
    def analysis_progress(cls, description: str, theme: UITheme = UITheme.ANALYSIS, 
                         console: Optional[Console] = None):
        """Create analysis progress bar with callback support"""
        config = ProgressConfig(
            description=description,
            progress_type=ProgressType.ANALYSIS,
            theme=theme,
            refresh_rate=10
        )
        
        with cls.progress_bar(config, console) as (progress, task, callback):
            yield progress, task, callback
    
    @classmethod
    @contextmanager
    def extraction_progress(cls, description: str, total: Optional[int] = None,
                           theme: UITheme = UITheme.EXTRACTION, show_speed: bool = True,
                           console: Optional[Console] = None):
        """Create extraction progress bar with callback support"""
        config = ProgressConfig(
            description=description,
            progress_type=ProgressType.EXTRACTION,
            theme=theme,
            show_speed=show_speed,
            total_items=total,
            refresh_rate=10
        )
        
        with cls.progress_bar(config, console) as (progress, task, callback):
            yield progress, task, callback
    
    @classmethod
    @contextmanager
    def topic_progress(cls, description: str, topics: List[str], 
                      theme: UITheme = UITheme.EXTRACTION, console: Optional[Console] = None):
        """Create topic-level progress bar"""
        config = ProgressConfig(
            description=description,
            progress_type=ProgressType.TOPIC_LEVEL,
            theme=theme,
            topics=topics,
            refresh_rate=15
        )
        
        with cls.progress_bar(config, console) as (progress, task, callback):
            yield progress, task, callback
    
    @classmethod
    @contextmanager
    def responsive_progress(cls, description: str, show_speed: bool = False,
                           theme: UITheme = UITheme.ANALYSIS, console: Optional[Console] = None):
        """Create responsive progress bar with advanced features"""
        config = ProgressConfig(
            description=description,
            progress_type=ProgressType.RESPONSIVE,
            theme=theme,
            show_speed=show_speed,
            refresh_rate=10
        )
        
        with cls.progress_bar(config, console) as (progress, task, callback, update_desc):
            yield progress, task, callback, update_desc
    
    @classmethod
    @contextmanager
    def unified_parsing_progress(cls, operation_title: str = "Processing ROS Bag",
                                console: Optional[Console] = None):
        """
        Create a unified two-line parsing progress display for extract and inspect
        
        Line 1: Currently processing topic
        Line 2: Progress bar with format, count, and percentage
        
        Args:
            operation_title: Title for the operation
            console: Optional console instance
            
        Yields:
            Callback function to update progress
        """
        if console is None:
            console = cls.get_console()
        
        # Progress state
        current_topic = "Initializing..."
        current_progress = 0.0
        total_topics = 0
        processed_topics = 0
        current_format = ""
        
        def create_display():
            """Create and display the two-line progress"""
            console.clear()
            
            # Line 1: Current topic being processed
            console.print(f"[bold white]{operation_title}[/bold white]")
            console.print()
            console.print(f"[cyan]📁 Processing:[/cyan] [yellow]{current_topic}[/yellow]")
            
            # Line 2: Progress bar with details
            if total_topics > 0:
                # Calculate progress bar
                progress_percent = (processed_topics / total_topics) * 100
                bar_width = 40
                filled = int((progress_percent / 100) * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)
                
                # Format details
                format_text = f"[dim]Format:[/dim] [green]{current_format}[/green]" if current_format else ""
                count_text = f"[dim]Topics:[/dim] [cyan]{processed_topics}/{total_topics}[/cyan]"
                percent_text = f"[dim]Progress:[/dim] [yellow]{progress_percent:.1f}%[/yellow]"
                
                console.print(f"[blue]{bar}[/blue] {format_text} {count_text} {percent_text}")
            else:
                # Simple progress for unknown total
                spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
                frame_index = int(current_progress / 10) % len(spinner_frames)
                spinner = spinner_frames[frame_index]
                
                format_text = f"[dim]Format:[/dim] [green]{current_format}[/green]" if current_format else ""
                percent_text = f"[dim]Progress:[/dim] [yellow]{current_progress:.1f}%[/yellow]"
                
                console.print(f"[blue]{spinner}[/blue] {format_text} {percent_text}")
            
            console.print()
        
        def update_progress(topic: str = None, progress: float = None, 
                          topics_total: int = None, topics_processed: int = None,
                          bag_format: str = None):
            """Update the progress display"""
            nonlocal current_topic, current_progress, total_topics, processed_topics, current_format
            
            if topic is not None:
                current_topic = topic
            if progress is not None:
                current_progress = progress
            if topics_total is not None:
                total_topics = topics_total
            if topics_processed is not None:
                processed_topics = topics_processed
            if bag_format is not None:
                current_format = bag_format
                
            create_display()
        
        # Show initial display
        update_progress("Starting analysis...", 0.0)
        
        try:
            yield update_progress
        finally:
            # Clear and show completion
            console.clear()
            console.print(f"[bold green]✓ {operation_title} complete[/bold green]")
            console.print()
    
    # ========================================================================
    # Advanced Progress Display Methods
    # ========================================================================
    
    @classmethod
    @contextmanager
    def dynamic_table_progress(cls, topics_info: List[Dict[str, Any]], 
                              title: str = "Topic Processing Progress",
                              console: Optional[Console] = None):
        """
        Create a dynamic table that shows topic processing progress in real-time
        
        Args:
            topics_info: List of topic info dicts with 'name', 'message_count', etc.
            title: Table title
            console: Optional console instance
            
        Yields:
            Callback function to update topic status
        """
        if console is None:
            console = cls.get_console()
        
        # Topic status tracking
        topic_status = {}
        for topic in topics_info:
            topic_name = topic['name']
            topic_status[topic_name] = {
                'status': 'pending',  # pending, processing, completed, skipped
                'processed': 0,
                'total': topic.get('message_count', 0),
                'phase': 'waiting'
            }
        
        # Create initial table
        def create_table():
            table = Table(
                title=title,
                show_header=True,
                header_style="bold magenta",
                expand=True,
                box=None
            )
            
            table.add_column("Status", style="bold", width=8, justify="center")
            table.add_column("Topic", style="cyan", no_wrap=False)
            table.add_column("Progress", width=30)
            table.add_column("Messages", justify="right", width=12)
            table.add_column("Phase", style="yellow", width=15)
            
            return table
        
        def update_table():
            """Update and display the current table"""
            table = create_table()
            
            for topic in topics_info:
                topic_name = topic['name']
                status_info = topic_status[topic_name]
                
                # Status icon and style
                if status_info['status'] == 'pending':
                    status_icon = "⏳"
                    status_style = "dim"
                    row_style = "dim"
                elif status_info['status'] == 'processing':
                    status_icon = "🔄"
                    status_style = "yellow bold"
                    row_style = "yellow"
                elif status_info['status'] == 'completed':
                    status_icon = "✅"
                    status_style = "green bold"
                    row_style = "green"
                elif status_info['status'] == 'skipped':
                    status_icon = "⏭️"
                    status_style = "blue"
                    row_style = "dim blue"
                else:
                    status_icon = "❓"
                    status_style = "red"
                    row_style = "red"
                
                # Progress bar
                total = status_info['total']
                processed = status_info['processed']
                if total > 0:
                    progress_percent = (processed / total) * 100
                    bar_width = 20
                    filled = int((progress_percent / 100) * bar_width)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    progress_text = f"{bar} {progress_percent:.1f}%"
                else:
                    progress_text = "N/A"
                
                # Messages count
                if total > 0:
                    messages_text = f"{processed:,}/{total:,}"
                else:
                    messages_text = "0"
                
                # Phase description
                phase_text = status_info['phase']
                
                # Topic name with styling
                if status_info['status'] == 'processing':
                    topic_display = f"[bold yellow]{topic_name}[/bold yellow]"
                elif status_info['status'] == 'completed':
                    topic_display = f"[green]{topic_name}[/green]"
                elif status_info['status'] == 'skipped':
                    topic_display = f"[dim blue]{topic_name}[/dim blue]"
                else:
                    topic_display = f"[dim]{topic_name}[/dim]"
                
                table.add_row(
                    f"[{status_style}]{status_icon}[/{status_style}]",
                    topic_display,
                    progress_text,
                    messages_text,
                    phase_text
                )
            
            # Clear screen and display table
            console.clear()
            console.print(table)
            console.print()  # Add some spacing
        
        def update_topic_status(topic_name: str, status: str = None, 
                               processed: int = None, phase: str = None):
            """Update topic status and refresh display"""
            if topic_name in topic_status:
                if status is not None:
                    topic_status[topic_name]['status'] = status
                if processed is not None:
                    topic_status[topic_name]['processed'] = processed
                if phase is not None:
                    topic_status[topic_name]['phase'] = phase
                
                # Update display
                update_table()
        
        # Show initial table
        update_table()
        
        try:
            yield update_topic_status
        finally:
            # Show final summary
            completed_count = sum(1 for s in topic_status.values() if s['status'] == 'completed')
            skipped_count = sum(1 for s in topic_status.values() if s['status'] == 'skipped')
            total_count = len(topic_status)
            
            console.print()
            console.print(f"[bold green]✅ Processing Complete![/bold green]")
            console.print(f"Topics: {completed_count} completed, {skipped_count} skipped, {total_count} total")
    
    @classmethod
    @contextmanager  
    def minimal_table_progress(cls, topics_info: List[Dict[str, Any]], 
                              title: str = "Processing Topics",
                              console: Optional[Console] = None):
        """
        Create a minimal table that shows topic processing progress with loading animation
        
        Args:
            topics_info: List of topic info dicts with 'name', 'message_count', etc.
            title: Table title
            console: Optional console instance
            
        Yields:
            Callback function to update topic status
        """
        if console is None:
            console = cls.get_console()
        
        # Topic status tracking
        topic_status = {}
        for topic in topics_info:
            topic_name = topic['name']
            topic_status[topic_name] = {
                'status': 'pending',  # pending, processing, completed
                'processed': 0,
                'total': topic.get('message_count', 0),
            }
        
        # Loading animation frames
        loading_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frame_index = 0
        
        def create_table():
            nonlocal frame_index
            table = Table(
                title=title,
                show_header=True,
                header_style="bold white",
                expand=True,
                box=None,
                padding=(0, 1)
            )
            
            table.add_column("", style="bold", width=3, justify="center")
            table.add_column("Topic", style="white", no_wrap=False)
            table.add_column("Messages", justify="right", width=15)
            table.add_column("Status", width=12)
            
            return table
        
        def update_table():
            """Update and display the current table"""
            nonlocal frame_index
            table = create_table()
            
            for topic in topics_info:
                topic_name = topic['name']
                status_info = topic_status[topic_name]
                
                # Status marker and style
                if status_info['status'] == 'pending':
                    marker = "○"
                    topic_style = "dim white"
                    messages_style = "dim white"
                    status_text = "waiting"
                    status_style = "dim white"
                elif status_info['status'] == 'processing':
                    marker = loading_frames[frame_index % len(loading_frames)]
                    topic_style = "bold yellow"
                    messages_style = "yellow"
                    status_text = "processing"
                    status_style = "yellow"
                elif status_info['status'] == 'completed':
                    marker = "✓"
                    topic_style = "green"
                    messages_style = "green"
                    status_text = "done"
                    status_style = "green"
                else:
                    marker = "○"
                    topic_style = "dim white"
                    messages_style = "dim white"
                    status_text = "unknown"
                    status_style = "dim white"
                
                # Messages count
                total = status_info['total']
                processed = status_info['processed']
                if total > 0:
                    messages_text = f"{processed:,}/{total:,}"
                else:
                    messages_text = "0"
                
                table.add_row(
                    f"[{topic_style}]{marker}[/{topic_style}]",
                    f"[{topic_style}]{topic_name}[/{topic_style}]",
                    f"[{messages_style}]{messages_text}[/{messages_style}]",
                    f"[{status_style}]{status_text}[/{status_style}]"
                )
            
            # Increment frame for loading animation
            frame_index += 1
            
            # Clear screen and display table
            console.clear()
            console.print(table)
            console.print()  # Add some spacing
        
        def update_topic_status(topic_name: str, status: str = None, 
                               processed: int = None):
            """Update topic status and refresh display"""
            if topic_name in topic_status:
                if status is not None:
                    topic_status[topic_name]['status'] = status
                if processed is not None:
                    topic_status[topic_name]['processed'] = processed
                
                # Update display
                update_table()
        
        # Show initial table
        update_table()
        
        try:
            yield update_topic_status
        finally:
            # Clear the screen completely when done - no final summary
            console.clear()
            
            # Show a simple completion message
            completed_count = sum(1 for s in topic_status.values() if s['status'] == 'completed')
            total_count = len(topic_status)
            
            if completed_count == total_count:
                console.print(f"[bold green]✓ Successfully processed all {total_count} topics[/bold green]")
            else:
                console.print(f"[yellow]Processed {completed_count}/{total_count} topics[/yellow]")
    
    @classmethod
    @contextmanager  
    def minimal_extraction_progress(cls, topics_info: List[Dict[str, Any]], 
                                   operation_title: str = "Extracting Topics",
                                   console: Optional[Console] = None):
        """
        Create a minimal extraction progress display with clean table
        
        Args:
            topics_info: List of topic info dicts
            operation_title: Title for the operation
            console: Optional console instance
            
        Yields:
            Callback function to update topic status
        """
        if console is None:
            console = cls.get_console()
        
        with cls.minimal_table_progress(topics_info, operation_title, console) as update_topic:
            
            def update_topic_status(topic_name: str, status: str = None, 
                                   processed: int = None, phase: str = None):
                """Update individual topic status"""
                # Map phase to status if needed
                if phase == "analyzing":
                    status = "processing"
                elif phase == "processing":
                    status = "processing"
                elif phase == "completed":
                    status = "completed"
                
                # Update the table
                update_topic(topic_name, status, processed)
            
            yield update_topic_status
    
    @classmethod
    @contextmanager  
    def minimal_inspection_progress(cls, title: str = "Analyzing ROS Bag",
                                   console: Optional[Console] = None):
        """
        Create a minimal inspection progress display with clean loading animation
        
        Args:
            title: Title for the operation
            console: Optional console instance
            
        Yields:
            Callback function to update progress and description
        """
        if console is None:
            console = cls.get_console()
        
        # Loading animation frames
        loading_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frame_index = 0
        current_description = "Initializing..."
        
        def create_display():
            nonlocal frame_index
            
            # Simple loading display
            spinner = loading_frames[frame_index % len(loading_frames)]
            frame_index += 1
            
            # Clear and show current status
            console.clear()
            console.print(f"[bold white]{title}[/bold white]")
            console.print()
            console.print(f"[yellow]{spinner}[/yellow] {current_description}")
            console.print()
        
        def update_progress(percent: float = None, description: str = None):
            """Update progress display"""
            nonlocal current_description
            
            if description:
                current_description = description
            elif percent is not None:
                if percent < 30:
                    current_description = "Reading bag structure..."
                elif percent < 60:
                    current_description = "Analyzing topics..."
                elif percent < 90:
                    current_description = "Processing metadata..."
                else:
                    current_description = "Finalizing analysis..."
            
            # Update display
            create_display()
        
        # Show initial display
        update_progress(0, "Starting analysis...")
        
        try:
            yield update_progress
        finally:
            # Clear the screen completely when done
            console.clear()
            console.print(f"[bold green]✓ Analysis complete[/bold green]")
    
    @classmethod
    @contextmanager
    def todo_analysis_progress(cls, bag_name: str, show_fields: bool = False, console: Optional[Console] = None):
        """
        Create a TODO-style analysis progress display with panel
        
        Args:
            bag_name: Name of the bag file being analyzed
            show_fields: Whether field extraction is enabled
            console: Optional console instance
            
        Yields:
            Callback function to update progress
        """
        if console is None:
            console = cls.get_console()
        
        from rich.live import Live
        from rich.text import Text
        from rich.panel import Panel
        from rich.align import Align
        
        # Define analysis tasks in TODO list style
        tasks = [
            "Reading bag metadata",
            "Discovering topics",
            "Analyzing message structure", 
            "Counting messages per topic",
            "Calculating topic sizes",
            "Extracting field information" if show_fields else "Computing frequencies",
            "Finalizing analysis"
        ]
        
        # Task status tracking
        task_status = {i: "pending" for i in range(len(tasks))}
        current_task = 0
        
        def create_todo_display():
            """Create indented TODO list display in panel"""
            todo_text = Text()
            
            # Main header
            todo_text.append("⏺ ", style="cyan bold")
            todo_text.append(f"Analyzing {bag_name}\n", style="cyan bold")
            
            for i, task in enumerate(tasks):
                # Indentation and connector
                if i == 0:
                    todo_text.append("  ⎿  ", style="dim")  # First item connector
                else:
                    todo_text.append("     ", style="dim")  # Regular indentation
                
                # Status icon and task
                if task_status[i] == "completed":
                    todo_text.append("✓ ", style="green bold")
                    todo_text.append(f"{task}\n", style="green")
                elif task_status[i] == "in_progress":
                    todo_text.append("⠋ ", style="yellow bold")
                    todo_text.append(f"{task}\n", style="yellow bold")
                else:  # pending
                    todo_text.append("○ ", style="dim")
                    todo_text.append(f"{task}\n", style="dim")
            
            return Panel(
                Align.left(todo_text),
                title=f"[bold cyan]Analysis Progress[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            )
        
        with Live(create_todo_display(), refresh_per_second=10, console=console) as live:
            
            def update_progress(percent: float):
                """Update progress callback"""
                nonlocal current_task
                
                # Determine current task based on progress
                new_task = min(int(percent / 100 * len(tasks)), len(tasks) - 1)
                
                # Mark previous tasks as completed
                for i in range(new_task):
                    if task_status[i] != "completed":
                        task_status[i] = "completed"
                
                # Mark current task as in progress
                if new_task < len(tasks) and task_status[new_task] != "completed":
                    task_status[new_task] = "in_progress"
                    current_task = new_task
                
                # Update display
                live.update(create_todo_display())
            
            try:
                yield update_progress
            finally:
                # Mark all tasks as completed
                for i in range(len(tasks)):
                    task_status[i] = "completed"
                live.update(create_todo_display())
        
        console.print()  # Add spacing after TODO list
    
    @classmethod
    @contextmanager
    def todo_extraction_progress(cls, bag_name: str, operation: str = "Extracting", console: Optional[Console] = None):
        """
        Create a TODO-style extraction progress display with progress bar at bottom
        
        Args:
            bag_name: Name of the bag file being processed
            operation: Operation description (e.g., "Extracting", "Processing")
            console: Optional console instance
            
        Yields:
            Callback function to update progress
        """
        if console is None:
            console = cls.get_console()
        
        from rich.live import Live
        from rich.text import Text
        from rich.panel import Panel
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
        from rich.align import Align
        
        # Define extraction tasks in TODO list style
        tasks = [
            "Analyzing bag structure",
            "Discovering topics",
            "Filtering topic selection",
            "Preparing extraction",
            "Processing messages",
            "Writing output file",
            "Finalizing extraction"
        ]
        
        # Task status tracking
        task_status = {i: "pending" for i in range(len(tasks))}
        current_task = 0
        
        # Progress bar setup
        progress_bar = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
            transient=False
        )
        progress_task = progress_bar.add_task("Processing...", total=100)
        
        # Current status tracking
        current_status = {
            'topic': 'Initializing...',
            'progress': 0.0,
            'topics_processed': 0,
            'topics_total': 0,
            'bag_format': 'ROS Bag'
        }
        
        def create_todo_display():
            """Create TODO list with progress bar at bottom"""
            todo_text = Text()
            
            # Main header
            todo_text.append("⏺ ", style="cyan bold")
            todo_text.append(f"{operation} {bag_name}\n", style="cyan bold")
            
            for i, task in enumerate(tasks):
                # Indentation and connector
                if i == 0:
                    todo_text.append("  ⎿  ", style="dim")  # First item connector
                else:
                    todo_text.append("     ", style="dim")  # Regular indentation
                
                # Status icon and task
                if task_status[i] == "completed":
                    todo_text.append("✓ ", style="green bold")
                    todo_text.append(f"{task}\n", style="green")
                elif task_status[i] == "in_progress":
                    todo_text.append("⠋ ", style="yellow bold")
                    todo_text.append(f"{task}\n", style="yellow bold")
                else:  # pending
                    todo_text.append("○ ", style="dim")
                    todo_text.append(f"{task}\n", style="dim")
            
            # Add current status info
            todo_text.append("\n", style="dim")
            todo_text.append(f"Current: {current_status['topic']}\n", style="cyan")
            
            if current_status['topics_total'] > 0:
                todo_text.append(f"Topics: {current_status['topics_processed']}/{current_status['topics_total']} ", style="blue")
                todo_text.append(f"({current_status['bag_format']})\n", style="dim")
            
            # Combine TODO list and progress bar
            from rich.console import Group
            combined_content = Group(
                Align.left(todo_text),
                "",  # Spacing
                progress_bar
            )
            
            return Panel(
                combined_content,
                title=f"[bold cyan]Extraction Progress[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            )
        
        with Live(create_todo_display(), refresh_per_second=10, console=console) as live:
            
            def update_progress(topic: str = None, progress: float = None,
                              topics_total: int = None, topics_processed: int = None,
                              bag_format: str = None, phase: str = None):
                """Update progress callback"""
                nonlocal current_task
                
                # Update current status
                if topic is not None:
                    current_status['topic'] = topic
                if progress is not None:
                    current_status['progress'] = progress
                    # Update progress bar
                    progress_bar.update(progress_task, completed=progress)
                if topics_total is not None:
                    current_status['topics_total'] = topics_total
                if topics_processed is not None:
                    current_status['topics_processed'] = topics_processed
                if bag_format is not None:
                    current_status['bag_format'] = bag_format
                
                # Determine current task based on progress or phase
                if phase:
                    if phase == "analyzing":
                        new_task = 0
                    elif phase == "filtering":
                        new_task = 2
                    elif phase == "preparing":
                        new_task = 3
                    elif phase == "processing":
                        new_task = 4
                    elif phase == "writing":
                        new_task = 5
                    elif phase == "finalizing":
                        new_task = 6
                    else:
                        new_task = current_task
                elif progress is not None:
                    # Map progress to tasks
                    if progress < 10:
                        new_task = 0  # Analyzing
                    elif progress < 20:
                        new_task = 1  # Discovering
                    elif progress < 30:
                        new_task = 2  # Filtering
                    elif progress < 40:
                        new_task = 3  # Preparing
                    elif progress < 80:
                        new_task = 4  # Processing
                    elif progress < 95:
                        new_task = 5  # Writing
                    else:
                        new_task = 6  # Finalizing
                else:
                    new_task = current_task
                
                # Mark previous tasks as completed
                for i in range(new_task):
                    if task_status[i] != "completed":
                        task_status[i] = "completed"
                
                # Mark current task as in progress
                if new_task < len(tasks) and task_status[new_task] != "completed":
                    task_status[new_task] = "in_progress"
                    current_task = new_task
                
                # Update display
                live.update(create_todo_display())
            
            try:
                yield update_progress
            finally:
                # Mark all tasks as completed
                for i in range(len(tasks)):
                    task_status[i] = "completed"
                progress_bar.update(progress_task, completed=100)
                live.update(create_todo_display())
        
        console.print()  # Add spacing after TODO list
    
    # ========================================================================
    # Result Display Methods
    # ========================================================================
    
    @classmethod
    def display_inspection_result(cls, result: Dict[str, Any], config: Optional[DisplayConfig] = None,
                                 console: Optional[Console] = None):
        """Display inspection results with rich formatting in panel"""
        if console is None:
            console = cls.get_console()
        if config is None:
            config = DisplayConfig()
        
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        # Create content for the results panel
        from rich.console import Group
        content_parts = []
        
        # Show summary if requested
        if config.show_summary:
            summary_content = cls._create_bag_summary_content(bag_info, config)
            content_parts.append(summary_content)
            content_parts.append("")  # Add spacing
        
        # Create topics table
        if config.show_details:
            topics_table = cls._create_topics_table_content(topics, bag_info, config)
            content_parts.append(topics_table)
        
        # Show cache stats if requested
        if config.show_cache_stats and result.get('cache_stats'):
            cache_content = cls._create_cache_stats_content(result['cache_stats'])
            content_parts.append("")  # Add spacing
            content_parts.append(cache_content)
        
        # Combine all content
        combined_content = Group(*content_parts)
        
        # Create results panel
        results_panel = Panel(
            combined_content,
            title=f"[bold green]Analysis Results[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        
        console.print(results_panel)
    
    @classmethod
    def display_extraction_result(cls, result: Dict[str, Any], config: Optional[DisplayConfig] = None,
                                 console: Optional[Console] = None):
        """Display extraction results with rich formatting"""
        if console is None:
            console = cls.get_console()
        if config is None:
            config = DisplayConfig()
        
        cls._display_extraction_summary(result, config, console)
    
    # ========================================================================
    # Result Rendering and Export Methods
    # ========================================================================
    
    @classmethod
    def render_result(cls, result: Dict[str, Any], options: Optional[RenderOptions] = None,
                     console: Optional[Console] = None) -> str:
        """
        Render result in specified format
        
        Args:
            result: Analysis result from BagManager or extraction result
            options: Rendering options
            console: Console instance
            
        Returns:
            Rendered string (for non-console formats)
        """
        if console is None:
            console = cls.get_console()
        if options is None:
            options = RenderOptions()
        
        # Check if this is an extraction result
        if result.get('operation') == 'extract_topics':
            return cls._render_extraction_result(result, options, console)
        
        # Route to appropriate renderer for inspection results
        if options.format == OutputFormat.TABLE:
            return cls._render_table(result, options, console)
        elif options.format == OutputFormat.LIST:
            return cls._render_list(result, options, console)
        elif options.format == OutputFormat.SUMMARY:
            return cls._render_summary(result, options, console)
        elif options.format == OutputFormat.JSON:
            return cls._render_json(result, options, console)
        elif options.format == OutputFormat.YAML:
            return cls._render_yaml(result, options, console)
        elif options.format == OutputFormat.MARKDOWN:
            return cls._render_markdown(result, options, console)
        else:
            _logger.warning(f"Unsupported render format: {options.format}")
            return cls._render_table(result, options, console)  # Fallback to table
    
    @classmethod
    def export_result(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """
        Export result to file in specified format
        
        Args:
            result: Analysis result from BagManager
            options: Export options
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            if options.format == OutputFormat.JSON:
                return cls._export_json(result, options)
            elif options.format == OutputFormat.YAML:
                return cls._export_yaml(result, options)
            elif options.format == OutputFormat.CSV:
                return cls._export_csv(result, options)
            elif options.format == OutputFormat.XML:
                return cls._export_xml(result, options)
            elif options.format == OutputFormat.HTML:
                return cls._export_html(result, options)
            elif options.format == OutputFormat.MARKDOWN:
                return cls._export_markdown(result, options)
            else:
                _logger.error(f"Unsupported export format: {options.format}")
                return False
        except Exception as e:
            _logger.error(f"Export failed: {e}")
            return False
    
    # ========================================================================
    # Status and Message Methods
    # ========================================================================
    
    @classmethod
    def show_success(cls, message: str, console: Optional[Console] = None):
        """Display success message"""
        if console is None:
            console = cls.get_console()
        console.print(f"✓ [green]{message}[/green]")
    
    @classmethod
    def show_error(cls, message: str, console: Optional[Console] = None):
        """Display error message"""
        if console is None:
            console = cls.get_console()
        console.print(f"✗ [red]{message}[/red]")
    
    @classmethod
    def show_warning(cls, message: str, console: Optional[Console] = None):
        """Display warning message"""
        if console is None:
            console = cls.get_console()
        console.print(f"⚠ [yellow]{message}[/yellow]")
    
    @classmethod
    def show_info(cls, message: str, console: Optional[Console] = None):
        """Display info message"""
        if console is None:
            console = cls.get_console()
        console.print(f"ℹ [blue]{message}[/blue]")
    
    # ========================================================================
    # Private Implementation Methods - Progress Bars
    # ========================================================================
    
    @classmethod
    @contextmanager
    def _create_analysis_progress(cls, config: ProgressConfig, console: Console):
        """Create analysis progress bar implementation"""
        theme_color = config.theme.value
        
        with Progress(
            SpinnerColumn("dots", style=theme_color),
            TextColumn(f"[bold {theme_color}]{{task.description}}"),
            BarColumn(bar_width=30, style=theme_color, complete_style=f"bright_{theme_color}"),
            TaskProgressColumn(style=theme_color),
            TimeElapsedColumn(),
            console=console,
            transient=True,
            refresh_per_second=config.refresh_rate
        ) as progress:
            task = progress.add_task(config.description, total=100)
            
            def progress_callback(percent: float):
                """Callback to update progress in real-time"""
                progress.update(task, completed=min(percent, 100))
            
            yield progress, task, progress_callback
    
    @classmethod
    @contextmanager
    def _create_extraction_progress(cls, config: ProgressConfig, console: Console):
        """Create extraction progress bar implementation"""
        theme_color = config.theme.value
        progress_total = config.total_items if config.total_items is not None else 100
        
        columns = [
            SpinnerColumn("dots", style=theme_color),
            TextColumn(f"[bold {theme_color}]{{task.description}}"),
            BarColumn(bar_width=40, style=theme_color, complete_style=f"bright_{theme_color}"),
            TaskProgressColumn(style=theme_color),
            TimeElapsedColumn(),
        ]
        
        if config.show_speed:
            columns.insert(-1, TransferSpeedColumn())
        
        with Progress(
            *columns,
            console=console,
            transient=True,
            refresh_per_second=config.refresh_rate
        ) as progress:
            task = progress.add_task(config.description, total=progress_total)
            
            def progress_callback(percent_or_count: float):
                """Callback to update progress in real-time"""
                if config.total_items is None:
                    # Percentage-based progress
                    progress.update(task, completed=min(percent_or_count, 100))
                else:
                    # Count-based progress
                    progress.update(task, completed=min(percent_or_count, config.total_items))
            
            yield progress, task, progress_callback
    
    @classmethod
    @contextmanager
    def _create_topic_progress(cls, config: ProgressConfig, console: Console):
        """Create topic-level progress bar implementation"""
        theme_color = config.theme.value
        topics = config.topics or []
        
        columns = [
            SpinnerColumn("dots", style=theme_color),
            TextColumn(f"[bold {theme_color}]{{task.description}}"),
            BarColumn(bar_width=40, style=theme_color, complete_style=f"bright_{theme_color}"),
            MofNCompleteColumn(),
            TaskProgressColumn(style=theme_color),
            TimeElapsedColumn(),
        ]
        
        with Progress(
            *columns,
            console=console,
            transient=True,
            refresh_per_second=config.refresh_rate
        ) as progress:
            task = progress.add_task(config.description, total=len(topics))
            
            def topic_progress_callback(
                current_topic_index: int, 
                current_topic: str, 
                messages_processed: int = 0,
                total_messages_in_topic: int = 0,
                phase: str = "processing"
            ):
                """Topic-specific progress callback"""
                # Update progress to current topic
                progress.update(task, completed=current_topic_index)
                
                # Create detailed description
                if phase == "analyzing":
                    desc = f"{config.description} - Analyzing {current_topic}..."
                elif phase == "processing":
                    if total_messages_in_topic > 0:
                        topic_percent = (messages_processed / total_messages_in_topic) * 100
                        desc = f"{config.description} - Processing {current_topic} ({messages_processed:,}/{total_messages_in_topic:,} messages, {topic_percent:.1f}%)"
                    else:
                        desc = f"{config.description} - Processing {current_topic}..."
                elif phase == "completed":
                    desc = f"{config.description} - Completed {current_topic} ({messages_processed:,} messages)"
                else:
                    desc = f"{config.description} - {current_topic}"
                
                progress.update(task, description=desc)
                
                # If topic is completed, advance to next
                if phase == "completed":
                    progress.update(task, completed=current_topic_index + 1)
            
            yield progress, task, topic_progress_callback
    
    @classmethod
    @contextmanager
    def _create_responsive_progress(cls, config: ProgressConfig, console: Console):
        """Create responsive progress bar implementation"""
        theme_color = config.theme.value
        
        columns = [
            SpinnerColumn("dots", style=theme_color),
            TextColumn(f"[bold {theme_color}]{{task.description}}"),
            BarColumn(bar_width=50, style=theme_color, complete_style=f"bright_{theme_color}"),
            MofNCompleteColumn(),
            TaskProgressColumn(style=theme_color),
        ]
        
        if config.show_speed:
            columns.append(TransferSpeedColumn())
        
        columns.append(TimeElapsedColumn())
        
        with Progress(
            *columns,
            console=console,
            transient=True,
            refresh_per_second=config.refresh_rate
        ) as progress:
            task = progress.add_task(config.description, total=100)
            
            def progress_callback(percent: float, current: Optional[int] = None, total_items: Optional[int] = None):
                """Enhanced callback with more detailed progress info"""
                completed = min(percent, 100)
                progress.update(task, completed=completed)
                
                # Update total if provided
                if total_items is not None:
                    progress.update(task, total=total_items)
                    if current is not None:
                        progress.update(task, completed=current)
            
            def update_description(new_description: str):
                """Update the progress description dynamically"""
                progress.update(task, description=new_description)
            
            yield progress, task, progress_callback, update_description
    
    # ========================================================================
    # Private Implementation Methods - Display
    # ========================================================================
    
    @classmethod
    def _display_bag_summary(cls, bag_info: Dict[str, Any], config: DisplayConfig, console: Console):
        """Display bag summary information"""
        if config.verbose:
            console.print("\n[bold]Bag File Summary[/bold]")
            console.print(f"File: {bag_info.get('file_name', 'Unknown')}")
            console.print(f"Path: {bag_info.get('file_path', 'Unknown')}")
            console.print(f"Analysis Time: {bag_info.get('analysis_time', 0):.3f}s")
            console.print(f"Cached: {'Yes' if bag_info.get('cached', False) else 'No'}")
            console.print("-" * 60)
        
        console.print(f"Topics: {bag_info.get('topics_count', 0)}")
        console.print(f"Messages: {bag_info.get('total_messages', 0):,}")
        console.print(f"File Size: {cls._format_size(bag_info.get('file_size', 0))}")
        console.print(f"Duration: {bag_info.get('duration_seconds', 0):.1f}s")
        
        if bag_info.get('total_messages', 0) > 0 and bag_info.get('duration_seconds', 0) > 0:
            avg_rate = bag_info['total_messages'] / bag_info['duration_seconds']
            console.print(f"Avg Rate: {avg_rate:.1f} Hz")
        
        console.print()
    
    @classmethod
    def _display_topics_table(cls, topics: List[Dict[str, Any]], bag_info: Dict[str, Any], 
                             config: DisplayConfig, console: Console):
        """Display topics in table format with size column"""
        table = Table(
            title=f"Topics in {bag_info.get('file_name', 'Unknown')}",
            show_header=True,
            header_style="bold magenta",
            expand=config.full_width
        )
        
        table.add_column("Topic", style="cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="green")
        table.add_column("Size", justify="right", style="yellow")
        table.add_column("Frequency", justify="right", style="blue")
        
        # Add topic rows
        for topic_info in topics:
            frequency_str = f"{topic_info.get('frequency', 0):.1f} Hz"
            
            # Format size
            size_bytes = topic_info.get('size_bytes', 0)
            if size_bytes > 1024 * 1024:
                size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
            elif size_bytes > 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} B"
            
            table.add_row(
                topic_info.get('name', ''),
                f"{topic_info.get('message_count', 0):,}",
                size_str,
                frequency_str
            )
        
        console.print(table)
    
    @classmethod
    def _display_extraction_summary(cls, result: Dict[str, Any], config: DisplayConfig, console: Console):
        """Display extraction result as summary panel"""
        # Create summary text
        summary_text = Text()
        
        # File information
        summary_text.append("File Information:\n", style="bold cyan")
        summary_text.append(f"  Input:  {result.get('input_file', 'Unknown')}\n", style="green")
        summary_text.append(f"  Output: {result.get('output_file', 'Unknown')}\n", style="blue")
        summary_text.append(f"  Compression: {result.get('compression', 'none')}\n")
        
        # Statistics
        stats = result.get('statistics', {})
        bag_info = result.get('bag_info', {})
        
        summary_text.append("\nStatistics:\n", style="bold cyan")
        
        if result.get('success') and not result.get('dry_run'):
            # Show actual results with before → after format
            summary_text.append(f"  Topics: {stats.get('total_topics', 0)} → {stats.get('selected_topics', 0)} ({stats.get('selection_percentage', 0):.1f}%)\n")
            summary_text.append(f"  Messages: {stats.get('total_messages', 0):,} → {stats.get('selected_messages', 0):,} ({stats.get('message_percentage', 0):.1f}%)\n")
            
            # Add file size info if available
            file_stats = result.get('file_stats', {})
            if file_stats:
                input_size = file_stats.get('input_size_bytes', 0) / 1024 / 1024
                output_size = file_stats.get('output_size_bytes', 0) / 1024 / 1024
                size_reduction = file_stats.get('size_reduction_percent', 0)
                summary_text.append(f"  Size: {input_size:.1f} MB → {output_size:.1f} MB ({100 - size_reduction:.1f}%)\n")
        else:
            # Show preview/estimation format
            summary_text.append(f"  Topics: {stats.get('total_topics', 0)} total, {stats.get('selected_topics', 0)} selected ({stats.get('selection_percentage', 0):.1f}%)\n")
            summary_text.append(f"  Messages: {stats.get('total_messages', 0):,} total, {stats.get('selected_messages', 0):,} selected ({stats.get('message_percentage', 0):.1f}%)\n")
        
        duration = bag_info.get('duration_seconds', 0)
        if duration > 0:
            summary_text.append(f"  Duration: {duration:.1f}s\n")
        
        # Performance information
        if result.get('performance') and config.show_performance:
            perf = result['performance']
            summary_text.append("\nPerformance:\n", style="bold cyan")
            summary_text.append(f"  Extraction Time: {perf.get('extraction_time', 0):.3f}s\n")
            if perf.get('messages_per_sec', 0) > 0:
                summary_text.append(f"  Processing Rate: {perf.get('messages_per_sec', 0):.0f} messages/sec\n")
        
        # Validation information
        validation = result.get('validation')
        if validation:
            summary_text.append("\nValidation Results:\n", style="bold cyan")
            
            # Overall validation status
            if validation.get('is_valid', False):
                summary_text.append("  Status: ", style="bold cyan")
                summary_text.append(" PASSED", style="bold green")
                summary_text.append(f" ({validation.get('validation_time', 0):.3f}s)\n")
            else:
                summary_text.append("  Status: ", style="bold cyan")
                summary_text.append(" FAILED", style="bold red")
                summary_text.append(f" ({validation.get('validation_time', 0):.3f}s)\n")
            
            # Validation details
            val_topics = validation.get('topics_count', 0)
            val_messages = validation.get('total_messages', 0)
            val_size = validation.get('file_size_bytes', 0) / 1024 / 1024  # Convert to MB
            
            if val_topics > 0:
                summary_text.append(f"  Verified Topics: {val_topics}\n")
            if val_messages > 0:
                summary_text.append(f"  Verified Messages: {val_messages:,}\n")
            if val_size > 0:
                summary_text.append(f"  Output File Size: {val_size:.1f} MB\n")
            
            # Show errors if any
            errors = validation.get('errors', [])
            if errors:
                summary_text.append("  Errors:\n", style="bold red")
                for error in errors[:3]:  # Show first 3 errors
                    summary_text.append(f"    • {error}\n", style="red")
                if len(errors) > 3:
                    summary_text.append(f"    • ... and {len(errors) - 3} more errors\n", style="red")
            
            # Show warnings if any
            warnings = validation.get('warnings', [])
            if warnings:
                summary_text.append("  Warnings:\n", style="bold yellow")
                for warning in warnings[:2]:  # Show first 2 warnings
                    summary_text.append(f"    • {warning}\n", style="yellow")
                if len(warnings) > 2:
                    summary_text.append(f"    • ... and {len(warnings) - 2} more warnings\n", style="yellow")
        
        # Add topics overview
        summary_text.append("\nTopics Overview:\n", style="bold cyan")
        summary_text.append(f"  Keeping {stats.get('selected_topics', 0)}, Excluding {stats.get('excluded_topics', 0)}\n")
        
        # Add topics table
        summary_text.append("\n")
        
        # Create topics table with full width
        table = Table(show_header=True, header_style="bold magenta", box=None, expand=config.full_width)
        table.add_column("Status", style="bold", width=8, justify="center")
        table.add_column("Topic", style="cyan")
        table.add_column("Count", style="yellow", justify="right", width=10)
        table.add_column("Size Est.", style="green", justify="right", width=12)
        
        topics_to_extract = result.get('topics_to_extract', [])
        
        for topic in result.get('all_topics', []):
            topic_name = topic['name']
            message_count = topic['message_count']
            size_estimate = topic.get('estimated_size_bytes', 0)
            
            should_keep = topic_name in topics_to_extract
            
            if should_keep:
                status = "●"
                status_style = "green"
            else:
                status = "○"
                status_style = "red dim"
                topic_name = f"[dim]{topic_name}[/dim]"
            
            # Format size
            if size_estimate > 1024 * 1024:
                size_str = f"{size_estimate / 1024 / 1024:.1f}MB"
            elif size_estimate > 1024:
                size_str = f"{size_estimate / 1024:.1f}KB"
            else:
                size_str = f"{size_estimate}B"
            
            table.add_row(
                f"[{status_style}]{status}[/{status_style}]",
                topic_name,
                f"{message_count:,}",
                size_str
            )
        
        # Create legend
        legend_text = Text()
        legend_text.append("● = Keep (included in output)  ", style="green")
        legend_text.append("○ = Drop (excluded from output)", style="red dim")
        
        # Create combined content
        combined_content = Group(
            summary_text,
            table,
            "",
            Align.center(legend_text)
        )
        
        # Create panel
        panel_title = "Summary"
        if config.verbose:
            panel_title += " (Verbose)"
        
        panel = Panel(
            combined_content,
            title=panel_title,
            border_style="cyan"
        )
        console.print(panel)
    
    @classmethod
    def _display_cache_stats(cls, cache_stats: Dict[str, Any], console: Console):
        """Display cache performance statistics"""
        if cache_stats.get('total_requests', 0) > 0:
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            total_requests = cache_stats.get('total_requests', 0)
            console.print(f"\nCache Performance: {hit_rate:.1f}% hit rate ({total_requests} requests)")
    
    # ========================================================================
    # Private Implementation Methods - Rendering
    # ========================================================================
    
    @classmethod
    def _render_table(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as rich table"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        # Show summary if requested
        if options.show_summary:
            cls._display_bag_summary(bag_info, DisplayConfig(verbose=options.verbose), console)
        
        # Create topics table
        table = Table(
            title=options.title or f"Topics in {bag_info.get('file_name', 'Unknown')}",
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("Topic", style="cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="green")
        table.add_column("Size", justify="right", style="yellow")
        table.add_column("Frequency", justify="right", style="blue")
        

        # Add topic rows
        for topic_info in topics:
            frequency_str = f"{topic_info.get('frequency', 0):.1f} Hz"
            
            # Format size
            size_bytes = topic_info.get('size_bytes', 0)
            if size_bytes > 1024 * 1024:
                size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
            elif size_bytes > 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} B"
            
            row = [
                topic_info.get('name', ''),
                f"{topic_info.get('message_count', 0):,}",
                size_str,
                frequency_str
            ]
            

            table.add_row(*row)
        
        console.print(table)
        
        # If show_fields is enabled, show detailed field analysis in separate panel
        if options.show_fields:
            field_analysis = result.get('field_analysis', {})
            if field_analysis:
                # Create fields content
                fields_content = cls._create_fields_content(field_analysis, topics)
                
                # Create fields panel
                fields_panel = Panel(
                    fields_content,
                    title=f"[bold magenta]Field Analysis Details[/bold magenta]",
                    border_style="magenta",
                    padding=(1, 2)
                )
                
                console.print()  # Add spacing
                console.print(fields_panel)
        
        return ""  # Console output, no string return
    
    @classmethod
    def _render_list(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as list format"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        if options.show_summary:
            cls._display_bag_summary(bag_info, DisplayConfig(verbose=options.verbose), console)
        
        console.print()
        
        for topic_info in topics:
            name = topic_info.get('name', '')
            count = topic_info.get('message_count', 0)
            frequency = topic_info.get('frequency', 0)
            
            parts = [f"[bold]{name}[/bold]"]
            parts.append(f"[green]{count:,} msgs[/green]")
            
            if frequency > 0:
                parts.append(f"[blue]{frequency:.1f} Hz[/blue]")
            
            console.print(" | ".join(parts))
        
        return ""
    
    @classmethod
    def _render_summary(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as summary only"""
        bag_info = result.get('bag_info', {})
        cls._display_bag_summary(bag_info, DisplayConfig(verbose=options.verbose), console)
        return ""
    
    @classmethod
    def _render_json(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as JSON"""
        json_result = cls._prepare_serializable_result(result)
        json_str = json.dumps(json_result, indent=2 if options.verbose else None, default=str)
        
        if options.color:
            console.print_json(data=json_result)
        else:
            console.print(json_str)
        
        return json_str
    
    @classmethod
    def _render_yaml(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as YAML"""
        if not YAML_AVAILABLE:
            console.print("[red]YAML library not available. Install with: pip install pyyaml[/red]")
            return ""
        
        yaml_result = cls._prepare_serializable_result(result)
        yaml_str = yaml.dump(yaml_result, default_flow_style=False, indent=2)
        
        console.print(f"```yaml\n{yaml_str}```")
        return yaml_str
    
    @classmethod
    def _render_markdown(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as Markdown"""
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        md_content = f"""# Bag Analysis Report

## Summary
- **File**: {bag_info.get('file_name', 'Unknown')}
- **Topics**: {bag_info.get('topics_count', 0)}
- **Messages**: {bag_info.get('total_messages', 0):,}
- **Duration**: {bag_info.get('duration_seconds', 0):.1f}s
- **File Size**: {cls._format_size(bag_info.get('file_size', 0))}

## Topics

| Topic | Message Type | Count | Frequency |
|-------|--------------|-------|-----------|
"""
        
        for topic_info in topics:
            name = topic_info.get('name', '')
            msg_type = topic_info.get('message_type', '')
            count = topic_info.get('message_count', 0)
            frequency = topic_info.get('frequency', 0)
            
            md_content += f"| `{name}` | {msg_type} | {count:,} | {frequency:.1f} Hz |\n"
        
        markdown = Markdown(md_content)
        console.print(markdown)
        
        return md_content
    
    @classmethod
    def _render_extraction_result(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result in specified format"""
        if options.format == OutputFormat.SUMMARY:
            return cls._render_extraction_summary(result, options, console)
        elif options.format == OutputFormat.TABLE:
            return cls._render_extraction_table(result, options, console)
        elif options.format == OutputFormat.LIST:
            return cls._render_extraction_list(result, options, console)
        elif options.format == OutputFormat.JSON:
            return cls._render_json(result, options, console)
        elif options.format == OutputFormat.YAML:
            return cls._render_yaml(result, options, console)
        elif options.format == OutputFormat.MARKDOWN:
            return cls._render_extraction_markdown(result, options, console)
        else:
            return cls._render_extraction_summary(result, options, console)  # Fallback
    
    @classmethod
    def _render_extraction_summary(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result as summary panel"""
        config = DisplayConfig(verbose=options.verbose, full_width=True)
        cls._display_extraction_summary(result, config, console)
        return ""
    
    @classmethod
    def _render_extraction_table(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result as table format"""
        cls._render_extraction_summary(result, options, console)
        return ""
    
    @classmethod
    def _render_extraction_list(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result as list format"""
        stats = result.get('statistics', {})
        
        console.print(f"\n[bold]Extraction Operation[/bold]")
        console.print(f"Topics: {stats.get('selected_topics', 0)}/{stats.get('total_topics', 0)} selected")
        console.print(f"Messages: {stats.get('selected_messages', 0):,}/{stats.get('total_messages', 0):,} selected")
        
        if result.get('topics_to_extract'):
            console.print(f"\n[bold]Selected Topics:[/bold]")
            for topic_name in result['topics_to_extract']:
                console.print(f"  • [green]{topic_name}[/green]")
        
        return ""
    
    @classmethod
    def _render_extraction_markdown(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render extraction result as Markdown"""
        stats = result.get('statistics', {})
        bag_info = result.get('bag_info', {})
        
        md_content = f"""# ROS Bag Extraction Report

## Operation Summary
- **Input File**: {result.get('input_file', 'Unknown')}
- **Output File**: {result.get('output_file', 'Unknown')}
- **Compression**: {result.get('compression', 'none')}
- **Operation**: {'Dry Run' if result.get('dry_run') else 'Extraction'}
- **Status**: {'Success' if result.get('success') else 'Failed'}

## Statistics
- **Topics**: {stats.get('selected_topics', 0)} / {stats.get('total_topics', 0)} ({stats.get('selection_percentage', 0):.1f}%)
- **Messages**: {stats.get('selected_messages', 0):,} / {stats.get('total_messages', 0):,} ({stats.get('message_percentage', 0):.1f}%)
- **Duration**: {bag_info.get('duration_seconds', 0):.1f}s

## Selected Topics

| Topic | Message Count | Status |
|-------|---------------|--------|
"""
        
        topics_to_extract = result.get('topics_to_extract', [])
        for topic in result.get('all_topics', []):
            topic_name = topic['name']
            count = topic['message_count']
            status = "✓ Keep" if topic_name in topics_to_extract else "✗ Drop"
            md_content += f"| `{topic_name}` | {count:,} | {status} |\n"
        
        if result.get('performance'):
            perf = result['performance']
            md_content += f"""
## Performance
- **Extraction Time**: {perf.get('extraction_time', 0):.3f}s
- **Processing Rate**: {perf.get('messages_per_sec', 0):.0f} messages/sec
- **Analysis Time**: {perf.get('analysis_time', 0):.3f}s
- **Total Time**: {perf.get('total_time', 0):.3f}s
"""
        
        markdown = Markdown(md_content)
        console.print(markdown)
        
        return md_content
    
    # ========================================================================
    # Private Implementation Methods - Export
    # ========================================================================
    
    @classmethod
    def _export_json(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as JSON file"""
        if options.output_file is None:
            return False
            
        json_result = cls._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            json.dump(
                json_result, 
                f, 
                indent=2 if options.pretty else None, 
                ensure_ascii=False,
                default=str
            )
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_yaml(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as YAML file"""
        if not YAML_AVAILABLE:
            cls.show_error("YAML library not available")
            return False
            
        if options.output_file is None:
            return False
        
        yaml_result = cls._prepare_serializable_result(result)
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                yaml_result, 
                f, 
                default_flow_style=False, 
                indent=2,
                allow_unicode=True
            )
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_csv(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as CSV file"""
        if options.output_file is None:
            return False
            
        topics = result.get('topics', [])
        
        with open(options.output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['topic', 'message_type', 'message_count', 'frequency']
            if any('field_paths' in topic for topic in topics):
                fieldnames.append('field_count')
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for topic_info in topics:
                row = {
                    'topic': topic_info.get('name', ''),
                    'message_type': topic_info.get('message_type', ''),
                    'message_count': topic_info.get('message_count', 0),
                    'frequency': topic_info.get('frequency', 0)
                }
                
                if 'field_count' in fieldnames:
                    row['field_count'] = len(topic_info.get('field_paths', []))
                
                writer.writerow(row)
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_xml(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as XML file"""
        if options.output_file is None:
            return False
            
        root = ET.Element("bag_analysis")
        
        # Add bag info
        bag_info_elem = ET.SubElement(root, "bag_info")
        for key, value in result.get('bag_info', {}).items():
            elem = ET.SubElement(bag_info_elem, key)
            elem.text = str(value)
        
        # Add topics
        topics_elem = ET.SubElement(root, "topics")
        for topic_info in result.get('topics', []):
            topic_elem = ET.SubElement(topics_elem, "topic")
            for key, value in topic_info.items():
                if key == 'field_paths':
                    fields_elem = ET.SubElement(topic_elem, "field_paths")
                    for field in value:
                        field_elem = ET.SubElement(fields_elem, "field")
                        field_elem.text = field
                else:
                    elem = ET.SubElement(topic_elem, key)
                    elem.text = str(value)
        
        # Write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)  # Pretty print
        tree.write(options.output_file, encoding='utf-8', xml_declaration=True)
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_html(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as HTML file"""
        if options.output_file is None:
            return False
            
        bag_info = result.get('bag_info', {})
        topics = result.get('topics', [])
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROS Bag Analysis Report - {bag_info.get('file_name', 'Unknown')}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 2rem; }}
        .header {{ border-bottom: 2px solid #007acc; padding-bottom: 1rem; margin-bottom: 2rem; }}
        .summary {{ margin-bottom: 2rem; background: #f8f9fa; padding: 1rem; border-radius: 5px; }}
        .topics {{ margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #007acc; color: white; font-weight: 600; }}
        .topic {{ font-family: monospace; }}
        .count {{ text-align: right; }}
        .frequency {{ text-align: right; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ROS Bag Analysis Report</h1>
        <p>{bag_info.get('file_name', 'Unknown')} • Generated at {cls._get_timestamp()}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Topics:</strong> {bag_info.get('topics_count', 0)}</p>
        <p><strong>Messages:</strong> {bag_info.get('total_messages', 0):,}</p>
        <p><strong>File Size:</strong> {cls._format_size(bag_info.get('file_size', 0))}</p>
        <p><strong>Duration:</strong> {bag_info.get('duration_seconds', 0):.1f}s</p>
        <p><strong>Analysis Time:</strong> {bag_info.get('analysis_time', 0):.3f}s</p>
        <p><strong>Cached:</strong> {'Yes' if bag_info.get('cached', False) else 'No'}</p>
    </div>
    
    <div class="topics">
        <h2>Topics ({len(topics)})</h2>
        <table>
            <thead>
                <tr>
                    <th>Topic</th>
                    <th>Message Type</th>
                    <th>Count</th>
                    <th>Frequency</th>
                </tr>
            </thead>
            <tbody>"""
        
        for topic_info in topics:
            html_content += f"""
                <tr>
                    <td class="topic">{topic_info.get('name', '')}</td>
                    <td>{topic_info.get('message_type', '')}</td>
                    <td class="count">{topic_info.get('message_count', 0):,}</td>
                    <td class="frequency">{topic_info.get('frequency', 0):.1f} Hz</td>
                </tr>"""
        
        html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>"""
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    @classmethod
    def _export_markdown(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result as Markdown file"""
        if options.output_file is None:
            return False
            
        md_content = cls._render_markdown(result, RenderOptions(show_fields=True), cls.get_console())
        
        with open(options.output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        cls.show_success(f"Results exported to {options.output_file}")
        return True
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    @classmethod
    def _prepare_serializable_result(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare result for JSON/YAML serialization"""
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {key: make_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, Path):
                return str(obj)
            elif hasattr(obj, '__dict__'):
                return make_serializable(obj.__dict__)
            else:
                return obj
        
        return make_serializable(result)
    
    @classmethod
    def _format_size(cls, size_bytes: int) -> str:
        """Format file size in human readable format"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    @classmethod
    def _get_timestamp(cls) -> str:
        """Get current timestamp for reports"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    @classmethod
    def _create_bag_summary_content(cls, bag_info: Dict[str, Any], config: DisplayConfig):
        """Create bag summary content for panel display"""
        from rich.text import Text
        
        summary_text = Text()
        summary_text.append("Summary\n", style="bold blue")
        
        # File information
        file_name = bag_info.get('file_name', 'Unknown')
        file_size = cls._format_size(bag_info.get('file_size', 0))
        topics_count = bag_info.get('topics_count', 0)
        total_messages = bag_info.get('total_messages', 0)
        duration = bag_info.get('duration_seconds', 0)
        
        summary_text.append(f"  File: {file_name}\n", style="cyan")
        summary_text.append(f"  Topics: {topics_count}\n", style="cyan")
        summary_text.append(f"  Messages: {total_messages:,}\n", style="cyan")
        summary_text.append(f"  File Size: {file_size}\n", style="cyan")
        summary_text.append(f"  Duration: {duration:.1f}s\n", style="cyan")
        
        if duration > 0 and total_messages > 0:
            avg_rate = total_messages / duration
            summary_text.append(f"  Avg Rate: {avg_rate:.1f} Hz\n", style="cyan")
        
        # Analysis information
        analysis_time = bag_info.get('analysis_time', 0)
        cached = bag_info.get('cached', False)
        summary_text.append(f"  Analysis Time: {analysis_time:.3f}s\n", style="dim")
        summary_text.append(f"  Cached: {'Yes' if cached else 'No'}\n", style="dim")
        
        return summary_text
    
    @classmethod
    def _create_topics_table_content(cls, topics: List[Dict[str, Any]], bag_info: Dict[str, Any], config: DisplayConfig):
        """Create topics table content for panel display"""
        table = Table(
            title=f"Topics ({len(topics)})",
            show_header=True,
            header_style="bold magenta",
            expand=config.full_width,
            box=None
        )
        
        table.add_column("Topic", style="cyan", no_wrap=True)
        table.add_column("Count", justify="right", style="green")
        table.add_column("Size", justify="right", style="yellow")
        table.add_column("Frequency", justify="right", style="blue")
        
        # Add topic rows
        for topic_info in topics:
            frequency_str = f"{topic_info.get('frequency', 0):.1f} Hz"
            
            # Format size
            size_bytes = topic_info.get('size_bytes', 0)
            if size_bytes > 1024 * 1024:
                size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
            elif size_bytes > 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} B"
            
            table.add_row(
                topic_info.get('name', ''),
                f"{topic_info.get('message_count', 0):,}",
                size_str,
                frequency_str
            )
        
        return table
    
    @classmethod
    def _create_cache_stats_content(cls, cache_stats: Dict[str, Any]):
        """Create cache stats content for panel display"""
        from rich.text import Text
        
        if cache_stats.get('total_requests', 0) > 0:
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            total_requests = cache_stats.get('total_requests', 0)
            
            cache_text = Text()
            cache_text.append("Cache Performance\n", style="bold blue")
            cache_text.append(f"  Hit Rate: {hit_rate:.1f}% ({total_requests} requests)", style="cyan")
            
            return cache_text
        return Text("")
    
    @classmethod
    def _create_fields_content(cls, field_analysis: Dict[str, Any], topics: List[Dict[str, Any]]):
        """Create fields content for panel display"""
        from rich.text import Text
        from rich.console import Group
        
        content_parts = []
        
        # Show fields for all topics that have field analysis
        if field_analysis:
            for topic, analysis in field_analysis.items():
                field_paths = analysis.get('field_paths', [])
                if field_paths:
                    topic_text = Text()
                    topic_text.append(f"{topic}", style="bold cyan")
                    topic_text.append(f" ({analysis.get('message_type', 'Unknown')})", style="dim")
                    content_parts.append(topic_text)
                    
                    fields_text = Text()
                    # Display fields as simple list with dot notation
                    for field_path in sorted(field_paths):
                        if '.' in field_path:
                            # Nested field - show with yellow color
                            fields_text.append(f"  • {field_path}\n", style="yellow")
                        else:
                            # Top-level field - show with green color
                            fields_text.append(f"  • {field_path}\n", style="green")
                    
                    content_parts.append(fields_text)
                    content_parts.append("")  # Add spacing between topics
        
        # Also check if topics have field_paths directly (fallback)
        elif any('field_paths' in topic for topic in topics):
            for topic_info in topics:
                if 'field_paths' in topic_info and topic_info['field_paths']:
                    topic_name = topic_info.get('name', '')
                    message_type = topic_info.get('message_type', 'Unknown')
                    field_paths = topic_info['field_paths']
                    
                    topic_text = Text()
                    topic_text.append(f"{topic_name}", style="bold cyan")
                    topic_text.append(f" ({message_type})", style="dim")
                    content_parts.append(topic_text)
                    
                    fields_text = Text()
                    # Display fields as simple list with dot notation
                    for field_path in sorted(field_paths):
                        if '.' in field_path:
                            # Nested field - show with yellow color
                            fields_text.append(f"  • {field_path}\n", style="yellow")
                        else:
                            # Top-level field - show with green color
                            fields_text.append(f"  • {field_path}\n", style="green")
                    
                    content_parts.append(fields_text)
                    content_parts.append("")  # Add spacing between topics
        
        # Remove last empty spacing if exists
        if content_parts and content_parts[-1] == "":
            content_parts.pop()
        
        return Group(*content_parts)


# ============================================================================
# Backward Compatibility
# ============================================================================

# Create aliases for backward compatibility
ResultHandler = UIControl
get_theme = UIControl.get_theme_colors
get_current_colors = UIControl.get_theme_colors
get_current_typography = UIControl.get_theme_typography
get_current_spacing = UIControl.get_theme_spacing

# Theme compatibility
class CompatibilityTheme:
    """Compatibility layer for legacy theme usage in CLI modules"""
    
    @property
    def colors(self) -> ThemeColors:
        return UIControl.get_theme_colors()
    
    @property
    def PRIMARY(self) -> str:
        return self.colors.primary
    
    @property
    def SECONDARY(self) -> str:
        return self.colors.secondary
    
    @property
    def ACCENT(self) -> str:
        return self.colors.accent
    
    @property
    def SUCCESS(self) -> str:
        return self.colors.success
    
    @property
    def WARNING(self) -> str:
        return self.colors.warning
    
    @property
    def ERROR(self) -> str:
        return self.colors.error
    
    def get_inquirer_style(self) -> Dict[str, str]:
        """Get InquirerPy style configuration"""
        return UIControl.get_inquirer_style()

# Progress Manager compatibility
class ProgressManager:
    """Backward compatibility wrapper for UIControl progress methods"""
    
    @staticmethod
    @contextmanager
    def analysis_progress(description: str, console: Optional[Console] = None):
        """Create a progress bar for analysis operations with callback support"""
        with UIControl.analysis_progress(description, UITheme.ANALYSIS, console) as result:
            yield result
    
    @staticmethod
    @contextmanager
    def extraction_progress(description: str, total: Optional[int] = None, console: Optional[Console] = None):
        """Create a progress bar for extraction operations with callback support"""
        with UIControl.extraction_progress(description, total, UITheme.EXTRACTION, True, console) as result:
            yield result
    
    @staticmethod
    @contextmanager
    def topic_progress(description: str, topics: List[str], style: str = "green", 
                      console: Optional[Console] = None):
        """Create a progress bar optimized for topic-by-topic processing"""
        theme_map = {
            "green": UITheme.EXTRACTION,
            "cyan": UITheme.ANALYSIS,
            "blue": UITheme.INSPECTION,
            "magenta": UITheme.CUSTOM
        }
        theme = theme_map.get(style, UITheme.EXTRACTION)
        
        with UIControl.topic_progress(description, topics, theme, console) as result:
            yield result
    
    @staticmethod
    @contextmanager
    def responsive_progress(description: str, show_speed: bool = False, 
                           style: str = "green", console: Optional[Console] = None):
        """Create a highly responsive progress bar with advanced features"""
        theme_map = {
            "green": UITheme.EXTRACTION,
            "cyan": UITheme.ANALYSIS,
            "blue": UITheme.INSPECTION,
            "magenta": UITheme.CUSTOM
        }
        theme = theme_map.get(style, UITheme.ANALYSIS)
        
        with UIControl.responsive_progress(description, show_speed, theme, console) as result:
            yield result
    
    @staticmethod
    @contextmanager
    def custom_progress(description: str, total: Optional[int] = None, 
                       spinner_style: str = "cyan", text_style: str = "bold cyan",
                       bar_style: str = "cyan", console: Optional[Console] = None):
        """Create a custom progress bar with callback support"""
        theme_map = {
            "cyan": UITheme.ANALYSIS,
            "green": UITheme.EXTRACTION,
            "blue": UITheme.INSPECTION,
            "magenta": UITheme.CUSTOM
        }
        theme = theme_map.get(bar_style, UITheme.ANALYSIS)
        
        config = ProgressConfig(
            description=description,
            progress_type=ProgressType.RESPONSIVE,
            theme=theme,
            total_items=total,
            refresh_rate=10
        )
        
        with UIControl.progress_bar(config, console) as (progress, task, callback):
            yield progress, task, callback

# Create global instances for backward compatibility
theme = CompatibilityTheme() 