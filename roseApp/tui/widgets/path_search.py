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
from textual.widgets import Input, Label, OptionList, DirectoryTree
from textual.widgets.option_list import Option



GLOBAL_BINDINGS = [
    Binding("tab", "autocomplete", "Complete"),
    Binding("down", "cursor_down", "Down", show=True),
    Binding("up", "cursor_up", "Up", show=True),
    Binding("enter", "submit", "Select"),
    Binding("ctrl+t", "toggle_tree", "Toggle View"),
    Binding("ctrl+c", "quit", "Quit"),
    Binding("escape", "dismiss", "Dismiss"),
]

def get_default_bag_validator(allow_multiple: bool = True) -> Callable[[str], Optional[str]]:
    """
    Returns a validator function for .bag files.
    
    Args:
        allow_multiple: Whether to allow matching multiple files via glob.
    """
    def validate(path: str) -> Optional[str]:
        if not path:
             return "Please enter a path."
             
        # Rule 1: Disallow raw directories (require * or file)
        if os.path.isdir(path):
            return "Please select a file or use a glob pattern (e.g. /*) to match files."

        # Rule 2: If it's an existing file, must be .bag
        if os.path.isfile(path):
            if not path.endswith(".bag"):
                return "Selected file must be a .bag file."
            return None # Valid file
            
        # Rule 3: Glob patterns
        if glob.has_magic(path):
             matches = glob.glob(path)
             if not matches:
                 return f"No match for pattern: {path}"
             
             # Filter only .bag files
             bag_matches = [m for m in matches if m.endswith(".bag")]
             
             if not bag_matches:
                 return f"No .bag files found matching pattern: {path}"

             if not allow_multiple and len(bag_matches) > 1:
                 return f"Ambiguous glob: matches {len(bag_matches)} .bag files. Please select a single file."
                 
             return None # Valid glob
             
        # Fallback
        return "File not found."
    return validate


