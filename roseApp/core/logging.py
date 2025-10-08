"""
Logging configuration module for Rose.

Provides centralized logging setup with file-based output.
No distinction between TUI and CLI modes - unified logging for all use cases.
"""

import time
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

# Global state
_logger: Optional[logging.Logger] = None
_log_file_path: Optional[Path] = None


def get_log_file_path() -> Optional[Path]:
    """Get current log file path
    
    Returns:
        Path to current log file, or None if not initialized
    """
    return _log_file_path


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get logger instance
    
    Args:
        name: Optional logger name for child logger
        
    Returns:
        Logger instance (root or child)
    """
    global _logger
    if _logger is None:
        _logger = _setup_logging()
    return _logger.getChild(name) if name else _logger


def setup_logging() -> logging.Logger:
    """Setup logging system (backward compatibility)
    
    Returns:
        Root logger instance
    """
    return get_logger()


def reconfigure_logging() -> logging.Logger:
    """Reconfigure logging system with current configuration
    
    This is useful when configuration has changed and logging needs to be reinitialized.
    
    Returns:
        Newly configured root logger instance
    """
    global _logger
    _logger = None
    return get_logger()


def _setup_logging() -> logging.Logger:
    """Configure application logging settings
    
    Sets up file-based logging with appropriate log levels from configuration.
    All logs go to files in the logs/ directory.
    
    Returns:
        Configured root logger instance
    """
    global _log_file_path
    
    # Get log level from configuration
    try:
        from .config import get_config
        config = get_config()
        log_level_str = config.log_level.value if hasattr(config.log_level, 'value') else str(config.log_level)
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    except Exception:
        # If config loading fails, use INFO as fallback
        log_level = logging.INFO
    
    # Create log directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Define log file path (single file for all sessions)
    _log_file_path = log_dir / "rose.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Rotating file handler (max 10MB, keep 5 backup files)
    file_handler = RotatingFileHandler(
        _log_file_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Add file handler
    root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level)
    
    # Redirect ROS-related logs to file to avoid terminal pollution
    for logger_name in ["rospy", "rosout", "gnupg", "rosbag", "rosbags", "roslib", "topicmanager", "rosmaster"]:
        ros_logger = logging.getLogger(logger_name)
        
        # Clear existing handlers
        for handler in ros_logger.handlers[:]:
            ros_logger.removeHandler(handler)
            
        # Add file handler
        ros_logger.addHandler(file_handler)
        
        # Set level and disable propagation
        ros_logger.setLevel(log_level)
        ros_logger.propagate = False
    
    return root_logger


def log_cli_error(e: Exception) -> str:
    """Log CLI error and return formatted error message
    
    Args:
        e: Exception to log
        
    Returns:
        Formatted error message string with log file path
    """
    global _log_file_path
    
    logger = get_logger()
    logger.error(f"Error: {str(e)}", exc_info=True)
    
    if _log_file_path:
        return f"Error: {str(e)}\nDetailed information has been recorded to: {_log_file_path}"
    else:
        return f"Error: {str(e)}"

