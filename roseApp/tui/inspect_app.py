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

from textual.widgets import Header, Footer, Input, Label, Static, Button, ListView, ListItem, Tree
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
from typing import Optional, List, Tuple
from datetime import datetime

from ..core.model import ComprehensiveBagInfo, TopicInfo
from ..core.output import ThemeColors

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
        matches = []
        
        try:
            regex_pattern = ".*".join(map(re.escape, query_lower))
            regex = re.compile(regex_pattern)
            
            count = 0
            for display_name, topic, field_filter in self.search_index:
                score = 0
                name_lower = display_name.lower()
                
                if name_lower.startswith(query_lower):
                    score = 2 # Prefix match
                elif query_lower in name_lower:
                    score = 1 # Substring match
                elif regex.search(name_lower):
                    score = 0 # Fuzzy match
                else:
                    continue

                matches.append((score, display_name, topic, field_filter))
                
            matches.sort(key=lambda x: (-x[0], x[1]))
            
            for _, display_name, topic, field_filter in matches[:20]:
                item_value = f"{topic.name}|{field_filter}"
                label = f"{display_name} ({topic.message_type})"
                results_list.append(ListItem(Label(label), name=item_value))
                
        except Exception:
            pass

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
    #main-row {
        height: 1fr;
        layout: horizontal;
    }

    #data-pane {
        width: 30%;
        height: 100%;
        layout: vertical;
        padding: 0 1;
        border-right: solid $primary;
    }

    #plot-pane {
        width: 70%;
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
        Binding("q", "quit", "Quit"),
        Binding("/", "show_search", "Search"),
        Binding("g", "show_jump", "Jump to Frame"),
        Binding("left,h", "prev_msg", "Previous"),
        Binding("right,l", "next_msg", "Next"),
    ]

    current_msg_index = reactive(0)
    current_field_filter = reactive("")
    
    # Plotting Data
    plot_data_x: List[float] = []
    plot_data_y: List[float] = []
    current_plot_point: Optional[Tuple[float, float]] = None

    SearchItem = Tuple[str, TopicInfo, str]

    def __init__(self, bag_path: str, bag_info: ComprehensiveBagInfo, theme: ThemeColors, **kwargs):
        super().__init__(**kwargs)
        self.bag_path = bag_path
        self.bag_info = bag_info
        self.rose_theme = theme
        self.topics = sorted(bag_info.topics, key=lambda t: t.name)
        self.current_topic: Optional[TopicInfo] = None
        self.reader = AnyReader([Path(bag_path)])
        self.reader.open()
        
        # Build search index
        self.search_index: List[InspectApp.SearchItem] = []
        self._build_search_index()

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

        with Horizontal(id="main-row"):
            # Swapped: Data Left, Plot Right
            with Vertical(id="data-pane"):
                yield Static("No topic selected. Press '/' to search.", id="topic-bar")
                yield Tree("Root", id="data-tree")
                
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

    def on_key(self, event: events.Key) -> None:
        if isinstance(self.focused, Input):
            return
        if event.key == "left":
            self.action_prev_msg()
        elif event.key == "right":
            self.action_next_msg()

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
        
        if field_filter and PLOTEXT_AVAILABLE:
             self.load_full_plot_data()
        
        self.load_message()

    def load_full_plot_data(self) -> None:
        """Load all data points for the selected field for plotting."""
        if not self.current_topic or not self.current_field_filter:
            return
            
        plot_label = self.query_one("#plot-label", Label)
        plot_label.update("Loading plot data...")
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
             # But islice doesn't support 'step' for simple iterators well if we also need index, 
             # actually standard islice(gen, 0, None, step) works!
            for conn, ts, raw in islice(gen, 0, None, step):
                ts_sec = ts / 1_000_000_000
                rel_time = ts_sec - start_ts
                
                # We need to deserialize to get the value.
                # This is the heavy part.
                msg = self.reader.deserialize(raw, conn.msgtype)
                
                # Extract value
                val = msg
                valid = True
                
                parts = self.current_field_filter.replace('/', '.').split('.')
                for part in parts:
                    if hasattr(val, part):
                         val = getattr(val, part)
                    elif isinstance(val, dict) and part in val:
                         val = val[part]
                    else:
                         valid = False
                         break
                
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

    def _update_plot(self) -> None:
        if not PLOTEXT_AVAILABLE: return
        try:
            plot_widget = self.query_one(PlotextPlot)
            plot_label = self.query_one("#plot-label", Label)
            
            plot_widget.visible = True
            plt = plot_widget.plt
            plt.clear_data()
            plt.title(f"Field: {self.current_field_filter}")
            plt.xlabel("Time (s)")
            
            # 1. Main Series
            if self.plot_data_x:
                plt.plot(self.plot_data_x, self.plot_data_y)
            
            # 2. Highlight Current Point
            if self.current_plot_point:
                cx, cy = self.current_plot_point
                plt.scatter([cx], [cy], marker="x", color="red")
                # Add text annotation
                # Plotext text(s, x, y)
                plt.text(f" {cy:.4f} ", cx, cy, alignment="left", color="red")
            
            plot_widget.refresh()
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

    def load_message(self) -> None:
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
        tree.clear()
        
        root_label = f"{self.current_topic.name}"
        if self.current_field_filter:
            root_label += f".{self.current_field_filter}"
            
        tree.root.label = Text(root_label, style=f"bold {self.rose_theme.accent}")
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
                
                # Apply filter
                data_to_show = msg
                if self.current_field_filter:
                    parts = self.current_field_filter.replace('/', '.').split('.')
                    for part in parts:
                        if hasattr(data_to_show, part):
                             data_to_show = getattr(data_to_show, part)
                        elif isinstance(data_to_show, dict) and part in data_to_show:
                             data_to_show = data_to_show[part]
                        else:
                             data_to_show = f"<Field '{part}' not found>"
                             break
                
                # Calculate visualization data regardless of plot mode
                current_val = None
                current_time_rel = None
                
                if isinstance(data_to_show, (int, float)):
                    current_val = float(data_to_show)
                    # Calc relative time
                    start_ts = 0.0
                    if self.current_topic.first_message_time:
                         start_ts = self.current_topic.first_message_time[0]
                    current_time_rel = ts_sec - start_ts

                self.build_tree(tree.root, data_to_show)
                
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
                tree.root.add(Text("Message not found", style="bold red"))
                self.query_one("#current-time-display", Label).update("--:--:--")
                
        except Exception as e:
            tree.root.add(Text(f"Error: {e}", style="bold red"))

    def build_tree(self, node: Tree, data: any) -> None:
        """Recursively add nodes to the tree."""
        from rich.text import Text
        
        # 1. Handle ROS Message objects (slots or dicts)
        if hasattr(data, '__slots__'):
            for field in data.__slots__:
                val = getattr(data, field)
                self._add_child_node(node, field, val)
                
        elif hasattr(data, '__dict__'):
            for field, val in data.__dict__.items():
                if field.startswith('_'): continue
                self._add_child_node(node, field, val)
                
        # 2. Handle Dicts
        elif isinstance(data, dict):
            for key, val in data.items():
                self._add_child_node(node, str(key), val)
                
        # 3. Handle Lists/Arrays
        elif isinstance(data, (list, tuple)):
            # Optimization: Collapse large primitive arrays
            if len(data) > 0 and isinstance(data[0], (int, float, bool)) and len(data) > 20:
                 # Show summary
                 summary = f"<Array[{len(data)}] {data[:5]}...>"
                 node.add(Text(summary, style="dim italic"))
            else:
                for i, item in enumerate(data):
                    self._add_child_node(node, f"[{i}]", item)
                    
        # 4. Handle Primitives (Leaf nodes)
        else:
             node.add(Text(str(data), style=self.rose_theme.info))

    def _add_child_node(self, parent: Tree, label: str, value: any) -> None:
        """Helper to format and add a child node."""
        from rich.text import Text
        
        is_container = False
        if hasattr(value, '__slots__') or hasattr(value, '__dict__') or isinstance(value, (dict, list, tuple)):
             is_container = True
             
        if is_container:
            # Container: label is the key, expand to show children
            # Styling: Key in default/blue
            subtree = parent.add(Text(label, style="bold " + self.rose_theme.info))
            self.build_tree(subtree, value)
            subtree.expand() 
        else:
            # Leaf: "label: value"
            # Value styling: Green for numbers, etc
            style_val = "green" if isinstance(value, (int, float)) else "white"
            text = Text.assemble(
                (f"{label}: ", "bold " + self.rose_theme.info),
                (str(value), style_val)
            )
            parent.add(text)
