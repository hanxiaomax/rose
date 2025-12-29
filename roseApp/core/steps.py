#!/usr/bin/env python3
"""
Step-by-step progress management for CLI operations.
Provides a unified interface for displaying progressive operations.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from .output import get_output


class StepManager:
    """
    Manages step-by-step progress display for CLI operations.
    
    Usage:
        steps = StepManager()
        
        steps.section("Finding bag files")
        steps.add_item("Scanning directory")
        # ... do work ...
        steps.complete_item("Found 5 bags")
        
        steps.section("Loading bags")
        steps.add_item("demo.bag")
        # ... do work ...
        steps.complete_item("demo.bag", status="done", details="0.5s")
    """
    
    def __init__(self):
        self.out = get_output()
        self._current_section = None
        self._items: Dict[str, Dict[str, Any]] = {}
    
    def section(self, title: str) -> None:
        """
        Start a new section.
        
        Args:
            title: Section title
        """
        self._current_section = title
        self.out.step_section(title)
    
    def add_item(self, key: str, message: Optional[str] = None, status: str = "processing") -> None:
        """
        Add a new item to current section.
        
        Args:
            key: Unique key for this item
            message: Display message (defaults to key)
            status: Initial status
        """
        display_msg = message or key
        self._items[key] = {
            "message": display_msg,
            "status": status
        }
        self.out.status_item(display_msg, status)
    
    def update_item(self, key: str, message: Optional[str] = None, status: Optional[str] = None, 
                    details: Optional[str] = None) -> None:
        """
        Update an existing item (prints new line with updated status).
        
        Args:
            key: Item key
            message: Updated message (optional)
            status: New status (optional)
            details: Additional details to append (optional)
        """
        if key not in self._items:
            # If item doesn't exist, create it
            self.add_item(key, message, status or "processing")
            return
        
        item = self._items[key]
        
        # Update stored values
        if message:
            item["message"] = message
        if status:
            item["status"] = status
        
        # Build display message
        display_msg = item["message"]
        if details:
            display_msg = f"{display_msg} {details}"
        
        # Print updated status
        self.out.status_item(display_msg, item["status"])
    
    def complete_item(self, key: str, message: Optional[str] = None, status: str = "done", 
                     details: Optional[str] = None) -> None:
        """
        Mark an item as complete.
        
        Args:
            key: Item key
            message: Updated message (optional)
            status: Completion status (done/error)
            details: Additional details
        """
        self.update_item(key, message, status, details)
    
    def skip_item(self, key: str, message: str, reason: Optional[str] = None) -> None:
        """
        Mark an item as skipped.
        
        Args:
            key: Item key
            message: Display message
            reason: Skip reason
        """
        display_msg = message
        if reason:
            display_msg = f"{display_msg} · {reason}"
        self.update_item(key, display_msg, "skip")
    
    def error_item(self, key: str, message: str, error: Optional[str] = None) -> None:
        """
        Mark an item as error.
        
        Args:
            key: Item key
            message: Display message
            error: Error message
        """
        display_msg = message
        if error:
            display_msg = f"{display_msg} · {error}"
        self.update_item(key, display_msg, "error")
    
    def get_item_status(self, key: str) -> Optional[str]:
        """Get status of an item."""
        return self._items.get(key, {}).get("status")
    
    def summary(self) -> Dict[str, int]:
        """
        Get summary of all items.
        
        Returns:
            Dict with counts of each status
        """
        summary = {
            "total": len(self._items),
            "done": 0,
            "error": 0,
            "skip": 0,
            "processing": 0
        }
        
        for item in self._items.values():
            status = item.get("status", "processing")
            if status in summary:
                summary[status] += 1
        
        return summary


def create_step_manager() -> StepManager:
    """Create a new step manager instance."""
    return StepManager()

