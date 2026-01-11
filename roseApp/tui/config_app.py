"""
TUI Configuration App for Rose.

Provides an inline TUI for editing Rose configuration.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalGroup, Vertical, Center, Container, HorizontalGroup
from textual.widgets import Label, Static, Footer, TabbedContent, TabPane, Switch, Button, Input
from textual.reactive import reactive
from textual.message import Message
from textual.screen import ModalScreen

from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import yaml

from .theme import ALL_THEMES
from ..core.config import get_config


class SettingRow(VerticalGroup):
    """A setting row with label and value."""
    
    # Fixed label width for alignment
    LABEL_WIDTH = 22
    
    DEFAULT_CSS = """
    SettingRow {
        height: auto;
        padding: 0 2;
        margin: 0 0 1 0;
    }
    
    SettingRow.-active {
        background: $primary 20%;
    }
    
    SettingRow #label-row {
        height: 1;
    }
    
    SettingRow #label {
        color: $text-muted;
    }
    
    SettingRow.-active #label {
        color: $text;
    }
    
    SettingRow #value {
        color: $accent;
        text-style: bold;
    }
    
    SettingRow.-active #value {
        color: $warning;
        text-style: bold;
    }
    
    SettingRow #modified-marker {
        display: none;
        color: $warning;
        margin-left: 1;
    }
    
    SettingRow.-modified #modified-marker {
        display: block;
    }
    """
    
    class Selected(Message):
        """User selected this setting for editing."""
        def __init__(self, setting: "SettingRow"):
            self.setting = setting
            super().__init__()
    
    def __init__(self, key: str, label: str, value: Any, setting_type: str, options: List[str] = None):
        super().__init__()
        self.key = key
        self.label_text = label
        self.current_value = value
        self.original_value = value  # Track original value
        self.setting_type = setting_type  # "toggle", "select", "path", "input"
        self.options = options or []
        
    def compose(self) -> ComposeResult:
        with HorizontalGroup(id="label-row"):
            # Fixed-width label for alignment
            padded_label = self.label_text.ljust(self.LABEL_WIDTH)
            yield Label(padded_label, id="label")
            yield Label(self._format_value(), id="value")
            yield Label("●", id="modified-marker")
    
    def _format_value(self) -> str:
        if self.setting_type == "toggle":
            return "[ON]" if self.current_value else "[OFF]"
        return str(self.current_value)
    
    def _update_modified_state(self) -> None:
        """Update modified class based on current vs original value."""
        if self.current_value != self.original_value:
            self.add_class("-modified")
        else:
            self.remove_class("-modified")
    
    def update_display(self) -> None:
        self.query_one("#value", Label).update(self._format_value())
        self._update_modified_state()
    
    def toggle(self) -> bool:
        """Toggle value if this is a toggle type. Returns True if toggled."""
        if self.setting_type == "toggle":
            self.current_value = not self.current_value
            self.update_display()
            return True
        return False
    
    def set_value(self, value: Any) -> None:
        """Set value directly."""
        self.current_value = value
        self.update_display()


class SettingsPanel(Vertical):
    """Panel containing all settings."""
    
    DEFAULT_CSS = """
    SettingsPanel {
        height: auto;
        padding: 1;
    }
    """
    
    current_index: reactive[int] = reactive(0)
    
    def __init__(self, settings: List[SettingRow]):
        super().__init__()
        self._settings = settings
        
    def compose(self) -> ComposeResult:
        for setting in self._settings:
            yield setting
    
    def on_mount(self) -> None:
        if self._settings:
            self._settings[0].add_class("-active")
    
    def watch_current_index(self, old: int, new: int) -> None:
        if 0 <= old < len(self._settings):
            self._settings[old].remove_class("-active")
        if 0 <= new < len(self._settings):
            self._settings[new].add_class("-active")
    
    def move_up(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
    
    def move_down(self) -> None:
        if self.current_index < len(self._settings) - 1:
            self.current_index += 1
    
    def get_current(self) -> Optional[SettingRow]:
        if 0 <= self.current_index < len(self._settings):
            return self._settings[self.current_index]
        return None
    
    def toggle_current(self) -> bool:
        """Toggle current setting if it's a toggle. Returns True if toggled."""
        setting = self.get_current()
        if setting:
            return setting.toggle()
        return False
    
    def get_values(self) -> Dict[str, Any]:
        return {s.key: s.current_value for s in self._settings}


