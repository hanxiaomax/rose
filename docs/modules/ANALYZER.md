# Analyzer 模块使用指南

## 概述

Analyzer 模块是 Rose 的异步分析引擎，提供高性能的 ROS bag 文件分析功能。它支持智能缓存、消息类型分析和多种分析类型。

## 主要特性

- ✅ **异步分析**: 高性能的异步处理，支持进度回调
- ✅ **智能缓存**: 自动缓存分析结果，避免重复计算
- ✅ **消息类型分析**: 深度分析消息结构和字段信息
- ✅ **多种分析类型**: 支持元数据和完整分析模式
- ✅ **错误恢复**: 优雅的错误处理和降级机制

## 核心类型

### AnalysisType (枚举)

```python
class AnalysisType(Enum):
    METADATA = "metadata"        # 仅元数据分析 (快速)
    FULL_ANALYSIS = "full_analysis"  # 完整分析 (包含消息类型)
```

### BagInfo (数据类)

```python
@dataclass
class BagInfo:
    path: Path                    # bag文件路径
    size_bytes: int              # 文件大小
    topics: Set[str]             # 话题列表
    message_counts: Dict[str, int]  # 每个话题的消息数量
    time_range: Optional[tuple]   # 时间范围
    connections: Dict[str, str]   # 话题到消息类型的映射
    duration_seconds: float       # 持续时间(秒)
```

### MessageTypeInfo (数据类)

```python
@dataclass
class MessageTypeInfo:
    type_name: str               # 消息类型名称
    fields: Dict[str, Any]       # 字段信息
    definition: str              # 消息定义
    md5sum: str                 # MD5校验和
    
    def get_field_paths(self) -> List[str]:
        """获取所有字段路径"""
```

### AnalysisResult (数据类)

```python
@dataclass
class AnalysisResult:
    bag_info: BagInfo                          # bag基本信息
    message_types: Dict[str, MessageTypeInfo]  # 消息类型信息
    analysis_type: AnalysisType                # 分析类型
    analysis_time: float                       # 分析耗时
    cached: bool                              # 是否来自缓存
    errors: List[str]                         # 错误信息
    
    def get_topic_field_paths(self, topic: str) -> List[str]:
        """获取指定话题的字段路径"""
```

## 主要接口

### analyze_bag_async() - 异步分析

```python
async def analyze_bag_async(
    bag_path: Path,
    analysis_type: AnalysisType = AnalysisType.METADATA,
    progress_callback: Optional[Callable[[float], None]] = None
) -> AnalysisResult:
    """异步分析bag文件"""
```

**参数说明:**
- `bag_path`: bag文件路径
- `analysis_type`: 分析类型 (METADATA 或 FULL_ANALYSIS)
- `progress_callback`: 进度回调函数，接收0-100的进度值

**返回值:**
- `AnalysisResult`: 完整的分析结果

## 使用示例

### 基础异步分析

```python
import asyncio
from pathlib import Path
from roseApp.core.analyzer import analyze_bag_async, AnalysisType

async def basic_analysis():
    bag_path = Path("example.bag")
    
    # 快速元数据分析
    result = await analyze_bag_async(bag_path, AnalysisType.METADATA)
    
    print(f"话题数量: {len(result.bag_info.topics)}")
    print(f"总消息数: {sum(result.bag_info.message_counts.values())}")
    print(f"持续时间: {result.bag_info.duration_seconds:.2f}s")
    print(f"分析耗时: {result.analysis_time:.3f}s")
    print(f"缓存命中: {result.cached}")

# 运行分析
asyncio.run(basic_analysis())
```

### 带进度回调的完整分析

```python
async def full_analysis_with_progress():
    bag_path = Path("large_bag.bag")
    
    def progress_callback(progress: float):
        print(f"分析进度: {progress:.1f}%")
    
    # 完整分析，包含消息类型信息
    result = await analyze_bag_async(
        bag_path, 
        AnalysisType.FULL_ANALYSIS,
        progress_callback=progress_callback
    )
    
    # 显示话题信息
    for topic in result.bag_info.topics:
        msg_count = result.bag_info.message_counts.get(topic, 0)
        msg_type = result.bag_info.connections.get(topic, 'unknown')
        frequency = msg_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
        
        print(f"话题: {topic}")
        print(f"  类型: {msg_type}")
        print(f"  消息数: {msg_count}")
        print(f"  频率: {frequency:.1f} Hz")
        
        # 获取字段路径
        field_paths = result.get_topic_field_paths(topic)
        if field_paths:
            print(f"  字段: {', '.join(field_paths[:3])}...")

asyncio.run(full_analysis_with_progress())
```

