# Parser 模块使用指南

## 概述

Parser 模块提供了Rose的智能解析器管理系统，自动选择最优的ROS bag解析器，支持rosbags高性能解析和legacy兼容性，具有健康检查和自动降级功能。

## 主要特性

- ✅ **智能选择**: 自动选择最优解析器 (rosbags → legacy)
- ✅ **健康检查**: 实时监控解析器状态和性能
- ✅ **自动降级**: 解析器故障时自动切换到备用解析器
- ✅ **高性能**: rosbags解析器提供70%+性能提升
- ✅ **兼容性**: 完全兼容legacy rosbag格式
- ✅ **统一接口**: 屏蔽底层实现差异，提供一致的API

## 核心类型

### ParserType (枚举)

```python
class ParserType(Enum):
    ROSBAGS = "rosbags"      # 高性能rosbags解析器
    LEGACY = "legacy"        # 兼容性legacy解析器
    AUTO = "auto"           # 自动选择
```

### ParserHealth (数据类)

```python
@dataclass
class ParserHealth:
    parser_type: ParserType     # 解析器类型
    is_available: bool         # 是否可用
    performance_score: float   # 性能评分 (0-100)
    error_rate: float         # 错误率 (0-1)
    last_check: float         # 上次检查时间
    status_message: str       # 状态信息
```

### IBagParser (抽象接口)

```python
class IBagParser:
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """加载bag文件基本信息"""
    
    def get_message_counts(self, bag_path: str) -> Dict[str, int]:
        """获取消息数量统计"""
    
    def read_messages(self, bag_path: str, topics: List[str] = None) -> Iterator:
        """读取消息迭代器"""
    
    def filter_bag(self, input_path: str, output_path: str, topics: List[str], **kwargs):
        """过滤bag文件"""
    
    def get_parser_info(self) -> Dict[str, Any]:
        """获取解析器信息"""
```

## 主要接口

### create_best_parser() - 创建最优解析器

```python
def create_best_parser() -> IBagParser:
    """创建性能最佳的可用解析器"""
```

### get_parser_health() - 获取解析器健康状态

```python
def get_parser_health(parser_type: ParserType) -> ParserHealth:
    """获取指定解析器的健康状态"""
```

### get_all_parser_health() - 获取所有解析器状态

```python
def get_all_parser_health() -> Dict[ParserType, ParserHealth]:
    """获取所有解析器的健康状态"""
```

## 使用示例

### 基础解析器使用

```python
from pathlib import Path
from roseApp.core.parser import create_best_parser

# 创建最优解析器
parser = create_best_parser()

# 获取解析器信息
info = parser.get_parser_info()
print(f"使用解析器: {info['type']}")
print(f"版本: {info['version']}")
print(f"性能评分: {info['performance_score']}")

# 加载bag文件
bag_path = "example.bag"
topics, connections, time_range = parser.load_bag(bag_path)

print(f"话题数量: {len(topics)}")
print(f"时间范围: {time_range}")

# 获取消息统计
message_counts = parser.get_message_counts(bag_path)
for topic, count in message_counts.items():
    print(f"{topic}: {count} messages")
```

### 健康检查和监控

```python
from roseApp.core.parser import get_all_parser_health, ParserType

# 获取所有解析器健康状态
health_status = get_all_parser_health()

for parser_type, health in health_status.items():
    print(f"\n解析器: {parser_type.value}")
    print(f"可用性: {'✓' if health.is_available else '✗'}")
    print(f"性能评分: {health.performance_score:.1f}/100")
    print(f"错误率: {health.error_rate:.1%}")
    print(f"状态: {health.status_message}")

# 检查特定解析器
from roseApp.core.parser import get_parser_health

rosbags_health = get_parser_health(ParserType.ROSBAGS)
if rosbags_health.is_available:
    print("rosbags解析器可用，性能优异")
else:
    print(f"rosbags解析器不可用: {rosbags_health.status_message}")
```

### 读取消息数据

```python
# 读取所有话题的消息
for timestamp, msg_data in parser.read_messages(bag_path):
    print(f"时间戳: {timestamp}, 消息类型: {type(msg_data)}")
    break  # 只显示第一条消息

# 读取特定话题的消息
target_topics = ["/camera/image", "/lidar/points"]
for timestamp, msg_data in parser.read_messages(bag_path, target_topics):
    print(f"话题消息: {timestamp}")
    # 处理消息数据
    break
```

### 过滤bag文件

```python
# 基础过滤
input_path = "input.bag"
output_path = "filtered.bag"
topics_to_keep = ["/camera/image", "/tf"]

try:
    parser.filter_bag(
        input_path=input_path,
        output_path=output_path,
        topics=topics_to_keep
    )
    print("过滤完成")
except Exception as e:
    print(f"过滤失败: {e}")

# 高级过滤配置
parser.filter_bag(
    input_path=input_path,
    output_path=output_path,
    topics=topics_to_keep,
    compression="bz2",           # 压缩格式
    time_range=(start_time, end_time),  # 时间范围
    overwrite=True              # 覆盖现有文件
)
```

