# Rose 无头引擎设计 v5.0

## 文档信息

- **版本**: 5.0 (纯 NDJSON 架构)
- **状态**: 设计与实施指南
- **日期**: 2025-10-08
- **作者**: AI Assistant

---

## 核心架构概览

### 设计哲学

Rose 采用**纯事件驱动架构**，完全面向机器可读输出：

```
┌─────────────────────────────────────────────────┐
│              Rose CLI Application               │
└───────────────┬─────────────────────────────────┘
                │
        ┌───────▼────────┐
        │  EventEmitter  │  (Pure NDJSON)
        │                │
        └───────┬────────┘
                │
                ▼
          stdout (NDJSON)
            一行一事件
```

### 核心原则

1. **纯 NDJSON 输出**: 所有输出均为结构化 JSON 事件流
2. **无人类可读模式**: 移除所有格式化输出，专注机器接口
3. **事件驱动**: 统一的事件类型与字段规范
4. **前端渲染**: 所有显示逻辑由前端负责
5. **零迭代输出**: CLI 不循环打印，只发射聚合数据

### 关键组件

1. **EventEmitter** (`roseApp/core/event_emitter.py`)
   - 纯 NDJSON 事件发射器
   - 统一事件 API: emit_progress, emit_partial, emit_done, emit_error
   - 直接写入 stdout，每行一个 JSON 对象

2. **CLI Commands** (`roseApp/cli/`)
   - **load**: 加载 bag 文件到缓存
   - **extract**: 从 bag 提取 topic
   - **compress**: 压缩 bag 文件
   - **inspect**: 分析 bag 内容
   - **cache**: 缓存管理
   - **config**: 配置管理

### 当前问题与目标

**当前状态**:
- ❌ 使用 OutputEngine 双模式（NDJSON + Prettify）
- ❌ Message API 进行迭代输出（逐行打印）
- ❌ 混合输出模式，前端难以处理

**目标状态**:
- ✅ 重命名为 EventEmitter，单一职责
- ✅ 仅支持 NDJSON 输出
- ✅ 移除 Message API
- ✅ 所有数据通过事件聚合发射
- ✅ 前端完全控制渲染

---

## NDJSON 事件协议 v1-min

### 协议总览

**Rose NDJSON Protocol v1-min** - 简化通用版本

- **编码**: UTF-8，每行一个完整 JSON 对象（NDJSON）
- **输出流**: `stdout` → 事件；`stderr` → 日志
- **时间格式**: ISO8601 UTC（如 `2025-10-08T10:00:00.123Z`）
- **退出约束**: 每次执行以 `done` 或 `error` 结束

### 事件基础结构

所有事件遵循统一格式：

```json
{
  "event": "<事件类型>",
  "timestamp": "<ISO8601_UTC_带Z后缀>",
  "protocol": {
    "name": "rose.ndjson",
    "version": "1.0"
  },
  "context": {
    "command": "load",
    "trace_id": "...",
    "run_id": "..."
  },
  "payload": {
    // 事件特定载荷
  }
}
```

### 通用字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event` | string | ✅ | 事件类型（4种之一） |
| `timestamp` | string | ✅ | UTC 时间戳 |
| `protocol` | object | 🚫 | 协议元信息 `{"name": "rose.ndjson", "version": "1.0"}` |
| `context` | object | 🚫 | 命令上下文 `{"command": "load", "trace_id": "...", "run_id": "..."}` |
| `payload` | object | 依事件 | 各事件载荷（见下） |

### 四种事件类型

| event | 用途 |
|-------|------|
| `progress` | 进度更新 |
| `data` | 中间结果或输出数据 |
| `done` | 成功结束 |
| `error` | 失败结束 |

---

#### 1. progress（进度事件）

**用途**: 报告长时间操作的进度

**结构**:
```json
{
  "event": "progress",
  "timestamp": "2025-10-08T10:00:00.123Z",
  "payload": {
    "percent": 75.5,
    "message": "Processing bag files",
    "step": 3,
    "total_steps": 4
  }
}
```

**payload 字段**:
- `percent` (float, 必需): 进度百分比 0-100，单调递增
- `message` (string, 可选): 描述性消息
- `step` (int, 可选): 当前步骤编号（从 1 开始）
- `total_steps` (int, 可选): 总步骤数

---

#### 2. data（数据事件）

**用途**: 传输中间结果、最终数据或简单列表。不细分语义类型，所有结构化数据均可放入。

**结构**:
```json
{
  "event": "data",
  "timestamp": "2025-10-08T10:00:01.456Z",
  "payload": {
    "label": "found_bags",
    "data": [
      {"path": "a.bag", "size_mb": 12.3},
      {"path": "b.bag", "size_mb": 45.6}
    ],
    "count": 2
  }
}
```

**payload 字段**:
- `label` (string, 可选): 用于区分不同阶段输出（如 `"topics"`, `"summary"`, `"metadata"`）
- `data` (any, 必需): 可为对象或数组，包含实际数据
- `count` (int, 可选): 统计信息（如列表长度）

**常见 label 值**:
- `found_bags`: 发现的 bag 文件列表
- `topics`: bag 中的 topic 信息
- `metadata`: bag 元数据
- `analysis`: 分析结果
- `cache_info`: 缓存信息
- `results`: 操作结果详情

---

