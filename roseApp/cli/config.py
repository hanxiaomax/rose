"""
Configuration CLI command for Rose.

Single command that launches inline TUI for configuration editing.
"""

import shutil
from pathlib import Path
from typing import Optional, List
import typer
import yaml

from ..core.logging import get_logger
from ..core.output import get_output, StepManager

logger = get_logger(__name__)

# Simple command instead of Typer app with subcommands
app = typer.Typer(help="Edit Rose configuration")


def _find_themes() -> List[str]:
    """Find available theme files."""
    themes_dir = Path(__file__).parent.parent / "config" / "themes"
    if themes_dir.exists():
        return sorted([f.name for f in themes_dir.glob("*.yaml")])
    return ["rose.theme.default.yaml"]


def _get_config_path() -> Path:
    """Get the global config file path (~/.rose/rose.config.yaml)."""
    return Path.home() / ".rose" / "rose.config.yaml"


def _ensure_config_exists(config_path: Path) -> bool:
    """Ensure config file exists, copy from default if needed."""
    if config_path.exists():
        return True
    
    # Find default template
    template_locations = [
        Path(__file__).parent.parent / "config" / "rose.config.default.yaml",
        Path(__file__).parent.parent.parent / "rose.config.default.yaml",
    ]
    
    for template in template_locations:
        if template.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template, config_path)
            return True
    
    return False


def _load_config(config_path: Path) -> dict:
    """Load config from YAML file."""
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config(config_path: Path, data: dict) -> None:
    """Save config to YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with comments
    content = """# Rose Configuration
#
# Environment variables: ROSE_<SETTING_NAME> (e.g., ROSE_PARALLEL_WORKERS=8)

# Performance
parallel_workers: {parallel_workers}
memory_limit_mb: {memory_limit_mb}

# Defaults
compression_default: {compression_default}
verbose_default: {verbose_default}
build_index_default: {build_index_default}

# Logging
log_level: {log_level}
log_to_file: {log_to_file}

# UI
theme_file: {theme_file}
enable_colors: {enable_colors}

# Directories
output_directory: {output_directory}
""".format(**data)
    
    with open(config_path, 'w') as f:
        f.write(content)


@app.callback(invoke_without_command=True)
def config(ctx: typer.Context):
    """
    Edit Rose configuration interactively.
    
    Opens inline TUI for editing configuration.
    Configuration is stored in ~/.rose/rose.config.yaml
    """
    out = get_output()
    
    # Global config path
    config_path = _get_config_path()
    config_created = False
    
    # Ensure config exists
    if not config_path.exists():
        if _ensure_config_exists(config_path):
            config_created = True
            out.success(f"Created new config: {config_path}")
        else:
            out.error("Could not create configuration file")
            raise typer.Exit(1)
    
    # Load configuration using core config system
    from ..core.config import RoseConfig
    loaded_config = RoseConfig.load(config_path)
    
    # Convert loaded config to dict for TUI
    # Include all fields from the config object
    config_data = {}
    for field_name in loaded_config.__fields__.keys():
        value = getattr(loaded_config, field_name, None)
        # Convert enums to their string values
        if hasattr(value, 'value'):
            value = value.value
        # Convert Path to string
        elif isinstance(value, Path):
            value = str(value)
        config_data[field_name] = value
    
    # Also load raw YAML to preserve any extra user-defined fields
    raw_yaml = _load_config(config_path)
    for key, value in raw_yaml.items():
        if key not in config_data:
            config_data[key] = value
    
    # Get available themes
    themes = _find_themes()
    
    # Show active config file
    out.section("Configuration")
    out.key_value({"Active config": out.format_path(str(config_path))})
    out.newline()
    
    # Run TUI
    from ..tui.config_app import run_config_app
    
    result = run_config_app(config_data, themes, config_path=str(config_path))
    
    if result:
        # Merge result with any extra fields from raw YAML
        final_config = {**raw_yaml}
        for key, value in result.items():
            final_config[key] = value
        _save_config(config_path, final_config)
        out.newline()
        out.success(f"Configuration saved to {out.format_path(str(config_path))}")
    else:
        out.newline()
        out.info("Configuration unchanged")

