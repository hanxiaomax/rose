"""
Main TUI Entry Point for Rose.

Provides a main menu interface for accessing all Rose commands.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Container
from textual.widgets import Static, Footer, Label

from .widgets.question import Question, Answer
from .theme import ALL_THEMES
from ..core.config import get_config


# Package Info - read from pyproject.toml via importlib.metadata
try:
    from importlib.metadata import metadata
    _meta = metadata("rose-bag")
    __version__ = _meta.get("Version", "dev")
    # Author is in Author-email format: "Name <email>" or just in Author
    _author_email = _meta.get("Author-email", "")
    if _author_email and "<" in _author_email:
        __author__ = _author_email.split("<")[0].strip()
    else:
        __author__ = _meta.get("Author", "Lingfeng_ai")
    # Extract repo from project URLs
    _urls = _meta.get_all("Project-URL") or []
    __repo__ = next((u.split(", ")[1] for u in _urls if u.startswith("Homepage")), "")
except Exception:
    __version__ = "dev"
    __author__ = "Lingfeng_ai"
    __repo__ = "https://github.com/hanxiaomax/rose"

# ASCII Art Banner
ROSE_BANNER = r"""
  ██████╗  ██████╗ ███████╗███████╗
  ██╔══██╗██╔═══██╗██╔════╝██╔════╝
  ██████╔╝██║   ██║███████╗█████╗  
  ██╔══██╗██║   ██║╚════██║██╔══╝  
  ██║  ██║╚██████╔╝███████║███████╗
  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝
"""


class MainApp(App):
    """Main TUI entry point with command selection."""
    
    CSS = """
    MainApp {
        background: $surface;
    }
    
    #banner-container {
        height: auto;
        width: 100%;
        padding: 1 2;
    }
    
    #banner {
        text-align: center;
        color: $primary;
    }
    
    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 0;
    }
    
    #info {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }
    
    #menu-container {
        height: auto;
        width: 100%;
        padding: 0 2;
    }
    
    Question {
        padding: 0 4;
    }
    """
    
    BINDINGS = [
        Binding("escape", "quit", "Exit"),
        Binding("q", "quit", "Quit", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        
        # Register themes
        for name, theme in ALL_THEMES.items():
            self.register_theme(theme)
        
        # Set current theme
        config = get_config()
        theme_name = "claude"
        parts = config.theme_file.split('.')
        if len(parts) >= 3:
            theme_name = parts[2]
        
        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"
        
        self.selected_command = None
    
    def compose(self) -> ComposeResult:
        with Vertical(id="banner-container"):
            yield Static(ROSE_BANNER, id="banner")
            yield Label("Yet Another ROS Bag Picker & Analyzer", id="subtitle")
            yield Label(f"v{__version__} · {__author__} · {__repo__}", id="info")
        
        with Container(id="menu-container"):
            yield Question(
                question="What would you like to do?",
                options=[
                    Answer("Load bag files into cache", "load", kind="l"),
                    Answer("Inspect bag contents", "inspect", kind="i"),
                    Answer("Extract topics from bags", "extract", kind="e"),
                    Answer("Compress bag files", "compress", kind="c"),
                    Answer("Manage cache (list/clear)", "list", kind="m"),
                    Answer("Edit configuration", "config", kind="o"),
                    Answer("Exit", "exit", kind="q"),
                ]
            )
        
        yield Footer()
    
    def on_question_answer(self, message: Question.Answer) -> None:
        """Handle command selection."""
        command = message.answer.id
        self.selected_command = command
        self.exit(command)
    
    def action_quit(self) -> None:
        self.exit(None)


def run_main_app() -> 'Optional[str]':
    """
    Run the main TUI and return selected command.
    Returns command id or None if cancelled.
    """
    app = MainApp()
    app.run(inline=True)
    return app.selected_command


def launch_interactive_command(command: str) -> None:
    """Launch the selected command in interactive mode."""
    import subprocess
    import sys
    import os
    
    if command == "exit" or command is None:
        return
    
    # Find rose executable - use the same one that launched us
    rose_cmd = "rose"
    
    if command == "config":
        subprocess.run([rose_cmd, "config"])
    elif command == "load":
        subprocess.run([rose_cmd, "load", "-i"])
    elif command == "inspect":
        subprocess.run([rose_cmd, "inspect", "-i"])
    elif command == "extract":
        subprocess.run([rose_cmd, "extract", "-i"])
    elif command == "compress":
        subprocess.run([rose_cmd, "compress", "-i"])
    elif command == "list":
        subprocess.run([rose_cmd, "list"])


def main_tui_loop() -> None:
    """
    Main TUI loop - shows menu, runs selected command, returns to menu.
    """
    while True:
        command = run_main_app()
        
        if command is None or command == "exit":
            print("Goodbye!")
            break
        
        launch_interactive_command(command)
        print()  # Spacing before returning to menu


if __name__ == "__main__":
    main_tui_loop()
