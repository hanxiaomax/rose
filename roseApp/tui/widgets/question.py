from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from textual.app import ComposeResult
from textual import events, on
from textual.binding import Binding
from textual import containers
from textual.content import Content
from textual.reactive import var, reactive
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label


@dataclass
class Answer:
    text: str
    id: str = ""
    kind: Optional[str] = None

Options = list[Answer]


@dataclass
class Ask:
    """Data for Question."""

    question: str
    options: Options
    callback: Callable[[Answer], Any] | None = None


class NonSelectableLabel(Label):
    ALLOW_SELECT = False


class Option(containers.HorizontalGroup):
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    Option {
        background: transparent;
        color: $text-muted;
    }

    Option:hover {
        background: $boost;
    }

    Option #caret {
        visibility: hidden;
        padding: 0 1;
    }

    Option #index {
        padding-right: 1;
    }

    Option #label {
        width: 1fr;
    }

    Option.-active {            
        color: $text-accent;
    }

    Option.-active #caret {
        visibility: visible;
    }

    Option.-selected {
        opacity: 0.5;
    }

    Option.-active.-selected {
        opacity: 1.0;
        background: transparent;
        color: $text-accent;            
    }

    Option.-active.-selected #label {
        text-style: underline;
    }

    Option.-active.-selected #caret {
        visibility: hidden;
    }
    """

    @dataclass
    class Selected(Message):
        """The option was selected."""

        index: int

    selected: reactive[bool] = reactive(False)
    
    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def __init__(
        self, index: int, content: Content, key: str | None, classes: str = ""
    ) -> None:
        super().__init__(classes=classes)
        self.index = index
        self.content = content
        self.key = key

    def compose(self) -> ComposeResult:
        key = self.key
        yield NonSelectableLabel("❯", id="caret")
        if key:
            yield NonSelectableLabel(Content.styled(f"{key}", "b"), id="index")
        else:
            yield NonSelectableLabel(Content(" "), id="index")

        yield NonSelectableLabel(self.content, id="label")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Selected(self.index))


class Question(Widget, can_focus=True):
    """A text question with a menu of responses."""

    BINDING_GROUP_TITLE = "Question"
    ALLOW_SELECT = False
    
    # Map answer kinds to display keys
    DEFAULT_KINDS = {
        "allow_once": "y",
        "allow_always": "a", 
        "reject": "n",
        "modify": "m",
        # Add shortcut keys for main menu
        "l": "l",
        "i": "i",
        "e": "e",
        "c": "c",
        "m": "m",
        "o": "o",
        "q": "q",
    }
    
    BINDINGS = [
        Binding("up", "selection_up", "Up"),
        Binding("down", "selection_down", "Down"),
        Binding("enter", "select", "Select"),
        Binding("escape", "quit", "Cancel"),
    ]

    DEFAULT_CSS = """
    Question {
        width: 1fr;
        height: auto;
        padding: 0 1; 
        background: transparent;
    }

    Question #prompt {
        margin-bottom: 1;
        color: $text-primary;
    }

    Question.-blink Option.-active #caret {
        opacity: 0.2;
    }

    Question:blur #index,
    Question:blur #caret {
        opacity: 0.3;
    }
    """

    question: var[str] = var("")
    options: var[Options] = var(list)

    selection: reactive[int] = reactive(0, init=False)
    selected: var[bool] = var(False)
    
    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")
    blink: var[bool] = var(False)


    @dataclass
    class Answer(Message):
        """User selected a response."""

        index: int
        answer: Answer

    def __init__(
        self,
        question: str = "Ask and you will receive",
        options: Options | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.set_reactive(Question.question, question)
        self.set_reactive(Question.options, options or [])

    def on_mount(self) -> None:
        def toggle_blink() -> None:
            if self.has_focus:
                self.blink = not self.blink
            else:
                self.blink = False

        self._blink_timer = self.set_interval(0.5, toggle_blink)

    def _reset_blink(self) -> None:
        self.blink = False
        self._blink_timer.reset()

    def update(self, ask: Ask) -> None:
        self.question = ask.question
        self.options = ask.options
        self.selection = 0
        self.selected = False
        self.refresh(recompose=True, layout=True)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup():
            if self.question:
                yield Label(self.question, id="prompt")

            with containers.VerticalGroup(id="option-container"):
                kinds: set[str] = set()
                for index, answer in enumerate(self.options):
                    active = index == self.selection
                    key = (
                        self.DEFAULT_KINDS.get(answer.kind)
                        if (answer.kind and answer.kind not in kinds)
                        else None
                    )
                    yield Option(
                        index,
                        Content(answer.text),
                        key,
                        classes="-active" if active else "",
                    ).data_bind(Question.selected)
                    if answer.kind is not None:
                        kinds.add(answer.kind)

    def watch_selection(self, old_selection: int, new_selection: int) -> None:
        self.query("#option-container > .-active").remove_class("-active")
        if new_selection >= 0:
            self.query_one("#option-container").children[new_selection].add_class(
                "-active"
            )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.selected and action in ("selection_up", "selection_down"):
            return False
        if action == "select_kind":
            kinds = {answer.kind for answer in self.options if answer.kind is not None}
            check_kinds = set()
            for parameter in parameters:
                if isinstance(parameter, str):
                    check_kinds.add(parameter)
                elif isinstance(parameter, tuple):
                    check_kinds.update(parameter)

            return any(kind in kinds for kind in check_kinds)

        return True

    def watch_blink(self, blink: bool) -> None:
        self.set_class(blink, "-blink")

    def action_selection_up(self) -> None:
        self._reset_blink()
        self.selection = max(0, self.selection - 1)

    def action_selection_down(self) -> None:
        self._reset_blink()
        self.selection = min(len(self.options) - 1, self.selection + 1)

    def action_select(self) -> None:
        self._reset_blink()
        self.post_message(
            self.Answer(
                index=self.selection,
                answer=self.options[self.selection],
            )
        )
        self.selected = True

    def action_select_kind(self, kind: str | tuple[str]) -> None:
        kinds = kind if isinstance(kind, tuple) else (kind,)
        for kind in kinds:
            for index, answer in enumerate(self.options):
                if answer.kind == kind:
                    self.selection = index
                    self.action_select()
                    break

    def action_quit(self) -> None:
        # Emit a None answer or handle in App
        # For simplicity, we can just post a Message if we had a specific Cancelled message,
        # but Question usually returns Answer.
        # If we use the same mechanism as QuestionDialogApp expects:
        # QuestionDialogApp.on_question_answer exits with message.answer
        # If we want to cancel, we might need a specific signal or just exit app.
        
        # Actually, standard way for a widget in an app to quit is:
        # self.app.exit(None) if it's the main widget?
        # But widget shouldn't assume it's the root.
        
        # Let's post a dummy Answer with everything None?
        # Or better, just rely on the App to bind escape if we can't easily change the protocol.
        # But wait, I'm editing the widget. 
        # I'll define a special id="cancel" answer?
        
        # Re-reading QuestionDialogApp: it exits with message.answer.
        # Let's just use self.app.exit(None) if we assume this is used in a dialog?
        # A bit hacky for a pure widget.
        # But given the context of "Refining TUI Dialogs", it's acceptable.
        if hasattr(self.app, "exit"):
            self.app.exit(None)

    @on(Option.Selected)
    def on_option_selected(self, event: Option.Selected) -> None:
        event.stop()
        self._reset_blink()
        if not self.selected:
            self.selection = event.index


if __name__ == "__main__":
    from textual.app import App
    from textual.widgets import Footer

    OPTIONS = [
        Answer("Yes, allow once", "proceed_always", kind="allow_once"),
        Answer("Yes, allow always", "allow_always", kind="allow_always"),
        Answer("Modify with external editor", "modify", kind="allow_once"),
        Answer("No, suggest changes (esc)", "reject"),
    ]

    class QuestionApp(App):
        def compose(self) -> ComposeResult:
            yield Question("Apply this change?", OPTIONS)
            yield Footer()

    QuestionApp().run(inline=True)
