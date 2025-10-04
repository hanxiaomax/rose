"""
Simple theme system for Rose CLI.
Loads colors from rose.theme.yaml configuration file.
"""

import os
from pathlib import Path
from typing import Dict, Optional
import yaml


class ThemeLoader:
    """Load and manage theme colors from YAML configuration"""
    
    _colors: Optional[Dict[str, str]] = None
    _theme_file: Optional[Path] = None
    
    @classmethod
    def _find_theme_file(cls) -> Optional[Path]:
        """Find theme file based on configuration
        
        Priority:
        1. Theme file specified in rose.config.yaml (theme_file setting)
        2. rose.theme.default.yaml in same directory as rose.config.yaml
        3. rose.theme.default.yaml in fallback search paths
        4. Built-in defaults
        
        Search paths:
        1. Same directory as rose.config.yaml (if found)
        2. Current directory
        3. Project root
        4. User config (~/.rose/)
        5. System config (/etc/rose/)
        
        Returns:
            Path to theme file or None if not found
        """
        # Try to load theme file from configuration
        theme_filename = None
        config_dir = None
        
        try:
            from ..core.config import get_config
            config = get_config()
            if hasattr(config, 'theme_file'):
                theme_filename = config.theme_file
            
            # Get config file directory if available
            if hasattr(config, '_loaded_config_path') and config._loaded_config_path:
                config_dir = Path(config._loaded_config_path).parent
        except Exception:
            pass
        
        # Default to rose.theme.default.yaml if not specified
        if not theme_filename:
            theme_filename = "rose.theme.default.yaml"
        
        # Build search paths with config directory first
        search_dirs = []
        
        # Priority 1: Same directory as rose.config.yaml
        if config_dir:
            search_dirs.append(config_dir)
        
        # Priority 2-5: Other search paths
        search_dirs.extend([
            Path.cwd(),
            Path(__file__).parent.parent.parent,
            Path.home() / ".rose",
            Path("/etc/rose"),
        ])
        
        # Search for the theme file
        for base_dir in search_dirs:
            theme_file = base_dir / theme_filename
            if theme_file.exists() and theme_file.is_file():
                return theme_file
        
        return None
    
    @classmethod
    def _load_colors(cls) -> Dict[str, str]:
        """Load colors from theme YAML file
        
        Returns:
            Dictionary of color name to Rich color value mappings
        """
        theme_file = cls._find_theme_file()
        
        if theme_file is None:
            # Fallback to default colors if no theme file found
            return cls._get_default_colors()
        
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                colors = yaml.safe_load(f)
                
            if not isinstance(colors, dict):
                # Invalid format, use defaults
                return cls._get_default_colors()
            
            cls._theme_file = theme_file
            return colors
            
        except Exception as e:
            # Error reading file, use defaults
            print(f"Warning: Error loading theme file {theme_file}: {e}")
            return cls._get_default_colors()
    
    @classmethod
    def _get_default_colors(cls) -> Dict[str, str]:
        """Get default color scheme (fallback)
        
        Returns:
            Dictionary of default colors
        """
        return {
            # Primary colors
            'primary': 'orange1',
            'accent': 'orange1',
            
            # Status colors
            'success': 'dark_cyan',
            'warning': 'bright_yellow',
            'error': 'bright_red',
            'info': 'bright_cyan',
            
            # UI colors
            'muted': 'bright_black',
            'highlight': 'bright_white',
            
            # Semantic colors
            'file': 'bright_cyan',
            'directory': 'bright_blue',
            'topic': 'orange1',
            'timestamp': 'bright_black',
            
            # Aliases
            'claude': 'orange1',
            'emphasis': 'orange1',
            'thinking': 'orange1',
            'dim': 'bright_black',
            'path': 'bright_cyan',
        }
    
    @classmethod
    def get_colors(cls) -> Dict[str, str]:
        """Get current color configuration
        
        Returns:
            Dictionary of color mappings
        """
        if cls._colors is None:
            cls._colors = cls._load_colors()
        return cls._colors
    
    @classmethod
    def reload(cls):
        """Reload colors from theme file"""
        cls._colors = None
        cls._theme_file = None
    
    @classmethod
    def get_theme_file(cls) -> Optional[Path]:
        """Get path to currently loaded theme file
        
        Returns:
            Path to theme file or None if using defaults
        """
        if cls._colors is None:
            cls.get_colors()  # Load colors to set theme_file
        return cls._theme_file


def get_color(color_name: str, default: str = 'orange1') -> str:
    """Get color value by name
    
    Args:
        color_name: Name of the color to retrieve
        default: Default color if name not found
        
    Returns:
        Rich color string
        
    Examples:
        >>> get_color('primary')
        'orange1'
        >>> get_color('success')
        'dark_cyan'
        >>> get_color('unknown', 'white')
        'white'
    """
    colors = ThemeLoader.get_colors()
    return colors.get(color_name.lower(), default)


def list_colors() -> Dict[str, str]:
    """List all available colors
    
    Returns:
        Dictionary of all color mappings
    """
    return ThemeLoader.get_colors().copy()


def get_theme_file() -> Optional[Path]:
    """Get path to current theme file
    
    Returns:
        Path to theme file or None if using defaults
    """
    return ThemeLoader.get_theme_file()


def reload_theme():
    """Reload theme from file
    
    Use this to pick up changes to theme file without restarting.
    """
    ThemeLoader.reload()


def get_theme_info() -> Dict[str, any]:
    """Get theme information
    
    Returns:
        Dictionary with file path and color count
    """
    theme_file = get_theme_file()
    colors = list_colors()
    
    return {
        'theme_file': str(theme_file) if theme_file else 'Built-in defaults',
        'color_count': len(colors),
        'colors': colors
    }
