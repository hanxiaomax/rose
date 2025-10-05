# Rose Plugin System Documentation

## 概述

Rose 插件系统是一个强大的扩展框架，允许用户通过插件来扩展 Rose 的功能。系统支持两种插件类型：

- **钩子插件 (Hook Plugins)**：在 Rose 的各种操作前后自动执行自定义逻辑
- **脚本插件 (Script Plugins)**：作为独立脚本运行，提供交互式数据处理功能

插件可以安全地访问和处理 ROS bag 数据，提供自定义的 CLI 命令，以及实现复杂的数据分析工作流。

## 系统架构

### 核心组件

```
roseApp/
├── core/
│   └── plugins/
│       ├── __init__.py          # 插件系统入口
│       ├── base.py              # 钩子插件基类和接口
│       ├── script_base.py       # 脚本插件基类和接口
│       ├── manager.py           # 插件管理器
│       └── data_interface.py    # 数据访问接口
├── cli/
│   └── plugin.py               # 插件管理 CLI 命令
└── ~/.rose/cache/plugins/      # 用户插件目录
```

### 工作原理

1. **插件发现**：系统启动时自动扫描 `~/.rose/cache/plugins/` 目录
2. **插件加载**：动态加载符合规范的 Python 插件文件，区分钩子插件和脚本插件
3. **钩子注册**：钩子插件注册感兴趣的钩子点
4. **钩子执行**：Rose 在相应操作时自动调用注册的钩子
5. **脚本执行**：脚本插件通过 CLI 命令手动执行
6. **数据访问**：插件通过 `DataInterface` 或 `ScriptContext` 访问 bag 数据

### 插件类型

#### 钩子插件 (Hook Plugins)
- **基类**：`BasePlugin`
- **用途**：在 Rose 操作前后自动执行逻辑
- **数据访问**：通过 `DataInterface`
- **执行方式**：事件驱动，自动触发
- **适用场景**：数据验证、自动备份、日志记录、通知系统

#### 脚本插件 (Script Plugins)  
- **基类**：`BaseScriptPlugin`
- **用途**：独立运行的数据处理脚本
- **数据访问**：通过 `ScriptContext`
- **执行方式**：手动执行，支持用户交互
- **适用场景**：数据分析、临时脚本、交互式探索、自定义工具

## 钩子系统

### 支持的钩子类型

| 钩子类型 | 触发时机 | 用途 |
|---------|---------|------|
| `BEFORE_LOAD` | 加载 bag 文件前 | 预处理、验证、准备工作 |
| `AFTER_LOAD` | 加载 bag 文件后 | 数据分析、索引建立、统计 |
| `BEFORE_INSPECT` | 检查 bag 前 | 预处理检查参数 |
| `AFTER_INSPECT` | 检查 bag 后 | 后处理检查结果 |
| `BEFORE_EXTRACT` | 提取数据前 | 预处理提取参数 |
| `AFTER_EXTRACT` | 提取数据后 | 后处理提取结果 |
| `BEFORE_EXPORT` | 导出数据前 | 数据预处理、格式转换 |
| `AFTER_EXPORT` | 导出数据后 | 后处理、通知、清理 |
| `BEFORE_COMPRESS` | 压缩前 | 压缩参数调整 |
| `AFTER_COMPRESS` | 压缩后 | 压缩结果处理 |

### 钩子上下文

每个钩子都会接收一个上下文字典，包含：

```python
context = {
    'bag_path': Path,           # bag 文件路径
    'operation': str,           # 操作类型 ('load', 'export', etc.)
    'data_interface': DataInterface,  # 数据访问接口
    'parameters': dict,         # 操作参数
    'plugin_manager': PluginManager,  # 插件管理器
    # ... 其他操作特定的参数
}
```

## 脚本插件系统

### ScriptContext 类

脚本插件通过 `ScriptContext` 获得完整的 Rose 功能访问：

```python
class MyScriptPlugin(BaseScriptPlugin):
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        # 加载 bag 文件
        bag_path = args.get('bag_path')
        if not context.load_bag(bag_path):
            return False
        
        # 获取主题数据
        topics = context.get_topics()
        df = context.get_dataframe('topic_name')
        
        # 用户交互
        selection = context.ask_user("选择处理方式:")
        if context.confirm("确认继续?"):
            # 处理数据...
            pass
        
        # 格式化输出
        context.print("[green]处理完成![/green]")
        context.print_table(results, "结果表格")
        
        # 导出数据
        return context.export_csv(df, "output.csv")
```

