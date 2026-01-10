from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
try:
    from textual_plotext import PlotextPlot
    PLOTEXT_AVAILABLE = True
except ImportError:
    PLOTEXT_AVAILABLE = False
    from textual.widgets import Static
    class PlotextPlot(Static):
        def __init__(self, *args, **kwargs):
            super().__init__("Plotting requires 'textual-plotext'.\nInstall with: pip install textual-plotext", *args, **kwargs)
            self.plt = None

from textual.widgets import Header, Footer, Input, Label, Static, Button, ListView, ListItem, Tree, TabbedContent, TabPane
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from textual.screen import ModalScreen
from textual import events, on
from rich.progress_bar import ProgressBar
from rich.text import Text
from rosbags.highlevel import AnyReader
from pathlib import Path
from itertools import islice
import re
from typing import Optional, List, Tuple, Any
from datetime import datetime

from ..core.model import BagInfo, TopicInfo
from ..core.output import ThemeColors
from ..core.config import get_config
from .theme import ALL_THEMES

class Timeline(Static):
    """Interactive timeline widget."""
    
    total = reactive(0)
    current = reactive(0)

    class Seek(Message):
        """Message sent when timeline is clicked."""
        def __init__(self, index: int):
            self.index = index
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.total = 100
        self.current = 0

    def render(self):
        return ProgressBar(total=self.total, completed=self.current, width=None)

    def on_click(self, event: events.Click) -> None:
        if self.total > 0:
            width = self.content_size.width
            if width == 0: return
            
            percent = max(0, min(1, event.x / width))
            target = int(percent * self.total)
            
            self.post_message(self.Seek(target))

