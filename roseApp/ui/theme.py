"""
Claude-inspired theme system for Rose CLI tools.
Simple color definitions with clean access interface.
"""

from dataclasses import dataclass


@dataclass
class Colors:
    """Claude-inspired color palette for CLI"""
    
    # Base colors
    primary: str = "orange1"
    accent: str = "orange1"
    
    # Status colors
    success: str = "dark_cyan"
    warning: str = "bright_yellow"
    error: str = "bright_red"
    info: str = "bright_cyan"
    
    # Neutral colors
    muted: str = "bright_black"
    highlight: str = "bright_white"
    
    # File operations
    file: str = "bright_cyan"
    directory: str = "bright_blue"


# Global color instance
_colors = Colors()


def get_color(color_name: str) -> str:
    """Get color by name"""
    color_map = {
        'primary': _colors.primary,
        'accent': _colors.accent,
        'success': _colors.success,
        'warning': _colors.warning,
        'error': _colors.error,
        'info': _colors.info,
        'muted': _colors.muted,
        'highlight': _colors.highlight,
        'file': _colors.file,
        'directory': _colors.directory,
        
        # Aliases for compatibility
        'claude': _colors.accent,
        'emphasis': _colors.accent,
        'thinking': _colors.accent,
        'dim': _colors.muted,
        'path': _colors.file,
        'topic': _colors.accent,
    }
    
    return color_map.get(color_name.lower(), _colors.primary)