widgets的边框可以定义在自己的class内部，也可以定义在父级容器中，前者更方便一些。需要注意的是，针对两种不同情况，css的定义是不一样的，需要相应地定义其边框样式。

## 定义在widgets内部

```css
TopicTree {
    border: solid $secondary;
    background: $panel;
    padding: 1; 
}

```
直接在组件内部定义
```python
class TopicTree(Tree):
    """Tree view for displaying bag topics with multi-selection support"""
    
    def __init__(self, bag_path: Optional[str] = None):
        super().__init__("Topics")
        self.bag_path = bag_path
        self.selected_topics = set()
    
    async def on_mount(self) -> None:
        """Load topics when the widget is mounted"""
        self.theme = "gruvbox"
        self.root.expand()
        self.border_title = "Topics"
        self.border_subtitle = "Selected: 0"
        if self.bag_path:
            await self.load_topics(self.bag_path)
```

## 定义在父级容器中 

```css
#topics-container {
    border: solid $secondary;
    background: $panel;
    padding: 1; 
}
```
在父级容器加载时query并设置边框标题
```python
    def on_mount(self) -> None:
        """Initial setup after mounting."""
        # Set border titles
        self.query_one("#file-explorer").border_title = "File Explorer"
        self.query_one("#tasks-table").border_title = "Tasks"
        # self.query_one("#info-panel").border_title = "Information"
```