#### 3. done（完成事件）

**用途**: 标志操作成功完成，包含最终聚合结果

**结构**:
```json
{
  "event": "done",
  "timestamp": "2025-10-08T10:00:05.789Z",
  "payload": {
    "summary": {
      "processed": 10,
      "succeeded": 8,
      "failed": 2,
      "elapsed_time": 4.12
    }
  }
}
```

**payload 字段**:
- `summary` (object, 必需): 最终聚合结果
- summary 中的具体字段由操作类型决定
- 退出码应为 0

---

#### 4. error（错误事件）

**用途**: 报告操作失败及诊断信息

**结构**:
```json
{
  "event": "error",
  "timestamp": "2025-10-08T10:00:02.345Z",
  "payload": {
    "code": "BAG_NOT_FOUND",
    "message": "Bag file not found: demo.bag",
    "details": {
      "path": "/path/to/demo.bag",
      "suggestions": ["Check file path", "Ensure file exists"]
    }
  }
}
```

**payload 字段**:
- `code` (string, 必需): 机器可读错误码（大写蛇形命名）
- `message` (string, 必需): 人类可读错误消息
- `details` (object, 可选): 额外诊断信息
- 退出码应为非 0

**常见错误码**:
- `BAG_NOT_FOUND`: Bag 文件不存在
- `INVALID_ARGUMENT`: 无效命令参数
- `CACHE_ERROR`: 缓存操作失败
- `PARSE_ERROR`: Bag 解析失败
- `PERMISSION_DENIED`: 文件权限错误
- `NO_COMMAND`: 未指定命令

### 事件生命周期

```
操作开始
   │
   ├─► progress (0%)
   │
   ├─► data (中间结果)
   ├─► progress (25%)
   │
   ├─► data (更多中间结果)
   ├─► progress (50%)
   │
   ├─► progress (100%)
   │
   └─► done (最终结果)
         或
       error (失败)
```

### 协议规则

1. **终止规则**: 每个操作必须以 `done` 或 `error` 结束（二选一）
2. **进度规则**: Progress 事件的 percent 应单调递增
3. **数据规则**: Data 事件可在任何时刻发射多次
4. **时间规则**: 时间戳必须是 ISO8601 UTC 格式，带 'Z' 后缀
5. **退出规则**: 成功退出码为 0（done），失败为非 0（error）
6. **序列化规则**: 所有字段必须可 JSON 序列化，不得出现 `NaN` / `Infinity`
7. **输出规则**: `stdout` 只包含 JSON 行，禁止混入文本输出

### 完整示例

一次典型的命令执行：

```json
{"event":"progress","timestamp":"2025-10-08T10:00:00.000Z","payload":{"percent":0,"message":"Starting"}}
{"event":"data","timestamp":"2025-10-08T10:00:01.000Z","payload":{"label":"found_files","data":["a.bag","b.bag"],"count":2}}
{"event":"progress","timestamp":"2025-10-08T10:00:02.000Z","payload":{"percent":50,"message":"Processing"}}
{"event":"data","timestamp":"2025-10-08T10:00:03.000Z","payload":{"label":"results","data":{"files_ok":2,"duration":2.5}}}
{"event":"done","timestamp":"2025-10-08T10:00:04.000Z","payload":{"summary":{"processed":2,"elapsed_time":2.5}}}
```

---

## EventEmitter API 参考

### 模块位置

```python
# 位置：roseApp/core/event_emitter.py
from roseApp.core.event_emitter import EventEmitter, init_emitter, get_emitter
```

### 初始化

```python
# 在应用启动时初始化（rose.py 中）
from roseApp.core.event_emitter import init_emitter

init_emitter()  # 创建全局 emitter 实例

# 在命令中获取
from roseApp.core.event_emitter import get_emitter

emitter = get_emitter()
```

### 核心方法

#### emit_progress()

发射进度更新事件。

```python
def emit_progress(
    percent: float,              # 0-100
    message: str = "",           # 描述消息
    step: Optional[int] = None,
    total_steps: Optional[int] = None
) -> None
```

**输出格式**:
```json
{
  "event": "progress",
  "timestamp": "2025-10-08T10:00:00.123Z",
  "payload": {
    "percent": 75.5,
    "message": "Processing files",
    "step": 2,
    "total_steps": 3
  }
}
```

**示例**:
```python
emitter.emit_progress(0, "Starting operation", step=1, total_steps=3)
emitter.emit_progress(50, "Processing files", step=2, total_steps=3)
emitter.emit_progress(100, "Complete", step=3, total_steps=3)
```

#### emit_data()

发射数据事件（中间结果或最终数据）。

```python
def emit_data(
    data: Any,                    # 数据载荷（必须可 JSON 序列化）
    label: Optional[str] = None,  # 数据标签
    count: Optional[int] = None   # 可选统计信息
) -> None
```

**输出格式**:
```json
{
  "event": "data",
  "timestamp": "2025-10-08T10:00:01.456Z",
  "payload": {
    "label": "found_bags",
    "data": [...],
    "count": 3
  }
}
```

**示例**:
```python
# 发射文件列表
emitter.emit_data(
    data=[
        {"path": "a.bag", "size_mb": 12.3},
        {"path": "b.bag", "size_mb": 45.6}
    ],
    label="found_bags",
    count=2
)

# 发射单个对象
emitter.emit_data(
    data={
        "path": "/path/to/demo.bag",
        "duration": 120.5,
        "topics_count": 15
    },
    label="metadata"
)
```

