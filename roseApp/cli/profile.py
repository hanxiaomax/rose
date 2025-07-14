#!/usr/bin/env python3
"""
Profile command for ROS bag performance analysis and benchmarking.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel

# Add the project root to the Python path for benchmark imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.benchmark.test_async_vs_sync_performance import BagAnalysisBenchmark
from ..core.util import set_app_mode, AppMode, get_logger, log_cli_error
from .error_handling import ValidationError, validate_file_exists

app = typer.Typer(name="profile", help="Performance analysis and benchmarking tools")

logger = get_logger("RoseProfile")


@app.command(name="run-benchmark")
def run_benchmark(
    bags: List[str] = typer.Option(
        [],
        "--bags",
        "-b",
        help="Path(s) to bag files for testing. If not specified, will prompt for files."
    ),
    iterations: int = typer.Option(
        2,
        "--iterations",
        "-i",
        help="Number of iterations per test (default: 2, max: 10)"
    ),
    output: str = typer.Option(
        "benchmark_results.json",
        "--output",
        "-o",
        help="Output file path for results (default: benchmark_results.json)"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Quiet mode - minimal output"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Force interactive mode even if bags are specified"
    )
):
    """
    Run performance benchmark comparing async vs sync ROS bag analysis.
    
    This command measures the performance differences between async and sync 
    bag analysis across multiple levels (metadata, statistics, messages, fields).
    It provides detailed metrics including timing, memory usage, and cache hit rates.
    
    Examples:
        rose profile run-benchmark                                    # Interactive mode
        rose profile run-benchmark --bags tests/demo.bag             # Single bag
        rose profile run-benchmark --bags file1.bag file2.bag        # Multiple bags
        rose profile run-benchmark --bags tests/demo.bag --iterations 3 --output my_results.json
    """
    
    # Set application mode
    set_app_mode(AppMode.CLI)
    
    # Validate iterations
    if not (1 <= iterations <= 10):
        logger.error(f"Invalid iterations: {iterations}. Must be between 1 and 10.")
        raise typer.Exit(code=1)
    
    # Run async benchmark
    try:
        asyncio.run(_run_benchmark_async(bags, iterations, output, quiet, interactive))
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
        raise typer.Exit(code=130)
    except Exception as e:
        log_cli_error(f"Benchmark failed: {e}")
        raise typer.Exit(code=1)


async def _run_benchmark_async(
    bags: List[str], 
    iterations: int, 
    output: str, 
    quiet: bool, 
    interactive: bool
):
    """Internal async function to run the benchmark"""
    
    console = Console(quiet=quiet)
    
    if not quiet:
        console.print(Panel.fit(
            "[bold cyan]ROS Bag Analysis Performance Benchmark[/bold cyan]\n\n"
            "This tool compares the performance of async vs sync bag analysis.\n"
            "It will test real bag files and provide accurate performance metrics.\n\n"
            "[yellow]Features:[/yellow]\n"
            "• Multi-level analysis (metadata, statistics, messages, fields)\n"
            "• Memory usage monitoring\n"
            "• Cache hit rate measurement\n"
            "• Performance improvement calculations\n"
            "• JSON results export",
            title="Performance Benchmark"
        ))
    
    # Get bag files
    test_bags = []
    
    if bags and not interactive:
        # Command line mode
        for bag_path in bags:
            try:
                validate_file_exists(bag_path)
                test_bags.append(bag_path)
                if not quiet:
                    size_mb = os.path.getsize(bag_path) / (1024 * 1024)
                    console.print(f"[green]OK Added: {bag_path} ({size_mb:.1f} MB)[/green]")
            except ValidationError as e:
                console.print(f"[red]ERROR {e}[/red]")
        
        if not test_bags:
            console.print("[red]ERROR No valid bag files found. Exiting.[/red]")
            raise typer.Exit(code=1)
    else:
        # Interactive mode
        test_bags = _get_test_bags_interactive(console)
        
        if not test_bags:
            console.print("[red]ERROR No valid bag files provided. Exiting.[/red]")
            raise typer.Exit(code=1)
    
    if not quiet:
        console.print(f"[green]OK Found {len(test_bags)} bag files to test[/green]")
        for i, bag in enumerate(test_bags, 1):
            size_mb = os.path.getsize(bag) / (1024 * 1024)
            console.print(f"  {i}. {bag} ({size_mb:.1f} MB)")
        
        console.print(f"\n[cyan]Starting benchmark with {iterations} iterations per test...[/cyan]")
    
    # Create benchmark instance
    benchmark = BagAnalysisBenchmark(console=console)
    
    # Run comprehensive benchmark
    try:
        summary = await benchmark.run_comprehensive_benchmark(
            test_bags=test_bags,
            iterations=iterations
        )
        
        # Display results
        if not quiet:
            benchmark.display_results(summary)
        
        # Save results
        benchmark.save_results(summary, output)
        
        if not quiet:
            console.print(f"\n[green]OK Benchmark completed successfully![/green]")
            console.print(f"Results saved to: {output}")
        else:
            console.print(f"Benchmark completed. Results saved to: {output}")
            
    except Exception as e:
        console.print(f"[red]ERROR Benchmark failed: {e}[/red]")
        if not quiet:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise


def _get_test_bags_interactive(console: Console) -> List[str]:
    """Get bag files from user input in interactive mode"""
    
    test_bags = []
    
    # Check for common bag file locations
    common_paths = [
        "tests/demo.bag",
        "tests/test_data/demo.bag",
        "test_data/demo.bag",
        "demo.bag"
    ]
    
    console.print("\n[yellow]Checking for common bag files...[/yellow]")
    found_bags = []
    for path in common_paths:
        if os.path.exists(path):
            found_bags.append(path)
            console.print(f"  [green]OK Found: {path}[/green]")
    
    if found_bags:
        console.print(f"\n[cyan]Found {len(found_bags)} bag files. Do you want to use them?[/cyan]")
        for i, bag in enumerate(found_bags, 1):
            size_mb = os.path.getsize(bag) / (1024 * 1024)
            console.print(f"  {i}. {bag} ({size_mb:.1f} MB)")
        
        try:
            use_found = typer.prompt(
                "\nUse these bag files? (y/n)",
                default="y"
            ).lower().strip()
            
            if use_found in ["y", "yes"]:
                test_bags.extend(found_bags)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Interrupted by user[/yellow]")
            return []
    
    # Allow user to add more bags
    console.print("\n[yellow]You can add more bag files (press Enter when done):[/yellow]")
    while True:
        try:
            bag_path = typer.prompt("Enter bag file path (or press Enter to finish)", default="")
            if not bag_path:
                break
            
            if os.path.exists(bag_path):
                if bag_path not in test_bags:
                    test_bags.append(bag_path)
                    size_mb = os.path.getsize(bag_path) / (1024 * 1024)
                    console.print(f"  [green]OK Added: {bag_path} ({size_mb:.1f} MB)[/green]")
                else:
                    console.print(f"  [yellow]Already added: {bag_path}[/yellow]")
            else:
                console.print(f"  [red]ERROR File not found: {bag_path}[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Interrupted by user[/yellow]")
            break
    
    return test_bags


def main():
    """Main entry point for profile command"""
    app()


if __name__ == "__main__":
    main() 