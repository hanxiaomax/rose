"""
Rose Event Emitter - Pure NDJSON event emitter for headless CLI.

This module implements the Rose NDJSON Protocol v1-min with 4 event types:
- progress: Progress updates
- data: Intermediate or final data
- done: Successful completion
- error: Operation failure

All events are emitted to stdout as newline-delimited JSON (NDJSON).
"""

import sys
import json
import uuid
import time
import traceback
import functools
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from enum import Enum
from pathlib import Path


class EventType(Enum):
    """Event types for Rose NDJSON protocol"""
    PROGRESS = "progress"
    DATA = "data"
    DONE = "done"
    ERROR = "error"


class TaskContext:
    """
    Task context manager for automatic progress tracking.
    
    Usage:
        with E.task("Loading files", steps=5) as t:
            for i in range(5):
                do_work()
                t.step(f"Loaded file {i+1}")
    """
    
    def __init__(self, emitter: 'EventEmitter', title: str, steps: int):
        """
        Initialize task context.
        
        Args:
            emitter: Parent EventEmitter instance
            title: Task title/description
            steps: Total number of steps
        """
        self.emitter = emitter
        self.title = title
        self.total_steps = steps
        self.current_step = 0
        self.start_time = None
        
    def __enter__(self):
        """Enter task context"""
        self.start_time = time.time()
        self.emitter.progress(0, f"{self.title} (0/{self.total_steps})", 0, self.total_steps)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit task context"""
        if exc_type is None:
            # Successful completion
            self.emitter.progress(100, f"{self.title} complete", self.total_steps, self.total_steps)
        return False
    
    def step(self, msg: Optional[str] = None):
        """
        Advance to next step and emit progress.
        
        Args:
            msg: Optional step message (defaults to step count)
        """
        self.current_step += 1
        percent = (self.current_step / self.total_steps) * 100
        
        if msg is None:
            msg = f"{self.title} ({self.current_step}/{self.total_steps})"
        
        self.emitter.progress(percent, msg, self.current_step, self.total_steps)
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time


class EventEmitter:
    """
    Pure NDJSON event emitter for headless CLI.
    
    Implements Rose NDJSON Protocol v1-min with structured event emission.
    All events are written to stdout as JSON lines.
    
    Minimal API Usage (recommended):
        E = get_emitter()
        E.progress(50, "Processing files")
        E.data([...], label="found_bags")
        E.done({"processed": 10})
        
    Task Context Usage:
        with E.task("Loading", steps=5) as t:
            for i in range(5):
                do_work()
                t.step(f"Loaded item {i+1}")
    
    Legacy API (still supported):
        emitter = EventEmitter()
        emitter.set_context("load", trace_id="abc123")
        emitter.emit_progress(50, "Processing files")
        emitter.emit_data([...], label="found_bags", count=3)
        emitter.emit_done({"processed": 10, "succeeded": 8})
    """
    
    def __init__(self):
        """Initialize event emitter"""
        self._context: Optional[Dict[str, Any]] = None
        self._protocol_info = {
            "name": "rose.ndjson",
            "version": "1.0"
        }
    
    def set_context(
        self, 
        command: str, 
        trace_id: Optional[str] = None, 
        run_id: Optional[str] = None
    ) -> None:
        """
        Set context for all subsequent events.
        
        Args:
            command: Command name (e.g., "load", "extract")
            trace_id: Optional trace ID for request tracking (auto-generated if None)
            run_id: Optional run ID for operation tracking (auto-generated if None)
        """
        # Auto-generate trace_id if not provided
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        # Auto-generate run_id if not provided (format: YYYYMMDD-HHMMSS-shortid)
        if run_id is None:
            now = datetime.utcnow()
            short_id = str(uuid.uuid4())[:8]
            run_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{short_id}"
        
        self._context = {
            "command": command,
            "trace_id": trace_id,
            "run_id": run_id
        }
    
    def _emit_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        """
        Emit event to stdout as NDJSON.
        
        Args:
            event_type: Type of event
            payload: Event payload data
        """
        event: Dict[str, Any] = {
            "event": event_type.value,
            "timestamp": self._get_timestamp(),
            "payload": payload
        }
        
        # Add optional fields
        if self._context:
            event["context"] = self._context
        
        event["protocol"] = self._protocol_info
        
        # Write as single JSON line
        try:
            json_line = json.dumps(event, ensure_ascii=False, allow_nan=False)
            sys.stdout.write(json_line + "\n")
            sys.stdout.flush()
        except (TypeError, ValueError) as e:
            # Fallback error if payload is not JSON serializable
            error_event = {
                "event": "error",
                "timestamp": self._get_timestamp(),
                "payload": {
                    "code": "SERIALIZATION_ERROR",
                    "message": f"Failed to serialize event: {str(e)}",
                    "details": {"event_type": event_type.value}
                }
            }
            sys.stderr.write(json.dumps(error_event) + "\n")
            sys.stderr.flush()
    
    @staticmethod
    def _get_timestamp() -> str:
        """
        Get current UTC timestamp in ISO8601 format.
        
        Returns:
            ISO8601 timestamp string with 'Z' suffix (e.g., "2025-10-08T10:00:00.123Z")
        """
        return datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
    
    def emit_progress(
        self, 
        percent: float, 
        message: str = "", 
        step: Optional[int] = None, 
        total_steps: Optional[int] = None
    ) -> None:
        """
        Emit progress event.
        
        Args:
            percent: Progress percentage (0-100), should be monotonically increasing
            message: Optional descriptive message
            step: Optional current step number (1-based)
            total_steps: Optional total number of steps
        
        Example:
            emitter.emit_progress(50, "Processing files", step=2, total_steps=4)
        """
        payload: Dict[str, Any] = {"percent": percent}
        
        if message:
            payload["message"] = message
        if step is not None:
            payload["step"] = step
        if total_steps is not None:
            payload["total_steps"] = total_steps
        
        self._emit_event(EventType.PROGRESS, payload)
    
    def emit_data(
        self, 
        data: Any, 
        label: Optional[str] = None, 
        count: Optional[int] = None
    ) -> None:
        """
        Emit data event (intermediate or final data).
        
        Args:
            data: Data payload (must be JSON serializable)
            label: Optional label to identify data type (e.g., "found_bags", "topics")
            count: Optional count information (e.g., list length)
        
        Example:
            emitter.emit_data(
                data=[{"path": "a.bag", "size_mb": 12.3}],
                label="found_bags",
                count=1
            )
        """
        payload: Dict[str, Any] = {"data": data}
        
        if label:
            payload["label"] = label
        if count is not None:
            payload["count"] = count
        
        self._emit_event(EventType.DATA, payload)
    
    def emit_done(self, summary: Dict[str, Any]) -> None:
        """
        Emit done event (successful completion).
        
        Args:
            summary: Summary data with operation results
        
        Example:
            emitter.emit_done({
                "processed": 10,
                "succeeded": 8,
                "failed": 2,
                "elapsed_time": 12.5
            })
        
        Note:
            This should be the last event emitted on success.
            Exit code should be 0.
        """
        payload = {"summary": summary}
        self._emit_event(EventType.DONE, payload)
    
    def emit_error(
        self, 
        code: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emit error event (operation failure).
        
        Args:
            code: Machine-readable error code (UPPER_SNAKE_CASE)
            message: Human-readable error message
            details: Optional additional diagnostic information
        
        Example:
            emitter.emit_error(
                "BAG_NOT_FOUND",
                "Bag file not found: demo.bag",
                details={
                    "path": "/path/to/demo.bag",
                    "suggestions": ["Check file path", "Ensure file exists"]
                }
            )
        
        Note:
            This should be the last event emitted on failure.
            Exit code should be non-zero.
        """
        payload: Dict[str, Any] = {
            "code": code,
            "message": message
        }
        
        if details:
            payload["details"] = details
        
        self._emit_event(EventType.ERROR, payload)
    
    # Simplified API (recommended for new code)
    
    def progress(
        self, 
        pct: float, 
        msg: str = "", 
        step: Optional[int] = None, 
        total: Optional[int] = None
    ) -> None:
        """
        Emit progress event (simplified API).
        
        Args:
            pct: Progress percentage (0-100)
            msg: Optional progress message
            step: Optional current step number
            total: Optional total steps
        
        Example:
            E.progress(50, "Processing files", step=5, total=10)
        """
        self.emit_progress(pct, msg, step, total)
    
    def data(
        self, 
        data: Any, 
        label: Optional[str] = None, 
        **kv
    ) -> None:
        """
        Emit data event (simplified API).
        
        Args:
            data: Data payload (must be JSON serializable)
            label: Optional label to identify data type
            **kv: Additional key-value pairs (e.g., count=N)
        
        Example:
            E.data([{"path": "a.bag"}], label="found_bags", count=1)
        """
        count = kv.get('count')
        self.emit_data(data, label, count)
    
    def done(
        self, 
        summary: Optional[Dict[str, Any]] = None, 
        **kv
    ) -> None:
        """
        Emit done event (simplified API).
        
        Args:
            summary: Summary data with operation results
            **kv: Additional key-value pairs to merge into summary
        
        Example:
            E.done({"processed": 10, "succeeded": 8})
            E.done(processed=10, succeeded=8)  # Alternative syntax
        """
        if summary is None:
            summary = {}
        
        # Merge additional kv into summary
        summary = {**summary, **kv}
        
        self.emit_done(summary)
    
    def error(
        self, 
        code: str, 
        message: str, 
        **details
    ) -> None:
        """
        Emit error event (simplified API).
        
        Args:
            code: Machine-readable error code (UPPER_SNAKE_CASE)
            message: Human-readable error message
            **details: Additional diagnostic information
        
        Example:
            E.error("BAG_NOT_FOUND", "File not found", path="/path/to/bag")
        """
        details_dict = details if details else None
        self.emit_error(code, message, details_dict)
    
    def task(self, title: str, steps: int) -> TaskContext:
        """
        Create a task context for automatic progress tracking.
        
        Args:
            title: Task title/description
            steps: Total number of steps
        
        Returns:
            TaskContext instance for use with 'with' statement
        
        Example:
            with E.task("Loading files", steps=5) as t:
                for i in range(5):
                    load_file(i)
                    t.step(f"Loaded file {i+1}")
        """
        return TaskContext(self, title, steps)