#### emit_done()

发射操作完成事件。

```python
def emit_done(
    summary: Dict[str, Any]  # 最终聚合结果
) -> None
```

**输出格式**:
```json
{
  "event": "done",
  "timestamp": "2025-10-08T10:00:05.789Z",
  "payload": {
    "summary": {
      "processed": 10,
      "succeeded": 8,
      "failed": 2,
      "elapsed_time": 4.12
    }
  }
}
```

**示例**:
```python
emitter.emit_done({
    "processed": 10,
    "succeeded": 8,
    "failed": 2,
    "elapsed_time": 12.5
})
```

#### emit_error()

发射错误事件。

```python
def emit_error(
    code: str,                      # 错误码（大写蛇形）
    message: str,                   # 错误消息
    details: Optional[Dict] = None  # 额外上下文
) -> None
```

**输出格式**:
```json
{
  "event": "error",
  "timestamp": "2025-10-08T10:00:02.345Z",
  "payload": {
    "code": "BAG_NOT_FOUND",
    "message": "Bag file not found: demo.bag",
    "details": {
      "path": "/path/to/demo.bag",
      "suggestions": ["Check file path"]
    }
  }
}
```

**示例**:
```python
emitter.emit_error(
    "BAG_NOT_FOUND",
    "Cannot find bag file: demo.bag",
    details={
        "path": str(bag_path),
        "cwd": os.getcwd(),
        "suggestions": ["Check the file path", "Ensure file exists"]
    }
)
```

### 可选特性

#### 设置命令上下文

```python
def set_context(
    command: str,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> None
```

设置后，所有事件将包含 context 字段。

**示例**:
```python
emitter.set_context("load", trace_id="abc123", run_id="run-456")
```

---

## 各命令无头化设计

### 设计指导原则

对每个命令：
1. **禁止迭代输出** - 不循环打印，用数组聚合
2. **发射结构化数据** - 使用 partial/done 事件
3. **前端负责渲染** - CLI 不关心显示格式
4. **适度进度报告** - 长操作使用 emit_progress()
5. **思考事件流** - 前端需要什么数据？何时需要？

---

### 1. load 命令

**当前问题**:
- 逐行打印发现的文件
- 逐个打印加载状态
- 混合使用 Message API 和 emit_done

**无头化方案**:

```python
def load(...):
    emitter = get_emitter()
    emitter.set_context("load")
    
    # 阶段1: 发现文件（data 事件）
    emitter.emit_data(
        data=[
            {
                "path": str(bag),
                "size_mb": bag.stat().st_size / 1024 / 1024,
                "exists": bag.exists()
            }
            for bag in valid_bags
        ],
        label="found_bags",
        count=len(valid_bags)
    )
    
    # 阶段2: 加载进度
    for i, bag in enumerate(valid_bags):
        percent = (i / len(valid_bags)) * 100
        emitter.emit_progress(
            percent, 
            f"Loading {bag.name}", 
            step=i+1, 
            total_steps=len(valid_bags)
        )
        # ... 执行加载工作 ...
    
    # 阶段3: 详细结果（data 事件）
    emitter.emit_data(
        data=[
            {
                "path": str(bag),
                "status": "loaded",  # loaded | cached | error
                "elapsed": 1.2,
                "topics_count": 15,
                "error": None
            }
            for bag, status, elapsed in all_results
        ],
        label="results",
        count=len(all_results)
    )
    
    # 阶段4: 完成（done 事件，包含汇总）
    emitter.emit_done({
        "loaded_files": loaded_count,
        "cached_files": cached_count,
        "failed_files": error_count,
        "total_ready": total_ready,
        "elapsed_time": total_time
    })
```

**输出示例**:
```json
{"event":"data","timestamp":"...","payload":{"label":"found_bags","data":[{"path":"a.bag","size_mb":12.3}],"count":1}}
{"event":"progress","timestamp":"...","payload":{"percent":0,"message":"Loading a.bag","step":1,"total_steps":1}}
{"event":"progress","timestamp":"...","payload":{"percent":100,"message":"Loading a.bag","step":1,"total_steps":1}}
{"event":"data","timestamp":"...","payload":{"label":"results","data":[{"path":"a.bag","status":"loaded","elapsed":1.2}],"count":1}}
{"event":"done","timestamp":"...","payload":{"summary":{"loaded_files":1,"cached_files":0,"failed_files":0,"total_ready":1,"elapsed_time":1.5}}}
```

**关键变化**:
- 移除所有 `Message.info()` 和循环打印
- 使用 `emit_data(label="found_bags")` 发射文件列表
- 使用 `emit_data(label="results")` 发射详细结果
- `emit_done()` 只包含汇总信息

---

### 2. extract 命令

**当前问题**:
- 逐行打印发现的 bag
- 逐行打印选中的 topic
- 分散的状态消息

**无头化方案**:

