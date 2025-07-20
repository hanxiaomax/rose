# Util 模块使用指南

## 概述

Util 模块提供了Rose的核心工具函数集合，包括时间转换、日志管理、压缩验证、应用模式控制等基础功能，为整个系统提供通用的工具支持。

## 主要特性

- ✅ **时间工具**: ROS时间戳与标准时间的转换
- ✅ **日志系统**: 结构化日志记录和管理
- ✅ **压缩支持**: 压缩格式检测和验证
- ✅ **应用模式**: CLI/TUI/Web模式管理
- ✅ **文件操作**: 安全的文件和目录操作
- ✅ **性能监控**: 执行时间测量和性能分析

## 核心类型

### AppMode (枚举)

```python
class AppMode(Enum):
    CLI = "cli"         # 命令行模式
    TUI = "tui"         # 终端UI模式
    WEB = "web"         # Web界面模式
    LIBRARY = "library" # 库模式
```

### TimeUtil (工具类)

```python
class TimeUtil:
    @staticmethod
    def ros_to_unix(ros_time: float) -> float:
        """ROS时间戳转Unix时间戳"""
    
    @staticmethod
    def unix_to_ros(unix_time: float) -> float:
        """Unix时间戳转ROS时间戳"""
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化持续时间为人类可读格式"""
    
    @staticmethod
    def parse_time_range(time_str: str) -> Tuple[float, float]:
        """解析时间范围字符串"""
```

### PerformanceMonitor (性能监控)

```python
class PerformanceMonitor:
    def __init__(self, name: str):
        self.name = name
        
    def __enter__(self):
        """进入上下文，开始计时"""
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，记录耗时"""
        
    @staticmethod
    def measure_memory() -> Dict[str, float]:
        """测量内存使用情况"""
```

## 主要接口

### 时间转换函数

```python
def ros_time_to_datetime(ros_time: float) -> datetime:
    """ROS时间转datetime对象"""

def datetime_to_ros_time(dt: datetime) -> float:
    """datetime对象转ROS时间"""

def format_ros_time(ros_time: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化ROS时间为字符串"""
```

### 日志管理函数

```python
def get_logger(name: str = "rose") -> logging.Logger:
    """获取配置好的日志器"""

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """设置日志系统"""

def log_performance(func_name: str, duration: float, **kwargs) -> None:
    """记录性能日志"""
```

### 应用模式管理

```python
def set_app_mode(mode: AppMode) -> None:
    """设置应用运行模式"""

def get_app_mode() -> AppMode:
    """获取当前应用模式"""

def is_cli_mode() -> bool:
    """检查是否为CLI模式"""

def is_tui_mode() -> bool:
    """检查是否为TUI模式"""
```

### 压缩工具函数

```python
def get_available_compression_types() -> List[str]:
    """获取可用的压缩格式列表"""

def validate_compression_type(compression: str) -> Tuple[bool, str]:
    """验证压缩格式是否支持"""

def detect_compression_from_file(file_path: str) -> str:
    """从文件检测压缩格式"""
```

## 使用示例

### 时间转换工具

```python
from datetime import datetime
from roseApp.core.util import TimeUtil, ros_time_to_datetime, format_ros_time

# ROS时间戳转换
ros_timestamp = 1640995200.123456  # ROS时间戳
unix_timestamp = TimeUtil.ros_to_unix(ros_timestamp)
print(f"Unix时间戳: {unix_timestamp}")

# 转换为datetime对象
dt = ros_time_to_datetime(ros_timestamp)
print(f"日期时间: {dt}")

# 格式化显示
formatted_time = format_ros_time(ros_timestamp, "%Y-%m-%d %H:%M:%S.%f")
print(f"格式化时间: {formatted_time}")

# 持续时间格式化
duration_seconds = 3661.5
formatted_duration = TimeUtil.format_duration(duration_seconds)
print(f"持续时间: {formatted_duration}")  # 输出: 1h 1m 1.5s

# 解析时间范围
time_range_str = "2022-01-01T00:00:00 to 2022-01-02T00:00:00"
start_time, end_time = TimeUtil.parse_time_range(time_range_str)
print(f"时间范围: {start_time} - {end_time}")
```

