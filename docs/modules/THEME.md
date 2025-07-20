# Theme 模块使用指南

## 概述

Theme 模块提供了Rose的主题系统，支持CSS主题解析、颜色管理、动态主题切换和多平台适配，为CLI、TUI和Web界面提供统一的视觉体验。

## 主要特性

- ✅ **CSS主题解析**: 支持完整的CSS语法和变量
- ✅ **动态切换**: 运行时主题切换，无需重启
- ✅ **多平台支持**: CLI/TUI/Web界面统一主题
- ✅ **颜色管理**: 智能颜色转换和适配
- ✅ **预设主题**: 内置多种精美主题
- ✅ **自定义扩展**: 支持用户自定义主题

## 核心类型

### ThemeColors (数据类)

```python
@dataclass
class ThemeColors:
    # 基础颜色
    primary: str = "#3b82f6"        # 主色调
    secondary: str = "#6b7280"      # 次要色
    accent: str = "#8b5cf6"         # 强调色
    success: str = "#10b981"        # 成功色
    warning: str = "#f59e0b"        # 警告色
    error: str = "#ef4444"          # 错误色
    
    # 背景和文字
    background: str = "#ffffff"     # 背景色
    surface: str = "#f8fafc"        # 表面色
    foreground: str = "#1f2937"     # 前景文字色
    muted: str = "#9ca3af"          # 静音文字色
    
    # 边框和分割线
    border: str = "#e5e7eb"         # 边框色
    divider: str = "#d1d5db"        # 分割线色
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
    
    def to_rich_style(self) -> Dict[str, str]:
        """转换为Rich库样式"""
    
    def to_css_vars(self) -> str:
        """转换为CSS变量"""
```

### Theme (数据类)

```python
@dataclass  
class Theme:
    name: str                       # 主题名称
    colors: ThemeColors            # 颜色配置
    typography: Dict[str, Any]     # 字体配置
    spacing: Dict[str, int]        # 间距配置
    borders: Dict[str, str]        # 边框配置
    shadows: Dict[str, str]        # 阴影配置
    
    def apply_to_rich(self) -> None:
        """应用到Rich控制台"""
    
    def apply_to_textual(self) -> str:
        """生成Textual CSS"""
    
    def export_css(self) -> str:
        """导出完整CSS"""
```

## 主要接口

### get_current_theme() - 获取当前主题

```python
def get_current_theme() -> Theme:
    """获取当前活动主题"""
```

### get_current_colors() - 获取当前颜色

```python
def get_current_colors() -> ThemeColors:
    """获取当前主题的颜色配置"""
```

### set_theme() - 设置主题

```python
def set_theme(theme_name: str) -> bool:
    """设置当前主题"""
```

### load_theme_from_css() - 从CSS加载主题

```python
def load_theme_from_css(css_content: str, theme_name: str) -> Theme:
    """从CSS内容创建主题"""
```

## 使用示例

### 基础主题使用

```python
from roseApp.core.theme import get_current_theme, get_current_colors

# 获取当前主题
theme = get_current_theme()
print(f"当前主题: {theme.name}")

# 获取颜色配置
colors = get_current_colors()
print(f"主色调: {colors.primary}")
print(f"背景色: {colors.background}")
print(f"成功色: {colors.success}")

# 在Rich中使用颜色
from rich.console import Console
console = Console()

console.print("这是主色调文本", style=f"color {colors.primary}")
console.print("这是成功信息", style=f"color {colors.success}")
console.print("这是错误信息", style=f"color {colors.error}")
```

### 主题切换

```python
from roseApp.core.theme import set_theme, get_available_themes

# 查看可用主题
available_themes = get_available_themes()
print("可用主题:")
for theme_name in available_themes:
    print(f"  - {theme_name}")

# 切换到暗色主题
success = set_theme("dark")
if success:
    print("成功切换到暗色主题")
    colors = get_current_colors()
    print(f"新的背景色: {colors.background}")
else:
    print("主题切换失败")

# 切换到自定义主题
set_theme("ocean-blue")
```

### 自定义CSS主题

```python
from roseApp.core.theme import load_theme_from_css, register_theme

# 定义自定义CSS主题
custom_css = """
:root {
    --primary: #ff6b6b;
    --secondary: #4ecdc4; 
    --accent: #45b7d1;
    --success: #96ceb4;
    --warning: #feca57;
    --error: #ff9ff3;
    
    --background: #2c3e50;
    --surface: #34495e;
    --foreground: #ecf0f1;
    --muted: #95a5a6;
    
    --border: #7f8c8d;
    --divider: #bdc3c7;
}

.title {
    font-size: 24px;
    font-weight: bold;
    color: var(--primary);
}

.subtitle {
    font-size: 18px;
    color: var(--secondary);
}
"""

# 从CSS创建主题
custom_theme = load_theme_from_css(custom_css, "custom-coral")

# 注册主题
register_theme(custom_theme)

# 使用自定义主题
set_theme("custom-coral")
print("已切换到自定义珊瑚主题")
```

