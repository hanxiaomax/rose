from textual.app import App, ComposeResult, SystemCommand
from textual.widgets import (
    Button, Input, Label
)
from textual.containers import Container, Vertical
from textual import work
from textual.worker import Worker, WorkerState
import time
from pathlib import Path
from core.util import get_logger
from components.BagSelector import BagSelector
from core.Types import BagManager, FilterConfig
from core.util import Operation

logger = get_logger("ControlPanel")

class ControlPanel(Container):
    """A container widget providing controls for ROS bag file operations"""
    
    def __init__(self):
        super().__init__()
        self.logger = logger.getChild("ControlPanel")
        self.multi_select_mode = False
        
    def on_mount(self) -> None:
        """Initialize control panel"""
        self.border_title = "Control Panel"
        self.watch(self.app.query_one(BagSelector), "bags", self.handle_bags_change)
        self.watch(self.app.query_one(BagSelector), "multi_select_mode", 
                                self.handle_multi_select_mode_change)
    
    @property
    def bags(self) -> BagManager:
        return self.app.query_one(BagSelector).bags
    
    def handle_multi_select_mode_change(self, multi_select_mode: bool) -> None:
        """Handle multi select mode change"""
        self.multi_select_mode = multi_select_mode
        self.set_disable(self.multi_select_mode)

    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle bag change event"""
        
        #set disable info when in multi mode
        if self.multi_select_mode:
            self.set_disable_info()
            return
        #clean content when no bag select in single mode
        if bags.get_bag_numbers() == 0:
            self.reset_info()
        #set information when bag selected in single mode
        if bags.get_bag_numbers() == 1:
            bag = bags.get_single_bag()
            self.set_time_range(bag.info.time_range_str)
            self.set_output_file(f"{bag.path.stem}_filtered.bag")
            return
    

            
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the control panel"""
        with Vertical():
            with Vertical():
                with Vertical(id="time-range-container1"):
                    yield Label("From:")
                    yield Input(placeholder="[YY/MM/DD HH:MM:SS]", id="start-time", classes="time-input")
                with Vertical(id="time-range-container2"):
                    yield Label("To:")
                    yield Input(placeholder="[YY/MM/DD HH:MM:SS]", id="end-time", classes="time-input")
                with Vertical(id="output-file-container"):
                    yield Label("Output File:")
                    yield Input(placeholder="", id="output-file", classes="file-input")
            
            with Container(id="run-btn-container"):
                yield Button(label="Run", variant="primary", id="run-btn", classes="task-btn")
    
    def get_time_range(self) -> 'tuple[str, str]':
        """Get the current time range from inputs, converting to milliseconds"""
        return self.query_one("#start-time").value, self.query_one("#end-time").value
    
    # def get_output_file(self, bag_path: Path = None) -> str:
    #     """Get the output file name"""
    #     if bag_path:
    #         # For Python < 3.9 compatibility
    #         return str(bag_path.parent / f"{bag_path.stem}_filtered{bag_path.suffix}")
    #     else:
    #         return self.query_one("#output-file").value or "output.bag"

    
    def set_time_range(self, time_range_str) -> None:
        self.query_one("#start-time").value = time_range_str[0]
        self.query_one("#end-time").value = time_range_str[1]
    
    def reset_info(self) -> None:
        """Set the time range in inputs, converting from milliseconds to seconds"""
        self.query_one("#start-time").value = ""
        self.query_one("#end-time").value = ""
        self.query_one("#output-file").value = ""
    
    def set_disable_info(self) -> None:
        """Set the disable state of the control panel"""
        self.query_one("#start-time").value = "slice not supported"
        self.query_one("#end-time").value = "slice not supported"
        self.query_one("#output-file").value = "Filename will be generated"
    
    def set_output_file(self, output_file: str) -> None:
        """Set the output file name"""
        self.query_one("#output-file").value = output_file

    def set_disable(self,disable:bool) -> None:
        """Render the enable state of the control panel"""
        if disable:
            self.set_disable_info()
            for input_widget in self.query("Input"):
                input_widget.disabled = True
        else:
            self.reset_info()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "run-btn":
            self.handle_run_process()

    
    def handle_run_process(self) -> None:
        if self.bags.get_bag_numbers() == 0:
            self.app.notify("Please select at least one bag file", title="Error", severity="error")
            return

        if not self.bags.get_selected_topics():
            self.app.notify("Please select at least one topic", title="Error", severity="error")
            return

        try:
            for bag_path, bag in self.bags.bags.items():
                
                self._process(bag_path,
                                bag.get_filter_config(),
                                bag.output_file)
            
        except Exception as e:
            self.logger.error(f"Error during bag filtering: {str(e)}", exc_info=True)
            self.app.notify(f"Error during bag filtering: {str(e)}", title="Error", severity="error")

    @work(thread=True)
    def _process(self,bag_path: str, config: FilterConfig,output_file:str) -> None:
        """Handle task creation for single bag"""
        process_start = time.time()

        Operation.filter_bag(
            bag_path.name,
            output_file.name,
            config.topic_list,
            config.time_range
        )
        process_end = time.time()
        time_cost = int(process_end - process_start)
        
        # # update UI
        # self.app.call_from_thread(
        #     task_table.add_task,
        #     bag_path,
        #     output_file,
        #     time_cost,
        #     time_range
        # )
            

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        worker = event.worker
        state = event.state
        
        print(f"Worker state changed: {worker}")
        bag_name = Path(worker.description.split(",")[0]).stem
        if state == WorkerState.SUCCESS:
            self.app.notify(f"Successfully processed {bag_name}",
                title="Success",
                severity="information")
        elif state == WorkerState.ERROR:
            self.app.notify(f"Failed when processing {bag_name} ",
                title="Error",
                severity="error")
        #elif state == WorkerState.RUNNING:
        #    self.app.notify(
        #        f"Task started, please wait...",
        #        title="INFO",severity="information")
