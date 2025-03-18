import os
import time
import typer
from typing import List, Optional, Tuple
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn

import logging

# Set to CLI mode
set_app_mode(AppMode.CLI)

# Initialize logger
logger = get_logger(__name__)

app = typer.Typer()

@app.command("filter")
def filter_bag(
    input_bag: str = typer.Argument(..., help="Input bag file path"),
    output_bag: str = typer.Argument(..., help="Output bag file path"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="Topic whitelist file path"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="Topics to include (can be specified multiple times). Alternative to whitelist file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter topics from a ROS bag file"""
    try:
        parser = create_parser(ParserType.PYTHON)
        
        # Check if input file exists
        if not os.path.exists(input_bag):
            typer.echo(f"Error: Input file '{input_bag}' does not exist", err=True)
            raise typer.Exit(code=1)
            
        # Check if whitelist file exists
        if whitelist and not os.path.exists(whitelist):
            typer.echo(f"Error: Whitelist file '{whitelist}' does not exist", err=True)
            raise typer.Exit(code=1)
        
        # Get all topics from input bag
        all_topics, connections, _ = parser.load_bag(input_bag)
        

        # Get topics from whitelist file or command line arguments
        whitelist_topics = set()
        if whitelist:
            whitelist_topics.update(parser.load_whitelist(whitelist))
        if topics:
            whitelist_topics.update(topics)
            
        if not whitelist_topics:
            typer.echo("Error: No topics specified. Use --whitelist or --topics to specify", err=True)
            raise typer.Exit(code=1)
            
        # Show what would be done in dry run mode
        if dry_run:
            typer.secho("Dry run - no actual modifications will be made", fg=typer.colors.YELLOW, bold=True)
            typer.echo(f"Filtering {typer.style(input_bag, fg=typer.colors.GREEN)} to {typer.style(output_bag, fg=typer.colors.BLUE)}")
            
            # Show all topics and their selection status
            typer.echo("\nTopic selection:")
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
        
        # Print filtering information
        typer.secho("\nStarting to filter bag file:", bold=True)
        typer.echo(f"Input:  {typer.style(input_bag, fg=typer.colors.GREEN)}")
        typer.echo(f"Output: {typer.style(output_bag, fg=typer.colors.BLUE)}")
        
        # Show all topics and their selection status
        typer.echo("\nTopic selection:")
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
        
        # Show selection summary
        typer.echo("─" * 80)
        typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} / "
                  f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics")
        

        # Use progress bar for filtering
        typer.echo("\nProcessing:")
        start_time = time.time()
        
        # 获取要显示的文件名，对较长的文件名进行处理
        input_basename = os.path.basename(input_bag)
        display_name = input_basename
        if len(input_basename) > 40:
            display_name = f"{input_basename[:15]}...{input_basename[-20:]}"
            
        # Use LoadingAnimation from util.py for consistent progress display
        from .util import LoadingAnimation
        
        with LoadingAnimation("Filtering bag file...") as progress:
            # Create progress task
            task_id = progress.add_task(f"Filtering: {display_name}", total=100)
            
            # Define progress update callback function
            def update_progress(percent: int):
                progress.update(task_id, description=f"Filtering: {display_name} ({percent}%)", completed=percent)
            
            # Execute filtering
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                progress_callback=update_progress
            )
            
            # Update final status
            progress.update(task_id, description=f"[green]✓ Complete: {display_name}[/green]", completed=100)
        
        # Add some extra space to ensure progress bar is fully visible        
        # Show filtering result
        end_time = time.time()
        elapsed = end_time - start_time
        input_size = os.path.getsize(input_bag)
        output_size = os.path.getsize(output_bag)
        size_reduction = (1 - output_size/input_size) * 100
        
        typer.secho("\nFiltering result:", fg=typer.colors.GREEN, bold=True)
        typer.echo("─" * 80)
        typer.echo(f"Time: {int(elapsed//60)} minutes {elapsed%60:.2f} seconds")
        typer.echo(f"Input size:  {typer.style(f'{input_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"Output size: {typer.style(f'{output_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"Size reduction:   {typer.style(f'{size_reduction:.1f}%', fg=typer.colors.GREEN)}")
        typer.echo(result)
        
    except Exception as e:
        error_msg = log_cli_error(e)
        typer.echo(error_msg, err=True)
        raise typer.Exit(code=1)

def main():
    """CLI tool entry point"""
    app()

if __name__ == "__main__":
    main() 