# Rose Command Test Suite

这个目录包含了 Rose 所有命令的 bash 测试脚本，用于验证各个命令和选项的功能。

## 测试文件

| 测试文件 | 测试命令 | 描述 |
|---------|---------|------|
| `test_load.sh` | `rose load` | 测试 bag 文件加载功能 |
| `test_extract.sh` | `rose extract` | 测试主题提取功能 |
| `test_compress.sh` | `rose compress` | 测试 bag 文件压缩功能 |
| `test_inspect.sh` | `rose inspect` | 测试 bag 文件检查功能 |
| `test_data.sh` | `rose data` | 测试数据操作命令 |
| `test_cache.sh` | `rose cache` | 测试缓存管理功能 |
| `test_plugin.sh` | `rose plugin` | 测试插件系统功能 |
| `run_all_tests.sh` | - | 运行所有测试的主脚本 |

## 使用方法

### 运行所有测试

```bash
# 从 Rose 根目录运行
cd /workspaces/rose
bash tests/bash_tests/run_all_tests.sh
```

### 运行单个测试

```bash
# 运行特定命令的测试
cd /workspaces/rose
bash tests/bash_tests/test_load.sh
bash tests/bash_tests/test_extract.sh
# ... 其他测试文件
```

## 测试内容

每个测试脚本都会测试以下内容：

### 基本功能测试
- 命令帮助信息显示
- 基本命令执行
- 各种选项组合

### 错误处理测试
- 无效参数处理
- 不存在的文件处理
- 权限错误处理

### 选项组合测试
- 单个选项使用
- 多个选项组合使用
- 边界情况测试

## 测试数据

所有测试使用 `roseApp/tests/demo3.bag` 作为输入文件。

## 输出

测试脚本会：
- 显示彩色输出，便于识别成功/失败
- 创建临时输出文件用于验证
- 自动清理测试生成的文件
- 提供详细的测试进度信息

## 测试覆盖的命令选项

### load 命令
- `--verbose`, `--force`, `--dry-run`
- `--build-index`, `--workers`
- 文件模式匹配

### extract 命令  
- `--topics`, `--output`, `--compression`
- `--reverse`, `--workers`, `--verbose`
- `--dry-run`, `--yes`

### compress 命令
- `--compression` (lz4, bz2)
- `--output`, `--workers`, `--verbose`
- `--validate`, `--dry-run`, `--yes`

### inspect 命令
- `--topics`, `--show-fields`, `--sort`
- `--reverse`, `--output`, `--verbose`
- `--debug`

### data 命令
- `data info`: `--topic`, `--columns`, `--sample`
- `data export`: `--topics`, `--output`, `--start-time`
- `--end-time`, `--search`, `--include-index`
- `--interactive`, `--yes`

### cache 命令
- `--content`, `--verbose`
- `cache export`: `--output`
- `cache clear`: `--yes`, 特定文件清理

### plugin 命令
- `list`: `--verbose`, `--enabled`, `--type`
- `info`, `create`, `run`, `enable/disable`
- `reload`, `install/uninstall`

## 错误处理

测试脚本包含以下错误处理：
- 优雅处理不存在的文件
- 测试无效参数的处理
- 验证错误消息的适当性
- 确保程序不会崩溃

## 清理机制

每个测试脚本都会：
- 在开始前清理可能的残留文件
- 在测试过程中创建必要的临时文件
- 在结束时清理所有测试生成的文件

## 注意事项

1. 测试需要在 Rose 根目录下运行
2. 确保 `roseApp/tests/demo3.bag` 文件存在
3. 某些测试可能需要一定的执行时间
4. 插件测试会创建和删除临时插件
5. 缓存测试会清理现有缓存数据

## 扩展测试

要添加新的测试：

1. 创建新的 `test_<command>.sh` 文件
2. 遵循现有测试的结构和风格
3. 在 `run_all_tests.sh` 中添加新测试脚本
4. 更新此 README 文件

## 故障排除

如果测试失败：

1. 检查 Rose 是否正确安装
2. 确认测试 bag 文件存在
3. 检查文件权限
4. 查看详细的错误输出
5. 运行单个测试脚本进行调试
