"""
Unified output engine for Rose - NDJSON by default, prettify on demand.

Design Philosophy (v2.0):
- NDJSON first: Default output is structured JSON events for machine consumption
- Prettify optional: --prettify flag provides human-readable text output
- Minimal dependencies: PrettifyBackend uses only ANSI codes, no Rich required
- Clean architecture: Adapter pattern with unified Message API

Architecture:
    OutputEngine (Facade)
        ├── NDJSONBackend (default, machine-readable)
        └── PrettifyBackend (optional, human-readable, ANSI-only)
"""

from enum import Enum
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import sys
import json
from datetime import datetime


class OutputMode(Enum):
    """Output mode selection"""
    NDJSON = "ndjson"      # Structured JSON events (default)
    PRETTIFY = "prettify"  # Human-readable text output


class EventType(Enum):
    """Event types for structured output"""
    PROGRESS = "progress"  # Progress update event
    PARTIAL = "partial"    # Intermediate result event
    DONE = "done"          # Operation complete event
    ERROR = "error"        # Error event
    MESSAGE = "message"    # General message event


class MessageLevel(Enum):
    """Message severity levels"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PRIMARY = "primary"
    ACCENT = "accent"
    MUTED = "muted"


class OutputBackend(ABC):
    """Abstract base class for output backends"""
    
    @abstractmethod
    def emit_progress(self, pct: float, msg: str, step: Optional[int] = None, 
                     total_steps: Optional[int] = None) -> None:
        """Emit progress update"""
        pass
    
    @abstractmethod
    def emit_partial(self, kind: str, data: Any) -> None:
        """Emit intermediate result"""
        pass
    
    @abstractmethod
    def emit_done(self, data: Optional[Any] = None) -> None:
        """Emit completion event"""
        pass
    
    @abstractmethod
    def emit_error(self, code: str, message: str, details: Optional[Dict] = None) -> None:
        """Emit error event"""
        pass
    
    @abstractmethod
    def print_message(self, text: str, level: MessageLevel = MessageLevel.INFO) -> None:
        """Print general message"""
        pass


class NDJSONBackend(OutputBackend):
    """
    Structured JSON event output backend (default mode).
    
    Outputs newline-delimited JSON events for machine consumption.
    Each line is a complete JSON object with event type, timestamp, and data.
    """
    
    def __init__(self):
        pass
    
    def _emit_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Emit JSON event to stdout"""
        event = {
            "event": event_type.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **data
        }
        # Use sys.stdout directly to allow testing with mocked stdout
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    
    def emit_progress(self, pct: float, msg: str, step: Optional[int] = None, 
                     total_steps: Optional[int] = None) -> None:
        """Emit progress event"""
        data = {
            "percent": pct,
            "message": msg
        }
        if step is not None:
            data["step"] = step
        if total_steps is not None:
            data["total_steps"] = total_steps
        self._emit_event(EventType.PROGRESS, data)
    
    def emit_partial(self, kind: str, data: Any) -> None:
        """Emit partial result event"""
        self._emit_event(EventType.PARTIAL, {
            "kind": kind,
            "data": data
        })
    
    def emit_done(self, data: Optional[Any] = None) -> None:
        """Emit completion event"""
        self._emit_event(EventType.DONE, {
            "data": data
        })
    
    def emit_error(self, code: str, message: str, details: Optional[Dict] = None) -> None:
        """Emit error event"""
        self._emit_event(EventType.ERROR, {
            "code": code,
            "message": message,
            "details": details
        })
    
    def print_message(self, text: str, level: MessageLevel = MessageLevel.INFO) -> None:
        """Emit message event"""
        self._emit_event(EventType.MESSAGE, {
            "text": text,
            "level": level.value
        })