```python
def extract(...):
    emitter = get_emitter()
    emitter.set_context("extract")
    
    # 阶段1: 发现输入 bag（data 事件）
    emitter.emit_data(
        data=[
            {
                "path": str(bag),
                "size_mb": bag.stat().st_size / 1024 / 1024,
                "topics_count": len(bag_info.topics)
            }
            for bag in valid_bags
        ],
        label="found_bags",
        count=len(valid_bags)
    )
    
    # 阶段2: Topic 选择（data 事件）
    emitter.emit_data(
        data={
            "total_topics": len(all_topics),
            "selected_count": len(selected_topics),
            "selected": selected_topics,
            "method": "pattern" if pattern else "explicit",
            "pattern": pattern if pattern else None
        },
        label="topics"
    )
    
    # 阶段3: 提取进度
    for i, bag in enumerate(valid_bags):
        percent = (i / len(valid_bags)) * 100
        emitter.emit_progress(
            percent,
            f"Extracting from {bag.name}",
            step=i+1,
            total_steps=len(valid_bags)
        )
        # ... 执行提取工作 ...
    
    # 阶段4: 详细结果（data 事件）
    emitter.emit_data(
        data=[
            {
                "input": str(bag),
                "output": str(output_bag),
                "topics_extracted": topic_count,
                "messages": msg_count,
                "size_mb": output_size,
                "status": "success"
            }
            for bag, output_bag, topic_count, msg_count, output_size in extraction_results
        ],
        label="results",
        count=len(extraction_results)
    )
    
    # 阶段5: 完成（done 事件，汇总）
    emitter.emit_done({
        "extracted_bags": success_count,
        "failed_bags": fail_count,
        "total_messages_extracted": total_msg_count,
        "total_output_size_mb": total_output_size,
        "compression": compression_type,
        "elapsed_time": total_time
    })
```

---

### 3. compress 命令

**当前问题**:
- 列出输入文件（迭代）
- 显示压缩设置（分散）
- 逐个显示压缩比

**无头化方案**:

```python
def compress(...):
    emitter = get_emitter()
    emitter.set_context("compress")
    
    # 阶段1: 压缩计划（data 事件）
    emitter.emit_data(
        data={
            "compression": compression_type,
            "total_input_size_mb": total_input_size,
            "bags": [
                {
                    "path": str(bag),
                    "size_mb": bag.stat().st_size / 1024 / 1024
                }
                for bag in bags
            ]
        },
        label="plan",
        count=len(bags)
    )
    
    # 阶段2: 压缩进度
    for i, bag in enumerate(bags):
        percent = (i / len(bags)) * 100
        emitter.emit_progress(
            percent,
            f"Compressing {bag.name}",
            step=i+1,
            total_steps=len(bags)
        )
        # ... 执行压缩 ...
    
    # 阶段3: 详细结果（data 事件）
    emitter.emit_data(
        data=[
            {
                "input": str(bag),
                "output": str(output),
                "original_mb": orig_size,
                "compressed_mb": comp_size,
                "ratio": (1 - comp_size/orig_size) * 100,
                "elapsed": elapsed,
                "status": "success"
            }
            for bag, output, orig_size, comp_size, elapsed in compression_results
        ],
        label="results",
        count=len(compression_results)
    )
    
    # 阶段4: 完成（done 事件，汇总）
    emitter.emit_done({
        "compressed_count": success_count,
        "failed_count": fail_count,
        "total_original_mb": total_original,
        "total_compressed_mb": total_compressed,
        "compression_ratio": (1 - total_compressed/total_original) * 100,
        "elapsed_time": total_time
    })
```

---

### 4. inspect 命令

**当前问题**:
- 逐行打印 topic 列表
- 复杂的表格格式化
- 字段分析分散输出

**无头化方案**:

```python
def inspect(...):
    emitter = get_emitter()
    emitter.set_context("inspect")
    
    # 阶段1: Bag 元数据（data 事件）
    emitter.emit_data(
        data={
            "path": str(bag_path),
            "size_mb": size_mb,
            "duration_sec": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "topics_count": len(topics),
            "messages_count": total_messages,
            "compression": compression_type,
            "version": bag_version
        },
        label="metadata"
    )
    
    # 阶段2: Topics 分析（data 事件）
    emitter.emit_data(
        data={
            "topics": [
                {
                    "name": topic.name,
                    "type": topic.msg_type,
                    "message_count": topic.msg_count,
                    "frequency_hz": topic.frequency,
                    "size_bytes": topic.size,
                    "size_mb": topic.size / 1024 / 1024,
                    "percentage": (topic.msg_count / total_messages) * 100,
                    "start_time": topic.start_time.isoformat(),
                    "end_time": topic.end_time.isoformat()
                }
                for topic in sorted_topics
            ],
            "sort_by": sort_by,
            "reverse": reverse_sort
        },
        label="topics",
        count=len(topics)
    )
    
    # 阶段3: 字段分析（data 事件，如果请求）
    if show_fields:
        emitter.emit_data(
            data={
                "topics": [
                    {
                        "topic": topic.name,
                        "message_type": topic.msg_type,
                        "fields": [
                            {
                                "name": field.name,
                                "type": field.type,
                                "count": field.count,
                                "nested": field.is_nested
                            }
                            for field in topic.fields
                        ]
                    }
                    for topic in topics_with_fields
                ]
            },
            label="fields",
            count=len(topics_with_fields)
        )
    
    # 阶段4: 完成（done 事件）
    emitter.emit_done({
        "bag": str(bag_path),
        "analyzed_topics": len(topics),
        "analyzed_messages": total_messages,
        "elapsed_time": elapsed
    })
```