### 解析器性能比较

```python
import time
from roseApp.core.parser import RosbagParser, LegacyParser

def benchmark_parsers(bag_path: str):
    """比较不同解析器的性能"""
    
    # 测试rosbags解析器
    try:
        rosbags_parser = RosbagParser()
        start_time = time.time()
        topics, _, _ = rosbags_parser.load_bag(bag_path)
        rosbags_time = time.time() - start_time
        rosbags_available = True
    except Exception as e:
        rosbags_time = float('inf')
        rosbags_available = False
        print(f"rosbags解析器不可用: {e}")
    
    # 测试legacy解析器
    try:
        legacy_parser = LegacyParser()
        start_time = time.time()
        topics, _, _ = legacy_parser.load_bag(bag_path)
        legacy_time = time.time() - start_time
        legacy_available = True
    except Exception as e:
        legacy_time = float('inf')
        legacy_available = False
        print(f"legacy解析器不可用: {e}")
    
    # 比较结果
    if rosbags_available and legacy_available:
        improvement = (legacy_time - rosbags_time) / legacy_time * 100
        print(f"rosbags解析器性能提升: {improvement:.1f}%")
        print(f"rosbags耗时: {rosbags_time:.3f}s")
        print(f"legacy耗时: {legacy_time:.3f}s")
    
    return {
        'rosbags': {'time': rosbags_time, 'available': rosbags_available},
        'legacy': {'time': legacy_time, 'available': legacy_available}
    }

# 运行性能测试
results = benchmark_parsers("test.bag")
```

### 自定义解析器选择

```python
from roseApp.core.parser import ParserManager

# 创建解析器管理器
manager = ParserManager()

# 强制使用特定解析器
try:
    rosbags_parser = manager.get_parser(ParserType.ROSBAGS)
    print("使用rosbags解析器")
except Exception:
    print("rosbags不可用，使用legacy解析器")
    legacy_parser = manager.get_parser(ParserType.LEGACY)

# 根据性能要求选择
performance_threshold = 80  # 性能评分阈值

best_parser = None
for parser_type in [ParserType.ROSBAGS, ParserType.LEGACY]:
    health = get_parser_health(parser_type)
    if health.is_available and health.performance_score >= performance_threshold:
        best_parser = manager.get_parser(parser_type)
        print(f"选择解析器: {parser_type.value}")
        break

if not best_parser:
    print("没有满足性能要求的解析器")
```

## 高级功能

### 解析器健康监控

```python
import time
from roseApp.core.parser import get_all_parser_health

def monitor_parser_health():
    """持续监控解析器健康状态"""
    while True:
        health_status = get_all_parser_health()
        
        print(f"\n时间: {time.strftime('%H:%M:%S')}")
        
        for parser_type, health in health_status.items():
            status_icon = "✓" if health.is_available else "✗"
            print(f"{parser_type.value}: {status_icon} "
                  f"性能{health.performance_score:.0f} "
                  f"错误率{health.error_rate:.1%}")
        
        # 检查是否需要切换解析器
        rosbags_health = health_status.get(ParserType.ROSBAGS)
        if rosbags_health and rosbags_health.error_rate > 0.1:
            print("警告: rosbags解析器错误率过高，建议切换到legacy")
        
        time.sleep(30)  # 每30秒检查一次

# 在后台运行监控
import threading
monitor_thread = threading.Thread(target=monitor_parser_health, daemon=True)
monitor_thread.start()
```

### 解析器故障恢复

```python
from roseApp.core.parser import create_best_parser

def robust_parsing(bag_path: str):
    """具有故障恢复能力的解析"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 创建最佳可用解析器
            parser = create_best_parser()
            
            # 尝试解析
            topics, connections, time_range = parser.load_bag(bag_path)
            
            print(f"解析成功，使用解析器: {parser.get_parser_info()['type']}")
            return topics, connections, time_range
            
        except Exception as e:
            retry_count += 1
            print(f"解析失败 (尝试 {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                print("等待2秒后重试...")
                time.sleep(2)
    
    raise Exception(f"解析失败，已重试{max_retries}次")

# 使用故障恢复解析
try:
    topics, connections, time_range = robust_parsing("problematic.bag")
    print(f"成功解析，发现{len(topics)}个话题")
except Exception as e:
    print(f"最终解析失败: {e}")
```

### 批量文件处理

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