class AboutPanel(Vertical):
    """About panel with app info."""
    
    # ASCII Art Banner
    BANNER = r"""
  ██████╗  ██████╗ ███████╗███████╗
  ██╔══██╗██╔═══██╗██╔════╝██╔════╝
  ██████╔╝██║   ██║███████╗█████╗  
  ██╔══██╗██║   ██║╚════██║██╔══╝  
  ██║  ██║╚██████╔╝███████║███████╗
  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝
    """
    
    DEFAULT_CSS = """
    AboutPanel {
        height: auto;
        padding: 1 2;
    }
    
    AboutPanel .banner {
        text-align: center;
        color: $primary;
    }
    
    AboutPanel .subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    
    AboutPanel .info {
        color: $text;
        padding-left: 2;
    }
    
    AboutPanel .info-label {
        color: $text-muted;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Static(self.BANNER, classes="banner")
        yield Label("Yet Another ROS Bag Picker & Analyzer", classes="subtitle")
        yield Label("", classes="info")
        yield Label("Version     0.3.5", classes="info")
        yield Label("Author      hanxiaomax", classes="info")
        yield Label("License     MIT", classes="info")
        yield Label("", classes="info")
        yield Label("Aesthetic   Cassette Futurism & Synthwave", classes="info")
        yield Label("Framework   Textual, Rich, Typer, Plotext", classes="info")
        yield Label("", classes="info")
        yield Label("GitHub      [link]https://github.com/hanxiaomax/rose[/link]", classes="info")


class SelectDialog(ModalScreen[Optional[str]]):
    """A modal dialog for selection."""
    
    DEFAULT_CSS = """
    SelectDialog {
        align: center middle;
    }
    
    #dialog-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    """
    
    def __init__(self, question: str, options: List[Any], current: str = None):
        super().__init__()
        self.question = question
        self.options = options
        self.current = current
        
    def compose(self) -> ComposeResult:
        from .widgets.question import Question, Answer
        with Container(id="dialog-container"):
            # Prepare Answers for Question widget
            answers = []
            for opt in self.options:
                if isinstance(opt, str):
                    answers.append(Answer(text=opt, id=opt))
                else:
                    answers.append(opt)
                    
            q = Question(question=self.question, options=answers)
            # Disable the violent action_quit in Question for ModalScreen
            q.action_quit = lambda: self.dismiss(None)
            yield q

    def on_question_answer(self, message: Any) -> None:
        self.dismiss(message.answer.id if hasattr(message.answer, "id") else message.answer)

    def action_cancel(self) -> None:
        """Handle Esc in dialog."""
        self.dismiss(None)

    BINDINGS = [
        Binding("escape", "cancel", "Back", priority=True)
    ]


class PathDialog(ModalScreen[Optional[str]]):
    """A modal dialog for path selection."""
    
    DEFAULT_CSS = """
    PathDialog {
        align: center middle;
    }
    
    #path-container {
        width: 80%;
        height: 60%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    """
    
    def __init__(self, message: str, start_path: str = "."):
        super().__init__()
        self.message = message
        self.start_path = start_path
        
    def compose(self) -> ComposeResult:
        from .widgets.path_search import PathInput
        with Container(id="path-container"):
            yield Label(self.message)
            yield PathInput(value=self.start_path)

    def on_path_input_submitted(self, message: Any) -> None:
        self.dismiss(message.path)
        
    def on_path_input_cancelled(self, message: Any) -> None:
        self.dismiss(None)


class InputDialog(ModalScreen[Optional[str]]):
    """A modal dialog for text/numeric input."""
    
    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    
    #input-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    
    #dialog-buttons {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    
    #dialog-buttons Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, message: str, value: str = "", placeholder: str = ""):
        super().__init__()
        self.message = message
        self.value = str(value)
        self.placeholder = placeholder
        
    def compose(self) -> ComposeResult:
        with Container(id="input-container"):
            yield Label(self.message)
            yield Input(value=self.value, placeholder=self.placeholder)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        """Handle Esc in dialog."""
        self.dismiss(None)

    BINDINGS = [
        Binding("escape", "cancel", "Back")
    ]


