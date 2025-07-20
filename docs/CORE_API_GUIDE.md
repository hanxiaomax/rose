# Rose Core Module API Usage Guide

## Overview

Rose core modules have been refactored to provide 6 main modules, each with clear API interfaces and functional boundaries. This document describes how to use these core modules.

> **Note**: This guide provides an API overview. For detailed usage, please refer to the dedicated module documentation:
> - [Analyzer Module Guide](modules/ANALYZER.md) - Asynchronous analysis engine
> - [Cache Module Guide](modules/CACHE.md) - Unified caching system
> - [Engine Module Guide](modules/ENGINE.md) - Core processing engine
> - [Parser Module Guide](modules/PARSER.md) - Intelligent parser management
> - [Theme Module Guide](modules/THEME.md) - Theme system
> - [Util Module Guide](modules/UTIL.md) - Utility functions collection

## 模块架构

```
roseApp.core/
├── cache.py          # 统一缓存系统
├── analyzer.py       # 异步分析引擎  
├── engine.py         # 核心处理引擎
├── parser.py         # 智能解析器管理
├── theme.py          # 主题系统
├── util.py           # 工具函数
└── BagManager.py     # TUI专用管理器
```

---

## 1. 缓存系统 (cache.py)

### 功能特性
- 多级缓存 (内存 → 文件)
- 智能预热和性能分析
- 跨会话持久化
- 自动缓存清理

### 基础使用

```python
from roseApp.core.cache import get_cache, clear_cache, get_cache_stats

# 获取全局缓存实例
cache = get_cache()

# 存储数据
cache.put("analysis_result", result_data, ttl=3600)  # 缓存1小时

# 获取数据
cached_result = cache.get("analysis_result")
if cached_result:
    print("缓存命中!")

# 删除特定缓存
cache.delete("analysis_result")

# 清空所有缓存
clear_cache()

# 获取缓存统计
stats = get_cache_stats()
print(f"缓存命中率: {stats['unified']['hit_rate']:.2%}")
```

### 高级功能

```python
# 缓存优化
optimization_results = cache.optimize()
print(f"预热了 {len(optimization_results['preheated_keys'])} 个缓存项")

# 性能分析
performance = cache.get_stats()['performance']
print(f"效率评分: {performance['efficiency_score']:.1f}/100")
```

---

## 2. 分析引擎 (analyzer.py)

### 功能特性
- 异步bag文件分析
- 消息类型智能分析
- 多种分析类型支持
- 智能缓存集成

### 基础使用

```python
from roseApp.core.analyzer import analyze_bag, AnalysisType
from pathlib import Path

# 同步分析
bag_path = Path("example.bag")
result = analyze_bag(bag_path, AnalysisType.FULL_ANALYSIS)

print(f"分析耗时: {result.analysis_time:.2f}s")
print(f"话题数量: {len(result.bag_info.topics)}")
print(f"消息类型: {list(result.message_types.keys())}")

# 获取话题字段路径
field_paths = result.get_topic_field_paths("/camera/image")
print(f"图像话题字段: {field_paths}")
```

### 异步分析

```python
import asyncio
from roseApp.core.analyzer import analyze_bag_async

async def analyze_multiple_bags():
    bag_paths = [Path("bag1.bag"), Path("bag2.bag")]
    
    # 并发分析多个bag文件
    tasks = [
        analyze_bag_async(bag_path, progress_callback=lambda p: print(f"进度: {p:.1f}%"))
        for bag_path in bag_paths
    ]
    
    results = await asyncio.gather(*tasks)
    
    for result in results:
        print(f"分析完成: {result.bag_info.path}")

# 运行异步分析
asyncio.run(analyze_multiple_bags())
```

### 分析类型

```python
# 不同的分析类型
from roseApp.core.analyzer import AnalysisType

# 仅元数据 (最快)
metadata_result = analyze_bag(bag_path, AnalysisType.METADATA)

# 字段分析 (包含消息结构)
field_result = analyze_bag(bag_path, AnalysisType.FIELD_ANALYSIS)

# 完整分析 (包含所有信息)
full_result = analyze_bag(bag_path, AnalysisType.FULL_ANALYSIS)
```

---

## 3. 处理引擎 (engine.py)

### 功能特性
- 异步bag文件处理
- 智能过滤和转换
- 批量处理支持
- 压缩格式支持

### 基础使用

