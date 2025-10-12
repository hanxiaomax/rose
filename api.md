# Rose NDJSON 极简调用层 · 设计与实施文档（v1）

## 0. 范围与目标

* **范围**：后端输出层（仅关注如何向 stdout 输出 NDJSON 事件），不涉及前端。
* **目标**：

  * 协议保持不变（`progress` / `data` / `done` / `error`）；
  * 业务调用面极简（仅 4 个方法）；
  * 自动注入通用元数据（`timestamp`/`protocol`/`context`）；
  * 统一异常收口与退出码；
  * 与 Typer 命令无缝集成；
  * 协议未来若调整，**尽量只改一处**（编码层），业务代码基本不动。

---

## 1. 关键设计与术语

* **EventEmitter（E）**：对外的稳定门面，仅暴露 4 个方法（`progress/data/done/error`），供业务命令调用。
* **EventEncoder**：**唯一协议细节所在**。负责把内部事件对象编码为一行 NDJSON，并注入 `timestamp/protocol/context` 等信封字段。协议迭代时优先只改这里。
* **内部事件模型**：四个极简数据对象（Progress/Data/Done/Error），仅包含业务最小字段。业务侧只感知这四类字段，不接触协议命名。
* **ndjson_command**：命令装饰器。统一初始化上下文（`command/trace_id/run_id`），捕获未处理异常并走 `E.error` 收口，可选负责在成功路径补充耗时并 `E.done`。
* **task**：任务进度上下文，自动计算百分比并调用 `E.progress`。

---

## 2. 协议：NDJSON v1-min（摘要）

* 事件类型固定：`progress` / `data` / `done` / `error`。
* 每行一个 JSON（UTF-8，`\n` 结尾）；`stdout` 只放事件；`stderr` 放日志或 traceback。
* 统一时间格式：UTC ISO8601（`...Z`）。
* 生命周期：可多次 `progress`/`data`，最终必须以 `done` 或 `error` 收尾；退出码分别为 0/非 0。
* 示例（结构示意）：

  * `progress.payload = {"percent": 0..100, "message"?, "step"?, "total_steps"?}`
  * `data.payload = {"label"?, "data": <object|array|scalar>, "count"?, ...}`
  * `done.payload = {"summary": {...}}`
  * `error.payload = {"code": "UPPER_SNAKE", "message": "...", "details"?: {...}}`

> 协议未变；本文件聚焦**如何用更少的代码**生成上述事件。

---

## 3. 稳定 API（对业务侧）

以下 **4 个方法**是业务唯一需要直接调用的接口：

* `E.emit_progress(percent: float, message: str = "", step: int | None = None, total_steps: int | None = None)`
* `E.emit_data(data: Any, label: str | None = None, count: int | None = None)`

  * 常见只填 `data`，必要时用 `label` 做轻语义标注（例如 `"found_files"` / `"topics"`）。
* `E.emit_done(summary: Dict[str, Any])`

  * 常见只填 `summary`，必要时可附加 `artifacts` 等键值。
* `E.emit_error(code: str, message: str, details: Dict[str, Any] | None = None)`

  * 仅 `code` 与 `message` 必填；其他诊断信息放在 `details`。

> 调用方**不需要**自己拼 `timestamp/protocol/context/payload` 外层结构，这些由编码层统一注入。

---

## 4. 自动注入与默认策略

| 字段                 | 由谁注入 | 规则与说明                                     |
| ------------------ | ---- | ----------------------------------------- |
| `timestamp`        | 编码层  | `utcnow().isoformat() + "Z"`              |
| `protocol`         | 编码层  | `{"name":"rose.ndjson", "version":"1.0"}` |
| `context.command`  | 发射器  | 来自 Typer 子命令名或装饰器参数                       |
| `context.trace_id` | 发射器  | 每次执行生成 UUID                               |
| `context.run_id`   | 发射器  | `YYYYMMDD-HHMMSS-<shortid>`               |
| `payload` 外层结构     | 编码层  | 由 EventEncoder 统一组织                       |
| 数值/时间格式            | 编码层  | 统一小数位策略；禁止 `NaN/Infinity`                 |
| flush 行为           | 发射器  | 每次写入后 `flush()`，保障前端及时消费                  |

---

## 5. 统一错误收口与进度工具（可选但推荐）

* **手动上下文设置**：

  * 使用 `emitter.set_context(command, trace_id, run_id)` 初始化 EventEmitter 上下文
  * 手动处理异常并使用 `E.emit_error()` 和适当的退出码
  * 成功时手动调用 `E.emit_done()`

* **进度管理**：

  * 对于多步骤任务，手动计算百分比并调用 `E.emit_progress()`
  * 业务逻辑关注步骤语义（例如"加载文件 N/总数"）

> 这些都是**薄封装**：删改成本低；主要减少重复样板与遗漏。

---

## 6. 调用示例（仅示意风格）

### 6.1 发现文件 + 进度 + 收尾

```python
def load_cmd(...):
    emitter = get_emitter()
    emitter.set_context("load")
    
    files = discover_files(...)
    emitter.emit_data(
        [{"path": str(f), "size_mb": size_of(f)} for f in files], 
        label="found_files",
        count=len(files)
    )

    # 手动进度跟踪
    for i, f in enumerate(files):
        load_one(f)
        percent = (i + 1) / len(files) * 100
        emitter.emit_progress(percent, f"loaded {f.name}", step=i+1, total_steps=len(files))

    emitter.emit_done({"loaded_files": len(files)})
```

### 6.2 错误收口

