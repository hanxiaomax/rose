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
def theme():
    """
    Interactively select and apply a theme.
    """
    out = get_output()
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from ..core.config import get_config
    import yaml
    
    # 1. Find available themes
    themes_dir = Path(__file__).parent.parent / "config" / "themes"
    if not themes_dir.exists():
        out.error("Themes directory not found", details=str(themes_dir))
        raise typer.Exit(1)
        
    theme_files = sorted(list(themes_dir.glob("*.yaml")))
    
    if not theme_files:
        out.error("No themes found in directory", details=str(themes_dir))
        raise typer.Exit(1)

    from ..core.output import ThemeColors
    
    # Display Preview Table
    out.section("Available Themes")
    preview_rows = []
    
    for f_path in theme_files:
        try:
            with open(f_path) as f:
                data = yaml.safe_load(f) or {}
                
            # Use shared logic to resolve colors
            tc = ThemeColors(data)
            
            name = f_path.name.replace("rose.theme.", "").replace(".yaml", "")
            
            # Rich styling for preview - Compact blocks for all colors
            # Pri, Acc, Suc, War, Err, Inf, Mut, Hgh
            preview_block = (
                f"[{tc.primary}]██[/{tc.primary}] "
                f"[{tc.accent}]██[/{tc.accent}] "
                f"[{tc.success}]██[/{tc.success}] "
                f"[{tc.warning}]██[/{tc.warning}] "
                f"[{tc.error}]██[/{tc.error}] "
                f"[{tc.info}]██[/{tc.info}] "
                f"[{tc.muted}]██[/{tc.muted}] "
                f"[{tc.highlight}]██[/{tc.highlight}]"
            )
            preview_rows.append([name, preview_block])
        except Exception:
             preview_rows.append([f_path.name, "Error reading file"])
             
    out.table(None, ["Theme", "Preview (Pri/Acc/Suc/War/Err/Inf/Mut/Hgh)"], preview_rows)
    out.newline()

    # Generate choices (simple filenames)
    choices = [Choice(value=f.name, name=f.name) for f in theme_files]

    # 2. Get current config to know active theme
    config = get_config()
    current_theme = config.theme_file
    
    # Find active choice index
    default_choice = None
    for c in choices:
        if c.value == current_theme:
            default_choice = c.value
            break
    
    # 3. Prompt user
    try:
        selected_theme = inquirer.select(
            message="Select a theme (Primary | Accent | Success | Bg):",
            choices=choices,
            default=default_choice,
            pointer="➤",
        ).execute()
    except KeyboardInterrupt:
        out.warning("Cancelled")
        raise typer.Exit(0)
        
    if not selected_theme:
        return

    # 4. Update configuration file
    # We need to find WHICH config file is active to update it
    # If using default (no file), we should probably init one?
    # Or just tell user?
    
    loaded_path = getattr(config, '_loaded_config_path', None)
    
    if not loaded_path:
        out.warning("No configuration file found.")
        if inquirer.confirm("Create new configuration file at ~/.rose/rose.config.yaml?", default=True).execute():
            # Trigger init
            from .config import init
            init(force=False)
            # Re-locate
            loaded_path = Path.home() / ".rose" / "rose.config.yaml"
        else:
            out.error("Cannot save theme selection without a configuration file.")
            raise typer.Exit(1)

    # Update the file
    try:
        # Read content
        lines = []
        with open(loaded_path, 'r') as f:
            lines = f.readlines()
            
        # Modify theme_file line
        new_lines = []
        updated = False
        theme_line_regex = "theme_file:"
        
        for line in lines:
            if line.strip().startswith("theme_file:"):
                new_lines.append(f"theme_file: {selected_theme}\n")
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            # Append if missing
            new_lines.append(f"\ntheme_file: {selected_theme}\n")
            
        # Write back
        with open(loaded_path, 'w') as f:
            f.writelines(new_lines)
            
        out.success(f"Theme updated to: {selected_theme}")
        out.info(f"Updated config file: {out.format_path(loaded_path)}")
        
    except Exception as e:
        out.error(f"Failed to update configuration: {e}")
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
        
        # Theme Preview
        out.newline()
        out.section("Theme Preview")
        
        theme_colors = [
            ("Primary", out.theme.primary),
            ("Accent", out.theme.accent),
            ("Success", out.theme.success),
            ("Warning", out.theme.warning),
            ("Error", out.theme.error),
            ("Info", out.theme.info),
            ("Muted", out.theme.muted),
            ("Highlight", out.theme.highlight),
            ("Path", out.theme.path),
        ]
        
        for name, color in theme_colors:
            # Create a block of color
            block = "██████"
            out.print(f"  [{config.theme_file}]{name.ljust(12)}[/]: [{color}]{block}[/{color}]  ({color})")
        
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
