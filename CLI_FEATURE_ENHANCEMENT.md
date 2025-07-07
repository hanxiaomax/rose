# CLI功能增强：Topic统计信息显示

## 功能概述

在CLI命令中列出topic时，现在增加了一列显示每个topic的消息格式和总体大小信息。

## 新增功能

### 1. 增强的Topic列表显示

在使用`filter`命令时，现在会显示以下信息：

- **Status**: 是否被选中的状态（✓ 或 ○）
- **Topic**: Topic名称
- **Message Type**: 消息类型
- **Count**: 消息数量
- **Size**: 消息总大小

### 2. Parser新增方法

在`IBagParser`接口中新增了三个方法：

- `get_topic_sizes(bag_path: str) -> Dict[str, int]`: 获取每个topic的总大小
- `get_topic_stats(bag_path: str) -> Dict[str, Dict[str, int]]`: 获取综合统计信息
- `inspect_bag(bag_path: str) -> str`: 增强版本，显示详细统计信息

### 3. 统计信息总览

在topic列表底部显示：
- 选中的topic数量 / 总topic数量
- 选中的数据大小 / 总数据大小

## 使用示例

### 1. 使用dry-run模式查看统计信息

```bash
python -m roseApp.cli.filter tests/demo.bag output/ --topics /tf --dry-run
```

输出示例：
```
Topic selection:
───────────────────────────────────────────────────────────────
Status Topic                          Message Type                 Count     Size      
───────────────────────────────────────────────────────────────
✓ /tf                                tf2_msgs/msg/TFMessage       1986      182.3KB
○ /image_raw                         sensor_msgs/msg/Image        600       410.2MB
○ /gps/fix                           sensor_msgs/msg/NavSatFix    146       17.0KB
───────────────────────────────────────────────────────────────
Selected: 1 / 17 topics, 182.3KB / 695.5MB data
```

### 2. 查看bag文件详细信息

```bash
python -c "
from roseApp.core.parser import RosbagsBagParser
parser = RosbagsBagParser()
print(parser.inspect_bag('tests/demo.bag'))
"
```

输出示例：
```
Topics in tests/demo.bag:
Topic                               Message Type                        Count      Size      
------------------------------------------------------------------------------------------
/tf                                 tf2_msgs/msg/TFMessage              1986       182.3KB   
/image_raw                          sensor_msgs/msg/Image               600        410.2MB   
/gps/fix                            sensor_msgs/msg/NavSatFix           146        17.0KB    
------------------------------------------------------------------------------------------
Total: 17 topics, 5390 messages, 695.5MB

Time range: 17/03/22 02:37:58 - 17/03/22 02:38:17
```

### 3. 编程接口使用

```python
from roseApp.core.parser import RosbagsBagParser

parser = RosbagsBagParser()

# 获取topic大小信息
topic_sizes = parser.get_topic_sizes('tests/demo.bag')
print(f"/tf topic size: {topic_sizes['/tf']} bytes")

# 获取综合统计信息
topic_stats = parser.get_topic_stats('tests/demo.bag')
print(f"/tf: {topic_stats['/tf']['count']} messages, {topic_stats['/tf']['size']} bytes")
```

## 技术实现

### 1. 高性能数据获取

- 使用`rosbags`库的`AnyReader`进行零拷贝数据读取
- 通过`rawdata`长度计算消息大小
- 一次性获取所有统计信息，避免重复读取

### 2. 大小格式化

自动将字节大小转换为人类可读格式（B, KB, MB, GB, TB）：

```python
def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"
```

### 3. 向后兼容性

- 保持现有API接口不变
- 为legacy parser也提供相同功能
- 新功能对现有代码完全透明

## 性能优化

- 使用`get_topic_stats()`一次性获取所有统计信息
- 避免多次调用`get_message_counts()`和`get_topic_sizes()`
- 在CLI中缓存统计信息，避免重复计算

## 测试覆盖

新增了以下测试用例：
- `test_get_topic_sizes`: 测试topic大小获取功能
- `test_get_topic_stats`: 测试综合统计信息获取
- `test_topic_stats_consistency`: 测试不同方法之间的一致性

所有测试都通过了验证，确保功能稳定可靠。 