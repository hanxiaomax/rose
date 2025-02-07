#!/usr/bin/env python3

import os
import click
from tui import RoseTUI     



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
@click.argument('input_bag')
@click.argument('output_bag')
@click.option('--whitelist', default='../roseApp/whitelists/example.txt',
              help='Path to topic whitelist file')
def filter(input_bag, output_bag, whitelist):
    """Filter ROS bag by topic whitelist"""
    if not os.path.exists(input_bag):
        raise click.ClickException(f"Input bag file {input_bag} not found")
    
    whitelist_topics = Operation.load_whitelist(whitelist)
    if not whitelist_topics:
        raise click.ClickException("No valid topics found in whitelist")
    
    click.echo(f"Filtering {input_bag} to {output_bag}")
    click.echo(f"Whitelisted topics: {whitelist_topics}")
    result = Operation.filter_bag(input_bag, output_bag, whitelist_topics)
    click.echo(result)

@cli.command()
@click.argument('input_bag')
def inspect(input_bag):
    """List all topics and message types in the bag file"""
    if not os.path.exists(input_bag):
        raise click.ClickException(f"Input bag file {input_bag} not found")
    result = Operation.inspect_bag(input_bag)
    click.echo(result)



if __name__ == '__main__':
    cli()
