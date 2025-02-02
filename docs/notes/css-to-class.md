在Textual中，可以通过两种方式控制组件的样式：

1. 直接使用组件类名：Textual会自动将类名转换为CSS选择器，比如`TopicTree`可以直接用`.topic-tree`来设置样式

2. 给组件添加ID：如果需要更精确的控制，可以给组件添加ID

```python
// ... existing code ...
                    with Container(id="topics-container"):
                        yield TopicTree(id="topic-tree")
// ... existing code ...
```

然后在CSS中你可以这样使用：
```css
/* 使用类名 */
TopicTree {
    /* 样式 */
}

/* 使用ID */
#topic-tree {
    /* 样式 */
}
```

通过这两种方式可以灵活地控制组件的样式，以满足不同的设计需求。