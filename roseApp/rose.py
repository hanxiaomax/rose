#!/usr/bin/env python3

import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import click
from roseApp.core.parser import create_parser, ParserType
from roseApp.core.util import get_logger, TimeUtil
from roseApp.tui import RoseTUI     
import logging
import time

# Initialize logger
logger = get_logger("RoseCLI")

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
        raise click.BadParameter(
            "Time range must be in format 'YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS'"
        )

@click.group(invoke_without_command=True)
@click.option('-v', '--verbose', count=True, help='Increase verbosity (e.g. -v, -vv, -vvv)')
@click.pass_context
def cli(ctx, verbose):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose
    
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command()
def tui():
    """Launch the TUI (Terminal User Interface) for interactive operation"""
    app = RoseTUI()
    app.run()

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
@click.argument('output_bag', type=click.Path())
@click.option('--whitelist', '-w', type=click.Path(exists=True),
              help='Path to topic whitelist file')
@click.option('--time-range', '-t', 
              help='Time range in format "YY/MM/DD HH:MM:SS,YY/MM/DD HH:MM:SS"')
@click.option('--topics', '-tp', multiple=True,
              help='Topics to include (can be specified multiple times). Alternative to whitelist file.')
@click.option('--dry-run', is_flag=True,
              help='Show what would be done without actually doing it')
def filter(input_bag, output_bag, whitelist, time_range, topics, dry_run):
    """Filter ROS bag by topic whitelist and/or time range.
    
    Examples:
    \b
        rose filter input.bag output.bag -w whitelist.txt
        rose filter input.bag output.bag -t "23/01/01 00:00:00,23/01/01 00:10:00"
        rose filter input.bag output.bag --topics /topic1 --topics /topic2
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        
        # Get all topics from input bag
        all_topics, connections, _ = parser.load_bag(input_bag)
        
        # Parse time range if provided
        time_range_tuple = parse_time_range(time_range) if time_range else None
        
        # Get topics from whitelist file or command line arguments
        whitelist_topics = set()
        if whitelist:
            whitelist_topics.update(parser.load_whitelist(whitelist))
        if topics:
            whitelist_topics.update(topics)
            
        if not whitelist_topics:
            raise click.ClickException("No topics specified. Use --whitelist or --topics")
            
        # Show what will be done in dry run mode
        if dry_run:
            click.secho("DRY RUN - No changes will be made", fg='yellow', bold=True)
            click.echo(f"Would filter {click.style(input_bag, fg='green')} to {click.style(output_bag, fg='blue')}")
            
            # Show all topics with selection status
            click.echo("\nTopic Selection:")
            click.echo("─" * 80)
            for topic in sorted(all_topics):
                is_selected = topic in whitelist_topics
                status_icon = click.style('✓', fg='green') if is_selected else click.style('○', fg='yellow')
                topic_style = 'green' if is_selected else 'white'
                msg_type_style = 'cyan' if is_selected else 'white'
                topic_str = f"{topic:<40}"
                click.echo(f"  {status_icon} {click.style(topic_str, fg=topic_style)} "
                          f"{click.style(connections[topic], fg=msg_type_style)}")
            
            if time_range_tuple:
                start_time, end_time = time_range_tuple
                click.echo(f"\nTime range: {click.style(TimeUtil.to_datetime(start_time), fg='yellow')} to "
                          f"{click.style(TimeUtil.to_datetime(end_time), fg='yellow')}")
            return
        
        # Print filter information
        click.secho("\nStarting bag filter:", bold=True)
        click.echo(f"Input:  {click.style(input_bag, fg='green')}")
        click.echo(f"Output: {click.style(output_bag, fg='blue')}")
        
        # Show all topics with selection status
        click.echo("\nTopic Selection:")
        click.echo("─" * 80)
        selected_count = 0
        for topic in sorted(all_topics):
            is_selected = topic in whitelist_topics
            if is_selected:
                selected_count += 1
            status_icon = click.style('✓', fg='green') if is_selected else click.style('○', fg='yellow')
            topic_style = 'green' if is_selected else 'white'
            msg_type_style = 'cyan' if is_selected else 'white'
            topic_str = f"{topic:<40}"
            click.echo(f"  {status_icon} {click.style(topic_str, fg=topic_style)} "
                      f"{click.style(connections[topic], fg=msg_type_style)}")
        
        # Show selection summary
        click.echo("─" * 80)
        click.echo(f"Selected: {click.style(str(selected_count), fg='green')} of "
                  f"{click.style(str(len(all_topics)), fg='white')} topics")
        
        if time_range_tuple:
            start_time, end_time = time_range_tuple
            click.echo(f"\nTime range: {click.style(TimeUtil.to_datetime(start_time), fg='yellow')} to "
                      f"{click.style(TimeUtil.to_datetime(end_time), fg='yellow')}")
        
        # Run the filter with progress bar
        click.echo("\nProcessing:")
        start_time = time.time()
        with click.progressbar(length=100, label='Filtering bag file', 
                             show_eta=True, show_percent=True) as bar:
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                time_range_tuple
            )
            bar.update(100)
        
        # Show filtering results
        end_time = time.time()
        elapsed = end_time - start_time
        input_size = os.path.getsize(input_bag)
        output_size = os.path.getsize(output_bag)
        size_reduction = (1 - output_size/input_size) * 100
        
        click.secho("\nFilter Results:", fg='green', bold=True)
        click.echo("─" * 80)
        click.echo(f"Time taken: {int(elapsed//60)}m {elapsed%60:.2f}s")
        click.echo(f"Input size:  {click.style(f'{input_size/1024/1024:.2f} MB', fg='yellow')}")
        click.echo(f"Output size: {click.style(f'{output_size/1024/1024:.2f} MB', fg='yellow')}")
        click.echo(f"Reduction:   {click.style(f'{size_reduction:.1f}%', fg='green')}")
        click.echo(result)
        
    except Exception as e:
        logger.error(f"Error during filtering: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command('cli')
def cli_tool():
    """Launch interactive command-line interface"""
    from .cli_tool import main
    main()

if __name__ == '__main__':
    cli()
