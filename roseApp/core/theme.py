"""
Unified theme system for Rose.

This module provides comprehensive theme management with CSS parsing,
multi-platform support, and dynamic theme switching capabilities.
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

from roseApp.core.util import get_logger

_logger = get_logger("theme")


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


class CSSThemeParser:
    """Parser for CSS-based theme definitions"""
    
    def __init__(self):
        self._variable_pattern = re.compile(r'--([^:]+):\s*([^;]+);')
        self._root_pattern = re.compile(r':root\s*{([^}]+)}', re.DOTALL)
        self._class_pattern = re.compile(r'\.([^{]+)\s*{([^}]+)}', re.DOTALL)
    
    def parse_css_file(self, css_path: Path) -> Dict[str, Dict[str, str]]:
        """Parse CSS file and extract theme variables"""
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            return self.parse_css_content(css_content)
        except Exception as e:
            _logger.error(f"Error parsing CSS file {css_path}: {e}")
            return {}
    
    def parse_css_content(self, css_content: str) -> Dict[str, Dict[str, str]]:
        """Parse CSS content and extract theme variables"""
        themes = {}
        
        # Parse :root variables (default theme)
        root_matches = self._root_pattern.findall(css_content)
        if root_matches:
            root_vars = self._parse_css_variables(root_matches[0])
            if root_vars:
                themes['default'] = root_vars
        
        # Parse class-based themes (.dark, .light, etc.)
        class_matches = self._class_pattern.findall(css_content)
        for class_name, class_content in class_matches:
            class_name = class_name.strip()
            if class_name in ['dark', 'light'] or class_name.endswith('-theme'):
                class_vars = self._parse_css_variables(class_content)
                if class_vars:
                    themes[class_name] = class_vars
        
        return themes
    
    def _parse_css_variables(self, css_block: str) -> Dict[str, str]:
        """Parse CSS variables from a CSS block"""
        variables = {}
        
        matches = self._variable_pattern.findall(css_block)
        for var_name, var_value in matches:
            var_name = var_name.strip()
            var_value = var_value.strip()
            
            # Clean up variable value
            var_value = self._clean_css_value(var_value)
            variables[var_name] = var_value
        
        return variables
    
    def _clean_css_value(self, value: str) -> str:
        """Clean CSS value by removing comments and extra whitespace"""
        # Remove comments
        value = re.sub(r'/\*.*?\*/', '', value, flags=re.DOTALL)
        
        # Remove extra whitespace
        value = ' '.join(value.split())
        
        return value.strip()
    
    def convert_to_theme_colors(self, css_vars: Dict[str, str]) -> ThemeColors:
        """Convert CSS variables to ThemeColors"""
        colors = ThemeColors()
        
        # Map CSS variables to theme colors
        color_mapping = {
            'background': ['background', 'bg', 'bg-color'],
            'foreground': ['foreground', 'fg', 'text', 'text-color'],
            'primary': ['primary', 'primary-color'],
            'secondary': ['secondary', 'secondary-color'],
            'accent': ['accent', 'accent-color'],
            'success': ['success', 'success-color', 'green'],
            'warning': ['warning', 'warning-color', 'yellow', 'orange'],
            'error': ['error', 'error-color', 'danger', 'red'],
            'info': ['info', 'info-color', 'blue'],
            'border': ['border', 'border-color'],
            'input': ['input', 'input-color'],
            'muted': ['muted', 'muted-color', 'gray', 'grey']
        }
        
        for color_attr, css_names in color_mapping.items():
            for css_name in css_names:
                if css_name in css_vars:
                    setattr(colors, color_attr, css_vars[css_name])
                    break
        
        # Handle chart colors
        chart_colors = []
        for i in range(1, 6):  # chart-1 through chart-5
            chart_var = f'chart-{i}'
            if chart_var in css_vars:
                chart_colors.append(css_vars[chart_var])
        
        if chart_colors:
            colors.chart_colors = chart_colors
        
        return colors


class RoseTheme:
    """Main theme manager for Rose application"""
    
    def __init__(self):
        self.current_mode = ThemeMode.LIGHT
        self.themes: Dict[str, Dict[str, Any]] = {}
        self.css_parser = CSSThemeParser()
        
        # Load default themes
        self._load_default_themes()
        
        _logger.info("Initialized RoseTheme manager")
    
    def _load_default_themes(self):
        """Load default light and dark themes"""
        # Light theme
        light_colors = ThemeColors(
            background="#ffffff",
            foreground="#000000",
            primary="#4f46e5",
            secondary="#14b8a6",
            accent="#f59e0b",
            success="#22c55e",
            warning="#f59e0b",
            error="#ef4444",
            info="#3b82f6",
            border="#e5e7eb",
            input="#f3f4f6",
            muted="#6b7280"
        )
        
        # Dark theme
        dark_colors = ThemeColors(
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
        
        # Default typography
        typography = ThemeTypography()
        
        # Default spacing
        spacing = ThemeSpacing()
        
        self.themes['light'] = {
            'colors': light_colors,
            'typography': typography,
            'spacing': spacing,
            'mode': ThemeMode.LIGHT
        }
        
        self.themes['dark'] = {
            'colors': dark_colors,
            'typography': typography,
            'spacing': spacing,
            'mode': ThemeMode.DARK
        }
    
    def load_theme_from_css(self, css_path: Path, theme_name: Optional[str] = None) -> bool:
        """Load theme from CSS file"""
        try:
            css_themes = self.css_parser.parse_css_file(css_path)
            
            if not css_themes:
                _logger.warning(f"No theme variables found in {css_path}")
                return False
            
            # Use provided theme name or derive from filename
            if not theme_name:
                theme_name = css_path.stem
            
            # Process each theme found in CSS
            for css_theme_name, css_vars in css_themes.items():
                full_theme_name = f"{theme_name}_{css_theme_name}" if css_theme_name != 'default' else theme_name
                
                # Convert CSS variables to theme components
                colors = self.css_parser.convert_to_theme_colors(css_vars)
                
                # Determine theme mode based on background color
                mode = self._detect_theme_mode(colors.background)
                
                self.themes[full_theme_name] = {
                    'colors': colors,
                    'typography': ThemeTypography(),
                    'spacing': ThemeSpacing(),
                    'mode': mode,
                    'source': str(css_path)
                }
            
            _logger.info(f"Loaded {len(css_themes)} theme(s) from {css_path}")
            return True
            
        except Exception as e:
            _logger.error(f"Error loading theme from {css_path}: {e}")
            return False
    
    def _detect_theme_mode(self, background_color: str) -> ThemeMode:
        """Detect theme mode based on background color"""
        # Simple heuristic: if background is dark, it's a dark theme
        bg = background_color.lower()
        
        # Handle hex colors
        if bg.startswith('#'):
            # Convert hex to RGB and calculate brightness
            try:
                hex_color = bg[1:]
                if len(hex_color) == 3:
                    hex_color = ''.join([c*2 for c in hex_color])
                
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                
                # Calculate perceived brightness
                brightness = (r * 0.299 + g * 0.587 + b * 0.114) / 255
                
                return ThemeMode.DARK if brightness < 0.5 else ThemeMode.LIGHT
                
            except ValueError:
                pass
        
        # Handle named colors and keywords
        dark_indicators = ['dark', 'black', 'night', 'midnight']
        if any(indicator in bg for indicator in dark_indicators):
            return ThemeMode.DARK
        
        return ThemeMode.LIGHT
    
    def set_theme(self, theme_name: str) -> bool:
        """Set active theme"""
        if theme_name not in self.themes:
            _logger.warning(f"Theme '{theme_name}' not found")
            return False
        
        theme = self.themes[theme_name]
        self.current_mode = theme['mode']
        
        _logger.info(f"Switched to theme: {theme_name}")
        return True
    
    def get_current_theme(self) -> Dict[str, Any]:
        """Get current active theme"""
        theme_name = 'dark' if self.current_mode == ThemeMode.DARK else 'light'
        return self.themes.get(theme_name, self.themes['light'])
    
    def get_theme(self, theme_name: str) -> Optional[Dict[str, Any]]:
        """Get specific theme by name"""
        return self.themes.get(theme_name)
    
    def list_themes(self) -> List[str]:
        """List all available themes"""
        return list(self.themes.keys())
    
    def get_colors(self, theme_name: Optional[str] = None) -> ThemeColors:
        """Get colors for specified theme or current theme"""
        if theme_name:
            theme = self.get_theme(theme_name)
        else:
            theme = self.get_current_theme()
        
        return theme['colors'] if theme else ThemeColors()
    
    def get_typography(self, theme_name: Optional[str] = None) -> ThemeTypography:
        """Get typography for specified theme or current theme"""
        if theme_name:
            theme = self.get_theme(theme_name)
        else:
            theme = self.get_current_theme()
        
        return theme['typography'] if theme else ThemeTypography()
    
    def get_spacing(self, theme_name: Optional[str] = None) -> ThemeSpacing:
        """Get spacing for specified theme or current theme"""
        if theme_name:
            theme = self.get_theme(theme_name)
        else:
            theme = self.get_current_theme()
        
        return theme['spacing'] if theme else ThemeSpacing()
    
    def export_theme_to_css(self, theme_name: str, output_path: Path) -> bool:
        """Export theme to CSS file"""
        try:
            theme = self.get_theme(theme_name)
            if not theme:
                _logger.error(f"Theme '{theme_name}' not found")
                return False
            
            colors = theme['colors']
            typography = theme['typography']
            spacing = theme['spacing']
            
            css_content = self._generate_css_content(colors, typography, spacing, theme_name)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(css_content)
            
            _logger.info(f"Exported theme '{theme_name}' to {output_path}")
            return True
            
        except Exception as e:
            _logger.error(f"Error exporting theme to {output_path}: {e}")
            return False
    
    def _generate_css_content(self, colors: ThemeColors, typography: ThemeTypography, 
                             spacing: ThemeSpacing, theme_name: str) -> str:
        """Generate CSS content from theme components"""
        css_lines = [
            f"/* Rose Theme: {theme_name} */",
            f".{theme_name} {{",
            "  /* Colors */",
            f"  --background: {colors.background};",
            f"  --foreground: {colors.foreground};",
            f"  --primary: {colors.primary};",
            f"  --secondary: {colors.secondary};",
            f"  --accent: {colors.accent};",
            f"  --success: {colors.success};",
            f"  --warning: {colors.warning};",
            f"  --error: {colors.error};",
            f"  --info: {colors.info};",
            f"  --border: {colors.border};",
            f"  --input: {colors.input};",
            f"  --muted: {colors.muted};",
            "",
            "  /* Chart Colors */",
        ]
        
        for i, color in enumerate(colors.chart_colors, 1):
            css_lines.append(f"  --chart-{i}: {color};")
        
        css_lines.extend([
            "",
            "  /* Typography */",
            f"  --font-family: {typography.font_family};",
            f"  --font-size-base: {typography.font_size_base};",
            f"  --font-size-small: {typography.font_size_small};",
            f"  --font-size-large: {typography.font_size_large};",
            f"  --font-weight-normal: {typography.font_weight_normal};",
            f"  --font-weight-bold: {typography.font_weight_bold};",
            f"  --line-height: {typography.line_height};",
            "",
            "  /* Spacing */",
            f"  --spacing-base: {spacing.base_unit};",
            f"  --spacing-small: {spacing.small};",
            f"  --spacing-medium: {spacing.medium};",
            f"  --spacing-large: {spacing.large};",
            f"  --spacing-xlarge: {spacing.xlarge};",
            "}",
            ""
        ])
        
        return "\n".join(css_lines)
    
    def get_matplotlib_style(self, theme_name: Optional[str] = None) -> Dict[str, Any]:
        """Get matplotlib style configuration for the theme"""
        colors = self.get_colors(theme_name)
        
        return {
            'figure.facecolor': colors.background,
            'axes.facecolor': colors.background,
            'axes.edgecolor': colors.border,
            'axes.labelcolor': colors.foreground,
            'text.color': colors.foreground,
            'xtick.color': colors.foreground,
            'ytick.color': colors.foreground,
            'grid.color': colors.border,
            'axes.prop_cycle': f"cycler('color', {colors.chart_colors})"
        }
    
    def get_plotly_theme(self, theme_name: Optional[str] = None) -> Dict[str, Any]:
        """Get plotly theme configuration"""
        colors = self.get_colors(theme_name)
        
        return {
            'layout': {
                'paper_bgcolor': colors.background,
                'plot_bgcolor': colors.background,
                'font': {'color': colors.foreground},
                'colorway': colors.chart_colors
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert theme manager state to dictionary"""
        return {
            'current_mode': self.current_mode.value,
            'themes': {
                name: {
                    'colors': theme['colors'].to_dict(),
                    'typography': theme['typography'].to_dict(),
                    'spacing': theme['spacing'].to_dict(),
                    'mode': theme['mode'].value
                }
                for name, theme in self.themes.items()
            }
        }


