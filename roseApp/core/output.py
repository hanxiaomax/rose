"""
Unified output interface for Rose CLI.

Provides consistent styling and theme support for all CLI output.
All CLI commands should use this interface instead of direct console.print() calls.
"""

import yaml
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Any, Dict, Generator

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text


class ThemeColors:
    """Theme color definitions with defaults."""
    
    def __init__(self, theme_data: Optional[Dict[str, str]] = None):
        """
        Initialize theme colors.
        
        Args:
            theme_data: Dictionary of color definitions from theme file
        """
        data = theme_data or {}
        
        # Core colors
        self.primary = data.get("primary", "cyan")
        self.accent = data.get("accent", "cyan")
        
        # Status colors
        self.success = data.get("success", "green")
        self.warning = data.get("warning", "yellow")
        self.error = data.get("error", "red")
        self.info = data.get("info", "cyan")
        
        # UI colors
        self.muted = data.get("muted", "dim")
        self.highlight = data.get("highlight", "bold white")
        
        # Semantic colors
        self.path = data.get("path", "cyan")


class Output:
    """
    Unified output interface with theme support.
    
    All CLI commands should use this interface instead of
    direct console.print() calls.
    
    Usage:
        from roseApp.core.output import get_output
        
        out = get_output()
        out.info("Processing files...")
        out.success("Done!")
        out.error("Something went wrong")
    """
    
    def __init__(self, theme_file: Optional[str] = None, enable_colors: bool = True):
        """
        Initialize output interface.
        
        Args:
            theme_file: Path to theme YAML file
            enable_colors: Whether to enable colored output
        """
        self._console = Console(force_terminal=enable_colors, no_color=not enable_colors)
        self._err_console = Console(stderr=True, force_terminal=enable_colors, no_color=not enable_colors)
        self._enable_colors = enable_colors
        self._theme = self._load_theme(theme_file)
    
    def _load_theme(self, theme_file: Optional[str] = None) -> ThemeColors:
        """
        Load theme from configuration file.
        
        Args:
            theme_file: Path to theme YAML file
            
        Returns:
            ThemeColors instance
        """
        theme_data = {}
        
        if theme_file:
            theme_path = Path(theme_file)
            if not theme_path.exists():
                # Try relative to project root
                project_root = Path(__file__).parent.parent.parent
                theme_path = project_root / theme_file
            
            if theme_path.exists():
                try:
                    with open(theme_path) as f:
                        theme_data = yaml.safe_load(f) or {}
                except Exception:
                    pass  # Use defaults on error
        
        return ThemeColors(theme_data)
    
    def set_theme(self, theme_file: str) -> None:
        """
        Switch theme at runtime.
        
        Args:
            theme_file: Path to new theme file
        """
        self._theme = self._load_theme(theme_file)
    
    # === Basic Messages ===
    
    def print(self, message: str, style: Optional[str] = None) -> None:
        """
        Print a message with optional style.
        
        Args:
            message: Message to print
            style: Rich style string
        """
        self._console.print(message, style=style)
    
    def info(self, message: str) -> None:
        """
        Print info message.
        
        Args:
            message: Info message
        """
        self._console.print(message, style=self._theme.info)
    
    def success(self, message: str) -> None:
        """
        Print success message with checkmark.
        
        Args:
            message: Success message
        """
        self._console.print(f"[{self._theme.success}][OK][/{self._theme.success}] {message}")
    
    def warning(self, message: str) -> None:
        """
        Print warning message.
        
        Args:
            message: Warning message
        """
        self._console.print(f"[{self._theme.warning}][WARN][/{self._theme.warning}] {message}")
    
    def error(self, message: str, details: Optional[str] = None) -> None:
        """
        Print error message to stderr.
        
        Args:
            message: Error message
            details: Optional additional details
        """
        self._err_console.print(f"[{self._theme.error}][ERROR][/{self._theme.error}] {message}")
        if details:
            self._err_console.print(f"  {details}", style=self._theme.muted)
    
    def debug(self, message: str) -> None:
        """
        Print debug message (muted style).
        
        Args:
            message: Debug message
        """
        self._console.print(message, style=self._theme.muted)
    
    # === Progress Indicators ===
    
    @contextmanager
    def spinner(self, message: str) -> Generator[None, None, None]:
        """
        Context manager for spinner progress indicator.
        
        Args:
            message: Message to display with spinner
            
        Usage:
            with out.spinner("Loading..."):
                do_work()
        """
        with self._console.status(f"[{self._theme.info}]{message}[/{self._theme.info}]"):
            yield
    
    @contextmanager
    def progress_bar(self, total: int, description: str = "Processing") -> Generator[Progress, None, None]:
        """
        Context manager for progress bar.
        
        Args:
            total: Total number of items
            description: Description text
            
        Yields:
            Progress object with task_id attribute for updating
            
        Usage:
            with out.progress_bar(100, "Loading") as progress:
                for i in range(100):
                    progress.update(progress.task_id, advance=1)
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[{self._theme.info}]{{task.description}}[/{self._theme.info}]"),
            BarColumn(complete_style=self._theme.accent, finished_style=self._theme.success),
            TaskProgressColumn(),
            console=self._console
        )
        
        with progress:
            task_id = progress.add_task(description, total=total)
            progress.task_id = task_id  # Store for easy access
            yield progress
    
    @contextmanager
    def live_status(self, message: str, total: Optional[int] = None) -> Generator['LiveStatus', None, None]:
        """
        Context manager for live status with spinner that allows real-time output.
        
        Args:
            message: Initial status message
            total: Optional total count for progress display
            
        Yields:
            LiveStatus object with update() and log() methods
            
        Usage:
            with out.live_status("Processing", total=5) as status:
                for i, item in enumerate(items):
                    status.update(f"Processing {item}... [{i+1}/5]")
                    result = process(item)
                    status.log(f"Done: {item}")
        """
        status = LiveStatus(self._console, self._theme, message, total)
        with status:
            yield status
    
    def spin_print(self, message: str) -> None:
        """
        Print a status message with spinner icon (static, non-animated).
        Use this for showing 'in progress' state before actual work.
        
        Args:
            message: Status message
        """
        # Using a simple arrow to indicate processing
        self._console.print(f"  [{self._theme.info}]⟳[/{self._theme.info}] {message}")
    
    def status_item(self, message: str, status: str = "processing") -> None:
        """
        Print a status item with icon.
        
        Args:
            message: Status message
            status: Status type - "processing", "done", "error", "skip"
        """
        icons = {
            "processing": "→",
            "done": "✓",
            "error": "✗",
            "skip": "·"
        }
        colors = {
            "processing": self._theme.info,
            "done": self._theme.success,
            "error": self._theme.error,
            "skip": self._theme.muted
        }
        
        icon = icons.get(status, "·")
        color = colors.get(status, self._theme.info)
        
        self._console.print(f"  [{color}]{icon}[/{color}] {message}")
    
    def step_section(self, title: str) -> None:
        """
        Print a step section header (like ➤ in the example).
        
        Args:
            title: Section title
        """
        self._console.print(f"\n[bold {self._theme.highlight}]➤ {title}[/bold {self._theme.highlight}]")
    
    # === Data Display ===
    
    def table(
        self, 
        title: Optional[str], 
        columns: List[str], 
        rows: List[List[Any]],
        show_header: bool = True
    ) -> None:
        """
        Print formatted table.
        
        Args:
            title: Table title (optional)
            columns: Column headers
            rows: List of row data
            show_header: Whether to show column headers
        """
        table = Table(
            title=title,
            show_header=show_header,
            header_style=self._theme.highlight,
            border_style=self._theme.muted
        )
        
        for col in columns:
            table.add_column(col)
        
        for row in rows:
            table.add_row(*[str(cell) for cell in row])
        
        self._console.print(table)
    
    def list_items(self, items: List[str], title: Optional[str] = None) -> None:
        """
        Print bulleted list.
        
        Args:
            items: List of items to display
            title: Optional title above the list
        """
        if title:
            self._console.print(title, style=self._theme.highlight)
        
        for item in items:
            self._console.print(f"  - {item}")
    
    def key_value(self, data: Dict[str, Any], title: Optional[str] = None) -> None:
        """
        Print key-value pairs.
        
        Args:
            data: Dictionary of key-value pairs
            title: Optional title above the data
        """
        if title:
            self._console.print(title, style=self._theme.highlight)
        
        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0
        
        for key, value in data.items():
            key_str = str(key).ljust(max_key_len)
            self._console.print(f"  [{self._theme.muted}]{key_str}[/{self._theme.muted}]: {value}")
    
    def file_info(self, path: Path, size_mb: float, extra: Optional[str] = None) -> None:
        """
        Print file information.
        
        Args:
            path: File path
            size_mb: File size in MB
            extra: Optional extra information
        """
        size_str = f"{size_mb:.1f} MB"
        path_str = f"[{self._theme.path}]{path.name}[/{self._theme.path}]"
        
        if extra:
            self._console.print(f"  {path_str} ({size_str}) - {extra}")
        else:
            self._console.print(f"  {path_str} ({size_str})")
    
    # === Sections ===
    
    def section(self, title: str) -> None:
        """
        Print section header.
        
        Args:
            title: Section title
        """
        self._console.print()
        self._console.print(f"[bold {self._theme.highlight}]{title}[/bold {self._theme.highlight}]")
    
    def divider(self) -> None:
        """Print horizontal divider."""
        self._console.print("-" * 40, style=self._theme.muted)
    
    def newline(self) -> None:
        """Print empty line."""
        self._console.print()
    
    # === Summary Display ===
    
    def summary(
        self, 
        title: str,
        stats: Dict[str, Any],
        success: bool = True
    ) -> None:
        """
        Print operation summary.
        
        Args:
            title: Summary title
            stats: Statistics dictionary
            success: Whether operation was successful
        """
        style = self._theme.success if success else self._theme.error
        
        self._console.print()
        self._console.print(f"[{style}]{title}[/{style}]")
        
        for key, value in stats.items():
            self._console.print(f"  {key}: {value}")


class LiveStatus:
    """
    Helper class for live status updates with animated spinner.
    Uses rich.progress.Progress for reliable animated spinner.
    """
    
    def __init__(self, console: Console, theme: ThemeColors, message: str, total: Optional[int] = None):
        self._console = console
        self._theme = theme
        self._message = message
        self._total = total
        self._completed = 0
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[{task.description}]"),
            console=console,
            transient=True,  # Spinner line will be removed when done
            refresh_per_second=10
        )
        self._task_id = None
    
    def __enter__(self):
        self._progress.start()
        self._task_id = self._progress.add_task(
            f"[{self._theme.info}]{self._message}[/{self._theme.info}]",
            total=self._total
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._progress:
            self._progress.stop()
        return False
    
    def update(self, message: str) -> None:
        """Update the spinner message."""
        self._message = message
        if self._task_id is not None:
            self._progress.update(
                self._task_id,
                description=f"[{self._theme.info}]{message}[/{self._theme.info}]"
            )
    
    def log(self, message: str, status: str = "done") -> None:
        """
        Log a completed item (prints and spinner continues).
        
        Args:
            message: Message to log
            status: Status type - "done", "error", "skip"
        """
        icons = {"done": "✓", "error": "✗", "skip": "·"}
        colors = {
            "done": self._theme.success,
            "error": self._theme.error,
            "skip": self._theme.muted
        }
        
        icon = icons.get(status, "·")
        color = colors.get(status, self._theme.info)
        
        # Print log line - Progress handles this correctly
        self._progress.console.print(f"  [{color}]{icon}[/{color}] {message}")
        
        self._completed += 1
        
        # Update spinner message with remaining count
        if self._total:
            remaining = self._total - self._completed
            if remaining > 0:
                self.update(f"Processing... ({remaining} remaining)")
    
    def advance(self) -> None:
        """Advance the completed count."""
        self._completed += 1


# Global output instance
_output: Optional[Output] = None


def get_output() -> Output:
    """
    Get global output instance.
    
    Creates instance on first call, loading theme from config.
    
    Returns:
        Output instance
    """
    global _output
    if _output is None:
        # Try to load theme from config
        try:
            from .config import get_config
            config = get_config()
            theme_file = config.theme_file
            enable_colors = config.enable_colors
        except Exception:
            theme_file = "rose.theme.default.yaml"
            enable_colors = True
        
        _output = Output(theme_file=theme_file, enable_colors=enable_colors)
    
    return _output


def reset_output() -> None:
    """Reset global output instance (for testing)."""
    global _output
    _output = None
