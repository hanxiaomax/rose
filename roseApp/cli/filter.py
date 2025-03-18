import os
import time
import typer
from typing import List, Optional, Tuple
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error
from rich.progress import Progress, SpinnerColumn, TextColumn

import logging

# 设置为CLI模式
set_app_mode(AppMode.CLI)

# 初始化日志记录器
logger = get_logger("RoseCLI-filter")

app = typer.Typer()

@app.command()
def filter(
    input_bag: str = typer.Argument(..., help="输入bag文件路径"),
    output_bag: str = typer.Argument(..., help="输出bag文件路径"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="话题白名单文件路径"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="要包含的话题（可以多次指定）。作为白名单文件的替代方案。"),
    dry_run: bool = typer.Option(False, "--dry-run", help="显示将要执行的操作而不实际执行")
):
    """过滤ROS bag文件，可按话题白名单和/或时间范围过滤。
    
    示例：
    
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
        

        # 从白名单文件或命令行参数获取话题
        whitelist_topics = set()
        if whitelist:
            whitelist_topics.update(parser.load_whitelist(whitelist))
        if topics:
            whitelist_topics.update(topics)
            
        if not whitelist_topics:
            typer.echo("错误: 未指定话题。使用 --whitelist 或 --topics 指定", err=True)
            raise typer.Exit(code=1)
            
        # 在dry run模式下显示将要执行的操作
        if dry_run:
            typer.secho("试运行 - 不会进行实际修改", fg=typer.colors.YELLOW, bold=True)
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
            
            return
        
        # 打印过滤信息
        typer.secho("\n开始过滤bag文件:", bold=True)
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
        

        # 使用进度条运行过滤
        typer.echo("\n处理中:")
        start_time = time.time()
        
        # 使用Rich的进度条
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=False,
        ) as progress:
            task = progress.add_task("正在过滤bag文件...", total=100)
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics)
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
        typer.echo(f"缩减比例:   {typer.style(f'{size_reduction:.1f}%', fg=typer.colors.GREEN)}")
        typer.echo(result)
        
    except Exception as e:
        error_msg = log_cli_error(e)
        typer.echo(error_msg, err=True)
        raise typer.Exit(code=1)

def main():
    """CLI工具入口点"""
    app()

if __name__ == "__main__":
    main() 