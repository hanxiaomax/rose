# Rose 插件系统

Rose 插件系统让你可以轻松扩展 Rose 的功能，无需修改核心代码。支持两种插件类型：

- **钩子插件**：在 Rose 操作时自动执行
- **脚本插件**：作为独立脚本手动执行

## 快速开始

### 创建插件

```bash
# 创建钩子插件（自动执行）
rose plugin create my_hook --template basic

# 创建脚本插件（手动执行）  
rose plugin create my_script --template script_basic

# 查看插件
rose plugin list
```

### 运行插件

#### 钩子插件（自动执行）
```bash
# 钩子插件在 Rose 操作时自动运行
rose load demo.bag --verbose
```

#### 脚本插件（手动执行）
```bash
# 脚本插件需要手动执行
rose plugin run my_script --bag demo.bag
```

## 主要特性

- 🔌 **插件热加载**：无需重启即可加载新插件
- 🎣 **钩子系统**：在 Rose 操作前后自动执行插件逻辑
- 📜 **脚本执行**：独立运行的数据处理脚本
- 📊 **数据访问**：插件可以安全访问 bag 数据和 DataFrame
- 🛠️ **自定义命令**：插件可以提供自己的 CLI 命令
- 💬 **用户交互**：脚本插件支持交互式操作
- 📝 **多种模板**：提供不同用途的插件模板

## 插件类型

### 钩子插件模板
| 模板 | 用途 | 适合场景 |
|------|------|---------|
| `basic` | 基础钩子插件 | 简单的自动化处理 |
| `data_processor` | 数据处理钩子 | 复杂的数据分析和转换 |
| `hook_example` | 钩子示例 | 学习钩子系统的使用 |

### 脚本插件模板
| 模板 | 用途 | 适合场景 |
|------|------|---------|
| `script_basic` | 基础脚本插件 | 简单的数据查看和处理 |
| `script_analyzer` | 数据分析脚本 | 交互式数据分析和导出 |

## 文档

- [完整文档](PLUGIN_SYSTEM.md) - 详细的 API 参考和开发指南
- [快速入门](PLUGIN_QUICKSTART.md) - 5分钟上手指南

## 插件命令

```bash
rose plugin --help                    # 查看所有插件命令
rose plugin list                      # 列出所有插件
rose plugin list --type hook          # 只列出钩子插件
rose plugin list --type script        # 只列出脚本插件
rose plugin create <name> --template <type>  # 创建插件
rose plugin run <name> [command]      # 运行插件
rose plugin enable/disable <name>     # 启用/禁用插件
```

## 示例插件

系统提供了几个示例插件：

### 钩子插件示例
- **example** - 基础钩子功能演示
- **data_analyzer** - 数据分析钩子示例  
- **hook_demo** - 钩子使用完整示例

### 脚本插件示例
- **my_script** - 基础脚本插件示例
- **analyzer** - 交互式数据分析脚本

## 插件类型选择指南

| 场景 | 推荐类型 | 原因 |
|------|---------|------|
| 自动数据验证 | 钩子插件 | 在操作时自动执行 |
| 临时数据分析 | 脚本插件 | 按需执行，支持交互 |
| 自动备份 | 钩子插件 | 在导出后自动执行 |
| 数据探索工具 | 脚本插件 | 需要用户交互选择 |
| 质量监控 | 钩子插件 | 持续自动监控 |
| 批处理脚本 | 脚本插件 | 一次性批量处理 |

立即开始创建你的插件吧！🚀
