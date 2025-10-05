# Rose Command Smoke Tests

这个目录包含了 Rose 所有命令的简单烟雾测试脚本，用于快速验证基本功能。

## 测试文件

| 测试文件 | 测试命令 | 描述 |
|---------|---------|------|
| `quick_test.sh` | 所有命令 | 快速烟雾测试 |
| `test_load.sh` | `rose load` | 加载命令基本功能 |
| `test_extract.sh` | `rose extract` | 提取命令基本功能 |
| `test_compress.sh` | `rose compress` | 压缩命令基本功能 |
| `test_inspect.sh` | `rose inspect` | 检查命令基本功能 |
| `test_data.sh` | `rose data` | 数据命令基本功能 |
| `test_cache.sh` | `rose cache` | 缓存命令基本功能 |
| `test_plugin.sh` | `rose plugin` | 插件命令基本功能 |
| `run_all_tests.sh` | - | 运行所有测试的主脚本 |

## 使用方法

### 快速烟雾测试

```bash
# 从 Rose 根目录运行
cd /workspaces/rose
bash tests/bash_tests/quick_test.sh
```

### 运行所有测试

```bash
cd /workspaces/rose
bash tests/bash_tests/run_all_tests.sh
```

### 运行单个测试

```bash
cd /workspaces/rose
bash tests/bash_tests/test_load.sh
```

## 测试特点

### 简单直接
- 只测试基本功能，不做复杂测试
- 快速执行，适合CI/CD
- 重点验证命令能正常启动和运行

### 烟雾测试内容
- 命令帮助信息显示
- 基本命令执行
- 错误处理验证
- 核心选项测试

### 测试数据
所有测试使用 `roseApp/tests/demo3.bag` 作为输入文件。

## 测试覆盖

### load 命令 (已迁移到新系统)
- 帮助显示
- 基本加载
- verbose, force, dry-run, build-index, workers 选项
- 错误处理

### 其他命令
- 帮助显示
- 基本功能验证
- 简单错误处理测试

## 输出

测试脚本特点：
- 彩色输出，清晰显示成功/失败
- 简洁的进度信息
- 自动清理临时文件
- 快速执行

## 适配当前系统

这些测试已经适配当前的CLI系统：
- 支持新的错误处理系统
- 支持配置管理系统
- 兼容迁移后的命令结构
- 简化测试逻辑，专注核心功能

## 运行要求

1. 在 Rose 根目录下运行
2. 确保 `roseApp/tests/demo3.bag` 文件存在
3. Python环境已正确配置
4. 所需依赖已安装

## 故障排除

如果测试失败：

1. 检查CLI是否能正常启动：`python -m roseApp.rose --help`
2. 确认测试bag文件存在
3. 检查Python依赖是否完整
4. 查看具体错误输出

## 扩展测试

要添加新测试：

1. 保持简单直接的原则
2. 只测试核心功能
3. 遵循现有测试风格
4. 更新此README文件
