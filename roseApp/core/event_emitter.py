"""
Rose Event Emitter - Pure NDJSON event emitter for headless CLI.

This module implements the Rose NDJSON Protocol v2 with 4 event types:
- progress: Progress updates
- data: Intermediate or final data
- done: Successful completion
- error: Operation failure

All events are emitted to stdout as newline-delimited JSON (NDJSON).

Protocol v2 Changes:
- Flat header/payload structure (no nested context)
- Support for parallel task grouping (group_id/task_id)
- Integrated heartbeat mechanism for smooth progress updates
"""

import sys
import json
import uuid
import time
import traceback
import functools
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Literal
from enum import Enum
from pathlib import Path
from contextlib import contextmanager


class EventType(Enum):
    """Event types for Rose NDJSON protocol"""
    PROGRESS = "progress"
    DATA = "data"
    DONE = "done"
    ERROR = "error"


class HeartbeatManager:
    """
    Manages periodic heartbeat for progress updates.
    
    Ensures frontend receives regular updates even during long operations.
    If no new progress is sent within the interval, the last progress is
    resent with an updated timestamp.
    
    Usage:
        with E.heartbeat(interval=1.0) as hb:
            hb.update(message="Processing", mode="count", current=0, total=10)
            for i in range(10):
                do_long_operation()  # Heartbeat sends updates automatically
                hb.update(message=f"Processed {i+1}", mode="count", 
                         current=i+1, total=10)
    """
    
    def __init__(self, emitter: 'EventEmitter', interval: float = 1.0):
        """
        Initialize heartbeat manager.
        
        Args:
            emitter: Parent EventEmitter instance
            interval: Heartbeat interval in seconds (default: 1.0)
        """
        self._emitter = emitter
        self._interval = interval
        self._last_progress: Optional[Dict[str, Any]] = None
        self._last_update_time = 0.0
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._enabled = True
    
    def start(self) -> None:
        """Start heartbeat background thread"""
        if self._heartbeat_thread is not None:
            return  # Already started
        
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def stop(self) -> None:
        """Stop heartbeat thread and wait for cleanup"""
        if self._heartbeat_thread is None:
            return
        
        self._stop_event.set()
        self._heartbeat_thread.join(timeout=2.0)
        self._heartbeat_thread = None
    
    def update(self, **progress_kwargs) -> None:
        """
        Update progress and record for heartbeat replay.
        
        This method:
        1. Records the progress parameters for potential replay
        2. Immediately emits the progress event
        
        Args:
            **progress_kwargs: Arguments to pass to emit_progress()
        """
        with self._lock:
            self._last_progress = progress_kwargs.copy()
            self._last_update_time = time.time()
        
        # Immediately emit
        self._emitter.emit_progress(**progress_kwargs)
    
    def disable(self) -> None:
        """Temporarily disable heartbeat (e.g., during fast operations)"""
        with self._lock:
            self._enabled = False
    
    def enable(self) -> None:
        """Re-enable heartbeat"""
        with self._lock:
            self._enabled = True
    
    def _heartbeat_loop(self) -> None:
        """Background thread that sends periodic heartbeats"""
        while not self._stop_event.is_set():
            time.sleep(self._interval)
            
            if self._stop_event.is_set():
                break
            
            progress_kwargs = None
            with self._lock:
                if not self._enabled or self._last_progress is None:
                    continue
                
                # Check if we need to send a heartbeat
                elapsed_since_last = time.time() - self._last_update_time
                if elapsed_since_last >= self._interval:
                    # Resend last progress (will get new timestamp automatically)
                    progress_kwargs = self._last_progress.copy()
            
            # Emit outside the lock to avoid deadlock
            if progress_kwargs:
                self._emitter.emit_progress(**progress_kwargs)
    
    def __enter__(self):
        """Enter context manager"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager"""
        self.stop()
        return False


