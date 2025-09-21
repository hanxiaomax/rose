#!/usr/bin/env python3
"""
Result Formatter - Formats CLI command outputs for user-friendly display
"""

from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from ...core.util import get_logger

logger = get_logger("result_formatter")


class ResultFormatter:
    """Formats CLI command results for interactive display"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def format_cli_result(self, result: Dict[str, Any]) -> str:
        """
        Convert raw CLI output to formatted display
        
        Args:
            result: CLI execution result dictionary
            
        Returns:
            Formatted string for display
        """
        try:
            success = result.get('success', False)
            
            if success:
                return self.format_success(result.get('stdout', ''))
            else:
                return self.format_error(
                    result.get('stderr', ''),
                    result.get('error', 'Unknown error')
                )
        
        except Exception as e:
            logger.error(f"Result formatting error: {e}")
            return f"[red]Error formatting result: {e}[/red]"
    
    def format_success(self, stdout: str) -> str:
        """
        Format successful command output
        
        Args:
            stdout: Standard output from command
            
        Returns:
            Formatted success message
        """
        if not stdout.strip():
            return "[green]✓[/green] Command completed successfully"
        
        # Clean up output
        cleaned_output = stdout.strip()
        
        # Add success indicator
        return f"[green]✓[/green] {cleaned_output}"
    
    def format_error(self, stderr: str, error: str) -> str:
        """
        Format error output
        
        Args:
            stderr: Standard error from command
            error: Error message
            
        Returns:
            Formatted error message
        """
        error_msg = stderr.strip() if stderr.strip() else error
        return f"[red]✗[/red] {error_msg}"
    
    def format_operation_result(self, operation: str, success: bool, message: str, error: Optional[str] = None) -> None:
        """
        Display operation result with rich formatting
        
        Args:
            operation: Operation name
            success: Whether operation succeeded
            message: Success message
            error: Error message if failed
        """
        if success:
            self.console.print(f"[green]✓[/green] {operation.title()}: {message}")
        else:
            error_text = error or "Unknown error"
            self.console.print(f"[red]✗[/red] {operation.title()} failed: {error_text}")
    
    def format_command_help(self, command: str, description: str) -> None:
        """
        Format command help display
        
        Args:
            command: Command name
            description: Command description
        """
        self.console.print(f"  [cyan]{command:<20}[/cyan] {description}")
    
    def format_status_info(self, title: str, items: Dict[str, Any]) -> None:
        """
        Format status information display
        
        Args:
            title: Status section title
            items: Status items to display
        """
        if not items:
            return
        
        table = Table(title=title, show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in items.items():
            table.add_row(key, str(value))
        
        self.console.print(table)
    
    def format_list_items(self, title: str, items: list, item_formatter=None) -> None:
        """
        Format list of items
        
        Args:
            title: List title
            items: Items to display
            item_formatter: Optional function to format each item
        """
        if not items:
            self.console.print(f"[dim]{title}: None[/dim]")
            return
        
        self.console.print(f"[bold]{title}:[/bold]")
        
        for item in items:
            if item_formatter:
                formatted_item = item_formatter(item)
            else:
                formatted_item = str(item)
            
            self.console.print(f"  • {formatted_item}")
    
    def format_panel(self, content: str, title: str, border_style: str = "blue") -> None:
        """
        Format content in a panel
        
        Args:
            content: Panel content
            title: Panel title
            border_style: Border style
        """
        panel = Panel(content, title=title, border_style=border_style)
        self.console.print(panel)
    
    def format_section_header(self, title: str) -> None:
        """
        Format section header
        
        Args:
            title: Section title
        """
        self.console.print(f"\n[bold blue]{title}[/bold blue]")
    
    def format_warning(self, message: str) -> None:
        """
        Format warning message
        
        Args:
            message: Warning message
        """
        self.console.print(f"[yellow]⚠[/yellow] {message}")
    
    def format_info(self, message: str) -> None:
        """
        Format info message
        
        Args:
            message: Info message
        """
        self.console.print(f"[blue]ℹ[/blue] {message}")
    
    def format_muted(self, message: str) -> None:
        """
        Format muted message
        
        Args:
            message: Muted message
        """
        self.console.print(f"[dim]{message}[/dim]")
