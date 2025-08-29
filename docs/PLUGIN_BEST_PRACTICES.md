# Rose 插件开发最佳实践

## 插件设计原则

### 1. 单一职责原则
每个插件应该专注于一个特定的功能：

```python
# ✅ 好的设计 - 专注于 GPS 数据分析
class GPSAnalyzerPlugin(BasePlugin):
    def analyze_gps_quality(self, df): pass
    def detect_gps_anomalies(self, df): pass
    def calculate_gps_metrics(self, df): pass

# ❌ 不好的设计 - 功能过于复杂
class SuperPlugin(BasePlugin):
    def analyze_gps(self): pass
    def process_images(self): pass
    def export_to_database(self): pass
    def send_emails(self): pass
```

### 2. 错误处理和容错性

```python
def robust_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """健壮的钩子实现"""
    try:
        # 主要逻辑
        result = self.process_data(context)
        context['my_plugin_result'] = result
        
    except Exception as e:
        # 记录错误但不中断主流程
        logger.error(f"Plugin {self.plugin_info.name} failed: {e}")
        
        # 可选：提供降级功能
        context['my_plugin_result'] = self.fallback_processing(context)
    
    # 总是返回上下文
    return context
```

### 3. 性能考虑

```python
class PerformantPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._cache = {}  # 本地缓存
    
    def efficient_processing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        bag_path = context.get('bag_path')
        
        # 使用缓存避免重复计算
        cache_key = str(bag_path)
        if cache_key in self._cache:
            context['cached_result'] = self._cache[cache_key]
            return context
        
        # 只在需要时进行昂贵的计算
        if self.should_process(context):
            result = self.expensive_calculation(context)
            self._cache[cache_key] = result
            context['result'] = result
        
        return context
    
    def should_process(self, context: Dict[str, Any]) -> bool:
        """检查是否需要处理"""
        # 基于文件大小、主题数量等条件决定
        bag_path = context.get('bag_path')
        return bag_path and bag_path.stat().st_size > 1024 * 1024  # 只处理 > 1MB 的文件
```

## 数据访问最佳实践

### 1. 安全的数据访问

```python
def safe_data_access(self, bag_path: Path, topic: str):
    """安全的数据访问模式"""
    data_interface = self.get_data_interface()
    
    # 1. 检查 bag 是否在缓存中
    if not data_interface.is_bag_cached(bag_path):
        logger.warning(f"Bag {bag_path} not in cache")
        return None
    
    # 2. 检查是否有 DataFrame
    if not data_interface.has_dataframes(bag_path):
        logger.warning(f"No DataFrames available for {bag_path}")
        return None
    
    # 3. 检查主题是否存在
    available_topics = data_interface.get_topics(bag_path)
    if topic not in available_topics:
        logger.warning(f"Topic {topic} not found in {bag_path}")
        return None
    
    # 4. 安全获取数据
    df = data_interface.get_dataframe(bag_path, topic)
    return df
```

### 2. 高效的批量处理

```python
def batch_processing(self, bag_path: Path, topics: List[str]):
    """高效的批量数据处理"""
    data_interface = self.get_data_interface()
    
    # 一次获取所有需要的 DataFrame
    dataframes = data_interface.get_multiple_dataframes(bag_path, topics)
    
    # 批量处理
    results = {}
    for topic, df in dataframes.items():
        if df is not None:
            results[topic] = self.process_single_dataframe(df)
    
    return results
```

### 3. 内存管理

```python
def memory_efficient_processing(self, bag_path: Path):
    """内存高效的数据处理"""
    data_interface = self.get_data_interface()
    topics = data_interface.get_topics(bag_path)
    
    # 逐个处理主题，避免同时加载所有数据
    for topic in topics:
        df = data_interface.get_dataframe(bag_path, topic)
        if df is not None:
            # 处理数据
            result = self.process_dataframe(df)
            
            # 立即保存结果，释放内存
            self.save_result(topic, result)
            
            # 显式删除 DataFrame 引用
            del df
```

## CLI 命令最佳实践

### 1. 用户友好的命令接口

