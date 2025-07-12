"""
Theme configuration for the CLI tool.
This module provides backward compatibility with the unified theme system.
"""

# Import from unified theme system
from ..core.theme import (
    theme,
    SUCCESS, WARNING, INFO, ACCENT, PRIMARY, SECONDARY, ERROR, 
    GRAY, DIM_INFO, INPUT_SECONDARY, style
)

# Additional CLI-specific color aliases for backward compatibility
YELLOW = WARNING  # Map old YELLOW to new WARNING 