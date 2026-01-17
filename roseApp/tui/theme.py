import logging
import yaml
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from textual.theme import Theme

if TYPE_CHECKING:
    from textual.app import App

logger = logging.getLogger(__name__)

# Default mapping for Base16 to Textual
# Textual keys: primary, secondary, accent, foreground, background, surface, error, success, warning
BASE16_MAP = {
    "primary": "base0D",
    "secondary": "base0E",  # Purple often works as secondary
    "accent": "base09",
    "foreground": "base05",
    "background": "base00",
    "surface": "base01",
    "error": "base08",
    "success": "base0B",
    "warning": "base0A",
}


def _parse_theme_name(theme_file: str, default: str = "claude") -> str:
    """
    Parse theme name from theme file path.
    
    Args:
        theme_file: Theme file path like "rose.theme.nord.yaml"
        default: Default theme name if parsing fails
        
    Returns:
        Extracted theme name or default
    """
    parts = theme_file.split(".")
    if len(parts) >= 3 and parts[0] == "rose" and parts[1] == "theme":
        return parts[2]
    return default


def setup_app_theme(app: "App") -> None:
    """
    Setup theme for a Textual App using Rose theme configuration.
    
    This function registers all available themes and sets the active theme
    based on the user's configuration.
    
    Args:
        app: The Textual App instance to configure
    """
    from ..core.config import get_config
    
    # Register all themes
    for theme in ALL_THEMES.values():
        app.register_theme(theme)
    
    # Get configured theme
    config = get_config()
    theme_name = _parse_theme_name(config.theme_file)
    
    # Apply theme with fallback
    if theme_name in ALL_THEMES:
        app.theme = theme_name
    elif "claude" in ALL_THEMES:
        app.theme = "claude"


def load_themes() -> Dict[str, Theme]:
    """
    Load all themes from roseApp/config/themes/ directory.
    
    Returns:
        Dict mapping theme name to Theme instance
    """
    themes: Dict[str, Theme] = {}
    
    # Locate config directory relative to this file
    base_dir = Path(__file__).parent.parent / "config" / "themes"
    
    if not base_dir.exists():
        logger.warning("Themes directory not found: %s", base_dir)
        return {}

    for theme_file in base_dir.glob("rose.theme.*.yaml"):
        try:
            # Extract name from filename pattern: rose.theme.NAME.yaml
            parts = theme_file.name.split(".")
            if len(parts) >= 4 and parts[0] == "rose" and parts[1] == "theme":
                name = parts[2]
            else:
                logger.warning("Skipping malformed theme file: %s", theme_file)
                continue

            with open(theme_file) as f:
                data = yaml.safe_load(f) or {}

            # Build Textual Theme arguments
            theme_args = {
                "name": name,
                "dark": True  # Assuming all our current themes are dark
            }
            
            def get_color(key: str, default: str) -> str:
                """Get color from config with Base16 fallback."""
                if key in data:
                    return data[key]
                base_key = BASE16_MAP.get(key)
                if base_key and base_key in data:
                    return data[base_key]
                return default

            theme_args["primary"] = get_color("primary", "#0000ff")
            theme_args["secondary"] = get_color("secondary", "#888888")
            theme_args["accent"] = get_color("accent", "#ffa500")
            theme_args["foreground"] = get_color("foreground", "#ffffff")
            theme_args["background"] = get_color("background", "#000000")
            theme_args["surface"] = get_color("surface", "#222222")
            theme_args["error"] = get_color("error", "#ff0000")
            theme_args["success"] = get_color("success", "#00ff00")
            theme_args["warning"] = get_color("warning", "#ffff00")
            
            themes[name] = Theme(**theme_args)
            
        except yaml.YAMLError as e:
            logger.warning("YAML error loading theme %s: %s", theme_file, e)
        except OSError as e:
            logger.warning("IO error loading theme %s: %s", theme_file, e)
        except Exception as e:
            logger.warning("Unexpected error loading theme %s: %s", theme_file, e)
            
    return themes


# Load all themes on module import
ALL_THEMES = load_themes()

# Backward compatibility / specific exports if needed
CLAUDE_THEME = ALL_THEMES.get("claude")
if not CLAUDE_THEME:
    # Fallback if file missing
    CLAUDE_THEME = Theme(
        name="claude",
        primary="#da7756",
        background="#252529",
        surface="#323236",
        accent="#e89e82",
        warning="#eebb85",
        error="#da7756",
        success="#76a67e",
        secondary="#83b8b8",
    )

