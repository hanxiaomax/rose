import traceback
import sys
import os
from typing import Optional, Dict, Any, Callable, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from roseApp.core.util import get_logger
from roseApp.core.legacy_parser import LegacyParserWrapper

class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for better organization"""
    VALIDATION = "validation"
    FILE_IO = "file_io"
    PARSING = "parsing"
    PROCESSING = "processing"
    NETWORK = "network"
    SYSTEM = "system"
    USER_INPUT = "user_input"
    CONFIGURATION = "configuration"

@dataclass
class ErrorContext:
    """Context information for errors"""
    command: str
    operation: str
    file_path: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class UnifiedErrorHandler:
    """Unified error handling system for all commands"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.console = Console()
        self.error_history: List[Dict[str, Any]] = []
        self.legacy_wrapper = LegacyParserWrapper()
        
    def handle_error(self, 
                    error: Exception, 
                    context: ErrorContext,
                    severity: ErrorSeverity = ErrorSeverity.ERROR,
                    category: ErrorCategory = ErrorCategory.PROCESSING,
                    suggestions: Optional[List[str]] = None,
                    show_traceback: bool = False,
                    exit_code: int = 1) -> None:
        """Handle errors with unified formatting and logging"""
        
        # Record error for history
        error_record = {
            'timestamp': context.timestamp,
            'command': context.command,
            'operation': context.operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'severity': severity.value,
            'category': category.value,
            'file_path': context.file_path,
            'parameters': context.parameters
        }
        self.error_history.append(error_record)
        
        # Log error
        self._log_error(error, context, severity, category)
        
        # Display error to user
        self._display_error(error, context, severity, category, suggestions, show_traceback)
        
        # Exit if it's a critical error
        if severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            sys.exit(exit_code)
    
    def handle_validation_error(self, 
                               error: Exception, 
                               context: ErrorContext,
                               parameter_name: str,
                               valid_values: Optional[List[str]] = None) -> None:
        """Handle parameter validation errors"""
        
        suggestions = []
        if valid_values:
            suggestions.append(f"Valid values for {parameter_name}: {', '.join(valid_values)}")
        
        suggestions.extend([
            f"Check your {parameter_name} parameter",
            "Use --help to see available options"
        ])
        
        self.handle_error(
            error, 
            context,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            suggestions=suggestions
        )
    
    def handle_file_error(self, 
                         error: Exception, 
                         context: ErrorContext,
                         file_path: str,
                         operation: str) -> None:
        """Handle file-related errors"""
        
        suggestions = []
        
        if not os.path.exists(file_path):
            suggestions.append(f"File does not exist: {file_path}")
            suggestions.append("Check the file path and try again")
        elif not os.access(file_path, os.R_OK):
            suggestions.append(f"No read permission for: {file_path}")
            suggestions.append("Check file permissions")
        elif operation == "write" and not os.access(os.path.dirname(file_path), os.W_OK):
            suggestions.append(f"No write permission for directory: {os.path.dirname(file_path)}")
            suggestions.append("Check directory permissions or choose a different output location")
        
        self.handle_error(
            error,
            context,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FILE_IO,
            suggestions=suggestions
        )
    
    def handle_parsing_error(self, 
                           error: Exception, 
                           context: ErrorContext,
                           parser_type: str,
                           bag_path: str) -> None:
        """Handle bag parsing errors with fallback suggestions"""
        
        suggestions = []
        
        # Check if legacy parser should be suggested
        if parser_type == "rosbags":
            suggestions.append("Trying legacy rosbag parser as fallback")
            suggestions.append("Consider installing rosbags: pip install rosbags")
        
        # Check if file is corrupted
        if os.path.exists(bag_path):
            file_size = os.path.getsize(bag_path)
            if file_size == 0:
                suggestions.append("Bag file is empty")
            elif file_size < 1024:
                suggestions.append("Bag file might be corrupted (very small size)")
        
        suggestions.extend([
            "Check if the bag file is valid",
            "Try: rosbag info <bag_file> to verify the bag",
            "The bag file might be from a different ROS version"
        ])
        
        self.handle_error(
            error,
            context,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PARSING,
            suggestions=suggestions
        )
    
    def handle_processing_error(self, 
                              error: Exception, 
                              context: ErrorContext,
                              operation_details: Optional[Dict[str, Any]] = None) -> None:
        """Handle processing errors during bag operations"""
        
        suggestions = []
        
        if operation_details:
            if "memory" in str(error).lower():
                suggestions.append("Processing might require more memory")
                suggestions.append("Try processing smaller chunks or use --parallel option")
            
            if "disk" in str(error).lower() or "space" in str(error).lower():
                suggestions.append("Insufficient disk space")
                suggestions.append("Free up disk space or choose a different output location")
        
        suggestions.extend([
            "Check system resources (memory, disk space)",
            "Try running the operation with fewer parallel workers",
            "Consider using compression to reduce output size"
        ])
        
        self.handle_error(
            error,
            context,
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PROCESSING,
            suggestions=suggestions
        )
    
    def handle_legacy_parser_warning(self, 
                                   bag_path: str, 
                                   context: ErrorContext,
                                   performance_impact: Optional[str] = None) -> None:
        """Handle legacy parser warnings"""
        
        # Use legacy parser wrapper for consistent messaging
        self.legacy_wrapper.show_performance_warning(
            bag_path, 
            expected_time=performance_impact
        )
        
        # Don't exit for warnings
        
    def display_error_summary(self, recent_count: int = 5) -> None:
        """Display a summary of recent errors"""
        
        if not self.error_history:
            self.console.print("[green]No errors recorded[/green]")
            return
        
        recent_errors = self.error_history[-recent_count:]
        
        table = Table(box=box.SIMPLE, title="Recent Errors", title_style="bold red")
        table.add_column("Time", style="cyan", min_width=10)
        table.add_column("Command", style="magenta", min_width=10)
        table.add_column("Category", style="yellow", min_width=10)
        table.add_column("Error", style="red", min_width=30)
        
        for error in recent_errors:
            table.add_row(
                error['timestamp'].strftime("%H:%M:%S"),
                error['command'],
                error['category'],
                error['error_message'][:50] + "..." if len(error['error_message']) > 50 else error['error_message']
            )
        
        self.console.print(table)
    
    def _log_error(self, 
                   error: Exception, 
                   context: ErrorContext,
                   severity: ErrorSeverity, 
                   category: ErrorCategory) -> None:
        """Log error details for debugging"""
        
        log_message = (
            f"Error in {context.command}.{context.operation}: "
            f"{type(error).__name__}: {str(error)}"
        )
        
        if context.file_path:
            log_message += f" (file: {context.file_path})"
        
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _display_error(self, 
                      error: Exception, 
                      context: ErrorContext,
                      severity: ErrorSeverity, 
                      category: ErrorCategory,
                      suggestions: Optional[List[str]] = None,
                      show_traceback: bool = False) -> None:
        """Display formatted error to user"""
        
        # Choose colors based on severity
        color_map = {
            ErrorSeverity.INFO: "blue",
            ErrorSeverity.WARNING: "yellow",
            ErrorSeverity.ERROR: "red",
            ErrorSeverity.CRITICAL: "bold red"
        }
        
        color = color_map.get(severity, "red")
        
        # Create error panel
        error_text = Text()
        error_text.append(f"{severity.value.upper()}: ", style=f"bold {color}")
        error_text.append(f"{type(error).__name__}: {str(error)}", style=color)
        
        if context.file_path:
            error_text.append(f"\nFile: {context.file_path}", style="dim")
        
        if context.operation:
            error_text.append(f"\nOperation: {context.operation}", style="dim")
        
        panel = Panel(
            error_text,
            title=f"[bold]{context.command.upper()} Error[/bold]",
            title_align="left",
            border_style=color,
            padding=(1, 2)
        )
        
        self.console.print(panel)
        
        # Show suggestions if available
        if suggestions:
            self.console.print("\n[bold cyan]Suggestions:[/bold cyan]")
            for i, suggestion in enumerate(suggestions, 1):
                self.console.print(f"  {i}. {suggestion}")
        
        # Show traceback if requested
        if show_traceback:
            self.console.print("\n[bold red]Traceback:[/bold red]")
            self.console.print(traceback.format_exc())
    
    def create_context(self, 
                      command: str, 
                      operation: str,
                      file_path: Optional[str] = None,
                      parameters: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """Create error context for current operation"""
        
        return ErrorContext(
            command=command,
            operation=operation,
            file_path=file_path,
            parameters=parameters
        )

# Global error handler instance
error_handler = UnifiedErrorHandler()

# Convenience functions for common error types
def handle_validation_error(error: Exception, 
                          command: str, 
                          parameter_name: str,
                          valid_values: Optional[List[str]] = None) -> None:
    """Handle parameter validation errors"""
    context = error_handler.create_context(command, "parameter_validation")
    error_handler.handle_validation_error(error, context, parameter_name, valid_values)

def handle_file_error(error: Exception, 
                     command: str, 
                     file_path: str,
                     operation: str = "read") -> None:
    """Handle file-related errors"""
    context = error_handler.create_context(command, "file_operation", file_path=file_path)
    error_handler.handle_file_error(error, context, file_path, operation)

def handle_parsing_error(error: Exception, 
                        command: str, 
                        parser_type: str,
                        bag_path: str) -> None:
    """Handle bag parsing errors"""
    context = error_handler.create_context(command, "bag_parsing", file_path=bag_path)
    error_handler.handle_parsing_error(error, context, parser_type, bag_path)

def handle_processing_error(error: Exception, 
                           command: str, 
                           operation: str,
                           details: Optional[Dict[str, Any]] = None) -> None:
    """Handle processing errors"""
    context = error_handler.create_context(command, operation)
    error_handler.handle_processing_error(error, context, details)

def handle_legacy_parser_warning(bag_path: str, 
                                command: str,
                                performance_impact: Optional[str] = None) -> None:
    """Handle legacy parser warnings"""
    context = error_handler.create_context(command, "parser_selection", file_path=bag_path)
    error_handler.handle_legacy_parser_warning(bag_path, context, performance_impact)

def display_error_summary(recent_count: int = 5) -> None:
    """Display recent error summary"""
    error_handler.display_error_summary(recent_count)

# Context manager for error handling
class ErrorHandlingContext:
    """Context manager for automatic error handling"""
    
    def __init__(self, command: str, operation: str, file_path: Optional[str] = None):
        self.command = command
        self.operation = operation
        self.file_path = file_path
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            context = error_handler.create_context(
                self.command, 
                self.operation, 
                file_path=self.file_path
            )
            
            # Determine error category based on exception type
            if "ValidationError" in str(exc_type):
                category = ErrorCategory.VALIDATION
            elif "FileNotFoundError" in str(exc_type) or "PermissionError" in str(exc_type):
                category = ErrorCategory.FILE_IO
            elif "ParserError" in str(exc_type):
                category = ErrorCategory.PARSING
            else:
                category = ErrorCategory.PROCESSING
            
            error_handler.handle_error(
                exc_val,
                context,
                severity=ErrorSeverity.ERROR,
                category=category
            )
        
        return False  # Don't suppress exceptions 