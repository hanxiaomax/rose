# Engine 模块使用指南

## 概述

Engine 模块是 Rose 的异步处理引擎，提供高性能的 ROS bag 文件处理功能，包括过滤、复制、验证和统计分析等操作。

## 主要特性

- ✅ **异步处理**: 高性能的异步I/O操作
- ✅ **批量处理**: 支持多文件并发处理
- ✅ **智能过滤**: 基于话题、时间范围的灵活过滤
- ✅ **压缩支持**: 支持多种压缩格式(none/bz2/lz4)
- ✅ **进度回调**: 实时处理进度反馈
- ✅ **错误恢复**: 优雅的错误处理和降级机制

## 核心类型

### CompressionType (枚举)

```python
class CompressionType(Enum):
    NONE = "none"    # 无压缩
    BZ2 = "bz2"      # BZ2压缩
    LZ4 = "lz4"      # LZ4压缩
```

### FilterConfig (数据类)

```python
@dataclass
class FilterConfig:
    topics: List[str]                    # 要过滤的话题列表
    time_range: Optional[tuple] = None   # 时间范围 (start, end)
    compression: str = CompressionType.NONE.value  # 压缩格式
    output_path: Optional[Path] = None   # 输出路径
    overwrite: bool = False             # 是否覆盖现有文件
```

### ProcessingResult (数据类)

```python
@dataclass
class ProcessingResult:
    success: bool                       # 处理是否成功
    input_path: Path                   # 输入文件路径
    output_path: Optional[Path] = None  # 输出文件路径
    processing_time: float = 0.0       # 处理耗时(秒)
    error_message: str = ""            # 错误信息
    output_size: int = 0               # 输出文件大小(字节)
    
    @property
    def size_str(self) -> str:
        """人类可读的文件大小"""
```

## 主要接口

### filter_bag_async() - 异步过滤

```python
async def filter_bag_async(
    input_path: Path,
    topics: List[str],
    output_path: Optional[Path] = None,
    compression: str = CompressionType.NONE.value,
    time_range: Optional[tuple] = None,
    overwrite: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None
) -> ProcessingResult:
    """异步过滤bag文件"""
```

### get_engine() - 获取引擎实例

```python
def get_engine() -> BagEngine:
    """获取全局引擎实例"""
```

## 使用示例

### 基础异步过滤

```python
import asyncio
from pathlib import Path
from roseApp.core.engine import filter_bag_async, CompressionType

async def basic_filter():
    input_path = Path("input.bag")
    topics = ["/camera/image", "/lidar/points"]
    
    # 进度回调函数
    def progress_callback(progress: float):
        print(f"过滤进度: {progress:.1f}%")
    
    # 执行过滤
    result = await filter_bag_async(
        input_path=input_path,
        topics=topics,
        compression=CompressionType.BZ2.value,
        progress_callback=progress_callback
    )
    
    if result.success:
        print(f"过滤成功!")
        print(f"输出文件: {result.output_path}")
        print(f"文件大小: {result.size_str}")
        print(f"处理耗时: {result.processing_time:.2f}s")
    else:
        print(f"过滤失败: {result.error_message}")

# 运行过滤
asyncio.run(basic_filter())
```

### 高级过滤配置

```python
async def advanced_filter():
    input_path = Path("large_dataset.bag")
    output_path = Path("filtered_output.bag")
    
    # 配置时间范围过滤 (Unix时间戳)
    start_time = 1640995200  # 2022-01-01 00:00:00
    end_time = 1641081600    # 2022-01-02 00:00:00
    time_range = (start_time, end_time)
    
    # 话题过滤
    topics = [
        "/camera/rgb/image_raw",
        "/camera/depth/image_raw", 
        "/tf",
        "/tf_static"
    ]
    
    result = await filter_bag_async(
        input_path=input_path,
        topics=topics,
        output_path=output_path,
        compression=CompressionType.LZ4.value,
        time_range=time_range,
        overwrite=True
    )
    
    print(f"过滤结果: {'成功' if result.success else '失败'}")
    if result.success:
        print(f"原始大小: {input_path.stat().st_size / 1024 / 1024:.1f}MB")
        print(f"过滤后大小: {result.output_size / 1024 / 1024:.1f}MB")
        compression_ratio = (1 - result.output_size / input_path.stat().st_size) * 100
        print(f"压缩比: {compression_ratio:.1f}%")

asyncio.run(advanced_filter())
```

