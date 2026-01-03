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
from textual.widgets import Label, Input
from rich.text import Text
import re


GLOBAL_BINDINGS = [
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("space", "toggle", "Toggle"),
        # User requested "Tab realizes next+toggle". Standard tab is often focus move. 
        # But let's map Tab to toggle_and_next as requested.
        Binding("tab", "toggle_next", "Toggle & Next"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "quit", "Quit", show=False),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("f", "focus_filter", "Filter", show=False),
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+l", "load_new", "Load New", show=True), # Hidden from default footer if not active
    ]
@dataclass
class SelectionItem:
    text: str
    id: str
    selected: bool = False

Options = List[SelectionItem]

class NonSelectableLabel(Label):
    ALLOW_SELECT = False

class SearchInput(Input):
    """Input that bubbles vertical nav and hides footer spam."""
    
    BINDINGS = GLOBAL_BINDINGS

    def _on_key(self, event: events.Key) -> None:
        # Forward navigation keys to parent by not handling them here (not calling super)
        # However, Textual events bubble if not stopped. Input._on_key stops them?
        # Yes, standard Input handles keys and likely stops valid inputs.
        # But 'up'/'down' are not valid inputs for single-line Input unless used for history?
        # We explicitly skip handling them so they bubble.
        
        if event.key == "escape":
             # Let parent handle escape to clear focus
             return
             
        elif event.key == "down":
             # Special handling for Down: if we are at the bottom or just generally,
             # we might want to move focus to the list?
             # For now, we just bubble it so cursor moves.
             # But if user wants to toggle items, they need to leave input.
             # Let's keep bubble behavior.
             return

        if event.key in ("up", "down", "ctrl+c"):
             return 
        
        # For Enter, we want it to trigger SUBMIT which is handled by Input.
        # So we let super handle it.
        super()._on_key(event)

class MultiSelectionOption(containers.HorizontalGroup):
    ALLOW_SELECT = False
    DEFAULT_CSS = ""

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
    
    BINDINGS = GLOBAL_BINDINGS

    DEFAULT_CSS = ""

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
        load_new_id: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.set_reactive(MultiSelection.message, message)
        self.set_reactive(MultiSelection.options, options)
        self.load_new_id = load_new_id

    display_options: var[List[tuple[int, SelectionItem, Text]]] = var(list)

    def compose(self) -> ComposeResult:
        yield Label(self.message, id="message")
        yield SearchInput(id="search", placeholder="Filter...")
        if self.load_new_id:
            # Add hint for loading new
            yield Label("[dim]Hint: Press 'l' to load new file...[/dim]", classes="hint")
            
        with containers.VerticalGroup(id="option-container"):
            pass # Children will be mounted dynamically

    def on_mount(self) -> None:
        self._update_display_options("")
        self._mount_options()
        self.query_one("#search").focus()

    @on(Input.Changed) # SearchInput matches Input.Changed
    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_display_options(event.value)
        self._mount_options()
        # Reset cursor to top when searching
        self.cursor_index = 0

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_confirm()

    def _update_display_options(self, query: str) -> None:
        """Filter options and prepare styled text."""
        result = []
        if not query:
            for i, opt in enumerate(self.options):
                result.append((i, opt, Text(opt.text)))
        else:
            # Fuzzy subsequence match
            # Pattern: .*c.*h.*a.*r.* case insensitive
            query = query.lower()
            for i, opt in enumerate(self.options):
                text_lower = opt.text.lower()
                
                # Check if query is subsequence of text
                match_indices = []
                last_idx = -1
                failed = False
                for char in query:
                    try:
                        idx = text_lower.index(char, last_idx + 1)
                        match_indices.append(idx)
                        last_idx = idx
                    except ValueError:
                        failed = True
                        break
                
                if not failed:
                    # Highlight matches
                    styled_text = Text(opt.text)
                    for idx in match_indices:
                        styled_text.stylize("bold underline reverse", idx, idx + 1)
                    result.append((i, opt, styled_text))
        
        self.display_options = result

    def _mount_options(self) -> None:
        container = self.query_one("#option-container")
        container.remove_children()
        
        for idx in range(len(self.display_options)):
            orig_idx, item, styled_text = self.display_options[idx]
            container.mount(
                MultiSelectionOption(
                    orig_idx, # Keep original index for referencing self.options
                    styled_text,
                    selected=item.selected,
                    classes="-active" if idx == 0 else ""
                )
            )

    def watch_cursor_index(self, old_idx: int, new_idx: int) -> None:
        container = self.query_one("#option-container")
        if not container.children:
            return
            
        # Update styling for active cursor
        if 0 <= old_idx < len(self.display_options):
            container.children[old_idx].remove_class("-active")
        
        if 0 <= new_idx < len(self.display_options):
            container.children[new_idx].add_class("-active")
            container.children[new_idx].scroll_visible()

    def action_cursor_up(self) -> None:
        self.cursor_index = max(0, self.cursor_index - 1)

    def action_cursor_down(self) -> None:
        self.cursor_index = min(len(self.display_options) - 1, self.cursor_index + 1)

    def _toggle_current(self) -> None:
        if 0 <= self.cursor_index < len(self.display_options):
            option_widget = self.query_one("#option-container").children[self.cursor_index]
            
            # Map visual index to original index
            original_index, _, _ = self.display_options[self.cursor_index]
            
            # Update internal model
            self.options[original_index].selected = not self.options[original_index].selected
            # Update UI
            option_widget.selected = self.options[original_index].selected

    def action_toggle_next(self) -> None:
        self._toggle_current()
        if self.display_options:
             self.cursor_index = (self.cursor_index + 1) % len(self.display_options)

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

    def action_load_new(self) -> None:
        """Handle 'l' shortcut to load new items."""
        if self.load_new_id:
            self.post_message(self.Confirmed([self.load_new_id]))

    def action_toggle(self) -> None:
        self._toggle_current()

    def action_focus_filter(self) -> None:
        self.query_one("#search").focus()
        
    def action_clear_filter_focus(self) -> None:
        self.focus()
