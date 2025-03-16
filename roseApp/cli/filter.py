import os
import time
import typer
from typing import List, Optional, Tuple
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil
# from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

import logging

# Initialize logger
logger = get_logger("RoseCLI - filter")
# console = Console()

app = typer.Typer()

@app.command()
def filter(
    input_bag: str = typer.Argument(..., help="Input bag file path"),
    output_bag: str = typer.Argument(..., help="Output bag file path"),
    whitelist: Optional[str] = typer.Option(None, "--whitelist", "-w", help="Path to topic whitelist file"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-tp", help="Topics to include (can be specified multiple times). Alternative to whitelist file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without actually doing it")
):
    """Filter ROS bag by topic whitelist and/or time range.
    
    Examples:
    
        rose filter input.bag output.bag -w whitelist.txt
        rose filter input.bag output.bag -t "23/01/01 00:00:00,23/01/01 00:10:00"
        rose filter input.bag output.bag --topics /topic1 --topics /topic2
    """
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
            typer.echo("Error: No topics specified. Use --whitelist or --topics", err=True)
            raise typer.Exit(code=1)
            
        # Show what will be done in dry run mode
        if dry_run:
            typer.secho("DRY RUN - No changes will be made", fg=typer.colors.YELLOW, bold=True)
            typer.echo(f"Would filter {typer.style(input_bag, fg=typer.colors.GREEN)} to {typer.style(output_bag, fg=typer.colors.BLUE)}")
            
            # Show all topics with selection status
            typer.echo("\nTopic Selection:")
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
        
        # Print filter information
        typer.secho("\nStarting bag filter:", bold=True)
        typer.echo(f"Input:  {typer.style(input_bag, fg=typer.colors.GREEN)}")
        typer.echo(f"Output: {typer.style(output_bag, fg=typer.colors.BLUE)}")
        
        # Show all topics with selection status
        typer.echo("\nTopic Selection:")
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
        typer.echo(f"Selected: {typer.style(str(selected_count), fg=typer.colors.GREEN)} of "
                  f"{typer.style(str(len(all_topics)), fg=typer.colors.WHITE)} topics")
        

        # Run the filter with progress bar
        typer.echo("\nProcessing:")
        start_time = time.time()
        
        # Use Rich's progress bar instead of Click's progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=False,
        ) as progress:
            task = progress.add_task("Filtering bag file...", total=100)
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics)
            )
            progress.update(task, completed=100)
        
        # Show filtering results
        end_time = time.time()
        elapsed = end_time - start_time
        input_size = os.path.getsize(input_bag)
        output_size = os.path.getsize(output_bag)
        size_reduction = (1 - output_size/input_size) * 100
        
        typer.secho("\nFilter Results:", fg=typer.colors.GREEN, bold=True)
        typer.echo("─" * 80)
        typer.echo(f"Time taken: {int(elapsed//60)}m {elapsed%60:.2f}s")
        typer.echo(f"Input size:  {typer.style(f'{input_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"Output size: {typer.style(f'{output_size/1024/1024:.2f} MB', fg=typer.colors.YELLOW)}")
        typer.echo(f"Reduction:   {typer.style(f'{size_reduction:.1f}%', fg=typer.colors.GREEN)}")
        typer.echo(result)
        
    except Exception as e:
        logger.error(f"Error during filtering: {str(e)}", exc_info=True)
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)

def main():
    """Entry point for the CLI tool"""
    app()

if __name__ == "__main__":
    main() 