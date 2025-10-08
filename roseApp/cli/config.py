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

# Initialize
set_app_mode(AppMode.CLI)
logger = get_logger(__name__)
# console deprecated in v2.0

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
        console.print(f"[cyan]✓[/cyan] Created directory: {rose_dir}")
    
    # Check if file already exists
    if config_file.exists() and not force:
        console.print(f"[cyan]Configuration file already exists: {config_file}[/cyan]")
        console.print(f"Use [cyan]rose config init --force[/cyan] to overwrite")
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
            console.print(f"[cyan]Could not find rose.config.default.yaml template[/cyan]")
            console.print(f"[cyan]Searched in:[/cyan]")
            for loc in template_locations:
                console.print(f"  • {loc}")
            raise typer.Exit(1)
        
        # Copy the template file
        shutil.copy2(template_file, config_file)
        
        console.print(f"[cyan]✓[/cyan] Configuration initialized: [cyan]{config_file}[/cyan]")
        console.print(f"[cyan]Copied from: {template_file}[/cyan]")
        console.print(f"\n[cyan]Edit your configuration:[/cyan]")
        console.print(f"  [cyan]rose config edit[/cyan]")
        
    except Exception as e:
        console.print(f"[cyan]Error initializing configuration: {e}[/cyan]")
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
        console.print(f"[cyan]Configuration file not found: {config_file}[/cyan]")
        console.print(f"[cyan]Run [cyan]rose config init[/cyan] to create it first[/cyan]")
        raise typer.Exit(1)
    
    # Find suitable editor
    editor = _find_editor()
    
    if not editor:
        console.print(f"[cyan]No suitable editor found[/cyan]")
        console.print(f"[cyan]Please set EDITOR environment variable or install vim, nano, or code[/cyan]")
        console.print(f"\n[cyan]You can edit the file manually:[/cyan]")
        console.print(f"  {config_file}")
        raise typer.Exit(1)
    
    try:
        console.print(f"[cyan]Opening configuration in {editor}...[/cyan]")
        result = subprocess.run([editor, str(config_file)])
        
        if result.returncode == 0:
            console.print(f"[cyan]✓[/cyan] Configuration file saved")
        
    except KeyboardInterrupt:
        console.print(f"\n[cyan]Editor cancelled[/cyan]")
    except Exception as e:
        console.print(f"[cyan]Error opening editor: {e}[/cyan]")
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