```python
from roseApp.core.engine import filter_bag, CompressionType
from pathlib import Path

# 同步过滤bag文件
input_path = Path("input.bag")
output_path = Path("filtered.bag")
topics = ["/camera/image", "/odom"]

result = filter_bag(
    input_path=input_path,
    topics=topics,
    output_path=output_path,
    compression=CompressionType.LZ4.value,
    overwrite=True
)

if result.success:
    print(f"处理成功! 输出大小: {result.size_str}")
    print(f"处理耗时: {result.processing_time:.2f}s")
else:
    print(f"处理失败: {result.error_message}")
```

### 异步处理

```python
import asyncio
from roseApp.core.engine import filter_bag_async, get_engine

async def process_bags():
    engine = get_engine()
    
    # 异步过滤
    result = await filter_bag_async(
        input_path=Path("large.bag"),
        topics=["/camera/image"],
        progress_callback=lambda p: print(f"进度: {p:.1f}%")
    )
    
    # 验证bag文件
    validation = await engine.validate_bag_async(Path("output.bag"))
    if validation['valid']:
        print(f"验证通过: {validation['message_count']} 条消息")

asyncio.run(process_bags())
```

### 批量处理

```python
from roseApp.core.engine import FilterConfig

async def batch_process():
    engine = get_engine()
    
    # 批量处理配置
    config = FilterConfig(
        topics=["/odom", "/tf"],
        compression=CompressionType.BZ2.value,
        overwrite=True
    )
    
    bag_paths = [Path("bag1.bag"), Path("bag2.bag"), Path("bag3.bag")]
    
    # 并发处理
    results = await engine.filter_multiple_bags_async(
        input_paths=bag_paths,
        config=config,
        progress_callback=lambda path, progress: print(f"{path}: {progress:.1f}%")
    )
    
    # 检查结果
    for path, result in results.items():
        if result.success:
            print(f"✓ {path}: {result.size_str}")
        else:
            print(f"✗ {path}: {result.error_message}")

asyncio.run(batch_process())
```

---

## 4. 解析器管理 (parser.py)

### 功能特性
- 智能解析器选择
- 健康检查和自动降级
- 性能警告系统
- 多格式支持

### 基础使用

```python
from roseApp.core.parser import create_best_parser, get_parser_health

# 创建最佳解析器
parser = create_best_parser()

# 加载bag信息
topics, connections, time_range = parser.load_bag("example.bag")
print(f"话题数: {len(topics)}")

# 获取消息统计
message_counts = parser.get_message_counts("example.bag")
topic_stats = parser.get_topic_stats("example.bag")

for topic, count in message_counts.items():
    size = topic_stats[topic]['size']
    print(f"{topic}: {count} 消息, {size} 字节")
```

### 解析器健康检查

```python
from roseApp.core.parser import get_all_parser_health, ParserType

# 检查所有解析器状态
health_status = get_all_parser_health()

for parser_type, health in health_status.items():
    status = "✓" if health.is_healthy() else "✗"
    print(f"{status} {parser_type.value}: {health.version}")
    if health.error_message:
        print(f"  错误: {health.error_message}")
    print(f"  性能评分: {health.performance_score}/100")
```

### 手动解析器选择

```python
from roseApp.core.parser import create_parser, ParserType

# 强制使用特定解析器
try:
    rosbags_parser = create_parser(ParserType.ROSBAGS)
    print("使用高性能rosbags解析器")
except RuntimeError as e:
    print(f"rosbags不可用: {e}")
    
    # 降级到legacy解析器
    legacy_parser = create_parser(ParserType.LEGACY)
    print("降级到legacy解析器")
```

---

## 5. 主题系统 (theme.py)

### 功能特性
- 统一主题管理
- CSS主题解析
- 多平台支持
- 动态主题切换

### 基础使用

```python
from roseApp.core.theme import get_theme, set_theme, get_current_colors

# 获取主题管理器
theme_manager = get_theme()

# 列出可用主题
available_themes = theme_manager.list_themes()
print(f"可用主题: {available_themes}")

# 切换主题
set_theme("dark")

# 获取当前颜色
colors = get_current_colors()
print(f"主色调: {colors.primary}")
print(f"背景色: {colors.background}")
```

### 从CSS加载主题

```python
from pathlib import Path
from roseApp.core.theme import load_theme_from_css

# 从CSS文件加载主题
css_path = Path("custom_theme.css")
success = load_theme_from_css(css_path, "custom")

if success:
    set_theme("custom")
    print("自定义主题加载成功")
```

### 可视化集成