```python
def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
    return {
        "analyze": self.analyze_command,
        "export": self.export_command,
        "report": self.report_command
    }

def analyze_command(self, context: Dict[str, Any]) -> bool:
    """用户友好的分析命令"""
    bag_path = context.get('bag_path')
    topics = context.get('topics', [])
    console = context.get('console')
    
    # 1. 参数验证
    if not bag_path:
        if console:
            console.print("[red]❌ 错误: 需要指定 bag 文件路径[/red]")
            console.print("[yellow]💡 使用方法: rose plugin run my_plugin analyze --bag demo.bag[/yellow]")
        return False
    
    # 2. 进度指示
    if console:
        console.print(f"[cyan]🔍 正在分析 {bag_path}...[/cyan]")
    
    # 3. 执行分析
    try:
        result = self.perform_analysis(bag_path, topics)
        
        # 4. 显示结果
        if console:
            console.print(f"[green]✅ 分析完成![/green]")
            self.display_results(result, console)
        
        return True
        
    except Exception as e:
        if console:
            console.print(f"[red]❌ 分析失败: {e}[/red]")
        return False
```

### 2. 丰富的输出格式

```python
def display_results(self, results: Dict[str, Any], console):
    """丰富的结果显示"""
    from rich.table import Table
    from rich.panel import Panel
    
    # 创建结果表格
    table = Table(title="分析结果")
    table.add_column("主题", style="cyan")
    table.add_column("消息数", justify="right")
    table.add_column("质量评分", style="green")
    table.add_column("问题", style="red")
    
    for topic, data in results.items():
        table.add_row(
            topic,
            str(data.get('message_count', 0)),
            f"{data.get('quality_score', 0):.1f}/10",
            data.get('issues', 'None')
        )
    
    # 显示表格
    console.print(table)
    
    # 显示摘要面板
    summary = Panel(
        f"总计分析了 {len(results)} 个主题\n"
        f"平均质量评分: {self.calculate_average_score(results):.1f}/10",
        title="📊 分析摘要",
        border_style="green"
    )
    console.print(summary)
```

## 钩子开发模式

### 1. 观察者模式

```python
class ObserverPlugin(BasePlugin):
    """观察者模式插件"""
    
    def initialize(self) -> bool:
        # 观察多个操作
        self.register_hook(HookType.AFTER_LOAD, self.on_data_change)
        self.register_hook(HookType.AFTER_EXTRACT, self.on_data_change)
        self.register_hook(HookType.AFTER_EXPORT, self.on_data_change)
        return True
    
    def on_data_change(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """统一的数据变化处理"""
        operation = context.get('operation')
        bag_path = context.get('bag_path')
        
        # 记录数据变化事件
        self.log_data_event(operation, bag_path)
        
        # 更新统计信息
        self.update_statistics(context)
        
        return context
```

### 2. 装饰器模式

```python
class DecoratorPlugin(BasePlugin):
    """装饰器模式插件 - 增强现有功能"""
    
    def initialize(self) -> bool:
        self.register_hook(HookType.BEFORE_EXPORT, self.enhance_export)
        return True
    
    def enhance_export(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """增强导出功能"""
        topics = context.get('topics', [])
        
        # 自动添加时间戳列
        context['enhanced_export'] = True
        context['add_timestamp_column'] = True
        
        # 自动过滤无效数据
        context['filter_invalid_data'] = True
        
        logger.info(f"Enhanced export for {len(topics)} topics")
        return context
```

### 3. 责任链模式

```python
class ChainPlugin(BasePlugin):
    """责任链模式 - 数据处理链"""
    
    def initialize(self) -> bool:
        self.register_hook(HookType.BEFORE_EXPORT, self.process_chain)
        return True
    
    def process_chain(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """数据处理责任链"""
        bag_path = context.get('bag_path')
        topics = context.get('topics', [])
        
        data_interface = self.get_data_interface()
        
        for topic in topics:
            df = data_interface.get_dataframe(bag_path, topic)
            if df is not None:
                # 处理链：清洗 -> 验证 -> 转换 -> 增强
                df = self.clean_data(df)
                df = self.validate_data(df)
                df = self.transform_data(df)
                df = self.enhance_data(df)
                
                # 将处理后的数据放回上下文
                context[f'processed_{topic}'] = df
        
        return context
```

## 测试和调试

### 1. 插件单元测试

