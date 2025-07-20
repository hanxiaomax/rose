# Tools 命令集成与实现

## 🎯 重构目标

将原来的 `prune.py` 重构为功能更全面的 `tools.py`，集成以下功能：

1. **Cache管理**: 原prune功能的现代化版本
2. **Diagnose诊断**: 集成原diagnose.py的功能
3. **System工具**: 版本信息、配置查看等实用工具

## 🏗️ 架构设计

### 命令结构
```
rose tools
├── cache-status     # 查看缓存状态
├── cache-clear      # 清理缓存
├── cache-info       # 缓存详细信息
├── diagnose-system  # 系统诊断
├── diagnose-bag     # bag文件诊断
└── version          # 版本信息
```

### 核心组件
1. **BagManager集成**: 使用统一的bag管理接口
2. **ResultHandler支持**: 支持多种输出格式的诊断报告
3. **Cache系统集成**: 与新的缓存系统无缝集成

## 📦 功能实现

### 1. Cache管理命令

#### cache-status
```bash
# 基本缓存状态
rose tools cache-status

# 详细缓存信息
rose tools cache-status --verbose
```

**功能特点:**
- 显示缓存类型和统计信息
- 命中率、请求总数、内存/磁盘使用
- 支持详细模式显示更多信息

#### cache-clear
```bash
# 交互式清理缓存
rose tools cache-clear

# 无确认清理
rose tools cache-clear --yes
```

**功能特点:**
- 安全的确认机制
- 显示清理前的缓存统计
- 支持强制清理模式

#### cache-info
```bash
# 显示缓存详细信息和缓存键
rose tools cache-info
```

**功能特点:**
- 显示缓存基本信息和统计
- 列出内存和文件缓存的键（前10个）
- 显示缓存条目数量和命中率

### 2. 诊断命令

#### diagnose-system
```bash
# 系统诊断
rose tools diagnose-system
```

**检查项目:**
- Python版本
- 依赖包状态 (rosbags, rich, typer, pyyaml)
- ROS环境检测
- 缓存系统状态

#### diagnose-bag
```bash
# 基本bag诊断
rose tools diagnose-bag /path/to/bag.bag

# 详细诊断
rose tools diagnose-bag /path/to/bag.bag --verbose

# 导出诊断报告
rose tools diagnose-bag /path/to/bag.bag --output report.html --format html
```

**诊断项目:**
- 文件完整性检查
- 时间戳一致性验证
- 消息计数合理性检查
- 支持多种输出格式 (table, json, yaml, html)

### 3. 实用工具命令

#### version
```bash
# 版本信息
rose tools version
```

**显示内容:**
- Rose版本
- Python版本
- 关键依赖版本



## 🔧 技术实现

### 1. BagManager集成

```python
# 使用BagManager进行bag诊断
manager = BagManager()
options = DiagnoseOptions(
    check_integrity=True,
    check_timestamps=True,
    check_message_counts=True,
    detailed=verbose
)

result = await manager.diagnose_bag(bag_path_obj, options)
```

### 2. ResultHandler支持

```python
# 获取结果处理器
handler = manager.get_result_handler()

# 导出到文件
if output:
    export_options = ExportOptions(
        format=output_format,
        output_file=output,
        pretty=True
    )
    handler.export(result, export_options)
else:
    # 渲染到控制台
    render_options = RenderOptions(
        format=output_format,
        verbose=verbose,
        show_summary=True
    )
    handler.render(result, render_options)
```

### 3. Cache系统集成

```python
# 获取缓存实例
cache = get_cache()

# 获取缓存统计
if hasattr(cache, 'get_stats'):
    stats = cache.get_stats()
    # 显示统计信息
```

## 📊 功能验证

### 1. 命令帮助测试 ✅
```bash
$ python -m roseApp.rose tools --help

Usage: python -m roseApp.rose tools [OPTIONS] COMMAND [ARGS]...

Utility tools for cache management, diagnostics, and system info

Commands:
│ cache-status      Show cache status and statistics
│ cache-clear       Clear all cache data  
│ cache-info        Show detailed cache information and keys
│ diagnose-system   Run system diagnostics
│ diagnose-bag      Diagnose bag file for potential issues
│ version           Show version information
```

