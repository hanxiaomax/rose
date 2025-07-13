# Rose CLI 命令行设计说明文档

Rose是一个强大的ROS bag文件处理工具，遵循现代CLI工具设计最佳实践，提供直观、高效的命令行体验。

## 设计理念与参考

### 借鉴的优秀CLI工具

本设计深度参考了以下优秀CLI工具的设计理念：

- **fzf**: 模糊查找与高度交互性，提升搜索体验
- **tmux**: 清晰的子命令结构，会话管理的扩展友好性
- **ImageMagick (magick)**: 统一入口点，多子功能设计
- **Git**: 动词化子命令组织，直观的操作语义
- **kubectl**: 一致的参数模式，结构化输出支持

### 核心设计原则

#### 1. 子命令结构与语义化 (类似Git/tmux)
```
rose <verb> <noun> [options]
```
- **动词+名词结构**: `filter bag`, `inspect bag`, `prune cache`
- **逻辑分层**: 主命令 → 动词 → 名词 → 参数
- **易于记忆和理解**: 操作意图清晰

#### 2. 帮助优先与示例驱动 (类似ImageMagick)
- 每个命令都有丰富的 `--help` 信息
- 示例优先，常用用法突出显示
- 上下文相关的帮助信息

#### 3. 进度反馈与状态可视化 (类似modern CLI tools)
- 实时进度条显示
- 颜色编码状态（绿色=成功，红色=错误）
- 清晰的操作结果反馈

#### 4. 交互与非交互模式并存 (类似atuin/fzf)
- 支持 `--dry-run` 预览模式
- 交互式TUI界面
- 脚本友好的非交互模式

#### 5. 输出格式标准化 (类似kubectl/terraform)
- **参数统一**: `--as` 指定格式, `--output` 指定路径
- **强制路径**: `csv`/`html` 格式强制要求 `--output`
- **便于管道处理**: `table`/`list` 格式直接输出到终端

## 总体架构

### 主命令入口
```bash
python -m roseApp.rose [GLOBAL_OPTIONS] COMMAND [NOUN] [ARGS]...
```

### 命令层级结构

- **全局选项**
  - `--verbose, -v`
  - `--install-completion`
  - `--show-completion`
  - `--help`
- **`extract`**
  - `bag`
- **`inspect`**
  - `bag`
  - `topic`
- **`plot`**
  - `bag`
  - `topic`
- **`prune`**
  - `cache`
- **`launch`**
  - `cli`
  - `tui`

## 核心命令设计

### 1. 全局选项

- `--verbose, -v INTEGER`: 增加详细程度 (例如: -v, -vv, -vvv)。
- `--install-completion`: 为当前shell安装自动补全。
- `--show-completion`: 显示当前shell的自动补全配置。
- `--help`: 显示帮助信息并退出。

---

### 2. `extract` - 主题提取命令

#### `extract bag` - 提取ROS Bag中的指定主题

**设计参考**: 类似grep的过滤逻辑，但重点是"提取"而非"过滤"。

**语法**:
```bash
rose extract bag [OPTIONS] INPUT_PATH [OUTPUT_DIR]
```

**参数设计哲学**:
- **位置参数逻辑**: 输入→输出，符合Unix管道思维
- **选项一致性**: 短选项遵循常见约定 (`-w`, `-tp`, `-c`, `-p`)
- **语义化命名**: `--whitelist` 比 `--wl` 更清晰

#### 核心选项
```bash
--whitelist, -w TEXT      # 白名单文件 (类似grep -f)
--topics, -tp TEXT        # 要提取的主题列表 (可重复，类似rsync --include)
--reverse, -r             # 反选模式，提取除指定主题外的所有主题
--compression, -c TEXT    # 压缩类型 (none|bz2|lz4)
--parallel, -p            # 并行处理开关
--workers INTEGER         # 工作进程数 (类似make -j)
--sort-by, -s TEXT        # 排序方式 (topic|count|size)
--dry-run                 # 预览模式 (类似rsync --dry-run)
```

