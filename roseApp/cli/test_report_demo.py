#!/usr/bin/env python3
"""
Demo program showing how to use the responsive test report table
"""

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box
from typing import List, Dict, Any
import typer


def create_test_report_table(test_results: List[Dict[str, Any]], console: Console) -> Table:
    """Create a responsive table for test report display with three columns"""
    # Get terminal width for responsive layout
    terminal_width = console.width
    
    # Create table with responsive columns
    table = Table(box=box.SIMPLE, title="Test Report", title_style="bold cyan")
    
    # Calculate column widths based on terminal width
    test_item_width = 25
    status_width = 10
    fixed_width = test_item_width + status_width + 6  # 6 for borders and padding
    
    # Available width for details column
    details_width = terminal_width - fixed_width
    
    # Ensure minimum width for details column
    if details_width < 30:
        test_item_width = 20
        details_width = terminal_width - test_item_width - status_width - 6
        
    # Add columns with responsive widths
    table.add_column("Test Item", justify="left", style="bold", width=test_item_width)
    table.add_column("Status", justify="center", style="bold", width=status_width)
    table.add_column("Details", justify="left", style="white", width=details_width, 
                    overflow="fold", no_wrap=False)
    
    # Add rows
    for result in test_results:
        test_item = result.get('test_item', 'Unknown')
        status = result.get('status', 'Unknown')
        details = result.get('details', 'No details available')
        
        # Create test item text
        test_item_text = Text(test_item, style="cyan")
        
        # Create status text with appropriate styling
        if status.lower() in ['pass', 'passed', 'success', 'ok']:
            status_text = Text("✓ PASS", style="green")
        elif status.lower() in ['fail', 'failed', 'error', 'failed']:
            status_text = Text("✗ FAIL", style="red")
        elif status.lower() in ['skip', 'skipped', 'pending']:
            status_text = Text("○ SKIP", style="yellow")
        else:
            status_text = Text(status, style="white")
        
        # Create details text with word wrapping
        details_text = Text(details, style="white")
        
        # Add row to table
        table.add_row(test_item_text, status_text, details_text)
    
    return table


def main():
    """Test report table demo"""
    console = Console()
    
    # Sample test results
    test_results = [
        {
            'test_item': 'Parser Initialization',
            'status': 'pass',
            'details': 'Successfully initialized rosbags parser with LZ4 compression support'
        },
        {
            'test_item': 'Topic Loading',
            'status': 'pass',
            'details': 'Loaded 17 topics from demo.bag file including /tf, /image_raw, /odom, /scan, /cmd_vel and others'
        },
        {
            'test_item': 'Statistics Calculation',
            'status': 'pass',
            'details': 'Calculated topic statistics: 5390 total messages, 695.5MB total size across all topics'
        },
        {
            'test_item': 'Whitelist Validation',
            'status': 'fail',
            'details': 'Whitelist file not found at path: /path/to/whitelist.txt. Please create the file or specify correct path'
        },
        {
            'test_item': 'Compression Test',
            'status': 'pass',
            'details': 'LZ4 compression working correctly, reduced output size by 25% with 70% performance improvement'
        },
        {
            'test_item': 'Parallel Processing',
            'status': 'skip',
            'details': 'Parallel processing test skipped as only single file specified'
        },
        {
            'test_item': 'Filter Operation',
            'status': 'pass',
            'details': 'Successfully filtered 1 out of 17 topics, resulting in 182.3KB output from 695.5MB input'
        },
        {
            'test_item': 'Memory Usage',
            'status': 'pass',
            'details': 'Memory usage stayed below 500MB during processing of 695.5MB bag file'
        },
        {
            'test_item': 'Error Handling',
            'status': 'fail',
            'details': 'Error handling test failed: expected graceful degradation when input file does not exist, but got unhandled exception'
        },
        {
            'test_item': 'CLI Interface',
            'status': 'pass',
            'details': 'Command line interface working correctly with proper argument parsing, help text, and error messages'
        }
    ]
    
    # Display test report
    console.print("\n[bold]Rose ROS Bag Tool - Test Report[/bold]")
    console.print("=" * 50)
    console.print()
    
    # Create and display responsive table
    table = create_test_report_table(test_results, console)
    console.print(table)
    
    # Calculate summary statistics
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results if result['status'].lower() in ['pass', 'passed', 'success', 'ok'])
    failed_tests = sum(1 for result in test_results if result['status'].lower() in ['fail', 'failed', 'error'])
    skipped_tests = sum(1 for result in test_results if result['status'].lower() in ['skip', 'skipped', 'pending'])
    
    # Display summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"Total: {total_tests} tests")
    console.print(f"[green]Passed: {passed_tests}[/green]")
    console.print(f"[red]Failed: {failed_tests}[/red]")
    console.print(f"[yellow]Skipped: {skipped_tests}[/yellow]")
    
    pass_rate = (passed_tests / total_tests) * 100
    console.print(f"\nPass Rate: [{'green' if pass_rate >= 80 else 'red'}]{pass_rate:.1f}%[/{'green' if pass_rate >= 80 else 'red'}]")


if __name__ == "__main__":
    main() 