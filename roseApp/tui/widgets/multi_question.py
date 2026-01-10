from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Set

from textual.app import ComposeResult
from textual import events, on
from textual.binding import Binding
from textual import containers
from textual.content import Content
from textual.reactive import var, reactive
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

# Reuse Answer from question.py for consistency
from .question import Answer, Options


class NonSelectableLabel(Label):
    ALLOW_SELECT = False


class MultiOption(containers.HorizontalGroup):
    """An option that can be toggled on/off for multi-selection."""
    
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    MultiOption {
        background: transparent;
        color: $text-muted;
    }

    MultiOption:hover {
        background: $boost;
    }

    MultiOption #caret {
        visibility: hidden;
        padding: 0 1;
    }

    MultiOption #checkbox {
        padding-right: 1;
    }

    MultiOption #label {
        width: 1fr;
    }

    MultiOption.-active {            
        color: $text-accent;
    }

    MultiOption.-active #caret {
        visibility: visible;
    }

    MultiOption.-checked {
        color: $text-accent;
    }

    MultiOption.-checked #checkbox {
        color: $success;
    }
    """

    @dataclass
    class Selected(Message):
        """The option was selected (cursor moved to it)."""
        index: int

    @dataclass
    class Toggled(Message):
        """The option was toggled (checked/unchecked)."""
        index: int
        checked: bool

    checked: reactive[bool] = reactive(False)
    
    def watch_checked(self, checked: bool) -> None:
        self.set_class(checked, "-checked")
        checkbox = self.query_one("#checkbox", Label)
        checkbox.update("◉" if checked else "○")

    def __init__(
        self, index: int, content: Content, key: str | None, checked: bool = False, classes: str = ""
    ) -> None:
        super().__init__(classes=classes)
        self.index = index
        self.content = content
        self.key = key
        self.initial_checked = checked

    def compose(self) -> ComposeResult:
        yield NonSelectableLabel("❯", id="caret")
        yield NonSelectableLabel("○", id="checkbox")
        if self.key:
            yield NonSelectableLabel(Content.styled(f"{self.key}", "b"), id="index")
        else:
            yield NonSelectableLabel(Content(" "), id="index")
        yield NonSelectableLabel(self.content, id="label")

    def on_mount(self) -> None:
        self.checked = self.initial_checked

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Selected(self.index))


class MultiQuestion(Widget, can_focus=True):
    """A question widget that allows selecting multiple answers."""

    BINDING_GROUP_TITLE = "Multi-Select"
    ALLOW_SELECT = False
    
    BINDINGS = [
        Binding("up", "selection_up", "Up"),
        Binding("down", "selection_down", "Down"),
        Binding("space", "toggle", "Toggle"),
        Binding("tab", "toggle_next", "Toggle & Next"),
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "quit", "Cancel"),
        Binding("ctrl+a", "select_all", "Select All"),
        Binding("ctrl+i", "invert_selection", "Invert"),
    ]

    DEFAULT_CSS = """
    MultiQuestion {
        width: 1fr;
        height: auto;
        padding: 0 1; 
        background: transparent;
    }

    MultiQuestion #prompt {
        margin-bottom: 1;
        color: $text-primary;
    }

    MultiQuestion.-blink MultiOption.-active #caret {
        opacity: 0.2;
    }

    MultiQuestion:blur #checkbox,
    MultiQuestion:blur #caret {
        opacity: 0.3;
    }
    """

    question: var[str] = var("")
    options: var[Options] = var(list)
    
    selection: reactive[int] = reactive(0, init=False)
    confirmed: var[bool] = var(False)
    blink: var[bool] = var(False)
    
    # Track which options are checked
    checked_indices: var[Set[int]] = var(set)

    @dataclass
    class Answers(Message):
        """User confirmed their selections."""
        indices: List[int]
        answers: List[Answer]

    def __init__(
        self,
        question: str = "Select one or more options",
        options: Options | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.set_reactive(MultiQuestion.question, question)
        self.set_reactive(MultiQuestion.options, options or [])
        self.set_reactive(MultiQuestion.checked_indices, set())

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

    def update(self, question: str, options: Options) -> None:
        """Update the question and options."""
        self.question = question
        self.options = options
        self.selection = 0
        self.confirmed = False
        self.checked_indices = set()
        self.refresh(recompose=True, layout=True)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup():
            if self.question:
                yield Label(self.question, id="prompt")

            with containers.VerticalGroup(id="option-container"):
                for index, answer in enumerate(self.options):
                    active = index == self.selection
                    checked = index in self.checked_indices
                    key = answer.kind if answer.kind else None
                    yield MultiOption(
                        index,
                        Content(answer.text),
                        key,
                        checked=checked,
                        classes=("-active" if active else "") + (" -checked" if checked else ""),
                    )

    def watch_selection(self, old_selection: int, new_selection: int) -> None:
        self.query("#option-container > .-active").remove_class("-active")
        if new_selection >= 0:
            container = self.query_one("#option-container")
            if new_selection < len(container.children):
                container.children[new_selection].add_class("-active")

    def watch_blink(self, blink: bool) -> None:
        self.set_class(blink, "-blink")

    def action_selection_up(self) -> None:
        if self.confirmed:
            return
        self._reset_blink()
        self.selection = max(0, self.selection - 1)

    def action_selection_down(self) -> None:
        if self.confirmed:
            return
        self._reset_blink()
        self.selection = min(len(self.options) - 1, self.selection + 1)

    def action_toggle(self) -> None:
        """Toggle the currently selected option."""
        if self.confirmed:
            return
        self._reset_blink()
        
        container = self.query_one("#option-container")
        if 0 <= self.selection < len(container.children):
            option_widget = container.children[self.selection]
            
            # Toggle checked state
            new_checked = not option_widget.checked
            option_widget.checked = new_checked
            
            # Update internal tracking
            if new_checked:
                self.checked_indices = self.checked_indices | {self.selection}
            else:
                self.checked_indices = self.checked_indices - {self.selection}

    def action_toggle_next(self) -> None:
        """Toggle current option and move to next (with wrap-around)."""
        if self.confirmed:
            return
        self._reset_blink()
        
        # Toggle current
        self.action_toggle()
        
        # Move to next with wrap-around
        if len(self.options) > 0:
            self.selection = (self.selection + 1) % len(self.options)

    def action_select_all(self) -> None:
        """Select all options."""
        if self.confirmed:
            return
        self._reset_blink()
        
        container = self.query_one("#option-container")
        for i, child in enumerate(container.children):
            child.checked = True
        
        self.checked_indices = set(range(len(self.options)))

    def action_invert_selection(self) -> None:
        """Invert current selection (toggle all)."""
        if self.confirmed:
            return
        self._reset_blink()
        
        container = self.query_one("#option-container")
        new_checked = set()
        
        for i, child in enumerate(container.children):
            new_state = not child.checked
            child.checked = new_state
            if new_state:
                new_checked.add(i)
        
        self.checked_indices = new_checked


    def action_confirm(self) -> None:
        """Confirm the current selections."""
        if self.confirmed:
            return
        self._reset_blink()
        
        selected_indices = sorted(self.checked_indices)
        selected_answers = [self.options[i] for i in selected_indices]
        
        self.post_message(
            self.Answers(
                indices=selected_indices,
                answers=selected_answers,
            )
        )
        self.confirmed = True

    def action_quit(self) -> None:
        """Cancel the selection."""
        if hasattr(self.app, "exit"):
            self.app.exit(None)

    @on(MultiOption.Selected)
    def on_option_selected(self, event: MultiOption.Selected) -> None:
        """Handle click selection on an option."""
        event.stop()
        self._reset_blink()
        if not self.confirmed:
            self.selection = event.index
            # Also toggle on click
            self.action_toggle()


if __name__ == "__main__":
    from textual.app import App
    from textual.widgets import Footer

    OPTIONS = [
        Answer("Option A", "opt_a", kind="a"),
        Answer("Option B", "opt_b", kind="b"),
        Answer("Option C", "opt_c", kind="c"),
        Answer("Option D", "opt_d"),
    ]

    class MultiQuestionApp(App):
        def compose(self) -> ComposeResult:
            yield MultiQuestion("Select your preferences:", OPTIONS)
            yield Footer()

        def on_multi_question_answers(self, event: MultiQuestion.Answers) -> None:
            self.notify(f"Selected: {[a.text for a in event.answers]}")

    MultiQuestionApp().run(inline=True)