### Rich控制台主题应用

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from roseApp.core.theme import get_current_colors

colors = get_current_colors()
console = Console()

# 创建主题化表格
table = Table(
    title="ROS Bag 信息",
    title_style=f"bold {colors.primary}",
    border_style=colors.border,
    header_style=f"bold {colors.accent}"
)

table.add_column("话题", style=colors.foreground)
table.add_column("类型", style=colors.secondary)
table.add_column("消息数", justify="right", style=colors.success)

table.add_row("/camera/image", "sensor_msgs/Image", "1,234")
table.add_row("/lidar/points", "sensor_msgs/PointCloud2", "5,678")

console.print(table)

# 创建主题化面板
panel = Panel(
    "这是一个使用当前主题的面板",
    title="信息面板",
    border_style=colors.primary,
    title_align="left"
)
console.print(panel)
```

### Textual应用主题

```python
from textual.app import App
from textual.widgets import Header, Footer, Button
from roseApp.core.theme import get_current_theme

class ThemedApp(App):
    def __init__(self):
        super().__init__()
        # 应用当前主题的CSS
        theme = get_current_theme()
        self.css = theme.apply_to_textual()
    
    def compose(self):
        yield Header()
        yield Button("主题化按钮", id="themed-button")
        yield Footer()

# 运行主题化应用
app = ThemedApp()
app.run()
```

### 动态主题切换

```python
import asyncio
from roseApp.core.theme import set_theme, get_current_colors

async def theme_demo():
    """演示动态主题切换"""
    themes = ["light", "dark", "ocean", "forest", "sunset"]
    
    for theme_name in themes:
        print(f"\n切换到主题: {theme_name}")
        set_theme(theme_name)
        
        colors = get_current_colors()
        print(f"主色调: {colors.primary}")
        print(f"背景色: {colors.background}")
        
        # 模拟UI更新
        await asyncio.sleep(2)

# 运行演示
asyncio.run(theme_demo())
```

### Web界面主题导出

```python
from roseApp.core.theme import get_current_theme

# 导出当前主题为CSS
theme = get_current_theme()
css_content = theme.export_css()

# 保存到文件
with open("current_theme.css", "w") as f:
    f.write(css_content)

print("主题CSS已导出到 current_theme.css")

# 生成内联样式
colors = theme.colors
inline_styles = f"""
<style>
    body {{
        background-color: {colors.background};
        color: {colors.foreground};
        font-family: 'Inter', sans-serif;
    }}
    
    .primary-button {{
        background-color: {colors.primary};
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
    }}
    
    .success-message {{
        color: {colors.success};
        background-color: {colors.surface};
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid {colors.success};
    }}
</style>
"""

print("内联样式生成完成")
```

## 高级功能

### 主题继承和扩展

```python
from roseApp.core.theme import get_theme, create_theme_variant

# 获取基础主题
base_theme = get_theme("dark")

# 创建主题变体
variant_colors = {
    "primary": "#ff6b6b",      # 改变主色调
    "accent": "#4ecdc4"        # 改变强调色
}

custom_variant = create_theme_variant(
    base_theme=base_theme,
    name="dark-coral",
    color_overrides=variant_colors
)

# 注册并使用变体
register_theme(custom_variant)
set_theme("dark-coral")
```

### 响应式颜色适配

```python
from roseApp.core.theme import adapt_colors_for_terminal

# 获取当前颜色
colors = get_current_colors()

# 为终端环境适配颜色
terminal_colors = adapt_colors_for_terminal(colors)

print("原始颜色:")
print(f"  主色调: {colors.primary}")
print(f"  背景色: {colors.background}")

print("终端适配颜色:")
print(f"  主色调: {terminal_colors.primary}")
print(f"  背景色: {terminal_colors.background}")
```

### 主题验证和测试

```python
from roseApp.core.theme import validate_theme, test_theme_contrast

# 验证主题完整性
theme = get_current_theme()
validation_result = validate_theme(theme)

if validation_result.is_valid:
    print("主题验证通过")
else:
    print("主题验证失败:")
    for error in validation_result.errors:
        print(f"  - {error}")

# 测试颜色对比度
contrast_results = test_theme_contrast(theme.colors)
for test_name, result in contrast_results.items():
    status = "✓" if result.passes_wcag else "✗"
    print(f"{status} {test_name}: 对比度 {result.ratio:.2f}")
```

### 主题性能优化

```python
from roseApp.core.theme import optimize_theme, get_theme_cache_stats

# 优化主题性能
theme = get_current_theme()
optimized_theme = optimize_theme(theme)

print("主题优化完成:")
print(f"原始CSS大小: {len(theme.export_css())} 字符")
print(f"优化后大小: {len(optimized_theme.export_css())} 字符")

