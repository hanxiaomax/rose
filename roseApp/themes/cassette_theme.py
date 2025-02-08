from textual.color import Color
from textual.theme import Theme

# Dark Theme (Terminal-safe)
CASSETTE_THEME_DARK = Theme(
    name="cassette-dark",
    primary="#b1b329",       
    secondary="#F5F5F5",     
    accent="#b1b329",        
    background="#002f33",    
    foreground="#FAF0E6",    
    success="#008001",       
    warning="#FFFF00",      
    error="#FF0000",        
    surface="#262626",      
    panel="#333333",        
    dark=True,
    variables={
        "border": "#b1b329 60%",  
        "scrollbar": "#002f33",   
        "button-background": "#00FF00",
        "button-color-foreground": "#1A1A1A",
        "footer-key-foreground": "#FF8C00",
        "input-cursor-background":"#FFFF00",
        "datatable--header-cursor":"#FFFF00"
    }
)

# Light Theme (Web-safe)
CASSETTE_THEME_LIGHT = Theme(
    name="cassette-light",
    primary="#F4A460",       
    secondary="#C0C0C0",      
    accent="#f24d11",        
    background="#fff1ca",    
    foreground="#333333",     
    success="#00FFFF",       
    warning="#DAA520",       
    error="#FF4500",        
    surface="#FFFFF0",       
    panel="#FFFFF0",         
    dark=False,
    variables={
        "border": "#ec6809 60%",  # dodgerblue
        "scrollbar": "#C0C0C0",   # silver
        "button-background": "#F4A460",
        "button-color-foreground": "#FFFFFF",
        "footer-key-foreground": "#F4A460",
    }
)