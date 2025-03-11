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
@click.option('--detailed', '-d', is_flag=True,
              help='Show detailed topic analysis instead of basic bag information')
def inspect(input_bag, json_output, pattern, save, detailed):
    """Analyze bag file and show information about topics.
    
    This command provides information about the bag file in two modes:
    
    1. Basic mode (default): Shows an overview of the bag file, including:
       - File information (size, path)
       - Time range and duration
       - Topic count and message types
    
    2. Detailed mode (--detailed): Analyzes topics and helps create whitelist files by:
       - Showing message type for each topic
       - Filtering topics by pattern (regex)
       - Generating whitelist files from filtered topics
    
    Examples:
    \b
        # Show basic bag information (like the old 'info' command)
        rose inspect input.bag
        
        # Show detailed topic analysis
        rose inspect input.bag --detailed
        
        # Filter topics matching pattern and save to whitelist
        rose inspect input.bag --detailed -p ".*gps.*" -s whitelist.txt
        
        # Filter sensor topics
        rose inspect input.bag --detailed -p "sensor.*"
        
        # Output topic information in JSON format
        rose inspect input.bag --detailed --json
    """
    try:
        parser = create_parser(ParserType.PYTHON)
        topics, connections, time_range = parser.load_bag(input_bag)
        
        # If detailed mode is not specified and no other options are provided,
        # show basic bag information (like the old 'info' command)
        if not detailed and not pattern and not save and not json_output:
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
            
            # Display topics and their types
            for topic in sorted(topics):
                msg_type = f"{connections[topic]:<30}"
                click.echo(f"  {click.style('•', fg='blue')} {topic:<40} "
                          f"{click.style(msg_type, fg='cyan')}")
            
            return
        
        # Detailed mode (original inspect functionality)
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
                        'type': connections[topic]
                    } for topic in filtered_topics
                }
            }
            click.echo(json.dumps(result, indent=2))
        else:
            click.secho(f"\nTopic Analysis: {click.style(input_bag, fg='green')}", bold=True)
            click.echo("─" * 90)
            
            # Header
            click.echo(f"{'Topic':<50} {'Type':<35}")
            click.echo("─" * 90)
            
            # Topic details
            for topic in sorted(filtered_topics):
                topic_str = f"{topic:<50}"
                type_str = f"{connections[topic]:<35}"
                
                click.echo(f"{click.style(topic_str, fg='white')} "
                          f"{click.style(type_str, fg='cyan')}")
            
            # Summary
            click.echo("─" * 90)
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
@click.argument('input_bag', type=click.Path(exists=True), required=False)
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output whitelist file path')
def whitelist(input_bag, output):
    """Interactive topic selection for whitelist creation.
    
    
    Examples:
    \b
        # Interactive selection with bag file prompt
        rose whitelist
        
        # Interactive selection with specified bag file
        rose whitelist input.bag
        
        # Interactive selection and save to specific file
        rose whitelist input.bag -o my_whitelist.txt
    """
    try:
        import questionary
        from questionary import Choice, Style
        
        # Define questionary style
        custom_style = Style([
            ('question', '#ffffff bold'),
            ('answer', '#2aa198'),  # Cyan
            ('path', '#268bd2'),    # Blue
            ('highlighted', '#859900 bold'),  # Green
            ('selected', '#859900'),  # Green
            ('instruction', '#93a1a1'),  # Gray
            ('text', '#ffffff'),
            ('completion-menu', 'bg:#333333 #ffffff'),
            ('completion-menu-selection', 'bg:#859900 #000000')
        ])
        
        # If input_bag is not provided, ask for it
        if not input_bag:
            while True:
                input_bag = questionary.path(
                    "Enter bag file path:",
                    only_directories=False,
                    style=custom_style
                ).ask()
                
                if input_bag is None:  # User cancelled
                    click.echo("\nOperation cancelled")
                    return
                
                # Validate the input
                if not os.path.exists(input_bag):
                    click.echo("Error: File does not exist")
                    continue
                    
                if not input_bag.endswith('.bag'):
                    click.echo("Error: File must be a .bag file")
                    continue
                    
                break
        
        parser = create_parser(ParserType.PYTHON)
        topics, connections, _ = parser.load_bag(input_bag)
        
        # Format topics with their message types for display
        topic_choices = []
        for topic in sorted(topics):
            msg_type = connections[topic]
            # Create choice with topic as value and formatted string as name
            topic_choices.append(Choice(
                title=f"{topic:<50} {msg_type}",
                value=topic
            ))
        
        # Show topic selection interface
        click.secho(f"\nBag file: {click.style(input_bag, fg='green')}", bold=True)
        click.echo(f"Total topics: {click.style(str(len(topics)), fg='yellow')}")
        click.echo("\nSelect topics to include in whitelist (use space to select, enter to confirm):")
        
        selected_topics = questionary.checkbox(
            "",
            choices=topic_choices,
            instruction="[space] select/unselect [enter] confirm",
            style=custom_style
        ).ask()
        
        if selected_topics is None:  # User cancelled
            click.echo("\nOperation cancelled")
            return
            
        # Show selection summary
        click.echo("\nSelected Topics:")
        click.echo("─" * 80)
        click.echo(f"Selected: {click.style(str(len(selected_topics)), fg='green')} of "
                  f"{click.style(str(len(topics)), fg='white')} topics")
        
        # Ask for save location if not specified in command line
        if not output:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            default_path = f"whitelists/whitelist_{timestamp}.txt"
            
            # Ask if user wants to use default path
            use_default = questionary.confirm(
                f"Use default path? ({default_path})",
                default=True,
                style=custom_style
            ).ask()
            
            if use_default:
                output = default_path
            else:
                # Ask for custom path with path completion
                while True:
                    output = questionary.path(
                        "Enter save path:",
                        default="whitelists/my_whitelist.txt",
                        only_directories=False,
                        style=custom_style
                    ).ask()
                    
                    if output is None:  # User cancelled
                        click.echo("\nOperation cancelled")
                        return
                        
                    # Validate directory exists or can be created
                    try:
                        dir_path = os.path.dirname(output)
                        if dir_path and not os.path.exists(dir_path):
                            create_dir = questionary.confirm(
                                f"Directory {dir_path} does not exist. Create it?",
                                default=True,
                                style=custom_style
                            ).ask()
                            
                            if not create_dir:
                                continue
                                
                        # Try to create directory and test file writability
                        os.makedirs(dir_path, exist_ok=True)
                        # Check if file exists
                        if os.path.exists(output):
                            overwrite = questionary.confirm(
                                f"File {output} already exists. Overwrite?",
                                default=False,
                                style=custom_style
                            ).ask()
                            
                            if not overwrite:
                                continue
                        
                        break
                    except Exception as e:
                        click.echo(f"Error: {str(e)}")
                        continue
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
        
        # Save selected topics to whitelist file
        with open(output, 'w') as f:
            f.write("# Generated by rose whitelist\n")
            f.write(f"# Source: {input_bag}\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for topic in sorted(selected_topics):
                f.write(f"{topic}\n")
        
        # Show results
        click.echo("\nWhitelist Summary:")
        click.echo("─" * 80)
        click.echo(f"Selected: {click.style(str(len(selected_topics)), fg='green')} of "
                  f"{click.style(str(len(topics)), fg='white')} topics")
        click.echo(f"Saved to: {click.style(output, fg='blue')}")
        
    except ImportError:
        raise click.ClickException("questionary package is required. Install it with: pip install questionary")
    except Exception as e:
        logger.error(f"Error creating whitelist: {str(e)}", exc_info=True)
        raise click.ClickException(str(e))

@cli.command('cli')
def cli_tool():
    """Launch interactive command-line interface"""
    from .cli_tool import main
    main()

if __name__ == '__main__':
    cli()