# 查看主题缓存统计
cache_stats = get_theme_cache_stats()
print(f"缓存命中率: {cache_stats['hit_rate']:.1%}")
print(f"缓存大小: {cache_stats['cache_size']} 个主题")
```

## 预设主题

### 内置主题列表

```python
# Light 主题 - 明亮清新
LIGHT_THEME = {
    "primary": "#3b82f6",
    "background": "#ffffff", 
    "foreground": "#1f2937"
}

# Dark 主题 - 深色护眼
DARK_THEME = {
    "primary": "#60a5fa",
    "background": "#1f2937",
    "foreground": "#f9fafb"
}

# Ocean 主题 - 海洋蓝调
OCEAN_THEME = {
    "primary": "#0ea5e9",
    "background": "#0c4a6e",
    "foreground": "#e0f2fe"
}

# Forest 主题 - 森林绿意
FOREST_THEME = {
    "primary": "#22c55e", 
    "background": "#14532d",
    "foreground": "#f0fdf4"
}

# Sunset 主题 - 日落暖色
SUNSET_THEME = {
    "primary": "#f97316",
    "background": "#7c2d12", 
    "foreground": "#fff7ed"
}
```

### 主题预览

```python
from roseApp.core.theme import preview_theme

# 预览所有可用主题
available_themes = get_available_themes()

for theme_name in available_themes:
    print(f"\n=== {theme_name.upper()} 主题预览 ===")
    preview_theme(theme_name)
```

## 最佳实践

### 1. 主题选择策略

```python
import os
from roseApp.core.theme import detect_system_theme, set_theme

def smart_theme_selection():
    """智能主题选择"""
    
    # 检测系统主题偏好
    system_preference = detect_system_theme()
    
    # 检测终端支持
    supports_truecolor = os.environ.get('COLORTERM') in ['truecolor', '24bit']
    
    if system_preference == "dark":
        theme = "dark" if supports_truecolor else "dark-simple"
    else:
        theme = "light" if supports_truecolor else "light-simple"
    
    set_theme(theme)
    print(f"自动选择主题: {theme}")

smart_theme_selection()
```

### 2. 响应式设计

```python
def create_responsive_ui():
    """创建响应式主题UI"""
    colors = get_current_colors()
    
    # 根据终端宽度调整样式
    import shutil
    terminal_width = shutil.get_terminal_size().columns
    
    if terminal_width < 80:
        # 窄屏幕样式
        title_style = f"bold {colors.primary}"
        content_style = colors.foreground
    else:
        # 宽屏幕样式  
        title_style = f"bold underline {colors.primary}"
        content_style = f"{colors.foreground} on {colors.surface}"
    
    return title_style, content_style
```

### 3. 主题持久化

```python
from roseApp.core.theme import save_theme_preference, load_theme_preference

# 保存用户主题偏好
def save_user_theme(theme_name: str):
    save_theme_preference(theme_name)
    print(f"主题偏好已保存: {theme_name}")

# 加载用户主题偏好
def load_user_theme():
    preferred_theme = load_theme_preference()
    if preferred_theme:
        set_theme(preferred_theme)
        print(f"已加载用户偏好主题: {preferred_theme}")
    else:
        print("未找到用户主题偏好，使用默认主题")

# 应用启动时加载
load_user_theme()
```

### 4. 主题兼容性

```python
def ensure_theme_compatibility():
    """确保主题兼容性"""
    current_theme = get_current_theme()
    
    # 检查颜色对比度
    colors = current_theme.colors
    bg_luminance = calculate_luminance(colors.background)
    fg_luminance = calculate_luminance(colors.foreground)
    
    contrast_ratio = (max(bg_luminance, fg_luminance) + 0.05) / (min(bg_luminance, fg_luminance) + 0.05)
    
    if contrast_ratio < 4.5:  # WCAG AA 标准
        print("警告: 当前主题对比度不足，可能影响可读性")
        
        # 自动调整到高对比度版本
        high_contrast_theme = f"{current_theme.name}-high-contrast"
        if high_contrast_theme in get_available_themes():
            set_theme(high_contrast_theme)
            print(f"已自动切换到高对比度主题: {high_contrast_theme}")

ensure_theme_compatibility()
```

## 内部实现

### 主题系统架构

```
ThemeManager
├── CSS解析器
│   ├── 变量提取
│   ├── 规则解析
│   └── 继承处理
├── 颜色管理
│   ├── 格式转换
│   ├── 对比度计算
│   └── 适配算法
└── 平台适配
    ├── Rich样式
    ├── Textual CSS
    └── Web CSS
```

### 主题缓存机制

- **解析缓存**: CSS解析结果缓存
- **颜色缓存**: 颜色转换结果缓存  
- **样式缓存**: 平台特定样式缓存
- **智能失效**: 主题变更时自动清理相关缓存

### 性能特性

- **延迟加载**: 按需加载主题资源
- **增量更新**: 仅更新变化的样式
- **批量应用**: 批量应用样式变更
- **内存优化**: 智能内存管理和清理

这个主题系统为Rose提供了强大而灵活的视觉定制能力，支持多种界面类型和使用场景，确保了一致的用户体验。 