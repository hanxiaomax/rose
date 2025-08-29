# Rose 插件 API 参考

## BasePlugin 类

### 抽象方法（必须实现）

#### `plugin_info` (属性)
```python
@property
def plugin_info(self) -> PluginInfo:
    return PluginInfo(
        name="plugin_name",
        version="1.0.0",
        description="插件描述",
        author="作者名",
        homepage="https://github.com/user/plugin",  # 可选
        requires_pandas=False,  # 是否需要 pandas
        requires_cache=True,    # 是否需要缓存
        supported_hooks=[HookType.AFTER_LOAD]  # 支持的钩子
    )
```

#### `initialize()` 方法
```python
def initialize(self) -> bool:
    """
    初始化插件
    
    Returns:
        bool: True 表示初始化成功，False 表示失败
    """
    # 注册钩子
    self.register_hook(HookType.AFTER_LOAD, self.my_hook)
    return True
```

### 可选方法

#### `cleanup()` 方法
```python
def cleanup(self) -> None:
    """清理插件资源"""
    # 清理临时文件、关闭连接等
    pass
```

#### `get_cli_commands()` 方法
```python
def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
    """
    返回插件提供的 CLI 命令
    
    Returns:
        Dict[str, Callable]: 命令名到函数的映射，或 None
    """
    return {
        "analyze": self.analyze_command,
        "export": self.export_command
    }
```

#### 钩子方法
```python
def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    钩子处理函数
    
    Args:
        context: 操作上下文字典
        
    Returns:
        Dict[str, Any]: 修改后的上下文（必须返回）
    """
    # 钩子逻辑
    return context
```

### 内置方法

#### `register_hook()`
```python
def register_hook(self, hook_type: HookType, callback: Callable) -> None:
    """
    注册钩子回调函数
    
    Args:
        hook_type: 钩子类型
        callback: 回调函数
    """
```

#### `get_data_interface()`
```python
def get_data_interface(self) -> Optional[DataInterface]:
    """获取数据访问接口"""
```

#### `enable()` / `disable()`
```python
def enable(self) -> None:
    """启用插件"""

def disable(self) -> None:
    """禁用插件"""
```

#### `is_enabled()`
```python
def is_enabled(self) -> bool:
    """检查插件是否启用"""
```

## DataInterface 类

### Bag 信息访问

#### `get_bag_info()`
```python
def get_bag_info(self, bag_path: Union[str, Path]) -> Optional[ComprehensiveBagInfo]:
    """
    获取 bag 文件的完整信息
    
    Args:
        bag_path: bag 文件路径
        
    Returns:
        ComprehensiveBagInfo: bag 信息对象，如果不在缓存中则返回 None
    """
```

#### `is_bag_cached()`
```python
def is_bag_cached(self, bag_path: Union[str, Path]) -> bool:
    """检查 bag 文件是否在缓存中"""
```

#### `has_dataframes()`
```python
def has_dataframes(self, bag_path: Union[str, Path]) -> bool:
    """检查 bag 文件是否有 DataFrame 索引"""
```

#### `get_bag_statistics()`
```python
def get_bag_statistics(self, bag_path: Union[str, Path]) -> Dict[str, Any]:
    """
    获取 bag 文件统计信息
    
    Returns:
        Dict 包含:
        - file_path: 文件路径
        - file_size_mb: 文件大小（MB）
        - total_messages: 总消息数
        - duration_seconds: 持续时间（秒）
        - topics_count: 主题数量
        - time_range: 时间范围
        - has_dataframes: 是否有 DataFrame
    """
```

### 主题信息访问

#### `get_topics()`
```python
def get_topics(self, bag_path: Union[str, Path]) -> List[str]:
    """
    获取 bag 文件中的所有主题名称
    
    Returns:
        List[str]: 主题名称列表
    """
```

