"""
Claude-inspired theme system for Rose CLI tools.
Features warm orange/amber accents with high contrast text for professional appearance.

This module provides a single source of truth for all CLI colors and styling,
ensuring consistent appearance across all CLI commands with Claude's signature
warm and professional color palette.
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
    """Claude-inspired color palette for CLI - warm and professional"""
    
    # Base colors - Claude's signature warm tones
    primary: str = "dark_orange3"        # Clean, high contrast text
    secondary: str = "gold3"              # Cool complement to warm accent
    accent: str = "orange1"              # Claude's signature orange/amber
    orange: str = "orange1"              # Consistent warm tone
    
    # Status colors - Clear semantic meaning
    success: str = "bright_green"        # Vibrant success indicator
    warning: str = "bright_yellow"       # Attention-grabbing yellow
    error: str = "bright_red"            # Clear error indication
    info: str = "bright_cyan"            # Informative blue-cyan
    
    # Neutral colors - Sophisticated grays
    muted: str = "bright_black"          # Subtle secondary text
    dim: str = "bright_black"            # Dimmed elements
    
    # Special colors - Professional highlights
    highlight: str = "bright_white"      # Maximum contrast
    background: str = "black"            # Deep background
    foreground: str = "bright_white"     # Primary text
    
    # File operations - Intuitive color coding
    file: str = "bright_cyan"            # Files in bright cyan
    directory: str = "bright_blue"       # Directories in blue
    executable: str = "bright_green"     # Executables in green
    link: str = "bright_magenta"         # Links in magenta


class SimpleTheme:
    """Claude-inspired theme system with warm professional colors"""
    
    # Standard color palette
    _colors = ThemeColors()
    
    # Claude-inspired color mappings with professional semantics
    _color_map = {
        # Status messages - Clear and vibrant
        'ok': _colors.success,
        'success': _colors.success,
        'good': _colors.success,
        'pass': _colors.success,
        'complete': _colors.success,
        
        'warn': _colors.warning,
        'warning': _colors.warning,
        'caution': _colors.warning,
        'attention': _colors.warning,
        
        'error': _colors.error,
        'fail': _colors.error,
        'bad': _colors.error,
        'critical': _colors.error,
        'danger': _colors.error,
        
        'info': _colors.info,
        'note': _colors.info,
        'tip': _colors.info,
        'debug': _colors.muted,
        
        # UI elements - Professional hierarchy
        'primary': _colors.primary,
        'accent': _colors.accent,
        'claude': _colors.accent,           # Claude signature color
        'title': _colors.primary,
        'header': _colors.primary,
        'label': _colors.secondary,
        'value': _colors.foreground,
        'path': _colors.file,
        'topic': _colors.orange,
        
        # Operations - Intuitive workflow colors
        'processing': _colors.accent,       # Use Claude's signature color
        'loading': _colors.accent,          # Warm loading indicator
        'working': _colors.accent,          # Active work indication
        'thinking': _colors.accent,         # AI thinking state
        'analyzing': _colors.info,          # Analysis mode
        'skip': _colors.muted,
        
        # File types - Enhanced visibility
        'file': _colors.file,
        'directory': _colors.directory,
        'folder': _colors.directory,
        'size': _colors.muted,
        'time': _colors.muted,
        'timestamp': _colors.muted,
        
        # Special - Maximum impact
        'highlight': _colors.highlight,
        'dim': _colors.dim,
        'muted': _colors.muted,
        'subtle': _colors.muted,
        'emphasis': _colors.accent,         # Claude emphasis color
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
    def claude(text: str) -> str:
        """Claude signature style - warm orange/amber"""
        return SimpleTheme.style_text(text, "claude", "bold")
    
    @staticmethod
    def accent(text: str) -> str:
        """Accent style using Claude's signature color"""
        return SimpleTheme.style_text(text, "accent")
    
    @staticmethod
    def emphasis(text: str) -> str:
        """Emphasis style for important text"""
        return SimpleTheme.style_text(text, "emphasis", "bold")
    
    @staticmethod
    def thinking(text: str) -> str:
        """Thinking/processing style"""
        return SimpleTheme.style_text(text, "thinking")
    
    @staticmethod
    def get_message(text: str, message_type: str) -> str:
        """Get styled message based on type - expanded for Claude theme"""
        type_map = {
            "success": MessageStyle.success,
            "error": MessageStyle.error,
            "warning": MessageStyle.warning,
            "info": MessageStyle.info,
            "title": MessageStyle.title,
            "path": MessageStyle.path,
            "topic": MessageStyle.topic,
            "dim": MessageStyle.dim,
            "claude": MessageStyle.claude,
            "accent": MessageStyle.accent,
            "emphasis": MessageStyle.emphasis,
            "thinking": MessageStyle.thinking,
            "primary": lambda t: SimpleTheme.style_text(t, "primary"),
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