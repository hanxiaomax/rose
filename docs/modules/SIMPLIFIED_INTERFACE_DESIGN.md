# 简化接口设计方案

## 当前问题分析

### 接口重复问题
- Engine 和 Parser 都有过滤、验证、统计功能
- 数据结构不统一，增加维护成本
- 异步和同步接口混杂，使用复杂

### 职责边界模糊
- Engine 包含了太多Parser的功能
- Parser 缺乏统一的操作抽象
- 错误处理分散在各个模块

## 简化设计方案

### 1. 统一数据模型

```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

class OperationType(Enum):
    """操作类型枚举"""
    FILTER = "filter"
    ANALYZE = "analyze" 
    VALIDATE = "validate"
    INSPECT = "inspect"
    COPY = "copy"

@dataclass
class BagOperation:
    """统一的Bag操作配置"""
    operation_type: OperationType
    input_path: Path
    output_path: Optional[Path] = None
    topics: Optional[List[str]] = None
    time_range: Optional[tuple] = None
    compression: str = "none"
    overwrite: bool = False
    options: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class OperationResult:
    """统一的操作结果"""
    success: bool
    operation: BagOperation
    processing_time: float
    output_size: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    
    @property
    def size_str(self) -> str:
        """Human readable size string"""
        if self.output_size == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(self.output_size)
        
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {units[i]}"
```

### 2. 简化Parser接口

```python
class IBagParser(ABC):
    """简化的Bag解析器接口"""
    
    @abstractmethod
    def execute_operation(self, operation: BagOperation) -> Dict[str, Any]:
        """执行bag操作 - 统一入口"""
        pass
    
    # 保留核心底层方法
    @abstractmethod
    def load_bag(self, bag_path: str) -> Tuple[List[str], Dict[str, str], Tuple]:
        """加载bag基础信息"""
        pass
    
    @abstractmethod
    def read_messages(self, bag_path: str, topics: List[str]):
        """读取消息流"""
        pass

class RosbagsBagParser(IBagParser):
    """高性能解析器实现"""
    
    def execute_operation(self, operation: BagOperation) -> Dict[str, Any]:
        """根据操作类型分发到具体方法"""
        if operation.operation_type == OperationType.FILTER:
            return self._filter_bag(operation)
        elif operation.operation_type == OperationType.ANALYZE:
            return self._analyze_bag(operation)
        elif operation.operation_type == OperationType.VALIDATE:
            return self._validate_bag(operation)
        elif operation.operation_type == OperationType.INSPECT:
            return self._inspect_bag(operation)
        else:
            raise ValueError(f"Unsupported operation: {operation.operation_type}")
    
    def _filter_bag(self, operation: BagOperation) -> Dict[str, Any]:
        """内部过滤实现"""
        # 实现过滤逻辑
        pass
    
    def _analyze_bag(self, operation: BagOperation) -> Dict[str, Any]:
        """内部分析实现"""
        # 实现分析逻辑
        pass
```

### 3. 简化Engine接口

```python
class BagEngine:
    """简化的异步处理引擎"""
    
    def __init__(self, max_workers: int = 4):
        self.io_manager = AsyncIOManager(max_workers)
        self.parser = create_best_parser()
        self.logger = get_logger()
    
    async def process_async(
        self, 
        operation: BagOperation,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> OperationResult:
        """统一的异步处理入口"""
        start_time = time.time()
        
        try:
            if progress_callback:
                progress_callback(10.0)
            
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            result_data = await loop.run_in_executor(
                self.io_manager.executor,
                self.parser.execute_operation,
                operation
            )
            
            if progress_callback:
                progress_callback(100.0)
            
            # 封装结果
            return OperationResult(
                success=True,
                operation=operation,
                processing_time=time.time() - start_time,
                data=result_data,
                output_size=operation.output_path.stat().st_size if operation.output_path and operation.output_path.exists() else 0
            )
            
        except Exception as e:
            return OperationResult(
                success=False,
                operation=operation,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def batch_process_async(
        self,
        operations: List[BagOperation],
        progress_callback: Optional[Callable[[BagOperation, float], None]] = None
    ) -> Dict[Path, OperationResult]:
        """批量异步处理"""
        
        async def process_single(op: BagOperation) -> OperationResult:
            progress_cb = None
            if progress_callback:
                progress_cb = lambda p: progress_callback(op, p)
            return await self.process_async(op, progress_cb)
        
        # 并发执行
        tasks = [process_single(op) for op in operations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        result_dict = {}
        for op, result in zip(operations, results):
            if isinstance(result, Exception):
                result_dict[op.input_path] = OperationResult(
                    success=False,
                    operation=op,
                    processing_time=0.0,
                    error_message=str(result)
                )
            else:
                result_dict[op.input_path] = result
        
        return result_dict
```

### 4. 使用示例

```python
# 创建操作配置
filter_op = BagOperation(
    operation_type=OperationType.FILTER,
    input_path=Path("input.bag"),
    output_path=Path("filtered.bag"),
    topics=["topic1", "topic2"],
    compression="lz4",
    overwrite=True
)

# 异步执行单个操作
engine = get_engine()
result = await engine.process_async(filter_op, progress_callback=print_progress)

# 批量处理
operations = [
    BagOperation(OperationType.ANALYZE, Path("bag1.bag")),
    BagOperation(OperationType.VALIDATE, Path("bag2.bag")),
    BagOperation(OperationType.FILTER, Path("bag3.bag"), topics=["topic1"])
]

results = await engine.batch_process_async(operations)
```

## 接口对比

### 简化前（复杂）
```python
# 多个分散的方法
await engine.filter_bag_async(path, topics, output, compression, time_range, overwrite, callback)
await engine.validate_bag_async(path)
await engine.get_bag_statistics_async(path)
await engine.analyze_bag_async(path, analysis_type, callback)

# 参数繁多，容易出错
parser.filter_bag(input_bag, output_bag, topics, time_range, progress_callback, compression, overwrite)
```

### 简化后（清晰）
```python
# 统一的操作入口
operation = BagOperation(OperationType.FILTER, input_path, output_path, topics=topics)
result = await engine.process_async(operation, callback)

# 批量处理
operations = [BagOperation(...), BagOperation(...)]
results = await engine.batch_process_async(operations)
```

## 优势总结

1. **接口统一**: 所有操作通过统一的 `process_async()` 入口
2. **配置清晰**: `BagOperation` 封装所有参数，减少错误
3. **结果一致**: `OperationResult` 统一返回格式
4. **易于扩展**: 新增操作类型只需在enum中添加
5. **职责分离**: Engine专注异步编排，Parser专注数据操作
6. **类型安全**: 强类型检查减少运行时错误
7. **可测试性**: 清晰的接口边界便于单元测试

这个设计保持了模块分离的优势，同时大大简化了接口复杂度。 