### 日志系统使用

```python
from roseApp.core.util import get_logger, setup_logging, log_performance

# 设置日志系统
setup_logging(level="DEBUG", log_file="rose.log")

# 获取日志器
logger = get_logger("my_module")

# 记录不同级别的日志
logger.debug("调试信息: 开始处理bag文件")
logger.info("信息: 成功加载配置文件")
logger.warning("警告: 缓存命中率较低")
logger.error("错误: 无法读取bag文件")

# 结构化日志记录
logger.info("处理完成", extra={
    'file_path': '/path/to/bag.bag',
    'processing_time': 2.5,
    'topics_count': 15,
    'success': True
})

# 性能日志记录
log_performance("bag_analysis", duration=1.23, 
                bag_size=1024*1024, topics=10)
```

### 性能监控

```python
import time
from roseApp.core.util import PerformanceMonitor

# 使用上下文管理器监控性能
def process_bag_file(bag_path: str):
    with PerformanceMonitor("bag_processing") as monitor:
        # 模拟处理过程
        time.sleep(2)
        
        # 记录中间步骤
        monitor.checkpoint("parsing_complete")
        time.sleep(1)
        
        monitor.checkpoint("analysis_complete")
        time.sleep(0.5)
    
    # 自动记录总耗时和各步骤耗时

# 手动性能测量
def manual_performance_test():
    monitor = PerformanceMonitor("manual_test")
    
    start_time = monitor.start()
    
    # 执行一些操作
    time.sleep(1)
    
    end_time = monitor.stop()
    duration = end_time - start_time
    
    print(f"操作耗时: {duration:.3f}s")

# 内存使用监控
memory_info = PerformanceMonitor.measure_memory()
print(f"内存使用: {memory_info['used_mb']:.1f}MB")
print(f"内存总量: {memory_info['total_mb']:.1f}MB")
print(f"使用率: {memory_info['usage_percent']:.1f}%")

process_bag_file("example.bag")
```

### 应用模式管理

```python
from roseApp.core.util import set_app_mode, get_app_mode, AppMode, is_cli_mode

# 设置应用模式
set_app_mode(AppMode.CLI)

# 检查当前模式
current_mode = get_app_mode()
print(f"当前模式: {current_mode.value}")

# 条件执行
if is_cli_mode():
    print("运行在CLI模式，使用Rich输出")
    from rich.console import Console
    console = Console()
    console.print("Hello from CLI!", style="bold green")
elif get_app_mode() == AppMode.TUI:
    print("运行在TUI模式，启动Textual应用")
else:
    print("运行在其他模式")

# 根据模式配置不同的行为
def configure_for_mode():
    mode = get_app_mode()
    
    if mode == AppMode.CLI:
        # CLI模式配置
        setup_logging(level="INFO")
        return {"progress_bar": True, "colors": True}
    elif mode == AppMode.TUI:
        # TUI模式配置
        setup_logging(level="WARNING", log_file="tui.log")
        return {"progress_bar": False, "colors": True}
    elif mode == AppMode.WEB:
        # Web模式配置
        setup_logging(level="ERROR", log_file="web.log")
        return {"progress_bar": False, "colors": False}
    else:
        # 库模式配置
        return {"progress_bar": False, "colors": False}

config = configure_for_mode()
print(f"应用配置: {config}")
```

### 压缩工具使用

```python
from roseApp.core.util import (
    get_available_compression_types, 
    validate_compression_type,
    detect_compression_from_file
)

# 获取支持的压缩格式
available_compressions = get_available_compression_types()
print(f"支持的压缩格式: {available_compressions}")

# 验证压缩格式
for compression in ["none", "bz2", "lz4", "gzip", "invalid"]:
    is_valid, message = validate_compression_type(compression)
    status = "✓" if is_valid else "✗"
    print(f"{status} {compression}: {message}")

# 从文件检测压缩格式
def check_file_compression(file_path: str):
    try:
        compression = detect_compression_from_file(file_path)
        print(f"文件 {file_path} 的压缩格式: {compression}")
    except Exception as e:
        print(f"无法检测文件压缩格式: {e}")

check_file_compression("example.bag")
check_file_compression("compressed.bag.bz2")
```