### 批量处理多个文件

```python
from roseApp.core.engine import get_engine, FilterConfig

async def batch_processing():
    # 输入文件列表
    input_paths = [
        Path("bag1.bag"),
        Path("bag2.bag"),
        Path("bag3.bag")
    ]
    
    # 配置过滤参数
    config = FilterConfig(
        topics=["/camera/image", "/lidar/scan"],
        compression=CompressionType.BZ2.value,
        output_path=Path("filtered_outputs/"),  # 输出目录
        overwrite=True
    )
    
    # 进度回调
    def progress_callback(bag_path: Path, progress: float):
        print(f"{bag_path.name}: {progress:.1f}%")
    
    # 获取引擎实例
    engine = get_engine()
    
    # 批量处理
    results = await engine.filter_multiple_bags_async(
        input_paths=input_paths,
        config=config,
        progress_callback=progress_callback
    )
    
    # 处理结果统计
    successful = sum(1 for result in results.values() if result.success)
    total_time = sum(result.processing_time for result in results.values())
    total_output_size = sum(result.output_size for result in results.values() if result.success)
    
    print(f"\n批量处理完成:")
    print(f"成功: {successful}/{len(input_paths)}")
    print(f"总耗时: {total_time:.2f}s")
    print(f"总输出大小: {total_output_size / 1024 / 1024:.1f}MB")
    
    # 显示失败的文件
    for path, result in results.items():
        if not result.success:
            print(f"失败: {path} - {result.error_message}")

asyncio.run(batch_processing())
```

### 文件复制和验证

```python
async def copy_and_validate():
    engine = get_engine()
    
    # 复制文件
    copy_result = await engine.copy_bag_async(
        input_path=Path("source.bag"),
        output_path=Path("backup.bag"),
        overwrite=True
    )
    
    if copy_result.success:
        print(f"文件复制成功: {copy_result.size_str}")
        
        # 验证文件
        validation = await engine.validate_bag_async(Path("backup.bag"))
        
        if validation['valid']:
            print("文件验证通过:")
            print(f"  话题数量: {validation['topic_count']}")
            print(f"  消息数量: {validation['message_count']}")
            print(f"  持续时间: {validation['duration']:.2f}s")
            print(f"  文件大小: {validation['file_size'] / 1024 / 1024:.1f}MB")
        else:
            print("文件验证失败:")
            for error in validation['errors']:
                print(f"  - {error}")
    else:
        print(f"文件复制失败: {copy_result.error_message}")

asyncio.run(copy_and_validate())
```

### 获取详细统计信息

```python
async def get_statistics():
    engine = get_engine()
    
    # 获取详细统计
    stats = await engine.get_bag_statistics_async(Path("example.bag"))
    
    if 'error' not in stats:
        print(f"文件: {stats['file_path']}")
        print(f"大小: {stats['file_size'] / 1024 / 1024:.1f}MB")
        print(f"话题数量: {stats['topic_count']}")
        print(f"总消息数: {stats['total_messages']}")
        print(f"持续时间: {stats['duration_seconds']:.2f}s")
        
        print("\n话题详情:")
        for topic, info in stats['topics'].items():
            print(f"  {topic}:")
            print(f"    类型: {info['message_type']}")
            print(f"    消息数: {info['message_count']}")
            print(f"    频率: {info['frequency_hz']:.1f} Hz")
    else:
        print(f"获取统计信息失败: {stats['error']}")

asyncio.run(get_statistics())
```

## 高级功能

### 自定义引擎配置

```python
from roseApp.core.engine import BagEngine

# 创建自定义配置的引擎
custom_engine = BagEngine(max_workers=8)  # 8个工作线程

try:
    # 使用自定义引擎
    result = await custom_engine.filter_bag_async(
        input_path=Path("large_file.bag"),
        topics=["/high_freq_topic"],
        compression=CompressionType.LZ4.value
    )
finally:
    # 清理资源
    custom_engine.cleanup()
```

### 错误处理和重试

