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

#### 1. 简洁的命令结构
```
rose <command> [options] [args]
```
- **直接命令**: `extract`, `inspect`, `plot`, `prune`, `launch`
- **简洁明了**: 避免冗余的动词+名词结构
- **易于记忆**: 命令名称直接表达功能

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

#### 5. 统一的输出格式处理
- **`--as`**: 指定输出格式 (table|list|csv|html|json)
- **`--output`**: 指定输出文件路径
- **自动处理**: 根据格式自动决定输出目标

## 总体架构

### 主命令入口
```bash
python -m roseApp.rose [GLOBAL_OPTIONS] COMMAND [ARGS]...
```

### 命令层级结构

- **全局选项**
  - `--verbose, -v`
  - `--install-completion`
  - `--show-completion`
  - `--help`
- **核心命令**
  - `extract` - 提取指定topics到新的bag文件
  - `inspect` - 检查bag文件或topic详情
  - `plot` - 生成数据可视化图表
  - `prune` - 清理分析缓存
  - `launch` - 启动交互式界面

## 核心命令设计

### 1. 全局选项

- `--verbose, -v INTEGER`: 增加详细程度 (例如: -v, -vv, -vvv)
- `--install-completion`: 为当前shell安装自动补全
- `--show-completion`: 显示当前shell的自动补全配置
- `--help`: 显示帮助信息并退出

---

### 2. `extract` - 提取Topics到新Bag文件

**设计参考**: 类似tar的提取功能，支持正选和反选模式

**语法**:
```bash
rose extract [OPTIONS] INPUT_PATH
```

**参数**:
- `INPUT_PATH`: 输入bag文件路径或包含bag文件的目录

**核心选项**:
```bash
--topics, -t TEXT        # 要提取的主题列表 (可重复指定)
--whitelist, -w TEXT     # 主题白名单文件路径
--reverse, -r            # 反选模式：提取除指定topics外的所有topics
--as, -a TEXT           # 压缩算法: none|bz2|lz4 (默认: none)
--output, -o TEXT       # 输出文件路径 (可选，默认: 时间戳+filtered后缀)
--parallel, -p           # 并行处理 (目录输入时)
--workers INTEGER        # 并行工作进程数 (默认: CPU数-2)
--dry-run                # 预览模式，显示将要执行的操作
```

**输出文件命名规则**:
- **指定输出**: `--output result.bag` → `result.bag`
- **默认输出**: `demo.bag` → `demo_20240101_123456_filtered.bag`
- **目录输入**: 每个文件都会在相同目录生成对应的filtered文件

**使用示例**:
```bash
# 提取指定topics (使用默认输出文件名)
rose extract demo.bag --topics /tf --topics /cmd_vel

# 指定输出文件
rose extract demo.bag --topics /tf --output result.bag

# 使用压缩算法
rose extract demo.bag --topics /tf --as lz4

# 反选模式：提取除了/tf外的所有topics
rose extract demo.bag --topics /tf --reverse

# 批量处理目录
rose extract input_dir/ --topics /tf --parallel

# 预览模式
rose extract demo.bag --topics /tf --dry-run
```

---

### 3. `inspect` - 检查Bag文件和Topic详情

**设计参考**: 类似`ls`命令的多格式输出，专注于文本信息展示

**功能定位**: 纯文本信息查看和分析，不涉及图表生成

**语法**:
```bash
# 检查bag文件概览
rose inspect [OPTIONS] INPUT_PATH

# 检查特定topic详情
rose inspect [OPTIONS] INPUT_PATH --topic TOPIC_NAME
```

**核心选项**:
```bash
# 目标选择
--topic, -t TEXT         # 检查特定topic的详细信息
--topics TEXT            # 过滤显示的topics (支持模糊匹配)

# 输出控制 (仅文本格式)
--as, -a TEXT           # 输出格式: table|list|summary|csv|html|json
--output, -o TEXT       # 输出文件路径 (csv/html/json格式时必需)
--sort-by, -s TEXT      # 排序字段: name|type|count|size|frequency
--reverse               # 反向排序
--verbose, -v           # 显示详细信息

# topic详情选项
--fields                # 显示消息字段结构 (与--topic配合使用)
```

**使用示例**:
```bash
# 快速查看bag概览 (默认table格式)
rose inspect demo.bag

# 详细分析
rose inspect demo.bag --verbose

# 检查特定topic
rose inspect demo.bag --topic /tf

# 查看topic字段结构
rose inspect demo.bag --topic /tf --fields

# 导出为CSV进行进一步分析
rose inspect demo.bag --as csv --output analysis.csv

# 生成HTML报告
rose inspect demo.bag --as html --output report.html

# 检查多个topic的详细信息
rose inspect demo.bag --topics "tf,odom" --verbose
```

---

### 4. `plot` - 数据可视化

**设计参考**: 专业的时间序列可视化工具，专注于图表生成

**功能定位**: 纯图表生成，将topic数据转换为可视化图表

**语法**:
```bash
rose plot <bag_path> --series <topic>:<field1,field2,...> [--series ...] --output/-o <file> [OPTIONS]
```

**参数**:
- `bag_path`: 输入bag文件路径

**核心选项**:
```bash
--series, -s TEXT       # 绘制序列 (必填，可重复)
                        # 格式: <topic>:<field1,field2> 
                        # 字段留空表示绘制该topic全部数值字段
--output, -o TEXT       # 输出文件路径 (必填)
--type, -t TEXT         # 图表类型: line|scatter (默认: line)
--as, -a TEXT          # 图表格式: png|svg|pdf|html (默认: png)
```