```python
# Matplotlib集成
matplotlib_style = theme_manager.get_matplotlib_style()
# 应用到matplotlib...

# Plotly集成
plotly_theme = theme_manager.get_plotly_theme()
# 应用到plotly...
```

---

## 6. 工具函数 (util.py)

### 功能特性
- 时间格式转换
- 日志管理
- 压缩类型验证
- 应用模式控制

### 基础使用

```python
from roseApp.core.util import TimeUtil, get_logger, validate_compression_type

# 时间转换
time_tuple = (1640995200, 123456789)  # (秒, 纳秒)
formatted_time = TimeUtil.to_datetime(time_tuple)
print(f"格式化时间: {formatted_time}")

# 解析时间字符串
time_range = TimeUtil.convert_time_range_to_tuple(
    "21/01/01 12:00:00", 
    "21/01/01 13:00:00"
)

# 日志记录
logger = get_logger("my_module")
logger.info("这是一条日志信息")

# 压缩验证
is_valid, error = validate_compression_type("lz4")
if is_valid:
    print("LZ4压缩可用")
else:
    print(f"压缩不可用: {error}")
```

---

## 完整示例：分析和过滤Bag文件

```python
import asyncio
from pathlib import Path
from roseApp.core.analyzer import analyze_bag_async, AnalysisType
from roseApp.core.engine import filter_bag_async, CompressionType
from roseApp.core.cache import get_cache_stats
from roseApp.core.util import get_logger

async def process_bag_workflow():
    logger = get_logger("workflow")
    bag_path = Path("input.bag")
    
    # 1. 分析bag文件
    logger.info("开始分析bag文件...")
    analysis_result = await analyze_bag_async(
        bag_path, 
        AnalysisType.FULL_ANALYSIS,
        progress_callback=lambda p: print(f"分析进度: {p:.1f}%")
    )
    
    if analysis_result.errors:
        logger.error(f"分析失败: {analysis_result.errors}")
        return
    
    # 2. 选择感兴趣的话题
    available_topics = list(analysis_result.bag_info.topics)
    selected_topics = [t for t in available_topics if "/camera" in t or "/odom" in t]
    
    logger.info(f"选择了 {len(selected_topics)} 个话题进行过滤")
    
    # 3. 过滤bag文件
    filter_result = await filter_bag_async(
        input_path=bag_path,
        topics=selected_topics,
        output_path=Path("filtered_output.bag"),
        compression=CompressionType.LZ4.value,
        overwrite=True,
        progress_callback=lambda p: print(f"过滤进度: {p:.1f}%")
    )
    
    if filter_result.success:
        logger.info(f"过滤成功! 输出大小: {filter_result.size_str}")
        logger.info(f"总耗时: {filter_result.processing_time:.2f}s")
    else:
        logger.error(f"过滤失败: {filter_result.error_message}")
    
    # 4. 显示缓存统计
    cache_stats = get_cache_stats()
    logger.info(f"缓存命中率: {cache_stats['unified']['hit_rate']:.2%}")

# 运行工作流
if __name__ == "__main__":
    asyncio.run(process_bag_workflow())
```

## CLI使用建议

对于CLI应用，建议的导入模式：

```python
# 最小导入 - 仅导入需要的功能
from roseApp.core.engine import filter_bag, analyze_bag_async
from roseApp.core.parser import create_best_parser
from roseApp.core.util import get_logger, validate_compression_type

# 或者使用便捷函数
from roseApp.core.analyzer import analyze_bag
from roseApp.core.engine import get_engine
```

## 性能建议

1. **缓存利用**: 重复操作会自动使用缓存，显著提升性能
2. **异步处理**: 对于大文件或批量处理，优先使用异步API
3. **解析器选择**: 系统会自动选择最佳解析器，无需手动干预
4. **压缩格式**: LZ4提供最佳的压缩速度平衡，BZ2提供最佳压缩率

## 错误处理

所有核心模块都提供了完善的错误处理：

```python
try:
    result = analyze_bag(bag_path)
    if result.errors:
        print(f"分析警告: {result.errors}")
except Exception as e:
    logger.error(f"分析失败: {e}")
```

## 总结

Rose核心模块现在提供了：
- **统一的API接口**: 清晰、一致的函数签名
- **智能缓存**: 自动缓存提升性能
- **异步支持**: 高并发处理能力  
- **错误恢复**: 智能降级和错误处理
- **易于使用**: 最少的导入，最大的功能

每个模块都可以独立使用，也可以组合使用以实现复杂的bag文件处理工作流。 