---

### 5. cache 命令

**当前问题**:
- 逐行列出缓存条目
- 分散的统计信息

**无头化方案**:

```python
# cache info (默认子命令)
def cache_info(...):
    emitter = get_emitter()
    emitter.set_context("cache")
    
    # 发射缓存信息（data 事件，包含统计和条目）
    emitter.emit_data(
        data={
            "stats": {
                "total_entries": total,
                "memory_entries": memory_count,
                "disk_entries": disk_count,
                "total_size_mb": size_mb,
                "cache_dir": str(cache_dir)
            },
            "entries": [
                {
                    "key": key,
                    "bag_path": str(path),
                    "size_mb": size,
                    "created": created.isoformat(),
                    "last_accessed": accessed.isoformat(),
                    "location": "memory" or "disk",
                    "topics_count": topics_count,
                    "messages_count": msg_count
                }
                for key, entry in all_entries
            ]
        },
        label="cache_info",
        count=len(all_entries)
    )
    
    emitter.emit_done({"entries_count": len(all_entries)})

# cache clear
def cache_clear(...):
    emitter = get_emitter()
    emitter.set_context("cache")
    
    # 清除计划（data 事件）
    emitter.emit_data(
        data={
            "entries_to_clear": entries_count,
            "size_to_free_mb": size_mb,
            "bag_path": str(bag_path) if bag_path else "all"
        },
        label="clear_plan"
    )
    
    # 执行清除...
    
    # 完成
    emitter.emit_done({
        "cleared_entries": cleared_count,
        "freed_mb": freed_size
    })

# cache export
def cache_export(...):
    emitter = get_emitter()
    emitter.set_context("cache")
    
    # 导出计划（data 事件）
    emitter.emit_data(
        data={
            "output_file": output_file,
            "format": format,
            "entries_count": entries_count
        },
        label="export_plan"
    )
    
    # 执行导出...
    
    # 完成
    emitter.emit_done({
        "exported_file": output_file,
        "format": format,
        "entries_exported": count
    })
```

---

### 6. config 命令

**当前问题**:
- 逐行显示配置项
- 设置操作的反馈分散

**无头化方案**:

```python
# config show (默认)
def config_show(...):
    emitter = get_emitter()
    emitter.set_context("config")
    
    # 发射配置数据（data 事件）
    emitter.emit_data(
        data={
            "config": {
                "verbose_default": config.verbose_default,
                "parallel_workers": config.parallel_workers,
                "build_index_default": config.build_index_default,
                "cache_dir": str(config.cache_dir),
                "cache_max_size_mb": config.cache_max_size_mb,
                "compression_default": config.compression_default
            },
            "source": "user" if is_user_config else "default",
            "config_file": str(config_file)
        },
        label="config_data",
        count=len(config.dict())
    )
    
    emitter.emit_done({"config_keys": len(config.dict())})

# config set
def config_set(key: str, value: Any, ...):
    emitter = get_emitter()
    emitter.set_context("config")
    
    # 配置变更（data 事件）
    emitter.emit_data(
        data={
            "key": key,
            "old_value": old_val,
            "new_value": value,
            "config_file": str(config_file)
        },
        label="change"
    )
    
    # 应用更改...
    
    # 完成
    emitter.emit_done({
        "key": key,
        "value": value,
        "applied": True
    })

# config reset
def config_reset(key: Optional[str] = None, ...):
    emitter = get_emitter()
    emitter.set_context("config")
    
    # 重置计划（data 事件）
    emitter.emit_data(
        data={
            "keys_to_reset": [key] if key else "all",
            "affected_count": affected_count
        },
        label="reset_plan"
    )
    
    # 执行重置...
    
    # 完成
    emitter.emit_done({
        "reset_keys": reset_keys,
        "count": len(reset_keys)
    })
```

---

## 实施策略

### 第一阶段：重构 EventEmitter

**目标**: 创建新的 EventEmitter 类，替换 OutputEngine

**任务**:
1. 创建 `roseApp/core/event_emitter.py`
2. 实现 `EventEmitter` 类（只支持 NDJSON）
3. 实现全局单例管理：`init_emitter()`, `get_emitter()`, `reset_emitter()`
4. 编写单元测试

**EventEmitter 实现要点**:
```python
class EventEmitter:
    """Pure NDJSON event emitter for headless CLI"""
    
    def __init__(self):
        self._context = None  # Optional context (command, trace_id, run_id)
    
    def set_context(self, command: str, trace_id: Optional[str] = None, 
                   run_id: Optional[str] = None) -> None:
        """Set context for all subsequent events"""
        self._context = {
            "command": command,
            "trace_id": trace_id,
            "run_id": run_id
        }
    
    def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit event to stdout as NDJSON"""
        event = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload
        }
        
        # Add optional fields
        if self._context:
            event["context"] = self._context
        
        # Optional: add protocol info
        event["protocol"] = {
            "name": "rose.ndjson",
            "version": "1.0"
        }
        
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    
    def emit_progress(self, percent: float, message: str = "", 
                     step: Optional[int] = None, 
                     total_steps: Optional[int] = None) -> None:
        """Emit progress event"""
        payload = {"percent": percent}
        if message:
            payload["message"] = message
        if step is not None:
            payload["step"] = step
        if total_steps is not None:
            payload["total_steps"] = total_steps
        self._emit_event("progress", payload)
    
    def emit_data(self, data: Any, label: Optional[str] = None, 
                 count: Optional[int] = None) -> None:
        """Emit data event"""
        payload = {"data": data}
        if label:
            payload["label"] = label
        if count is not None:
            payload["count"] = count
        self._emit_event("data", payload)
    
    def emit_done(self, summary: Dict[str, Any]) -> None:
        """Emit done event"""
        self._emit_event("done", {"summary": summary})
    
    def emit_error(self, code: str, message: str, 
                  details: Optional[Dict] = None) -> None:
        """Emit error event"""
        payload = {
            "code": code,
            "message": message
        }
        if details:
            payload["details"] = details
        self._emit_event("error", payload)
```