**--series 参数详解**:
- `--series /odom:pose.pose.position.x` - 绘制单个字段
- `--series /odom:pose.pose.position.x,pose.pose.position.y` - 绘制多个字段
- `--series /odom:` - 绘制该topic的所有数值字段 (字段留空)
- 可重复使用 `--series` 来绘制多个topic

**使用示例**:
```bash
# 绘制单个topic的单个字段
rose plot demo.bag --series /odom:pose.pose.position.x --output pos_x.png

# 绘制单个topic的多个字段
rose plot demo.bag --series /odom:pose.pose.position.x,pose.pose.position.y --output pos_xy.png

# 绘制topic的所有数值字段
rose plot demo.bag --series /odom: --output odom_all.png

# 多topic对比
rose plot demo.bag --series /odom:pose.pose.position.x --series /tf:transform.translation.x --output multi_pos.png

# 散点图
rose plot demo.bag --series /odom:pose.pose.position.x,pose.pose.position.y --type scatter --output scatter.png

# 生成HTML交互图表
rose plot demo.bag --series /odom:pose.pose.position.x --as html --output interactive.html
```

**与inspect命令的功能区分**:
- **inspect**: 查看文本信息 → 使用 `rose inspect demo.bag --topic /odom --fields`
- **plot**: 生成图表 → 使用 `rose plot demo.bag --series /odom:pose.pose.position.x --output chart.png`

---

### 5. `prune` - 缓存管理

**设计参考**: 简洁的缓存清理工具

**语法**:
```bash
rose prune [OPTIONS]
```

**核心选项**:
```bash
--all, -a               # 清理所有缓存
--older-than, -o INTEGER # 清理N天前的缓存
--status, -s            # 显示缓存状态
--dry-run               # 预览模式
```

**使用示例**:
```bash
# 查看缓存状态
rose prune --status

# 清理所有缓存
rose prune --all

# 清理7天前的缓存
rose prune --older-than 7

# 预览清理操作
rose prune --all --dry-run
```

---

### 6. `launch` - 启动交互式界面

**设计参考**: 统一的交互模式入口

**语法**:
```bash
rose launch [MODE]
```

**参数**:
- `MODE`: `cli` 或 `tui` (默认: `cli`)

**使用示例**:
```bash
# 启动命令行交互模式
rose launch cli

# 启动终端UI模式
rose launch tui

# 默认启动CLI模式
rose launch
```

## 设计特点与UX模式

### 1. 简化的命令结构

**直接命令组织**:
```
rose <command> [options] [args]
extract  = 提取topics
inspect  = 检查文件/topic
plot     = 数据可视化
prune    = 缓存管理
launch   = 交互界面
```

### 2. 统一的输出格式处理

**输出格式策略**:
- **`--as`**: 指定输出格式，支持 table|list|csv|html|json|png|svg|pdf
- **`--output`**: 指定输出文件路径
- **智能处理**: 
  - `table`/`list` 格式直接输出到终端
  - `csv`/`html`/`json` 格式要求指定 `--output`
  - 图表格式 (`png`/`svg`/`pdf`/`html`) 始终要求 `--output`

### 3. 友好的错误处理

**错误消息示例**:
```bash
# 缺少输出路径
Error: --as=csv requires --output to be specified
Suggestion: rose inspect demo.bag --as csv --output report.csv

# 反选模式提示
Error: --reverse requires --topics or --whitelist to be specified
Suggestion: rose extract demo.bag output.bag --topics /tf --reverse
```

### 4. 功能增强设计

**extract命令特色**:
- **正选模式**: 提取指定的topics
- **反选模式**: 提取除指定topics外的所有topics
- **批量处理**: 支持目录级别的并行处理

**plot命令特色**:
- **bag概览**: 显示整个bag的统计信息图表
- **topic字段**: 绘制特定topic字段的时间序列图
- **多topic支持**: 同时绘制多个topic的相同字段进行对比

## 与优秀CLI工具的对比分析

### 命令结构对比

| 工具 | 结构模式 | Rose采用 | 优势 |
|------|----------|----------|------|
| Git | `git <verb>` | `rose <command>` | 直接简洁 |
| Docker | `docker <command>` | `rose <command>` | 功能明确 |
| kubectl | `kubectl <verb> <noun>` | 未采用 | 避免冗余结构 |

## 设计决策总结

### 选择的设计模式

| 设计决策 | 选择 | 理由 |
|----------|------|------|
| 命令结构 | 直接命令 | 简洁明了，易于记忆 |
| 输出处理 | `--as` + `--output` | 统一且灵活 |
| 默认行为 | 直接覆盖 | 减少用户操作步骤 |
| 反选功能 | `--reverse` | 提供更灵活的过滤选项 |

### 不采用的设计模式

| 设计模式 | 为什么不采用 | 替代方案 |
|----------|--------------|----------|
| 动词+名词结构 | 过于冗长 | 直接功能命令 |
| 覆盖确认 | 增加操作复杂度 | 默认覆盖 |
| 单一输出格式 | 限制使用场景 | 多格式统一处理 |

这个设计文档体现了现代CLI工具的最佳实践，通过简化命令结构、统一输出处理、增强功能特性，确保Rose既强大又易用，适合各种使用场景。 