class PathInputField(Input):
    """Input with explicit bindings for Footer visibility."""
    
    # We explicitly bind enter here so it shows up in Footer while Input handles the event
    BINDINGS = GLOBAL_BINDINGS


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree with prefix filter support (Linux-style)."""
    
    filter_text: reactive[str] = reactive("", init=False)
    
    def filter_paths(self, paths):
        """Filter paths based on current filter text using prefix matching (Linux-style)."""
        if not self.filter_text:
            return paths
        
        filter_lower = self.filter_text.lower()
        result = []
        
        for path in paths:
            name_lower = path.name.lower()
            # Linux-style prefix match
            if name_lower.startswith(filter_lower):
                result.append(path)
        
        return result
    
    def watch_filter_text(self, old_val: str, new_val: str) -> None:
        """Reload tree when filter changes."""
        if old_val != new_val:
            self.reload()

class PathInput(Widget):
    """
    A widget for path input with auto-completion and directory navigation.
    """
    
    # Parent bindings for navigation that Input ignores
    BINDINGS = GLOBAL_BINDINGS

    path = reactive("")
    suggestions = reactive([])
    tree_mode = reactive(False)  # Toggle between suggestion and tree mode
    
    DEFAULT_CSS = """
    PathInput {
        height: auto;
        width: 100%;
        background: $surface;
    }

    PathInput > PathInputField {
        width: 100%;
        border: round $primary;
        padding: 0 1;
        background: $surface;
        height: auto;
        margin: 0;
    }

    PathInput > PathInputField:focus {
        border: none;
        background: $surface;
        padding: 0;
        margin: 0;
    }

    PathInput > OptionList {
        height: auto;
        max-height: 10;
        width: 100%;
        display: none;
        background: $surface;
        border: none;
        margin-top: 0;
        padding: 0;
    }

    PathInput.show-suggestions > OptionList {
        display: block;
        border: round $primary;
        margin-top: 0;
    }

    /* When suggestions are shown, merge borders */
    PathInput.show-suggestions > PathInputField {
        border: none;
        height: auto;
    }

    PathInput > OptionList > .option-list--option-highlighted {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    /* Tree view mode */
    PathInput > DirectoryTree {
        display: none;
        height: auto;
        max-height: 15;
        width: 100%;
        background: $surface;
        border: round $primary;
        margin-top: 0;
        padding: 0;
    }

    PathInput.tree-mode > DirectoryTree {
        display: block;
    }

    PathInput.tree-mode > OptionList {
        display: none;
    }
    """

    
    class Submitted(Message):
        """Path submitted."""
        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    class Cancelled(Message):
        """Input cancelled."""
        pass

    class TreeModeRequested(Message):
        """User requested to switch to tree mode."""
        def __init__(self, current_path: str) -> None:
            self.current_path = current_path
            super().__init__()

    def __init__(
        self, 
        value: str = "", 
        id: str | None = None,
        validator: Optional[Callable[[str], Optional[str]]] = None,
        default_tree_mode: bool = True,
    ) -> None:
        super().__init__(id=id)
        self.initial_value = value
        self._suggestion_paths: List[str] = []
        self.validator = validator
        self._default_tree_mode = default_tree_mode

    def compose(self) -> ComposeResult:
        yield PathInputField(value=self.initial_value, id="path-input", placeholder="Enter path... (Ctrl+T to toggle view)")
        yield OptionList(id="suggestions")
        # Start tree at current working directory or initial value
        start_dir = self._get_start_dir()
        yield FilteredDirectoryTree(start_dir, id="tree-view")

    def _get_start_dir(self) -> str:
        """Get starting directory for tree view."""
        if self.initial_value:
            expanded = self._get_expanded_path(self.initial_value)
            if os.path.isdir(expanded):
                return expanded
            elif os.path.isfile(expanded):
                return os.path.dirname(expanded)
        return os.getcwd()

    def on_mount(self) -> None:
        self.query_one(PathInputField).focus()
        self.path = self.initial_value
        
        # Apply default view mode
        if self._default_tree_mode:
            self.tree_mode = True
            self.add_class("tree-mode")

    def _get_expanded_path(self, path_str: str) -> str:
        """Expand user and vars in path."""
        try:
            return os.path.expanduser(os.path.expandvars(path_str))
        except:
            return path_str

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        self.path = event.value
        if self.tree_mode:
            self._filter_tree(self.path)
        else:
            self._update_suggestions(self.path)

    def _filter_tree(self, filter_text: str) -> None:
        """Filter tree view based on input text."""
        try:
            tree = self.query_one("#tree-view", FilteredDirectoryTree)
            
            # Check if input is a valid directory path - navigate to it
            if filter_text:
                expanded = self._get_expanded_path(filter_text)
                if os.path.isdir(expanded) and expanded != str(tree.path):
                    tree.path = expanded
                    tree.filter_text = ""  # Clear filter when navigating
                    return
            
            # Otherwise, use as fuzzy filter for current directory
            # Extract just the filename portion for filtering
            basename = os.path.basename(filter_text) if filter_text else ""
            tree.filter_text = basename
        except Exception:
            pass

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
            # Ensure footer knows we can nav up/down
        else:
            self.remove_class("show-suggestions")

    def action_autocomplete(self) -> None:
        """Handle Tab key for completion."""

        # Tree mode: Tab completes based on cursor position
        if self.tree_mode:
            try:
                tree = self.query_one("#tree-view", FilteredDirectoryTree)
                input_field = self.query_one(PathInputField)
                tree_path = Path(tree.path)
                filter_text = tree.filter_text or ""
                
                # First, check if cursor is on a specific node
                cursor_node = tree.cursor_node
                if cursor_node is not None and cursor_node.data and hasattr(cursor_node.data, 'path'):
                    selected_path = cursor_node.data.path
                    if selected_path.is_dir():
                        new_path = str(selected_path) + os.sep
                        input_field.value = new_path
                        input_field.cursor_position = len(new_path)
                        tree.path = selected_path
                        tree.filter_text = ""
                    else:
                        new_path = str(selected_path)
                        input_field.value = new_path
                        input_field.cursor_position = len(new_path)
                        self.notify(f"Completed: {selected_path.name}. Press Enter to confirm.", severity="information")
                    return
                
                # No cursor selection: fall back to first match if filter is active
                if tree_path.is_dir() and filter_text:
                    # Find matching items using prefix matching (Linux-style)
                    matches = []
                    filter_lower = filter_text.lower()
                    
                    try:
                        for item in tree_path.iterdir():
                            name_lower = item.name.lower()
                            # Linux-style prefix match
                            if name_lower.startswith(filter_lower):
                                matches.append(item)
                    except PermissionError:
                        pass
                    
                    if matches:
                        # Sort: directories first, then by name
                        matches.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
                        first_match = matches[0]
                        
                        if first_match.is_dir():
                            new_path = str(first_match) + os.sep
                            input_field.value = new_path
                            input_field.cursor_position = len(new_path)
                            tree.path = first_match
                            tree.filter_text = ""
                        else:
                            new_path = str(first_match)
                            input_field.value = new_path
                            input_field.cursor_position = len(new_path)
                            self.notify(f"Completed: {first_match.name}. Press Enter to confirm.", severity="information")
                        return
                    else:
                        self.notify(f"No match for: {filter_text}", severity="warning")
                        return
            except Exception:
                pass
            return
        # Bubble up from Input
        
        # Check if suggestions visible
        if not self.has_class("show-suggestions"):
            return # Nothing to complete
            
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None and 0 <= option_list.highlighted < len(self._suggestion_paths):
            # Complete with the HIGHLIGHTED suggestion
             selection = self._suggestion_paths[option_list.highlighted]
        else:
            # Standard: fill with common prefix first
            if not self._suggestion_paths:
                return
            common = os.path.commonprefix(self._suggestion_paths)
            if len(common) > len(os.path.basename(self.path)):
                 selection = common
            elif len(self._suggestion_paths) == 1:
                 selection = self._suggestion_paths[0]
            else:
                 return 
        
        self._apply_completion(selection)

    def action_cursor_up(self) -> None:
        """Move cursor in suggestion list or tree."""
        if self.tree_mode:
            tree = self.query_one("#tree-view", FilteredDirectoryTree)
            tree.action_cursor_up()
        elif self.has_class("show-suggestions"):
            self.query_one(OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move cursor in suggestion list or tree."""
        if self.tree_mode:
            tree = self.query_one("#tree-view", FilteredDirectoryTree)
            tree.action_cursor_down()
        elif self.has_class("show-suggestions"):
            self.query_one(OptionList).action_cursor_down()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Input submission (Enter key)."""
        event.stop() # we handle it
        self.action_submit()
        
    def _validate_and_submit(self, path: str) -> None:
        """Run validation and submit if valid."""
        if self.validator:
            error = self.validator(path)
            
            if error:
                # Use Notify for error
                self.notify(error, title="Invalid Path", severity="error")
                return
        
        self.post_message(self.Submitted(path))

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
                     current_input = self.query_one(PathInputField).value
                     parent = os.path.dirname(self._get_expanded_path(current_input))
                     full_path = os.path.join(parent, selection) if parent else selection
                     self._validate_and_submit(full_path)
                     return

        # 2. No suggestion selected, process current input
        input_val = self.query_one(PathInputField).value
        expanded = self._get_expanded_path(input_val)
        
        if os.path.isdir(expanded) and not input_val.endswith(os.sep):
             # Enter directory
             new_val = input_val + os.sep
             self.query_one(PathInputField).value = new_val
             self.query_one(PathInputField).cursor_position = len(new_val)
             return

        if os.path.isfile(expanded):
             self._validate_and_submit(expanded)
             return
             
        # Fallback for globs / new files
        if "*" in input_val or "?" in input_val:
             self._validate_and_submit(input_val)
             return
        
        # Explicit submit of typed path
        if input_val.strip():
            self._validate_and_submit(input_val)

    def _apply_completion(self, selection: str) -> None:
        current_input = self.query_one(PathInputField).value
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
                
        self.query_one(PathInputField).value = new_val
        self.query_one(PathInputField).cursor_position = len(new_val)

    def action_quit(self) -> None:
        self.post_message(self.Cancelled())

    def action_dismiss(self) -> None:
        self.post_message(self.Cancelled())

    def action_toggle_tree(self) -> None:
        """Toggle between suggestion and tree view mode."""
        self.tree_mode = not self.tree_mode
        
        if self.tree_mode:
            self.add_class("tree-mode")
            self.remove_class("show-suggestions")
            # Update tree path based on current input
            current_path = self.query_one(PathInputField).value
            expanded = self._get_expanded_path(current_path) if current_path else os.getcwd()
            if os.path.isdir(expanded):
                try:
                    tree = self.query_one("#tree-view", FilteredDirectoryTree)
                    tree.path = expanded
                    tree.filter_text = ""  # Clear filter when switching modes
                except:
                    pass
            self.notify("Tree view mode (Ctrl+E to switch back)", severity="information")
        else:
            self.remove_class("tree-mode")
            self._update_suggestions(self.path)
            self.notify("Suggestion mode", severity="information")

    @on(DirectoryTree.FileSelected)
    def on_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection from tree - update input field instead of auto-submitting."""
        event.stop()
        selected_path = str(event.path)
        input_field = self.query_one(PathInputField)
        input_field.value = selected_path
        input_field.cursor_position = len(selected_path)
        self.notify(f"Selected: {event.path.name}. Press Enter to confirm.", severity="information")

    @on(DirectoryTree.DirectorySelected) 
    def on_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection from tree - update input field."""
        event.stop()
        selected_path = str(event.path) + os.sep
        self.query_one(PathInputField).value = selected_path
        self.query_one(PathInputField).cursor_position = len(selected_path)