#### `get_topic_info()`
```python
def get_topic_info(self, bag_path: Union[str, Path], topic_name: str) -> Optional[TopicInfo]:
    """
    获取特定主题的详细信息
    
    Returns:
        TopicInfo: 主题信息对象，包含消息类型、数量等
    """
```

#### `filter_topics()`
```python
def filter_topics(self, bag_path: Union[str, Path], patterns: List[str]) -> List[str]:
    """
    使用模式过滤主题
    
    Args:
        patterns: 主题名称模式列表（支持模糊匹配）
        
    Returns:
        List[str]: 匹配的主题名称
    """
```

### DataFrame 数据访问

#### `get_dataframe()`
```python
def get_dataframe(self, bag_path: Union[str, Path], topic_name: str) -> Any:
    """
    获取特定主题的 DataFrame
    
    Returns:
        pandas.DataFrame: 主题数据，如果不可用则返回 None
    """
```

#### `get_multiple_dataframes()`
```python
def get_multiple_dataframes(self, bag_path: Union[str, Path], topic_names: List[str]) -> Dict[str, Any]:
    """
    获取多个主题的 DataFrame
    
    Returns:
        Dict[str, pandas.DataFrame]: 主题名到 DataFrame 的映射
    """
```

### 数据处理

#### `merge_dataframes()`
```python
def merge_dataframes(self, dataframes: Dict[str, Any]) -> Any:
    """
    按时间戳合并多个 DataFrame
    
    Args:
        dataframes: 主题名到 DataFrame 的映射
        
    Returns:
        pandas.DataFrame: 合并后的 DataFrame
    """
```

#### `filter_dataframe()`
```python
def filter_dataframe(self, df: Any, filters: Dict[str, Any]) -> Any:
    """
    对 DataFrame 应用过滤器
    
    Args:
        df: 要过滤的 DataFrame
        filters: 过滤条件字典
            - start_time: 开始时间
            - end_time: 结束时间  
            - search_text: 搜索文本
            - column_filters: 列过滤条件
            
    Returns:
        pandas.DataFrame: 过滤后的 DataFrame
    """
```

### 数据导出

#### `export_to_csv()`
```python
def export_to_csv(self, df: Any, output_path: Union[str, Path], include_index: bool = True) -> bool:
    """
    导出 DataFrame 为 CSV 文件
    
    Args:
        df: 要导出的 DataFrame
        output_path: 输出文件路径
        include_index: 是否包含索引
        
    Returns:
        bool: 导出是否成功
    """
```

## HookType 枚举

### 可用的钩子类型

```python
class HookType(Enum):
    BEFORE_LOAD = "before_load"        # 加载前
    AFTER_LOAD = "after_load"          # 加载后
    BEFORE_INSPECT = "before_inspect"  # 检查前
    AFTER_INSPECT = "after_inspect"    # 检查后
    BEFORE_EXTRACT = "before_extract"  # 提取前
    AFTER_EXTRACT = "after_extract"    # 提取后
    BEFORE_EXPORT = "before_export"    # 导出前
    AFTER_EXPORT = "after_export"      # 导出后
    BEFORE_COMPRESS = "before_compress" # 压缩前
    AFTER_COMPRESS = "after_compress"   # 压缩后
```

## PluginInfo 类

### 插件元数据

```python
@dataclass
class PluginInfo:
    name: str                           # 插件名称（必需）
    version: str                        # 版本号（必需）
    description: str                    # 描述（必需）
    author: str                         # 作者（必需）
    homepage: Optional[str] = None      # 主页 URL
    requires_pandas: bool = False       # 是否需要 pandas
    requires_cache: bool = True         # 是否需要缓存
    supported_hooks: List[HookType] = None  # 支持的钩子列表
```

## 上下文数据结构

### 通用上下文

所有钩子都会收到的基础上下文：

```python
{
    'bag_path': Path,                    # bag 文件路径
    'operation': str,                    # 操作名称
    'data_interface': DataInterface,     # 数据接口
    'parameters': dict,                  # 操作参数
    'plugin_manager': PluginManager      # 插件管理器
}
```

