下面给出一套**极简调用层**，在不改变你既定「NDJSON v1-min 协议」的前提下，大幅减少日常编码时的字段冗余与样板代码。思路是：**协议保持完整、调用保持短小**——由封装层自动补全 `timestamp/protocol/context` 等通用字段，开发者只关心少数业务参数。

---

# 目标

* 协议不变（progress / data / done / error）。
* 代码端只写极少参数（如 `pct`、`msg`、`data`、`summary`）。
* 自动注入：`timestamp`、`protocol.version`、`context(trace_id/command/run_id)`。
* 统一错误收口与退出码。
* 与 Typer 命令无缝集成。

---

# 一、最小化 API 设计

## 1) 顶层门面（推荐固定名）

`EventEmitter`（或 `E` 作为别名）：

* `E.progress(pct: float, msg: str = "", step: int | None = None, total: int | None = None)`
* `E.data(data: Any, label: str | None = None, **kv)`

  * 常用就两个参数：`data` 与可选 `label`
* `E.done(summary: dict | None = None, **kv)`

  * 一般只传 `summary`，偶尔附带 `artifacts` 等
* `E.error(code: str, message: str, **details)`

  * 必填只有 `code` 和 `message`

> 以上四个方法内部自动构造完整事件并输出 NDJSON；`protocol/context/timestamp` 无需在调用处出现。

## 2) 命令级包装（装饰器）

* `@ndjson_command(name: str | None = None)`

  * 初始化 emitter 的上下文（`command`、`trace_id`、`run_id`）
  * 捕获未处理异常 → `E.error(...)` + 退出码非 0
  * 可选记录耗时，在成功路径自动把耗时并入 `E.done(summary=...)`

## 3) 任务级进度（上下文管理器）

* `with E.task("Loading", steps=N) as t: t.step("file1"); t.step("file2") ...`

  * 自动计算百分比并调用 `E.progress(...)`
  * 让调用点只写“语义”，无需关心 `percent/step/total`

---

# 二、自动注入与默认值策略

| 字段                 | 由谁填      | 规则                                              |
| ------------------ | -------- | ----------------------------------------------- |
| `timestamp`        | 框架       | `utcnow().isoformat() + "Z"`                    |
| `protocol`         | 框架       | `{"name":"rose.ndjson","version":"1.0"}`（或全局常量） |
| `context.command`  | 装饰器      | 来自 Typer 子命令名或装饰器参数                             |
| `context.trace_id` | 装饰器      | 每次执行生成 UUID                                     |
| `context.run_id`   | 装饰器      | `YYYYMMDD-HHMMSS-<shortid>`                     |
| `payload`          | 调用者 + 框架 | 调用者仅提供业务最小集；框架补齐结构外层                            |

> 这样调用点只需要传业务数据，协议“信封”完全由封装层统一生成。

---

# 三、可选的“语义标签”快捷口（不破坏通用性）

为了在前端更好路由但仍保持通用协议，可在 `E.data(...)` 里提供轻量标签参数（全可选）：

* `E.data(data, label="found_files")`
* `E.data(data, label="topics")`
* `E.data(summary, label="summary")`

内部实现：将 `label` 放入 `payload.label`，不影响协议稳定性，也避免定义一堆“子类型”。

---

# 四、错误与退出码统一

* 在 `@ndjson_command` 内部：

  * 未捕获异常 → `E.error(code="INTERNAL_ERROR", message=str(e), details=trace)` 并 `Exit(1)`
  * 显式业务失败 → 调用方可直接 `E.error("INVALID_ARGUMENT", "...")` 后抛 `Exit(1)` 或返回错误码
* 成功路径最后必须 `E.done(summary=...)`，并 `Exit(0)`（装饰器也可代为封口）

---

# 五、与 Typer 的无痕集成建议

* 在应用入口统一 `init_emitter()`。
* 每个子命令函数加 `@ndjson_command()`。
* 旧的逐行打印与 Message API 统一替换为：

  * 小结果：`E.data({...})` 或 `E.data(list)`
  * 进度：`with E.task(...): ...` 或 `E.progress(...)`
  * 收尾：`E.done(summary=...)`

---

# 六、调用示例（仅示意签名与用法）

> 以下仅示范“调用端多简短”，非要求你现在就改代码。

**发现文件 + 进度 + 收尾**

```python
@ndjson_command("load")
def load_cmd(...):
    files = discover_files(...)
    E.data([{"path": str(f), "size_mb": size_of(f)} for f in files], label="found_files")

    with E.task("loading", steps=len(files)) as t:
        for f in files:
            load_one(f)
            t.step(f"loaded {f.name}")

    E.done({"loaded_files": len(files), "elapsed_time": t.elapsed})
```

**错误收口**

```python
@ndjson_command("inspect")
def inspect_cmd(path: Path):
    if not path.exists():
        E.error("BAG_NOT_FOUND", f"{path} not found", path=str(path))
        raise Exit(1)
    meta = analyze(path)
    E.data(meta, label="bag_meta")
    E.done({"analyzed_topics": meta["topics_count"]})
```

> 注意：调用方完全不需要填写 `timestamp/context/protocol/payload` 的外层字段。

---

# 七、测试与可维护性

* **测试**：只断言业务部分（`percent`、`label`、`data`、`summary`）与最后一条事件类型；信封层在一处测试即可。
* **演进**：未来如需表格/树/分块等复杂场景，可在 `E` 层新增辅助方法（如 `E.table_schema(...) / E.table_rows(...)`），不影响已有简单接口。
* **一致性**：所有命令通过 `@ndjson_command` 统一上下文与异常处理，避免每个命令重复样板。

---

# 八、API 摘要（便于贴在项目 README）

* `E.progress(pct, msg="", step=None, total=None)`
* `E.data(data, label=None, **kv)`
* `E.done(summary=None, **kv)`
* `E.error(code, message, **details)`
* `@ndjson_command(name=None)`
* `with E.task(title, steps) as t: t.step(msg=None)`

> 以上即为“**协议不改、调用极简**”的设计：
>
> * 协议细字段由封装层一次性处理；
> * 业务代码只写必要参数；
> * 统一收口、统一上下文、统一错误与退出码。
