"""
Theme configuration for the CLI tool.
This module contains color schemes and style definitions.
"""

from InquirerPy import get_style

# Color definitions
GREEN = "#98c379"
YELLOW = "#e5c07b"
BLUE = "#61afef"
PURPLE = "#c678dd"
ORANGE = "#e69875"
GRAY = "#5c6370"
DIM_WHITE = "#Fef2d5"
INPUT_GREEN = "#35A77c"

# Style configuration for InquirerPy
DEFAULT_STYLE = {
    "questionmark": YELLOW,
    "answermark": YELLOW,
    "answer": GREEN,
    "input": INPUT_GREEN,
    "question": PURPLE,
    "answered_question": "#9379e5",
    "instruction": ORANGE,
    "long_instruction": ORANGE,
    "pointer": DIM_WHITE,
    "checkbox": GREEN,
    "separator": "",
    "skipped": GRAY,
    "validator": "",
    "marker": GREEN,
    "fuzzy_prompt": PURPLE,
    "fuzzy_info": GREEN,
    "fuzzy_border": GREEN,
    "fuzzy_match": PURPLE,
    "spinner_pattern": YELLOW,
    "spinner_text": "",
}

# Create style instance
style = get_style(DEFAULT_STYLE, style_override=True) 