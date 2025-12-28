"""
Configuration management CLI commands for Rose.

Provides commands to initialize and edit Rose configuration.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import typer

from ..core.logging import get_logger
from ..core.output import get_output

# Initialize logger
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
    out = get_output()
    
    # Fixed output location
    rose_dir = Path.home() / ".rose"
    config_file = rose_dir / "rose.config.yaml"
    
    # Check if file already exists
    if config_file.exists() and not force:
        out.warning(f"Configuration file already exists: {config_file}")
        out.error(
            "File exists",
            details="Use --force flag to overwrite"
        )
        raise typer.Exit(1)
    
    try:
        # Create .rose directory if it doesn't exist
        created_dir = False
        if not rose_dir.exists():
            rose_dir.mkdir(parents=True, exist_ok=True)
            created_dir = True
            out.info(f"Created directory: {rose_dir}")
        
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
            out.error(
                "Could not find rose.config.default.yaml template",
                details="Template not found in expected locations"
            )
            raise typer.Exit(1)
        
        # Copy the template file
        out.info(f"Copying template from: {template_file}")
        shutil.copy2(template_file, config_file)
        
        # Success
        out.success(f"Configuration initialized: {config_file}")
        
        if created_dir:
            out.info(f"Created new directory: {rose_dir}")
        
    except typer.Exit:
        raise
    except Exception as e:
        out.error(f"Error initializing configuration: {str(e)}")
        logger.error(f"Config init error: {e}", exc_info=True)
        raise typer.Exit(1)


@app.command()
def edit():
    """
    Edit Rose configuration file in your default editor.
    
    Opens ~/.rose/rose.config.yaml in vim (or $EDITOR if set).
    If the config file doesn't exist, run 'rose config init' first.
    """
    out = get_output()
    
    config_file = Path.home() / ".rose" / "rose.config.yaml"
    
    # Check if config file exists
    if not config_file.exists():
        out.error(
            f"Configuration file not found: {config_file}",
            details="Run 'rose config init' to create it first"
        )
        raise typer.Exit(1)
    
    # Find suitable editor
    editor = _find_editor()
    
    if not editor:
        out.error(
            "No suitable editor found",
            details=f"Set EDITOR env var or install vim/nano. File: {config_file}"
        )
        raise typer.Exit(1)
    
    try:
        out.info(f"Opening {config_file} with {editor}...")
        result = subprocess.run([editor, str(config_file)])
        
        if result.returncode == 0:
            out.success("Configuration file edited")
        else:
            out.warning(f"Editor exited with code: {result.returncode}")
        
    except KeyboardInterrupt:
        out.warning("Editor cancelled by user")
        raise typer.Exit(1)
    except Exception as e:
        out.error(f"Error opening editor: {str(e)}")
        logger.error(f"Config edit error: {e}", exc_info=True)
        raise typer.Exit(1)


@app.command()
def show():
    """
    Show current configuration settings.
    """
    out = get_output()
    
    try:
        from ..core.config import get_config
        config = get_config()
        
        out.section("Rose Configuration")
        
        # Show loaded config path
        loaded_path = getattr(config, '_loaded_config_path', None)
        if loaded_path:
            out.info(f"Loaded from: {loaded_path}")
        else:
            out.info("Using default configuration")
        
        out.newline()
        
        # Display configuration values
        out.key_value({
            "Parallel workers": config.parallel_workers,
            "Memory limit": f"{config.memory_limit_mb} MB",
            "Cache enabled": config.enable_cache,
            "Verbose default": config.verbose_default,
            "Build index default": config.build_index_default,
            "Compression default": config.compression_default.value,
            "Log level": config.log_level.value,
            "Theme file": config.theme_file,
            "Colors enabled": config.enable_colors,
        }, title="Settings")
        
        out.newline()
        out.key_value({
            "Cache dir": str(config.cache_dir),
            "Logs dir": str(config.logs_dir),
        }, title="Directories")
        
    except Exception as e:
        out.error(f"Error reading configuration: {str(e)}")
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