### 第二阶段：更新 rose.py 入口

**目标**: 移除 OutputEngine，使用 EventEmitter

**任务**:
1. 移除 `--prettify` 参数
2. 移除 `OutputMode` 枚举
3. 使用 `init_emitter()` 初始化
4. 更新无命令错误处理

**示例**:
```python
@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True)
):
    """Rose CLI - ROS bag processing tool"""
    # Initialize event emitter
    from roseApp.core.event_emitter import init_emitter
    init_emitter()
    
    # Configure logging
    configure_logging(verbose)
    
    # Handle no command
    if ctx.invoked_subcommand is None:
        from roseApp.core.event_emitter import get_emitter
        emitter = get_emitter()
        emitter.emit_error(
            "NO_COMMAND",
            "No command specified. Use --help for usage."
        )
        raise typer.Exit(1)
```

### 第三阶段：重构各命令

**目标**: 移除 Message API，使用 EventEmitter

**优先级顺序**:
1. **cache** - 最简单，作为参考示例
2. **config** - 简单，数据结构清晰
3. **load** - 高频使用，重要参考
4. **inspect** - 数据密集，展示 partial 用法
5. **extract** - 复杂，多阶段操作
6. **compress** - 类似 extract

**重构模式**:

```python
# 之前：迭代输出
from ..ui.common_ui import Message

Message.info(f"Found {len(items)} items:")
for item in items:
    Message.muted(f"  {item}")

# 之后：事件发射
from ..core.event_emitter import get_emitter

emitter = get_emitter()
emitter.emit_data(
    data=[str(i) for i in items],
    label="found_items",
    count=len(items)
)
```

**需要移除的模式**:
- ❌ `Message.info()`, `Message.error()`, etc.
- ❌ `console.print()` 调用
- ❌ 循环中的输出语句
- ❌ Rich 表格、面板等格式化输出
- ❌ 进度条（使用 emit_progress 替代）

**保留的输出**:
- ✅ `emit_progress()` - 进度更新
- ✅ `emit_partial()` - 中间结果
- ✅ `emit_done()` - 最终结果
- ✅ `emit_error()` - 错误信息

### 第四阶段：清理旧代码

**目标**: 删除不再需要的文件和代码

**要删除的文件**:
```bash
# OutputEngine 相关
roseApp/core/output_engine.py  # 替换为 event_emitter.py

# Message API 相关
roseApp/ui/common_ui.py  # 移除或大幅简化（只保留工具函数）
```

**要更新的导入**:
```python
# 在所有命令文件中
# 之前
from ..core.output_engine import get_engine, OutputMode
from ..ui.common_ui import Message

# 之后
from ..core.event_emitter import get_emitter
```

### 第五阶段：测试

**目标**: 验证 NDJSON 输出正确性

**单元测试**:
```python
def test_event_emitter_progress(capsys):
    """Test progress event emission"""
    from roseApp.core.event_emitter import EventEmitter
    
    emitter = EventEmitter()
    emitter.emit_progress(50, "Testing", step=1, total_steps=2)
    
    captured = capsys.readouterr()
    event = json.loads(captured.out.strip())
    
    assert event["event"] == "progress"
    assert event["percent"] == 50
    assert event["message"] == "Testing"
    assert event["step"] == 1
    assert event["total_steps"] == 2
    assert "timestamp" in event

def test_load_command_ndjson(capsys):
    """Test load command produces valid NDJSON"""
    from roseApp.core.event_emitter import init_emitter, reset_emitter
    
    reset_emitter()
    init_emitter()
    
    # Run load command
    # ...
    
    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')
    
    # Validate all lines are JSON
    events = [json.loads(line) for line in lines]
    
    # Check event sequence
    assert any(e['event'] == 'partial' for e in events)
    assert events[-1]['event'] == 'done'
    
    # Check data structure
    done_event = events[-1]
    assert 'data' in done_event
    assert 'loaded_files' in done_event['data']
```

**集成测试**:
```bash
#!/bin/bash
# test_ndjson_output.sh

echo "Testing load command NDJSON output..."

output=$(rose load tests/demo.bag 2>&1)

# Verify all lines are valid JSON
echo "$output" | while read -r line; do
    if ! echo "$line" | jq . > /dev/null 2>&1; then
        echo "Invalid JSON: $line"
        exit 1
    fi
done

# Verify event types
if ! echo "$output" | jq -r '.event' | grep -q 'partial'; then
    echo "Missing partial events"
    exit 1
fi

if ! echo "$output" | jq -r '.event' | tail -1 | grep -qE '(done|error)'; then
    echo "Missing final done/error event"
    exit 1
fi

echo "All tests passed!"
```

