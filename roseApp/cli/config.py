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
from rich.console import Console

from ..core.util import get_logger, set_app_mode, AppMode
from ..ui.theme import get_color

# Initialize
set_app_mode(AppMode.CLI)
logger = get_logger(__name__)
console = Console()

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
        console.print(f"[{get_color('success')}]✓[/{get_color('success')}] Created directory: {rose_dir}")
    
    # Check if file already exists
    if config_file.exists() and not force:
        console.print(f"[{get_color('warning')}]Configuration file already exists: {config_file}[/{get_color('warning')}]")
        console.print(f"Use [{get_color('accent')}]rose config init --force[/{get_color('accent')}] to overwrite")
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
            console.print(f"[{get_color('error')}]Could not find rose.config.default.yaml template[/{get_color('error')}]")
            console.print(f"[{get_color('muted')}]Searched in:[/{get_color('muted')}]")
            for loc in template_locations:
                console.print(f"  • {loc}")
            raise typer.Exit(1)
        
        # Copy the template file
        shutil.copy2(template_file, config_file)
        
        console.print(f"[{get_color('success')}]✓[/{get_color('success')}] Configuration initialized: [{get_color('accent')}]{config_file}[/{get_color('accent')}]")
        console.print(f"[{get_color('muted')}]Copied from: {template_file}[/{get_color('muted')}]")
        console.print(f"\n[{get_color('info')}]Edit your configuration:[/{get_color('info')}]")
        console.print(f"  [{get_color('accent')}]rose config edit[/{get_color('accent')}]")
        
    except Exception as e:
        console.print(f"[{get_color('error')}]Error initializing configuration: {e}[/{get_color('error')}]")
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
        console.print(f"[{get_color('warning')}]Configuration file not found: {config_file}[/{get_color('warning')}]")
        console.print(f"[{get_color('info')}]Run [{get_color('accent')}]rose config init[/{get_color('accent')}] to create it first[/{get_color('info')}]")
        raise typer.Exit(1)
    
    # Find suitable editor
    editor = _find_editor()
    
    if not editor:
        console.print(f"[{get_color('error')}]No suitable editor found[/{get_color('error')}]")
        console.print(f"[{get_color('muted')}]Please set EDITOR environment variable or install vim, nano, or code[/{get_color('muted')}]")
        console.print(f"\n[{get_color('info')}]You can edit the file manually:[/{get_color('info')}]")
        console.print(f"  {config_file}")
        raise typer.Exit(1)
    
    try:
        console.print(f"[{get_color('info')}]Opening configuration in {editor}...[/{get_color('info')}]")
        result = subprocess.run([editor, str(config_file)])
        
        if result.returncode == 0:
            console.print(f"[{get_color('success')}]✓[/{get_color('success')}] Configuration file saved")
        
    except KeyboardInterrupt:
        console.print(f"\n[{get_color('warning')}]Editor cancelled[/{get_color('warning')}]")
    except Exception as e:
        console.print(f"[{get_color('error')}]Error opening editor: {e}[/{get_color('error')}]")
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


