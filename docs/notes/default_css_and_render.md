## Textual Tree 组件样式机制解析

Textual 的 Tree 组件样式机制主要基于以下几个关键点实现：

1. **CSS 样式继承**
   - Tree 组件继承自 Widget 基类，支持标准的 CSS 样式定义
   - 可以通过 `.tree` 类选择器来定义全局样式
   - 支持通过 `id` 或 `class` 选择器为特定 Tree 实例定义样式

2. **节点状态样式**
   - 使用伪类选择器来定义不同状态下的样式：
     - `.tree--cursor`：当前聚焦节点的样式
     - `.tree--highlight`：鼠标悬停节点的样式
     - `.tree--selected`：选中节点的样式
     - `.tree--guides`：引导线的样式

3. **动态样式应用**
   - 组件内部通过 `rich.text.Text` 对象来渲染节点标签
   - 可以在 `render_label` 方法中动态应用样式
   - 支持根据节点数据（如文件类型）应用不同样式

4. **主题支持**
   - 内置支持多种主题（如 `gruvbox`）
   - 可以通过 `theme` 属性切换主题
   - 主题会自动应用到所有节点和交互状态

5. **自定义渲染**
   - 可以通过重写 `render_label` 方法实现完全自定义的节点渲染
   - 支持组合多个样式，如为特定文件类型添加图标和颜色
   - 可以动态修改节点标签的样式和内容

```css
/* 修改选中节点的样式 */
Tree > .tree--cursor {
    background: $accent;
    color: $text;
}

/* 修改鼠标悬停时的样式 */
Tree > .tree--highlight {
    background: $boost;
}

/* 修改 DirectoryTree 选中节点的样式 */
DirectoryTree > .tree--cursor {
    background: $accent;
    color: $text;
}

/* 修改 DirectoryTree 鼠标悬停时的样式 */
DirectoryTree > .tree--highlight {
    background: $boost;
}

/* 如果你想特别指定 BagExplorer 的样式 */
#file-explorer .tree--cursor {
    background: $accent;
    color: $text;
}

#file-explorer .tree--highlight {
    background: $boost;
}
```
默认情况下可以通过定义样式来直接控制渲染。但如果需要自行控制渲染，可以重新render_label方法。

```python
def render_label(self, node: TreeNode, base_style: Style, style: Style) -> Text:
  # 注意调用基类的方法以保持默认行为
    return super().render_label(node, base_style, style)
```