### 第六阶段：文档更新

**目标**: 更新所有文档

**需要更新的文档**:
1. **README.md** - 移除 prettify 模式说明
2. **EVENTS_REFERENCE.md** - 创建完整事件参考
3. **命令帮助文本** - 更新 help 描述
4. **API 文档** - EventEmitter API 文档

---

## 前端集成指南

### 消费 NDJSON 流

**基础模式**:
```javascript
const { spawn } = require('child_process');

function executeRoseCommand(args) {
    const rose = spawn('rose', args);
    
    let buffer = '';
    
    rose.stdout.on('data', (data) => {
        buffer += data.toString();
        const lines = buffer.split('\n');
        
        // Keep last incomplete line in buffer
        buffer = lines.pop();
        
        for (const line of lines) {
            if (!line.trim()) continue;
            
            try {
                const event = JSON.parse(line);
                handleEvent(event);
            } catch (e) {
                console.error('Invalid JSON:', line, e);
            }
        }
    });
    
    rose.stderr.on('data', (data) => {
        console.error('stderr:', data.toString());
    });
    
    rose.on('close', (code) => {
        console.log(`Command exited with code ${code}`);
        if (code !== 0) {
            handleCommandFailure(code);
        }
    });
}

function handleEvent(event) {
    const { event: type, payload, timestamp, context } = event;
    
    switch (type) {
        case 'progress':
            updateProgress(payload.percent, payload.message, payload.step, payload.total_steps);
            break;
        
        case 'data':
            handleData(payload.label, payload.data, payload.count);
            break;
        
        case 'done':
            handleSuccess(payload.summary);
            break;
        
        case 'error':
            handleError(payload.code, payload.message, payload.details);
            break;
        
        default:
            console.warn(`Unknown event type: ${type}`);
    }
}
```

### 事件路由（按 label）

```javascript
function handleData(label, data, count) {
    const handlers = {
        // Load command
        'found_bags': (d) => {
            renderFileList(d);
            updateStatus(`Found ${count} bag files`);
        },
        'results': (d) => {
            renderProcessingResults(d);
        },
        
        // Extract command
        'found_bags': (d) => {
            renderBagList(d);
        },
        'topics': (d) => {
            renderSelectedTopics(d.selected);
            updateStatus(`Selected ${d.selected_count} topics`);
        },
        
        // Inspect command
        'metadata': (d) => {
            renderBagMetadata(d);
        },
        'topics': (d) => {
            renderTopicsTable(d.topics, d.sort_by);
        },
        'fields': (d) => {
            renderFieldAnalysis(d.topics);
        },
        
        // Compress command
        'plan': (d) => {
            renderCompressionPlan(d.bags, d.compression);
        },
        
        // Cache command
        'cache_info': (d) => {
            renderCacheStats(d.stats);
            renderCacheEntries(d.entries);
        },
        
        // Config command
        'config_data': (d) => {
            renderConfigTable(d.config);
        },
        'change': (d) => {
            showNotification(`Config updated: ${d.key} = ${d.new_value}`);
        }
    };
    
    const handler = handlers[label];
    if (handler) {
        handler(data);
    } else {
        console.warn(`Unknown data label: ${label}`, data);
    }
}
```

### 进度显示

```javascript
class ProgressManager {
    constructor() {
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.currentOperation = null;
    }
    
    updateProgress(percent, message, step, totalSteps) {
        this.progressBar.style.width = `${percent}%`;
        
        let text = message;
        if (step && totalSteps) {
            text = `[${step}/${totalSteps}] ${message}`;
        }
        
        this.progressText.textContent = text;
        
        if (percent >= 100) {
            setTimeout(() => this.hide(), 1000);
        }
    }
    
    show() {
        this.progressBar.parentElement.style.display = 'block';
    }
    
    hide() {
        this.progressBar.parentElement.style.display = 'none';
        this.reset();
    }
    
    reset() {
        this.progressBar.style.width = '0%';
        this.progressText.textContent = '';
    }
}
```

### 错误处理

```javascript
class ErrorHandler {
    constructor() {
        this.errorDialog = document.getElementById('error-dialog');
        this.errorMessages = {
            'BAG_NOT_FOUND': {
                title: '文件未找到',
                message: '指定的 bag 文件不存在'
            },
            'INVALID_ARGUMENT': {
                title: '参数错误',
                message: '提供的命令参数无效'
            },
            'CACHE_ERROR': {
                title: '缓存错误',
                message: '缓存操作失败'
            },
            'PARSE_ERROR': {
                title: '解析错误',
                message: 'Bag 文件解析失败'
            },
            'PERMISSION_DENIED': {
                title: '权限不足',
                message: '没有访问文件的权限'
            }
        };
    }
    
    handleError(code, message, details) {
        const errorInfo = this.errorMessages[code] || {
            title: '错误',
            message: '操作失败'
        };
        
        // Show error dialog
        this.showErrorDialog(
            errorInfo.title,
            message,
            details
        );
        
        // Log for debugging
        console.error('Rose Error:', {
            code,
            message,
            details,
            timestamp: new Date().toISOString()
        });
    }
    
    showErrorDialog(title, message, details) {
        this.errorDialog.querySelector('.title').textContent = title;
        this.errorDialog.querySelector('.message').textContent = message;
        
        // Show suggestions if available
        if (details?.suggestions) {
            const suggestionsList = this.errorDialog.querySelector('.suggestions');
            suggestionsList.innerHTML = '';
            details.suggestions.forEach(s => {
                const li = document.createElement('li');
                li.textContent = s;
                suggestionsList.appendChild(li);
            });
            suggestionsList.style.display = 'block';
        }
        
        this.errorDialog.style.display = 'block';
    }
}
```

