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

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
@click.option('--json', 'json_output', is_flag=True,
              help='Output in JSON format')
@click.option('--pattern', '-p', type=str, default=None,
              help='Filter topics by regex pattern')
@click.option('--save', '-s', type=click.Path(),
              help='Save filtered topics to whitelist file')
def inspect(input_bag, json_output, pattern, save):
    """Analyze topics and help create whitelist.
    
    This command helps analyze topics and create whitelist files by:
    - Showing message count for each topic
    - Filtering topics by pattern (regex)
    - Generating whitelist files from filtered topics
    
    Examples:
    \b
        # Show all topics with statistics
        rose inspect input.bag
        
        # Filter topics matching pattern and save to whitelist
        rose inspect input.bag -p ".*gps.*" -s whitelist.txt
        
        # Filter sensor topics
        rose inspect input.bag -p "sensor.*"
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        topics, connections, time_range = parser.load_bag(input_bag)
        
        # Get message counts
        try:
            msg_counts = parser.get_message_counts(input_bag)
        except:
            msg_counts = {topic: 0 for topic in topics}
        
        # Filter topics based on pattern
        filtered_topics = set(topics)
        if pattern:
            import re
            regex = re.compile(pattern)
            filtered_topics = {topic for topic in topics if regex.search(topic)}
        
        # Format output
        if json_output:
            import json
            result = {
                'topics': {
                    topic: {
                        'type': connections[topic],
                        'messages': msg_counts[topic]
                    } for topic in filtered_topics
                }
            }
            click.echo(json.dumps(result, indent=2))
        else:
            click.secho(f"\nTopic Analysis: {click.style(input_bag, fg='green')}", bold=True)
            click.echo("─" * 80)
            
            # Header
            click.echo(f"{'Topic':<50} {'Type':<30} {'Messages':<12}")
            click.echo("─" * 80)
            
            # Topic details
            for topic in sorted(filtered_topics):
                msg_count = msg_counts[topic]
                
                topic_str = f"{topic:<50}"
                type_str = f"{connections[topic]:<30}"
                count_str = f"{msg_count:,}"
                
                click.echo(f"{click.style(topic_str, fg='white')} "
                          f"{click.style(type_str, fg='cyan')} "
                          f"{click.style(f'{count_str:>12}', fg='yellow')}")
            
            # Summary
            click.echo("─" * 80)
            click.echo(f"Showing {click.style(str(len(filtered_topics)), fg='green')} of "
                      f"{click.style(str(len(topics)), fg='white')} topics")
            
            if pattern:
                click.echo(f"\nApplied filter: {click.style(pattern, fg='yellow')}")
        
        # Save to whitelist if requested
        if save and filtered_topics:
            os.makedirs(os.path.dirname(save) if os.path.dirname(save) else '.', exist_ok=True)
            with open(save, 'w') as f:
                f.write("# Generated by rose inspect\n")
                f.write(f"# Source: {input_bag}\n")
                if pattern:
                    f.write(f"# Pattern: {pattern}\n")
                f.write("\n")
                for topic in sorted(filtered_topics):
                    f.write(f"{topic}\n")
            click.secho(f"\nSaved {len(filtered_topics)} topics to {click.style(save, fg='blue')}", fg='green')
            
    except Exception as e:
        logger.error(f"Error during inspection: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command()
@click.argument('input_bag', type=click.Path(exists=True))
def info(input_bag):
    """Show basic information about the bag file.
    
    This command provides a quick overview of the bag file, including:
    - File information (size, path)
    - Time range and duration
    - Topic count and message types
    - Message counts per topic
    
    Examples:
    \b
        rose info input.bag
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        topics, connections, time_range = parser.load_bag(input_bag)
        
        # Get file information
        file_size = os.path.getsize(input_bag)
        file_size_mb = file_size / (1024 * 1024)
        
        # Format output
        click.secho(f"\nBag Summary: {click.style(input_bag, fg='green')}", bold=True)
        click.echo("─" * 80)
        
        # File information
        click.echo(f"File Size: {click.style(f'{file_size_mb:.2f} MB', fg='yellow')} "
                  f"({click.style(f'{file_size:,}', fg='yellow')} bytes)")
        click.echo(f"Location: {click.style(os.path.abspath(input_bag), fg='blue')}")
        
        # Time information
        start_time = TimeUtil.to_datetime(time_range[0])
        end_time = TimeUtil.to_datetime(time_range[1])
        duration_secs = time_range[1][0] - time_range[0][0] + (time_range[1][1] - time_range[0][1])/1e9
        mins, secs = divmod(duration_secs, 60)
        hours, mins = divmod(mins, 60)
        
        click.echo(f"\nTime Range:")
        click.echo(f"  Start:    {click.style(start_time, fg='yellow')}")
        click.echo(f"  End:      {click.style(end_time, fg='yellow')}")
        click.echo(f"  Duration: {click.style(f'{int(hours)}h {int(mins)}m {secs:.2f}s', fg='yellow')}")
        
        # Topic information
        click.echo(f"\nTopics: {click.style(str(len(topics)), fg='yellow')} total")
        click.echo("─" * 80)
        
        # Get message counts if available
        try:
            msg_counts = parser.get_message_counts(input_bag)
            for topic in sorted(topics):
                count = msg_counts.get(topic, 'N/A')
                count_str = f"{count:,}" if isinstance(count, int) else count
                msg_type = f"{connections[topic]:<30}"
                click.echo(f"  {click.style('•', fg='blue')} {topic:<40} "
                          f"{click.style(msg_type, fg='cyan')} "
                          f"({click.style(count_str, fg='yellow')} msgs)")
        except:
            # Fallback if message counts not available
            for topic in sorted(topics):
                msg_type = f"{connections[topic]:<30}"
                click.echo(f"  {click.style('•', fg='blue')} {topic:<40} "
                          f"{click.style(msg_type, fg='cyan')}")
            
    except Exception as e:
        logger.error(f"Error getting bag info: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

if __name__ == '__main__':
    cli()