```python
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

class TestMyPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = MyPlugin()
        self.plugin.initialize()
        
        # 模拟数据接口
        self.mock_data_interface = Mock()
        self.plugin.set_data_interface(self.mock_data_interface)
    
    def test_hook_execution(self):
        """测试钩子执行"""
        context = {
            'bag_path': Path('test.bag'),
            'operation': 'load'
        }
        
        result = self.plugin.on_bag_loaded(context)
        
        self.assertIn('my_plugin_result', result)
        self.assertTrue(result['my_plugin_result'])
    
    def test_cli_command(self):
        """测试 CLI 命令"""
        context = {
            'bag_path': Path('test.bag'),
            'console': Mock()
        }
        
        success = self.plugin.analyze_command(context)
        self.assertTrue(success)
```

### 2. 调试技巧

```python
class DebuggablePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.debug = True  # 开发时启用调试
    
    def debug_log(self, message: str, data: Any = None):
        """调试日志"""
        if self.debug:
            logger.debug(f"[{self.plugin_info.name}] {message}")
            if data:
                logger.debug(f"[{self.plugin_info.name}] Data: {data}")
    
    def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.debug_log("Hook started", context.keys())
        
        # 处理逻辑...
        
        self.debug_log("Hook completed")
        return context
```

### 3. 性能监控

```python
import time
from functools import wraps

def monitor_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(self, context: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        
        result = func(self, context)
        
        elapsed = time.time() - start_time
        logger.info(f"Plugin {self.plugin_info.name} hook {func.__name__} took {elapsed:.3f}s")
        
        return result
    return wrapper

class MonitoredPlugin(BasePlugin):
    @monitor_performance
    def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 钩子逻辑...
        return context
```

## 插件配置管理

### 1. 配置文件支持

```python
class ConfigurablePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载插件配置"""
        from ..core.directories import get_rose_directories
        
        rose_dirs = get_rose_directories()
        config_file = rose_dirs.config_dir / f'{self.plugin_info.name}.json'
        
        default_config = {
            'enabled': True,
            'auto_export': False,
            'output_format': 'csv',
            'max_file_size_mb': 100
        }
        
        if config_file.exists():
            import json
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        from ..core.directories import get_rose_directories
        
        rose_dirs = get_rose_directories()
        config_file = rose_dirs.config_dir / f'{self.plugin_info.name}.json'
        
        import json
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
```

### 2. 环境变量支持

```python
class EnvConfigPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.load_env_config()
    
    def load_env_config(self):
        """从环境变量加载配置"""
        import os
        
        self.config = {
            'debug': os.getenv('ROSE_PLUGIN_DEBUG', 'false').lower() == 'true',
            'output_dir': os.getenv('ROSE_PLUGIN_OUTPUT_DIR', '/tmp'),
            'max_workers': int(os.getenv('ROSE_PLUGIN_WORKERS', '4')),
        }
```

## 插件发布和分享

### 1. 插件包结构

```
my_awesome_plugin/
├── plugin.py              # 主插件文件
├── config.json           # 默认配置
├── README.md             # 使用说明
├── requirements.txt      # 依赖列表
└── examples/            # 使用示例
    ├── basic_usage.py
    └── advanced_usage.py
```

### 2. 插件元数据

```python
@property
def plugin_info(self) -> PluginInfo:
    return PluginInfo(
        name="my_awesome_plugin",
        version="2.1.0",  # 语义化版本
        description="一个很棒的 Rose 数据处理插件",
        author="Your Name <your.email@example.com>",
        homepage="https://github.com/username/rose-awesome-plugin",
        requires_pandas=True,
        requires_cache=True,
        supported_hooks=[
            HookType.AFTER_LOAD,
            HookType.BEFORE_EXPORT,
            HookType.AFTER_EXPORT
        ]
    )
```

### 3. 插件文档

在插件文件中包含详细的文档：

```python
class DocumentedPlugin(BasePlugin):
    """
    我的文档化插件
    
    这个插件提供以下功能：
    1. 自动数据质量检查
    2. 智能数据过滤
    3. 自定义格式导出
    
    使用方法：
    - rose plugin run my_plugin analyze --bag demo.bag
    - rose plugin run my_plugin export --bag demo.bag --topics gps
    
    配置选项：
    - auto_check: 是否自动检查数据质量
    - export_format: 默认导出格式 (csv, json, parquet)
    """
    
    def analyze_command(self, context: Dict[str, Any]) -> bool:
        """
        分析 bag 文件数据质量
        
        参数:
            bag_path: bag 文件路径
            topics: 要分析的主题列表（可选）
            
        返回:
            bool: 分析是否成功
            
        示例:
            rose plugin run my_plugin analyze --bag demo.bag --topics gps imu
        """
        # 实现逻辑...
        pass
```