### ScriptContext 方法

#### 数据访问方法
- `load_bag(bag_path, auto_load=True)` - 加载 bag 文件到缓存
- `get_bag_info(bag_path=None)` - 获取 bag 信息
- `get_topics(bag_path=None)` - 获取主题列表
- `filter_topics(patterns, bag_path=None)` - 过滤主题
- `get_dataframe(topic, bag_path=None)` - 获取单个主题数据
- `get_dataframes(topics=None, bag_path=None)` - 获取多个主题数据

#### 数据处理方法
- `merge_dataframes(dataframes)` - 按时间戳合并数据
- `filter_dataframe(df, filters)` - 应用数据过滤器
- `export_csv(df, output_path, include_index=True)` - 导出 CSV

#### 用户交互方法
- `ask_user(question, default=None)` - 获取用户输入
- `confirm(question, default=True)` - 确认对话框

#### 输出格式化方法
- `print(*args, style=None)` - Rich 格式化打印
- `print_table(data, title=None)` - 打印表格

### 脚本插件便捷方法

`BaseScriptPlugin` 提供了一些便捷方法：

```python
class MyAnalyzer(BaseScriptPlugin):
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        bag_path = args.get('bag_path')
        
        # 快速分析
        analysis = self.quick_analysis(bag_path, ['gps', 'imu'])
        
        # 交互式主题选择
        selected_topics = self.interactive_topic_selection(bag_path)
        
        # 加载并获取主题
        topics = self.load_and_get_topics(bag_path)
        
        return True
```

## 数据接口

### DataInterface 类

钩子插件通过 `DataInterface` 访问 Rose 的数据：

```python
data_interface = self.get_data_interface()

# 获取 bag 信息
bag_info = data_interface.get_bag_info(bag_path)

# 检查缓存状态
is_cached = data_interface.is_bag_cached(bag_path)
has_dataframes = data_interface.has_dataframes(bag_path)

# 获取主题信息
topics = data_interface.get_topics(bag_path)
topic_info = data_interface.get_topic_info(bag_path, 'topic_name')

# 获取数据
df = data_interface.get_dataframe(bag_path, 'topic_name')
dataframes = data_interface.get_multiple_dataframes(bag_path, ['topic1', 'topic2'])

# 数据处理
merged_df = data_interface.merge_dataframes(dataframes)
filtered_df = data_interface.filter_dataframe(df, {'start_time': '2023-01-01'})

# 数据导出
success = data_interface.export_to_csv(df, 'output.csv')

# 获取统计信息
stats = data_interface.get_bag_statistics(bag_path)
```

## 插件开发指南

### 1. 创建新插件

使用模板快速创建插件：

#### 钩子插件模板
```bash
# 基础钩子插件模板
rose plugin create my_plugin --template basic

# 数据处理钩子插件模板  
rose plugin create data_plugin --template data_processor

# 钩子示例插件模板
rose plugin create hook_plugin --template hook_example
```

#### 脚本插件模板
```bash
# 基础脚本插件模板
rose plugin create my_script --template script_basic

# 数据分析脚本插件模板
rose plugin create analyzer --template script_analyzer
```

### 2. 插件基本结构

#### 钩子插件结构

```python
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from roseApp.core.plugins import BasePlugin, PluginInfo, HookType

class MyHookPlugin(BasePlugin):
    """自定义钩子插件"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            version="1.0.0", 
            description="我的自定义插件",
            author="Your Name",
            homepage="https://github.com/username/my-plugin",
            requires_pandas=True,  # 如果需要 pandas
            requires_cache=True,   # 如果需要缓存
            supported_hooks=[HookType.AFTER_LOAD, HookType.BEFORE_EXPORT]
        )
    
    def initialize(self) -> bool:
        """初始化插件"""
        # 注册钩子
        self.register_hook(HookType.AFTER_LOAD, self.on_bag_loaded)
        self.register_hook(HookType.BEFORE_EXPORT, self.before_export)
        return True
    
    def on_bag_loaded(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """bag 加载后的钩子"""
        bag_path = context.get('bag_path')
        # 处理逻辑...
        return context
    
    def before_export(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """导出前的钩子"""
        topics = context.get('topics', [])
        # 预处理逻辑...
        return context
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """提供自定义 CLI 命令"""
        return {
            "analyze": self.analyze_command,
            "process": self.process_command
        }
    
    def analyze_command(self, context: Dict[str, Any]) -> bool:
        """分析命令"""
        bag_path = context.get('bag_path')
        console = context.get('console')
        
        data_interface = self.get_data_interface()
        stats = data_interface.get_bag_statistics(bag_path)
        
        if console:
            console.print(f"分析结果: {stats}")
        return True
```

