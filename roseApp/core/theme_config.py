"""
Centralized Theme Configuration Module

This module provides unified theme configuration for all components in the Rose application,
including CLI, TUI, and plotting modules. It ensures consistent color usage across the entire application.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .ui_control import UIControl


class ComponentType(Enum):
    """Component types for theme application"""
    CLI = "cli"
    TUI = "tui"
    PLOT = "plot"
    PROGRESS = "progress"
    TABLE = "table"
    PANEL = "panel"


@dataclass
class ComponentTheme:
    """Theme configuration for specific component types"""
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    error: str
    info: str
    muted: str
    background: str
    foreground: str
    border: str


class UnifiedThemeManager:
    """
    Unified Theme Manager for consistent color usage across all components
    
    This class provides a centralized way to manage themes and ensures
    all components use consistent colors regardless of their type.
    """
    
    @classmethod
    def get_component_theme(cls, component_type: ComponentType) -> ComponentTheme:
        """Get theme configuration for specific component type
        
        Args:
            component_type: Type of component requesting theme
            
        Returns:
            ComponentTheme with appropriate colors for the component
        """
        colors = UIControl.get_theme_colors()
        
        # Base theme applies to all components
        base_theme = ComponentTheme(
            primary=colors.primary,
            secondary=colors.secondary,
            accent=colors.accent,
            success=colors.success,
            warning=colors.warning,
            error=colors.error,
            info=colors.info,
            muted=colors.muted,
            background=colors.background,
            foreground=colors.foreground,
            border=colors.border
        )
        
        # Component-specific adjustments
        if component_type == ComponentType.CLI:
            # CLI uses rich color names for better terminal compatibility
            return ComponentTheme(
                primary=colors.rich_primary,
                secondary=colors.rich_secondary,
                accent=colors.rich_accent,
                success=colors.rich_success,
                warning=colors.rich_warning,
                error=colors.rich_error,
                info=colors.rich_info,
                muted=colors.rich_muted,
                background=colors.background,
                foreground=colors.foreground,
                border=colors.border
            )
        elif component_type == ComponentType.PLOT:
            # Plotting uses hex colors for precise color control
            return base_theme
        elif component_type == ComponentType.TUI:
            # TUI uses textual-compatible color names
            return ComponentTheme(
                primary="blue",
                secondary="cyan",  
                accent="yellow",
                success="green",
                warning="yellow",
                error="red",
                info="blue",
                muted="dim white",
                background=colors.background,
                foreground=colors.foreground,
                border=colors.border
            )
        else:
            return base_theme
    
    @classmethod
    def get_color(cls, component_type: ComponentType, color_name: str, modifier: str = "") -> str:
        """Get unified color for any component type
        
        Args:
            component_type: Type of component requesting color
            color_name: Name of the color (primary, success, error, etc.)
            modifier: Style modifier (bold, dim, italic, etc.)
            
        Returns:
            Formatted color string appropriate for the component
        """
        theme = cls.get_component_theme(component_type)
        
        color_map = {
            'primary': theme.primary,
            'secondary': theme.secondary,
            'accent': theme.accent,
            'success': theme.success,
            'warning': theme.warning,
            'error': theme.error,
            'info': theme.info,
            'muted': theme.muted,
            'background': theme.background,
            'foreground': theme.foreground,
            'border': theme.border
        }
        
        color = color_map.get(color_name, theme.foreground)
        
        if modifier and component_type in [ComponentType.CLI, ComponentType.PROGRESS, ComponentType.TABLE]:
            return f"{modifier} {color}"
        return color
    
    @classmethod
    def get_style_dict(cls, component_type: ComponentType) -> Dict[str, str]:
        """Get style dictionary for component configuration
        
        Args:
            component_type: Type of component requesting styles
            
        Returns:
            Dictionary of style definitions
        """
        theme = cls.get_component_theme(component_type)
        
        return {
            'primary': theme.primary,
            'secondary': theme.secondary,
            'accent': theme.accent,
            'success': theme.success,
            'warning': theme.warning,
            'error': theme.error,
            'info': theme.info,
            'muted': theme.muted,
            'background': theme.background,
            'foreground': theme.foreground,
            'border': theme.border,
            # Additional derived styles
            'primary_bold': f"bold {theme.primary}",
            'success_bold': f"bold {theme.success}",
            'error_bold': f"bold {theme.error}",
            'warning_bold': f"bold {theme.warning}",
            'accent_bold': f"bold {theme.accent}",
            'muted_dim': f"dim {theme.muted}"
        }
    
    @classmethod
    def get_plot_colors(cls) -> Dict[str, str]:
        """Get color palette for plotting components
        
        Returns:
            Dictionary of hex colors for plotting
        """
        colors = UIControl.get_theme_colors()
        return {
            'primary': colors.primary,
            'secondary': colors.secondary,
            'accent': colors.accent,
            'success': colors.success,
            'warning': colors.warning,
            'error': colors.error,
            'info': colors.info,
            'background': colors.background,
            'foreground': colors.foreground,
            'grid': colors.border,
            'chart_colors': colors.chart_colors
        }
    
    @classmethod
    def get_tui_css_variables(cls) -> Dict[str, str]:
        """Get CSS variables for TUI components
        
        Returns:
            Dictionary of CSS variable definitions
        """
        theme = cls.get_component_theme(ComponentType.TUI)
        colors = UIControl.get_theme_colors()
        
        return {
            '--primary': colors.primary,
            '--secondary': colors.secondary,
            '--accent': colors.accent,
            '--success': colors.success,
            '--warning': colors.warning,
            '--error': colors.error,
            '--info': colors.info,
            '--muted': colors.muted,
            '--background': colors.background,
            '--foreground': colors.foreground,
            '--border': colors.border,
            '--input': colors.input
        }
    
    @classmethod
    def apply_theme_to_component(cls, component_type: ComponentType, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply unified theme to component configuration
        
        Args:
            component_type: Type of component
            config: Component configuration dictionary
            
        Returns:
            Updated configuration with theme colors applied
        """
        theme = cls.get_component_theme(component_type)
        style_dict = cls.get_style_dict(component_type)
        
        # Apply theme colors to configuration
        themed_config = config.copy()
        
        # Replace color placeholders with actual theme colors
        for key, value in themed_config.items():
            if isinstance(value, str):
                for color_name, color_value in style_dict.items():
                    placeholder = f"${{{color_name}}}"
                    if placeholder in value:
                        themed_config[key] = value.replace(placeholder, color_value)
        
        return themed_config


# Convenience functions for backward compatibility
def get_cli_colors() -> Dict[str, str]:
    """Get CLI color theme (backward compatibility)"""
    return UnifiedThemeManager.get_style_dict(ComponentType.CLI)


def get_tui_colors() -> Dict[str, str]:
    """Get TUI color theme (backward compatibility)"""
    return UnifiedThemeManager.get_style_dict(ComponentType.TUI)


def get_plot_colors() -> Dict[str, str]:
    """Get plotting color theme (backward compatibility)"""
    return UnifiedThemeManager.get_plot_colors()


# Global theme manager instance
theme_manager = UnifiedThemeManager() 