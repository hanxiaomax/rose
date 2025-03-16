#!/usr/bin/env python3

from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from roseApp.core.util import get_logger, TimeUtil
from roseApp.cli.filter import app as filter_app
from roseApp.cli.cli_tool import app as cli_tool_app
from roseApp.tui.tui import app as tui_app
import logging

# Initialize logger
logger = get_logger("RoseCLI")
console = Console()
app = typer.Typer(help="ROS bag filter utility - A powerful tool for ROS bag manipulation")

def configure_logging(verbosity: int):
    """Configure logging level based on verbosity count
    
    Args:
        verbosity: Number of 'v' flags (e.g. -vvv = 3)
    """
    levels = {
        0: logging.WARNING,  # Default
        1: logging.INFO,     # -v
        2: logging.DEBUG,    # -vv
        3: logging.DEBUG,    # -vvv (with extra detail in formatter)
    }
    level = levels.get(min(verbosity, 3), logging.DEBUG)
    logger.setLevel(level)
    
    if verbosity >= 3:
        # Add more detailed formatting for high verbosity
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            ))

def parse_time_range(time_range: str) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Parse time range string in format 'start_time,end_time'
    
    Args:
        time_range: String in format 'YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS'
    
    Returns:
        Tuple of ((start_seconds, start_nanos), (end_seconds, end_nanos))
    """
    if not time_range:
        return None
        
    try:
        start_str, end_str = time_range.split(',')
        return TimeUtil.convert_time_range_to_tuple(start_str.strip(), end_str.strip())
    except Exception as e:
        logger.error(f"Error parsing time range: {str(e)}")
        raise typer.BadParameter(
            "Time range must be in format 'YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS'"
        )

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity (e.g. -v, -vv, -vvv)")
):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    configure_logging(verbose)
    
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())



app.add_typer(filter_app)
app.add_typer(cli_tool_app)
app.add_typer(tui_app)

if __name__ == '__main__':
    app()