# Global theme manager instance
_global_theme: Optional[RoseTheme] = None


def get_theme() -> RoseTheme:
    """Get or create global theme manager instance"""
    global _global_theme
    if _global_theme is None:
        _global_theme = RoseTheme()
    return _global_theme


def set_theme(theme_name: str) -> bool:
    """Set active theme globally"""
    return get_theme().set_theme(theme_name)


def get_current_colors() -> ThemeColors:
    """Get colors for current theme"""
    return get_theme().get_colors()


def get_current_typography() -> ThemeTypography:
    """Get typography for current theme"""
    return get_theme().get_typography()


def get_current_spacing() -> ThemeSpacing:
    """Get spacing for current theme"""
    return get_theme().get_spacing()


def load_theme_from_css(css_path: Path, theme_name: Optional[str] = None) -> bool:
    """Load theme from CSS file globally"""
    return get_theme().load_theme_from_css(css_path, theme_name)


# Backward compatibility layer for CLI modules
class CompatibilityTheme:
    """Compatibility layer for legacy theme usage in CLI modules"""
    
    def __init__(self):
        self._colors = None
    
    @property
    def colors(self) -> ThemeColors:
        if self._colors is None:
            self._colors = get_current_colors()
        return self._colors
    
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
        colors = self.colors
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


# Create global theme instance for backward compatibility
theme = CompatibilityTheme() 