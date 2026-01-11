#!/usr/bin/env python3
"""
Rose CLI - ROS bag filter utility.

A powerful tool for ROS bag manipulation.
"""

import sys
import typer

# Import necessary functions from utility modules
from roseApp.core.logging import get_logger, log_cli_error
from roseApp.core.output import get_output
from roseApp.cli.load import load as load_main
from roseApp.cli.extract import extract as extract_main
from roseApp.cli.compress import compress as compress_main
from roseApp.cli.inspect import inspect as inspect_main
from roseApp.cli.list import app as list_app
from roseApp.cli.config import app as config_app

# Initialize logger
logger = get_logger("RoseCLI")

# Create main app
app = typer.Typer(help="ROS bag filter utility - A powerful tool for ROS bag manipulation")


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    # If no subcommand is provided, launch interactive TUI
    if ctx.invoked_subcommand is None:
        from roseApp.tui.main_app import main_tui_loop
        main_tui_loop()
        raise typer.Exit(0)


# Add subcommands
app.command(name="load")(load_main)
app.command(name="extract")(extract_main)
app.command(name="compress")(compress_main)
app.command(name="inspect")(inspect_main)
app.add_typer(list_app, name="list")
app.add_typer(config_app, name="config")


if __name__ == '__main__':
    try:
        app()
    except typer.Exit as e:
        # Re-raise typer.Exit cleanly (this is expected behavior)
        raise
    except Exception as e:
        # Handle top-level exceptions gracefully
        error_msg = log_cli_error(e)
        typer.echo(error_msg, err=True)
        sys.exit(1)