# Global emitter instance
_emitter: Optional[EventEmitter] = None


def init_emitter() -> EventEmitter:
    """
    Initialize global event emitter.
    
    This should be called once at application startup (in rose.py callback).
    
    Returns:
        Initialized EventEmitter instance
    """
    global _emitter
    _emitter = EventEmitter()
    return _emitter


def get_emitter() -> EventEmitter:
    """
    Get global event emitter (creates one if not initialized).
    
    Returns:
        Global EventEmitter instance
    """
    global _emitter
    if _emitter is None:
        _emitter = EventEmitter()
    return _emitter


def reset_emitter() -> None:
    """
    Reset global emitter (for testing).
    
    This clears the global emitter instance, allowing fresh initialization.
    """
    global _emitter
    _emitter = None


# E: Shorthand alias for get_emitter() - for convenient usage
# Usage: from roseApp.core.event_emitter import E
class _EmitterProxy:
    """
    Proxy class that forwards all attribute access to the global emitter.
    This allows using E.progress(), E.data(), etc. directly.
    """
    def __getattr__(self, name: str):
        return getattr(get_emitter(), name)


E = _EmitterProxy()


def ndjson_command(name: Optional[str] = None):
    """
    Decorator for Typer commands to automatically handle NDJSON context and errors.
    
    This decorator:
    - Initializes emitter context with command name, trace_id, and run_id
    - Catches all exceptions and emits error events
    - Ensures proper exit codes (0 for success, 1 for failure)
    
    Args:
        name: Optional command name (defaults to function name)
    
    Usage:
        @ndjson_command("load")
        def load_cmd(...):
            E.data([...], label="found_files")
            E.done({"loaded": 10})
    
    Example with automatic command name:
        @ndjson_command()
        def extract(...):
            # Command name will be "extract"
            E.data([...])
            E.done({})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine command name
            cmd_name = name if name is not None else func.__name__.replace('_cmd', '').replace('_', '-')
            
            # Initialize emitter context
            emitter = get_emitter()
            emitter.set_context(cmd_name)
            
            # Track execution time
            start_time = time.time()
            
            try:
                # Execute command
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Check if error event was already emitted (by checking if e is typer.Exit)
                import typer
                if isinstance(e, typer.Exit):
                    # Exit was already handled by command, just re-raise
                    raise
                
                # Emit error event for unexpected exceptions
                error_code = type(e).__name__.upper()
                error_message = str(e)
                
                # Include traceback in details
                tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
                tb_str = ''.join(tb_lines)
                
                emitter.error(
                    code=error_code,
                    message=error_message,
                    traceback=tb_str,
                    elapsed_time=time.time() - start_time
                )
                
                # Exit with error code
                raise typer.Exit(1) from e
        
        return wrapper
    return decorator