#### 使用示例 (按复杂度递增)
```bash
# 基础提取 - 提取指定主题
rose extract bag demo.bag output/ --topics /tf

# 反选提取 - 提取除指定主题外的所有主题
rose extract bag demo.bag output/ --topics /tf --reverse

# 高级用法 - 压缩+并行
rose extract bag input_dir/ output_dir/ --topics /tf --compression lz4 --parallel

# 安全预览 - 避免意外操作
rose extract bag demo.bag output/ --topics /tf --dry-run
```

---

### 3. `inspect` - 文件/主题检查命令

#### `inspect bag` - 检查Bag文件概览

**功能**: 快速检查ROS bag文件概览信息。

**语法**:
```bash
rose inspect bag [OPTIONS] INPUT_PATH
```

**核心选项**:
```bash
# 内容过滤
--topics, -t TEXT         # 主题过滤 (支持模糊匹配)

# 输出格式
--format, -f TEXT         # 输出格式: table|list|summary|csv|html (默认: table)
--output, -o TEXT         # 输出文件路径 (仅在 --format=csv/html 时生效)

# 排序控制 (类似ls排序选项)
--sort-by, -s TEXT        # 排序字段: name|type|count|size|frequency
--reverse, -r             # 反向排序
--verbose, -v             # 详细统计信息
```

**使用示例**:
```bash
# 快速查看 - 默认体验
rose inspect bag demo.bag

# 详细分析 - 深入了解
rose inspect bag demo.bag --verbose

# 数据导出 - 结构化输出
rose inspect bag demo.bag --format csv --output analysis.csv

# 报告生成 - 专业输出
rose inspect bag demo.bag --format html --output report.html --verbose
```

---

#### `inspect topic` - 检查Topic详情

**功能**: 检查指定topic的详细信息，如消息定义和字段结构。

**语法**:
```bash
rose inspect topic [OPTIONS] INPUT_PATH TOPIC_NAME
```

**核心选项**:
```bash
--fields                # 显示消息类型的字段结构
--verbose               # 显示更详细的信息
--format, -f TEXT       # 输出格式: table|list|json (默认: table)
--output, -o TEXT       # 输出文件路径 (可选)
```

**使用示例**:
```bash
# 查看topic基本信息
rose inspect topic demo.bag /tf

# 查看topic的字段结构
rose inspect topic demo.bag /tf --fields

# 导出topic信息为JSON
rose inspect topic demo.bag /tf --format json --output tf_info.json
```

---

### 4. `plot` - 数据可视化命令

**设计参考**: 从`inspect`中解耦，形成独立的可视化命令。

#### `plot bag` - 可视化Bag统计信息

**功能**: 生成整个bag文件的统计可视化图表，包括主题分布、消息数量、文件大小等统计信息。

**语法**:
```bash
rose plot bag [OPTIONS] INPUT_PATH
```

**核心选项**:
```bash
--type TEXT           # 图表类型: frequency|size|count|overview|timeline (默认: overview)
--format, -f TEXT     # 输出格式: png|svg|pdf|html (默认: png)
--output, -o TEXT     # 图表输出路径 (必需)
--verbose, -v         # 显示详细统计信息
```

**使用示例**:
```bash
# 生成bag概览图表
rose plot bag demo.bag --type overview --format png --output overview.png

# 生成时间线图表
rose plot bag demo.bag --type timeline --format html --output timeline.html

# 生成详细统计图表
rose plot bag demo.bag --type frequency --format svg --output stats.svg --verbose
```

---

#### `plot topic` - 可视化Topic字段数据

**功能**: 对指定topic的某个或多个字段进行可视化，支持多个topic的组合绘制。

**语法**:
```bash
rose plot topic [OPTIONS] INPUT_PATH TOPIC_NAME [TOPIC_NAME...]
```

**核心选项**:
```bash
--field, -fd TEXT     # 要可视化的消息字段 (可重复指定多个字段)
                      # 例如: 'pose.position.x' 或 'twist.linear.x'
--format, -f TEXT     # 输出格式: png|svg|pdf|html (默认: png)
--output, -o TEXT     # 图表输出路径 (必需)
--type TEXT           # 图表类型: line|scatter|histogram (默认: line)
--time-range TEXT     # 时间范围过滤 (格式: start:end 或 duration)
```

