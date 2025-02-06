from pathlib import Path
from textual.widgets import (DataTable)
from components.BagSelector import BagSelector
from core.Types import BagManager
class TaskTable(DataTable):
    """Table for displaying tasks"""
    
    def __init__(self):
        super().__init__()
        self.task_count = 0
    
    def on_mount(self) -> None:
        """Initialize table when mounted"""
        self.cursor_type = "row"
        self.border_title = "Tasks"

        self.watch(self.app.query_one(BagSelector), "bags", self.handle_bags_change)
    
    @property
    def bags(self) -> BagManager:
        return self.app.query_one(BagSelector).bags
      
    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle changes in BagManager and update tasks accordingly"""
        self.render_tasks()
    
    def render_tasks(self) -> None:
        """Render tasks based on BagManager's state"""
        self.clear(columns=True)
        self.add_columns("ID", "Status", "Input", "Output", "Time Range", "Size", "Time Elapsed")
        self.add_class("has-header")
        for bag in self.app.query_one(BagSelector).bags.bags.values():
            self.add_row(
                str(self.task_count),
                f"{bag.status.name}",
                Path(bag.path).name,
                Path(bag.output_file).name,
                f"{bag.info.time_range_str[0][8:]}->{bag.info.time_range_str[1][8:]}",
                bag.info.size_str,
                "0.00s",
            )

