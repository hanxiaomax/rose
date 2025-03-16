from pathlib import Path
from textual.widgets import (DataTable)
from roseApp.tui.components.BagExplorer import BagExplorer
from roseApp.core.BagManager import BagManager, BagStatus

class TaskTable(DataTable):
    """Table for displaying tasks"""
    
    def __init__(self):
        super().__init__()
        self.task_count = 0
    
    def on_mount(self) -> None:
        """Initialize table when mounted"""
        self.cursor_type = "row"
        self.border_title = "Tasks"

        self.watch(self.app.query_one(BagExplorer), "bags", self.handle_bags_change)
    
    @property
    def bags(self) -> BagManager:
        return self.app.query_one(BagExplorer).bags
      
    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle changes in BagManager and update tasks accordingly"""
        self.render_tasks()
    
    def get_status_icon(self, status: BagStatus) -> str:
        if status == BagStatus.SUCCESS:
            return "√"
        elif status == BagStatus.ERROR:
            return "×"
        elif status == BagStatus.IDLE:
            return "*"
        else:
            return "?"
        
    def render_tasks(self) -> None:
        """Render tasks based on BagManager's state"""
        self.clear(columns=True)

        self.add_columns("", "Input", "Output", "Time Range", "Size", "Time Elapsed")
        self.add_class("has-header")
        for bag in self.app.query_one(BagExplorer).bags.bags.values():
            if bag.info.size_after_filter == bag.info.size:
                size_content = f"{bag.info.size_str}"
            else:
                size_content = f"{bag.info.size_str}->{bag.info.size_after_filter_str}"
            
            
            self.add_row(
                self.get_status_icon(bag.status),
                Path(bag.path).name,
                Path(bag.output_file).name,
                f"{bag.info.time_range_str[0][8:]},{bag.info.time_range_str[1][8:]}",
                size_content,
                f"{bag.time_elapsed}ms",
            )