class PrettifyBackend(OutputBackend):
    """
    Human-readable text output backend (prettify mode).
    
    Outputs simple, clean text using ANSI color codes.
    No heavy dependencies (Rich, Textual) required.
    Design: minimal, clear, no clutter.
    """
    
    # ANSI color codes
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    
    def __init__(self):
        self._last_progress_pct = -1
    
    def emit_progress(self, pct: float, msg: str, step: Optional[int] = None, 
                     total_steps: Optional[int] = None) -> None:
        """
        Display progress (simplified).
        
        Only outputs at key milestones (0%, 25%, 50%, 75%, 100%)
        to avoid cluttering the output.
        """
        # Only show progress at key percentages to reduce noise
        if pct == 0 or pct >= 100 or (pct % 25 == 0 and pct != self._last_progress_pct):
            status = f"[{pct:>3.0f}%] {msg}"
            if step and total_steps:
                status = f"[{step}/{total_steps}] {status}"
            print(f"{self.CYAN}→{self.RESET} {status}")
            self._last_progress_pct = pct
    
    def emit_partial(self, kind: str, data: Any) -> None:
        """
        Display partial results.
        
        In prettify mode, usually skip to avoid clutter.
        Frontend can handle rich partial data display.
        """
        pass  # Skip in prettify mode for clean output
    
    def emit_done(self, data: Optional[Any] = None) -> None:
        """Display completion message"""
        print(f"{self.GREEN}✓{self.RESET} 操作完成")
        
        # If data provided, show summary
        if data and isinstance(data, dict):
            print()
            for key, value in data.items():
                label = key.replace("_", " ").title()
                print(f"  {label}: {value}")
    
    def emit_error(self, code: str, message: str, details: Optional[Dict] = None) -> None:
        """Display error message"""
        print(f"{self.RED}✗{self.RESET} 错误 [{code}]: {message}", file=sys.stderr)
        
        # Show details if available
        if details and isinstance(details, dict):
            for key, value in details.items():
                if value:
                    print(f"  {key}: {value}", file=sys.stderr)
    
    def print_message(self, text: str, level: MessageLevel = MessageLevel.INFO) -> None:
        """Print message with appropriate styling"""
        icons_and_colors = {
            MessageLevel.SUCCESS: (f"{self.GREEN}✓{self.RESET}", sys.stdout),
            MessageLevel.ERROR: (f"{self.RED}✗{self.RESET}", sys.stderr),
            MessageLevel.WARNING: (f"{self.YELLOW}⚠{self.RESET}", sys.stdout),
            MessageLevel.INFO: (f"{self.CYAN}ℹ{self.RESET}", sys.stdout),
            MessageLevel.PRIMARY: (f"{self.MAGENTA}●{self.RESET}", sys.stdout),
            MessageLevel.ACCENT: (f"{self.CYAN}◆{self.RESET}", sys.stdout),
            MessageLevel.MUTED: (f"{self.GRAY}·{self.RESET}", sys.stdout),
        }
        
        icon, output = icons_and_colors.get(level, ("", sys.stdout))
        print(f"{icon} {text}", file=output)


class OutputEngine:
    """
    Unified output engine facade (v2.0).
    
    Provides a single interface for all output operations,
    delegating to the appropriate backend based on output mode.
    
    Default: NDJSON mode (machine-readable)
    Optional: Prettify mode (human-readable, via --prettify flag)
    
    Usage:
        # Initialize (done in rose.py)
        engine = init_engine(OutputMode.NDJSON)  # or PRETTIFY
        
        # Use in commands
        engine = get_engine()
        engine.emit_progress(50, "Processing...")
        engine.print_message("Done!", MessageLevel.SUCCESS)
        engine.emit_done({"files": 3})
    """
    
    def __init__(self, mode: OutputMode = OutputMode.NDJSON):
        self.mode = mode
        self._backend: OutputBackend = self._create_backend()
    
    def _create_backend(self) -> OutputBackend:
        """Factory method to create backend"""
        if self.mode == OutputMode.NDJSON:
            return NDJSONBackend()
        elif self.mode == OutputMode.PRETTIFY:
            return PrettifyBackend()
        else:
            raise ValueError(f"Unknown output mode: {self.mode}")
    
    # Delegate all methods to backend
    
    def emit_progress(self, pct: float, msg: str, step: Optional[int] = None, 
                     total_steps: Optional[int] = None) -> None:
        """Emit progress update event"""
        self._backend.emit_progress(pct, msg, step, total_steps)
    
    def emit_partial(self, kind: str, data: Any) -> None:
        """Emit intermediate result event"""
        self._backend.emit_partial(kind, data)
    
    def emit_done(self, data: Optional[Any] = None) -> None:
        """Emit operation completion event"""
        self._backend.emit_done(data)
    
    def emit_error(self, code: str, message: str, details: Optional[Dict] = None) -> None:
        """Emit error event"""
        self._backend.emit_error(code, message, details)
    
    def print_message(self, text: str, level: MessageLevel = MessageLevel.INFO) -> None:
        """Print general message"""
        self._backend.print_message(text, level)
    
    def is_ndjson_mode(self) -> bool:
        """Check if running in NDJSON mode (default)"""
        return self.mode == OutputMode.NDJSON
    
    def is_prettify_mode(self) -> bool:
        """Check if running in prettify mode"""
        return self.mode == OutputMode.PRETTIFY
    
    # Deprecated methods for backward compatibility
    # These will be removed in future versions
    
    def is_text_mode(self) -> bool:
        """Deprecated: Use is_prettify_mode() instead"""
        return self.is_prettify_mode()
    
    def is_headless(self) -> bool:
        """Deprecated: Use is_ndjson_mode() instead"""
        return self.is_ndjson_mode()


# Global engine instance
_engine: Optional[OutputEngine] = None


def init_engine(mode: OutputMode = OutputMode.NDJSON) -> OutputEngine:
    """
    Initialize global output engine.
    
    This should be called once at application startup (in rose.py callback).
    
    Args:
        mode: Output mode (NDJSON or PRETTIFY), default is NDJSON
        
    Returns:
        Initialized OutputEngine instance
    """
    global _engine
    _engine = OutputEngine(mode)
    return _engine


def get_engine() -> OutputEngine:
    """
    Get global output engine (creates NDJSON engine if not initialized).
    
    Returns:
        Global OutputEngine instance
    """
    global _engine
    if _engine is None:
        _engine = OutputEngine(OutputMode.NDJSON)  # Default to NDJSON
    return _engine


def reset_engine() -> None:
    """
    Reset global engine (for testing).
    
    This clears the global engine instance, allowing a fresh initialization.
    """
    global _engine
    _engine = None
