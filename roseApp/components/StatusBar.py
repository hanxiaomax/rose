from rich.text import Text
from textual.widgets import Static

class StatusBar(Static):
    """Custom status bar with dynamic styling"""

    def update_status(self, message: str, status_class: str = "normal") -> None:
        """Update status message with optional style"""
        message = Text(message)

        if status_class:
            self.classes = status_class
        
        self.update(message)
