from textual.app import App, ComposeResult, SystemCommand
from textual.widgets import (
    Button, Input, Label
)
from textual.containers import Container, Vertical
from textual import work
from textual.worker import Worker, WorkerState
import time
from pathlib import Path
from typing import Tuple
from core.util import get_logger
from components.BagSelector import BagSelector
from core.Types import BagManager, FilterConfig, BagStatus
from core.util import Operation
import re
logger = get_logger("ControlPanel")

class ControlPanel(Container):
    """A container widget providing controls for ROS bag file operations"""
    
    def __init__(self):
        super().__init__()
        self.logger = logger.getChild("ControlPanel")
        self.multi_select_mode = False
        self.current_bag_path = None
        
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
        if self.multi_select_mode:
            self.set_disable_info()
            return
        
        if bags.get_bag_numbers() == 1:
            bag = bags.get_single_bag()
            # Check if the bag path has actually changed
            # Only update input values when a new bag is loaded
            if self.current_bag_path != bag.path:
                self.current_bag_path = bag.path
                self.set_time_range(bag.info.time_range_str)
                self.set_output_file(f"{bag.path.stem}_filtered.bag")
        elif bags.get_bag_numbers() == 0:
            self.reset_info()
            self.current_bag_path = None
    
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

    
    def _validate_output_file(self) -> bool:
        """Validate and fix output file extension"""
        output_file = self.query_one("#output-file").value
        if output_file and not output_file.endswith('.bag'):
            output_file += '.bag'
            self.set_output_file(output_file)
            self.app.notify(
                "output file must end with .bag, added for you. :)",
                title="Info",
                severity="information"
            )
            return False
        return True

    def _validate_time_range(self) -> bool:
        """Validate that the time range is within the bag's initial range"""
        if self.bags.get_bag_numbers() != 1:
            return True

        bag = self.bags.get_single_bag()
        start_time, end_time = self.get_time_range()
        
        try:
            input_start = Operation.from_datetime(start_time)
            input_end = Operation.from_datetime(end_time)
            bag_start, bag_end = bag.info.init_time_range
            
            print(f"input_start: {input_start}, input_end: {input_end}, bag_start: {bag_start}, bag_end: {bag_end}")
            if input_start[0] < bag_start[0] or input_end[0] > bag_end[0]:
                # Reset to initial time range
                self.set_time_range(bag.info.init_time_range_str)
                self.app.notify(
                    f"Time range reset to {bag.info.init_time_range_str[0]} - {bag.info.init_time_range_str[1]}",
                    title="Invalid Time Range",
                    severity="warning"
                )
                return False
            return True
        except ValueError as e:
            self.logger.warning(f"Invalid time format: {str(e)}")
            return False

    def handle_run_process(self) -> None:
        """Handle Run button press with validation"""
        if self.bags.get_bag_numbers() == 0:
            self.app.notify("Please select at least one bag file", title="Error", severity="error")
            return

        if not self.bags.get_selected_topics():
            self.app.notify("Please select at least one topic", title="Error", severity="error")
            return

        if not self.multi_select_mode:
            # Validate output file
            if not self._validate_output_file():
                return

            # Validate time range
            if not self._validate_time_range():
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
    def _process(self, bag_path: str, config: FilterConfig, output_file: str) -> None:
        """Handle task creation for single bag"""
        process_start = time.time()

        Operation.filter_bag(
            str(bag_path),
            str(output_file),
            config.topic_list,
            config.time_range
        )
        process_end = time.time()
        # Convert to milliseconds
        time_elapsed = int((process_end - process_start) * 1000)
        
        self.bags.set_time_elapsed(bag_path, time_elapsed)
        self.bags.set_size_after_filter(bag_path, output_file.stat().st_size)
        

    def extract_paths_from_description(self, description: str) -> Tuple[Path, Path]:
            """Extract two PosixPaths from worker description string using regex"""
            path_pattern = r"PosixPath\('([^']+)'\)"
            matches = re.findall(path_pattern, description)
            
            if len(matches) < 2:
                raise ValueError("Could not find two paths in description")
            
            return Path(matches[0]), Path(matches[1])
        
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        
        """Called when the worker state changes."""
        worker = event.worker
        state = event.state
        
        input_path, output_path = self.extract_paths_from_description(worker.description)
        
        bag_name = input_path.stem
        if state == WorkerState.SUCCESS:
            self.bags.set_status(input_path, BagStatus.SUCCESS)
            self.app.notify(f"Successfully processed {bag_name}",
                title="Success",
                severity="information")
        elif state == WorkerState.ERROR:
            self.app.notify(f"Failed when processing {bag_name} ",
                title="Error",
                severity="error")


    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes and update bag configurations"""
        if self.bags.get_bag_numbers() == 0 or self.multi_select_mode:
            return

        input_id = event.input.id
        if input_id == "start-time" or input_id == "end-time":
            self._update_time_range()
        elif input_id == "output-file":
            self._update_output_file()

    def _update_time_range(self) -> None:
        """Update time range for current bag"""
        try:
            time_range = Operation.convert_time_range_to_tuple(*self.get_time_range())
            if self.bags.get_bag_numbers() == 1:
                bag = self.bags.get_single_bag()
                self.bags.set_time_range(bag.path, time_range)
        except ValueError as e:
            self.logger.warning(f"Invalid time range: {str(e)}")

    def _update_output_file(self) -> None:
        """Update output file name for current bag"""
        output_file = self.query_one("#output-file").value
        if not output_file:
            return
        if self.bags.get_bag_numbers() == 1:
            bag = self.bags.get_single_bag()
            self.bags.set_output_file(bag.path, output_file)