**使用示例**:
```bash
# 绘制单个topic的单个字段
rose plot topic demo.bag /odom --field 'pose.pose.position.x' --output pos_x.png

# 绘制单个topic的多个字段
rose plot topic demo.bag /odom --field 'pose.pose.position.x' --field 'pose.pose.position.y' --output pos_xy.png

# 绘制多个topic的对比图
rose plot topic demo.bag /odom /cmd_vel --field 'pose.pose.position.x' --field 'linear.x' --output comparison.png

# 生成HTML交互图表
rose plot topic demo.bag /odom --field 'pose.pose.position.x' --format html --output interactive.html
```

---

### 5. `prune` - 缓存管理命令

#### `prune cache` - 管理分析缓存

**设计参考**: 简化`prune`命令，聚焦核心功能。

**语法**:
```bash
rose prune cache [OPTIONS]
```

**核心选项**:
```bash
--all, -a                # 清理所有缓存
--older-than, -o INTEGER # 时间条件清理 (类似find -mtime)
--dry-run                # 预览模式
--status                 # 显示缓存状态
```

**使用示例**:
```bash
# 查看缓存状态
rose prune cache --status

# 安全清理 - 预览模式
rose prune cache --all --dry-run

# 条件清理 - 时间过滤
rose prune cache --older-than 7

# 完全清理 - 一键清空
rose prune cache --all
```

---

### 6. `launch` - 交互模式启动命令

**设计参考**: 统一启动入口，语义更清晰。

#### `launch cli/tui` - 启动交互式模式

**语法**:
```bash
# 启动命令行交互模式
rose launch cli

# 启动终端UI模式
rose launch tui
```

## 设计特点与UX模式

### 1. 统一的命令结构 (类似Git生态系统)

**动词+名词命令组织**:
```
rose <动词> <名词> [选项]
extract  bag      = 提取 + bag文件中的主题
inspect  bag/topic= 检查 + bag文件/topic
plot     bag/topic= 绘制 + bag/topic的可视化
prune    cache    = 清理 + 缓存
launch   cli/tui  = 启动 + 交互模式
```

### 2. 友好的错误处理 (类似现代CLI最佳实践)

**错误消息示例**:
```bash
# 强制输出路径
Error: --format=csv requires --output to be specified.
Suggestion: rose inspect bag demo.bag --format csv --output report.csv

# 多字段要求
Error: plot topic requires at least one --field to be specified.
Suggestion: rose plot topic demo.bag /odom --field 'pose.pose.position.x' --output chart.png
```

### 3. 统一的输出参数设计

**输出格式统一**:
- `--format, -f`: 指定输出格式
- `--output, -o`: 指定输出文件路径
- 文件格式(`csv`, `html`, `png`等)强制要求输出路径
- 终端格式(`table`, `list`)忽略输出路径

## 与优秀CLI工具的对比分析

### 命令结构对比

| 工具 | 结构模式 | Rose采用 | 优势 |
|------|----------|----------|------|
| Git | `git <verb> <object>` | `rose <verb> <noun>` | 语义化，易记忆 |
| Docker | `docker <object> <verb>` | 未采用 | 动词优先更符合操作习惯 |

## 设计决策总结

### 选择的设计模式

| 设计决策 | 选择 | 理由 | 参考工具 |
|----------|------|------|----------|
| 命令结构 | 动词 + 名词 | 语义清晰，可扩展性强 | Git, kubectl |
| 参数位置 | 输入→输出 | 符合Unix管道思维 | cp, rsync |
| 输出参数 | `--format` 和 `--output` | 简洁且功能分离 | kubectl |
| 默认行为 | 自动覆盖 | 减少用户决策负担 | 现代CLI趋势 |

### 不采用的设计模式

| 设计模式 | 为什么不采用 | 替代方案 |
|----------|--------------|----------|
| 选项式子功能 | 功能混杂 (如--plot) | 独立子命令 (`plot bag`) |
| 多层级子命令 | 结构过深 (如prune clean)| 简化为一级命令+选项 |
| 覆盖确认 | 增加操作复杂度 | 默认覆盖，提供--dry-run预览 |

这个设计文档体现了现代CLI工具的最佳实践，融合了多个优秀工具的设计理念，确保Rose既强大又易用，既适合新手也适合专家，既支持交互使用也支持脚本化自动化。 