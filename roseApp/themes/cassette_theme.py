from textual.color import Color
from textual.theme import Theme

# Dark Theme (Terminal-safe)
CASSETTE_THEME_DARK = Theme(
    name="cassette-dark",
    primary="#00FF00",        # ansi_bright_green (荧光绿)
    secondary="#0000FF",     # ansi_bright_blue (电子蓝)
    accent="#FF8C00",        # darkorange (工业橙)
    background="#1A1A1A",    # grey10 (工业黑)
    foreground="#B2B2B2",    # grey70 (金属银)
    success="#008000",       # ansi_green (信号绿)
    warning="#FFFF00",       # ansi_yellow (警示黄)
    error="#FF0000",        # ansi_red (警报红)
    surface="#262626",      # grey15 (机械灰)
    panel="#333333",        # grey20 (工业灰)
    dark=True,
    variables={
        "border": "#00FFFF 60%",  # ansi_bright_cyan
        "scrollbar": "#4D4D4D",   # grey30
        "link-color": "#00FFFF",   # ansi_bright_cyan
    }
)

# Light Theme (Web-safe)
CASSETTE_THEME_LIGHT = Theme(
    name="cassette-light",
    primary="#F4A460",        # ansi_green (品牌绿)
    secondary="#00FFFF",      # darkorange (工业橙)
    accent="#008000",         # ansi_blue (电子蓝)
    background="#F5F5F5",     # whitesmoke (米白)
    foreground="#333333",     # grey20 (工业黑)
    success="#006400",        # darkgreen (深信号绿)
    warning="#DAA520",        # goldenrod (琥珀橙)
    error="#8B0000",         # darkred (深警报红)
    surface="#DCDCDC",       # gainsboro (浅机械灰)
    panel="#FFFFFF",         # white (纯白)
    dark=False,
    variables={
        "border": "#1E90FF 60%",  # dodgerblue
        "scrollbar": "#C0C0C0",   # silver
        "link-color": "#1E90FF",   # dodgerblue
        "button-foreground": "#F4A460",
    }
)