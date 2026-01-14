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
from textual.widgets import Label, Input

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
        original_index: int  # Added to track original index

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
        self, index: int, original_index: int, content: Content, key: str | None, checked: bool = False, classes: str = ""
    ) -> None:
        super().__init__(classes=classes)
        self.index = index  # Display index (in filtered list)
        self.original_index = original_index  # Original index in self.options
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
        self.post_message(self.Selected(self.index, self.original_index))


class MultiQuestion(Widget, can_focus=True):
    """A question widget that allows selecting multiple answers with fuzzy search."""

    BINDING_GROUP_TITLE = "Multi-Select"
    ALLOW_SELECT = False
    
    BINDINGS = [
        Binding("up", "selection_up", "Up"),
        Binding("down", "selection_down", "Down"),
        Binding("space", "toggle", "Toggle"),
        Binding("tab", "focus_options", "Focus Options"),
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "handle_escape", "Cancel/Exit Search"),
        Binding("ctrl+a", "select_all", "Select All"),
        Binding("ctrl+i", "invert_selection", "Invert"),
        Binding("slash", "toggle_search", "Search", key_display="/"),
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

    MultiQuestion #search-input {
        margin-bottom: 1;
        dock: top;
        background: $surface;
        border: solid $primary;
    }

    MultiQuestion #search-input.-hidden {
        display: none;
    }

    MultiQuestion #search-input:focus {
        border: solid $accent;
    }

    MultiQuestion.-blink MultiOption.-active #caret {
        opacity: 0.2;
    }

    MultiQuestion:blur #checkbox,
    MultiQuestion:blur #caret {
        opacity: 0.3;
    }
    
    MultiQuestion #no-results {
        color: $text-muted;
        padding: 1;
        text-style: italic;
    }
    """

    question: var[str] = var("")
    options: var[Options] = var(list)
    
    selection: reactive[int] = reactive(0, init=False)
    confirmed: var[bool] = var(False)
    blink: var[bool] = var(False)
    
    # Track which options are checked (by original index)
    checked_indices: var[Set[int]] = var(set)
    
    # Search mode state
    search_mode: reactive[bool] = reactive(False)
    filter_text: reactive[str] = reactive("")
    
    # Mapping: list of original indices that match the filter
    filtered_indices: var[List[int]] = var(list)

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
        self.set_reactive(MultiQuestion.filtered_indices, list(range(len(options or []))))

    def on_mount(self) -> None:
        def toggle_blink() -> None:
            if self.has_focus:
                self.blink = not self.blink
            else:
                self.blink = False

        self._blink_timer = self.set_interval(0.5, toggle_blink)
        # Initialize filtered indices
        self.filtered_indices = list(range(len(self.options)))

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
        self.filter_text = ""
        self.search_mode = False
        self.filtered_indices = list(range(len(options)))
        self.refresh(recompose=True, layout=True)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup():
            if self.question:
                yield Label(self.question, id="prompt")
            
            # Search input (hidden by default)
            yield Input(
                placeholder="Type to filter... (ESC to close)",
                id="search-input",
                classes="-hidden" if not self.search_mode else "",
            )

            with containers.VerticalGroup(id="option-container"):
                if not self.filtered_indices:
                    yield Label("No matching options", id="no-results")
                else:
                    for display_idx, original_idx in enumerate(self.filtered_indices):
                        answer = self.options[original_idx]
                        active = display_idx == self.selection
                        checked = original_idx in self.checked_indices
                        key = answer.kind if answer.kind else None
                        yield MultiOption(
                            display_idx,
                            original_idx,
                            Content(answer.text),
                            key,
                            checked=checked,
                            classes=("-active" if active else "") + (" -checked" if checked else ""),
                        )

    def watch_search_mode(self, search_mode: bool) -> None:
        """Toggle search input visibility and focus."""
        try:
            search_input = self.query_one("#search-input", Input)
            if search_mode:
                search_input.remove_class("-hidden")
                search_input.focus()
            else:
                search_input.add_class("-hidden")
                self.filter_text = ""
                self._apply_filter()
                self.focus()
        except Exception:
            pass  # Widget not yet mounted

    def watch_selection(self, old_selection: int, new_selection: int) -> None:
        self.query("#option-container > .-active").remove_class("-active")
        if new_selection >= 0:
            try:
                container = self.query_one("#option-container")
                if new_selection < len(container.children) and not isinstance(container.children[new_selection], Label):
                    container.children[new_selection].add_class("-active")
            except Exception:
                pass

    def watch_blink(self, blink: bool) -> None:
        self.set_class(blink, "-blink")

    def _apply_filter(self) -> None:
        """Apply fuzzy filter and rebuild visible options."""
        if not self.filter_text:
            self.filtered_indices = list(range(len(self.options)))
        else:
            query = self.filter_text.lower()
            self.filtered_indices = [
                i for i, opt in enumerate(self.options)
                if query in opt.text.lower()
            ]
        self.selection = 0
        self._rebuild_options()
    
    def _rebuild_options(self) -> None:
        """Rebuild the option container with filtered options."""
        try:
            container = self.query_one("#option-container")
            container.remove_children()
            
            if not self.filtered_indices:
                container.mount(Label("No matching options", id="no-results"))
            else:
                for display_idx, original_idx in enumerate(self.filtered_indices):
                    answer = self.options[original_idx]
                    active = display_idx == self.selection
                    checked = original_idx in self.checked_indices
                    key = answer.kind if answer.kind else None
                    container.mount(MultiOption(
                        display_idx,
                        original_idx,
                        Content(answer.text),
                        key,
                        checked=checked,
                        classes=("-active" if active else "") + (" -checked" if checked else ""),
                    ))
        except Exception:
            pass

    def _get_original_index(self) -> int | None:
        """Get the original index for the current selection."""
        if 0 <= self.selection < len(self.filtered_indices):
            return self.filtered_indices[self.selection]
        return None

    def _is_search_input_focused(self) -> bool:
        """Check if the search input currently has focus."""
        try:
            search_input = self.query_one("#search-input", Input)
            return search_input.has_focus
        except Exception:
            return False

    def action_toggle_search(self) -> None:
        """Toggle search mode on/off."""
        if self.confirmed:
            return
        self.search_mode = not self.search_mode

    def action_focus_options(self) -> None:
        """Move focus from search input to options (Tab key), or toggle+next if already on options."""
        if self.confirmed:
            return
        
        if self._is_search_input_focused():
            # First Tab: move focus from search input to options
            self.focus()
            self._reset_blink()
        else:
            # Subsequent Tab: toggle current and move to next (like original behavior)
            self.action_toggle_next()

    def action_handle_escape(self) -> None:
        """Handle ESC: exit search mode if active, otherwise quit."""
        if self.search_mode:
            self.search_mode = False
        else:
            self.action_quit()

    def action_selection_up(self) -> None:
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        self.selection = max(0, self.selection - 1)

    def action_selection_down(self) -> None:
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        max_sel = len(self.filtered_indices) - 1
        self.selection = min(max_sel, self.selection + 1)

    def action_toggle(self) -> None:
        """Toggle the currently selected option."""
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        
        original_idx = self._get_original_index()
        if original_idx is None:
            return
            
        container = self.query_one("#option-container")
        if 0 <= self.selection < len(container.children):
            option_widget = container.children[self.selection]
            if isinstance(option_widget, MultiOption):
                # Toggle checked state
                new_checked = not option_widget.checked
                option_widget.checked = new_checked
                
                # Update internal tracking using original index
                if new_checked:
                    self.checked_indices = self.checked_indices | {original_idx}
                else:
                    self.checked_indices = self.checked_indices - {original_idx}

    def action_toggle_next(self) -> None:
        """Toggle current option and move to next (with wrap-around)."""
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        
        # Toggle current
        self.action_toggle()
        
        # Move to next with wrap-around
        if len(self.filtered_indices) > 0:
            self.selection = (self.selection + 1) % len(self.filtered_indices)

    def action_select_all(self) -> None:
        """Select all visible options."""
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        
        container = self.query_one("#option-container")
        for child in container.children:
            if isinstance(child, MultiOption):
                child.checked = True
                self.checked_indices = self.checked_indices | {child.original_index}

    def action_invert_selection(self) -> None:
        """Invert current selection (toggle all visible)."""
        if self.confirmed or self._is_search_input_focused():
            return
        self._reset_blink()
        
        container = self.query_one("#option-container")
        
        for child in container.children:
            if isinstance(child, MultiOption):
                new_state = not child.checked
                child.checked = new_state
                if new_state:
                    self.checked_indices = self.checked_indices | {child.original_index}
                else:
                    self.checked_indices = self.checked_indices - {child.original_index}


    def action_confirm(self) -> None:
        """Confirm the current selections."""
        if self.confirmed:
            return
        # Exit search mode before confirming
        if self.search_mode:
            self.search_mode = False
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
        if not self.confirmed and not self.search_mode:
            self.selection = event.index
            # Also toggle on click
            self.action_toggle()

    @on(Input.Changed, "#search-input")
    def on_search_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        event.stop()
        self.filter_text = event.value
        self._apply_filter()


if __name__ == "__main__":
    from textual.app import App
    from textual.widgets import Footer

    OPTIONS = [
        Answer("GPS Position Data", "gps_pos", kind="a"),
        Answer("IMU Acceleration", "imu_accel", kind="b"),
        Answer("Camera Image Raw", "cam_raw", kind="c"),
        Answer("LiDAR Point Cloud", "lidar_pc"),
        Answer("Vehicle Odometry", "odom"),
        Answer("Wheel Encoder Ticks", "wheel_enc"),
        Answer("Battery Status", "battery"),
        Answer("Temperature Sensor", "temp"),
    ]

    class MultiQuestionApp(App):
        CSS = """
        Screen {
            background: $surface;
        }
        """
        
        BINDINGS = [
            Binding("escape", "quit", "Quit", show=False),
        ]
        
        def compose(self) -> ComposeResult:
            yield MultiQuestion("Select topics to extract (press / to search):", OPTIONS)
            yield Footer()

        def on_multi_question_answers(self, event: MultiQuestion.Answers) -> None:
            self.notify(f"Selected: {[a.text for a in event.answers]}")
            self.exit(event.answers)

    MultiQuestionApp().run(inline=True)

