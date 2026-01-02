from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

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
class SelectionItem:
    text: str
    id: str
    selected: bool = False

Options = List[SelectionItem]

class NonSelectableLabel(Label):
    ALLOW_SELECT = False

class MultiSelectionOption(containers.HorizontalGroup):
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    MultiSelectionOption {
        &:hover {
            background: $boost;
        }
        color: $text-muted;
        
        #cursor {
            width: 1;
            padding-right: 1;
            color: $accent;
            text-style: bold;
            display: block;
            visibility: hidden;
        }
        
        &.-active #cursor {
            visibility: visible;
        }
        
        #status {
            width: 2;
            padding-right: 1;
        }

        #label {
            width: 1fr;
        }

        
        &.-active {
            color: $text;
        }
        
        &.-selected {
            color: $text-accent;
        }
    }
    """

    @dataclass
    class Toggled(Message):
        index: int

    selected: reactive[bool] = reactive(False)
    
    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")
        self.query_one("#status", Label).update("●" if selected else "○")

    def __init__(
        self, index: int, content: Content, selected: bool = False, classes: str = ""
    ) -> None:
        super().__init__(classes=classes)
        self.index = index
        self.content = content
        self.initial_selected = selected

    def compose(self) -> ComposeResult:
        yield Label("❯", id="cursor")
        yield Label("○", id="status")
        yield NonSelectableLabel(self.content, id="label")

    def on_mount(self) -> None:
        self.selected = self.initial_selected

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Toggled(self.index))


class MultiSelection(Widget, can_focus=True):
    """A widget for selecting multiple items."""

    BINDING_GROUP_TITLE = "Selection"
    
    BINDINGS = [
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("space", "toggle", "Toggle"),
        # User requested "Tab realizes next+toggle". Standard tab is often focus move. 
        # But let's map Tab to toggle_and_next as requested.
        Binding("tab", "toggle_next", "Toggle & Next"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    MultiSelection {
        width: 1fr;
        height: auto;
        padding: 0 1; 
        background: transparent;
        #message {
            margin-bottom: 1;
            color: $text-primary;
            text-style: bold;
        }
    }
    """

    message: var[str] = var("")
    options: var[Options] = var(list)
    cursor_index: reactive[int] = reactive(0)

    @dataclass
    class Confirmed(Message):
        selected_ids: List[str]

    def __init__(
        self,
        message: str,
        options: Options,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.set_reactive(MultiSelection.message, message)
        self.set_reactive(MultiSelection.options, options)

    def compose(self) -> ComposeResult:
        yield Label(self.message, id="message")
        with containers.VerticalGroup(id="option-container"):
            for index, item in enumerate(self.options):
                yield MultiSelectionOption(
                    index,
                    Content(item.text),
                    selected=item.selected,
                    classes="-active" if index == 0 else ""
                )

    def watch_cursor_index(self, old_idx: int, new_idx: int) -> None:
        container = self.query_one("#option-container")
        if not container.children:
            return
            
        # Update styling for active cursor
        if 0 <= old_idx < len(self.options):
            container.children[old_idx].remove_class("-active")
        
        if 0 <= new_idx < len(self.options):
            container.children[new_idx].add_class("-active")
            container.children[new_idx].scroll_visible()

    def action_cursor_up(self) -> None:
        self.cursor_index = max(0, self.cursor_index - 1)

    def action_cursor_down(self) -> None:
        self.cursor_index = min(len(self.options) - 1, self.cursor_index + 1)

    def action_toggle(self) -> None:
        self._toggle_current()
    
    def action_toggle_next(self) -> None:
        self._toggle_current()
        if self.options:
             self.cursor_index = (self.cursor_index + 1) % len(self.options)

    def _toggle_current(self) -> None:
        if 0 <= self.cursor_index < len(self.options):
            option_widget = self.query_one("#option-container").children[self.cursor_index]
            # Update internal model
            self.options[self.cursor_index].selected = not self.options[self.cursor_index].selected
            # Update UI
            option_widget.selected = self.options[self.cursor_index].selected

    def action_confirm(self) -> None:
        selected_ids = [opt.id for opt in self.options if opt.selected]
        self.post_message(self.Confirmed(selected_ids))

    def action_quit(self) -> None:
        self.post_message(self.Confirmed([]))

    @on(MultiSelectionOption.Toggled)
    def on_option_toggled(self, event: MultiSelectionOption.Toggled) -> None:
        event.stop()
        self.cursor_index = event.index
        self.action_toggle()