---

## 最佳实践

### CLI 命令开发者

1. **思考事件而非输出**
   - 设计命令时先规划事件流
   - 确定需要哪些 partial 事件
   - 明确 done 事件应包含什么数据

2. **禁止迭代输出**
   - 永远不在循环中发射事件（除了 progress）
   - 收集数据到数组，一次性在 partial/done 中发射
   - 让前端决定如何显示列表/表格

3. **提供完整数据**
   - done 事件应包含操作的完整结果
   - 包含详细的 results 数组供前端使用
   - 不要假设前端只需要摘要

4. **错误处理要详细**
   - 提供清晰的错误码
   - 包含诊断信息在 details 中
   - 提供可行的 suggestions

5. **一致性**
   - 使用标准化的 kind 命名
   - 保持相似命令的数据结构一致
   - 遵循事件生命周期规则

### 前端开发者

1. **验证事件结构**
   - 总是验证必需字段是否存在
   - 优雅处理缺失的可选字段
   - 对无效 JSON 要有容错机制

2. **处理缓冲**
   - NDJSON 可能跨越多个 data 事件
   - 缓冲不完整的行
   - 处理空行

3. **状态管理**
   - 跟踪操作状态（进行中/完成/失败）
   - 确保 done/error 事件重置状态
   - 处理并发命令（如果支持）

4. **用户体验**
   - 进度条要流畅
   - 错误消息要友好
   - 提供详细信息的折叠面板
   - 结果要可导出/复制

5. **调试支持**
   - 记录所有原始事件
   - 提供事件查看器
   - 支持重放事件流（测试用）

---

## 总结

### 架构变更

| 方面 | v2.0 (旧) | v5.0 (新) |
|------|-----------|-----------|
| 输出引擎 | OutputEngine | EventEmitter |
| 输出模式 | NDJSON + Prettify | 纯 NDJSON |
| Message API | 广泛使用 | 完全移除 |
| 迭代输出 | 常见 | 禁止 |
| 前端渲染 | 部分 | 全部 |

### 迁移路径

1. **创建 EventEmitter** - 替换 OutputEngine
2. **更新 rose.py** - 移除 prettify 支持
3. **重构命令** - 移除 Message API，使用事件
4. **清理代码** - 删除旧文件
5. **测试验证** - 确保 NDJSON 正确
6. **更新文档** - 反映新架构

### 工作量估算

- **EventEmitter 实现**: 2-3 小时
- **命令重构**: 
  - cache: 1 小时
  - config: 1 小时
  - load: 2 小时
  - inspect: 2 小时
  - extract: 3 小时
  - compress: 3 小时
- **测试**: 4-5 小时
- **文档**: 2-3 小时
- **总计**: 约 20-25 小时

### 预期收益

1. **架构清晰** - 单一职责，无模式切换
2. **前端自由** - 完全控制 UI 渲染
3. **易于集成** - 标准 NDJSON 协议
4. **易于测试** - JSON 输出易于验证
5. **可扩展性** - 添加新命令模式一致

---

## 附录：事件类型速查表

### Load 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `found_bags` | [{"path", "size_mb", "exists"}], count |
| progress | - | percent, message, step, total_steps |
| data | `results` | [{"path", "status", "elapsed", "topics_count"}], count |
| done | - | summary: {loaded_files, cached_files, failed_files, elapsed_time} |

### Extract 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `found_bags` | [{"path", "size_mb", "topics_count"}], count |
| data | `topics` | {total_topics, selected_count, selected[], method} |
| progress | - | percent, message, step, total_steps |
| data | `results` | [{"input", "output", "topics_extracted", "messages"}], count |
| done | - | summary: {extracted_bags, failed_bags, total_messages_extracted} |

### Compress 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `plan` | {compression, total_input_size_mb, bags[]} |
| progress | - | percent, message, step, total_steps |
| data | `results` | [{"input", "output", "original_mb", "compressed_mb", "ratio"}] |
| done | - | summary: {compressed_count, compression_ratio, elapsed_time} |

### Inspect 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `metadata` | {path, size_mb, duration_sec, topics_count, messages_count} |
| data | `topics` | {topics[], sort_by}, count |
| data | `fields` | {topics[].fields[]}, count |
| done | - | summary: {analyzed_topics, analyzed_messages, elapsed_time} |

### Cache 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `cache_info` | {stats{}, entries[]}, count |
| data | `clear_plan` | {entries_to_clear, size_to_free_mb, bag_path} |
| done | - | summary: {cleared_entries, freed_mb} |

### Config 命令

| 事件 | label | 数据 |
|------|------|------|
| data | `config_data` | {config{}, source, config_file} |
| data | `change` | {key, old_value, new_value, config_file} |
| done | - | summary: {key, value, applied} |