### LOAD 操作上下文

```python
{
    # 基础上下文 +
    'verbose': bool,                     # 详细输出
    'build_index': bool,                 # 是否构建索引
    'bag_info': ComprehensiveBagInfo,    # bag 信息（after_load）
    'elapsed_time': float                # 加载耗时（after_load）
}
```

### EXPORT 操作上下文

```python
{
    # 基础上下文 +
    'topics': List[str],                 # 导出的主题
    'output_path': str,                  # 输出文件路径
    'filters': Dict[str, Any],           # 过滤条件
    'bag_info': ComprehensiveBagInfo,    # bag 信息
    'success': bool,                     # 导出是否成功（after_export）
    'row_count': int,                    # 导出行数（after_export）
    'column_count': int,                 # 列数（after_export）
    'export_type': str                   # 导出类型：'single' 或 'stacked'
}
```

### EXTRACT 操作上下文

```python
{
    # 基础上下文 +
    'topics': List[str],                 # 提取的主题
    'output_format': str,                # 输出格式
    'output_path': str,                  # 输出路径
    'extracted_files': List[str]         # 提取的文件列表（after_extract）
}
```

## CLI 命令函数签名

### 命令函数接口

```python
def my_command(self, context: Dict[str, Any]) -> bool:
    """
    插件 CLI 命令函数
    
    Args:
        context: 命令上下文，包含：
            - bag_path: bag 文件路径（可选）
            - topics: 主题列表（可选）
            - output: 输出路径（可选）
            - console: Rich Console 对象
            
    Returns:
        bool: 命令执行是否成功
    """
    bag_path = context.get('bag_path')
    topics = context.get('topics', [])
    output = context.get('output')
    console = context.get('console')
    
    # 命令逻辑...
    
    return True  # 成功
```

## 错误处理

### 异常类型

```python
class PluginError(Exception):
    """插件基础异常"""
    pass

class PluginLoadError(PluginError):
    """插件加载失败"""
    pass

class PluginValidationError(PluginError):
    """插件验证失败"""
    pass
```

### 错误处理最佳实践

```python
def safe_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 钩子逻辑
        result = self.process(context)
        context['result'] = result
        
    except PluginError as e:
        # 插件特定错误
        logger.error(f"Plugin error in {self.plugin_info.name}: {e}")
        
    except Exception as e:
        # 未预期的错误
        logger.error(f"Unexpected error in {self.plugin_info.name}: {e}")
        
    finally:
        # 清理工作
        self.cleanup_temp_resources()
    
    return context
```

## 日志记录

### 推荐的日志模式

```python
import logging

logger = logging.getLogger(__name__)

class MyPlugin(BasePlugin):
    def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        bag_path = context.get('bag_path')
        
        # 信息日志
        logger.info(f"Processing {bag_path} with {self.plugin_info.name}")
        
        # 调试日志
        logger.debug(f"Context keys: {list(context.keys())}")
        
        # 警告日志
        if not self.validate_input(context):
            logger.warning("Invalid input detected, using defaults")
        
        # 错误日志
        try:
            result = self.process(context)
        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
        
        return context
```

## 配置管理 API

### 推荐的配置模式

```python
class ConfigurablePlugin(BasePlugin):
    DEFAULT_CONFIG = {
        'enabled': True,
        'auto_process': False,
        'output_format': 'csv',
        'max_file_size': 100  # MB
    }
    
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        import json
        from ..core.directories import get_rose_directories
        
        config_file = get_rose_directories().config_dir / f'{self.plugin_info.name}.json'
        config = self.DEFAULT_CONFIG.copy()
        
        if config_file.exists():
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                config.update(user_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        
        return config
    
    def save_config(self):
        """保存配置"""
        import json
        from ..core.directories import get_rose_directories
        
        config_file = get_rose_directories().config_dir / f'{self.plugin_info.name}.json'
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
```

