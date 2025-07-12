#!/usr/bin/env python3
"""
Unified theme system for the Rose application
Uses index.css as base theme and provides conversions for different platforms
"""

from typing import Dict, List, Any, Optional
import os

# Import the new simplified theme parser
from .theme_parser import (
    theme_parser,
    get_cli_colors,
    get_plot_colors,
    get_html_colors,
    get_inquirer_style,
    apply_matplotlib_style,
    generate_html_css
)

# Detect theme preference from environment
def get_theme_mode() -> bool:
    """Detect if dark mode should be used (legacy compatibility)"""
    # Check environment variables
    theme_env = os.environ.get('ROSE_THEME', '').lower()
    if theme_env in ['dark', 'true', '1']:
        return True
    elif theme_env in ['light', 'false', '0']:
        return False
    
    # Default to dark mode for better terminal experience
    return True

# Global theme mode (kept for compatibility)
DARK_MODE = get_theme_mode()

class RoseTheme:
    """Unified theme class for Rose application"""
    
    def __init__(self, dark_mode: bool = None):
        """Initialize theme with specified mode (mode parameter kept for compatibility)"""
        if dark_mode is None:
            dark_mode = DARK_MODE
        
        self.dark_mode = dark_mode
        # Use CLI colors for theme properties (since CLI uses dark theme)
        self._cli_colors = get_cli_colors()
        self._plot_colors = get_plot_colors()
        self._html_colors = get_html_colors()
    
    # Core color properties
    @property
    def PRIMARY(self) -> str:
        return self._cli_colors['primary']
    
    @property
    def SECONDARY(self) -> str:
        return self._cli_colors['secondary']
    
    @property
    def ACCENT(self) -> str:
        return self._cli_colors['accent']
    
    @property
    def WARNING(self) -> str:
        return self._cli_colors['warning']
    
    @property
    def ERROR(self) -> str:
        return self._cli_colors['error']
    
    @property
    def SUCCESS(self) -> str:
        return self._cli_colors['success']
    
    @property
    def INFO(self) -> str:
        return self._cli_colors['info']
    
    @property
    def BACKGROUND(self) -> str:
        return self._cli_colors['background']
    
    @property
    def FOREGROUND(self) -> str:
        return self._cli_colors['text_primary']
    
    @property
    def SURFACE(self) -> str:
        return self._cli_colors['background']
    
    @property
    def PANEL(self) -> str:
        return self._cli_colors['background']
    
    @property
    def TEXT_PRIMARY(self) -> str:
        return self._cli_colors['text_primary']
    
    @property
    def TEXT_SECONDARY(self) -> str:
        return self._cli_colors['text_secondary']
    
    @property
    def TEXT_DIM(self) -> str:
        return self._cli_colors['text_secondary']
    
    @property
    def TEXT_MUTED(self) -> str:
        return self._cli_colors['text_secondary']
    
    @property
    def BORDER(self) -> str:
        return self._cli_colors['border']
    
    # Data visualization colors (for plots)
    @property
    def PLOT_COLORS(self) -> List[str]:
        return self._plot_colors
    
    def get_rich_color(self, color_name: str) -> str:
        """Get a Rich console color by name"""
        return self._cli_colors.get(color_name, self.TEXT_PRIMARY)
    
    def get_plot_color(self, index: int) -> str:
        """Get a plot color by index (cycles through available colors)"""
        return self.PLOT_COLORS[index % len(self.PLOT_COLORS)]
    
    def get_inquirer_style(self):
        """Get InquirerPy style configuration"""
        return get_inquirer_style()
    
    def get_textual_theme(self):
        """Get Textual theme configuration (legacy compatibility)"""
        # Return basic theme dict for compatibility
        return {
            'primary': self.PRIMARY,
            'secondary': self.SECONDARY,
            'accent': self.ACCENT,
            'background': self.BACKGROUND,
            'foreground': self.FOREGROUND,
            'success': self.SUCCESS,
            'warning': self.WARNING,
            'error': self.ERROR,
        }
    
    def apply_matplotlib_style(self):
        """Apply matplotlib style configuration"""
        apply_matplotlib_style()
    
    def get_plotly_template(self) -> Dict[str, Any]:
        """Get Plotly template configuration (legacy compatibility)"""
        # Return basic template for compatibility
        return {
            'layout': {
                'paper_bgcolor': self._html_colors['background'],
                'plot_bgcolor': self._html_colors['background'],
                'font': {'color': self._html_colors['foreground']},
                'colorway': self._plot_colors,
            }
        }
    
    def generate_html_css(self) -> str:
        """Generate CSS for HTML export"""
        return generate_html_css()

# Create global theme instance
theme = RoseTheme()

# Export functions for easy access
def get_theme(dark_mode: bool = None) -> RoseTheme:
    """Get theme instance for specified mode"""
    return RoseTheme(dark_mode)

def set_theme_mode(dark_mode: bool):
    """Set global theme mode"""
    global DARK_MODE, theme
    DARK_MODE = dark_mode
    theme = RoseTheme(dark_mode) 