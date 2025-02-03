from textual.color import Color
from textual.theme import Theme

CASSETTE_THEME = Theme(
    name="cassette",
    # 基础颜色
    primary="#20B2AA",       # 荧光绿，代表磁带指示灯
    secondary="#FF71CE",    # 霓虹粉，用于次要元素
    accent="#01CDFE",       # 电子蓝，强调色
    background="#1A1B26",   # 深蓝黑色，像老式录音机的外壳
    foreground="#C7D3E3",   # 柔和的银白色，像磁带的金属外壳
    success="#96F7C8",      # 柔和的绿色，表示录制状态
    warning="#FFA500",      # 柔和的黄色，表示等待状态
    error="#DC5C5C",        # 柔和的红色，表示错误状态
    surface="#24283B",      # 稍浅的背景色，用于面板
    panel="#2F354D",        # 更浅的背景色，用于控件
    dark=True,
    variables={
        # Border 变量
        "border": "#5CFFAF 60%",
        "border-blurred": "#24283B",
        
        # Cursor 变量
        "block-cursor-foreground": "#1A1B26",
        "block-cursor-background": "#5CFFAF",
        "block-cursor-text-style": "bold",
        "block-cursor-blurred-foreground": "#C7D3E3",
        "block-cursor-blurred-background": "#5CFFAF 30%",
        "block-cursor-blurred-text-style": "none",
        "block-hover-background": "#5CFFAF 5%",
        
        # Input 变量
        "input-cursor-background": "#C7D3E3",
        "input-cursor-foreground": "#1A1B26",
        "input-cursor-text-style": "none",
        "input-selection-background": "#5CFFAF 40%",
        
        # Scrollbar 变量
        "scrollbar": "#2F354D",
        "scrollbar-hover": "#3F455D",
        "scrollbar-active": "#4F556D",
        "scrollbar-background": "#0A0B16",
        "scrollbar-corner-color": "#0A0B16",
        "scrollbar-background-hover": "#0A0B16",
        "scrollbar-background-active": "#0A0B16",
        
        # Link 变量
        "link-background": "initial",
        "link-background-hover": "#5CFFAF",
        "link-color": "#C7D3E3",
        "link-style": "underline",
        "link-color-hover": "#1A1B26",
        "link-style-hover": "bold not underline",
        
        # Footer 变量
        "footer-foreground": "#C7D3E3",
        "footer-background": "#2F354D",
        "footer-key-foreground": "#FFA500",
        "footer-key-background": "transparent",
        "footer-description-foreground": "#C7D3E3",
        "footer-description-background": "transparent",
        "footer-item-background": "transparent",
        
        # Button 变量
        "button-foreground": "#C7D3E3",
        "button-color-foreground": "#1A1B26",
        "button-focus-text-style": "bold reverse"
    }
)