```python
def inspect_cmd(path: Path):
    emitter = get_emitter()
    emitter.set_context("inspect")
    
    if not path.exists():
        emitter.emit_error("BAG_NOT_FOUND", f"{path} not found", details={"path": str(path)})
        raise typer.Exit(1)
    
    meta = analyze(path)
    emitter.emit_data(meta, label="bag_meta")
    emitter.emit_done({"analyzed_topics": meta["topics_count"]})
```

---

## 7. 组件职责与依赖

```
[ 业务命令（Typer） ]
        │ 仅调用 4 方法
        ▼
[ EventEmitter ]  —— 写行/flush ——►  stdout (NDJSON)
        │
        ▼
[ EventEncoder ]  —— 组装协议信封与载荷（唯一协议细节所在）
```

* **EventEmitter**：稳定 API、最薄逻辑、聚合内部事件模型 → 委托编码。
* **EventEncoder**：**协议唯一改动点**。字段名、结构、默认值、时间/数值格式、上下文注入与兼容策略均在此集中处理。
* **内部事件模型**：进度/数据/收尾/错误四类轻量对象，字段稳定，供业务构造与传递。

---

## 8. 约束与边界

* **stdout**：只输出事件 NDJSON；**stderr**：用于日志/traceback；绝不混用。
* **完成规则**：一次执行必须以 `done` 或 `error` 结束；退出码与之匹配。
* **进度规则**：`percent ∈ [0, 100]` 且单调不减（由调用侧保证）。
* **性能**：默认每行 flush；若后续需要吞吐优化，可在发射器增加可配置的缓冲策略（不影响 API）。
* **并发**：若存在并行子任务，建议由业务侧串行发射事件（或加互斥），以保证 NDJSON 行不乱序；此处不做复杂并发抽象。

---

## 9. 协议变更的影响与控制

* **原则**：协议若变化，**优先只改 EventEncoder**；业务命令不动或极少动。
* **常见变更映射**：

| 变更类型            | 示例                                | 改动位置              |
| --------------- | --------------------------------- | ----------------- |
| 增加信封字段          | 新增 `context.run_id`               | EventEncoder 自动注入 |
| 改信封字段名          | `event` → `etype`                 | EventEncoder 字段映射 |
| 改载荷字段名/结构       | `payload.data` → `payload.items`  | EventEncoder 变换   |
| 新增可选字段          | `payload.version`                 | EventEncoder 默认补齐 |
| 进度结构变化          | `percent` → `progress.value(0-1)` | EventEncoder 内部换算 |
| 引入 shape/schema | `shape=table`/`rows` 分块输出         | EventEncoder 组合输出 |

> 以上都不要求改业务调用面（4 方法）与命令代码。

---

## 10. 与 Typer 的集成指引

* 应用入口：统一调用 `init_emitter()`（内部完成 encoder/emitter 初始化）。
* 每个子命令：手动初始化发射器上下文；旧的逐行打印/Message API 统一替换为：

  * 小结果：`emitter.emit_data({...})` 或 `emitter.emit_data(list)`
  * 长任务：手动进度跟踪 `emitter.emit_progress(...)`
  * 收尾：`emitter.emit_done(summary=...)`
* 顶级选项：若已有 `--as-backend`，则在入口处强制启用 NDJSON 输出（无 UI）。

---


---

## 11. 分阶段实施步骤

### 阶段一：核心基础设施（已完成）

✅ **已完成**：
1. **EventEmitter 核心类** - 实现 4 个核心发射方法
2. **EventEncoder 编码器** - 协议信封组装与自动注入
3. **全局发射器管理** - `init_emitter()`, `get_emitter()`, `reset_emitter()`
4. **基础协议支持** - NDJSON v1-min 协议实现
5. **CLI 命令集成** - load, extract, compress, inspect, cache, config

### 阶段二：开发者体验优化（进行中）

🔧 **当前实现细节**：
- EventEmitter 位于 `roseApp/core/event_emitter.py`
- 所有 CLI 命令使用 `get_emitter()` 和手动上下文设置
- 协议版本：`rose.ndjson v1.0`
- 自动时间戳和协议注入
- 手动进度跟踪（无任务上下文管理器）

### 阶段三：高级功能增强（规划中）

📋 **待实现功能**：
1. **@ndjson_command 装饰器** - 自动上下文初始化与异常处理
2. **E.task 上下文管理器** - 自动进度计算与管理
3. **协议版本管理** - 向后兼容性支持
4. **性能优化** - 缓冲策略与批量发射
5. **测试覆盖** - 单元测试与集成测试

### 阶段四：生态系统集成（未来规划）

🚀 **扩展计划**：
1. **前端 SDK** - JavaScript/TypeScript 事件消费库
2. **协议验证工具** - NDJSON 流验证与调试
3. **性能监控** - 事件流性能指标收集
4. **插件系统扩展** - 事件处理插件支持
5. **文档完善** - API 参考与最佳实践指南

---

## 12. API 摘要（便于放到 README）

* `emitter.emit_progress(percent, message="", step=None, total_steps=None)`
* `emitter.emit_data(data, label=None, count=None)`
* `emitter.emit_done(summary)`
* `emitter.emit_error(code, message, details=None)`
* `emitter.set_context(command, trace_id=None, run_id=None)`
* 全局管理：`init_emitter()`, `get_emitter()`, `reset_emitter()`

> **总之**：协议细节统一交给 **EventEncoder**；业务代码只认 **EventEmitter** 的 4 个方法。协议迭代时，尽量只修改编码层即可完成全局适配。
