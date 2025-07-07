# Rose ROS Bag Tool - 测试套件

精简的测试套件，专注于核心parser功能和基本CLI命令行功能。

## 📁 测试结构

### 核心功能测试 (`tests/core/`)
- **`test_parser.py`** - 核心parser功能测试
  - Parser创建和基本API
  - 单/多topic过滤
  - 基本压缩功能
  - 白名单加载
  - 错误处理

### CLI测试 (`tests/cli/`)
- **`test_cli.py`** - 基本CLI功能测试
  - 单/多topic过滤命令
  - 白名单文件支持
  - 压缩选项
  - Dry run模式
  - 目录输出
  - 错误处理

### 测试数据
- **`demo.bag`** - 696MB真实ROS bag文件
- **`fixtures/test_whitelist.txt`** - 测试白名单文件

## 🚀 运行测试

### 运行所有测试
```bash
pytest tests/ -v
```

### 运行核心parser测试
```bash
pytest tests/core/test_parser.py -v
```

### 运行CLI测试
```bash
pytest tests/cli/test_cli.py -v
```

### 生成覆盖率报告
```bash
pytest tests/ --cov=roseApp --cov-report=html --cov-report=term-missing
```

### 运行特定测试
```bash
# 测试单topic过滤
pytest tests/core/test_parser.py::TestParserCore::test_single_topic_filtering -v

# 测试CLI基本功能
pytest tests/cli/test_cli.py::TestCLIBasic::test_cli_single_topic_filtering -v
```

## 🎯 测试覆盖范围

### Parser功能
- ✅ Parser创建和类型验证
- ✅ 真实bag文件读取和分析
- ✅ 单topic和多topic过滤
- ✅ 基本压缩功能
- ✅ 白名单文件加载
- ✅ 文件覆盖保护
- ✅ 错误处理（无效路径、不存在的topic）

### CLI功能
- ✅ 帮助信息显示
- ✅ 单topic和多topic过滤命令
- ✅ 白名单文件支持
- ✅ 压缩选项
- ✅ Dry run预览模式
- ✅ 目录输出支持
- ✅ 错误处理（无效topic、缺少参数）

## 📊 真实数据测试

使用696MB的真实ROS bag文件（`demo.bag`）进行测试：
- **消息数**: 5,390条
- **Topics**: 17个不同的topics
- **类型**: 传感器数据、GPS、雷达、激光雷达等
- **优势**: 避免mock依赖，测试真实场景

## 🔧 测试原则

1. **精简必要** - 只测试核心功能，避免重复测试
2. **真实数据** - 使用真实bag文件，避免mock依赖
3. **快速执行** - 测试运行时间控制在合理范围内
4. **清晰命名** - 测试名称清楚表达测试目的
5. **独立性** - 每个测试独立运行，不依赖其他测试

## 📈 性能基准

- **Parser单topic过滤**: ~1-2秒
- **Parser多topic过滤**: ~2-3秒
- **CLI命令执行**: ~1-2秒
- **总测试运行时间**: ~30-40秒

## 🛠️ 添加新测试

### 添加Parser测试
```python
def test_new_parser_feature(self, demo_bag_path, temp_output_dir):
    """Test description"""
    parser = RosbagsBagParser()
    # 测试逻辑
    assert result == expected
```

### 添加CLI测试
```python
def test_new_cli_feature(self, runner, demo_bag_path, temp_output_dir):
    """Test description"""
    result = runner.invoke(app, [demo_bag_path, output_path, "--option"])
    assert result.exit_code == 0
```

## 🎯 注意事项

- 测试使用临时目录，会自动清理
- 需要`tests/demo.bag`文件存在
- 需要`tests/fixtures/test_whitelist.txt`文件存在
- 测试依赖真实的rosbags库功能