#### 脚本插件结构

```python
from pathlib import Path
from typing import Dict, Any
from roseApp.core.plugins import BaseScriptPlugin, PluginInfo, ScriptContext

class MyScriptPlugin(BaseScriptPlugin):
    """自定义脚本插件"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="my_script",
            version="1.0.0",
            description="我的自定义脚本插件",
            author="Your Name",
            requires_pandas=False,
            requires_cache=True
        )
    
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """
        脚本主执行函数
        
        Args:
            context: ScriptContext 提供 Rose 函数访问
            args: 命令行参数
            
        Returns:
            bool: True 表示执行成功
        """
        # 获取参数
        bag_path = args.get('bag_path')
        topics = args.get('topics', [])
        output = args.get('output')
        
        # 检查参数
        if not bag_path:
            context.print("[yellow]请指定 bag 文件路径: --bag path/to/file.bag[/yellow]")
            return True
        
        # 加载 bag 文件
        context.print(f"[cyan]加载 bag 文件: {bag_path}[/cyan]")
        if not context.load_bag(bag_path):
            context.print("[red]加载失败[/red]")
            return False
        
        # 获取主题
        if not topics:
            all_topics = context.get_topics()
            context.print(f"[green]发现 {len(all_topics)} 个主题[/green]")
            
            # 交互式选择
            selection = context.ask_user("输入主题编号或模式", "all")
            if selection.lower() != "all":
                topics = context.filter_topics([selection])
            else:
                topics = all_topics[:5]  # 限制数量
        
        # 处理数据
        for topic in topics:
            df = context.get_dataframe(topic)
            if df is not None:
                context.print(f"[cyan]处理主题 {topic}: {len(df)} 条消息[/cyan]")
                # 自定义处理逻辑...
        
        # 导出结果
        if output and topics:
            # 合并数据并导出
            dataframes = context.get_dataframes(topics)
            merged_df = context.merge_dataframes(dataframes)
            if context.export_csv(merged_df, output):
                context.print(f"[green]结果已导出到 {output}[/green]")
        
        return True
```

### 3. 高级插件功能

#### 数据处理插件

```python
class DataProcessorPlugin(BasePlugin):
    """数据处理插件示例"""
    
    def process_topics(self, bag_path: Path, topic_patterns: List[str]) -> Dict[str, Any]:
        """处理多个主题的数据"""
        data_interface = self.get_data_interface()
        
        # 过滤主题
        topics = data_interface.filter_topics(bag_path, topic_patterns)
        
        # 获取数据
        dataframes = data_interface.get_multiple_dataframes(bag_path, topics)
        
        # 数据处理
        results = {}
        for topic, df in dataframes.items():
            if df is not None:
                # 自定义数据处理逻辑
                processed_df = self.custom_processing(df)
                results[topic] = processed_df
        
        return results
    
    def custom_processing(self, df) -> Any:
        """自定义数据处理逻辑"""
        # 例如：计算统计信息、数据清洗、特征提取等
        return df
```

#### 钩子插件

