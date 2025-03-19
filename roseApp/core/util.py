"""
ROS bag parser module using C++ implementation for better performance.
This module provides the same interface as parser.py but uses rosbag_io_py for operations.
"""

import time
import logging
import os
import tempfile
import sys
from pathlib import Path
from typing import Tuple, Optional
from textual.logging import TextualHandler

# 应用程序模式
class AppMode:
    TUI = "tui"
    CLI = "cli"

# 添加日志变量
_logger = None
_log_file_path = None
_app_mode = AppMode.TUI  # 默认为TUI模式

def set_app_mode(mode: str):
    """设置应用程序模式 (TUI 或 CLI)"""
    global _app_mode
    if mode in [AppMode.TUI, AppMode.CLI]:
        _app_mode = mode

def get_log_file_path():
    """Get current log file path"""
    return _log_file_path

def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    global _logger
    if _logger is None:
        _logger = _setup_logging()
    return _logger.getChild(name) if name else _logger

def setup_logging():
    """Backward compatibility function"""
    return get_logger()

def _setup_logging():
    """Configure application logging settings"""
    global _log_file_path
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 定义日志文件路径
    if _app_mode == AppMode.TUI:
        _log_file_path = log_dir / "rose_tui.log"
    else:  # CLI模式使用临时日志文件
        temp_dir = log_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        _log_file_path = temp_dir / f"rose_cli_{int(time.time())}.log"
    
    # 创建格式化程序
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 文件处理程序
    file_handler = logging.FileHandler(_log_file_path)
    file_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    
    # 清除现有处理程序
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # 添加文件处理程序
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)  # 默认级别设置为INFO
    
    # 如果是TUI模式，添加Textual处理程序
    if _app_mode == AppMode.TUI:
        try:
            textual_handler = TextualHandler()
            textual_handler.setFormatter(formatter)
            root_logger.addHandler(textual_handler)
        except ImportError:
            pass
    
    # 将ROS相关日志重定向到文件而不是终端
    for logger_name in ["rospy", "rosout", "gnupg", "rosbag", "rosbags", "roslib", "topicmanager", "rosmaster"]:
        ros_logger = logging.getLogger(logger_name)
        
        # 清除现有处理程序
        for handler in ros_logger.handlers[:]:
            ros_logger.removeHandler(handler)
            
        # 添加文件处理程序
        ros_logger.addHandler(file_handler)
        
        # 设置级别并禁止传播
        ros_logger.setLevel(logging.INFO) 
        ros_logger.propagate = False  
    
    return root_logger

_logger = _setup_logging()

def log_cli_error(e: Exception) -> str:
    global _log_file_path
    
    if _logger:
        _logger.error(f"Error: {str(e)}", exc_info=True)
    
    if _log_file_path:
        return f"Error: {str(e)}\nDetailed information has been recorded to: {_log_file_path}"
    else:
        return f"Error: {str(e)}"


class TimeUtil:
    """Utility class for handling time conversions"""
    
    @staticmethod
    def to_datetime(time_tuple: Tuple[int, int]) -> str:
        """
        Convert (seconds, nanoseconds) tuple to [YY/MM/DD HH:MM:SS] formatted string
        
        Args:
            time_tuple: Tuple of (seconds, nanoseconds)
            
        Returns:
            Formatted time string
        """
        if not time_tuple or len(time_tuple) != 2:
            return "N.A"
        
        seconds, nanoseconds = time_tuple
        total_seconds = seconds + nanoseconds / 1e9
        return time.strftime("%y/%m/%d %H:%M:%S", time.localtime(total_seconds))

    @staticmethod
    def from_datetime(time_str: str) -> Tuple[int, int]:
        """
        Convert [YY/MM/DD HH:MM:SS] formatted string to (seconds, nanoseconds) tuple
        
        Args:
            time_str: Time string in YY/MM/DD HH:MM:SS format
            
        Returns:
            Tuple of (seconds, nanoseconds)
        """
        try:
            # Parse time string to time struct
            time_struct = time.strptime(time_str, "%y/%m/%d %H:%M:%S")
            # Convert to Unix timestamp
            total_seconds = time.mktime(time_struct)
            # Return (seconds, nanoseconds) tuple
            return (int(total_seconds), 0)
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}. Expected format: YY/MM/DD HH:MM:SS")

    @staticmethod
    def convert_time_range_to_tuple(start_time_str: str, end_time_str: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Create time range from start and end time strings
        
        Args:
            start_time_str: Start time in YY/MM/DD HH:MM:SS format
            end_time_str: End time in YY/MM/DD HH:MM:SS format
            
        Returns:
            Tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
        """
        try:
            start_time = TimeUtil.from_datetime(start_time_str)
            end_time = TimeUtil.from_datetime(end_time_str)
            # make sure start and end are within range of output bag file
            start_time = (start_time[0] - 1, start_time[1])
            end_time = (end_time[0] + 1, end_time[1]) 
            return (start_time, end_time)
        except ValueError as e:
            raise ValueError(f"Invalid time range format: {e}")