class SearchModal(ModalScreen[Tuple[Optional[str], str]]):
    """Modal screen for searching topics and fields."""

    CSS = """
    SearchModal {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }

    #search_container {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: solid $accent;
        padding: 1;
        layout: vertical;
    }

    #modal_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    #search_input {
        margin-bottom: 1;
        border: solid $primary;
    }

    #results_list {
        height: 1fr;
        border: solid $surface-lighten-1;
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "focus_list", "Results", show=False),
    ]

    def __init__(self, search_index: List[Tuple[str, TopicInfo, str]], initial_query: str = "", **kwargs):
        super().__init__(**kwargs)
        self.search_index = search_index
        self.initial_query = initial_query

    def compose(self) -> ComposeResult:
        with Container(id="search_container"):
            yield Label("Search Topics & Fields", id="modal_title")
            inp = Input(placeholder="Type to search... (e.g. 'gps' or '/topic.field')", id="search_input")
            inp.value = self.initial_query
            yield inp
            yield ListView(id="results_list")

    def on_mount(self) -> None:
        self.query_one("#search_input").focus()
        self.update_results(self.initial_query)

    def action_cancel(self) -> None:
        self.dismiss((None, ""))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_results(event.value)

    def action_focus_list(self) -> None:
        results = self.query_one("#results_list")
        if len(results.children) > 0:
            results.focus()
            results.index = 0

    def update_results(self, query: str) -> None:
        results_list = self.query_one("#results_list", ListView)
        results_list.clear()
        
        if not query:
            return

        query_lower = query.lower()
        # Remove array indices for matching against index
        # e.g. "foo[1]" -> "foo"
        query_base = re.sub(r'\[\d+\]', '', query_lower)
        
        matches = []
        
        try:
            regex_pattern = ".*".join(map(re.escape, query_base))
            regex = re.compile(regex_pattern)
            
            count = 0
            for display_name, topic, field_filter in self.search_index:
                score = 0
                name_lower = display_name.lower()
                
                if name_lower.startswith(query_base):
                    score = 2 # Prefix match
                elif query_base in name_lower:
                    score = 1 # Substring match
                elif regex.search(name_lower):
                    score = 0 # Fuzzy match
                else:
                    continue

                matches.append((score, display_name, topic, field_filter))
                
            matches.sort(key=lambda x: (-x[0], x[1]))
            
            # Increased limit to 100
            for _, display_name, topic, field_filter in matches[:100]:
                item_value = f"{topic.name}|{field_filter}"
                # If user typed an index, append it to the filter for the result
                # This is tricky: we matched "foo" against "foo", but user wanted "foo[1]".
                # We should probably just return the raw field_filter from index, 
                # and let the user's manual input (not list selection) handle specific indices?
                # OR, if the user picks from list, we just give them the array root.
                # BUT, if they typed "points[0]", and we matched "points", we should probably 
                # try to pass "points[0]" if they hit enter on that specific filter.
                # However, the list item name is used for selection.
                
                # If we want to support selecting specific index via search, we'd need to dynamically generate list items.
                # For now, let's just make sure "points[0]" finds "points".
                # If they select "points", they get the array.
                # If they want "points[0]", they might need to use the Input field directly...
                # Wait, on_list_view_selected uses event.item.name.
                
                label = f"{display_name} ({topic.message_type})"
                results_list.append(ListItem(Label(label), name=item_value))
                
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow manual submission for deep paths or array indices not in index."""
        val = event.value.strip()
        if not val:
            self.dismiss((None, ""))
            return
            
        # Try to find a matching topic prefix
        # We need access to topics. We passed search_index, which has topic objects.
        # Let's collect unique topics from search_index (inefficient but safe)
        # Or better, just iterate search_index to find best match?
        # Actually, InspectApp passes 'search_index' which is List[(display, topic, filter)].
        
        # Simple heuristic: Exact match in results list?
        # If the input matches a result item name exactly, select it.
        results_list = self.query_one("#results_list", ListView)
        if len(results_list.children) > 0 and results_list.highlighted_child:
             # If user is highlighting something, select that (default behavior of list view on enter? No, list view needs separate enter handling usually, but Input enter falls through?)
             # Textual: Input.Submitted is separate.
             # If we want "Enter" to pick selected item if list has focus? No, Input has focus.
             # If Input has focus, and user hits Enter:
             # 1. If exact match in index, use it.
             # 2. If valid "Topic.Field" structure manually typed, use it.
             pass
        
        # Helper to extract topic
        # val might be "/gps/fix.header.stamp" or "header.stamp" (if context?)
        # Search is usually global "Topic.Field" or just "Topic".
        
        best_topic = None
        best_filter = ""
        
        # We search for the longest topic name that matches the start of val
        unique_topics = {t for _, t, _ in self.search_index}
        
        for topic in unique_topics:
            t_name = topic.name
            # Check if val starts with topic name
            # Handle potential leading slash consistency
            if val.startswith(t_name):
                # Candidate.
                # Check if what follows is empty or a separator (dot or slash converted to dot)
                remainder = val[len(t_name):]
                if not remainder:
                    best_topic = topic
                    best_filter = ""
                    break # Exact match
                elif remainder.startswith('.') or remainder.startswith('/'):
                    # Match!
                    # If existing best match is shorter, replace?
                    # Since we allow arbitrary topics, logic is tricky if topics overlap (e.g. /foo and /foo/bar).
                    # We should match longest topic.
                    if best_topic is None or len(t_name) > len(best_topic.name):
                        best_topic = topic
                        # strip separator
                        best_filter = remainder[1:]
        
        if best_topic:
            self.dismiss((best_topic.name, best_filter))
        else:
            # If no topic found, maybe it's a field filter on CURRENT topic?
            # But SearchModal doesn't know current topic context easily unless passed.
            # We only passed initial_query.
            # Let's assume if it fails to match a topic, we return None (cancellation) or try logic?
            # User expectation: If I type "gps", I want to filter. 
            # If I type "/diagnostics.status[0]", I expect it to work.
            
            # Fallback: Check if the input value directly matches a "Name" in the list val
            # (already covered by list selection if they cursored down).
            
            # If they just typed something and hit enter, assume they might mean a topic if it matches logic, 
            # otherwise maybe they just typed "status[0]" expecting context?
            # Since this is a global search (modally), forcing Topic prefix is safer.
            pass
            
        # If we couldn't resolve a topic, just try to return what we have if it looks like a topic name?
        # Or Just dismiss with nothing to avoid bad state.
        if best_topic:
             pass 
        else:
             # Try one last check: exact match of any display string in index?
             for disp, topic, filt in self.search_index:
                 if disp == val:
                     self.dismiss((topic.name, filt))
                     return
             
             # If absolute failure
             self.app.notify("Could not resolve topic from input. Format: /topic.field", severity="error")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        val = event.item.name
        if "|" in val:
            t_name, f_filter = val.split("|", 1)
        else:
            t_name, f_filter = val, ""
        self.dismiss((t_name, f_filter))

