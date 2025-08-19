"""
UI Control - Unified interface for all UI operations
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
    
    # ========================================================================
    # Status and Message Methods (Simplified for backwards compatibility)
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

    # ========================================================================
    # Backward Compatibility Methods
    # ========================================================================

    @classmethod
    def display_inspection_result(cls, result: Dict[str, Any], config: Optional[DisplayConfig] = None,
                                 console: Optional[Console] = None):
        """Display inspection results with rich formatting"""
        if console is None:
            console = cls.get_console()
        if config is None:
            config = DisplayConfig()
        
        # Use the new UI components for display
        from ..ui.inspect_ui import InspectUI
        inspect_ui = InspectUI()
        inspect_ui.display_inspection_results(result, verbose=config.verbose)

    @classmethod
    def render_result(cls, result: Dict[str, Any], options: Optional[RenderOptions] = None,
                     console: Optional[Console] = None) -> str:
        """Render result in specified format"""
        if console is None:
            console = cls.get_console()
        
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

# ============================================================================
# Backward Compatibility
# ============================================================================

# Create aliases for backward compatibility
ResultHandler = UIControl
get_theme = UIControl.get_theme_colors
get_current_colors = UIControl.get_theme_colors
get_current_typography = UIControl.get_theme_typography
get_current_spacing = UIControl.get_theme_spacing