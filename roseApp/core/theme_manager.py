"""
Theme Manager - Handles theme management including colors, typography, and spacing
Provides unified theme system for consistent UI styling across the application
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from rich.console import Console


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
    
    # Rich console color names (for backward compatibility)
    @property
    def rich_primary(self) -> str:
        """Primary color as rich color name"""
        return "blue"
    
    @property
    def rich_secondary(self) -> str:
        """Secondary color as rich color name"""
        return "cyan"
    
    @property
    def rich_accent(self) -> str:
        """Accent color as rich color name"""
        return "yellow"
    
    @property
    def rich_success(self) -> str:
        """Success color as rich color name"""
        return "green"
    
    @property
    def rich_warning(self) -> str:
        """Warning color as rich color name"""
        return "yellow"
    
    @property
    def rich_error(self) -> str:
        """Error color as rich color name"""
        return "red"
    
    @property
    def rich_info(self) -> str:
        """Info color as rich color name"""
        return "blue"
    
    @property
    def rich_muted(self) -> str:
        """Muted color as rich color name"""
        return "dim white"
    
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
    
    def get_style(self, color_name: str, modifier: str = "") -> str:
        """Get styled color string for rich console
        
        Args:
            color_name: Name of the color (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
        
        Returns:
            Formatted style string for rich console
        """
        color_map = {
            'primary': self.primary,
            'secondary': self.secondary,
            'accent': self.accent,
            'success': self.success,
            'warning': self.warning,
            'error': self.error,
            'info': self.info,
            'muted': self.muted,
            'foreground': self.foreground,
            'background': self.background,
            'border': self.border
        }
        
        color = color_map.get(color_name, self.foreground)
        
        if modifier:
            return f"{modifier} {color}"
        return color
    
    def get_rich_style(self, color_name: str, modifier: str = "") -> str:
        """Get rich color name for console styling
        
        Args:
            color_name: Name of the color (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
        
        Returns:
            Rich color name string
        """
        rich_color_map = {
            'primary': self.rich_primary,
            'secondary': self.rich_secondary,
            'accent': self.rich_accent,
            'success': self.rich_success,
            'warning': self.rich_warning,
            'error': self.rich_error,
            'info': self.rich_info,
            'muted': self.rich_muted
        }
        
        color = rich_color_map.get(color_name, "white")
        
        if modifier:
            return f"{modifier} {color}"
        return color


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


class ThemeManager:
    """
    Theme Manager for handling UI themes across the application
    
    Provides methods for:
    - Theme switching (light/dark/auto)
    - Color management with consistent naming
    - Typography and spacing settings
    - Rich console styling integration
    - InquirerPy style configuration
    """
    
    _theme_colors = ThemeColors()
    _theme_typography = ThemeTypography()
    _theme_spacing = ThemeSpacing()
    _current_theme_mode = ThemeMode.LIGHT
    
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
    def get_theme_mode(cls) -> ThemeMode:
        """Get current theme mode"""
        return cls._current_theme_mode
    
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
    
    @classmethod
    def get_color(cls, color_name: str, modifier: str = "") -> str:
        """Get unified color for any component
        
        Args:
            color_name: Color name (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
        
        Returns:
            Styled color string
        """
        return cls._theme_colors.get_style(color_name, modifier)
    
    @classmethod
    def style_text(cls, text: str, color_name: str, modifier: str = "") -> str:
        """Apply unified styling to text
        
        Args:
            text: Text to style
            color_name: Color name (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
        
        Returns:
            Styled text for rich console
        """
        style = cls.get_color(color_name, modifier)
        return f"[{style}]{text}[/{style}]"
    
    @classmethod
    def get_component_color(cls, component_type: str, color_name: str, modifier: str = "") -> str:
        """Get color for specific component type using UnifiedThemeManager
        
        Args:
            component_type: Type of component (cli, tui, plot, etc.)
            color_name: Name of the color (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
        
        Returns:
            Formatted color string appropriate for the component
        """
        try:
            # Import here to avoid circular imports
            from .theme_config import UnifiedThemeManager, ComponentType
            
            # Map string to ComponentType enum
            component_map = {
                'cli': ComponentType.CLI,
                'tui': ComponentType.TUI,
                'plot': ComponentType.PLOT,
                'progress': ComponentType.PROGRESS,
                'table': ComponentType.TABLE,
                'panel': ComponentType.PANEL
            }
            
            comp_type = component_map.get(component_type.lower(), ComponentType.CLI)
            return UnifiedThemeManager.get_color(comp_type, color_name, modifier)
        except ImportError:
            # Fallback to regular color method if theme_config is not available
            return cls.get_color(color_name, modifier)
    
    @classmethod
    def update_typography(cls, **kwargs):
        """Update typography settings
        
        Args:
            **kwargs: Typography properties to update
        """
        for key, value in kwargs.items():
            if hasattr(cls._theme_typography, key):
                setattr(cls._theme_typography, key, value)
    
    @classmethod
    def update_spacing(cls, **kwargs):
        """Update spacing settings
        
        Args:
            **kwargs: Spacing properties to update
        """
        for key, value in kwargs.items():
            if hasattr(cls._theme_spacing, key):
                setattr(cls._theme_spacing, key, value)
    
    @classmethod
    def update_colors(cls, **kwargs):
        """Update color settings
        
        Args:
            **kwargs: Color properties to update
        """
        for key, value in kwargs.items():
            if hasattr(cls._theme_colors, key):
                setattr(cls._theme_colors, key, value)
    
    @classmethod
    def reset_to_defaults(cls):
        """Reset all theme settings to defaults"""
        cls._theme_colors = ThemeColors()
        cls._theme_typography = ThemeTypography()
        cls._theme_spacing = ThemeSpacing()
        cls._current_theme_mode = ThemeMode.LIGHT
    
    @classmethod
    def get_theme_dict(cls) -> Dict[str, Any]:
        """Get complete theme configuration as dictionary"""
        return {
            'mode': cls._current_theme_mode.value,
            'colors': cls._theme_colors.to_dict(),
            'typography': cls._theme_typography.to_dict(),
            'spacing': cls._theme_spacing.to_dict()
        }


# ============================================================================
# Backward Compatibility
# ============================================================================

# Create aliases for backward compatibility
get_theme = ThemeManager.get_theme_colors
get_current_colors = ThemeManager.get_theme_colors
get_current_typography = ThemeManager.get_theme_typography
get_current_spacing = ThemeManager.get_theme_spacing