#!/usr/bin/env python3
"""
Rose CLI - ROS bag filter utility.

A powerful tool for ROS bag manipulation with headless NDJSON output.
"""

import sys
import typer

# Import necessary functions from utility modules
from roseApp.core.logging import get_logger, log_cli_error
from roseApp.cli.load import load as load_main
from roseApp.cli.extract import extract as extract_main
from roseApp.cli.compress import compress as compress_main
from roseApp.cli.inspect import app as inspect_app
from roseApp.cli.cache import app as cache_app
from roseApp.cli.config import app as config_app

# Initialize logger
logger = get_logger("RoseCLI")

# Create main app
app = typer.Typer(help="ROS bag filter utility - A powerful tool for ROS bag manipulation")


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    # Initialize event emitter (headless mode - pure NDJSON output)
    from roseApp.core.event_emitter import init_emitter
    init_emitter()
    
    # If no subcommand is provided, emit error event
    if ctx.invoked_subcommand is None:
        from roseApp.core.event_emitter import E
        E.error(
            "NO_COMMAND",
            "No command specified. Use --help for usage."
        )
        raise typer.Exit(1)


# Add subcommands
app.command(name="load")(load_main)
app.command(name="extract")(extract_main)
app.command(name="compress")(compress_main)
app.add_typer(inspect_app)
app.add_typer(cache_app)
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
