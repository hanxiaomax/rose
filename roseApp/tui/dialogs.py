from typing import Any, List, Optional, Union

from textual.app import App, ComposeResult
from textual.widgets import Footer, Label

from roseApp.tui.widgets.question import Question, Answer
from roseApp.tui.widgets.multi_selection import MultiSelection, SelectionItem
from roseApp.tui.widgets.path_search import PathInput

class QuestionDialogApp(App[Union[Answer, None]]):
    """An app that displays a question and returns the answer."""

    CSS_PATH = "interactive_comp.tcss"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, question: str, options: List[Answer], id: Optional[str] = None):
        super().__init__()
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


class MultiSelectionDialogApp(App[List[str]]):
    """An app that displays a multi-selection list."""
    
    # Inline styles 
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "interactive_comp.tcss"

    def __init__(self, message: str, options: List[SelectionItem], id: Optional[str] = None):
        super().__init__()
        self.message = message
        self.options = options
        self.widget_id = id

    def compose(self) -> ComposeResult:
        yield MultiSelection(
            message=self.message,
            options=self.options,
            id=self.widget_id
        )
        yield Footer()

    def on_multi_selection_confirmed(self, message: MultiSelection.Confirmed) -> None:
        self.exit(message.selected_ids)

def ask_selection(message: str, options: List[SelectionItem]) -> List[str]:
    """
    Run a TUI multi-selection dialog.
    Returns list of selected IDs.
    Returns empty list if cancelled.
    """
    app = MultiSelectionDialogApp(message, options)
    res = app.run(inline=True)
    return res if res is not None else []

class PathDialogApp(App[Optional[str]]):
    """An app that displays a path input dialog."""
    
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "interactive_comp.tcss"

    def __init__(self, message: str, start_path: str = ".", id: Optional[str] = None):
        super().__init__()
        self.message = message
        self.start_path = start_path
        self.widget_id = id

    def compose(self) -> ComposeResult:
        # We can add a Label for the message if desired, 
        # but PathInput compose doesn't have one builtin.
        # Let's add one here.
        yield Label(self.message)
        yield PathInput(
            value=self.start_path,
            id=self.widget_id
        )

    def on_path_input_submitted(self, message: PathInput.Submitted) -> None:
        self.exit(message.path)
        
    def on_path_input_cancelled(self, message: PathInput.Cancelled) -> None:
        self.exit(None)

def ask_path(message: str, start_path: str = ".") -> Optional[str]:
    """
    Run a TUI path selection dialog.
    Returns selected path string or None if cancelled.
    """
    app = PathDialogApp(message, start_path)
    return app.run(inline=True)
