import os
import glob
from typing import Any, List, Optional, Union, Callable

from textual.app import App, ComposeResult
from textual.widgets import Footer, Label

from roseApp.tui.widgets.question import Question, Answer
from roseApp.tui.widgets.multi_question import MultiQuestion
from roseApp.tui.widgets.path_search import PathInput
from roseApp.tui.theme import ALL_THEMES
from roseApp.core.config import get_config

class QuestionDialogApp(App[Union[Answer, None]]):
    CSS_PATH = "interactive_comp.tcss"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, question: str, options: List[Answer], id: Optional[str] = None):
        super().__init__()
    def __init__(self, question: str, options: List[Answer], id: Optional[str] = None):
        super().__init__()
        for t in ALL_THEMES.values():
            self.register_theme(t)
            
        config = get_config()
        # Parse theme name from file "rose.theme.NAME.yaml"
        theme_name = "claude"
        parts = config.theme_file.split('.')
        if len(parts) >= 3:
            theme_name = parts[2]
            
        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"

        self.question_text = question
        self.options = options
        self.widget_id = id

    def compose(self) -> ComposeResult:
        yield Question(
            question=self.question_text,
            options=self.options,
            id=self.widget_id,
        )
        yield Footer()
    
    def on_question_answer(self, message: Question.Answer) -> None:
        self.exit(message.answer)

def ask_question(question: str, options: List[Answer]) -> Optional[Answer]:
    """
    Run a TUI question dialog and return the selected Answer.
    Returns None if cancelled (Ctrl+C).
    """
    app = QuestionDialogApp(question, options)
    return app.run(inline=True)


class MultiQuestionDialogApp(App[List[Answer]]):
    """An app that displays a multi-selection question."""
    
    # Inline styles 
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "interactive_comp.tcss"

    def __init__(self, question: str, options: List[Answer], id: Optional[str] = None):
        super().__init__()
        for t in ALL_THEMES.values():
            self.register_theme(t)
            
        config = get_config()
        theme_name = "claude"
        parts = config.theme_file.split('.')
        if len(parts) >= 3:
            theme_name = parts[2]

        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"

        self.question_text = question
        self.options = options
        self.widget_id = id

    def compose(self) -> ComposeResult:
        yield MultiQuestion(
            question=self.question_text,
            options=self.options,
            id=self.widget_id,
        )
        yield Footer()

    def on_multi_question_answers(self, message: MultiQuestion.Answers) -> None:
        self.exit(message.answers)

def ask_multi_selection(question: str, options: List[Answer]) -> List[Answer]:
    """
    Run a TUI multi-selection dialog.
    Returns list of selected Answers.
    Returns empty list if cancelled.
    """
    app = MultiQuestionDialogApp(question, options)
    res = app.run(inline=True)
    return res if res is not None else []

class PathDialogApp(App[Optional[str]]):
    """An app that displays a path input dialog."""
    
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "interactive_comp.tcss"

    def __init__(
        self, 
        message: str, 
        start_path: str = ".", 
        id: Optional[str] = None,
        validator: Optional[Callable[[str], Optional[str]]] = None
    ):
        super().__init__()
        for t in ALL_THEMES.values():
            self.register_theme(t)

        config = get_config()
        theme_name = "claude"
        parts = config.theme_file.split('.')
        if len(parts) >= 3:
            theme_name = parts[2]

        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"

        self.message = message
        self.start_path = start_path
        self.widget_id = id
        self.validator = validator

    def compose(self) -> ComposeResult:
        # We can add a Label for the message if desired, 
        # but PathInput compose doesn't have one builtin.
        # Let's add one here.
        yield Label(self.message)
        yield PathInput(
            value=self.start_path,
            id=self.widget_id,
            validator=self.validator
        )
        yield Footer()

    def on_path_input_submitted(self, message: PathInput.Submitted) -> None:
        self.exit(message.path)
        
    def on_path_input_cancelled(self, message: PathInput.Cancelled) -> None:
        self.exit(None)

def ask_path(
    message: str, 
    start_path: str = ".", 
    validator: Optional[Callable[[str], Optional[str]]] = None
) -> Optional[str]:
    """
    Run a TUI path selection dialog.
    Returns selected path string or None if cancelled.
    """
    app = PathDialogApp(message, start_path, validator=validator)
    return app.run(inline=True)

def ask_bags(message: str, start_path: str = "./", allow_multiple: bool = True) -> List[str]:
    """
    Ask user to select valid .bag file(s).
    Returns list of resolved paths (files or glob matches).
    Returns empty list if cancelled.
    """
    from roseApp.tui.widgets.path_search import get_default_bag_validator
    
    validator = get_default_bag_validator(allow_multiple=allow_multiple)
    result = ask_path(message, start_path=start_path, validator=validator)
    
    if result:
        # Resolver logic moved here
        if os.path.isfile(result):
            return [result]
        
        if glob.has_magic(result):
            matches = glob.glob(result)
            return [m for m in matches if m.endswith(".bag")]
            
        return []
    return []
