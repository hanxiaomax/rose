from dataclasses import dataclass
from typing import Any

@dataclass
class ProgressEvent:
    current: int
    total: int
    description: str = ""

@dataclass
class LogEvent:
    message: str
    level: str = "INFO"  # INFO, WARN, ERROR

@dataclass
class ResultEvent:
    success: bool
    data: Any = None  # 携带最终的返回数据（如文件路径、统计字典等）
