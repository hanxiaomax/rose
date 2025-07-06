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

- **`test_real_bag.py`** - 真实Bag文件测试 🆕
  - 使用696MB真实ROS bag文件，减少mock依赖
  - 真实数据过滤、消息计数验证、压缩功能
  - 白名单功能测试、错误处理测试
  - 性能测试、解析器对比测试
  - 22个测试，100%通过

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

- **`test_real_bag_cli.py`** - 真实Bag文件CLI测试 🆕
  - 使用696MB真实bag文件测试CLI功能
  - 基本过滤、多topic过滤、白名单支持
  - 压缩选项、并行处理、Dry Run模式
  - 目录操作和批处理模拟
  - 13个测试，100%通过

### 共享工具 (`tests/`)
- **`conftest.py`** - Pytest配置和共享fixtures
- **`run_tests.py`** - 便捷的测试运行脚本

### 测试数据文件 🆕
- **`demo.bag`** - 696MB真实ROS bag文件
  - 17个不同topics，5,390条消息
  - 包含传感器数据、GPS、雷达、激光雷达等
  - 用于真实场景测试，替代mock数据
- **`fixtures/test_whitelist.txt`** - 测试白名单文件
  - 包含demo.bag中存在的topics
  - 支持注释和空行处理测试

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

# 运行真实bag文件测试 🆕
python tests/run_tests.py specific --path tests/core/test_real_bag.py
python tests/run_tests.py specific --path tests/cli/test_real_bag_cli.py
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

# 运行真实bag文件测试 🆕
pytest tests/core/test_real_bag.py tests/cli/test_real_bag_cli.py -v

# 运行特定真实bag测试
pytest tests/core/test_real_bag.py::TestRealBagFiltering::test_single_topic_filtering -v
pytest tests/cli/test_real_bag_cli.py::TestRealBagCLI::test_cli_basic_filtering -v
```

## 覆盖率报告

### 生成覆盖率报告

```bash
# 使用run_tests.py生成覆盖率报告
python tests/run_tests.py coverage

# 直接使用pytest生成覆盖率报告
pytest tests/ --cov=roseApp --cov-report=html --cov-report=term-missing

# 或者分步执行
coverage run -m pytest tests/
coverage report        # 命令行文本报告
coverage html          # 生成HTML交互式报告
```

### 查看文本覆盖率报告

```bash
# 查看总体覆盖率摘要
coverage report

# 查看详细覆盖率报告（包含缺失行号）
coverage report -m

# 只显示特定模块的覆盖率
coverage report roseApp/core/parser.py

# 按覆盖率排序显示
coverage report --sort=cover
```

### 查看HTML交互式报告

HTML报告提供了最详细和直观的覆盖率分析：

```bash
# 生成HTML报告
coverage html

# 启动HTTP服务器查看报告
cd htmlcov
python -m http.server 8080

# 在浏览器中访问: http://localhost:8080
```

#### HTML报告功能特性

- **📁 多视图支持**
  - **Files**: 文件级覆盖率概览
  - **Functions**: 函数级覆盖率分析  
  - **Classes**: 类级覆盖率分析

- **🔍 交互功能**
  - **实时搜索**: 输入框过滤文件
  - **列排序**: 点击表头按不同指标排序
  - **隐藏100%**: 隐藏完全覆盖的文件
  - **键盘快捷键**: 
    - `f/s/m/x/b/p/c` - 列排序
    - `[/]` - 上一个/下一个文件
    - `?` - 显示/隐藏帮助

- **📈 详细分析**
  - **行级覆盖率**: 红色=未覆盖，绿色=已覆盖
  - **分支覆盖率**: 条件分支执行情况
  - **精确定位**: 具体行号定位未测试代码

### 覆盖率指标解释

| 指标 | 说明 |
|------|------|
| **statements** | 代码语句总数 |
| **missing** | 未覆盖的语句数 |
| **branches** | 分支条件总数 |
| **partial** | 部分覆盖的分支数 |
| **coverage** | 覆盖率百分比 |

### 覆盖率目标

| 模块类型 | 目标覆盖率 | 当前状态 | 备注 |
|----------|------------|----------|------|
| 核心逻辑 | ≥80% | 🟡 需改进 | parser.py 53% |
| CLI功能 | ≥70% | 🟠 进行中 | filter.py 40% |
| 工具函数 | ≥90% | 🟢 良好 | util.py 66% |
| 整体项目 | ≥75% | 🟠 36% | ⬆️ 从33%提升 |

### 覆盖率改进建议

1. **优先处理0%覆盖率模块**
   ```bash
   # 查看未覆盖模块
   coverage report --show-missing | grep "0%"
   ```

2. **关注核心功能模块**
   - `roseApp/core/parser.py` - 当前53% (⬆️ 从48%提升)
   - `roseApp/cli/filter.py` - 当前40% (⬆️ 从34%提升)

3. **真实bag测试贡献 🆕**
   - 新增35个真实bag测试，100%通过
   - 覆盖率从33%提升到36%
   - 减少mock依赖，提高测试真实性
   - 验证大文件处理能力(696MB)

4. **增加边界情况测试**
   - 异常处理路径
   - 错误输入处理
   - 边界条件测试

### 停止HTTP服务器

查看完HTML报告后，停止HTTP服务器：

```bash
# 停止服务器
pkill -f 'python -m http.server 8080'

# 或者按 Ctrl+C 停止
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
