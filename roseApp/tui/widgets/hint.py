from typing import Optional
from textual.widgets import Label

class Hint(Label):
    """
    A unified hint label component with transparent background.
    """
    DEFAULT_CSS = """
    Hint {
        background: transparent;
        width: 100%;
        display: block;
        text-align: center;
    }
    """
    
    def __init__(self, renderable: str, id: Optional[str] = "hint") -> None:
        super().__init__(renderable, id=id)