```python
class HookPlugin(BasePlugin):
    """钩子使用示例"""
    
    def initialize(self) -> bool:
        # 注册多个钩子
        self.register_hook(HookType.BEFORE_LOAD, self.validate_bag)
        self.register_hook(HookType.AFTER_LOAD, self.analyze_bag)
        self.register_hook(HookType.BEFORE_EXPORT, self.prepare_export)
        self.register_hook(HookType.AFTER_EXPORT, self.notify_completion)
        return True
    
    def validate_bag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """加载前验证 bag 文件"""
        bag_path = context.get('bag_path')
        
        # 验证文件大小、格式等
        if bag_path.stat().st_size > 1024 * 1024 * 1024:  # 1GB
            logger.warning(f"Large bag file detected: {bag_path}")
        
        return context
    
    def analyze_bag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """加载后分析数据"""
        bag_path = context.get('bag_path')
        data_interface = self.get_data_interface()
        
        stats = data_interface.get_bag_statistics(bag_path)
        logger.info(f"Bag analysis: {stats.get('topics_count')} topics, "
                   f"{stats.get('total_messages')} messages")
        
        return context
    
    def prepare_export(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """导出前数据预处理"""
        topics = context.get('topics', [])
        output_path = context.get('output_path')
        
        # 预处理逻辑...
        logger.info(f"Preparing export for {len(topics)} topics to {output_path}")
        
        return context
    
    def notify_completion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """导出完成后通知"""
        success = context.get('success', False)
        output_path = context.get('output_path')
        
        if success:
            logger.info(f"Export completed successfully: {output_path}")
            # 可以发送通知、更新状态等
        
        return context
```

## 插件管理

### 安装插件

```bash
# 从文件安装插件
rose plugin install /path/to/my_plugin.py --name my_plugin

# 查看插件信息
rose plugin info my_plugin

# 启用插件
rose plugin enable my_plugin
```

### 卸载插件

```bash
# 卸载插件
rose plugin uninstall my_plugin --force
```

### 重新加载插件

```bash
# 重新加载插件（开发时很有用）
rose plugin reload my_plugin
```

## 实际使用案例

### 案例1：数据质量检查插件

```python
class DataQualityPlugin(BasePlugin):
    """数据质量检查插件"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="data_quality",
            version="1.0.0",
            description="检查 ROS bag 数据质量",
            author="Rose Team",
            requires_pandas=True,
            supported_hooks=[HookType.AFTER_LOAD]
        )
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_LOAD, self.check_data_quality)
        return True
    
    def check_data_quality(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """检查数据质量"""
        bag_path = context.get('bag_path')
        data_interface = self.get_data_interface()
        
        topics = data_interface.get_topics(bag_path)
        quality_report = {}
        
        for topic in topics:
            df = data_interface.get_dataframe(bag_path, topic)
            if df is not None:
                # 检查数据质量
                quality_report[topic] = {
                    'total_rows': len(df),
                    'null_percentage': df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100,
                    'duplicate_rows': df.duplicated().sum(),
                    'time_gaps': self.check_time_gaps(df)
                }
        
        # 保存质量报告
        context['quality_report'] = quality_report
        logger.info(f"Data quality check completed for {len(topics)} topics")
        
        return context
    
    def check_time_gaps(self, df) -> int:
        """检查时间间隙"""
        if 'timestamp' in df.columns:
            time_diffs = df['timestamp'].diff()
            # 检查是否有异常大的时间间隙（例如 > 1秒）
            return (time_diffs > 1.0).sum()
        return 0
```

### 案例2：自动导出插件

```python
class AutoExportPlugin(BasePlugin):
    """自动导出插件"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="auto_export",
            version="1.0.0",
            description="自动导出关键主题数据",
            author="Rose Team",
            requires_pandas=True,
            supported_hooks=[HookType.AFTER_LOAD]
        )
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_LOAD, self.auto_export_key_topics)
        self.key_topics = ['/gps/fix', '/imu/data', '/camera/image']  # 关键主题
        return True
    
    def auto_export_key_topics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """自动导出关键主题"""
        bag_path = context.get('bag_path')
        data_interface = self.get_data_interface()
        
        available_topics = data_interface.get_topics(bag_path)
        
        # 找到存在的关键主题
        export_topics = [t for t in self.key_topics if t in available_topics]
        
        if export_topics:
            # 自动导出到同名 CSV 文件
            output_dir = bag_path.parent / f"{bag_path.stem}_auto_export"
            output_dir.mkdir(exist_ok=True)
            
            for topic in export_topics:
                df = data_interface.get_dataframe(bag_path, topic)
                if df is not None:
                    output_file = output_dir / f"{topic.replace('/', '_')}.csv"
                    success = data_interface.export_to_csv(df, output_file)
                    if success:
                        logger.info(f"Auto-exported {topic} to {output_file}")
        
        return context
```

### 案例3：数据统计插件

