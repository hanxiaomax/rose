from typing import Any, List, Optional, Union

from textual.app import App, ComposeResult
from textual.widgets import Footer

from roseApp.tui.widgets.question import Question, Answer
from roseApp.tui.widgets.multi_selection import MultiSelection, SelectionItem

class QuestionDialogApp(App[Union[Answer, None]]):
    """An app that displays a question and returns the answer."""

    CSS_PATH = "styles.tcss" # Re-use styles if possible or define inline
    ENABLE_COMMAND_PALETTE = False
    # Inline styles to ensure it looks okay even if main styles.tcss is missing specific bits
    CSS = """
    QuestionDialogApp {
        align: left top;
        height: auto;
        background: transparent;
    }
    
    Question {
        width: 100%;
        height: auto;
        border: round $accent;
        background: transparent;
        #prompt {
            color: $text;
            text-style: bold;
        }
    }
    """

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
    CSS = """
    MultiSelectionDialogApp {
        align: left top;
        height: auto;
        background: transparent;
    }
    
    MultiSelection {
        width: 100%;
        height: auto;
        border: round $accent;
        padding: 0 1;
        background: transparent;
    }
    """

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
