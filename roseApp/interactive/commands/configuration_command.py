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
            # Use the new unified configuration system
            config_file = Path("rose.config.yaml")
            
            # If config file doesn't exist in current directory, create it
            if not config_file.exists():
                self._create_default_config(config_file)
            
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
    
    
    def _create_default_config(self, config_path: Path):
        """Create a default configuration file"""
        import yaml
        
        # Copy from example if available, otherwise create basic config
        example_path = Path("rose.config.yaml.example")
        
        if example_path.exists():
            # Copy from example
            import shutil
            shutil.copy2(example_path, config_path)
            self.result_formatter.format_info(f"Created configuration file from example: {config_path}")
        else:
            # Create basic configuration
            default_config = {
                "# Rose Configuration File": None,
                "# Basic configuration for Rose ROS Bag Processing Tool": None,
                "": None,
                "# Performance settings": None,
                "parallel_workers": 4,
                "cache_ttl_seconds": 300,
                "memory_limit_mb": 512,
                "": None,
                "# Default behaviors": None,
                "verbose_default": False,
                "build_index_default": False,
                "auto_cache_default": True,
                "compression_default": "none",
                "": None,
                "# File settings": None,
                "output_directory": "output",
                "": None,
                "# Feature flags": None,
                "enable_plugins": True,
                "": None,
                "# Logging": None,
                "log_level": "INFO",
                "log_to_file": True,
                "": None,
                "# UI settings": None,
                "theme_file": "rose.theme.default.yaml",
                "enable_colors": True
            }
            
            try:
                with open(config_path, 'w') as f:
                    yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
                self.result_formatter.format_info(f"Created default configuration file: {config_path}")
            except Exception as e:
                self.result_formatter.format_warning(f"Could not create config file: {e}")
    
    def _find_editor(self) -> str:
        """Find suitable editor"""
        # Check EDITOR environment variable first
        if 'EDITOR' in os.environ:
            return os.environ['EDITOR']
        
        # Try common editors in order of preference (vim first as per original implementation)
        editors = ['vim', 'vi', 'nano', 'code', 'gedit', 'notepad']
        
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

Opens the Rose configuration file (rose.config.yaml) in your default editor.
The configuration file controls:
- Performance settings (workers, memory limits)
- Default behaviors (compression, caching)
- UI settings (theme, colors)
- Plugin system settings
- Logging configuration

If no configuration file exists, a default one will be created.

Environment variables:
  EDITOR - Preferred editor (e.g., export EDITOR=nano)

Fallback editors: vim, vi, nano, code, gedit, notepad"""
