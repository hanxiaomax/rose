```python
def load_bag(self, path: Path) -> 'tuple[list, list, tuple[float, float]]':
        """Load bag file and return topics, connections and time range"""
        try:
            #lower level C++ code which is synchronous
            return Operation.load_bag(str(path))
        except Exception as e:
            self.app.query_one("#status").update(f"Error loading bag: {str(e)}")
            return [], [], (0.0, 0.0)

@work
async def on_tree_node_selected(self, event: DirectoryTree.NodeSelected) -> None:
    """Handle file selection with improved directory navigation"""
    path = event.node.data.path
    self.current_node = event.node
    self.show_guides = True
    
    if path.is_dir():
        # Handle directory selection
        if path == self.current_path:
            self.path = self.current_path.parent
        else:
            self.path = path
        self.current_path = self.path
        status = self.app.query_one("#status")
        status.update(f"File: {self.path}")

    elif str(path).endswith('.bag'):
        # Handle bag file selection
        self.app.selected_bag = str(path)
        status = self.app.query_one("#status")
        status.update(f"File: {path}")
        
        # Load bag and update UI
        topics, connections, (start_time, end_time) = self.load_bag(path)
        
        # Update TopicTree
        topic_tree = self.app.query_one(TopicTree)
        topic_tree.set_topics(topics)
        
        # Update ControlPanel
        control_panel = self.app.query_one(ControlPanel)
        control_panel.set_time_range(start_time, end_time)
        control_panel.set_output_file(f"{path.stem}_filtered.bag")
```
上面代码中，由于Operation.load_bag(str(path))是阻塞的，所以load_bag函数不能使用普通的work，只能使用[Thread Workers](https://textual.textualize.io/guide/workers/#thread-workers)。然后在执行完成后，根据work的状态更新topic tree和control panel。因此暂时将on_tree_node_selected作为work来使用。后续可以使用线程或者将底层函数实现为异步。

在异步编程中，通常建议将阻塞操作放在最内层的函数中，并使用@work装饰器。这样可以让调用链中的其他函数保持异步特性，并且更容易管理异步任务。
