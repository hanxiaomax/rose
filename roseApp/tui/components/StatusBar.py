from rich.text import Text
from textual.widgets import Static
from typing import Optional
import time

class StatusBar(Static):
    """Custom status bar with dynamic styling and loading indicator"""

    SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_loading: bool = False
        self._loading_start_time: Optional[float] = None
        self._loading_text: Optional[str] = None

    def _render_spinner(self) -> str:
        """Render a spinning animation
        
        Returns:
            String representation of the spinner with loading text
        """
        if not self._is_loading or self._loading_start_time is None:
            return ""
        
        elapsed = time.time() - self._loading_start_time
        spinner_idx = int(elapsed * 10) % len(self.SPINNER_CHARS)
        spinner = self.SPINNER_CHARS[spinner_idx]
        
        if self._loading_text:
            dots = "." * (int(elapsed * 2) % 4)
            return f"{spinner} {self._loading_text}{dots:<3}"
        return spinner

    def start_loading(self, text: str = "Processing") -> None:
        """Start showing loading animation
        
        Args:
            text: Text to show next to the spinner
        """
        self._is_loading = True
        self._loading_start_time = time.time()
        self._loading_text = text
        self.update_status(self.renderable.plain if hasattr(self, 'renderable') else "", self.classes)

    def stop_loading(self) -> None:
        """Stop showing loading animation"""
        self._is_loading = False
        self._loading_start_time = None
        self._loading_text = None
        self.update_status(self.renderable.plain if hasattr(self, 'renderable') else "", self.classes)

    def update_status(self, message: str, status_class: str = "normal") -> None:
        """Update status message with optional style and loading animation
        
        Args:
            message: Status message to display
            status_class: CSS class for styling
        """
        text = Text()
        
        if self._is_loading:
            spinner_text = self._render_spinner()
            if spinner_text:
                text.append(spinner_text, style="bold yellow")
        else:
            text.append(message)
        if status_class:
            self.classes = status_class

        self.update(text)
