"""
Configuration management CLI commands for Rose.

Provides commands to initialize and edit Rose configuration.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import typer

from ..core.util import get_logger, set_app_mode, AppMode
from ..ui.common_ui import Message
# Initialize
set_app_mode(AppMode.CLI)
logger = get_logger(__name__)


app = typer.Typer(help="Configuration management commands")

@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration file")
):
    """
    Initialize Rose configuration by copying default config to ~/.rose/rose.config.yaml
    
    This command creates the Rose configuration directory and copies the default
    configuration template.
    """
    # Fixed output location
    rose_dir = Path.home() / ".rose"
    config_file = rose_dir / "rose.config.yaml"
    
    # Create .rose directory if it doesn't exist
    if not rose_dir.exists():
        rose_dir.mkdir(parents=True, exist_ok=True)
        Message.success(f"Created directory: {rose_dir}")

    
    # Check if file already exists
    if config_file.exists() and not force:
        Message.warning(f"Configuration file already exists: {config_file}")
        Message.warning(f"Use [cyan]rose config init --force[/cyan] to overwrite")
        raise typer.Exit(1)
    
    try:
        # Find the default configuration template
        template_locations = [
            Path(__file__).parent.parent.parent / "rose.config.default.yaml",  # Installed location
            Path.cwd() / "rose.config.default.yaml",  # Current directory
            Path(__file__).parent.parent.parent.parent / "rose.config.default.yaml",  # Development location
        ]
        
        template_file = None
        for loc in template_locations:
            if loc.exists():
                template_file = loc
                break
        
        if not template_file:
            Message.error(f"Could not find rose.config.default.yaml template")
            Message.error(f"Searched in:")
            for loc in template_locations:
                Message.error(f"  • {loc}")
            raise typer.Exit(1)
        
        # Copy the template file
        shutil.copy2(template_file, config_file)
        
        Message.success(f"Configuration initialized: {config_file}")
        Message.info(f"Copied from: {template_file}")
        Message.info(f"Edit your configuration:")
        Message.info(f"  [cyan]rose config edit[/cyan]")
        
    except Exception as e:
        Message.error(f"Error initializing configuration: {e}")
        logger.error(f"Config init error: {e}", exc_info=True)
        raise typer.Exit(1)

@app.command()
def edit():
    """
    Edit Rose configuration file in your default editor.
    
    Opens ~/.rose/rose.config.yaml in vim (or $EDITOR if set).
    If the config file doesn't exist, run 'rose config init' first.
    """
    config_file = Path.home() / ".rose" / "rose.config.yaml"
    
    # Check if config file exists
    if not config_file.exists():
        Message.error(f"Configuration file not found: {config_file}")
        Message.error(f"Run [cyan]rose config init[/cyan] to create it first")
        raise typer.Exit(1)
    
    # Find suitable editor
    editor = _find_editor()
    
    if not editor:
        Message.error(f"No suitable editor found")
        Message.error(f"Please set EDITOR environment variable or install vim, nano, or code")
        Message.error(f"You can edit the file manually:")
        Message.error(f"  {config_file}")
        raise typer.Exit(1)

    
    try:
        Message.info(f"Opening configuration in {editor}...")
        result = subprocess.run([editor, str(config_file)])
        
        if result.returncode == 0:
            Message.success(f"Configuration file saved")
        
    except KeyboardInterrupt:
        Message.error(f"Editor cancelled")
    except Exception as e:
        Message.error(f"Error opening editor: {e}")
        logger.error(f"Config edit error: {e}", exc_info=True)
        raise typer.Exit(1)


def _find_editor() -> Optional[str]:
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


