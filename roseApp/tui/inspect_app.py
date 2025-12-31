from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
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

class SearchModal(ModalScreen[Tuple[Optional[TopicInfo], str]]):
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

    def __init__(self, search_index: List[Tuple[str, TopicInfo, str]], **kwargs):
        super().__init__(**kwargs)
        self.search_index = search_index

    def compose(self) -> ComposeResult:
        with Container(id="search_container"):
            yield Label("Search Topics & Fields", id="modal_title")
            yield Input(placeholder="Type to search... (e.g. 'gps' or '/topic.field')", id="search_input")
            yield ListView(id="results_list")

    def on_mount(self) -> None:
        self.query_one("#search_input").focus()

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
        
        # 1. Exact/Prefix match on Topic Name (Boosted)
        # 2. Fuzzy regex match
        
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
                
            # Sort by score desc, then name
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

        # Find topic object from original index to be safe, or just pass back name?
        # We need the TopicInfo object. 
        # Since we can't easily pass object through ListItem name (string only), 
        # we'll look it up in parent or pass it via message. 
        # But wait, self.search_index has the objects.
        
        # Optimization: Just return the topic associated with the selected item.
        # But we need to look it up again or store it closer.
        # Let's simple lookup from our index based on name match? 
        # No, multiple topics could have same name? No, topic names are unique.
        
        # Let's return the names and let main app resolve.
        self.dismiss((t_name, f_filter))


class InspectApp(App):
    """Interactive TUI for inspecting ROS bags."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        dock: top;
    }

    /* Main Area: Plot + Data */
    #main-row {
        height: 1fr;
        layout: horizontal;
    }

    #plot-pane {
        width: 70%;
        height: 100%;
        border-right: solid $primary;
        background: $surface-lighten-1;
        content-align: center middle;
    }

    #data-pane {
        width: 30%;
        height: 100%;
        layout: vertical;
        padding: 0 1;
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
        height: 3;
        dock: bottom;
        layout: horizontal;
        border-top: solid $secondary;
        padding: 0 1;
        align: center middle;
    }
    
    #play-controls {
        width: auto;
        min-width: 20;
        align: center middle;
    }
    
    Timeline {
        width: 1fr;
        height: 1;
        margin: 1 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "show_search", "Search"),
        Binding("command+p", "show_search", "Search"),
        Binding("left,h", "prev_msg", "Previous Message"),
        Binding("right,l", "next_msg", "Next Message"),
    ]

    current_msg_index = reactive(0)
    current_field_filter = reactive("")

    # Search Index Item: (Display Name, TopicInfo, Field Path/Filter)
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
        
        # 1. Add Topics
        for topic in self.topics:
            self.search_index.append((topic.name, topic, ""))
            
            # 2. Add Fields
            msg_type_info = next((mt for mt in self.bag_info.message_types if mt.message_type == topic.message_type), None)
            
            if msg_type_info:
                # Recursive generator for field paths
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
            yield Static("[bold]Plot Area[/]\n\n(Visualization coming soon)", id="plot-pane")
            with Vertical(id="data-pane"):
                yield Static("No topic selected. Press '/' to search.", id="topic-bar")
                yield Tree("Root", id="data-tree")

        with Horizontal(id="bottom-bar"):
            with Horizontal(id="play-controls"):
                yield Button("<<", id="btn_prev", variant="primary")
                yield Label("0 / 0", id="frame_label")
                yield Button(">>", id="btn_next", variant="primary")
            
            yield Timeline(id="timeline")
            
        yield Footer()

    def action_show_search(self) -> None:
        self.push_screen(SearchModal(self.search_index), self.on_search_result)

    def on_search_result(self, result: Tuple[Optional[str], str]) -> None:
        topic_name, field_filter = result
        if topic_name:
            topic = next((t for t in self.topics if t.name == topic_name), None)
            if topic:
                self.select_topic(topic, field_filter)

    def select_topic(self, topic: TopicInfo, field_filter: str = "") -> None:
        self.current_topic = topic
        self.current_msg_index = 0
        self.current_field_filter = field_filter
        
        info_str = f"{topic.name} ({topic.message_type})"
        if field_filter:
            info_str += f" | Filter: .{field_filter}"
            
        self.query_one("#topic-bar", Static).update(info_str)
        
        timeline = self.query_one("#timeline", Timeline)
        timeline.total = topic.message_count - 1
        timeline.current = 0
        
        self.query_one("#frame_label", Label).update(f"0 / {topic.message_count - 1}")
        
        self.load_message()

    def watch_current_msg_index(self, new_val: int) -> None:
        self.load_message()

    def load_message(self) -> None:
        if not self.current_topic:
            return
            
        # Update Timeline
        timeline = self.query_one("#timeline", Timeline)
        timeline.current = self.current_msg_index
        self.query_one("#frame_label", Label).update(f"{self.current_msg_index} / {max(0, self.current_topic.message_count - 1)}")

        tree = self.query_one("#data-tree", Tree)
        tree.clear()
        
        root_label = f"{self.current_topic.name}"
        if self.current_field_filter:
            root_label += f".{self.current_field_filter}"
            
        # Ensure we use a valid theme color (accent)
        tree.root.label = Text(root_label, style=f"bold {self.rose_theme.accent}")
        tree.root.expand()
        
        try:
            gen = self.reader.messages(connections=[x for x in self.reader.connections if x.topic == self.current_topic.name])
            target_msg = next(islice(gen, self.current_msg_index, None), None)
            
            if target_msg:
                conn, ts, raw = target_msg
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

                self.build_tree(tree.root, data_to_show)

            else:
                tree.root.add(Text("Message not found", style="bold red"))
                
        except Exception as e:
            tree.root.add(Text(f"Error: {e}", style="bold red"))

    def build_tree(self, node: Tree, data: any) -> None:
        """Recursively add nodes to the tree."""
        # reusing previous logic
        
        if hasattr(data, '__slots__'):
            for field in data.__slots__:
                val = getattr(data, field)
                self._add_child_node(node, field, val)
                
        elif hasattr(data, '__dict__'):
            for field, val in data.__dict__.items():
                if field.startswith('_'): continue
                self._add_child_node(node, field, val)
                
        elif isinstance(data, dict):
            for key, val in data.items():
                self._add_child_node(node, str(key), val)
                
        elif isinstance(data, (list, tuple)):
            if len(data) > 0 and isinstance(data[0], (int, float, bool)) and len(data) > 20:
                 summary = f"<Array[{len(data)}] {data[:5]}...>"
                 node.add(Text(summary, style="dim italic"))
            else:
                for i, item in enumerate(data):
                    self._add_child_node(node, f"[{i}]", item)
                    
        else:
             node.add(Text(str(data), style=self.rose_theme.info))

    def _add_child_node(self, parent: Tree, label: str, value: any) -> None:
        is_container = False
        if hasattr(value, '__slots__') or hasattr(value, '__dict__') or isinstance(value, (dict, list, tuple)):
             is_container = True
             
        if is_container:
            subtree = parent.add(Text(label, style="bold " + self.rose_theme.info))
            self.build_tree(subtree, value)
            subtree.expand() 
        else:
            style_val = "green" if isinstance(value, (int, float)) else "white"
            text = Text.assemble(
                (f"{label}: ", "bold " + self.rose_theme.info),
                (str(value), style_val)
            )
            parent.add(text)

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self.current_topic:
            return 
        if event.button.id == "btn_prev":
            self.action_prev_msg()
        elif event.button.id == "btn_next":
            self.action_next_msg()
