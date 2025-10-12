"""
Unified error handling system for Rose.

This module provides a consistent error handling strategy across the entire application.
All Rose-specific errors should inherit from RoseError for proper handling and logging.
"""

import sys
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path


class ErrorCode(Enum):
    """Standard error codes for Rose operations"""
    
    # General errors (1000-1099)
    UNKNOWN_ERROR = (1000, "An unknown error occurred: {}")
    OPERATION_CANCELLED = (1001, "Operation cancelled by user")
    INVALID_ARGUMENT = (1002, "Invalid argument: {}")
    
    # File errors (1100-1199)
    FILE_NOT_FOUND = (1100, "File not found: {}")
    FILE_ALREADY_EXISTS = (1101, "File already exists: {}")
    FILE_NOT_READABLE = (1102, "File is not readable: {}")
    FILE_NOT_WRITABLE = (1103, "File is not writable: {}")
    DIRECTORY_NOT_FOUND = (1104, "Directory not found: {}")
    INVALID_FILE_FORMAT = (1105, "Invalid file format: {}")
    
    # Bag file errors (1200-1299)
    BAG_NOT_FOUND = (1200, "Bag file not found: {}")
    BAG_CORRUPTED = (1201, "Bag file is corrupted: {}")
    BAG_EMPTY = (1202, "Bag file is empty")
    BAG_INVALID_FORMAT = (1203, "Invalid bag file format: {}")
    BAG_LOAD_FAILED = (1204, "Failed to load bag file: {}")
    BAG_PARSE_ERROR = (1205, "Error parsing bag file: {}")
    
    # Topic errors (1300-1399)
    TOPIC_NOT_FOUND = (1300, "Topic not found: {}")
    TOPIC_EMPTY = (1301, "Topic has no messages: {}")
    NO_TOPICS_SELECTED = (1302, "No topics selected for operation")
    INVALID_TOPIC_PATTERN = (1303, "Invalid topic pattern: {}")
    
    # Cache errors (1400-1499)
    CACHE_ERROR = (1400, "Cache operation failed: {}")
    CACHE_CORRUPTED = (1401, "Cache data is corrupted: {}")
    CACHE_MISS = (1402, "Cache miss for key: {}")
    CACHE_WRITE_FAILED = (1403, "Failed to write to cache: {}")
    CACHE_READ_FAILED = (1404, "Failed to read from cache: {}")
    
    # Compression errors (1500-1599)
    INVALID_COMPRESSION = (1500, "Invalid compression type: {}")
    COMPRESSION_FAILED = (1501, "Compression failed: {}")
    DECOMPRESSION_FAILED = (1502, "Decompression failed: {}")
    COMPRESSION_NOT_AVAILABLE = (1503, "Compression type not available: {}")
    
    # Export/Extract errors (1600-1699)
    EXPORT_FAILED = (1600, "Export operation failed: {}")
    EXTRACT_FAILED = (1601, "Extraction failed: {}")
    INVALID_OUTPUT_FORMAT = (1602, "Invalid output format: {}")
    OUTPUT_PATH_INVALID = (1603, "Invalid output path: {}")
    
    # Plugin errors (1700-1799)
    PLUGIN_NOT_FOUND = (1700, "Plugin not found: {}")
    PLUGIN_LOAD_FAILED = (1701, "Failed to load plugin: {}")
    PLUGIN_INIT_FAILED = (1702, "Plugin initialization failed: {}")
    PLUGIN_EXECUTION_FAILED = (1703, "Plugin execution failed: {}")
    PLUGIN_INVALID = (1704, "Invalid plugin: {}")
    
    # Configuration errors (1800-1899)
    CONFIG_ERROR = (1800, "Configuration error: {}")
    CONFIG_NOT_FOUND = (1801, "Configuration file not found: {}")
    CONFIG_INVALID = (1802, "Invalid configuration: {}")
    
    # DataFrame errors (1900-1999)
    DATAFRAME_NOT_AVAILABLE = (1900, "DataFrame not available for topic: {}")
    DATAFRAME_BUILD_FAILED = (1901, "Failed to build DataFrame: {}")
    DATAFRAME_EMPTY = (1902, "DataFrame is empty")
    
    # Memory errors (2000-2099)
    OUT_OF_MEMORY = (2000, "Out of memory: {}")
    MEMORY_LIMIT_EXCEEDED = (2001, "Memory limit exceeded: {}")
    
    # Validation errors (2100-2199)
    VALIDATION_FAILED = (2100, "Validation failed: {}")
    INVALID_TIME_RANGE = (2101, "Invalid time range: {}")
    INVALID_PARAMETER = (2102, "Invalid parameter: {}")
    
    @property
    def code(self) -> int:
        """Get error code"""
        return self.value[0]
    
    @property
    def message_template(self) -> str:
        """Get error message template"""
        return self.value[1]
    
    def format_message(self, *args) -> str:
        """Format error message with arguments"""
        try:
            return self.message_template.format(*args)
        except (IndexError, KeyError):
            return f"{self.message_template} (formatting error with args: {args})"