```python
class StatisticsPlugin(BasePlugin):
    """数据统计插件"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="statistics",
            version="1.0.0",
            description="生成 bag 数据统计报告",
            author="Rose Team",
            requires_pandas=True,
            supported_hooks=[HookType.AFTER_LOAD]
        )
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_LOAD, self.generate_statistics)
        return True
    
    def generate_statistics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成统计报告"""
        bag_path = context.get('bag_path')
        data_interface = self.get_data_interface()
        
        stats = data_interface.get_bag_statistics(bag_path)
        topics = data_interface.get_topics(bag_path)
        
        report = {
            'bag_file': str(bag_path),
            'file_size_mb': stats.get('file_size_mb', 0),
            'total_topics': len(topics),
            'total_messages': stats.get('total_messages', 0),
            'duration_seconds': stats.get('duration_seconds', 0),
            'topics_with_dataframes': 0,
            'topic_details': {}
        }
        
        # 生成每个主题的详细统计
        for topic in topics:
            df = data_interface.get_dataframe(bag_path, topic)
            if df is not None:
                report['topics_with_dataframes'] += 1
                report['topic_details'][topic] = {
                    'message_count': len(df),
                    'columns': list(df.columns),
                    'memory_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
                }
        
        # 保存统计报告
        report_file = bag_path.parent / f"{bag_path.stem}_statistics.json"
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Statistics report saved to {report_file}")
        return context
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """提供统计相关命令"""
        return {
            "report": self.generate_report_command,
            "summary": self.show_summary_command
        }
    
    def generate_report_command(self, context: Dict[str, Any]) -> bool:
        """生成详细统计报告"""
        bag_path = context.get('bag_path')
        console = context.get('console')
        
        if not bag_path:
            if console:
                console.print("[red]需要指定 bag 文件路径[/red]")
            return False
        
        # 强制重新生成统计
        self.generate_statistics({'bag_path': bag_path})
        
        if console:
            console.print(f"[green]统计报告已生成[/green]")
        return True
```

## CLI 使用指南

### 基本插件管理

```bash
# 列出所有插件
rose plugin list

# 按类型过滤插件
rose plugin list --type hook     # 只显示钩子插件
rose plugin list --type script   # 只显示脚本插件

# 显示详细信息
rose plugin list --verbose

# 查看特定插件信息
rose plugin info my_plugin

# 启用/禁用插件
rose plugin enable my_plugin
rose plugin disable my_plugin
```

### 运行插件

#### 运行钩子插件命令

```bash
# 查看钩子插件提供的命令
rose plugin run my_hook_plugin

# 运行钩子插件的特定命令
rose plugin run my_hook_plugin analyze --bag demo.bag
rose plugin run my_hook_plugin process --bag demo.bag --topics gps --output result.csv
```

#### 运行脚本插件

```bash
# 运行脚本插件（直接执行）
rose plugin run my_script --bag demo.bag

# 运行脚本插件并指定参数
rose plugin run my_script --bag demo.bag --topics gps imu --output result.csv

# 运行数据分析脚本插件
rose plugin run analyzer --bag demo.bag --output analysis.json
```

### 创建和管理插件

```bash
# 创建钩子插件
rose plugin create my_hook_plugin --template basic
rose plugin create data_processor --template data_processor
rose plugin create hook_example --template hook_example

# 创建脚本插件
rose plugin create my_script --template script_basic
rose plugin create analyzer --template script_analyzer

# 从文件安装插件
rose plugin install /path/to/plugin.py --name custom_plugin

# 重新加载插件（开发时使用）
rose plugin reload my_plugin

# 卸载插件
rose plugin uninstall my_plugin
```

## 钩子开发最佳实践

### 1. 钩子函数设计

```python
def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    钩子函数最佳实践
    
    Args:
        context: 上下文字典，包含操作相关信息
        
    Returns:
        Dict: 修改后的上下文（必须返回）
    """
    try:
        # 1. 获取需要的参数
        bag_path = context.get('bag_path')
        operation = context.get('operation')
        
        # 2. 检查前置条件
        if not bag_path:
            logger.warning("No bag_path in context")
            return context
        
        # 3. 执行钩子逻辑
        result = self.process_logic(bag_path)
        
        # 4. 将结果添加到上下文
        if result:
            context['my_plugin_result'] = result
        
        # 5. 记录日志
        logger.info(f"Hook executed successfully for {operation}")
        
    except Exception as e:
        # 6. 错误处理（不要中断主流程）
        logger.error(f"Hook execution failed: {e}")
    
    # 7. 必须返回上下文
    return context
```

