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
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class EventType(Enum):
    """Event types for Rose NDJSON protocol"""
    PROGRESS = "progress"
    DATA = "data"
    DONE = "done"
    ERROR = "error"


class EventEmitter:
    """
    Pure NDJSON event emitter for headless CLI.
    
    Implements Rose NDJSON Protocol v1-min with structured event emission.
    All events are written to stdout as JSON lines.
    
    Usage:
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
            trace_id: Optional trace ID for request tracking
            run_id: Optional run ID for operation tracking
        """
        self._context = {"command": command}
        if trace_id:
            self._context["trace_id"] = trace_id
        if run_id:
            self._context["run_id"] = run_id
    
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

