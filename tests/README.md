# Rose ROS Bag Tool - 测试套件

本测试套件专注于核心转换逻辑和命令行模式的全面测试。

## 测试结构

### 核心功能测试 (`tests/core/`)
专注于核心转换逻辑和算法的单元测试：

- **`test_parser_core.py`** - 核心parser功能测试
  - Parser工厂创建测试
  - RosbagsBagParser和BagParser基础功能
  - 方法签名验证
  - 文件覆盖处理
  - 自定义异常处理

- **`test_topic_filtering.py`** - Topic过滤功能测试
  - 单个和多个topic过滤
  - 不存在topic的处理
  - 大小写敏感性测试
  - Whitelist文件加载
  - 过滤逻辑验证

- **`test_compression.py`** - 压缩功能测试
  - 压缩类型验证 (none/bz2/lz4)
  - 压缩可用性检测
  - RosbagsBagParser压缩处理
  - 传统parser压缩支持
  - 错误处理和参数流传递

### CLI测试 (`tests/cli/`)
专注于命令行界面和参数处理的集成测试：

- **`test_filter_command.py`** - Filter命令核心测试
  - 基本命令功能
  - 单文件和目录处理
  - 输出路径处理
  - 错误处理

- **`test_parameters.py`** - 参数验证测试
  - 所有CLI参数验证
  - 参数组合测试
  - 默认值验证
  - 帮助信息测试

### 共享工具 (`tests/`)
- **`conftest.py`** - Pytest配置和共享fixtures
- **`run_tests.py`** - 便捷的测试运行脚本

## 运行测试

### 基本用法

```bash
# 运行所有测试
python tests/run_tests.py all

# 运行核心功能测试
python tests/run_tests.py core

# 运行CLI测试
python tests/run_tests.py cli

# 运行测试并生成覆盖率报告
python tests/run_tests.py coverage
```

### 高级用法

```bash
# 运行特定测试文件
python tests/run_tests.py specific --path tests/core/test_parser_core.py

# 运行特定测试函数
python tests/run_tests.py specific --path tests/core/test_parser_core.py::TestRosbagsBagParser::test_filter_bag_basic_functionality

# 按标记运行测试
python tests/run_tests.py marker --marker unit
python tests/run_tests.py marker --marker integration

# 安装测试依赖
python tests/run_tests.py all --install-deps
```

### 直接使用pytest

```bash
# 运行所有测试
pytest tests/ -v

# 运行核心功能测试
pytest tests/core/ -v -m unit

# 运行CLI测试
pytest tests/cli/ -v -m integration

# 生成覆盖率报告
pytest tests/ --cov=roseApp --cov-report=html --cov-report=term-missing

# 运行特定测试
pytest tests/core/test_parser_core.py::TestRosbagsBagParser -v
```

## 测试标记

测试使用pytest标记进行分类：

- `@pytest.mark.unit` - 单元测试（核心功能）
- `@pytest.mark.integration` - 集成测试（CLI）
- `@pytest.mark.slow` - 慢速测试（可选择跳过）

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"
```

## 测试覆盖范围

### 核心转换逻辑覆盖
- ✅ Parser工厂和创建逻辑
- ✅ RosbagsBagParser核心功能
- ✅ BagParser (legacy) 核心功能
- ✅ Topic过滤算法
- ✅ 压缩功能 (none/bz2/lz4)
- ✅ 文件覆盖处理
- ✅ 异常处理和传播
- ✅ 参数验证

### CLI模式覆盖
- ✅ 所有命令行参数
- ✅ 参数组合和冲突处理
- ✅ 单文件处理模式
- ✅ 目录批处理模式
- ✅ 输出路径处理逻辑
- ✅ 错误处理和用户反馈
- ✅ 帮助信息和文档

## 测试数据和Mock

### 共享Fixtures
```python
@pytest.fixture
def temp_dir():
    """临时目录"""

@pytest.fixture
def mock_bag_data():
    """模拟bag数据"""

@pytest.fixture
def test_bag_file(temp_dir):
    """测试bag文件"""
```

### Mock策略
- 使用`unittest.mock`模拟外部依赖
- 模拟文件系统操作
- 模拟rosbags和legacy rosbag库
- 模拟CLI输入/输出

## 持续集成

测试设计为可在CI/CD环境中运行：

```yaml
# GitHub Actions示例
- name: Run tests
  run: |
    python tests/run_tests.py all --install-deps
    python tests/run_tests.py coverage
```

## 测试原则

1. **快速执行** - 大量使用Mock避免实际文件操作
2. **独立性** - 每个测试独立运行，不依赖其他测试
3. **全面覆盖** - 覆盖核心逻辑和边界情况
4. **可维护性** - 清晰的测试结构和命名
5. **文档化** - 每个测试都有明确的目的和说明

## 添加新测试

### 核心功能测试
```python
# tests/core/test_new_feature.py
class TestNewFeature:
    def test_basic_functionality(self):
        # 测试基本功能
        pass
    
    def test_error_handling(self):
        # 测试错误处理
        pass
```

### CLI测试
```python
# tests/cli/test_new_command.py
class TestNewCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_command_execution(self, runner):
        # 测试命令执行
        pass
```

## 故障排除

### 常见问题

1. **Import错误** - 确保项目根目录在Python路径中
2. **Mock问题** - 确保mock的路径与实际import路径一致
3. **文件权限** - 确保测试文件有执行权限
4. **依赖缺失** - 使用`--install-deps`安装测试依赖

### 调试技巧

```bash
# 详细输出
pytest tests/ -v -s

# 只运行失败的测试
pytest tests/ --lf

# 进入调试模式
pytest tests/ --pdb

# 显示覆盖率缺失
pytest tests/ --cov=roseApp --cov-report=term-missing
```