### 2. 错误处理

```python
def robust_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """健壮的钩子实现"""
    try:
        # 钩子逻辑...
        pass
    except Exception as e:
        # 记录错误但不中断主流程
        logger.error(f"Plugin {self.plugin_info.name} hook failed: {e}")
        
        # 可选：将错误信息添加到上下文
        if 'plugin_errors' not in context:
            context['plugin_errors'] = []
        context['plugin_errors'].append({
            'plugin': self.plugin_info.name,
            'error': str(e)
        })
    
    return context
```

### 3. 性能考虑

```python
def efficient_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """高效的钩子实现"""
    # 1. 快速检查是否需要执行
    if not self.should_process(context):
        return context
    
    # 2. 缓存重复计算
    cache_key = f"plugin_cache_{context.get('bag_path')}"
    if hasattr(self, cache_key):
        return context
    
    # 3. 异步处理长时间操作
    if self.is_long_running_operation():
        # 启动后台任务，不阻塞主流程
        self.start_background_task(context)
    else:
        # 同步快速处理
        self.quick_process(context)
    
    return context
```

## 调试和开发

### 启用调试日志

```bash
# 查看插件加载和执行日志
tail -f ~/.rose/logs/rose_tui.log | grep -E "(plugin|hook)"
```

### 开发工作流

1. **创建插件**：
   ```bash
   rose plugin create my_dev_plugin --template basic
   ```

2. **编辑插件文件**：
   ```bash
   # 插件文件位置
   ~/.rose/cache/plugins/my_dev_plugin.py
   ```

3. **重新加载测试**：
   ```bash
   rose plugin reload my_dev_plugin
   ```

4. **测试插件功能**：
   ```bash
   rose plugin run my_dev_plugin hello
   rose load demo.bag --verbose  # 测试钩子
   ```

### 常见问题

#### Q: 插件加载失败？
A: 检查：
- 插件文件语法是否正确
- 是否正确继承 `BasePlugin`
- 是否实现了必需的抽象方法
- 依赖库是否安装

#### Q: 钩子没有被调用？
A: 检查：
- 钩子是否在 `initialize()` 中正确注册
- 钩子类型是否正确
- 插件是否启用
- 钩子函数是否返回上下文

#### Q: 无法访问数据？
A: 检查：
- bag 文件是否已加载到缓存
- 是否需要 DataFrame 索引
- 数据接口是否正确初始化

## API 参考

### BasePlugin 类

| 方法 | 描述 |
|------|------|
| `plugin_info` | 插件元数据（抽象属性）|
| `initialize()` | 初始化插件（抽象方法）|
| `cleanup()` | 清理资源 |
| `register_hook(type, callback)` | 注册钩子 |
| `get_data_interface()` | 获取数据接口 |
| `get_cli_commands()` | 获取自定义命令 |
| `enable()` / `disable()` | 启用/禁用插件 |

### DataInterface 类

| 方法 | 描述 |
|------|------|
| `get_bag_info(path)` | 获取 bag 信息 |
| `get_topics(path)` | 获取主题列表 |
| `get_dataframe(path, topic)` | 获取主题 DataFrame |
| `get_multiple_dataframes(path, topics)` | 获取多个 DataFrame |
| `merge_dataframes(dataframes)` | 合并 DataFrame |
| `filter_dataframe(df, filters)` | 过滤 DataFrame |
| `export_to_csv(df, path)` | 导出为 CSV |
| `get_bag_statistics(path)` | 获取统计信息 |

### 钩子上下文

不同操作的上下文包含不同的参数：

#### LOAD 操作
```python
{
    'bag_path': Path,
    'operation': 'load',
    'verbose': bool,
    'build_index': bool,
    'bag_info': ComprehensiveBagInfo,  # after_load 钩子中可用
    'elapsed_time': float              # after_load 钩子中可用
}
```

#### EXPORT 操作
```python
{
    'bag_path': Path,
    'operation': 'export', 
    'topics': List[str],
    'output_path': str,
    'filters': Dict[str, Any],
    'bag_info': ComprehensiveBagInfo,
    'success': bool,        # after_export 钩子中可用
    'row_count': int,      # after_export 钩子中可用
    'column_count': int,   # after_export 钩子中可用
    'export_type': str     # 'single' 或 'stacked'
}
```

