#!/usr/bin/env python3
"""
Configuration Command - Opens config file in editor
"""

import os
import shutil
import subprocess
from typing import Dict, Any
from pathlib import Path
from .base_command import BaseCommand


class ConfigurationCommand(BaseCommand):
    """Handles /configuration - opens Rose config file in editor"""
    
    def get_command_name(self) -> str:
        return "configuration"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute configuration command - opens config file in editor
        
        Opens ~/.rose/rose.config.yaml in the default editor
        """
        try:
            # Fixed configuration location
            rose_dir = Path.home() / ".rose"
            config_file = rose_dir / "rose.config.yaml"
            
            # Check if config file exists
            if not config_file.exists():
                # Ask user if they want to initialize it
                from InquirerPy import inquirer
                
                self.result_formatter.format_warning(
                    f"Configuration file not found: {config_file}"
                )
                
                should_init = inquirer.confirm(
                    message="Initialize Rose configuration now?",
                    default=True
                ).execute()
                
                if should_init:
                    # Initialize configuration
                    init_result = self._init_config(rose_dir, config_file)
                    if not init_result['success']:
                        return init_result
                else:
                    return {
                        'success': False,
                        'message': 'Configuration initialization cancelled',
                        'stdout': '',
                        'stderr': '',
                        'returncode': 1
                    }
            
            # Find editor
            editor = self._find_editor()
            
            if not editor:
                return {
                    'success': False,
                    'error': 'No suitable editor found',
                    'stdout': '',
                    'stderr': 'Please set EDITOR environment variable or install vim, nano, or code',
                    'returncode': 1
                }
            
            # Open config file in editor
            self.result_formatter.format_info(f"Opening configuration in {editor}...")
            result = subprocess.run([editor, str(config_file)])
            
            if result.returncode == 0:
                self.result_formatter.format_success("Configuration file saved")
            
            return {
                'success': result.returncode == 0,
                'message': f'Configuration edited with {editor}',
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
    
    
    def _init_config(self, rose_dir: Path, config_file: Path) -> Dict[str, Any]:
        """Initialize configuration by copying default template"""
        try:
            # Create .rose directory if needed
            if not rose_dir.exists():
                rose_dir.mkdir(parents=True, exist_ok=True)
                self.result_formatter.format_success(f"Created directory: {rose_dir}")
            
            # Find template file
            template_locations = [
                Path(__file__).parent.parent.parent.parent / "rose.config.default.yaml",  # Installed
                Path.cwd() / "rose.config.default.yaml",  # Current directory
                Path(__file__).parent.parent.parent.parent.parent / "rose.config.default.yaml",  # Dev
            ]
            
            template_file = None
            for loc in template_locations:
                if loc.exists():
                    template_file = loc
                    break
            
            if not template_file:
                return {
                    'success': False,
                    'error': 'Could not find rose.config.default.yaml template',
                    'stdout': '',
                    'stderr': f'Searched in: {", ".join(str(l) for l in template_locations)}',
                    'returncode': 1
                }
            
            # Copy template
            shutil.copy2(template_file, config_file)
            self.result_formatter.format_success(f"Configuration initialized: {config_file}")
            self.result_formatter.format_info(f"Copied from: {template_file}")
            
            return {
                'success': True,
                'message': 'Configuration initialized',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to initialize configuration: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _find_editor(self) -> str:
        """Find suitable editor"""
        # Check EDITOR environment variable first
        if 'EDITOR' in os.environ:
            return os.environ['EDITOR']
        
        # Try common editors in order of preference
        editors = ['vim', 'vi', 'nano', 'code', 'gedit', 'emacs']
        
        for editor in editors:
            if shutil.which(editor):
                return editor
        
        return None
    
    def get_help_text(self) -> str:
        return """Open Rose configuration file in editor

Usage: /configuration

Opens the Rose configuration file (~/.rose/rose.config.yaml) in your default editor.

The configuration file controls:
- Performance settings (workers, memory limits)
- Default behaviors (compression, caching)
- Interactive command defaults
- UI settings (theme, colors)
- Plugin system settings
- Logging configuration

If no configuration file exists, you will be prompted to initialize it.

Environment variables:
  EDITOR - Preferred editor (e.g., export EDITOR=nano)

Fallback editors: vim, vi, nano, code, gedit, emacs

See also: 
  rose config init - Initialize configuration
  rose config edit - Edit configuration from CLI"""
