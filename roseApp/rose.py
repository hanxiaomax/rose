#!/usr/bin/env python3

import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import click
from core.parser import create_parser, ParserType
from core.util import get_logger, TimeUtil
from tui import RoseTUI     

# Initialize logger
logger = get_logger("RoseCLI")

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
@click.pass_context
def cli(ctx):
    """ROS bag filter utility"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command()
def tui():
    """Launch the TUI interface"""
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
@click.option('--use-cpp', is_flag=True,
              help='Use C++ implementation for better performance')
def filter(input_bag, output_bag, whitelist, time_range, topics, dry_run, use_cpp):
    """Filter ROS bag by topic whitelist and/or time range.
    
    Examples:
        rose filter input.bag output.bag -w whitelist.txt
        rose filter input.bag output.bag -t "23/01/01 00:00:00,23/01/01 00:10:00"
        rose filter input.bag output.bag --topics /topic1 --topics /topic2
        rose filter input.bag output.bag -w whitelist.txt --use-cpp
    """
    try:
        # Create parser instance
        parser_type = ParserType.CPP if use_cpp else ParserType.PYTHON
        parser = create_parser(parser_type)
        
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
            click.echo(f"Would filter {input_bag} to {output_bag}")
            click.echo(f"Topics to include: {sorted(whitelist_topics)}")
            if time_range_tuple:
                start_time, end_time = time_range_tuple
                click.echo(f"Time range: {TimeUtil.to_datetime(start_time)} to {TimeUtil.to_datetime(end_time)}")
            return
            
        click.echo(f"Filtering {input_bag} to {output_bag}")
        click.echo(f"Including topics: {sorted(whitelist_topics)}")
        if time_range_tuple:
            start_time, end_time = time_range_tuple
            click.echo(f"Time range: {TimeUtil.to_datetime(start_time)} to {TimeUtil.to_datetime(end_time)}")
            
        result = parser.filter_bag(
            input_bag, 
            output_bag, 
            list(whitelist_topics),
            time_range_tuple
        )
        click.echo(result)
        
    except Exception as e:
        logger.error(f"Error during filtering: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
@click.option('--json', 'json_output', is_flag=True,
              help='Output in JSON format')
@click.option('--use-cpp', is_flag=True,
              help='Use C++ implementation for better performance')
def inspect(input_bag, json_output, use_cpp):
    """List all topics and message types in the bag file.
    
    Examples:
        rose inspect input.bag
        rose inspect input.bag --json
        rose inspect input.bag --use-cpp
    """
    try:
        parser_type = ParserType.CPP if use_cpp else ParserType.PYTHON
        parser = create_parser(parser_type)
        result = parser.inspect_bag(input_bag)
        click.echo(result)
    except Exception as e:
        logger.error(f"Error during inspection: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
@click.option('--use-cpp', is_flag=True,
              help='Use C++ implementation for better performance')
def info(input_bag, use_cpp):
    """Show detailed information about the bag file.
    
    Examples:
        rose info input.bag
        rose info input.bag --use-cpp
    """
    try:
        parser_type = ParserType.CPP if use_cpp else ParserType.PYTHON
        parser = create_parser(parser_type)
        topics, connections, time_range = parser.load_bag(input_bag)
        
        # Format output
        result = [f"\nBag information for {input_bag}:"]
        result.append(f"Number of topics: {len(topics)}")
        result.append(f"Time range: {TimeUtil.to_datetime(time_range[0])} - {TimeUtil.to_datetime(time_range[1])}")
        result.append("\nTopics:")
        for topic in sorted(topics):
            result.append(f"  - {topic} ({connections[topic]})")
            
        click.echo("\n".join(result))
    except Exception as e:
        logger.error(f"Error getting bag info: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

if __name__ == '__main__':
    cli()