class RoseError(Exception):
    """
    Base exception for all Rose-specific errors.
    
    Provides consistent error handling with error codes, messages,
    and context information for debugging.
    """
    
    def __init__(
        self,
        error_code: ErrorCode,
        *args,
        details: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize Rose error.
        
        Args:
            error_code: Standard error code from ErrorCode enum
            *args: Arguments to format the error message
            details: Optional detailed error information
            context: Optional context dictionary for debugging
            cause: Optional underlying exception that caused this error
        """
        self.error_code = error_code
        self.args_provided = args
        self.details = details
        self.context = context or {}
        self.cause = cause
        
        # Format message (keep it clean, details handled separately)
        self.message = error_code.format_message(*args)
        
        # Initialize exception with message only
        # Details are stored separately and displayed by error handler
        super().__init__(self.message)
    
    @property
    def code(self) -> int:
        """Get error code number"""
        return self.error_code.code
    
    def __str__(self) -> str:
        """String representation of error (message only, without details)"""
        return self.message
    
    def __repr__(self) -> str:
        """Representation of error for debugging (compact format)"""
        return f"{self.__class__.__name__}({self.error_code.name}): {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization"""
        return {
            'error_code': self.error_code.name,
            'code': self.code,
            'message': self.message,
            'details': self.details,
            'context': self.context,
            'cause': str(self.cause) if self.cause else None
        }


# Specific error classes for common scenarios

class FileError(RoseError):
    """Error related to file operations"""
    pass


class BagFileError(RoseError):
    """Error related to bag file operations"""
    pass


class TopicError(RoseError):
    """Error related to topic operations"""
    pass


class CacheError(RoseError):
    """Error related to cache operations"""
    pass


class CompressionError(RoseError):
    """Error related to compression operations"""
    pass


class ExportError(RoseError):
    """Error related to export/extract operations"""
    pass


class PluginError(RoseError):
    """Error related to plugin operations"""
    pass


class ConfigError(RoseError):
    """Error related to configuration"""
    pass


class DataFrameError(RoseError):
    """Error related to DataFrame operations"""
    pass


class ValidationError(RoseError):
    """Error related to validation"""
    pass


# Helper functions for error handling

def handle_cli_error(error: Exception, verbose: bool = False) -> int:
    """
    Handle CLI errors and return appropriate exit code.
    
    Args:
        error: Exception to handle
        verbose: Whether to show detailed error information
        
    Returns:
        Exit code (0-255)
    """
    import traceback as tb
    import logging
    
    logger = logging.getLogger(__name__)
    
    # In headless mode, all error output should be via EventEmitter
    # This function only logs to file and returns exit code
    if isinstance(error, RoseError):
        # Log Rose-specific error
        logger.error(f"Error ({error.code}): {error.message}", exc_info=verbose)
        
        if error.details:
            logger.debug(f"Details: {error.details}")
        
        if verbose and error.context:
            logger.debug(f"Context: {error.context}")
        
        # Return error code (modulo 256 for valid exit code)
        return error.code % 256
    
    else:
        # Log generic error
        logger.error(f"Unexpected error: {str(error)}", exc_info=verbose)
        
        return 1


def validate_file_exists(path: Path, error_code: ErrorCode = ErrorCode.FILE_NOT_FOUND) -> Path:
    """
    Validate that a file exists.
    
    Args:
        path: Path to validate
        error_code: Error code to use if validation fails
        
    Returns:
        Path if valid
        
    Raises:
        FileError: If file doesn't exist
    """
    if not path.exists():
        raise FileError(error_code, str(path))
    return path


def validate_bag_file(path: Path) -> Path:
    """
    Validate that a bag file exists and has correct format.
    
    Args:
        path: Path to bag file
        
    Returns:
        Path if valid
        
    Raises:
        BagFileError: If bag file is invalid
    """
    validate_file_exists(path, ErrorCode.BAG_NOT_FOUND)
    
    if path.suffix != '.bag':
        raise BagFileError(
            ErrorCode.BAG_INVALID_FORMAT,
            str(path),
            details="File must have .bag extension"
        )
    
    return path


def validate_compression_type(compression: str) -> str:
    """
    Validate compression type.
    
    Args:
        compression: Compression type to validate
        
    Returns:
        Compression type if valid
        
    Raises:
        CompressionError: If compression type is invalid
    """
    valid_types = ['none', 'bz2', 'lz4']
    
    if compression not in valid_types:
        raise CompressionError(
            ErrorCode.INVALID_COMPRESSION,
            compression,
            details=f"Valid types: {', '.join(valid_types)}"
        )
    
    return compression


def validate_topics_selected(topics: list) -> list:
    """
    Validate that topics are selected.
    
    Args:
        topics: List of topics
        
    Returns:
        Topics list if valid
        
    Raises:
        TopicError: If no topics selected
    """
    if not topics or len(topics) == 0:
        raise TopicError(
            ErrorCode.NO_TOPICS_SELECTED,
            details="At least one topic must be selected"
        )
    
    return topics


def safe_execute(func, *args, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR, **kwargs):
    """
    Safely execute a function and wrap exceptions in RoseError.
    
    Args:
        func: Function to execute
        *args: Function arguments
        error_code: Error code to use if function fails
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        RoseError: If function raises exception
    """
    try:
        return func(*args, **kwargs)
    except RoseError:
        # Re-raise Rose errors as-is
        raise
    except Exception as e:
        # Wrap other exceptions
        raise RoseError(
            error_code,
            str(e),
            cause=e,
            context={'function': func.__name__}
        )


# Context manager for error handling

class ErrorContext:
    """
    Context manager for consistent error handling.
    
    Usage:
        with ErrorContext(ErrorCode.BAG_LOAD_FAILED, bag_path):
            # Operations that might fail
            load_bag(bag_path)
    """
    
    def __init__(
        self,
        error_code: ErrorCode,
        *args,
        details: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.args = args
        self.details = details
        self.context = context or {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        
        if isinstance(exc_val, RoseError):
            # Already a Rose error, don't wrap
            return False
        
        # Wrap exception in RoseError
        raise RoseError(
            self.error_code,
            *self.args,
            details=self.details or str(exc_val),
            context=self.context,
            cause=exc_val
        ) from exc_val



