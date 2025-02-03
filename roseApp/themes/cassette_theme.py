from textual.color import Color
from textual.theme import Theme

# Dark Theme (Terminal-safe)
CASSETTE_THEME_DARK = Theme(
    name="cassette-dark",
    primary="#00FF00",       
    secondary="#00FFFF",     
    accent="#FF8C00",        
    background="#1A1A1A",    
    foreground="#B2B2B2",    
    success="#008000",       
    warning="#FFFF00",      
    error="#FF0000",        
    surface="#262626",      
    panel="#333333",        
    dark=True,
    variables={
        "border": "#00FFFF 60%",  
        "scrollbar": "#4D4D4D",   
        "button-background": "#00FF00",
        "button-color-foreground": "#1A1A1A",
        "footer-key-foreground": "#FF8C00"
    }
)

# Light Theme (Web-safe)
CASSETTE_THEME_LIGHT = Theme(
    name="cassette-light",
    primary="#F4A460",       
    secondary="#00FFFF",      
    accent="#008000",        
    background="#F5F5F5",    
    foreground="#333333",     
    success="#00FFFF",       
    warning="#DAA520",       
    error="#FF4500",        
    surface="#DCDCDC",       
    panel="#C0C0C0",         
    dark=False,
    variables={
        "border": "#1E90FF 60%",  # dodgerblue
        "scrollbar": "#C0C0C0",   # silver
        "button-background": "#F4A460",
        "button-color-foreground": "#FFFFFF",
        "footer-key-foreground": "#F4A460"
    }
)