### 2. 系统诊断测试 ✅
```bash
$ python -m roseApp.rose tools diagnose-system

🔍 System Diagnostics

Python Version: 3.9.21

Dependencies:
  ✅ rosbags: unknown
  ✅ rich: Available
  ✅ typer: Available
  ✅ pyyaml: Available (YAML export supported)

ROS Environment:
  ROS Distro: Not set
  ⚠️  No ROS environment detected

Cache System:
  ✅ Cache system: UnifiedCache

✅ System diagnostics complete
```

### 3. 版本信息测试 ✅
```bash
$ python -m roseApp.rose tools version

Rose: Development version
Python: 3.9.21

Dependencies:
  rosbags: unknown
  rich: unknown
  typer: 0.15.2
  pyyaml: 6.0.2
```

## 🎯 核心优势

### 1. 功能整合
- **统一入口**: 所有工具功能集中在tools命令下
- **一致体验**: 统一的参数风格和输出格式
- **功能完整**: cache管理 + 诊断 + 系统信息

### 2. 架构升级
- **BagManager集成**: 使用最新的bag管理接口
- **ResultHandler支持**: 支持多种输出格式
- **现代化设计**: 清晰的命令分组和帮助信息

### 3. 用户体验
- **直观命令**: 命令名称清晰易懂
- **丰富帮助**: 每个命令都有详细的使用示例
- **多种输出**: 支持table、json、yaml、html等格式

## 🔄 迁移指南

### 从prune命令迁移

| 原命令 | 新命令 | 说明 |
|--------|--------|------|
| `rose prune status` | `rose tools cache-status` | 查看缓存状态 |
| `rose prune clear` | `rose tools cache-clear` | 清理所有缓存 |
| `rose prune clean --all` | `rose tools cache-clear` | 清理所有缓存 |

### 从diagnose命令迁移

| 原命令 | 新命令 | 说明 |
|--------|--------|------|
| `rose diagnose system` | `rose tools diagnose-system` | 系统诊断 |
| `rose diagnose bag <path>` | `rose tools diagnose-bag <path>` | bag文件诊断 |

## 🚀 使用示例

### 日常维护
```bash
# 检查系统状态
rose tools diagnose-system

# 查看缓存使用情况
rose tools cache-status

# 清理缓存释放空间
rose tools cache-clear --yes
```

### 问题诊断
```bash
# 诊断bag文件问题
rose tools diagnose-bag /path/to/problematic.bag --verbose

# 生成HTML诊断报告
rose tools diagnose-bag /path/to/bag.bag --output report.html --format html

# 检查依赖和环境
rose tools diagnose-system
```

### 信息查询
```bash
# 查看版本信息
rose tools version

# 查看缓存详细信息
rose tools cache-info
```

## ✅ 实现成果

1. **🔧 功能整合**: 成功将cache管理和diagnose功能整合到统一的tools命令中
2. **🏗️ 架构升级**: 使用最新的BagManager和ResultHandler架构  
3. **📝 命令简化**: 提供清晰直观的命令结构和帮助信息
4. **🎯 用户体验**: 统一的参数风格和多种输出格式支持
5. **🚀 扩展性**: 易于添加新的工具功能
6. **🐛 问题修复**: 修复了cache递归调用导致的无限循环问题

### 文件变更总结
- ✅ **创建**: `roseApp/cli/tools.py` - 新的统一工具命令
- ✅ **更新**: `roseApp/rose.py` - 主CLI文件，替换prune为tools
- ✅ **删除**: `roseApp/cli/diagnose.py` - 功能已集成到tools中
- ✅ **保留**: `roseApp/cli/prune.py` - 保留原文件以供参考

现在用户可以通过 `rose tools` 命令访问所有实用工具功能，享受统一、现代化的工具体验！ 