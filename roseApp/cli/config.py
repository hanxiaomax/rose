"""
Configuration management CLI commands for Rose.

Provides commands to initialize and edit Rose configuration.
Headless NDJSON mode - pure event emission.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import typer

from ..core.logging import get_logger
from ..core.event_emitter import E, ndjson_command

# Initialize logger
logger = get_logger(__name__)


app = typer.Typer(help="Configuration management commands")

@app.command()
@ndjson_command("config-init")
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration file")
):
    """
    Initialize Rose configuration by copying default config to ~/.rose/rose.config.yaml
    
    This command creates the Rose configuration directory and copies the default
    configuration template.
    """
    # Using global E emitter (context set by @ndjson_command)
    
    # Fixed output location
    rose_dir = Path.home() / ".rose"
    config_file = rose_dir / "rose.config.yaml"
    
    # Check if file already exists
    if config_file.exists() and not force:
        E.data(
            data={
                "config_file": str(config_file),
                "exists": True,
                "force": False
            },
            label="init_check"
        )
        E.error(
            "CONFIG_EXISTS",
            f"Configuration file already exists: {config_file}",
            details={
                "config_file": str(config_file),
                "suggestion": "Use --force flag to overwrite"
            }
        )
        raise typer.Exit(1)
    
    try:
        # Create .rose directory if it doesn't exist
        created_dir = False
        if not rose_dir.exists():
            rose_dir.mkdir(parents=True, exist_ok=True)
            created_dir = True
        
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
            E.error(
                "TEMPLATE_NOT_FOUND",
                "Could not find rose.config.default.yaml template",
                details={
                    "searched_locations": [str(loc) for loc in template_locations]
                }
            )
            raise typer.Exit(1)
        
        # Emit initialization plan
        E.data(
            data={
                "rose_dir": str(rose_dir),
                "config_file": str(config_file),
                "template_file": str(template_file),
                "created_dir": created_dir,
                "force": force
            },
            label="init_plan"
        )
        
        # Copy the template file
        shutil.copy2(template_file, config_file)
        
        # Emit success
        E.done({
            "config_file": str(config_file),
            "template_file": str(template_file),
            "created_dir": created_dir,
            "action": "initialized"
        })
        
    except typer.Exit:
        raise
    except Exception as e:
        E.error(
            "CONFIG_INIT_ERROR",
            f"Error initializing configuration: {str(e)}",
            details={"config_file": str(config_file)}
        )
        logger.error(f"Config init error: {e}", exc_info=True)
        raise typer.Exit(1)

@app.command()
@ndjson_command("config-edit")
def edit():
    """
    Edit Rose configuration file in your default editor.
    
    Opens ~/.rose/rose.config.yaml in vim (or $EDITOR if set).
    If the config file doesn't exist, run 'rose config init' first.
    
    Note: This command is interactive and may not work in pure headless environments.
    """
    # Using global E emitter (context set by @ndjson_command)
    
    config_file = Path.home() / ".rose" / "rose.config.yaml"
    
    # Check if config file exists
    if not config_file.exists():
        E.error(
            "CONFIG_NOT_FOUND",
            f"Configuration file not found: {config_file}",
            details={
                "config_file": str(config_file),
                "suggestion": "Run 'rose config init' to create it first"
            }
        )
        raise typer.Exit(1)
    
    # Find suitable editor
    editor = _find_editor()
    
    if not editor:
        E.error(
            "NO_EDITOR",
            "No suitable editor found",
            details={
                "config_file": str(config_file),
                "suggestions": [
                    "Set EDITOR environment variable",
                    "Install vim, nano, or code",
                    f"Edit the file manually: {config_file}"
                ]
            }
        )
        raise typer.Exit(1)

    
    try:
        # Emit edit plan
        E.data(
            data={
                "config_file": str(config_file),
                "editor": editor,
                "action": "opening_editor"
            },
            label="edit_plan"
        )
        
        result = subprocess.run([editor, str(config_file)])
        
        # Emit done
        E.done({
            "config_file": str(config_file),
            "editor": editor,
            "exit_code": result.returncode,
            "action": "edited"
        })
        
    except KeyboardInterrupt:
        E.error(
            "EDIT_CANCELLED",
            "Editor cancelled by user",
            details={"config_file": str(config_file)}
        )
        raise typer.Exit(1)
    except Exception as e:
        E.error(
            "EDIT_ERROR",
            f"Error opening editor: {str(e)}",
            details={
                "config_file": str(config_file),
                "editor": editor
            }
        )
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