### 批量分析多个bag文件

```python
async def batch_analysis():
    bag_paths = [
        Path("bag1.bag"),
        Path("bag2.bag"), 
        Path("bag3.bag")
    ]
    
    # 并发分析多个文件
    tasks = []
    for bag_path in bag_paths:
        task = analyze_bag_async(bag_path, AnalysisType.METADATA)
        tasks.append((bag_path, task))
    
    # 等待所有任务完成
    for bag_path, task in tasks:
        try:
            result = await task
            print(f"{bag_path}: {len(result.bag_info.topics)} topics, {result.analysis_time:.3f}s")
        except Exception as e:
            print(f"{bag_path}: 分析失败 - {e}")

asyncio.run(batch_analysis())
```

### 错误处理

```python
async def robust_analysis():
    bag_path = Path("potentially_corrupted.bag")
    
    try:
        result = await analyze_bag_async(bag_path)
        
        if result.errors:
            print("分析完成但有警告:")
            for error in result.errors:
                print(f"  - {error}")
        
        # 使用分析结果
        print(f"成功分析: {len(result.bag_info.topics)} 个话题")
        
    except Exception as e:
        print(f"分析失败: {e}")

asyncio.run(robust_analysis())
```

## 性能优化建议

### 1. 缓存利用

```python
# 第一次分析会执行完整解析
result1 = await analyze_bag_async(bag_path)
print(f"首次分析: {result1.analysis_time:.3f}s, 缓存: {result1.cached}")

# 第二次分析会使用缓存
result2 = await analyze_bag_async(bag_path)  
print(f"缓存分析: {result2.analysis_time:.3f}s, 缓存: {result2.cached}")
```

### 2. 选择合适的分析类型

```python
# 如果只需要基本信息，使用METADATA模式
quick_result = await analyze_bag_async(bag_path, AnalysisType.METADATA)

# 如果需要消息类型信息，使用FULL_ANALYSIS模式
detailed_result = await analyze_bag_async(bag_path, AnalysisType.FULL_ANALYSIS)
```

### 3. 并发处理

```python
# 并发分析多个文件以提高效率
results = await asyncio.gather(*[
    analyze_bag_async(path) for path in bag_paths
], return_exceptions=True)
```

## 内部实现

### BagAnalyzer 类

核心分析器类，负责:
- 管理线程池执行器
- 处理缓存逻辑
- 协调解析器操作
- 执行消息类型分析

### 缓存策略

- **缓存键**: 基于文件路径、分析类型和修改时间生成
- **缓存时间**: 默认1小时TTL
- **缓存级别**: 自动根据分析类型选择合适的缓存级别

### 错误恢复

- 解析器自动降级 (rosbags → legacy)
- 优雅的错误处理，返回部分结果
- 详细的错误信息记录

## 资源管理

### 清理资源

```python
from roseApp.core.analyzer import cleanup_analyzer

# 在应用退出时清理资源
cleanup_analyzer()
```

### 线程池配置

```python
# 创建自定义分析器实例
from roseApp.core.analyzer import BagAnalyzer

analyzer = BagAnalyzer(max_workers=8)  # 自定义线程数
try:
    result = await analyzer.analyze_bag_async(bag_path)
finally:
    analyzer.cleanup()  # 清理资源
```

## 最佳实践

1. **使用适当的分析类型**: 根据需求选择METADATA或FULL_ANALYSIS
2. **利用缓存**: 相同文件的重复分析会自动使用缓存
3. **并发处理**: 对于多个文件，使用asyncio.gather进行并发分析
4. **错误处理**: 始终检查result.errors字段
5. **进度回调**: 对于大文件，提供进度回调改善用户体验
6. **资源清理**: 在应用退出时调用cleanup_analyzer()

## 集成示例

### 与其他模块集成

```python
from roseApp.core.analyzer import analyze_bag_async
from roseApp.core.cache import get_cache_stats
from roseApp.core.util import get_logger

async def integrated_analysis():
    logger = get_logger()
    
    # 执行分析
    result = await analyze_bag_async(bag_path)
    logger.info(f"分析完成: {result.analysis_time:.3f}s")
    
    # 检查缓存性能
    cache_stats = get_cache_stats()
    if cache_stats:
        hit_rate = cache_stats.get('unified', {}).get('hit_rate', 0)
        logger.info(f"缓存命中率: {hit_rate:.1%}")
    
    return result
```

这个模块为Rose提供了强大而灵活的bag分析能力，支持从简单的元数据提取到复杂的消息类型分析，同时保持高性能和良好的用户体验。 