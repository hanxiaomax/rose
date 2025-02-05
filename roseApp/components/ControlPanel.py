
from textual.app import App, ComposeResult, SystemCommand
from textual.widgets import (
    Button, Input, Label
)
from textual.containers import Container, Vertical
from textual import work
from textual.worker import Worker, WorkerState
import time
from pathlib import Path
from core.util import Operation, setup_logging
from components.BagSelector import BagSelector
from core.Types import BagManager


logger = setup_logging()

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
    
    def handle_multi_select_mode_change(self, multi_select_mode: bool) -> None:
        """Handle multi select mode change"""
        self.multi_select_mode = multi_select_mode
        self.set_disable()

    def handle_bags_change(self, bags: BagManager) -> None:
        """Handle bag change event"""
        
        # bag number is 1 can be single mode or multi mode
        # set info when enabled
        if self.multi_select_mode:
            self.set_disable_info()
            return
        
        if bags.get_bag_numbers() == 1:
            bag = bags.get_single_bag()
            self.set_time_range(bag.info.time_range_str)
            self.set_output_file(f"{bag.path.stem}_filtered.bag")
        elif bags.get_bag_numbers() == 0:
            self.reset_info()
        
            
    
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
            
            with Container(id="add-task-btn-container"):
                yield Button(label="Run", variant="primary", id="add-task-btn", classes="task-btn")
    
    def get_time_range(self) -> 'tuple[str, str]':
        """Get the current time range from inputs, converting to milliseconds"""
        return self.query_one("#start-time").value, self.query_one("#end-time").value
    
    def get_output_file(self) -> str:
        """Get the output file name"""
        return self.query_one("#output-file").value or "output.bag"
    
    def set_time_range(self, time_range_str) -> None:
        """Set the time range in inputs, converting from milliseconds to seconds"""
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

    def set_disable(self) -> None:
        """Render the enable state of the control panel"""
        for input_widget in self.query("Input"):
            input_widget.disabled = self.multi_select_mode
        

        if self.multi_select_mode:
            self.set_disable_info()
        else:
            self.reset_info()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "add-task-btn":
            self._handle_add_task()

    
    def _handle_add_task(self) -> None:
        """Handle Run button press"""
        #TODO:ge topics from bag manager
        # bag_selector = self.app.query_one(BagSelector)
        # topic_tree = self.app.query_one(TopicTreePanel).get_topic_tree()
        # selected_topics = topic_tree.get_selected_topics()
        
        # if not selected_topics:
        #     self.app.notify("Please select at least one topic", title="Error", severity="error")
        #     return

        # try:
        #     if bag_selector.multi_select_mode:
        #         self._handle_multi_bag_task(bag_selector, selected_topics)
        #     else:
        #         self._handle_single_bag_task(selected_topics)
        # except Exception as e:
        #     self.logger.error(f"Error during bag filtering: {str(e)}", exc_info=True)
        #     self.app.notify(f"Error during bag filtering: {str(e)}", title="Error", severity="error")

    @work(thread=True)
    def _process(self,task_table, bag_path: str, selected_topics: list,time_range:tuple,output_file:str) -> None:
        """Handle task creation for single bag"""
        process_start = time.time()
        
        Operation.filter_bag(
            bag_path,
            output_file,
            selected_topics,
            time_range
        )
        process_end = time.time()
        time_cost = int(process_end - process_start)
        
        # update UI
        self.app.call_from_thread(
            task_table.add_task,
            bag_path,
            output_file,
            time_cost,
            time_range
        )
            

    def _handle_multi_bag_task(self, bag_selector: BagSelector, selected_topics: list) -> None:
        """Handle task creation for multiple bags"""
        if not bag_selector.selected_bags:
            self.app.notify("Please select at least one bag file", title="Error", severity="error")
            return
        #TODO: tasktable should handle by itself
        task_count = 0
        task_table = self.app.query_one(TaskTable)
        
        for bag_path in bag_selector.selected_bags:
            try:
                _, _, bag_time_range = Operation.load_bag(bag_path)
                output_file = f"{Path(bag_path).stem}_filtered.bag"
                self._process(task_table,bag_path,selected_topics,bag_time_range,output_file)
                task_count += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {bag_path}: {str(e)}", exc_info=True)
                self.app.notify(f"Error processing {Path(bag_path).name}: {str(e)}",
                title="Error",
                severity="error")
        
        if task_count > 0:
            self.app.notify(
                f"Successfully add {task_count} tasks",
                title="INFO",severity="information")
               

    def _handle_single_bag_task(self, selected_topics: list) -> None:
        """Handle task creation for single bag"""
        if not self.app.selected_bag:
            self.app.notify("Please select a bag file first",title="Error",severity="error")
            return

        try:
            self.logger.debug(f"Starting bag filtering task: {self.app.selected_bag} -> {self.get_output_file()}")
            start_time = time.time()
            time_range = Operation.convert_time_range_to_tuple(*self.get_time_range())
            #TODO: tasktable should handle by itself
            task_table = self.app.query_one(TaskTable)

            self._process(task_table,self.app.selected_bag,selected_topics,time_range,self.get_output_file())

        except Exception as e:
            self.logger.error(f"Error processing bag: {str(e)}", exc_info=True)
            self.app.notify(f"Error processing bag: {str(e)}",
                title="Error",
                severity="error")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Called when the worker state changes."""
        worker = event.worker
        state = event.state
        bag_name = Path(worker.description.split(",")[1]).stem
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
