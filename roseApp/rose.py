#!/usr/bin/env python3
import sys

import typer

# Import logging module first
import logging

# Import necessary functions from utility modules
from roseApp.core.util import get_logger, TimeUtil, set_app_mode, AppMode, log_cli_error
from roseApp.cli.load import load as load_main
from roseApp.cli.extract import extract as extract_main
from roseApp.cli.compress import compress as compress_main
from roseApp.cli.inspect import app as inspect_app
from roseApp.cli.cache import app as cache_app
from roseApp.cli.config import app as config_app

# Initialize logger
logger = get_logger("RoseCLI")

app = typer.Typer(help="ROS bag filter utility - A powerful tool for ROS bag manipulation")

def configure_logging(verbosity: int):
    """Configure logging level based on verbosity
    
    Args:
        verbosity: Number of 'v' flags (e.g., -vvv = 3)
    """
    levels = {
        0: logging.WARNING,  # Default
        1: logging.INFO,     # -v
        2: logging.DEBUG,    # -vv
        3: logging.DEBUG,    # -vvv (more details in formatter)
    }
    level = levels.get(min(verbosity, 3), logging.DEBUG)
    logger.setLevel(level)
    
    if verbosity >= 3:
        # Add more detailed format for high verbosity
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            ))

@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity (e.g., -v, -vv, -vvv)")
):
    """ROS bag filter utility - A powerful tool for ROS bag manipulation"""
    # Set application mode to CLI
    set_app_mode(AppMode.CLI)
    
    # Initialize event emitter
    # v3.0: Pure NDJSON output (headless mode)
    from roseApp.core.event_emitter import init_emitter
    init_emitter()
        
    configure_logging(verbose)
    
    # If no subcommand is provided, emit error event
    # v3.0: Pure NDJSON event-driven architecture
    if ctx.invoked_subcommand is None:
        from roseApp.core.event_emitter import get_emitter
        emitter = get_emitter()
        emitter.emit_error(
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
