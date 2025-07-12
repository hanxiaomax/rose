#!/usr/bin/env python3
"""
Unified theme system for the Rose application
Provides consistent colors across CLI, TUI, and plotting modules
"""

from typing import Dict, List, Any, Optional
from InquirerPy import get_style
from textual.theme import Theme
from textual.color import Color

class RoseTheme:
    """Unified theme class for Rose application"""
    
    # Core color palette - inspired by cassette theme
    PRIMARY = "#b1b329"      # Lime green
    SECONDARY = "#008001"    # Dark green  
    ACCENT = "#9b50b7"       # Purple
    WARNING = "#DDA853"      # Gold/Yellow
    ERROR = "#FF4500"        # Orange red
    SUCCESS = "#35A77c"      # Teal green
    INFO = "#5B99C2"         # Blue
    
    # Surface colors
    BACKGROUND = "#002f33"   # Dark teal
    FOREGROUND = "#FAF0E6"   # Light cream
    SURFACE = "#262626"      # Dark gray
    PANEL = "#333333"        # Light gray
    
    # Text colors
    TEXT_PRIMARY = "#FAF0E6"     # Light cream
    TEXT_SECONDARY = "#C0C0C0"   # Silver
    TEXT_DIM = "#8D77AB"         # Dim purple
    TEXT_MUTED = "#666666"       # Gray
    
    # Data visualization colors (for plots)
    PLOT_COLORS = [
        "#b1b329",  # Primary lime
        "#9b50b7",  # Accent purple
        "#008001",  # Secondary green
        "#DDA853",  # Warning gold
        "#5B99C2",  # Info blue
        "#35A77c",  # Success teal
        "#FF4500",  # Error orange
        "#C0C0C0",  # Silver
    ]
    
    # Rich console color mappings
    RICH_COLORS = {
        'primary': PRIMARY,
        'secondary': SECONDARY,
        'accent': ACCENT,
        'warning': WARNING,
        'error': ERROR,
        'success': SUCCESS,
        'info': INFO,
        'text_primary': TEXT_PRIMARY,
        'text_secondary': TEXT_SECONDARY,
        'text_dim': TEXT_DIM,
        'text_muted': TEXT_MUTED,
    }
    
    # InquirerPy style configuration
    INQUIRER_STYLE = {
        "questionmark": PRIMARY,
        "answermark": PRIMARY,
        "answer": PRIMARY,
        "input": "#FFF5E0",
        "question": ACCENT,
        "answered_question": "#FFFAE6",
        "instruction": TEXT_DIM,
        "long_instruction": TEXT_DIM,
        "pointer": PRIMARY,
        "checkbox": ACCENT,
        "separator": "",
        "skipped": TEXT_MUTED,
        "validator": "",
        "marker": ACCENT,
        "fuzzy_prompt": PRIMARY,
        "fuzzy_info": PRIMARY,
        "fuzzy_border": PRIMARY,
        "fuzzy_match": ACCENT,
        "spinner_pattern": WARNING,
        "spinner_text": "",
    }
    
    # Matplotlib style configuration
    MATPLOTLIB_STYLE = {
        'axes.facecolor': BACKGROUND,
        'axes.edgecolor': TEXT_SECONDARY,
        'axes.labelcolor': TEXT_PRIMARY,
        'axes.titlecolor': TEXT_PRIMARY,
        'figure.facecolor': BACKGROUND,
        'figure.edgecolor': BACKGROUND,
        'text.color': TEXT_PRIMARY,
        'xtick.color': TEXT_SECONDARY,
        'ytick.color': TEXT_SECONDARY,
        'grid.color': TEXT_MUTED,
        'axes.spines.left': True,
        'axes.spines.bottom': True,
        'axes.spines.top': False,
        'axes.spines.right': False,
    }
    
    # Plotly template configuration
    PLOTLY_TEMPLATE = {
        'layout': {
            'paper_bgcolor': BACKGROUND,
            'plot_bgcolor': BACKGROUND,
            'font': {'color': TEXT_PRIMARY},
            'title': {'font': {'color': TEXT_PRIMARY}},
            'xaxis': {
                'gridcolor': TEXT_MUTED,
                'linecolor': TEXT_SECONDARY,
                'tickcolor': TEXT_SECONDARY,
                'title': {'font': {'color': TEXT_PRIMARY}},
                'tickfont': {'color': TEXT_SECONDARY},
            },
            'yaxis': {
                'gridcolor': TEXT_MUTED,
                'linecolor': TEXT_SECONDARY,
                'tickcolor': TEXT_SECONDARY,
                'title': {'font': {'color': TEXT_PRIMARY}},
                'tickfont': {'color': TEXT_SECONDARY},
            },
            'colorway': PLOT_COLORS,
        }
    }
    
    @classmethod
    def get_rich_color(cls, color_name: str) -> str:
        """Get a Rich console color by name"""
        return cls.RICH_COLORS.get(color_name, cls.TEXT_PRIMARY)
    
    @classmethod
    def get_plot_color(cls, index: int) -> str:
        """Get a plot color by index (cycles through available colors)"""
        return cls.PLOT_COLORS[index % len(cls.PLOT_COLORS)]
    
    @classmethod
    def get_inquirer_style(cls):
        """Get InquirerPy style configuration"""
        return get_style(cls.INQUIRER_STYLE, style_override=True)
    
    @classmethod
    def get_textual_theme(cls, theme_name: str = "cassette-dark") -> Theme:
        """Get Textual theme configuration"""
        return Theme(
            name=theme_name,
            primary=cls.PRIMARY,
            secondary=cls.SECONDARY,
            accent=cls.ACCENT,
            background=cls.BACKGROUND,
            foreground=cls.FOREGROUND,
            success=cls.SUCCESS,
            warning=cls.WARNING,
            error=cls.ERROR,
            surface=cls.SURFACE,
            panel=cls.PANEL,
            dark=True,
            variables={
                "border": f"{cls.PRIMARY} 60%",
                "scrollbar": cls.BACKGROUND,
                "button-background": cls.PRIMARY,
                "button-color-foreground": cls.BACKGROUND,
                "footer-key-foreground": cls.ACCENT,
                "input-cursor-background": cls.WARNING,
                "datatable--header-cursor": cls.WARNING,
                "button-focus-text-style": "bold",
            }
        )
    
    @classmethod
    def apply_matplotlib_style(cls):
        """Apply matplotlib style configuration"""
        try:
            import matplotlib.pyplot as plt
            plt.style.use('dark_background')
            for key, value in cls.MATPLOTLIB_STYLE.items():
                plt.rcParams[key] = value
        except ImportError:
            pass
    
    @classmethod
    def get_plotly_template(cls) -> Dict[str, Any]:
        """Get Plotly template configuration"""
        return cls.PLOTLY_TEMPLATE

# Create global theme instance
theme = RoseTheme()

# Backward compatibility exports
SUCCESS = theme.SUCCESS
WARNING = theme.WARNING
INFO = theme.INFO
ACCENT = theme.ACCENT
PRIMARY = theme.PRIMARY
SECONDARY = theme.SECONDARY
ERROR = theme.ERROR
GRAY = theme.TEXT_MUTED
DIM_INFO = theme.TEXT_DIM
INPUT_SECONDARY = "#FFF5E0"

# Export style for backward compatibility
style = theme.get_inquirer_style() 