## 插件示例库

Rose 提供了多种插件模板：

### 钩子插件模板

#### 1. Basic Template (`basic`)
基础钩子插件模板，包含：
- 基本钩子插件结构
- 简单的钩子注册
- 示例 CLI 命令

#### 2. Data Processor Template (`data_processor`)
数据处理钩子插件模板，包含：
- 完整的数据处理流程
- 多种钩子使用示例
- 高级数据操作

#### 3. Hook Example Template (`hook_example`)
钩子示例模板，包含：
- 所有钩子类型的使用示例
- 钩子最佳实践
- 错误处理示例

### 脚本插件模板

#### 4. Script Basic Template (`script_basic`)
基础脚本插件模板，包含：
- 基本脚本插件结构
- Rose 函数访问示例
- 用户交互演示
- bag 文件加载和主题显示

#### 5. Script Analyzer Template (`script_analyzer`)
数据分析脚本插件模板，包含：
- 交互式主题选择
- 数值数据统计分析
- Rich 表格显示
- JSON 结果导出
- 完整的数据分析工作流

## 扩展建议

### 插件生态系统

建议的插件类型：

#### 钩子插件用途

1. **自动化处理插件**
   - 数据清洗和预处理
   - 自动备份和归档
   - 数据质量检查

2. **监控和通知插件** 
   - 操作日志记录
   - 错误监控和报警
   - 进度通知

3. **集成插件**
   - 第三方工具集成
   - API 接口调用
   - 数据库自动存储

#### 脚本插件用途

1. **数据分析脚本**
   - 统计分析和报告
   - 数据探索和可视化
   - 自定义计算和指标

2. **数据处理工具**
   - 格式转换工具
   - 数据合并和分割
   - 自定义导出格式

3. **交互式工具**
   - 数据查询界面
   - 参数配置工具
   - 批处理脚本

4. **专用分析器**
   - 传感器数据分析
   - 轨迹分析工具
   - 性能评估脚本

5. **开发辅助工具**
   - 数据验证脚本
   - 测试数据生成
   - 调试辅助工具

### 发布插件

1. **插件打包**：创建独立的 Python 文件
2. **文档编写**：包含使用说明和示例
3. **测试验证**：确保在不同环境下工作
4. **版本管理**：使用语义化版本号

## 总结

Rose 插件系统为用户提供了强大的扩展能力，支持两种互补的插件类型：

### 插件类型对比

| 特性 | 钩子插件 | 脚本插件 |
|------|---------|---------|
| **基类** | `BasePlugin` | `BaseScriptPlugin` |
| **执行方式** | 自动触发 | 手动执行 |
| **数据访问** | `DataInterface` | `ScriptContext` |
| **用户交互** | 后台运行 | 支持交互 |
| **适用场景** | 自动化工作流 | 数据分析脚本 |
| **开发复杂度** | 中等 | 简单 |

### 开发指南要点

#### 钩子插件开发
- 🎯 **专注单一功能**：保持插件简单和专注
- 🛡️ **错误处理**：确保插件不会中断主流程
- ⚡ **性能优化**：考虑内存使用和执行效率
- 🔗 **钩子选择**：选择合适的钩子时机

#### 脚本插件开发
- 🚀 **用户友好**：提供清晰的交互界面
- 📊 **数据处理**：充分利用 ScriptContext 功能
- 💬 **交互设计**：合理使用用户输入和确认
- 📈 **结果展示**：使用 Rich 格式化输出

### 通用最佳实践
- 📚 **良好文档**：提供清晰的使用说明和示例
- 🧪 **充分测试**：确保插件在各种场景下正常工作
- 🔧 **模板使用**：基于官方模板快速开发
- 🎨 **代码质量**：遵循 Python 编码规范

### 功能特色

通过 Rose 插件系统，你可以：
- 🔌 **扩展 Rose 功能**：无需修改核心代码
- ⚡ **提高工作效率**：自动化重复任务
- 📊 **定制数据处理**：实现专用分析工具
- 🤝 **分享解决方案**：与社区共享插件
- 🛠️ **灵活选择**：根据需求选择钩子或脚本插件
- 🎯 **精确控制**：细粒度的数据访问和操作

---

插件系统的设计确保了高性能、易用性和可扩展性。开始创建你的插件，让 Rose 更加强大！🚀
