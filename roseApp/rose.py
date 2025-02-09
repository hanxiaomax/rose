#!/usr/bin/env python3

import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import click
from core.parser import create_parser, ParserType
from core.util import get_logger, TimeUtil
from tui import RoseTUI     
import logging

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
            click.echo("\nTopics to include:")
            for topic in sorted(whitelist_topics):
                click.echo(f"  {click.style('✓', fg='green')} {topic}")
            
            if time_range_tuple:
                start_time, end_time = time_range_tuple
                click.echo(f"\nTime range: {click.style(TimeUtil.to_datetime(start_time), fg='yellow')} to "
                          f"{click.style(TimeUtil.to_datetime(end_time), fg='yellow')}")
            return
        
        # Print filter information
        click.secho("\nStarting bag filter:", bold=True)
        click.echo(f"Input:  {click.style(input_bag, fg='green')}")
        click.echo(f"Output: {click.style(output_bag, fg='blue')}")
        
        click.echo("\nSelected topics:")
        for topic in sorted(whitelist_topics):
            click.echo(f"  {click.style('✓', fg='green')} {topic}")
        
        if time_range_tuple:
            start_time, end_time = time_range_tuple
            click.echo(f"\nTime range: {click.style(TimeUtil.to_datetime(start_time), fg='yellow')} to "
                      f"{click.style(TimeUtil.to_datetime(end_time), fg='yellow')}")
        
        # Run the filter with progress bar
        click.echo("\nProcessing:")
        with click.progressbar(length=100, label='Filtering bag file', 
                             show_eta=True, show_percent=True) as bar:
            result = parser.filter_bag(
                input_bag, 
                output_bag, 
                list(whitelist_topics),
                time_range_tuple
            )
            bar.update(100)
            
        click.secho("\n" + result, fg='green', bold=True)
        
    except Exception as e:
        logger.error(f"Error during filtering: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
@click.option('--json', 'json_output', is_flag=True,
              help='Output in JSON format')
def inspect(input_bag, json_output):
    """Analyze bag structure and show detailed topic statistics.
    
    This command provides a comprehensive analysis of the bag file, including:
    - Message counts per topic
    - Data rates and sizes
    - Frequency statistics
    - Connection information
    
    Examples:
    \b
        rose inspect input.bag
        rose inspect input.bag --json
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        result = parser.inspect_bag(input_bag)
        
        if json_output:
            click.echo(result)
        else:
            click.secho(f"\nAnalyzing {click.style(input_bag, fg='green')}:", bold=True)
            click.echo(result)
            
    except Exception as e:
        logger.error(f"Error during inspection: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
def info(input_bag):
    """Show basic information about the bag file.
    
    This command provides a quick overview of the bag file, including:
    - Number of topics
    - Time range
    - Basic topic list
    
    Examples:
    \b
        rose info input.bag
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        topics, connections, time_range = parser.load_bag(input_bag)
        
        # Format output
        click.secho(f"\nBag Summary: {click.style(input_bag, fg='green')}", bold=True)
        click.echo("─" * 80)
        
        click.echo(f"Topics: {click.style(str(len(topics)), fg='yellow')} total")
        click.echo(f"Duration: {click.style(TimeUtil.to_datetime(time_range[0]), fg='yellow')} to "
                  f"{click.style(TimeUtil.to_datetime(time_range[1]), fg='yellow')}")
        
        click.secho("\nTopic List:", bold=True)
        click.echo("─" * 80)
        for topic in sorted(topics):
            click.echo(f"  {click.style('•', fg='blue')} {topic:<40} "
                      f"{click.style(connections[topic], fg='cyan')}")
            
    except Exception as e:
        logger.error(f"Error getting bag info: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

if __name__ == '__main__':
    cli()
