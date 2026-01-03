import yaml
from pathlib import Path
from typing import Dict, Optional
from textual.theme import Theme

# Default mapping for Base16 to Textual
# Textual keys: primary, secondary, accent, foreground, background, surface, error, success, warning
BASE16_MAP = {
    "primary": "base0D",
    "secondary": "base0E", # Purple often works as secondary
    "accent": "base09",
    "foreground": "base05",
    "background": "base00",
    "surface": "base01",
    "error": "base08",
    "success": "base0B",
    "warning": "base0A",
}

def load_themes() -> Dict[str, Theme]:
    """
    Load all themes from roseApp/config/themes/ directory.
    
    Returns:
        Dict[theme_name, Theme]
    """
    themes = {}
    
    # Locate config directory relative to this file
    # this file is in roseApp/tui/
    base_dir = Path(__file__).parent.parent / "config" / "themes"
    
    if not base_dir.exists():
        return {}

    for theme_file in base_dir.glob("rose.theme.*.yaml"):
        try:
            # Extract name: rose.theme.NAME.yaml
            parts = theme_file.name.split('.')
            if len(parts) >= 3:
                name = parts[2]
            else:
                continue
                
            with open(theme_file) as f:
                data = yaml.safe_load(f) or {}

            # Build Textual Theme arguments
            theme_args = {
                "name": name,
                "dark": True # Assuming all our current themes are dark
            }
            
            # Helper to get color: try direct name -> try base16 mapping -> default
            def get_color(key: str, default: str) -> str:
                # 1. Direct (key)
                if key in data: return data[key]
                # 2. Base16
                base_key = BASE16_MAP.get(key)
                if base_key and base_key in data: return data[base_key]
                # 3. Fallback/Default
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
            
        except Exception as e:
            # Log error? Silent fail for now to avoid breaking import
            print(f"Error loading theme {theme_file}: {e}")
            pass
            
    return themes

# Load all themes on module import
ALL_THEMES = load_themes()

# Backward compatibility / specific exports if needed
CLAUDE_THEME = ALL_THEMES.get("claude")
if not CLAUDE_THEME:
    # Fallback if file missing
    CLAUDE_THEME = Theme(name="claude", primary="#da7756", background="#252529", surface="#323236", accent="#e89e82", warning="#eebb85", error="#da7756", success="#76a67e", secondary="#83b8b8")
