# Cache 模块使用指南

## 概述

Cache 模块提供了Rose的统一缓存系统，支持多级缓存架构，包括内存缓存和文件缓存，具有智能预热、性能分析和自动优化功能。

## 主要特性

- ✅ **多级缓存**: 内存缓存 + 文件缓存的分层架构
- ✅ **智能预热**: 基于访问模式的智能缓存预热
- ✅ **性能分析**: 详细的缓存性能统计和分析
- ✅ **自动优化**: 动态调整缓存策略以提升性能
- ✅ **TTL支持**: 灵活的生存时间管理
- ✅ **线程安全**: 支持多线程并发访问

## 核心类型

### CacheEntry (数据类)

```python
@dataclass
class CacheEntry:
    key: str                    # 缓存键
    value: Any                  # 缓存值
    timestamp: float            # 创建时间戳
    access_count: int           # 访问次数
    last_access: float          # 最后访问时间
    size_bytes: int            # 数据大小(字节)
    ttl: float                 # 生存时间(秒)
    tags: Set[str]             # 标签集合
    
    def is_expired(self) -> bool:
        """检查是否已过期"""
    
    def touch(self) -> None:
        """更新访问时间和次数"""
```

### UnifiedCache (主缓存类)

```python
class UnifiedCache:
    def __init__(self, 
                 memory_max_size: int = 512 * 1024 * 1024,  # 512MB
                 file_max_size: int = 2 * 1024 * 1024 * 1024):  # 2GB
    
    def get(self, key: str) -> Any:
        """获取缓存项"""
    
    def put(self, key: str, value: Any, ttl: float = 3600) -> None:
        """存储缓存项"""
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
    
    def clear(self) -> None:
        """清空所有缓存"""
    
    def optimize() -> Dict[str, Any]:
        """执行缓存优化"""
    
    def get_stats() -> Dict[str, Any]:
        """获取缓存统计信息"""
```

## 主要接口

### get_cache() - 获取全局缓存实例

```python
def get_cache() -> UnifiedCache:
    """获取全局缓存实例"""
```

### get_cache_stats() - 获取缓存统计

```python
def get_cache_stats() -> Dict[str, Any]:
    """获取全局缓存统计信息"""
```

### clear_cache() - 清空缓存

```python
def clear_cache() -> None:
    """清空全局缓存"""
```

## 使用示例

### 基础缓存操作

```python
from roseApp.core.cache import get_cache

# 获取缓存实例
cache = get_cache()

# 存储数据
cache.put("user_data", {"name": "Alice", "age": 30}, ttl=1800)  # 30分钟TTL
cache.put("analysis_result", analysis_data, ttl=3600)  # 1小时TTL

# 获取数据
user_data = cache.get("user_data")
if user_data:
    print(f"用户: {user_data['name']}")
else:
    print("缓存未命中")

# 删除数据
success = cache.delete("user_data")
print(f"删除结果: {success}")
```

### 缓存统计和性能监控

```python
from roseApp.core.cache import get_cache_stats

# 获取详细统计信息
stats = get_cache_stats()

if stats and stats.get('unified', {}).get('enabled'):
    unified_stats = stats['unified']
    
    print(f"缓存命中率: {unified_stats.get('hit_rate', 0):.1%}")
    print(f"总请求数: {unified_stats.get('total_requests', 0)}")
    print(f"内存缓存项: {unified_stats.get('memory_entries', 0)}")
    print(f"文件缓存项: {unified_stats.get('file_entries', 0)}")
    
    # 性能分析
    performance = unified_stats.get('performance', {})
    if performance:
        print(f"效率评分: {performance.get('efficiency_score', 0)}/100")
        print(f"平均访问时间: {performance.get('avg_access_time', 0):.3f}ms")
```

### 缓存优化

```python
# 执行缓存优化
cache = get_cache()
optimization_result = cache.optimize()

print("优化结果:")
print(f"预热的缓存项: {len(optimization_result.get('preheated_keys', []))}")
print(f"清理的过期项: {optimization_result.get('expired_cleaned', 0)}")
print(f"内存使用优化: {optimization_result.get('memory_optimized', False)}")

# 查看优化建议
recommendations = optimization_result.get('recommendations', [])
for rec in recommendations:
    print(f"建议: {rec}")
```

### 带标签的缓存管理

```python
# 使用标签组织缓存
cache = get_cache()

# 存储带标签的数据
cache.put("bag_analysis_1", result1, ttl=3600, tags={"analysis", "bag1"})
cache.put("bag_analysis_2", result2, ttl=3600, tags={"analysis", "bag2"})
cache.put("user_session", session_data, ttl=1800, tags={"session", "user"})

# 批量清理特定标签的缓存
cache.clear_by_tags({"analysis"})  # 清理所有分析相关的缓存
```

### 高级缓存模式

```python
import asyncio
from roseApp.core.cache import get_cache

async def cache_with_computation():
    cache = get_cache()
    key = "expensive_computation_result"
    
    # 检查缓存
    result = cache.get(key)
    if result is not None:
        print("缓存命中，直接返回结果")
        return result
    
    # 缓存未命中，执行计算
    print("缓存未命中，执行计算...")
    result = await perform_expensive_computation()
    
    # 存储到缓存
    cache.put(key, result, ttl=7200)  # 2小时TTL
    
    return result

async def perform_expensive_computation():
    # 模拟耗时计算
    await asyncio.sleep(2)
    return {"computed_value": 42, "timestamp": time.time()}
```

## 缓存策略配置