```python
import asyncio
from pathlib import Path

async def robust_processing():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            result = await filter_bag_async(
                input_path=Path("problematic.bag"),
                topics=["/camera/image"]
            )
            
            if result.success:
                print("处理成功")
                break
            else:
                print(f"处理失败: {result.error_message}")
                
        except Exception as e:
            print(f"异常发生: {e}")
            
        retry_count += 1
        if retry_count < max_retries:
            print(f"重试 {retry_count}/{max_retries}...")
            await asyncio.sleep(2)  # 等待2秒后重试
    
    if retry_count >= max_retries:
        print("达到最大重试次数，处理失败")

asyncio.run(robust_processing())
```

### 性能监控

```python
import time
from roseApp.core.engine import get_engine

async def monitor_performance():
    engine = get_engine()
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理多个文件
    tasks = []
    for i in range(5):
        task = filter_bag_async(
            input_path=Path(f"bag_{i}.bag"),
            topics=["/sensor_data"]
        )
        tasks.append(task)
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 计算性能指标
    total_time = time.time() - start_time
    successful_results = [r for r in results if isinstance(r, ProcessingResult) and r.success]
    
    if successful_results:
        avg_processing_time = sum(r.processing_time for r in successful_results) / len(successful_results)
        total_output_size = sum(r.output_size for r in successful_results)
        throughput = total_output_size / total_time / 1024 / 1024  # MB/s
        
        print(f"性能统计:")
        print(f"总耗时: {total_time:.2f}s")
        print(f"平均处理时间: {avg_processing_time:.2f}s")
        print(f"吞吐量: {throughput:.2f} MB/s")
        print(f"成功率: {len(successful_results)}/{len(results)} ({len(successful_results)/len(results)*100:.1f}%)")

asyncio.run(monitor_performance())
```

## 最佳实践

### 1. 选择合适的压缩格式

```python
# 根据场景选择压缩格式
compression_choice = {
    "speed_priority": CompressionType.LZ4.value,     # 速度优先
    "size_priority": CompressionType.BZ2.value,      # 大小优先  
    "no_compression": CompressionType.NONE.value     # 无压缩
}
```

### 2. 合理设置并发数

```python
import os

# 根据CPU核心数设置工作线程
cpu_count = os.cpu_count()
optimal_workers = min(cpu_count, 8)  # 最多8个工作线程

engine = BagEngine(max_workers=optimal_workers)
```

### 3. 处理大文件

```python
async def handle_large_files():
    # 对于大文件，提供进度回调
    def progress_callback(progress: float):
        if progress % 10 == 0:  # 每10%输出一次
            print(f"处理进度: {progress:.0f}%")
    
    # 使用时间范围分块处理
    time_chunks = [
        (start_time, start_time + 3600) for start_time in range(start, end, 3600)
    ]
    
    for i, time_range in enumerate(time_chunks):
        result = await filter_bag_async(
            input_path=Path("huge_file.bag"),
            topics=["/sensor_data"],
            output_path=Path(f"chunk_{i}.bag"),
            time_range=time_range,
            progress_callback=progress_callback
        )
```

### 4. 错误恢复策略

```python
async def resilient_processing(input_files: List[Path]):
    successful_files = []
    failed_files = []
    
    for file_path in input_files:
        try:
            result = await filter_bag_async(
                input_path=file_path,
                topics=["/important_data"]
            )
            
            if result.success:
                successful_files.append(file_path)
            else:
                failed_files.append((file_path, result.error_message))
                
        except Exception as e:
            failed_files.append((file_path, str(e)))
    
    # 对失败的文件进行降级处理
    for file_path, error in failed_files:
        print(f"处理失败: {file_path} - {error}")
        # 可以尝试其他处理策略
```

## 内部实现

### AsyncIOManager

负责异步I/O操作:
- 文件读写操作
- 目录管理
- 线程池管理

### BagEngine

主要处理引擎:
- 协调各种处理操作
- 管理并发任务
- 提供统一接口

### 性能特性

- **并发处理**: 支持多文件并行处理
- **内存优化**: 流式处理，避免大文件内存占用
- **错误恢复**: 单个文件失败不影响其他文件处理
- **进度跟踪**: 实时进度反馈

## 资源管理

### 清理资源

```python
from roseApp.core.engine import cleanup_engine

# 在应用退出时清理资源
cleanup_engine()
```

### 内存使用优化

```python
# 对于内存敏感的环境
engine = BagEngine(max_workers=2)  # 减少并发数
```

这个引擎模块为Rose提供了强大的异步处理能力，支持各种bag文件操作，具有良好的性能和可靠性，是整个系统的核心处理组件。 