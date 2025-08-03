"""
UI Control - Unified interface for all UI operations including progress bars, result display, and theme management
Provides static methods for consistent UI operations across the application
"""

from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from rich.console import Console, Group

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.live import Live

from .util import get_logger
from .theme_manager import ThemeManager, ThemeMode, ThemeColors, ThemeTypography, ThemeSpacing
from .export_manager import ExportManager, OutputFormat, RenderOptions, ExportOptions
from .model import TopicInfo

_logger = get_logger("ui_control")



@dataclass
class DisplayConfig:
    """Configuration for result display"""
    show_summary: bool = True
    show_details: bool = True
    show_cache_stats: bool = True
    show_performance: bool = True
    verbose: bool = False
    full_width: bool = True


@dataclass
class Message:
    """Standard message component with consistent styling"""
    text: str
    message_type: str = "info"  # info, success, warning, error
    
    def render(self, console: Optional[Console] = None) -> None:
        """Render the message to console"""
        if console is None:
            console = UIControl.get_console()
        color = UIControl.get_color(self.message_type)
        console.print(f"[{color}]{self.text}[/{color}]")


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
    # Theme Management Methods (Delegated to ThemeManager)
    # ========================================================================
    
    @classmethod
    def set_theme_mode(cls, mode: ThemeMode):
        """Set current theme mode"""
        ThemeManager.set_theme_mode(mode)
    
    @classmethod
    def get_theme_colors(cls) -> ThemeColors:
        """Get current theme colors"""
        return ThemeManager.get_theme_colors()
    
    @classmethod
    def get_theme_typography(cls) -> ThemeTypography:
        """Get current theme typography"""
        return ThemeManager.get_theme_typography()
    
    @classmethod
    def get_theme_spacing(cls) -> ThemeSpacing:
        """Get current theme spacing"""
        return ThemeManager.get_theme_spacing()
    
    @classmethod
    def get_inquirer_style(cls) -> Dict[str, str]:
        """Get InquirerPy style configuration"""
        return ThemeManager.get_inquirer_style()
    
    @classmethod
    def get_color(cls, color_name: str, modifier: str = "") -> str:
        """Get unified color for any component"""
        return ThemeManager.get_color(color_name, modifier)
    

    @classmethod
    def style_text(cls, text: str, color_name: str, modifier: str = "") -> str:
        """Apply unified styling to text"""
        return ThemeManager.style_text(text, color_name, modifier)
    
    @classmethod
    def get_component_color(cls, component_type: str, color_name: str, modifier: str = "") -> str:
        """Get color for specific component type"""
        return ThemeManager.get_component_color(component_type, color_name, modifier)
    
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
            topics_table = cls.create_topics_table_content(topics, config)
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
            title=f"[{cls.get_color('success', 'bold')}]Analysis Results[/{cls.get_color('success', 'bold')}]",
            border_style=cls.get_color('success'),
            padding=(1, 2)
        )
        
        console.print(results_panel)



    @classmethod
    def render_result(cls, result: Dict[str, Any], options: Optional[RenderOptions] = None,
                     console: Optional[Console] = None) -> str:
        """Render result in specified format"""
        if console is None:
            console = cls.get_console()
        
        # Check if this is a table/list/summary format that needs UIControl rendering
        if options and options.format in [OutputFormat.TABLE, OutputFormat.LIST, OutputFormat.SUMMARY]:
            # Handle these formats locally for UI display
            if options.format == OutputFormat.TABLE:
                return cls._render_table(result, options, console)
            elif options.format == OutputFormat.LIST:
                return cls._render_list(result, options, console)
            elif options.format == OutputFormat.SUMMARY:
                return cls._render_summary(result, options, console)
        
        # Delegate other formats to ExportManager
        return ExportManager.render_result(result, options, console)
    
    @classmethod
    def export_result(cls, result: Dict[str, Any], options: ExportOptions) -> bool:
        """Export result to file in specified format"""
        success = ExportManager.export_result(result, options)
        if success:
            cls.show_success(f"Results exported to {options.output_file}")
        else:
            cls.show_error("Export failed")
        return success
    
    # ========================================================================
    # Status and Message Methods
    # ========================================================================
    
    @classmethod
    def show_success(cls, message: str, console: Optional[Console] = None):
        """Display success message"""
        if console is None:
            console = cls.get_console()
        console.print(f"✓ [{cls.get_color('success')}]{message}[/{cls.get_color('success')}]")
    
    @classmethod
    def show_error(cls, message: str, console: Optional[Console] = None):
        """Display error message"""
        if console is None:
            console = cls.get_console()
        console.print(f"✗ [{cls.get_color('error')}]{message}[/{cls.get_color('error')}]")
    
    @classmethod
    def show_warning(cls, message: str, console: Optional[Console] = None):
        """Display warning message"""
        if console is None:
            console = cls.get_console()
        console.print(f"⚠ [{cls.get_color('warning')}]{message}[/{cls.get_color('warning')}]")
    
    @classmethod
    def show_info(cls, message: str, console: Optional[Console] = None):
        """Display info message"""
        if console is None:
            console = cls.get_console()
        console.print(f"ℹ [{cls.get_color('info')}]{message}[/{cls.get_color('info')}]")
    
    @classmethod
    def show_operation_cancelled(cls, console: Optional[Console] = None):
        """Display operation cancelled message"""
        if console is None:
            console = cls.get_console()
        console.print("Operation cancelled.", style=cls.get_color('muted'))
    
    @classmethod
    def show_operation_status(cls, message: str, console: Optional[Console] = None):
        """Display general operation status (unified for analyzing, processing, etc.)"""
        if console is None:
            console = cls.get_console()
        console.print(message, style=cls.get_color('primary', 'dim'))
    
    @classmethod
    def show_operation_description(cls, operation_desc: str, items: List[str], item_type: str = "topics", console: Optional[Console] = None):
        """Display operation description and items (unified for extraction, inspection, etc.)"""
        if console is None:
            console = cls.get_console()
        console.print(f"\n{operation_desc}", style=cls.get_color('primary', 'bold'))
        console.print(f"{item_type.capitalize()} to process: {', '.join(items)}", style=cls.get_color('foreground'))
    
    @classmethod
    def show_dry_run_preview(cls, items_count: int, items: List[str], output_path: Path, operation: str = "extract", console: Optional[Console] = None):
        """Display dry run preview (unified for different operations)"""
        if console is None:
            console = cls.get_console()
        console.print(f"\nDry run - would {operation} {items_count} items:", style=cls.get_color('warning', 'bold'))
        for item in items:
            console.print(f"  • {item}", style=cls.get_color('foreground'))
        console.print(f"\nOutput would be saved to: {output_path}", style=cls.get_color('muted', 'dim'))
        console.print(f"Dry run completed - no files were created", style=cls.get_color('warning', 'bold'))
    
    @classmethod
    def show_operation_success(cls, operation: str, items_count: int, output_path: Path, processing_time: float, console: Optional[Console] = None):
        """Display operation success message (unified for extraction, inspection, etc.)"""
        if console is None:
            console = cls.get_console()
        console.print(f"\n✓ Successfully {operation} {items_count} items", style=cls.get_color('success', 'bold'))
        console.print(f"Output saved to: {output_path}", style=cls.get_color('muted', 'dim'))
        console.print(f"Operation completed in {processing_time:.2f}s", style=cls.get_color('muted', 'dim'))
    
    @classmethod
    def show_operation_details(cls, operation: str, input_path: Path, output_path: Path, 
                              processing_time: float, additional_info: Dict[str, Any] = None, console: Optional[Console] = None):
        """Display detailed operation information (unified for extraction, inspection, etc.)"""
        if console is None:
            console = cls.get_console()
        
        console.print(f"\n{operation.capitalize()} Details:", style=cls.get_color('primary', 'bold'))
        console.print(f"  Input file: {input_path}", style=cls.get_color('foreground'))
        console.print(f"  Output file: {output_path}", style=cls.get_color('foreground'))
        console.print(f"  Processing time: {processing_time:.2f}s", style=cls.get_color('foreground'))
        
        if additional_info:
            for key, value in additional_info.items():
                console.print(f"  {key}: {value}", style=cls.get_color('foreground'))
    
    @classmethod
    def show_items_selection_summary(cls, total_items: int, selected_items: int, excluded_items: int = None, 
                                    item_type: str = "topics", console: Optional[Console] = None):
        """Display item selection summary (unified for topics, files, etc.)"""
        if console is None:
            console = cls.get_console()
        
        console.print(f"\n{item_type.capitalize()} Selection:", style=cls.get_color('primary', 'bold'))
        console.print(f"  Total {item_type} available: {total_items}", style=cls.get_color('foreground'))
        console.print(f"  {item_type.capitalize()} selected: {selected_items}", style=cls.get_color('foreground'))
        
        if excluded_items is not None:
            console.print(f"  {item_type.capitalize()} excluded: {excluded_items}", style=cls.get_color('foreground'))
    
    @classmethod
    def show_items_lists(cls, kept_items: List[str], excluded_items: List[str] = None, 
                        reverse_mode: bool = False, item_type: str = "topics", console: Optional[Console] = None):
        """Display kept and excluded item lists (unified for topics, files, etc.)"""
        if console is None:
            console = cls.get_console()
        
        if reverse_mode and excluded_items:
            console.print(f"\nExcluded {item_type.capitalize()} (matching patterns):", style=cls.get_color('primary', 'bold'))
            for item in excluded_items:
                console.print(f"    ✗ {item}", style=cls.get_color('error'))
            
            console.print(f"\nKept {item_type.capitalize()} (remaining):", style=cls.get_color('primary', 'bold'))
            for item in kept_items:
                console.print(f"    ✓ {item}", style=cls.get_color('success'))
        else:
            console.print(f"\nKept {item_type.capitalize()} (matching patterns):", style=cls.get_color('primary', 'bold'))
            for item in kept_items:
                console.print(f"    ✓ {item}", style=cls.get_color('success'))
            
            if excluded_items:
                console.print(f"\nExcluded {item_type.capitalize()} (not matching):", style=cls.get_color('primary', 'bold'))
                for item in excluded_items:
                    console.print(f"    ○ {item}", style=cls.get_color('muted', 'dim'))
    
    @classmethod
    def show_pattern_matching_summary(cls, patterns: List[str], reverse_mode: bool, all_items: List[str], 
                                     item_type: str = "topics", console: Optional[Console] = None):
        """Display pattern matching summary (unified for topics, files, etc.)"""
        if console is None:
            console = cls.get_console()
        
        console.print(f"\nPattern Matching:", style=cls.get_color('primary', 'bold'))
        console.print(f"  Requested patterns: {', '.join(patterns)}", style=cls.get_color('foreground'))
        console.print(f"  Matching mode: {'Exclude matching' if reverse_mode else 'Include matching'}", style=cls.get_color('foreground'))
        
        # Show which patterns matched which items
        for pattern in patterns:
            # Use more precise matching logic similar to _filter_topics
            exact_matches = [item for item in all_items if item == pattern]
            if exact_matches:
                matched_items = exact_matches
            else:
                # Fall back to fuzzy matching
                matched_items = [item for item in all_items if pattern.lower() in item.lower()]
            
            if matched_items:
                console.print(f"  Pattern '{pattern}' matched: {', '.join(matched_items)}", style=cls.get_color('foreground'))
            else:
                console.print(f"  Pattern '{pattern}' matched: none", style=cls.get_color('muted', 'dim'))
    
    @classmethod
    def show_no_matching_items(cls, patterns: List[str], available_items: List[str], reverse_mode: bool = False, 
                              item_type: str = "topics", console: Optional[Console] = None):
        """Display no matching items warning (unified for topics, files, etc.)"""
        if console is None:
            console = cls.get_console()
        
        if reverse_mode:
            cls.show_warning(f"All {item_type} would be excluded. No {item_type} to process.", console)
        else:
            cls.show_warning(f"No matching {item_type} found.", console)
            console.print(f"Available {item_type}: {', '.join(available_items[:5])}{'...' if len(available_items) > 5 else ''}", style=cls.get_color('foreground'))
            console.print(f"Requested patterns: {', '.join(patterns)}", style=cls.get_color('foreground'))
    
    @classmethod
    def show_unsupported_format_error(cls, format_name: str, supported_formats: List[str], console: Optional[Console] = None):
        """Display unsupported output format error"""
        if console is None:
            console = cls.get_console()
        cls.show_error(f"Unsupported output format '{format_name}'. Supported: {', '.join(supported_formats)}")
    
    @classmethod
    def show_export_failed_error(cls, console: Optional[Console] = None):
        """Display export failed error"""
        if console is None:
            console = cls.get_console()
        cls.show_error("Export failed")
    
    @classmethod
    def show_fields_panel(cls, field_analysis: Dict[str, Any], topics: List[Dict[str, Any]], console: Optional[Console] = None):
        """Display field analysis panel for inspect command"""
        if console is None:
            console = cls.get_console()
        
        # Create fields content using existing method
        fields_content = cls._create_fields_content(field_analysis, topics)
        
        # Create fields panel with themed styling
        from rich.panel import Panel
        from rich.text import Text
        
        # Create styled title
        title = Text("Field Analysis Details", style=cls.get_color('accent', 'bold'))
        
        fields_panel = Panel(
            fields_content,
            title=title,
            border_style=cls.get_color('accent'),
            padding=(1, 2)
        )
        
        console.print()  # Add spacing
        console.print(fields_panel)
    
    # ========================================================================
    # Private Implementation Methods - Display
    # ========================================================================
    
    @classmethod
    def _display_bag_summary(cls, bag_info: Dict[str, Any], config: DisplayConfig, console: Console):
        """Display bag summary information"""
        if config.verbose:
            console.print(f"\n[{cls.get_color('primary', 'bold')}]Bag File Summary[/{cls.get_color('primary', 'bold')}]")
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
            header_style=cls.get_color('accent', 'bold'),
            expand=config.full_width
        )
        
        table.add_column("Topic", style=cls.get_color('info'), no_wrap=True)
        table.add_column("Count", justify="right", style=cls.get_color('success'))
        table.add_column("Size", justify="right", style=cls.get_color('accent'))
        table.add_column("Frequency", justify="right", style=cls.get_color('primary'))
        
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
        summary_text.append("File Information:\n", style=cls.get_color('info', 'bold'))
        summary_text.append(f"  Input:  {result.get('input_file', 'Unknown')}\n", style=cls.get_color('success'))
        summary_text.append(f"  Output: {result.get('output_file', 'Unknown')}\n", style=cls.get_color('primary'))
        summary_text.append(f"  Compression: {result.get('compression', 'none')}\n")
        
        # Statistics
        stats = result.get('statistics', {})
        bag_info = result.get('bag_info', {})
        
        summary_text.append("\nStatistics:\n", style=cls.get_color('info', 'bold'))
        
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
            summary_text.append("\nPerformance:\n", style=cls.get_color('info', 'bold'))
            summary_text.append(f"  Extraction Time: {perf.get('extraction_time', 0):.3f}s\n")
            if perf.get('messages_per_sec', 0) > 0:
                summary_text.append(f"  Processing Rate: {perf.get('messages_per_sec', 0):.0f} messages/sec\n")
        
        # Validation information
        validation = result.get('validation')
        if validation:
            summary_text.append("\nValidation Results:\n", style=cls.get_color('info', 'bold'))
            
            # Overall validation status
            if validation.get('is_valid', False):
                summary_text.append("  Status: ", style=cls.get_color('info', 'bold'))
                summary_text.append(" PASSED", style=cls.get_color('success', 'bold'))
                summary_text.append(f" ({validation.get('validation_time', 0):.3f}s)\n")
            else:
                summary_text.append("  Status: ", style=cls.get_color('info', 'bold'))
                summary_text.append(" FAILED", style=cls.get_color('error', 'bold'))
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
                summary_text.append("  Errors:\n", style=cls.get_color('error', 'bold'))
                for error in errors[:3]:  # Show first 3 errors
                    summary_text.append(f"    • {error}\n", style=cls.get_color('error'))
                if len(errors) > 3:
                    summary_text.append(f"    • ... and {len(errors) - 3} more errors\n", style=cls.get_color('error'))
            
            # Show warnings if any
            warnings = validation.get('warnings', [])
            if warnings:
                summary_text.append("  Warnings:\n", style=cls.get_color('warning', 'bold'))
                for warning in warnings[:2]:  # Show first 2 warnings
                    summary_text.append(f"    • {warning}\n", style=cls.get_color('warning'))
                if len(warnings) > 2:
                    summary_text.append(f"    • ... and {len(warnings) - 2} more warnings\n", style=cls.get_color('warning'))
        
        # Add topics overview
        summary_text.append("\nTopics Overview:\n", style=cls.get_color('info', 'bold'))
        summary_text.append(f"  Keeping {stats.get('selected_topics', 0)}, Excluding {stats.get('excluded_topics', 0)}\n")
        
        # Add topics table
        summary_text.append("\n")
        
        # Create topics table with full width
        table = Table(show_header=True, header_style=cls.get_color('accent', 'bold'), box=None, expand=config.full_width)
        table.add_column("Status", style=cls.get_color('primary', 'bold'), width=8, justify="center")
        table.add_column("Topic", style=cls.get_color('info'))
        table.add_column("Count", style=cls.get_color('accent'), justify="right", width=10)
        
        topics_to_extract = result.get('topics_to_extract', [])
        
        for topic in result.get('all_topics', []):
            topic_name = topic['name']
            message_count = topic['message_count']
            
            should_keep = topic_name in topics_to_extract
            
            if should_keep:
                status = "●"
                status_style = "green"
            else:
                status = "○"
                status_style = "red dim"
                topic_name = f"[{cls.get_color('muted', 'dim')}]{topic_name}[/{cls.get_color('muted', 'dim')}]"
            
            table.add_row(
                f"[{status_style}]{status}[/{status_style}]",
                topic_name,
                f"{message_count:,}",
            )
        
        # Create legend
        legend_text = Text()
        legend_text.append("● = Keep (included in output)  ", style=cls.get_color('success'))
        legend_text.append("○ = Drop (excluded from output)", style=cls.get_color('error', 'dim'))
        
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
            border_style=cls.get_color('info')
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
            header_style=cls.get_color('accent', 'bold')
        )
        
        table.add_column("Topic", style=cls.get_color('info'), no_wrap=True)
        table.add_column("Count", justify="right", style=cls.get_color('success'))
        table.add_column("Size", justify="right", style=cls.get_color('accent'))
        table.add_column("Frequency", justify="right", style=cls.get_color('primary'))
        

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
                    border_style=cls.get_color('accent'),
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
            
            parts = [f"[{cls.get_color('primary', 'bold')}]{name}[/{cls.get_color('primary', 'bold')}]"]
            parts.append(f"[{cls.get_color('success')}]{count:,} msgs[/{cls.get_color('success')}]")
            
            if frequency > 0:
                parts.append(f"[{cls.get_color('info')}]{frequency:.1f} Hz[/{cls.get_color('info')}]")
            
            console.print(" | ".join(parts))
        
        return ""
    
    @classmethod
    def _render_summary(cls, result: Dict[str, Any], options: RenderOptions, console: Console) -> str:
        """Render result as summary only"""
        bag_info = result.get('bag_info', {})
        cls._display_bag_summary(bag_info, DisplayConfig(verbose=options.verbose), console)
        return ""
    

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
    def _create_bag_summary_content(cls, bag_info: Dict[str, Any], config: DisplayConfig):
        """Create bag summary content for panel display"""
        from rich.text import Text
        
        summary_text = Text()
        summary_text.append("Summary\n", style=cls.get_color('primary', 'bold'))
        
        # File information
        file_name = bag_info.get('file_name', 'Unknown')
        file_size = cls._format_size(bag_info.get('file_size', 0))
        topics_count = bag_info.get('topics_count', 0)
        total_messages = bag_info.get('total_messages', 0)
        duration = bag_info.get('duration_seconds', 0)
        
        summary_text.append(f"  File: {file_name}\n", style=cls.get_color('info'))
        summary_text.append(f"  Topics: {topics_count}\n", style=cls.get_color('info'))
        summary_text.append(f"  Messages: {total_messages:,}\n", style=cls.get_color('info'))
        summary_text.append(f"  File Size: {file_size}\n", style=cls.get_color('info'))
        summary_text.append(f"  Duration: {duration:.1f}s\n", style=cls.get_color('info'))
        
        if duration > 0 and total_messages > 0:
            avg_rate = total_messages / duration
            summary_text.append(f"  Avg Rate: {avg_rate:.1f} Hz\n", style=cls.get_color('info'))
        
        # Analysis information
        analysis_time = bag_info.get('analysis_time', 0)
        cached = bag_info.get('cached', False)
        summary_text.append(f"  Analysis Time: {analysis_time:.3f}s\n", style="dim")
        summary_text.append(f"  Cached: {'Yes' if cached else 'No'}\n", style="dim")
        
        return summary_text
    
    @classmethod
    def create_topics_table_content(cls, topics: List[TopicInfo],config: DisplayConfig):
        """Create topics table content for panel display"""
        table = Table(
            title=f"Topics ({len(topics)})",
            show_header=True,
            header_style=cls.get_color('accent', 'bold'),
            expand=config.full_width,
            box=None
        )
        # print(topics)
        
        table.add_column("Topic", style=cls.get_color('info'), no_wrap=True)
        table.add_column("Count", justify="right", style=cls.get_color('success'))
        table.add_column("Size", justify="right", style=cls.get_color('accent'))
        table.add_column("Frequency", justify="right", style=cls.get_color('primary'))
        
        # Add topic rows
        for topic_info in topics:
            # Handle both dict and object formats
            if isinstance(topic_info, dict):
                frequency_str = str(topic_info.get('frequency', 0.0))
                size_str = str(topic_info.get('size_bytes', 0))
                name = topic_info.get('name', 'Unknown')
                count = str(topic_info.get('message_count', 0))
            else:
                # Object format
                frequency_str = topic_info.frequency
                size_str = topic_info.size
                name = topic_info.name
                count = topic_info.count
            
            table.add_row(
                name,
                count,
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
            cache_text.append("Cache Performance\n", style=cls.get_color('primary', 'bold'))
            cache_text.append(f"  Hit Rate: {hit_rate:.1f}% ({total_requests} requests)", style=cls.get_color('info'))
            
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
                    topic_text.append(f"{topic}", style=cls.get_color('info', 'bold'))
                    topic_text.append(f" ({analysis.get('message_type', 'Unknown')})", style=cls.get_color('muted', 'dim'))
                    content_parts.append(topic_text)
                    
                    fields_text = Text()
                    # Display fields with hierarchical structure (preserving indentation)
                    for field_path in field_paths:
                        # Count leading spaces to determine nesting level
                        leading_spaces = len(field_path) - len(field_path.lstrip())
                        field_name = field_path.strip()
                        
                        if leading_spaces > 0:
                            # Nested field - show with accent color and preserve indentation
                            indent = "  " * (leading_spaces // 2 + 1)  # Convert spaces to proper indentation
                            fields_text.append(f"{indent}• {field_name}\n", style=cls.get_color('accent'))
                        else:
                            # Top-level field - show with success color
                            fields_text.append(f"  • {field_name}\n", style=cls.get_color('success'))
                    
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
                    topic_text.append(f"{topic_name}", style=cls.get_color('info', 'bold'))
                    topic_text.append(f" ({message_type})", style=cls.get_color('muted', 'dim'))
                    content_parts.append(topic_text)
                    
                    fields_text = Text()
                    # Display fields with hierarchical structure (preserving indentation)
                    for field_path in field_paths:
                        # Count leading spaces to determine nesting level
                        leading_spaces = len(field_path) - len(field_path.lstrip())
                        field_name = field_path.strip()
                        
                        if leading_spaces > 0:
                            # Nested field - show with accent color and preserve indentation
                            indent = "  " * (leading_spaces // 2 + 1)  # Convert spaces to proper indentation
                            fields_text.append(f"{indent}• {field_name}\n", style=cls.get_color('accent'))
                        else:
                            # Top-level field - show with success color
                            fields_text.append(f"  • {field_name}\n", style=cls.get_color('success'))
                    
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


# Import theme from theme_manager for backward compatibility
