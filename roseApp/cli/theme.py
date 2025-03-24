"""
Theme configuration for the CLI tool.
This module contains color schemes and style definitions.
"""

from InquirerPy import get_style

# Color definitions
SUCCESS = "#35A77c"
YELLOW = "#DDA853"
INFO = "#5B99C2"
ACCENT = "#DF6D2D"
PRIMARY = "#F9DBBA"
GRAY = "#F3F7EC"
DIM_INFO = "#8D77AB"
INPUT_SECONDARY = "#FFF5E0"

# Style configuration for InquirerPy
DEFAULT_STYLE = {
    "questionmark": PRIMARY,
    "answermark": PRIMARY,
    "answer": PRIMARY,
    "input": INPUT_SECONDARY,
    "question": ACCENT,
    "answered_question": "#FFFAE6",
    "instruction": DIM_INFO,
    "long_instruction": DIM_INFO,
    "pointer": PRIMARY,
    "checkbox": ACCENT,
    "separator": "",
    "skipped": GRAY,
    "validator": "",
    "marker": ACCENT,
    "fuzzy_prompt": PRIMARY,
    "fuzzy_info": PRIMARY,
    "fuzzy_border": PRIMARY,
    "fuzzy_match": ACCENT,
    "spinner_pattern": YELLOW,
    "spinner_text": "",
}

# Create style instance
style = get_style(DEFAULT_STYLE, style_override=True) 