### 文件操作工具

```python
from roseApp.core.util import (
    safe_create_directory,
    safe_remove_file,
    get_file_size_formatted,
    calculate_file_hash
)

# 安全创建目录
success = safe_create_directory("/path/to/new/directory")
if success:
    print("目录创建成功")

# 安全删除文件
success = safe_remove_file("/path/to/temp/file.tmp")
if success:
    print("文件删除成功")

# 获取格式化文件大小
file_path = "large_file.bag"
size_str = get_file_size_formatted(file_path)
print(f"文件大小: {size_str}")

# 计算文件哈希
file_hash = calculate_file_hash(file_path, algorithm="md5")
print(f"文件MD5: {file_hash}")

# 批量文件操作
def process_files(file_paths: List[str]):
    results = []
    
    for file_path in file_paths:
        result = {
            'path': file_path,
            'size': get_file_size_formatted(file_path),
            'hash': calculate_file_hash(file_path, algorithm="sha256"),
            'compression': detect_compression_from_file(file_path)
        }
        results.append(result)
    
    return results

file_results = process_files(["file1.bag", "file2.bag.bz2"])
for result in file_results:
    print(f"文件: {result['path']}")
    print(f"  大小: {result['size']}")
    print(f"  哈希: {result['hash'][:16]}...")
    print(f"  压缩: {result['compression']}")
```

## 高级功能

### 配置管理

```python
from roseApp.core.util import ConfigManager

# 创建配置管理器
config = ConfigManager("rose_config.json")

# 设置配置值
config.set("cache.memory_size", 512 * 1024 * 1024)
config.set("cache.file_size", 2 * 1024 * 1024 * 1024)
config.set("logging.level", "INFO")
config.set("theme.default", "dark")

# 获取配置值
memory_size = config.get("cache.memory_size", default=256*1024*1024)
log_level = config.get("logging.level", default="WARNING")

print(f"内存缓存大小: {memory_size} bytes")
print(f"日志级别: {log_level}")

# 保存配置到文件
config.save()

# 从文件加载配置
config.load()

# 监听配置变化
def on_config_change(key: str, old_value, new_value):
    print(f"配置变化: {key} = {old_value} -> {new_value}")

config.add_change_listener("logging.level", on_config_change)
config.set("logging.level", "DEBUG")  # 触发监听器
```

### 环境检测

```python
from roseApp.core.util import (
    detect_environment,
    check_system_requirements,
    get_system_info
)

# 检测运行环境
env_info = detect_environment()
print(f"操作系统: {env_info['os']}")
print(f"Python版本: {env_info['python_version']}")
print(f"终端支持: {env_info['terminal_support']}")
print(f"颜色支持: {env_info['color_support']}")

# 检查系统要求
requirements_check = check_system_requirements()
if requirements_check['all_satisfied']:
    print("✓ 系统要求全部满足")
else:
    print("✗ 系统要求不满足:")
    for req, satisfied in requirements_check['details'].items():
        status = "✓" if satisfied else "✗"
        print(f"  {status} {req}")

# 获取详细系统信息
sys_info = get_system_info()
print(f"CPU核心数: {sys_info['cpu_count']}")
print(f"内存总量: {sys_info['memory_total_gb']:.1f}GB")
print(f"磁盘空间: {sys_info['disk_free_gb']:.1f}GB")
```

### 错误处理工具

```python
from roseApp.core.util import (
    safe_execute,
    retry_on_failure,
    ErrorContext
)

# 安全执行函数
def risky_operation():
    import random
    if random.random() < 0.3:
        raise Exception("随机错误")
    return "操作成功"

# 带错误处理的执行
result = safe_execute(risky_operation, default_value="默认值")
print(f"执行结果: {result}")

# 重试机制
@retry_on_failure(max_retries=3, delay=1.0)
def unstable_function():
    import random
    if random.random() < 0.7:
        raise Exception("不稳定操作失败")
    return "成功"

try:
    result = unstable_function()
    print(f"重试成功: {result}")
except Exception as e:
    print(f"重试失败: {e}")

# 错误上下文管理
with ErrorContext("处理bag文件") as ctx:
    # 可能出错的操作
    ctx.add_info("file_path", "/path/to/bag.bag")
    ctx.add_info("operation", "parsing")
    
    # 如果这里出错，会自动记录上下文信息
    # raise Exception("解析失败")
    
    print("操作成功完成")
```

