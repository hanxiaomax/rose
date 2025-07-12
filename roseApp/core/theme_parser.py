#!/usr/bin/env python3
"""
Simplified theme parser for ROS bag processing tools
CLI uses dark theme colors, HTML/plots use light theme colors
"""

import re
from typing import Dict, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ThemeColors:
    """Container for theme color definitions"""
    # Core colors
    background: str
    foreground: str
    primary: str
    secondary: str
    accent: str
    destructive: str
    border: str
    muted_foreground: str
    
    # Chart colors
    chart_1: str
    chart_2: str
    chart_3: str
    chart_4: str
    chart_5: str


class ThemeParser:
    """Simplified theme parser for CSS theme definitions"""
    
    def __init__(self, css_file_path: str = None):
        """Initialize with CSS file path"""
        if css_file_path is None:
            css_file_path = Path(__file__).parent / "index.css"
        
        self.css_file_path = Path(css_file_path)
        self.light_colors = None
        self.dark_colors = None
        self._parse_css()
    
    def _parse_css(self):
        """Parse the CSS file and extract theme variables"""
        if not self.css_file_path.exists():
            raise FileNotFoundError(f"CSS file not found: {self.css_file_path}")
        
        content = self.css_file_path.read_text(encoding='utf-8')
        
        # Parse light theme (:root)
        root_match = re.search(r':root\s*\{([^}]+)\}', content, re.DOTALL)
        if root_match:
            self.light_colors = self._parse_variables(root_match.group(1))
        
        # Parse dark theme (.dark)
        dark_match = re.search(r'\.dark\s*\{([^}]+)\}', content, re.DOTALL)
        if dark_match:
            self.dark_colors = self._parse_variables(dark_match.group(1))
    
    def _parse_variables(self, css_block: str) -> ThemeColors:
        """Parse CSS variables from a CSS block"""
        variables = {}
        
        # Extract CSS variables
        var_pattern = r'--([a-zA-Z0-9-]+):\s*([^;]+);'
        matches = re.findall(var_pattern, css_block)
        
        for name, value in matches:
            value = value.strip()
            variables[name.replace('-', '_')] = value
        
        # Create ThemeColors object with only essential colors
        return ThemeColors(
            background=variables.get('background', '#ffffff'),
            foreground=variables.get('foreground', '#000000'),
            primary=variables.get('primary', '#ff7e5f'),
            secondary=variables.get('secondary', '#ffedea'),
            accent=variables.get('accent', '#feb47b'),
            destructive=variables.get('destructive', '#e63946'),
            border=variables.get('border', '#ffe0d6'),
            muted_foreground=variables.get('muted_foreground', '#78716c'),
            chart_1=variables.get('chart_1', '#ff7e5f'),
            chart_2=variables.get('chart_2', '#feb47b'),
            chart_3=variables.get('chart_3', '#ffcaa7'),
            chart_4=variables.get('chart_4', '#ffad8f'),
            chart_5=variables.get('chart_5', '#ce6a57'),
        )
    
    def get_cli_colors(self) -> Dict[str, str]:
        """Get colors for CLI (dark theme)"""
        colors = self.dark_colors if self.dark_colors else self.light_colors
        return {
            'primary': colors.primary,
            'secondary': colors.secondary,
            'accent': colors.accent,
            'warning': colors.chart_4,
            'error': colors.destructive,
            'success': colors.chart_3,
            'info': colors.chart_1,
            'text_primary': colors.foreground,
            'text_secondary': colors.muted_foreground,
            'background': colors.background,
            'border': colors.border,
        }
    
    def get_plot_colors(self) -> list:
        """Get colors for plotting (light theme)"""
        colors = self.light_colors if self.light_colors else self.dark_colors
        return [
            colors.chart_1,
            colors.chart_2,
            colors.chart_3,
            colors.chart_4,
            colors.chart_5,
            colors.primary,
            colors.accent,
            colors.secondary,
        ]
    
    def get_html_colors(self) -> Dict[str, str]:
        """Get colors for HTML export (light theme)"""
        colors = self.light_colors if self.light_colors else self.dark_colors
        return {
            'background': colors.background,
            'foreground': colors.foreground,
            'primary': colors.primary,
            'secondary': colors.secondary,
            'accent': colors.accent,
            'destructive': colors.destructive,
            'border': colors.border,
            'muted_foreground': colors.muted_foreground,
        }
    
    def to_inquirer_style(self) -> Dict[str, str]:
        """Convert to InquirerPy style format (dark theme for CLI)"""
        colors = self.dark_colors if self.dark_colors else self.light_colors
        return {
            "questionmark": colors.primary,
            "answermark": colors.primary,
            "answer": colors.primary,
            "question": colors.accent,
            "answered_question": colors.secondary,
            "instruction": colors.muted_foreground,
            "pointer": colors.primary,
            "checkbox": colors.accent,
            "marker": colors.accent,
            "fuzzy_prompt": colors.primary,
            "fuzzy_info": colors.primary,
            "fuzzy_border": colors.primary,
            "fuzzy_match": colors.accent,
            "spinner_pattern": colors.chart_4,
        }
    
    def to_matplotlib_style(self) -> Dict[str, Any]:
        """Convert to matplotlib style (light theme for plots)"""
        colors = self.light_colors if self.light_colors else self.dark_colors
        return {
            'axes.facecolor': colors.background,
            'axes.edgecolor': colors.border,
            'axes.labelcolor': colors.foreground,
            'axes.titlecolor': colors.foreground,
            'figure.facecolor': colors.background,
            'figure.edgecolor': colors.background,
            'text.color': colors.foreground,
            'xtick.color': colors.muted_foreground,
            'ytick.color': colors.muted_foreground,
            'grid.color': colors.border,
            'axes.spines.left': True,
            'axes.spines.bottom': True,
            'axes.spines.top': False,
            'axes.spines.right': False,
        }
    
    def generate_html_css(self) -> str:
        """Generate CSS for HTML export (light theme)"""
        colors = self.light_colors if self.light_colors else self.dark_colors
        
        return f"""
        :root {{
            --background: {colors.background};
            --foreground: {colors.foreground};
            --primary: {colors.primary};
            --secondary: {colors.secondary};
            --accent: {colors.accent};
            --destructive: {colors.destructive};
            --border: {colors.border};
            --muted-foreground: {colors.muted_foreground};
            --chart-1: {colors.chart_1};
            --chart-2: {colors.chart_2};
            --chart-3: {colors.chart_3};
            --chart-4: {colors.chart_4};
            --chart-5: {colors.chart_5};
            --radius: 0.625rem;
        }}
        
        body {{
            font-family: Montserrat, sans-serif;
            background-color: var(--background);
            color: var(--foreground);
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }}
        
        .bg-background {{ background-color: var(--background); }}
        .bg-primary {{ background-color: var(--primary); }}
        .bg-secondary {{ background-color: var(--secondary); }}
        .bg-accent {{ background-color: var(--accent); }}
        
        .text-foreground {{ color: var(--foreground); }}
        .text-primary {{ color: var(--primary); }}
        .text-secondary {{ color: var(--secondary); }}
        .text-accent {{ color: var(--accent); }}
        .text-destructive {{ color: var(--destructive); }}
        .text-muted {{ color: var(--muted-foreground); }}
        
        .border {{ border: 1px solid var(--border); }}
        .rounded {{ border-radius: var(--radius); }}
        
        .p-4 {{ padding: 1rem; }}
        .p-6 {{ padding: 1.5rem; }}
        .mb-4 {{ margin-bottom: 1rem; }}
        .mt-4 {{ margin-top: 1rem; }}
        
        .text-lg {{ font-size: 1.125rem; }}
        .text-xl {{ font-size: 1.25rem; }}
        .text-2xl {{ font-size: 1.5rem; }}
        .font-bold {{ font-weight: 700; }}
        
        .flex {{ display: flex; }}
        .items-center {{ align-items: center; }}
        .justify-between {{ justify-content: space-between; }}
        
        .w-full {{ width: 100%; }}
        .max-w-4xl {{ max-width: 56rem; }}
        .mx-auto {{ margin-left: auto; margin-right: auto; }}
        
        .shadow {{ box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1); }}
        .transition-colors {{ transition: color, background-color 0.15s; }}
        """


# Global theme parser instance
theme_parser = ThemeParser()


def get_cli_colors() -> Dict[str, str]:
    """Get CLI colors (dark theme)"""
    return theme_parser.get_cli_colors()


def get_plot_colors() -> list:
    """Get plot colors (light theme)"""
    return theme_parser.get_plot_colors()


def get_html_colors() -> Dict[str, str]:
    """Get HTML colors (light theme)"""
    return theme_parser.get_html_colors()


def get_inquirer_style():
    """Get InquirerPy style (dark theme for CLI)"""
    try:
        from InquirerPy import get_style
        return get_style(theme_parser.to_inquirer_style(), style_override=True)
    except ImportError:
        return None


def apply_matplotlib_style():
    """Apply matplotlib style (light theme for plots)"""
    try:
        import matplotlib.pyplot as plt
        style_dict = theme_parser.to_matplotlib_style()
        for key, value in style_dict.items():
            plt.rcParams[key] = value
    except ImportError:
        pass


def generate_html_css() -> str:
    """Generate CSS for HTML export (light theme)"""
    return theme_parser.generate_html_css() 