class EventEmitter:
    """
    Pure NDJSON event emitter for headless CLI.
    
    Implements Rose NDJSON Protocol v2 with structured event emission.
    All events are written to stdout as JSON lines with flat header/payload structure.
    
    Protocol v2 Features:
    - Unix timestamp (float, seconds since epoch)
    - Simplified ID format: trace_id:run_id[:task_id]
    - Version field instead of protocol object
    - Flat header structure (no nested context)
    
    Minimal API Usage (recommended):
        E = get_emitter()
        E.progress("Processing files", mode="count", current=5, total=10)
        E.data([...], label="found_bags")
        E.done({"processed": 10})
    
    Heartbeat Usage:
        with E.heartbeat(interval=1.0) as hb:
            hb.update(message="Loading", mode="count", current=0, total=10)
            for i in range(10):
                do_work()  # Heartbeat sends updates automatically
                hb.update(message=f"Loaded {i+1}", mode="count", 
                         current=i+1, total=10)
    
    Task-Level Events (Parallel Execution):
        # Run-level event (default)
        E.progress("Loading bags", mode="count", current=0, total=10)
        # ID: "abc123:20251012-100000-xyz"
        
        # Task-level event
        with E.task_scope("bag1.bag"):
            E.progress("Analyzing bag1.bag", mode="stage", 
                      stage="analysis", stage_index=1, total_stages=3)
        # ID: "abc123:20251012-100000-xyz:bag1.bag"
    """
    
    def __init__(self):
        """Initialize event emitter"""
        self._context: Optional[Dict[str, Any]] = None
        self._version = "2.0"
    
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
            "run_id": run_id,
            "id": None  # Format: trace_id:run_id or trace_id:run_id:task_id for task-level events
        }
    
    def set_id(self, task_id: Optional[str] = None) -> None:
        """
        Set event ID for grouping and correlation.
        
        ID Format: trace_id:run_id[:task_id]
        - trace_id:run_id - Run-level events (default)
        - trace_id:run_id:task_id - Task-level events (parallel tasks)
        
        Args:
            task_id: Optional task identifier for parallel tasks
        
        Example:
            # Run-level event (default)
            E.progress("Loading bags", mode="count", current=0, total=10)
            # ID: "abc123:20251012-100000-xyz"
            
            # Task-level event (parallel execution)
            E.set_id("bag1.bag")
            E.progress("Analyzing bag1.bag", mode="stage", ...)
            # ID: "abc123:20251012-100000-xyz:bag1.bag"
        """
        if self._context is None:
            raise RuntimeError("Context not initialized. Call set_context() first.")
        
        trace_id = self._context["trace_id"]
        run_id = self._context["run_id"]
        
        if task_id:
            # Task-level: trace_id:run_id:task_id
            self._context["id"] = f"{trace_id}:{run_id}:{task_id}"
        else:
            # Run-level: trace_id:run_id
            self._context["id"] = f"{trace_id}:{run_id}"
    
    def clear_id(self) -> None:
        """Clear custom ID (reset to run-level)"""
        if self._context is not None:
            trace_id = self._context["trace_id"]
            run_id = self._context["run_id"]
            self._context["id"] = f"{trace_id}:{run_id}"
    
    @contextmanager
    def task_scope(self, task_id: str):
        """
        Context manager for automatic task-level ID management.
        
        Args:
            task_id: Task identifier for parallel tasks
        
        Usage:
            with E.task_scope("bag1.bag"):
                E.progress("Analyzing bag1.bag", mode="stage", ...)
                E.data({"status": "loaded"}, label="task_complete")
            # ID automatically cleared after context exit
        """
        self.set_id(task_id)
        try:
            yield
        finally:
            self.clear_id()
    
    def _emit_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        """
        Emit event to stdout as NDJSON v2 format.
        
        Format:
        {
            "header": {
                "type": "progress",
                "version": "2.0",
                "timestamp": 1728734400.123,
                "command": "load",
                "id": "abc123:20251012-100000-xyz" or "abc123:20251012-100000-xyz:bag1.bag"
            },
            "payload": {
                // Business-specific data
            }
        }
        
        ID Format:
        - Run-level: trace_id:run_id
        - Task-level: trace_id:run_id:task_id
        
        Args:
            event_type: Type of event
            payload: Event payload data (business data only)
        """
        # Build header
        header: Dict[str, Any] = {
            "type": event_type.value,
            "version": self._version,
            "timestamp": self._get_timestamp()
        }
        
        # Add context fields to header
        if self._context:
            header["command"] = self._context["command"]
            
            # Ensure ID is set (default to run-level if not set)
            if self._context.get("id") is None:
                trace_id = self._context["trace_id"]
                run_id = self._context["run_id"]
                header["id"] = f"{trace_id}:{run_id}"
            else:
                header["id"] = self._context["id"]
        
        # Construct final event
        event: Dict[str, Any] = {
            "header": header,
            "payload": payload
        }
        
        # Write as single JSON line
        try:
            json_line = json.dumps(event, ensure_ascii=False, allow_nan=False)
            sys.stdout.write(json_line + "\n")
            sys.stdout.flush()
        except (TypeError, ValueError) as e:
            # Fallback error if payload is not JSON serializable
            error_header = {
                "type": "error",
                "version": self._version,
                "timestamp": self._get_timestamp()
            }
            if self._context:
                error_header["command"] = self._context["command"]
                trace_id = self._context["trace_id"]
                run_id = self._context["run_id"]
                error_header["id"] = f"{trace_id}:{run_id}"
            
            error_event = {
                "header": error_header,
                "payload": {
                    "code": "SERIALIZATION_ERROR",
                    "message": f"Failed to serialize event: {str(e)}",
                    "details": {"event_type": event_type.value}
                }
            }
            sys.stderr.write(json.dumps(error_event) + "\n")
            sys.stderr.flush()
    
    @staticmethod
    def _get_timestamp() -> float:
        """
        Get current Unix timestamp (seconds since epoch).
        
        Returns:
            Unix timestamp as float with millisecond precision
        """
        return time.time()
    
    def emit_progress(
        self,
        message: str,
        mode: Literal["stage", "count", "heartbeat"],
        
        # Stage mode fields
        stage: Optional[str] = None,
        stage_index: Optional[int] = None,
        total_stages: Optional[int] = None,
        
        # Count mode fields
        current: Optional[int] = None,
        total: Optional[int] = None,
        
        # Optional fields
        elapsed: Optional[float] = None
    ) -> None:
        """
        Emit progress event with standardized payload.
        
        Args:
            message: Human-readable status message
            mode: Progress mode (stage/count/heartbeat)
            stage: Stage identifier for stage mode
            stage_index: Current stage index (1-based) for stage mode
            total_stages: Total number of stages for stage mode
            current: Current item count for count/heartbeat mode
            total: Total item count for count mode
            elapsed: Elapsed time in seconds
            
        Examples:
            # Stage mode
            emit_progress("Analyzing metadata", mode="stage", 
                         stage="analysis", stage_index=2, total_stages=5)
            
            # Count mode
            emit_progress("Loaded bag3.bag", mode="count",
                         current=3, total=10, elapsed=5.2)
            
            # Stage mode with heartbeat
            emit_progress("Compressing (running...)", mode="stage",
                         stage="compression", stage_index=3, total_stages=5,
                         current=15, elapsed=45.0)
        """
        payload = {
            "message": message,
            "mode": mode
        }
        
        if stage is not None:
            payload["stage"] = stage
        if stage_index is not None:
            payload["stage_index"] = stage_index
        if total_stages is not None:
            payload["total_stages"] = total_stages
        if current is not None:
            payload["current"] = current
        if total is not None:
            payload["total"] = total
        if elapsed is not None:
            payload["elapsed"] = elapsed
        
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
        message: str,
        mode: Literal["stage", "count", "heartbeat"],
        
        # Stage mode fields
        stage: Optional[str] = None,
        stage_index: Optional[int] = None,
        total_stages: Optional[int] = None,
        
        # Count mode fields
        current: Optional[int] = None,
        total: Optional[int] = None,
        
        # Optional fields
        elapsed: Optional[float] = None
    ) -> None:
        """
        Emit progress event (simplified API).
        
        Args:
            message: Human-readable status message
            mode: Progress mode (stage/count/heartbeat)
            stage: Stage identifier for stage mode
            stage_index: Current stage index (1-based) for stage mode
            total_stages: Total number of stages for stage mode
            current: Current item count for count/heartbeat mode
            total: Total item count for count mode
            elapsed: Elapsed time in seconds
        
        Examples:
            # Stage mode
            E.progress("Analyzing metadata", mode="stage", 
                      stage="analysis", stage_index=2, total_stages=5)
            
            # Count mode
            E.progress("Loaded bag3.bag", mode="count",
                      current=3, total=10, elapsed=5.2)
            
            # Stage mode with heartbeat
            E.progress("Compressing (running...)", mode="stage",
                      stage="compression", stage_index=3, total_stages=5,
                      current=15, elapsed=45.0)
        """
        self.emit_progress(
            message=message,
            mode=mode,
            stage=stage,
            stage_index=stage_index,
            total_stages=total_stages,
            current=current,
            total=total,
            elapsed=elapsed
        )
    
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
    
    # Heartbeat API
    
    def create_heartbeat(self, interval: float = 1.0) -> HeartbeatManager:
        """
        Create a heartbeat manager for periodic progress updates.
        
        Args:
            interval: Heartbeat interval in seconds (default: 1.0)
        
        Returns:
            HeartbeatManager instance
        
        Usage:
            hb = E.create_heartbeat(interval=1.0)
            hb.start()
            try:
                hb.update(message="Processing", mode="count", current=0, total=10)
                # ... long operations ...
            finally:
                hb.stop()
        """
        return HeartbeatManager(self, interval)
    
    @contextmanager
    def heartbeat(self, interval: float = 1.0):
        """
        Context manager for automatic heartbeat management.
        
        Args:
            interval: Heartbeat interval in seconds (default: 1.0)
        
        Yields:
            HeartbeatManager instance
        
        Usage:
            with E.heartbeat(interval=1.0) as hb:
                hb.update(message="Loading", mode="count", current=0, total=10)
                for i in range(10):
                    do_long_operation()  # Heartbeat sends updates automatically
                    hb.update(message=f"Loaded {i+1}", mode="count", 
                             current=i+1, total=10)
        """
        hb = HeartbeatManager(self, interval)
        with hb:
            yield hb
    

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

