#!/usr/bin/env python3

import os
import time
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil
from roseApp.tui import RoseTUI     
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
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="增加详细程度 (例如 -v, -vv, -vvv)")
):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    configure_logging(verbose)
    
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def tui():
    """启动TUI（终端用户界面）进行交互式操作"""
    app = RoseTUI()
    app.run()

@app.command()
def filter(
    input_bag: str = typer.Argument(..., help="输入bag文件路径"),
    output_bag: str = typer.Argument(..., help="输出bag文件路径"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="话题白名单文件路径"),
    time_range: Optional[str] = typer.Option(None, "--time-range", "-t", help="时间范围，格式为 \"YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS\""),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="要包含的话题（可多次指定）。作为白名单文件的替代方式。"),
    dry_run: bool = typer.Option(False, "--dry-run", help="显示将要执行的操作，但不实际执行")
):
    """根据话题白名单和/或时间范围过滤ROS bag文件。
    
    示例:
    
        rose filter input.bag output.bag -w whitelist.txt
        rose filter input.bag output.bag -t "23/01/01 00:00:00,23/01/01 00:10:00"
        rose filter input.bag output.bag --topics /topic1 --topics /topic2
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        
        # 检查输入文件是否存在
        if not os.path.exists(input_bag):
            typer.echo(f"错误: 输入文件 '{input_bag}' 不存在", err=True)
            raise typer.Exit(code=1)
            
        # 检查白名单文件是否存在
        if whitelist and not os.path.exists(whitelist):
            typer.echo(f"错误: 白名单文件 '{whitelist}' 不存在", err=True)
            raise typer.Exit(code=1)
        
        # 从输入bag获取所有话题
        all_topics, connections, _ = parser.load_bag(input_bag)
        
        # 解析时间范围（如果提供）
        time_range_tuple = parse_time_range(time_range) if time_range else None
        
        # 从白名单文件或命令行参数获取话题
        whitelist_topics = set()
        if whitelist:
            whitelist_topics.update(parser.load_whitelist(whitelist))
        if topics:
            whitelist_topics.update(topics)
            
        if not whitelist_topics:
            typer.echo("错误: 未指定话题。请使用 --whitelist 或 --topics", err=True)
            raise typer.Exit(code=1)
            
        # 在dry run模式下显示将要执行的操作
        if dry_run:
            typer.secho("DRY RUN - 不会进行任何更改", fg=typer.colors.YELLOW, bold=True)
            typer.echo(f"将过滤 {typer.style(input_bag, fg=typer.colors.GREEN)} 到 {typer.style(output_bag, fg=typer.colors.BLUE)}")
            
            # 显示所有话题及其选择状态
            typer.echo("\n话题选择:")
            typer.echo("─" * 80)
            for topic in sorted(all_topics):
                is_selected = topic in whitelist_topics
                status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
                topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
                msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
                topic_str = f"{topic:<40}"
                typer.echo(f"  {status_icon} {typer.style(topic_str, fg=topic_style)} "
                          f"{typer.style(connections[topic], fg=msg_type_style)}")
            
            if time_range_tuple:
                start_time, end_time = time_range_tuple
                typer.echo(f"\n时间范围: {typer.style(TimeUtil.to_datetime(start_time), fg=typer.colors.YELLOW)} 到 "
                          f"{typer.style(TimeUtil.to_datetime(end_time), fg=typer.colors.YELLOW)}")
            return
        
        # 打印过滤信息
        typer.secho("\n开始bag过滤:", bold=True)
        typer.echo(f"输入:  {typer.style(input_bag, fg=typer.colors.GREEN)}")
        typer.echo(f"输出: {typer.style(output_bag, fg=typer.colors.BLUE)}")
        
        # 显示所有话题及其选择状态
        typer.echo("\n话题选择:")
        typer.echo("─" * 80)
        selected_count = 0
        for topic in sorted(all_topics):
            is_selected = topic in whitelist_topics
            if is_selected:
                selected_count += 1
            status_icon = typer.style('✓', fg=typer.colors.GREEN) if is_selected else typer.style('○', fg=typer.colors.YELLOW)
            topic_style = typer.colors.GREEN if is_selected else typer.colors.WHITE
            msg_type_style = typer.colors.CYAN if is_selected else typer.colors.WHITE
            topic_str = f"{topic:<40}"
            typer.echo(f"  {status_icon} {typer.style(topic_str, fg=topic_style)} "
                      f"{typer.style(connections[topic], fg=msg_type_style)}")
        
        # 显示选择摘要
        typer.echo("─" * 80)
        typer.echo(f"已选择: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
                  f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} 个话题")
        
        if time_range_tuple:
            start_time, end_time = time_range_tuple
            typer.echo(f"\n时间范围: {typer.style(TimeUtil.to_datetime(start_time), fg=typer.colors.YELLOW)} 到 "
                      f"{typer.style(TimeUtil.to_datetime(end_time), fg=typer.colors.YELLOW)}")
        
        # 使用进度条运行过滤
        typer.echo("\n处理中:")
        start_time = time.time()
        
        # 使用Rich的进度条替代Click的进度条
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=False,
        ) as progress:
            task = progress.add_task("过滤bag文件...", total=100)
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                time_range_tuple
            )
            progress.update(task, completed=100)
        
        # 显示过滤结果
        end_time = time.time()
        elapsed = end_time - start_time
        input_size = os.path.getsize(input_bag)
        output_size = os.path.getsize(output_bag)
        size_reduction = (1 - output_size/input_size) * 100
        
        typer.secho("\n过滤结果:", fg=typer.colors.GREEN, bold=True)
        typer.echo("─" * 80)
        typer.echo(f"耗时: {int(elapsed//60)}分 {elapsed%60:.2f}秒")
        typer.echo(f"输入大小:  {typer.style(f'{input_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"输出大小: {typer.style(f'{output_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"减少比例:   {typer.style(f'{size_reduction:.1f}%', fg=typer.colors.GREEN)}")
        typer.echo(result)
        
    except Exception as e:
        logger.error(f"过滤过程中出错: {str(e)}", exc_info=True)
        typer.echo(f"错误: {str(e)}", err=True)
        raise typer.Exit(code=1)

@app.command('cli')
def cli_tool():
    """启动交互式命令行界面"""
    from .cli_tool import main
    main()

def main():
    """Entry point for the CLI tool"""
    app()

if __name__ == '__main__':
    app()