class JumpModal(ModalScreen[int]):
    """Modal to jump to a specific frame index."""
    
    CSS = """
    JumpModal {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }
    #jump_container {
        width: 40;
        height: auto;
        background: $surface;
        border: solid $accent;
        padding: 1;
    }
    #jump_label {
        margin-bottom: 1;
        text-align: center;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(id="jump_container"):
            yield Label("Jump to Frame Index:", id="jump_label")
            yield Input(placeholder="Enter frame number...", type="integer", id="jump_input")
            
    def on_mount(self) -> None:
        self.query_one("#jump_input").focus()
        
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.isdigit():
            self.dismiss(int(event.value))
        else:
            self.dismiss(None)

class InspectApp(App):
    """Interactive TUI for inspecting ROS bags."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        dock: top;
    }

    /* Main Area */
    /* Main Area - Now using Tabs */
    TabbedContent {
        height: 1fr;
    }
    
    ContentSwitcher {
        height: 1fr;
    }

    TabPane {
        height: 100%;
        padding: 0;
    }

    #data-pane {
        width: 100%;
        height: 100%;
        layout: vertical;
        padding: 0 1;
        /* Border moved to Tabs or just remove visual separation since tabs separate them */
        /* border-right: solid $primary; */ 
    }

    #plot-pane {
        width: 100%;
        height: 100%;
        background: $surface-lighten-1;
        content-align: center middle;
        layout: vertical;
    }
    
    PlotextPlot {
        width: 100%;
        height: 1fr;
        margin: 1;
    }
    
    #plot-label {
        width: 100%;
        text-align: center;
        color: $text-muted;
        height: 1;
    }
    
    #topic-bar {
        height: 1;
        background: $surface;
        border-bottom: solid $primary;
        color: $text;
        padding: 0 1;
    }

    /* Bottom: Timeline/Navigator */
    #bottom-bar {
        height: 4; /* Increased height for time info */
        dock: bottom;
        layout: vertical;
        border-top: solid $secondary;
        padding: 0 1;
        background: $surface;
    }
    
    #time-info-row {
        height: 1;
        layout: horizontal;
        color: $text-muted;
        margin-top: 0;
    }
    
    #current-time-display {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }
    
    #timeline-row {
        height: 1;
        layout: horizontal;
        align: center middle;
    }
    
    Timeline {
        width: 1fr;
        height: 1;
        margin: 0 1;
    }
    
    .time-label {
        width: auto;
        min-width: 20;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("/", "show_search", "Search"),
        Binding("g", "show_jump", "Jump to Frame"),
        Binding("left,h", "prev_msg", "Previous"),
        Binding("right,l", "next_msg", "Next"),
        Binding("down", "focus_tree", "Focus Tree", show=False),
    ]

    current_msg_index = reactive(0)
    current_field_filter = reactive("")
    current_plot_field: str = ""
    
    # Plotting Data
    plot_data_x: List[float] = []
    plot_data_y: List[float] = []
    current_plot_point: Optional[Tuple[float, float]] = None

    def _get_field_value(self, msg: Any, path: str) -> Tuple[Any, bool]:
        """
        Navigate message using path with support for array indexing.
        Returns (value, success).
        """
        if not path:
             return msg, True
        current = msg
        try:
            parts = path.split('.')
            for part in parts:
                match = re.match(r"(\w+)\[(\d+)\]", part)
                if match:
                    field_name = match.group(1)
                    index = int(match.group(2))
                    
                    if hasattr(current, field_name):
                        current = getattr(current, field_name)
                    elif isinstance(current, dict) and field_name in current:
                        current = current[field_name]
                    else:
                        return None, False
                        
                    if isinstance(current, (list, tuple)) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None, False
                else:
                    if hasattr(current, part):
                        current = getattr(current, part)
                    elif isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return None, False
            return current, True
        except Exception:
            return None, False

    SearchItem = Tuple[str, TopicInfo, str]

    def __init__(self, bag_path: str, bag_info: BagInfo, theme: ThemeColors, initial_topic: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        for t in ALL_THEMES.values():
            self.register_theme(t)
            
        # Determine theme name from config
        config = get_config()
        theme_file = config.theme_file
        # theme_file is like "rose.theme.nord.yaml" -> extract "nord"
        # Or just match logic in theme.py
        theme_name = "claude" # fallback
        
        # Try to parse name from filename
        parts = theme_file.split('.')
        if len(parts) >= 3 and parts[0] == "rose" and parts[1] == "theme":
            theme_name = parts[2]
            
        if theme_name in ALL_THEMES:
            self.theme = theme_name
        elif "claude" in ALL_THEMES:
            self.theme = "claude"
        elif "default" in ALL_THEMES:
            self.theme = "default"
            
        self.bag_path = bag_path
        self.bag_info = bag_info
        self.rose_theme = theme
        self.initial_topic = initial_topic
        self.topics = sorted(bag_info.topics, key=lambda t: t.name)
        self.current_topic: Optional[TopicInfo] = None
        self.reader = AnyReader([Path(bag_path)])
        self.reader.open()
        
        self.search_index: List[InspectApp.SearchItem] = []
        self._build_search_index()

    def action_focus_tree(self) -> None:
        """Focus the data tree to allow navigation."""
        if not self.current_topic:
             # Enhance UX: If no topic, Down key opens search
             self.action_show_search()
             return

        tree = self.query_one("#data-tree")
        if self.focused != tree:
            tree.focus()

    def _build_search_index(self) -> None:
        """Flatten topics and fields into a searchable list."""
        self.search_index = []
        for topic in self.topics:
            self.search_index.append((topic.name, topic, ""))
            msg_type_info = next((mt for mt in self.bag_info.message_types if mt.message_type == topic.message_type), None)
            if msg_type_info:
                def get_paths(fields, prefix=""):
                    paths = []
                    if not fields: return []
                    for f in fields:
                        curr = f"{prefix}.{f.field_name}" if prefix else f.field_name
                        paths.append(curr)
                        if f.nested_fields:
                            paths.extend(get_paths(f.nested_fields, curr))
                    return paths
                if msg_type_info.fields:
                    all_paths = get_paths(msg_type_info.fields)
                    for p in all_paths:
                        full = f"{topic.name}.{p}"
                        self.search_index.append((full, topic, p))

    def on_unmount(self) -> None:
        if self.reader:
            self.reader.close()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")

        with TabbedContent(initial="raw-tab"):
            with TabPane("Raw Data", id="raw-tab"):
                with Vertical(id="data-pane"):
                    yield Static("No topic selected. Press '/' to search.", id="topic-bar")
                    yield Tree("Root", id="data-tree")
                    
            with TabPane("Plot", id="plot-tab"):
                with Vertical(id="plot-pane"):
                    yield Label("Plot Area (Numeric Data Only)", id="plot-label")
                    if PLOTEXT_AVAILABLE:
                        yield PlotextPlot(id="plot-graph")
                    else:
                        yield Static("\n[bold red]Dependency Missing[/]\n\nPlease install 'textual-plotext' to view plots.\n\nRun:\npip install textual-plotext", id="plot-graph", classes="error-msg")

        with Vertical(id="bottom-bar"):
            # Row 1: Current Time/Frame Info
            with Horizontal(id="time-info-row"):
                yield Label("Frame: 0/0", id="frame-counter", classes="time-label")
                yield Label("--:--:--", id="current-time-display")
                yield Label("0%", id="percent-display", classes="time-label")
            
            # Row 2: Timeline with absolute start/end
            with Horizontal(id="timeline-row"):
                yield Label("Start: --:--", id="start-time-label", classes="time-label")
                yield Timeline(id="timeline")
                yield Label("End: --:--", id="end-time-label", classes="time-label")
            
        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection to update plot."""
        if not event.node.data:
            return
            
        # If node has valid path data, update plot field
        path = str(event.node.data)
        
        # Only update if different
        if path != self.current_plot_field:
            self.current_plot_field = path
             
            # Trigger load plot data
            if PLOTEXT_AVAILABLE:
                self.load_full_plot_data()
                
            # Trigger load message to update highlight
            self.load_message()

    def action_show_search(self) -> None:
        query = ""
        if self.current_topic:
            query = self.current_topic.name
            if self.current_field_filter:
                query += "." + self.current_field_filter
        
        self.push_screen(SearchModal(self.search_index, initial_query=query), self.on_search_result)
        
    def action_show_jump(self) -> None:
        self.push_screen(JumpModal(), self.on_jump_result)
        
    def on_jump_result(self, index: Optional[int]) -> None:
        if index is not None and self.current_topic:
            target = max(0, min(index, self.current_topic.message_count - 1))
            self.current_msg_index = target

    def on_search_result(self, result: Tuple[Optional[str], str]) -> None:
        topic_name, field_filter = result
        if topic_name:
            topic = next((t for t in self.topics if t.name == topic_name), None)
            if topic:
                self.select_topic(topic, field_filter)

    def select_topic(self, topic: TopicInfo, field_filter: str = "") -> None:
        # Check if topic changed or filter changed significantly
        if topic != self.current_topic or field_filter != self.current_field_filter:
            self.plot_data_x.clear()
            self.plot_data_y.clear()
            self.current_plot_point = None
            try:
                plot = self.query_one(PlotextPlot)
                plot.plt.clear_data()
                plot.refresh()
            except: pass
            
        self.current_topic = topic
        self.current_msg_index = 0
        self.current_field_filter = field_filter
        # Sync plot field with filter initially
        self.current_plot_field = field_filter
        
        info_str = f"{topic.name} ({topic.message_type})"
        if field_filter:
            info_str += f" | Filter: .{field_filter}"
            
        self.query_one("#topic-bar", Static).update(info_str)
        
        # Setup Timeline Bounds
        timeline = self.query_one("#timeline", Timeline)
        timeline.total = topic.message_count - 1
        timeline.current = 0
        
        # Format Start/End times
        start_str = "N/A"
        end_str = "N/A"
        
        if topic.first_message_time:
            s_dt = datetime.fromtimestamp(topic.first_message_time[0])
            start_str = s_dt.strftime("%H:%M:%S")
        if topic.last_message_time:
            e_dt = datetime.fromtimestamp(topic.last_message_time[0])
            end_str = e_dt.strftime("%H:%M:%S")
            
        self.query_one("#start-time-label", Label).update(start_str)
        self.query_one("#end-time-label", Label).update(end_str)
        
        if self.current_plot_field and PLOTEXT_AVAILABLE:
             self.load_full_plot_data()
        
        self.load_message()

    def load_full_plot_data(self) -> None:
        """Load all data points for the selected plot field."""
        if not self.current_topic or not self.current_plot_field:
            return
            
        plot_label = self.query_one("#plot-label", Label)
        plot_label.update(f"Loading data for {self.current_plot_field}...")
        self.refresh() # Force UI update if possible
        
        self.plot_data_x = []
        self.plot_data_y = []
        
        # Performance: Limit number of points to prevent TUI freeze
        MAX_POINTS = 500
        step = max(1, self.current_topic.message_count // MAX_POINTS)
        
        start_ts = 0.0
        if self.current_topic.first_message_time:
             start_ts = self.current_topic.first_message_time[0]
             
        # Create iterator
        gen = self.reader.messages(connections=[x for x in self.reader.connections if x.topic == self.current_topic.name])
        
        # Iterate with step
        try:
             # We use islice to step through the generator efficiently
            for conn, ts, raw in islice(gen, 0, None, step):
                ts_sec = ts / 1_000_000_000
                rel_time = ts_sec - start_ts
                
                # We need to deserialize to get the value.
                # This is the heavy part.
                msg = self.reader.deserialize(raw, conn.msgtype)
                
                # Use robust getter
                val, valid = self._get_field_value(msg, self.current_plot_field)
                
                if valid and isinstance(val, (int, float)):
                    self.plot_data_x.append(rel_time)
                    self.plot_data_y.append(float(val))
                    
        except Exception as e:
            plot_label.update(f"Error loading plot: {e}")
            return
            
        if self.plot_data_x:
            self._update_plot()
        else:
            plot_label.update("No numeric data found for field.")

    def on_mount(self) -> None:
        """Apply theme colors to UI elements dynamically."""
        try:
            # Map rose_theme colors to UI
            primary = self.rose_theme.primary
            accent = self.rose_theme.accent
            
            # Update borders
            # self.query_one("#data-pane").styles.border_right = ("solid", primary) # Removed for tabs
            self.query_one("#topic-bar").styles.border_bottom = ("solid", primary)
            self.query_one("#bottom-bar").styles.border_top = ("solid", accent)
            
            # Style Tabs?
            # from textual.widgets import Tabs
            # self.query_one(Tabs).styles.color = primary 
            # self.query_one(Tabs).styles.background = ... # Textual defaults are okay usually

            self.query_one("#topic-bar").styles.border_bottom = ("solid", primary)
            self.query_one("#bottom-bar").styles.border_top = ("solid", accent)
            
            # Update labels
            self.query_one("#frame-counter").styles.color = primary
            self.query_one("#percent-display").styles.color = primary
            
        except Exception:
            pass

        # Handle Initial Topic Selection
        if self.initial_topic:
            # Find exact match
            match = next((t for t in self.topics if t.name == self.initial_topic), None)
            if match:
                self.select_topic(match)
                # Auto focus tree for immediate traversal
                self.query_one("#data-tree").focus()
            else:
                self.notify(f"Topic '{self.initial_topic}' not found.", severity="error")

    def _update_plot(self) -> None:
        if not PLOTEXT_AVAILABLE: return
        try:
            plot_widget = self.query_one(PlotextPlot)
            plot_label = self.query_one("#plot-label", Label)
            
            plot_widget.visible = True
            plt = plot_widget.plt
            plt.clear_data()
            
            # 1. Full Path Title
            full_path = f"{self.current_topic.name}.{self.current_plot_field}" if self.current_topic else self.current_plot_field
            plt.title(f"{full_path}")
            
            plt.xlabel("Time (s)")
            
            # 2. Main Series with Legend
            color = self.rose_theme.primary
            
            # Determine legend label
            legend_label = "History"
            if self.current_plot_point:
                legend_label = f"Val: {self.current_plot_point[1]:.4f}" # Current value in legend
            
            if self.plot_data_x:
                plt.plot(self.plot_data_x, self.plot_data_y, color=color, label=legend_label, marker="braille")
            
            # 3. Highlight Current Point
            if self.current_plot_point:
                cx, cy = self.current_plot_point
                # Use accent/error for highlight
                h_color = self.rose_theme.accent
                
                # Marker: "inverse color pixel" -> Use a solid block char or circle
                # plotext 'marker' can be a single char.
                # "inverse" effect is hard without bg color control per pixel, but high contrast helps.
                # To make it larger but aligned: Plot a cluster of braille dots around center.
                
                # Estimate canvas resolution if possible, or use heuristic
                # We need dx, dy corresponding to sub-pixel size
                
                # Get data range
                y_min = min(self.plot_data_y) if self.plot_data_y else cy
                y_max = max(self.plot_data_y) if self.plot_data_y else cy
                y_range = max(1e-6, y_max - y_min)
                
                x_min = min(self.plot_data_x) if self.plot_data_x else cx
                x_max = max(self.plot_data_x) if self.plot_data_x else cx
                x_range = max(1e-6, x_max - x_min)

                # Get widget size (chars)
                w, h = plot_widget.content_size # (width, height)
                if w == 0: w = 80
                if h == 0: h = 20
                
                # Plotext resolution: 2 horizontal dots per char, 4 vertical dots per char
                dots_w = w * 2
                dots_h = h * 4
                
                # Size of one dot in data units
                dx = x_range / dots_w
                dy = y_range / dots_h
                
                # Generate 2x2 cluster (offsets in dot units)
                # 2x2 grid centered: -0.5, 0.5
                cluster_x = []
                cluster_y = []
                
                # Use theme error color for high visibility
                h_color = self.rose_theme.error
                
                for off_x in [-0.5, 0.5]:
                    for off_y in [-0.5, 0.5]:
                        cluster_x.append(cx + (off_x * dx))
                        cluster_y.append(cy + (off_y * dy))
                
                plt.scatter(cluster_x, cluster_y, marker="braille", color=h_color)
                
                # Calculate alignment and offset based on position
                # Logic:
                # 1. Y-Axis: If near bottom, place text ABOVE. Else BELOW.
                # Threshold: Bottom 10% of range
                is_near_bottom = (cy - y_min) < (0.1 * y_range)
                text_y = cy + (y_range * 0.08) if is_near_bottom else cy - (y_range * 0.08) # Increased offset for larger cursor
                
                # 2. X-Axis: If near left, align LEFT. Else align RIGHT.
                is_near_left = (cx - x_min) < (0.1 * x_range)
                text_align = "left" if is_near_left else "right"

                # Plotext text(s, x, y)
                plt.text(f" {cy:.4f} ", cx, text_y, alignment=text_align, color=h_color)
            
            # Force deep refresh of the widget chain
            plot_widget.refresh(layout=True)
            self.query_one("#plot-pane").refresh()
            self.query_one(TabbedContent).refresh()
            # self.refresh() # App refresh might be too broad/slow, try targeted first
            
            # Update label to just show count, not value (since value is in legend)
            if self.plot_data_x:
                plot_label.update(f"Loaded {len(self.plot_data_x)} points")
                
        except: pass

    def watch_current_msg_index(self, new_val: int) -> None:
        self.load_message()

    def on_timeline_seek(self, message: Timeline.Seek) -> None:
        if self.current_topic:
            idx = max(0, min(message.index, self.current_topic.message_count - 1))
            self.current_msg_index = idx

    def action_prev_msg(self) -> None:
        if self.current_topic and self.current_msg_index > 0:
             self.current_msg_index -= 1
             
    def action_next_msg(self) -> None:
        if self.current_topic and self.current_msg_index < self.current_topic.message_count - 1:
             self.current_msg_index += 1

    def load_message(self, skip_tree: bool = False) -> None:
        if not self.current_topic:
            return
            
        # Update Timeline Progress
        timeline = self.query_one("#timeline", Timeline)
        timeline.current = self.current_msg_index
        
        total_msgs = max(1, self.current_topic.message_count)
        percent = int((self.current_msg_index / (total_msgs - 1)) * 100) if total_msgs > 1 else 100
        
        self.query_one("#frame-counter", Label).update(f"Frame: {self.current_msg_index} / {total_msgs - 1}")
        self.query_one("#percent-display", Label).update(f"{percent}%")

        tree = self.query_one("#data-tree", Tree)
        
        if not skip_tree:
            tree.clear()
            
            root_label = f"{self.current_topic.name}"
            if self.current_field_filter:
                root_label += f".{self.current_field_filter}"
                
            tree.root.label = Text(root_label, style=f"bold {self.rose_theme.accent}")
            # Ensure root has the base path data
            tree.root.data = self.current_field_filter
            tree.root.expand()
        
        try:
            # Efficiently seek to current message
            gen = self.reader.messages(connections=[x for x in self.reader.connections if x.topic == self.current_topic.name])
            target_msg = next(islice(gen, self.current_msg_index, None), None)
            
            if target_msg:
                conn, ts, raw = target_msg
                
                # Update Current Time Display
                ts_sec = ts / 1_000_000_000
                dt = datetime.fromtimestamp(ts_sec)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # ms precision
                self.query_one("#current-time-display", Label).update(time_str)
                
                msg = self.reader.deserialize(raw, conn.msgtype)
                
                # Apply filter to get DATA TO SHOW IN TREE
                data_to_show = msg
                if self.current_field_filter:
                    val, valid = self._get_field_value(msg, self.current_field_filter)
                    if valid:
                        data_to_show = val
                    else:
                        data_to_show = f"<Field '{self.current_field_filter}' not found/valid>"

                if not skip_tree:
                    self.build_tree(tree.root, data_to_show, self.current_field_filter)

                # CALCULATE PLOT HIGHLIGHT based on current_plot_field
                current_val = None
                current_time_rel = None
                
                # We need the value for current_plot_field
                pval, pvalid = self._get_field_value(msg, self.current_plot_field)
                
                if pvalid and isinstance(pval, (int, float)):
                    current_val = float(pval)
                    # Calc relative time
                    start_ts = 0.0
                    if self.current_topic.first_message_time:
                         start_ts = self.current_topic.first_message_time[0]
                    current_time_rel = ts_sec - start_ts
                
                # Update plot highlight
                plot_label = self.query_one("#plot-label", Label)
                if current_val is not None and PLOTEXT_AVAILABLE:
                     self.current_plot_point = (current_time_rel, current_val)
                     self._update_plot()
                     plot_label.update(f"Val: {current_val:.4f}")
                else:
                     self.current_plot_point = None
                     # If we have background plot data, keep it visible, just clear highlight
                     if self.plot_data_x:
                         self._update_plot()
                     else:
                         plot_label.update("Selected data is not numeric.")
            else:
                 if not skip_tree:
                    tree.root.add(Text("Message not found", style=f"bold {self.rose_theme.error}"))
                 self.query_one("#current-time-display", Label).update("--:--:--")
                
        except Exception as e:
            if not skip_tree:
                tree.root.add(Text(f"Error: {e}", style=f"bold {self.rose_theme.error}"))

    def build_tree(self, node: Tree, data: any, path_prefix: str = "") -> None:
        """Recursively add nodes to the tree."""
        from rich.text import Text
        
        # 1. Handle ROS Message objects (slots or dicts)
        if hasattr(data, '__slots__'):
            for field in data.__slots__:
                val = getattr(data, field)
                self._add_child_node(node, field, val, path_prefix)
                
        elif hasattr(data, '__dict__'):
            for field, val in data.__dict__.items():
                if field.startswith('_'): continue
                self._add_child_node(node, field, val, path_prefix)
                
        # 2. Handle Dicts
        elif isinstance(data, dict):
            for key, val in data.items():
                self._add_child_node(node, str(key), val, path_prefix)
                
        # 3. Handle Lists/Arrays
        elif isinstance(data, (list, tuple)):
            # Optimization: Collapse large primitive arrays
            if len(data) > 0 and isinstance(data[0], (int, float, bool)) and len(data) > 20:
                 # Show summary
                 summary = f"<Array[{len(data)}] {data[:5]}...>"
                 # Arrays themselves can be plotted if index is selected
                 node.add(Text(summary, style="dim italic"), data=path_prefix)
            else:
                for i, item in enumerate(data):
                    self._add_child_node(node, f"[{i}]", item, path_prefix)
                    
        # 4. Handle Primitives (Leaf nodes)
        else:
             # Leaf node data is already set by parent via _add_child_node
             node.add(Text(str(data), style=self.rose_theme.info), data=path_prefix)

    def _add_child_node(self, parent: Tree, label: str, value: any, path_prefix: str) -> None:
        """Helper to format and add a child node."""
        from rich.text import Text
        
        # Construct full path for this node
        new_path = ""
        if not path_prefix:
            new_path = label
        elif label.startswith('['):
            new_path = f"{path_prefix}{label}"
        else:
            new_path = f"{path_prefix}.{label}"

        is_container = False
        if hasattr(value, '__slots__') or hasattr(value, '__dict__') or isinstance(value, (dict, list, tuple)):
             is_container = True
             
        if is_container:
            # Container: label is the key, expand to show children
            # Styling: Key in default/blue
            subtree = parent.add(Text(label, style="bold " + self.rose_theme.info), data=new_path)
            self.build_tree(subtree, value, new_path)
            # subtree.expand() # Don't auto-expand everything, too noisy? User can expand.
            # Only expand primitive containers or small ones
            if isinstance(value, (list, tuple)) and len(value) < 10:
                subtree.expand()
            elif not isinstance(value, (list, tuple)):
                subtree.expand()
        else:
            # Leaf: "label: value"
            # Value styling: Success color for numbers, highlight for others
            style_val = self.rose_theme.success if isinstance(value, (int, float)) else self.rose_theme.highlight
            text = Text.assemble(
                (f"{label}: ", "bold " + self.rose_theme.info),
                (str(value), style_val)
            )
            # Add node with path data
            parent.add(text, data=new_path)