### 内存缓存配置

```python
from roseApp.core.cache import UnifiedCache

# 创建自定义配置的缓存
custom_cache = UnifiedCache(
    memory_max_size=1024 * 1024 * 1024,  # 1GB内存缓存
    file_max_size=5 * 1024 * 1024 * 1024,  # 5GB文件缓存
)

# 配置LRU策略参数
custom_cache.set_eviction_policy("lru", max_age_seconds=3600)
```

### 文件缓存配置

```python
# 配置文件缓存目录
import os
from pathlib import Path

cache_dir = Path.home() / ".cache" / "rose" / "custom"
cache_dir.mkdir(parents=True, exist_ok=True)

# 设置缓存目录
cache.set_file_cache_dir(cache_dir)
```

## 性能分析和优化

### 缓存性能分析

```python
from roseApp.core.cache import get_cache

cache = get_cache()
stats = cache.get_stats()

# 分析缓存效率
performance = stats.get('performance', {})
if performance:
    efficiency_score = performance.get('efficiency_score', 0)
    
    if efficiency_score < 70:
        print("缓存效率较低，建议优化")
        
        # 获取优化建议
        recommendations = performance.get('recommendations', [])
        for rec in recommendations:
            print(f"优化建议: {rec}")
    else:
        print(f"缓存效率良好: {efficiency_score}/100")
```

### 智能预热

```python
# 手动触发智能预热
cache = get_cache()
preheat_result = cache.preheat_intelligent()

print(f"预热了 {preheat_result['preheated_count']} 个缓存项")
print(f"预计性能提升: {preheat_result['estimated_improvement']:.1%}")

# 基于访问模式的预热
access_patterns = cache.analyze_access_patterns()
for pattern in access_patterns['frequent_patterns']:
    print(f"频繁访问模式: {pattern}")
```

## 监控和调试

### 缓存监控

```python
import time
from roseApp.core.cache import get_cache

def monitor_cache_performance():
    cache = get_cache()
    
    while True:
        stats = cache.get_stats()
        unified_stats = stats.get('unified', {})
        
        print(f"时间: {time.strftime('%H:%M:%S')}")
        print(f"命中率: {unified_stats.get('hit_rate', 0):.1%}")
        print(f"内存使用: {unified_stats.get('memory_usage_mb', 0):.1f}MB")
        print(f"文件缓存大小: {unified_stats.get('file_cache_size_mb', 0):.1f}MB")
        print("-" * 40)
        
        time.sleep(10)  # 每10秒输出一次
```

### 缓存调试

```python
# 启用详细日志
import logging
logging.getLogger('roseApp.core.cache').setLevel(logging.DEBUG)

# 检查缓存内容
cache = get_cache()
cache_contents = cache.debug_dump()

print("缓存内容:")
for key, entry in cache_contents.items():
    print(f"  {key}: {entry['size_bytes']} bytes, 访问 {entry['access_count']} 次")
```

## 最佳实践

### 1. 合理设置TTL

```python
# 根据数据特性设置合适的TTL
cache.put("static_config", config, ttl=86400)      # 24小时 - 静态配置
cache.put("user_session", session, ttl=3600)      # 1小时 - 用户会话
cache.put("analysis_result", result, ttl=1800)    # 30分钟 - 分析结果
cache.put("temp_data", temp, ttl=300)             # 5分钟 - 临时数据
```

### 2. 使用标签组织缓存

```python
# 使用有意义的标签
cache.put("user_123_profile", profile, tags={"user", "profile", "user_123"})
cache.put("bag_analysis_abc", analysis, tags={"analysis", "bag", "abc"})

# 批量清理相关缓存
cache.clear_by_tags({"user_123"})  # 清理特定用户的所有缓存
```

### 3. 监控缓存性能

```python
# 定期检查缓存性能
def check_cache_health():
    stats = get_cache_stats()
    unified_stats = stats.get('unified', {})
    
    hit_rate = unified_stats.get('hit_rate', 0)
    if hit_rate < 0.7:  # 命中率低于70%
        print("警告: 缓存命中率偏低，建议检查缓存策略")
    
    memory_usage = unified_stats.get('memory_usage_percent', 0)
    if memory_usage > 0.9:  # 内存使用超过90%
        print("警告: 内存缓存使用率过高，建议清理或增加容量")
```

### 4. 错误处理

```python
try:
    result = cache.get("important_data")
    if result is None:
        # 缓存未命中，从数据源加载
        result = load_from_source()
        cache.put("important_data", result, ttl=3600)
except Exception as e:
    print(f"缓存操作失败: {e}")
    # 降级到直接从数据源加载
    result = load_from_source()
```

## 内部实现

### 缓存层次结构

```
UnifiedCache
├── MemoryCache (L1)
│   ├── LRU淘汰策略
│   ├── 快速访问
│   └── 512MB默认容量
└── FileCache (L2)
    ├── SQLite索引
    ├── 持久化存储
    └── 2GB默认容量
```

### 缓存流程

1. **读取流程**: 内存缓存 → 文件缓存 → 缓存未命中
2. **写入流程**: 内存缓存 → (容量不足时) 文件缓存
3. **淘汰策略**: LRU + TTL + 智能预测

### 性能特性

- **内存访问**: < 1ms
- **文件访问**: < 10ms  
- **并发支持**: 线程安全
- **容量管理**: 自动清理和优化

这个缓存系统为Rose提供了高性能、可靠的数据缓存能力，支持复杂的缓存策略和智能优化，是整个系统性能的重要基础。 