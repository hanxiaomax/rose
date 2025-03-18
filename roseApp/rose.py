#!/usr/bin/env python3

from typing import List, Optional, Tuple
import sys

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# 先导入日志模块
import logging

# 从工具模块导入必要的函数
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error
from roseApp.cli.filter import app as filter_app
from roseApp.cli.cli_tool import app as cli_tool_app
from roseApp.tui.tui import app as tui_app

# 初始化日志记录器
logger = get_logger("RoseCLI")
console = Console()
app = typer.Typer(help="ROS bag filter utility - A powerful tool for ROS bag manipulation")

def configure_logging(verbosity: int):
    """根据详细程度配置日志级别
    
    Args:
        verbosity: 'v'标志的数量 (例如 -vvv = 3)
    """
    levels = {
        0: logging.WARNING,  # 默认
        1: logging.INFO,     # -v
        2: logging.DEBUG,    # -vv
        3: logging.DEBUG,    # -vvv (格式化程序中有更多详细信息)
    }
    level = levels.get(min(verbosity, 3), logging.DEBUG)
    logger.setLevel(level)
    
    if verbosity >= 3:
        # 为高详细度添加更详细的格式
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            ))

def parse_time_range(time_range: str) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """解析格式为'start_time,end_time'的时间范围字符串
    
    Args:
        time_range: 格式为'YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS'的字符串
    
    Returns:
        元组 ((start_seconds, start_nanos), (end_seconds, end_nanos))
    """
    if not time_range:
        return None
        
    try:
        start_str, end_str = time_range.split(',')
        return TimeUtil.convert_time_range_to_tuple(start_str.strip(), end_str.strip())
    except Exception as e:
        logger.error(f"解析时间范围时出错: {str(e)}")
        raise typer.BadParameter(
            "时间范围必须采用 'YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS' 格式"
        )

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="增加详细程度 (例如 -v, -vv, -vvv)")
):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    # 根据命令设置应用程序模式
    if ctx.invoked_subcommand == "tui":
        set_app_mode(AppMode.TUI)
    else:
        set_app_mode(AppMode.CLI)
        
    configure_logging(verbose)
    
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# 添加子命令
app.add_typer(filter_app)
app.add_typer(cli_tool_app)
app.add_typer(tui_app)

if __name__ == '__main__':
    try:
        app()
    except Exception as e:
        # 只在CLI模式下处理顶级异常
        if 'tui' not in sys.argv:
            error_msg = log_cli_error(e)
            typer.echo(error_msg, err=True)
            sys.exit(1)
        else:
            # TUI模式下重新抛出异常
            raise