## 实用工具函数

### 时间处理

```python
def parse_time_filter(time_str: str) -> float:
    """解析时间过滤器字符串"""
    try:
        # 尝试解析为浮点数（秒）
        return float(time_str)
    except ValueError:
        # 尝试解析为 ISO 格式
        import pandas as pd
        return pd.to_datetime(time_str).timestamp()
```

### 文件处理

```python
def safe_file_operation(self, file_path: Path, operation: str):
    """安全的文件操作"""
    try:
        if operation == 'read':
            return file_path.read_text()
        elif operation == 'write':
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # 写入逻辑...
    except PermissionError:
        logger.error(f"Permission denied: {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except Exception as e:
        logger.error(f"File operation failed: {e}")
```

### 数据验证

```python
def validate_dataframe(self, df, required_columns: List[str] = None) -> bool:
    """验证 DataFrame"""
    if df is None or len(df) == 0:
        return False
    
    if required_columns:
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            logger.warning(f"Missing required columns: {missing_cols}")
            return False
    
    return True
```

## 插件生命周期

### 1. 发现阶段
- 扫描 `~/.rose/cache/plugins/` 目录
- 查找 `.py` 文件和包含 `__init__.py` 的目录

### 2. 加载阶段
- 动态导入 Python 模块
- 查找继承自 `BasePlugin` 的类
- 创建插件实例

### 3. 验证阶段
- 检查插件依赖（pandas、cache 等）
- 调用 `validate_requirements()`
- 验证插件元数据

### 4. 初始化阶段
- 调用插件的 `initialize()` 方法
- 注册插件提供的钩子
- 设置数据接口

### 5. 运行阶段
- 响应钩子调用
- 执行 CLI 命令
- 处理数据请求

### 6. 清理阶段
- 调用 `cleanup()` 方法
- 注销钩子
- 释放资源

## 版本兼容性

### 插件版本声明

```python
# 在插件文件顶部声明兼容性
"""
Rose Plugin: My Awesome Plugin
Compatible with: Rose >= 2.0.0
Requires: pandas >= 1.3.0
"""

class MyPlugin(BasePlugin):
    def validate_requirements(self) -> bool:
        """检查版本兼容性"""
        if not super().validate_requirements():
            return False
        
        # 检查 Rose 版本
        try:
            from .. import __version__
            import pkg_resources
            
            if pkg_resources.parse_version(__version__) < pkg_resources.parse_version("2.0.0"):
                logger.error("This plugin requires Rose >= 2.0.0")
                return False
        except ImportError:
            logger.warning("Cannot verify Rose version")
        
        return True
```

## 调试和开发

### 开发模式插件

```python
class DevelopmentPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.debug_mode = True
    
    def debug_print(self, message: str, data: Any = None):
        """调试输出"""
        if self.debug_mode:
            print(f"[DEBUG {self.plugin_info.name}] {message}")
            if data:
                print(f"[DEBUG {self.plugin_info.name}] Data: {data}")
    
    def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.debug_print("Hook started", context.keys())
        
        # 处理逻辑...
        
        self.debug_print("Hook completed")
        return context
```

### 性能分析

```python
import time
from functools import wraps

def profile_hook(func):
    """钩子性能分析装饰器"""
    @wraps(func)
    def wrapper(self, context: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.perf_counter()
        
        result = func(self, context)
        
        elapsed = time.perf_counter() - start_time
        logger.info(f"Hook {func.__name__} took {elapsed:.3f}s")
        
        return result
    return wrapper

class ProfiledPlugin(BasePlugin):
    @profile_hook
    def my_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 钩子逻辑...
        return context
```

这个 API 参考提供了开发 Rose 插件所需的所有接口和方法。配合完整文档和最佳实践指南，你可以开发出功能强大且稳定的插件。
