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
            # Look for existing config files using the same logic as run_handlers.py
            rose_dir = Path.home() / ".rose"
            config_files = [
                rose_dir / "config.json",
                rose_dir / "config.yaml", 
                rose_dir / "config.yml"
            ]
            
            # Use the first existing config file
            config_file = None
            for cf in config_files:
                if cf.exists():
                    config_file = cf
                    break
            
            # If no config file exists, create default JSON config
            if config_file is None:
                config_file = rose_dir / "config.json"
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
        import json
        
        # Ensure .rose directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        default_config = {
            "cache": {
                "max_size_gb": 10,
                "auto_cleanup": True
            },
            "processing": {
                "default_workers": 4,
                "compression": "lz4"
            },
            "ui": {
                "theme": "default",
                "show_progress": True
            },
            "paths": {
                "default_output_dir": "~/rose_output"
            }
        }
        
        try:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
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