async def process_multiple_bags(bag_paths: List[Path]):
    """并发处理多个bag文件"""
    
    def process_single_bag(bag_path: Path):
        try:
            parser = create_best_parser()
            topics, connections, time_range = parser.load_bag(str(bag_path))
            
            return {
                'path': bag_path,
                'success': True,
                'topic_count': len(topics),
                'parser_type': parser.get_parser_info()['type']
            }
        except Exception as e:
            return {
                'path': bag_path,
                'success': False,
                'error': str(e)
            }
    
    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=4) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, process_single_bag, bag_path)
            for bag_path in bag_paths
        ]
        
        results = await asyncio.gather(*tasks)
    
    # 统计结果
    successful = sum(1 for r in results if r['success'])
    print(f"处理完成: {successful}/{len(results)} 成功")
    
    for result in results:
        if result['success']:
            print(f"✓ {result['path'].name}: {result['topic_count']} topics "
                  f"({result['parser_type']})")
        else:
            print(f"✗ {result['path'].name}: {result['error']}")
    
    return results

# 运行批量处理
bag_files = [Path(f"bag_{i}.bag") for i in range(5)]
results = asyncio.run(process_multiple_bags(bag_files))
```

## 最佳实践

### 1. 解析器选择策略

```python
def choose_parser_strategy():
    """根据环境选择最佳解析器策略"""
    health_status = get_all_parser_health()
    
    # 优先使用rosbags (高性能)
    rosbags_health = health_status.get(ParserType.ROSBAGS)
    if rosbags_health and rosbags_health.is_available and rosbags_health.performance_score > 70:
        return ParserType.ROSBAGS
    
    # 降级到legacy (兼容性)
    legacy_health = health_status.get(ParserType.LEGACY)
    if legacy_health and legacy_health.is_available:
        return ParserType.LEGACY
    
    raise Exception("没有可用的解析器")
```

### 2. 错误处理

```python
def safe_parse_with_fallback(bag_path: str):
    """安全解析，带自动降级"""
    parsers_to_try = [ParserType.ROSBAGS, ParserType.LEGACY]
    
    for parser_type in parsers_to_try:
        try:
            health = get_parser_health(parser_type)
            if not health.is_available:
                continue
                
            parser = create_parser(parser_type)
            return parser.load_bag(bag_path)
            
        except Exception as e:
            print(f"{parser_type.value}解析器失败: {e}")
            continue
    
    raise Exception("所有解析器都失败了")
```

### 3. 性能监控

```python
def track_parser_performance():
    """跟踪解析器性能指标"""
    metrics = {
        'total_parses': 0,
        'successful_parses': 0,
        'parser_usage': {},
        'average_time': 0
    }
    
    def parse_with_metrics(bag_path: str):
        start_time = time.time()
        metrics['total_parses'] += 1
        
        try:
            parser = create_best_parser()
            parser_type = parser.get_parser_info()['type']
            
            result = parser.load_bag(bag_path)
            
            # 更新指标
            metrics['successful_parses'] += 1
            metrics['parser_usage'][parser_type] = metrics['parser_usage'].get(parser_type, 0) + 1
            
            parse_time = time.time() - start_time
            metrics['average_time'] = (metrics['average_time'] + parse_time) / 2
            
            return result
            
        except Exception as e:
            print(f"解析失败: {e}")
            raise
    
    return parse_with_metrics, metrics
```

### 4. 资源管理

```python
class ManagedParser:
    """带资源管理的解析器包装器"""
    
    def __init__(self):
        self.parser = None
        self.last_health_check = 0
        self.health_check_interval = 300  # 5分钟
    
    def get_parser(self):
        current_time = time.time()
        
        # 定期健康检查
        if (current_time - self.last_health_check) > self.health_check_interval:
            self._check_and_update_parser()
            self.last_health_check = current_time
        
        if not self.parser:
            self.parser = create_best_parser()
        
        return self.parser
    
    def _check_and_update_parser(self):
        """检查并更新解析器"""
        if self.parser:
            current_type = self.parser.get_parser_info()['type']
            health = get_parser_health(ParserType(current_type))
            
            # 如果当前解析器健康度下降，尝试切换
            if health.performance_score < 50 or health.error_rate > 0.2:
                print("解析器性能下降，尝试切换...")
                self.parser = create_best_parser()
    
    def __del__(self):
        # 清理资源
        if hasattr(self.parser, 'cleanup'):
            self.parser.cleanup()

# 使用托管解析器
managed_parser = ManagedParser()
parser = managed_parser.get_parser()
```

## 内部实现

### 解析器层次结构

```
ParserManager
├── RosbagParser (优先)
│   ├── 高性能解析
│   ├── 现代Python API
│   └── 70%+ 性能提升
└── LegacyParser (降级)
    ├── 兼容性保证
    ├── 传统rosbag接口
    └── 稳定可靠
```

### 健康检查机制

- **性能评分**: 基于解析速度和资源使用
- **错误率监控**: 跟踪解析失败率
- **可用性检测**: 检查依赖和运行时环境
- **自动降级**: 故障时自动切换解析器

### 智能选择算法

1. **环境检测**: 检查rosbags库可用性
2. **性能测试**: 小样本性能基准测试  
3. **健康评估**: 综合性能和错误率
4. **自动选择**: 选择最优可用解析器

这个解析器模块为Rose提供了智能、高性能、可靠的bag文件解析能力，自动处理不同解析器间的差异，为上层应用提供统一的接口。 