class ConfirmSaveDialog(ModalScreen[Optional[bool]]):
    """A modal dialog to confirm saving changes."""
    
    DEFAULT_CSS = """
    ConfirmSaveDialog {
        align: center middle;
    }
    
    #confirm-container {
        width: 45;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    #confirm-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        from .widgets.question import Question, Answer
        with Container(id="confirm-container"):
            yield Label("UNSAVED CHANGES", id="confirm-title")
            q = Question(
                question="Save changes before exiting?",
                options=[
                    Answer("Yes, save and exit", "save"),
                    Answer("No, discard changes", "discard"),
                    Answer("Cancel, stay here", "cancel")
                ]
            )
            # Ensure Esc handles correctly
            q.action_quit = lambda: self.dismiss(None)
            yield q

    def on_question_answer(self, message: Any) -> None:
        ans = message.answer.id
        if ans == "save":
            self.dismiss(True)
        elif ans == "discard":
            self.dismiss(False)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    BINDINGS = [
        Binding("escape", "cancel", "Back", priority=True)
    ]


class ConfigApp(App):
    """TUI Configuration App."""
    
    CSS = """
    ConfigApp {
        background: $surface;
    }
    
    #header-row {
        height: auto;
        width: 100%;
        align: center middle;
        padding: 1 0;
    }
    
    #title {
        text-align: center;
        text-style: bold;
        color: $primary;
    }
    
    #modified-pill {
        display: none;
        margin-left: 2;
        padding: 0 1;
        background: $warning;
        color: $surface;
        text-style: bold;
    }
    
    #modified-pill.-visible {
        display: block;
    }
    
    #hint {
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }
    
    TabbedContent {
        height: auto;
    }
    
    TabPane {
        padding: 0;
    }
    """
    
    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("space", "toggle", "Toggle", show=True),
        Binding("enter", "edit", "Edit", show=True),
        Binding("s", "save_and_exit", "Save", show=True),
        Binding("escape", "cancel", "Exit", show=True),
        Binding("q", "cancel", "Quit", show=False),
    ]
    
    def __init__(self, config_data: Dict[str, Any], themes: List[str]):
        super().__init__()
        self.config_data = config_data
        self.themes = themes
        self.result = None
        self._settings_panel: Optional[SettingsPanel] = None
        self._dirty = False # Initial state
        
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

    _dirty: reactive[bool] = reactive(False)

    def watch__dirty(self, dirty: bool) -> None:
        """Update modified pill visibility when dirty state changes."""
        try:
            pill = self.query_one("#modified-pill", Label)
            if dirty:
                pill.add_class("-visible")
            else:
                pill.remove_class("-visible")
        except Exception:
            pass
    
    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal
        with Horizontal(id="header-row"):
            yield Label("Rose Configuration", id="title")
            yield Label("MODIFIED", id="modified-pill")
        yield Label("Tab Switch  Space Toggle  Enter Edit/Save  Esc Cancel", id="hint")
        
        # Build settings
        settings = [
            SettingRow("parallel_workers", "Parallel Workers", 
                      self.config_data.get("parallel_workers", 4), "input"),
            SettingRow("memory_limit_mb", "Memory Limit (MB)", 
                      self.config_data.get("memory_limit_mb", 512), "input"),
            SettingRow("compression_default", "Default Compression", 
                      self.config_data.get("compression_default", "none"), "select", 
                      ["none", "bz2", "lz4"]),
            SettingRow("log_level", "Log Level", 
                      self.config_data.get("log_level", "INFO"), "select", 
                      ["DEBUG", "INFO", "WARNING", "ERROR"]),
            SettingRow("theme_file", "Theme File", 
                      self.config_data.get("theme_file", "rose.theme.default.yaml"), "select", 
                      self.themes),
            SettingRow("output_directory", "Output Directory", 
                      self.config_data.get("output_directory", "output"), "path"),
            SettingRow("verbose_default", "Verbose Output", 
                      self.config_data.get("verbose_default", False), "toggle"),
            SettingRow("build_index_default", "Build Index", 
                      self.config_data.get("build_index_default", False), "toggle"),
            SettingRow("log_to_file", "Log to File", 
                      self.config_data.get("log_to_file", True), "toggle"),
            SettingRow("enable_colors", "Enable Colors", 
                      self.config_data.get("enable_colors", True), "toggle"),
        ]
        
        self._settings_panel = SettingsPanel(settings)
        
        with TabbedContent():
            with TabPane("Settings", id="settings"):
                yield self._settings_panel
            with TabPane("About", id="about"):
                yield AboutPanel()
        
        yield Footer()
    
    def action_cursor_up(self) -> None:
        if self._settings_panel:
            self._settings_panel.move_up()
    
    def action_cursor_down(self) -> None:
        if self._settings_panel:
            self._settings_panel.move_down()
    
    def action_toggle(self) -> None:
        """Toggle current setting if it's a toggle type."""
        if self._settings_panel:
            if self._settings_panel.toggle_current():
                self._dirty = True
            else:
                # Not a toggle, show edit dialog
                self._edit_current()
    
    def action_edit(self) -> None:
        """Edit current setting."""
        self._edit_current()

    def action_save_and_exit(self) -> None:
        """Save and exit directly."""
        self._save_and_exit()
    
    def _edit_current(self) -> None:
        """Edit current non-toggle setting."""
        setting = self._settings_panel.get_current() if self._settings_panel else None
        if not setting:
            return
        
        if setting.setting_type == "select":
            self._show_select_dialog(setting)
        elif setting.setting_type == "path":
            self._show_path_dialog(setting)
        elif setting.setting_type == "input":
            self._show_input_dialog(setting)
        elif setting.setting_type == "toggle":
            if setting.toggle():
                self._dirty = True
    
    def _show_input_dialog(self, setting: SettingRow) -> None:
        """Show text/numeric input dialog."""
        def handle_result(result: Optional[str]) -> None:
            if result is not None:
                value = result
                if setting.key in ["parallel_workers", "memory_limit_mb"]:
                    try:
                        value = int(value)
                    except ValueError:
                        return # Ignore invalid input
                
                if value != setting.current_value:
                    self._dirty = True
                    setting.set_value(value)
        
        self.push_screen(
            InputDialog(
                message=f"Enter {setting.label_text}:",
                value=str(setting.current_value)
            ),
            handle_result
        )
    
    def _show_select_dialog(self, setting: SettingRow) -> None:
        """Show select dialog for setting."""
        def handle_result(result: Optional[str]) -> None:
            if result is not None and result != str(setting.current_value):
                self._dirty = True
                # Convert to int if needed
                value = result
                if setting.key in ["parallel_workers", "memory_limit_mb"]:
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                setting.set_value(value)
        
        self.push_screen(
            SelectDialog(
                question=f"Select {setting.label_text}:",
                options=setting.options,
                current=str(setting.current_value)
            ),
            handle_result
        )
    
    def _show_path_dialog(self, setting: SettingRow) -> None:
        """Show path input dialog."""
        def handle_result(result: Optional[str]) -> None:
            if result and result != setting.current_value:
                self._dirty = True
                setting.set_value(result)
        
        self.push_screen(
            PathDialog(
                message=f"Enter {setting.label_text}:",
                start_path=str(setting.current_value)
            ),
            handle_result
        )
    
    def _save_and_exit(self) -> None:
        """Collect values and exit."""
        if self._settings_panel:
            self.result = self._settings_panel.get_values()
        self.exit(self.result)
    
    def action_cancel(self) -> None:
        if self._dirty:
            def handle_confirm(result: Optional[bool]) -> None:
                if result is True:
                    self._save_and_exit()
                elif result is False:
                    self.exit(None)
                # If None (Cancel/Esc), stay in app
            
            self.push_screen(ConfirmSaveDialog(), handle_confirm)
        else:
            self.exit(None)


def run_config_app(config_data: Dict[str, Any], themes: List[str]) -> Optional[Dict[str, Any]]:
    """Run the config app and return new configuration or None if cancelled."""
    app = ConfigApp(config_data, themes)
    app.run(inline=True)
    return app.result
