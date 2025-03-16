from textual.color import Color
from textual.theme import Theme

# Dark Theme (Terminal-safe)
CASSETTE_THEME_DARK = Theme(
    name="cassette-dark",
    primary="#b1b329",       
    secondary="#008001",     
    accent="#9b50b7",        
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
        "footer-key-foreground": "#9b50b7",
        "input-cursor-background":"#FFFF00",
        "datatable--header-cursor":"#FFFF00",
        "button-focus-text-style": "bold",
    }
)

CASSETTE_THEME_WALKMAN = Theme(
    name="cassette-walkman",
    primary="#43748f",       
    secondary="#6e92a6",      
    accent="#ef8e04",        
    background="#e7e5e6",    
    foreground="#353530",     
    success="#43748f",       
    warning="#DAA520",       
    error="#ef8e04",        
    surface="#43748f",       
    panel="#d6d6d6",         
    dark=False,
    variables={
        "border": "#6e92a6 60%",  
        "scrollbar": "#d6d6d6",  
        "button-color-foreground": "#313a44",
        "footer-key-foreground": "#ef8e04",
        "button-focus-text-style": "bold",
    }
)

# Light Theme (Web-safe)
CASSETTE_THEME_LIGHT = Theme(
    name="cassette-light",
    primary="#F4A460",       
    secondary="#C0C0C0",      
    accent="#f24d11",        
    background="#fcf2d4",    
    foreground="#333333",     
    success="#00FFFF",       
    warning="#DAA520",       
    error="#FF4500",        
    surface="#FFFFF0",       
    panel="#FFFFF0",         
    dark=False,
    variables={
        "border": "#ec6809 60%",  # dodgerblue
        "scrollbar": "#fcf2d4",   # silver
        "button-background": "#ec6809",
        "button-color-foreground": "#333333",
        "footer-key-foreground": "#ec6809",
        "button-focus-text-style": "bold",
    }
)


