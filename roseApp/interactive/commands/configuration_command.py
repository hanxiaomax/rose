#!/usr/bin/env python3
"""
Configuration Command - Opens config file in editor
"""

import os
import subprocess
from typing import Dict, Any
from pathlib import Path
from .base_command import BaseCommand


class ConfigurationCommand(BaseCommand):
    """Handles /configuration - opens config file in editor"""
    
    def get_command_name(self) -> str:
        return "configuration"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute configuration command - opens config file in editor
        
        This is an internal command that opens the configuration file
        """
        try:
            config_file = self._find_config_file()
            
            if not config_file:
                return {
                    'success': False,
                    'error': 'Rose configuration file not found',
                    'stdout': '',
                    'stderr': 'No configuration file found',
                    'returncode': 1
                }
            
            editor = self._find_editor()
            
            if not editor:
                return {
                    'success': False,
                    'error': 'No suitable editor found',
                    'stdout': '',
                    'stderr': 'Please set EDITOR environment variable or install a common editor',
                    'returncode': 1
                }
            
            # Open config file in editor
            result = subprocess.run([editor, str(config_file)])
            
            return {
                'success': result.returncode == 0,
                'message': f'Opened {config_file} in {editor}',
                'stdout': '',
                'stderr': '',
                'returncode': result.returncode
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Configuration command failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _find_config_file(self) -> Path:
        """Find Rose configuration file"""
        # Look for configuration files in common locations
        possible_configs = [
            Path.cwd() / "rose.conf",
            Path.cwd() / "rose.config",
            Path.cwd() / ".rose.conf",
            Path.cwd() / "config" / "rose.conf",
            Path.home() / ".rose" / "config",
            Path.home() / ".config" / "rose" / "config"
        ]
        
        for config_path in possible_configs:
            if config_path.exists():
                return config_path
        
        # If no config file exists, create a default one
        default_config = Path.cwd() / "rose.conf"
        self._create_default_config(default_config)
        return default_config
    
    def _create_default_config(self, config_path: Path):
        """Create a default configuration file"""
        default_content = """# Rose Configuration File
# This file contains configuration settings for Rose ROS bag processing tool

[general]
# Default compression for bag files (none, lz4, bz2)
compression = lz4

# Number of parallel workers for processing
workers = 4

# Default output directory for exports
output_dir = ./output

[cache]
# Enable caching for bag metadata
enabled = true

# Cache directory (relative to current working directory)
cache_dir = .rose_cache

# Cache expiration time in seconds (0 = never expire)
expire_time = 0

[ui]
# Default theme for interactive mode (cassette-walkman, cassette-dark)
theme = cassette-walkman

# Enable color output
color = true

[plugins]
# Plugin directory
plugin_dir = ./plugins

# Enable plugin system
enabled = true
"""
        
        try:
            with open(config_path, 'w') as f:
                f.write(default_content)
            self.result_formatter.format_info(f"Created default configuration file: {config_path}")
        except Exception as e:
            self.result_formatter.format_warning(f"Could not create config file: {e}")
    
    def _find_editor(self) -> str:
        """Find suitable editor"""
        # Check EDITOR environment variable first
        if 'EDITOR' in os.environ:
            return os.environ['EDITOR']
        
        # Try common editors in order of preference
        editors = ['code', 'nano', 'vim', 'vi', 'gedit', 'notepad']
        
        for editor in editors:
            try:
                # Check if editor is available
                result = subprocess.run(['which', editor], capture_output=True)
                if result.returncode == 0:
                    return editor
            except Exception:
                continue
        
        return None
    
    def get_help_text(self) -> str:
        return """Open Rose configuration file in editor

Usage: /configuration

Opens the Rose configuration file in your default editor.
The configuration file controls:
- Default compression settings
- Cache behavior
- UI theme and preferences
- Plugin system settings

If no configuration file exists, a default one will be created.

Environment variables:
  EDITOR - Preferred editor (e.g., export EDITOR=nano)

Fallback editors: code, nano, vim, vi, gedit, notepad"""
