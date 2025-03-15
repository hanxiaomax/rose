from typing import Callable
from textual.app import Screen, ComposeResult
from textual.containers import  Horizontal, Vertical
from textual.widgets import Label, Button

class ConfirmDialog(Screen):
    """Dialog screen for confirming actions"""
    def __init__(self,message:str,yes_callback:Callable,no_callback:Callable):
        super().__init__()
        self.message = message
        self.yes_callback = yes_callback
        self.no_callback = no_callback
        
    def compose(self) -> ComposeResult:
        """Create dialog content"""
        with Vertical(id="dialog-container"):
            yield Label(f"{self.message}")
            with Horizontal(id="dialog-buttons"):
                yield Button("No", classes="confirm-btn",id="confirm-no")
                yield Button("Yes",classes="confirm-btn",id="confirm-yes")
                

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "confirm-yes":
            self.yes_callback()
        else:
            self.no_callback()
