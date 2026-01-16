"""
TUI for List/Cache Management.

Provides an interactive interface for viewing and managing cached bag files.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Container, HorizontalGroup
from textual.widgets import Label, Static, Footer, DataTable
from textual.reactive import reactive
from textual.message import Message
from textual.screen import ModalScreen

from pathlib import Path
from typing import List, Dict, Any, Optional
import pickle

from .theme import ALL_THEMES
from .widgets.question import Question, Answer
from ..core.config import get_config
from ..core.cache import get_cache
from ..core.model import BagInfo


class CacheEntryRow:
    """Data structure for cache entry display."""
    def __init__(self, key: str, value: Any, cache_type: str, idx: int):
        self.key = key
        self.value = value
        self.cache_type = cache_type
        self.idx = idx
        
        # Extract display info
        self.bag_name = key
        self.bag_path = "Unknown"
        self.size_mb = 0.0
        self.topics_count = 0
        self.has_index = False
        self.duration_sec = 0.0
        
        if isinstance(value, BagInfo):
            self.bag_name = Path(getattr(value, 'file_path', key)).name
            self.bag_path = getattr(value, 'file_path', 'Unknown')
            self.size_mb = value.file_size / 1024 / 1024 if value.file_size else 0
            self.topics_count = len(getattr(value, 'topics', []))
            self.has_index = getattr(value, 'has_message_index', lambda: False)()
            self.duration_sec = getattr(value, 'duration_seconds', 0)


class ConfirmDeleteDialog(ModalScreen[bool]):
    """Confirmation dialog for deleting cache entries."""
    
    DEFAULT_CSS = """
    ConfirmDeleteDialog {
        align: center middle;
    }
    
    #confirm-container {
        width: 60;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1;
    }
    
    #confirm-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    
    #confirm-message {
        margin-bottom: 1;
    }
    """
    
    def __init__(self, entry_count: int, entries_info: str = ""):
        super().__init__()
        self.entry_count = entry_count
        self.entries_info = entries_info
        
    def compose(self) -> ComposeResult:
        with Container(id="confirm-container"):
            yield Label("Confirm Deletion", id="confirm-title")
            msg = f"Delete {self.entry_count} cache entries?"
            if self.entries_info:
                msg += f"\n\n{self.entries_info}"
            yield Label(msg, id="confirm-message")
            
            q = Question(
                question="",
                options=[
                    Answer("Yes, delete", "yes"),
                    Answer("No, cancel", "no"),
                ]
            )
            q.action_quit = lambda: self.dismiss(False)
            yield q
    
    def on_question_answer(self, message: Any) -> None:
        self.dismiss(message.answer.id == "yes")
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True)
    ]
    
    def action_cancel(self) -> None:
        self.dismiss(False)


class ListApp(App):
    """TUI for Cache Management."""
    
    CSS = """
    ListApp {
        background: $surface;
        min-height: 20;
    }
    
    #header {
        height: auto;
        padding: 1 2;
    }
    
    #title {
        text-align: center;
        text-style: bold;
        color: $primary;
    }
    
    #stats {
        text-align: center;
        color: $text-muted;
    }
    
    #table-container {
        height: auto;
        max-height: 80%;
        padding: 0 1;
    }
    
    DataTable {
        height: auto;
        max-height: 20;
    }
    
    #hint {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-top: 1;
    }
    """
    
    ENABLE_COMMAND_PALETTE = False
    
    BINDINGS = [
        Binding("space", "show_details", "Details", show=True),
        Binding("d", "delete_selected", "Delete", show=True),
        Binding("delete", "delete_selected", "Delete", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("c", "clear_all", "Clear All", show=True),
        Binding("escape", "quit", "Exit", show=True),
        Binding("q", "quit", "Quit", show=False),
    ]
    
    deleted_count: reactive[int] = reactive(0)
    
    def __init__(self):
        super().__init__()
        
        # Instance variable for entries (not class variable)
        self.entries: List[CacheEntryRow] = []
        
        # Register themes
        for name, theme in ALL_THEMES.items():
            self.register_theme(theme)
        
        # Set current theme
        config = get_config()
        theme_name = "claude"
        parts = config.theme_file.split('.')
        if len(parts) >= 3:
            theme_name = parts[2]
        
        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"
    
    def _load_entries(self) -> None:
        """Load cache entries."""
        self.entries = []
        try:
            cache = get_cache()
            all_entries = self._get_all_cache_entries(cache)
            
            for idx, (key, value, cache_type) in enumerate(all_entries, 1):
                self.entries.append(CacheEntryRow(key, value, cache_type, idx))
        except Exception as e:
            self.notify(f"Error loading cache: {e}", severity="error")
    
    def _get_all_cache_entries(self, cache) -> List[tuple]:
        """Get all cache entries from disk."""
        all_entries = []
        seen_keys = set()
        
        if hasattr(cache, 'cache_dir'):
            for file_path in cache.cache_dir.glob("*.pkl"):
                try:
                    with open(file_path, 'rb') as f:
                        value = pickle.load(f)
                    key = file_path.stem
                    if key not in seen_keys:
                        all_entries.append((key, value, 'disk'))
                        seen_keys.add(key)
                except Exception:
                    continue
        
        return all_entries
    
    def compose(self) -> ComposeResult:
        with Vertical(id="header"):
            yield Label("Cache Manager", id="title")
            yield Label(self._get_stats_text(), id="stats")
        
        with Container(id="table-container"):
            table = DataTable(id="cache-table")
            table.cursor_type = "row"
            yield table
        
        yield Label("↑↓ Navigate  Space Details  D Delete  R Refresh  C Clear All  Esc Exit", id="hint")
        yield Footer()
    
    def _get_stats_text(self) -> str:
        total = len(self.entries)
        total_size = sum(e.size_mb for e in self.entries)
        indexed = sum(1 for e in self.entries if e.has_index)
        return f"{total} entries | {total_size:.1f} MB | {indexed} indexed"
    
    def on_mount(self) -> None:
        """Initialize table with data."""
        table = self.query_one("#cache-table", DataTable)
        
        # Add columns
        table.add_column("ID", width=4)
        table.add_column("File", width=30)
        table.add_column("Size", width=10)
        table.add_column("Topics", width=7)
        table.add_column("Duration", width=10)
        table.add_column("Index", width=7)
        
        # Load entries
        self._load_entries()
        self._populate_table()
        
        if not self.entries:
            self.notify("Cache is empty", severity="information")

    
    def _populate_table(self) -> None:
        """Populate table with current entries."""
        table = self.query_one("#cache-table", DataTable)
        table.clear()
        
        for entry in self.entries:
            index_str = "✓" if entry.has_index else "✗"
            table.add_row(
                str(entry.idx),
                entry.bag_name[:28] + ".." if len(entry.bag_name) > 30 else entry.bag_name,
                f"{entry.size_mb:.1f} MB",
                str(entry.topics_count),
                f"{entry.duration_sec:.1f}s",
                index_str,
                key=entry.key,
            )
        
        # Update stats
        self.query_one("#stats", Label).update(self._get_stats_text())
    
    def action_refresh(self) -> None:
        """Refresh the cache list."""
        self._load_entries()
        self._populate_table()
        self.notify("Cache refreshed", severity="information")
    
    def action_show_details(self) -> None:
        """Show details for the currently selected cache entry."""
        table = self.query_one("#cache-table", DataTable)
        
        if not table.row_count:
            self.notify("No entries to show", severity="warning")
            return
        
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key is None:
            return
        
        # Find entry by key
        entry = next((e for e in self.entries if e.key == row_key.value), None)
        if not entry:
            return
        
        # Build details message
        index_status = "Yes" if entry.has_index else "No"
        details = (
            f"File: {entry.bag_name}\n"
            f"Path: {entry.bag_path}\n"
            f"Size: {entry.size_mb:.2f} MB\n"
            f"Topics: {entry.topics_count}\n"
            f"Duration: {entry.duration_sec:.2f}s\n"
            f"Message Index: {index_status}"
        )
        
        self.notify(details, title="Bag Details", timeout=10)
    
    def action_delete_selected(self) -> None:
        """Delete selected cache entry."""
        table = self.query_one("#cache-table", DataTable)
        
        if not table.row_count:
            self.notify("No entries to delete", severity="warning")
            return
        
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key is None:
            return
        
        # Find entry by key
        entry = next((e for e in self.entries if e.key == row_key.value), None)
        if not entry:
            return
        
        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                self._delete_entry(entry)
        
        self.push_screen(
            ConfirmDeleteDialog(1, entry.bag_name),
            handle_confirm
        )
    
    def action_clear_all(self) -> None:
        """Clear all cache entries."""
        if not self.entries:
            self.notify("Cache is empty", severity="warning")
            return
        
        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                self._clear_all()
        
        self.push_screen(
            ConfirmDeleteDialog(len(self.entries), f"{len(self.entries)} entries"),
            handle_confirm
        )
    
    def _delete_entry(self, entry: CacheEntryRow) -> None:
        """Delete a single cache entry."""
        try:
            cache = get_cache()
            cache_file = cache.cache_dir / f"{entry.key}.pkl"
            
            if cache_file.exists():
                cache_file.unlink()
                self.entries.remove(entry)
                self._populate_table()
                self.deleted_count += 1
                self.notify(f"Deleted: {entry.bag_name}", severity="information")
            else:
                self.notify(f"Cache file not found", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
    
    def _clear_all(self) -> None:
        """Clear all cache entries."""
        try:
            cache = get_cache()
            count = len(self.entries)
            cache.clear()
            self.entries.clear()
            self._populate_table()
            self.deleted_count += count
            self.notify(f"Cleared {count} entries", severity="information")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
    
    def action_quit(self) -> None:
        self.exit(self.deleted_count)


def run_list_app() -> int:
    """Run the list TUI and return number of deleted entries."""
    app = ListApp()
    app.run(inline=True)
    return app.deleted_count


if __name__ == "__main__":
    run_list_app()
