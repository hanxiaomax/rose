from __future__ import annotations

import os
import glob
from pathlib import Path
from typing import List, Optional, Callable

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive, var
from textual.widget import Widget
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

GLOBAL_BINDINGS = [
    Binding("tab", "autocomplete", "Complete"),
    Binding("down", "cursor_down", "Down", show=True),
    Binding("up", "cursor_up", "Up", show=True),
    Binding("enter", "submit", "Select"),
    Binding("ctrl+c", "quit", "Quit"),
    Binding("escape", "dismiss", "Dismiss"),
]


class PathInput(Widget):
    """
    A widget for path input with auto-completion and directory navigation.
    """

    DEFAULT_CSS = """
    PathInput {
        height: auto;
        width: 100%;
        background: $surface;
    }
    
    PathInput > Input {
        width: 100%;
        background: transparent;
        padding: 0;
        margin: 0;
    }
    
    PathInput > Input:focus {
        background: transparent;
        padding: 0;
        margin: 0;
    }
    
    PathInput > OptionList {
        height: auto;
        max-height: 10;
        width: 100%;
        display: none;
        background: transparent;
        margin-top: 0;
    }
    
    PathInput.show-suggestions > OptionList {
        display: block;
    }
    """
    
    BINDINGS = GLOBAL_BINDINGS

    path = reactive("")
    suggestions = reactive([])
    
    class Submitted(Message):
        """Path submitted."""
        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    class Cancelled(Message):
        """Input cancelled."""
        pass

    def __init__(self, value: str = "", id: str | None = None) -> None:
        super().__init__(id=id)
        self.initial_value = value
        self._suggestion_paths: List[str] = []

    def compose(self) -> ComposeResult:
        yield Input(value=self.initial_value, id="path-input", placeholder="Enter path relative to ./ or absolute...")
        yield OptionList(id="suggestions")
        yield Label("[dim]↑/↓ to navigate, Tab to complete, Enter to select[/]", id="hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()
        self.path = self.initial_value

    def _get_expanded_path(self, path_str: str) -> str:
        """Expand user and vars in path."""
        try:
            return os.path.expanduser(os.path.expandvars(path_str))
        except:
            return path_str

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        self.path = event.value
        self._update_suggestions(self.path)

    def _update_suggestions(self, input_path: str) -> None:
        """Scan directory and update suggestions."""
        # Hide if input is empty
        if not input_path:
            self.remove_class("show-suggestions")
            return

        expanded = self._get_expanded_path(input_path)
        
        # Determine search directory and prefix
        if os.path.isdir(expanded) and not input_path.endswith(os.sep):
             # If exact dir but no slash, maybe user wants to enter it?
             # Or maybe user is typing name of sibling?
             # Standard shell: treat as prefix unless slash is appended
             dirname = os.path.dirname(expanded)
             prefix = os.path.basename(expanded)
        elif os.path.isdir(expanded) and input_path.endswith(os.sep):
            dirname = expanded
            prefix = ""
        else:
            dirname = os.path.dirname(expanded)
            prefix = os.path.basename(expanded)

        if not dirname: 
            dirname = "."
        
        matches = []
        try:
            if os.path.isdir(dirname):
                with os.scandir(dirname) as it:
                    for entry in it:
                        if entry.name.startswith(prefix):
                            # Add slash to dirs
                            name = entry.name + (os.sep if entry.is_dir() else "")
                            matches.append(name)
        except OSError:
            pass

        matches.sort()
        
        # Limit matches to avoid lag
        if len(matches) > 50:
            matches = matches[:50]
            
        self._suggestion_paths = matches
        
        # Update UI
        options = [Option(m) for m in matches]
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        
        if options:
            option_list.add_options(options)
            self.add_class("show-suggestions")
            option_list.highlighted = 0
        else:
            self.remove_class("show-suggestions")

    def action_autocomplete(self) -> None:
        """Handle Tab key for completion."""
        # Check if suggestions visible
        if not self.has_class("show-suggestions"):
            return # Nothing to complete
            
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None and 0 <= option_list.highlighted < len(self._suggestion_paths):
            # Complete with the HIGHLIGHTED suggestion
             selection = self._suggestion_paths[option_list.highlighted]
        else:
            # Or common prefix?
            # Standard: fill with common prefix first
            if not self._suggestion_paths:
                return
            common = os.path.commonprefix(self._suggestion_paths)
            if len(common) > len(os.path.basename(self.path)):
                 selection = common
            elif len(self._suggestion_paths) == 1:
                 selection = self._suggestion_paths[0]
            else:
                 # Rotate selection if multiple?
                 # For now let's just use highlighted if available
                 return 
        
        # Apply completion
        # We need to replace the basename of current input with selection
        current_input = self.query_one(Input).value
        expanded = self._get_expanded_path(current_input)
        
        if current_input.endswith(os.sep):
             # We are in a dir, appending
            new_val = current_input + selection
        else:
            # Replacing basename
            parent = os.path.dirname(current_input)
            if parent:
                new_val = os.path.join(parent, selection)
            else:
                new_val = selection
                
        # Fix: os.path.join might remove trailing slash of parent if empty?
        # Manually:
        # If parent is empty, it means we are in relative root
        
        self.query_one(Input).value = new_val
        self.query_one(Input).cursor_position = len(new_val)

    def action_cursor_down(self) -> None:
        """Move cursor in suggestion list."""
        if self.has_class("show-suggestions"):
            self.query_one(OptionList).action_cursor_down()
        else:
             pass # Maybe history?

    def action_cursor_up(self) -> None:
        """Move cursor in suggestion list."""
        if self.has_class("show-suggestions"):
            self.query_one(OptionList).action_cursor_up()
        else:
            pass

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Input submission (Enter key)."""
        self.action_submit()
        
    def action_submit(self) -> None:
        """Handle Enter key."""
        # 1. Check if OptionList has active highlight
        option_list = self.query_one(OptionList)
        if self.has_class("show-suggestions") and option_list.highlighted is not None:
             idx = option_list.highlighted
             if 0 <= idx < len(self._suggestion_paths):
                 selection = self._suggestion_paths[idx]
                 
                 # If selection is a directory (ends with separator), enter it
                 if selection.endswith(os.sep):
                     self._apply_completion(selection)
                     return
                 else:
                     # File -> Submit
                     current_input = self.query_one(Input).value
                     parent = os.path.dirname(self._get_expanded_path(current_input))
                     full_path = os.path.join(parent, selection) if parent else selection
                     self.post_message(self.Submitted(full_path))
                     return

        # 2. No suggestion selected, process current input
        input_val = self.query_one(Input).value
        expanded = self._get_expanded_path(input_val)
        
        if os.path.isdir(expanded) and not input_val.endswith(os.sep):
             # Enter directory
             new_val = input_val + os.sep
             self.query_one(Input).value = new_val
             self.query_one(Input).cursor_position = len(new_val)
             return

        if os.path.isfile(expanded):
             self.post_message(self.Submitted(expanded))
             return
             
        # Fallback for globs / new files
        if "*" in input_val or "?" in input_val:
             self.post_message(self.Submitted(input_val))
             return
        
        # If path looks like a new file in existing dir?
        # For strict existing file search, maybe error?
        # But for 'load' generic, maybe we accept typed path if user insists?
        # Let's emit it and let higher level validate.
        if input_val.strip():
            self.post_message(self.Submitted(input_val))

    def _apply_completion(self, selection: str) -> None:
        current_input = self.query_one(Input).value
        expanded = self._get_expanded_path(current_input)
        
        if current_input.endswith(os.sep):
             # We are in a dir, appending
            new_val = current_input + selection
        else:
            # Replacing basename
            parent = os.path.dirname(current_input)
            if parent:
                new_val = os.path.join(parent, selection)
                # Keep trailing slash if selection had it
                if selection.endswith(os.sep) and not new_val.endswith(os.sep):
                    new_val += os.sep
            else:
                new_val = selection
                
        self.query_one(Input).value = new_val
        self.query_one(Input).cursor_position = len(new_val)

    def action_quit(self) -> None:
        self.post_message(self.Cancelled())

    def action_dismiss(self) -> None:
        self.post_message(self.Cancelled())