## 常见使用场景

### 1. 数据验证插件

```python
class ValidationPlugin(BasePlugin):
    """数据验证插件"""
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_LOAD, self.validate_data)
        return True
    
    def validate_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """验证加载的数据"""
        bag_path = context.get('bag_path')
        data_interface = self.get_data_interface()
        
        validation_results = {}
        topics = data_interface.get_topics(bag_path)
        
        for topic in topics:
            df = data_interface.get_dataframe(bag_path, topic)
            if df is not None:
                validation_results[topic] = {
                    'has_nulls': df.isnull().any().any(),
                    'has_duplicates': df.duplicated().any(),
                    'time_ordered': self.is_time_ordered(df),
                    'valid_ranges': self.check_value_ranges(df)
                }
        
        # 生成验证报告
        self.generate_validation_report(validation_results)
        context['validation_results'] = validation_results
        
        return context
```

### 2. 自动备份插件

```python
class BackupPlugin(BasePlugin):
    """自动备份插件"""
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_EXPORT, self.backup_export)
        return True
    
    def backup_export(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """自动备份导出的文件"""
        output_path = context.get('output_path')
        success = context.get('success', False)
        
        if success and output_path:
            backup_dir = Path.home() / '.rose' / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            import shutil
            import datetime
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f"{Path(output_path).stem}_{timestamp}.csv"
            
            shutil.copy2(output_path, backup_file)
            logger.info(f"Auto backup created: {backup_file}")
        
        return context
```

### 3. 通知插件

```python
class NotificationPlugin(BasePlugin):
    """通知插件"""
    
    def initialize(self) -> bool:
        self.register_hook(HookType.AFTER_EXPORT, self.send_notification)
        return True
    
    def send_notification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """发送完成通知"""
        success = context.get('success', False)
        output_path = context.get('output_path')
        row_count = context.get('row_count', 0)
        
        if success:
            message = f"✅ 数据导出完成!\n文件: {output_path}\n行数: {row_count}"
            
            # 发送桌面通知
            self.send_desktop_notification(message)
            
            # 发送邮件通知（如果配置了）
            if self.config.get('email_notifications'):
                self.send_email_notification(message)
        
        return context
    
    def send_desktop_notification(self, message: str):
        """发送桌面通知"""
        try:
            import subprocess
            subprocess.run(['notify-send', 'Rose', message], check=False)
        except Exception:
            pass  # 静默失败
```

## 部署和分发

### 1. 插件打包

```bash
# 创建插件包
mkdir my_plugin_package
cp my_plugin.py my_plugin_package/
cp config.json my_plugin_package/
cp README.md my_plugin_package/

# 创建安装脚本
cat > my_plugin_package/install.sh << 'EOF'
#!/bin/bash
PLUGIN_DIR="$HOME/.rose/cache/plugins"
mkdir -p "$PLUGIN_DIR"
cp plugin.py "$PLUGIN_DIR/my_plugin.py"
echo "Plugin installed successfully!"
EOF

chmod +x my_plugin_package/install.sh
```

### 2. 版本兼容性

```python
class VersionCompatiblePlugin(BasePlugin):
    def validate_requirements(self) -> bool:
        """检查版本兼容性"""
        if not super().validate_requirements():
            return False
        
        # 检查 Rose 版本
        try:
            from .. import __version__ as rose_version
            if rose_version < "2.0.0":
                logger.error("This plugin requires Rose >= 2.0.0")
                return False
        except ImportError:
            logger.warning("Cannot determine Rose version")
        
        return True
```

## 总结

Rose 插件系统为用户提供了强大的扩展能力。通过遵循这些最佳实践，你可以开发出高质量、高性能的插件，为 Rose 生态系统做出贡献。

关键要点：
- 🎯 **专注单一功能**：保持插件简单和专注
- 🛡️ **错误处理**：确保插件不会中断主流程
- ⚡ **性能优化**：考虑内存使用和执行效率
- 📚 **良好文档**：提供清晰的使用说明
- 🧪 **充分测试**：确保插件在各种场景下正常工作

开始创建你的插件，让 Rose 更加强大！🚀
