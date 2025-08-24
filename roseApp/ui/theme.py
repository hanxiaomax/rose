"""
Simple, unified theme system for Rose CLI tools.
Inspired by vim color schemes - provides minimal but consistent styling.

This module provides a single source of truth for all CLI colors and styling,
ensuring consistent appearance across all CLI commands without exposing
implementation details to individual UI components.
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class ThemeMode(Enum):
    """Simple theme modes"""
    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


@dataclass
class ThemeColors:
    """Simple color palette for CLI"""
    
    # Base colors
    primary: str = "cyan"
    secondary: str = "blue"
    accent: str = "yellow"
    
    # Status colors
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    info: str = "blue"
    
    # Neutral colors
    muted: str = "dim"
    dim: str = "dim"
    
    # Special colors
    highlight: str = "bright_white"
    background: str = "black"
    foreground: str = "white"
    
    # File operations
    file: str = "cyan"
    directory: str = "blue"
    executable: str = "green"
    link: str = "magenta"


class SimpleTheme:
    """Simple theme system without complexity"""
    
    # Standard color palette
    _colors = ThemeColors()
    
    # Vim-inspired color mappings
    _color_map = {
        # Status messages
        'ok': _colors.success,
        'success': _colors.success,
        'good': _colors.success,
        'pass': _colors.success,
        
        'warn': _colors.warning,
        'warning': _colors.warning,
        'caution': _colors.warning,
        
        'error': _colors.error,
        'fail': _colors.error,
        'bad': _colors.error,
        'critical': _colors.error,
        
        'info': _colors.info,
        'note': _colors.info,
        'debug': _colors.muted,
        
        # UI elements
        'title': _colors.primary,
        'header': _colors.primary,
        'label': _colors.secondary,
        'value': _colors.foreground,
        'path': _colors.file,
        'topic': _colors.accent,
        
        # Operations
        'processing': _colors.accent,
        'loading': _colors.muted,
        'complete': _colors.success,
        'skip': _colors.muted,
        
        # File types
        'file': _colors.file,
        'directory': _colors.directory,
        'size': _colors.muted,
        'time': _colors.muted,
        
        # Special
        'highlight': _colors.highlight,
        'dim': _colors.dim,
        'muted': _colors.muted,
    }
    
    @classmethod
    def get_color(cls, color_name: str) -> str:
        """Get color by name - simple lookup without complexity"""
        return cls._color_map.get(color_name.lower(), cls._colors.foreground)
    
    @classmethod
    def get_style(cls, style_name: str) -> str:
        """Get style by name - same as color for simplicity"""
        return cls.get_color(style_name)
    
    @classmethod
    def style_text(cls, text: str, color_name: str, modifier: str = "") -> str:
        """Apply style to text"""
        color = cls.get_color(color_name)
        if modifier:
            return f"[{modifier} {color}]{text}[/{modifier} {color}]"
        return f"[{color}]{text}[/{color}]"
    
    @classmethod
    def get_all_colors(cls) -> Dict[str, str]:
        """Get all available color names"""
        return cls._color_map.copy()


# Message styles for different contexts
class MessageStyle:
    """Predefined message styles for consistency"""
    
    @staticmethod
    def success(text: str) -> str:
        return SimpleTheme.style_text(text, "success")
    
    @staticmethod
    def error(text: str) -> str:
        return SimpleTheme.style_text(text, "error")
    
    @staticmethod
    def warning(text: str) -> str:
        return SimpleTheme.style_text(text, "warning")
    
    @staticmethod
    def info(text: str) -> str:
        return SimpleTheme.style_text(text, "info")
    
    @staticmethod
    def title(text: str) -> str:
        return SimpleTheme.style_text(text, "title", "bold")
    
    @staticmethod
    def path(text: str) -> str:
        return SimpleTheme.style_text(text, "path")
    
    @staticmethod
    def topic(text: str) -> str:
        return SimpleTheme.style_text(text, "topic")
    
    @staticmethod
    def dim(text: str) -> str:
        return SimpleTheme.style_text(text, "dim")
    
    @staticmethod
    def get_message(text: str, message_type: str) -> str:
        """Get styled message based on type"""
        type_map = {
            "success": MessageStyle.success,
            "error": MessageStyle.error,
            "warning": MessageStyle.warning,
            "info": MessageStyle.info,
            "title": MessageStyle.title,
            "path": MessageStyle.path,
            "topic": MessageStyle.topic,
            "dim": MessageStyle.dim,
        }
        
        style_func = type_map.get(message_type, MessageStyle.info)
        return style_func(text)


# Global theme instance
THEME = SimpleTheme()


def get_color(color_name: str) -> str:
    """Global function to get color by name"""
    return THEME.get_color(color_name)


def style_text(text: str, color_name: str, modifier: str = "") -> str:
    """Global function to style text"""
    return THEME.style_text(text, color_name, modifier)