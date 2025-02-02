from textual.color import Color
from textual.theme import Theme

CASSETTE_THEME = Theme(
    name="cassette",
    # 主色调：复古磁带配色
    primary="#5CFFAF",      # 荧光绿，代表磁带指示灯
    secondary="#FF71CE",    # 霓虹粉，用于次要元素
    accent="#01CDFE",       # 电子蓝，强调色
    
    # 背景和前景
    background="#1A1B26",   # 深蓝黑色，像老式录音机的外壳
    foreground="#C7D3E3",   # 柔和的银白色，像磁带的金属外壳
    
    # 功能色
    success="#96F7C8",      # 柔和的绿色，表示录制状态
    warning="#FFFB96",      # 柔和的黄色，表示等待状态
    error="#FF8B8B",        # 柔和的红色，表示错误状态
    
    # 界面层次
    surface="#24283B",      # 稍浅的背景色，用于面板
    panel="#2F354D",        # 更浅的背景色，用于控件
    
    dark=True,
    variables={
        # 基础样式
        "text-style": "bold",
        "text-muted": "#565F89",
        
        # 交互元素
        "button-background": "#2F354D",
        "button-hover": "#5CFFAF 20%",
        "button-border": "#5CFFAF 60%",
        
        # 输入框样式
        "input-background": "#1A1B26",
        "input-border": "#01CDFE 60%",
        "input-cursor": "#5CFFAF",
        "input-selection": "#01CDFE 30%",
        
        # 滚动条
        "scrollbar-background": "#1A1B26",
        "scrollbar-color": "#01CDFE 40%",
        "scrollbar-hover": "#5CFFAF 60%",
        "scrollbar-size": "1 1",
        
        # 特殊效果
        "glow-effect": "#5CFFAF 20%",
    }
)