## 最佳实践

### 1. 日志记录策略

```python
# 为不同组件创建专用日志器
analyzer_logger = get_logger("rose.analyzer")
parser_logger = get_logger("rose.parser")
cache_logger = get_logger("rose.cache")

# 使用结构化日志
def log_operation_result(operation: str, success: bool, **kwargs):
    logger = get_logger("rose.operations")
    
    log_data = {
        'operation': operation,
        'success': success,
        'timestamp': time.time(),
        **kwargs
    }
    
    if success:
        logger.info(f"操作成功: {operation}", extra=log_data)
    else:
        logger.error(f"操作失败: {operation}", extra=log_data)

# 使用示例
log_operation_result("bag_analysis", True, 
                    duration=2.5, topics_count=15, file_size=1024*1024)
```

### 2. 性能监控最佳实践

```python
# 装饰器方式监控函数性能
def performance_monitor(func_name: str = None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor_name = func_name or func.__name__
            
            with PerformanceMonitor(monitor_name) as monitor:
                result = func(*args, **kwargs)
                
                # 记录额外信息
                if hasattr(result, '__len__'):
                    monitor.add_metric('result_size', len(result))
                    
            return result
        return wrapper
    return decorator

@performance_monitor("bag_processing")
def process_bag(bag_path: str):
    # 处理逻辑
    time.sleep(1)
    return ["topic1", "topic2", "topic3"]

result = process_bag("example.bag")
```

### 3. 配置管理最佳实践

```python
# 创建配置单例
class RoseConfig:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config = ConfigManager("rose.json")
        return cls._instance
    
    def get(self, key: str, default=None):
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        self._config.set(key, value)
        self._config.save()  # 自动保存

# 全局配置访问
config = RoseConfig()
cache_size = config.get("cache.memory_size", 512*1024*1024)
```

### 4. 错误处理最佳实践

```python
def robust_file_operation(file_path: str):
    """健壮的文件操作示例"""
    logger = get_logger("file_ops")
    
    try:
        with ErrorContext(f"处理文件 {file_path}") as ctx:
            # 添加上下文信息
            ctx.add_info("file_size", os.path.getsize(file_path))
            ctx.add_info("file_type", "bag")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 检查文件权限
            if not os.access(file_path, os.R_OK):
                raise PermissionError(f"文件不可读: {file_path}")
            
            # 执行实际操作
            with open(file_path, 'rb') as f:
                data = f.read(1024)  # 读取前1KB
            
            logger.info("文件操作成功", extra={
                'file_path': file_path,
                'bytes_read': len(data)
            })
            
            return data
            
    except Exception as e:
        logger.error(f"文件操作失败: {e}", extra={
            'file_path': file_path,
            'error_type': type(e).__name__
        })
        raise
```

## 内部实现

### 工具函数组织

```
util/
├── time_utils.py      # 时间转换工具
├── logging_utils.py   # 日志系统
├── file_utils.py      # 文件操作
├── performance.py     # 性能监控
├── config.py         # 配置管理
├── compression.py    # 压缩工具
└── app_mode.py      # 应用模式
```

### 性能特性

- **轻量级**: 最小化依赖和资源占用
- **高效率**: 优化的算法和数据结构
- **线程安全**: 支持多线程并发使用
- **内存友好**: 智能内存管理和清理

### 扩展性

- **插件化**: 支持自定义工具函数
- **配置驱动**: 通过配置调整行为
- **模块化**: 各工具模块独立，可选择性使用

这个工具模块为Rose提供了丰富的基础功能，是整个系统稳定运行的重要基石，确保了代码的可维护性和可扩展性。 