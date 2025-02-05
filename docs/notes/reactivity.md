# Reactivity
## 一个watch的例子

下面展示了[官方文档-reactivity](https://textual.textualize.io/guide/reactivity/#reactivity)中没有说清楚的两个点：
1. 是否可以支持自定义类型
2. 在观察者组件中如何使用[mutate_reactive](https://textual.textualize.io/api/dom_node/#textual.dom.DOMNode.mutate_reactive)触发reactive

```python
class BagSelector(DirectoryTree):
    """A directory tree widget specialized for selecting ROS bag files"""

    bag_manager = reactive(BagManager())
    def _handle_bagfile_selection(self, path: Path, event: DirectoryTree.NodeSelected,multi_select_mode:bool ) -> None:
    # clear bags before load current bag
    if not multi_select_mode:
        self.bag_manager.clear_bags()
        self.bag_manager.load_bag(path)
    else:
        if path not in self.bag_manager.bags:
            self.bag_manager.load_bag(path)
            event.node.label = Text("☑️ ") + Text(path.name)
        else:
            self.bag_manager.unload_bag(path)
            event.node.label = Text(path.name)

    self.mutate_reactive(BagSelector.bag_manager)  
```
bag_manager = reactive(BagManager())是定义在BagSelector类中的一个reactive，其本身是复杂类型，内部是一个字典，是mutable的。很显然，我们可以使用它，但是必须要按照[Mutable reactives](https://textual.textualize.io/guide/reactivity/#mutable-reactives)的说明使用[mutate_reactive函数](https://textual.textualize.io/api/dom_node/#textual.dom.DOMNode.mutate_reactive)触发。

该函数接受两个参数，一个是`self`，一个是`reactive_value`。且第二个参数要使用类名作为命名空间，例如`BagSelector.my_reactive`。

当bag_manager改变并通过mutate_reactive触发后，观察它的组件会收到通知。当然该组件也可以使用`bag_manager = self.app.query_one(BagSelector).bag_manager`获取该reactive的值并修改。

修改后仍需使用[mutate_reactive函数](https://textual.textualize.io/api/dom_node/#textual.dom.DOMNode.mutate_reactive)但语法为`self.app.query_one(BagSelector).mutate_reactive(BagSelector.bag_manager)`。需要调用`mutate_reactive`函数，仍然是BagSelector的成员函数。`TopicTree`中由于没有定义reactive，是不存在该函数。

```python
class TopicTree(Tree):
    """A tree widget for displaying ROS bag topics with multi-selection capability"""
    
    def on_mount(self) -> None:
        """Initialize when mounted"""
        self.border_title = "Topics"
        ## 观察BagSelector的bag_manager属性
        self.watch(self.app.query_one(BagSelector), "bag_manager", self.handle_bag_manager_change)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle topic selection toggle"""
        if event.node.allow_expand:
            return
        # 修改
        bag_manager = self.app.query_one(BagSelector).bag_manager
        data = event.node.data
        if data:
            data["selected"] = not data["selected"]
            topic = data["topic"]
            
            if data["selected"]:
                bag_manager.selected_topic(topic)
            else:
                bag_manager.deselected_topic(topic)
            # 触发reactive
            self.app.query_one(BagSelector).mutate_reactive(BagSelector.bag_manager)
```
