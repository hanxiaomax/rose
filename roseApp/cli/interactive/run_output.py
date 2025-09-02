#!/usr/bin/env python3
"""
Output rendering and streaming for Rose interactive run environment
Implements collapsible output, streaming progress, and structured logging
"""

import time
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.live import Live
from rich.layout import Layout

from ...ui.theme import get_color


@dataclass
class LogEntry:
    """Single log entry with metadata"""
    timestamp: float
    level: str  # 'info', 'warning', 'error', 'success'
    message: str
    context: Optional[Dict[str, Any]] = None


@dataclass
class ProgressStep:
    """Progress step with collapsible details"""
    name: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    logs: List[LogEntry]
    substeps: List['ProgressStep']
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress_percent: Optional[float] = None


class StreamingRenderer:
    """Handles streaming output and collapsible progress display"""
    
    def __init__(self, console: Console):
        self.console = console
        self.current_steps = []
        self.live_display = None
        self.show_details = {}  # step_id -> bool
    
    def create_progress_tree(self, steps: List[ProgressStep], max_logs: int = 3) -> Tree:
        """Create collapsible tree view of progress steps"""
        tree = Tree("[bold]Operations Progress[/bold]")
        
        for step in steps:
            # Determine step status icon and style
            if step.status == 'completed':
                icon = "[green]✓[/green]"
                style = "green"
            elif step.status == 'running':
                icon = "[yellow]⚡[/yellow]"
                style = "yellow"
            elif step.status == 'failed':
                icon = "[red]✗[/red]"
                style = "red"
            else:
                icon = "[dim]○[/dim]"
                style = "dim"
            
            # Create step node
            step_text = f"{icon} {step.name}"
            if step.progress_percent is not None:
                step_text += f" ({step.progress_percent:.0f}%)"
            
            if step.start_time and step.end_time:
                elapsed = step.end_time - step.start_time
                step_text += f" ({elapsed:.1f}s)"
            elif step.start_time:
                elapsed = time.time() - step.start_time
                step_text += f" ({elapsed:.1f}s)"
            
            step_node = tree.add(step_text, style=style)
            
            # Add recent logs (limited to prevent clutter)
            recent_logs = step.logs[-max_logs:] if len(step.logs) > max_logs else step.logs
            
            for log in recent_logs:
                log_style = {
                    'info': 'dim',
                    'warning': 'yellow',
                    'error': 'red',
                    'success': 'green'
                }.get(log.level, 'white')
                
                timestamp_str = time.strftime("%H:%M:%S", time.localtime(log.timestamp))
                log_text = f"[{timestamp_str}] {log.message}"
                step_node.add(log_text, style=log_style)
            
            # Show truncation indicator if needed
            if len(step.logs) > max_logs:
                step_node.add(f"[dim]... and {len(step.logs) - max_logs} more entries[/dim]")
            
            # Add substeps recursively
            for substep in step.substeps:
                self._add_substep_to_tree(step_node, substep, max_logs)
        
        return tree
    
    def _add_substep_to_tree(self, parent_node, substep: ProgressStep, max_logs: int):
        """Add substep to tree recursively"""
        # Similar logic to main step but as child node
        if substep.status == 'completed':
            icon = "[green]✓[/green]"
        elif substep.status == 'running':
            icon = "[yellow]⚡[/yellow]"
        elif substep.status == 'failed':
            icon = "[red]✗[/red]"
        else:
            icon = "[dim]○[/dim]"
        
        substep_text = f"{icon} {substep.name}"
        if substep.progress_percent is not None:
            substep_text += f" ({substep.progress_percent:.0f}%)"
        
        substep_node = parent_node.add(substep_text)
        
        # Add logs (fewer for substeps)
        recent_logs = substep.logs[-2:] if len(substep.logs) > 2 else substep.logs
        for log in recent_logs:
            log_style = {
                'info': 'dim',
                'warning': 'yellow', 
                'error': 'red',
                'success': 'green'
            }.get(log.level, 'white')
            
            substep_node.add(f"[dim]{log.message}[/dim]", style=log_style)
    
    def create_status_panel(self, title: str, content: Dict[str, Any]) -> Panel:
        """Create status panel with structured content"""
        status_text = Text()
        
        for key, value in content.items():
            if isinstance(value, dict):
                status_text.append(f"{key}:\n", style="bold")
                for subkey, subvalue in value.items():
                    status_text.append(f"  {subkey}: {subvalue}\n", style="dim")
            elif isinstance(value, list):
                status_text.append(f"{key}: {len(value)} items\n", style="dim")
                if len(value) <= 3:
                    for item in value:
                        status_text.append(f"  • {item}\n", style="dim")
            else:
                status_text.append(f"{key}: {value}\n", style="dim")
        
        return Panel(status_text, title=title, border_style=get_color('primary'))
    
    def start_streaming_progress(self, title: str = "Operations") -> 'StreamingContext':
        """Start streaming progress display"""
        return StreamingContext(self, title)
    
    def display_collapsible_results(self, results: Dict[str, Any], title: str = "Results"):
        """Display results in collapsible format"""
        tree = Tree(f"[bold]{title}[/bold]")
        
        for category, items in results.items():
            if isinstance(items, list) and items:
                category_node = tree.add(f"[cyan]{category} ({len(items)})[/cyan]")
                
                for item in items[:10]:  # Limit display to first 10 items
                    if isinstance(item, dict):
                        item_name = item.get('name', item.get('path', str(item)))
                        item_status = item.get('status', item.get('success', 'unknown'))
                        
                        if item_status in [True, 'completed', 'success']:
                            category_node.add(f"[green]✓ {item_name}[/green]")
                        elif item_status in [False, 'failed', 'error']:
                            category_node.add(f"[red]✗ {item_name}[/red]")
                        else:
                            category_node.add(f"[yellow]• {item_name}[/yellow]")
                    else:
                        category_node.add(str(item))
                
                if len(items) > 10:
                    category_node.add(f"[dim]... and {len(items) - 10} more items[/dim]")
            
            elif isinstance(items, dict):
                category_node = tree.add(f"[cyan]{category}[/cyan]")
                for key, value in list(items.items())[:5]:  # Limit to first 5 items
                    category_node.add(f"{key}: {value}")
                
                if len(items) > 5:
                    category_node.add(f"[dim]... and {len(items) - 5} more entries[/dim]")
            
            else:
                tree.add(f"[cyan]{category}[/cyan]: {items}")
        
        self.console.print(tree)


class StreamingContext:
    """Context manager for streaming progress display"""
    
    def __init__(self, renderer: StreamingRenderer, title: str):
        self.renderer = renderer
        self.title = title
        self.steps = []
        self.live = None
        self.console = renderer.console
    
    def __enter__(self):
        # Setup live display
        self.live = Live(
            self._create_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False
        )
        self.live.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.live:
            self.live.stop()
    
    def add_step(self, name: str) -> 'StepContext':
        """Add a new progress step"""
        step = ProgressStep(
            name=name,
            status='pending',
            logs=[],
            substeps=[],
            start_time=None
        )
        self.steps.append(step)
        self._update_display()
        return StepContext(self, step)
    
    def _create_display(self):
        """Create the display layout"""
        if not self.steps:
            return Panel("[dim]No operations in progress[/dim]", title=self.title)
        
        tree = self.renderer.create_progress_tree(self.steps)
        return Panel(tree, title=self.title, border_style=get_color('accent'))
    
    def _update_display(self):
        """Update the live display"""
        if self.live:
            self.live.update(self._create_display())


class StepContext:
    """Context manager for individual progress steps"""
    
    def __init__(self, streaming_context: StreamingContext, step: ProgressStep):
        self.streaming_context = streaming_context
        self.step = step
    
    def __enter__(self):
        self.step.start_time = time.time()
        self.step.status = 'running'
        self.streaming_context._update_display()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.step.end_time = time.time()
        
        if exc_type is None:
            self.step.status = 'completed'
            self.log("Operation completed successfully", 'success')
        else:
            self.step.status = 'failed'
            self.log(f"Operation failed: {exc_val}", 'error')
        
        self.streaming_context._update_display()
    
    def log(self, message: str, level: str = 'info', context: Optional[Dict[str, Any]] = None):
        """Add log entry to current step"""
        log_entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            context=context
        )
        self.step.logs.append(log_entry)
        self.streaming_context._update_display()
    
    def update_progress(self, percent: float):
        """Update step progress percentage"""
        self.step.progress_percent = max(0, min(100, percent))
        self.streaming_context._update_display()
    
    def add_substep(self, name: str) -> 'StepContext':
        """Add substep to current step"""
        substep = ProgressStep(
            name=name,
            status='pending',
            logs=[],
            substeps=[]
        )
        self.step.substeps.append(substep)
        self.streaming_context._update_display()
        return StepContext(self.streaming_context, substep)


class TableRenderer:
    """Helper for rendering structured data as tables"""
    
    @staticmethod
    def create_status_table(data: Dict[str, Any], title: str = "Status") -> Table:
        """Create a status table from dictionary data"""
        table = Table(title=title, show_header=True)
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                display_value = f"{len(value)} items" if isinstance(value, list) else f"{len(value)} entries"
            else:
                display_value = str(value)
            
            table.add_row(key.replace('_', ' ').title(), display_value)
        
        return table
    
    @staticmethod
    def create_results_table(results: List[Dict[str, Any]], title: str = "Results") -> Table:
        """Create results table from list of dictionaries"""
        if not results:
            return Table(title=title)
        
        table = Table(title=title, show_header=True)
        
        # Auto-detect columns from first result
        first_result = results[0]
        for key in first_result.keys():
            if key in ['path', 'file', 'name']:
                table.add_column(key.title(), style="cyan")
            elif key in ['status', 'success']:
                table.add_column(key.title(), style="green")
            elif key in ['error', 'message']:
                table.add_column(key.title(), style="red", max_width=40)
            else:
                table.add_column(key.title(), style="white")
        
        # Add rows
        for result in results:
            row_data = []
            for key in first_result.keys():
                value = result.get(key, '')
                
                # Format specific types
                if key in ['status', 'success']:
                    if value in [True, 'completed', 'success']:
                        row_data.append("[green]✓[/green]")
                    elif value in [False, 'failed', 'error']:
                        row_data.append("[red]✗[/red]")
                    else:
                        row_data.append(str(value))
                elif key == 'path' and isinstance(value, str):
                    # Show only filename for paths
                    from pathlib import Path
                    row_data.append(Path(value).name)
                else:
                    display_value = str(value)
                    if len(display_value) > 40:
                        display_value = display_value[:37] + "..."
                    row_data.append(display_value)
            
            table.add_row(*row_data)
        
        return table


class StreamingProgress:
    """Context manager for streaming progress with real-time updates"""
    
    def __init__(self, console: Console, description: str = "Processing"):
        self.console = console
        self.description = description
        self.progress = None
        self.task_id = None
        self.log_entries = []
    
    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False
        )
        self.progress.start()
        self.task_id = self.progress.add_task(self.description, total=100)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            if exc_type is None:
                self.progress.update(self.task_id, description=f"[green]✓ {self.description}[/green]", completed=100)
            else:
                self.progress.update(self.task_id, description=f"[red]✗ {self.description}[/red]", completed=100)
            
            # Keep the progress visible for a moment
            time.sleep(0.5)
            self.progress.stop()
    
    def update(self, percent: float, description: Optional[str] = None):
        """Update progress percentage and optionally description"""
        if self.progress and self.task_id is not None:
            update_args = {'completed': max(0, min(100, percent))}
            if description:
                update_args['description'] = description
            self.progress.update(self.task_id, **update_args)
    
    def log(self, message: str, level: str = 'info'):
        """Add log entry (will be shown after progress completes)"""
        log_entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message
        )
        self.log_entries.append(log_entry)
    
    def show_logs(self):
        """Display accumulated logs after progress completes"""
        if not self.log_entries:
            return
        
        self.console.print("\n[bold]Operation Details:[/bold]")
        for log in self.log_entries:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime(log.timestamp))
            style = {
                'info': 'dim',
                'warning': 'yellow',
                'error': 'red', 
                'success': 'green'
            }.get(log.level, 'white')
            
            self.console.print(f"[{timestamp_str}] {log.message}", style=style)


class ResultFormatter:
    """Formats operation results for display"""
    
    @staticmethod
    def format_load_result(result: Dict[str, Any]) -> str:
        """Format load operation result"""
        if result.get('success'):
            bag_name = Path(result['bag_path']).name
            topics_count = result.get('topics_count', 0)
            size_mb = result.get('file_size_mb', 0)
            return f"SUCCESS: Loaded {bag_name} ({topics_count} topics, {size_mb:.1f} MB)"
        else:
            error = result.get('error', 'Unknown error')
            return f"ERROR: Load failed: {error}"
    
    @staticmethod
    def format_extract_result(result: Dict[str, Any]) -> str:
        """Format extract operation result"""
        if result.get('success'):
            success_count = result.get('success_count', 0)
            total_count = result.get('total_count', 0)
            topics_count = result.get('topics_count', 0)
            return f"SUCCESS: Extracted {topics_count} topics from {success_count}/{total_count} bags"
        else:
            error = result.get('error', 'Unknown error')
            return f"ERROR: Extraction failed: {error}"
    
    @staticmethod
    def format_inspect_result(result: Dict[str, Any]) -> str:
        """Format inspect operation result"""
        if result.get('success'):
            report = result.get('report', {})
            topics_count = report.get('topics_count', 0)
            messages_count = report.get('total_messages', 0)
            return f"SUCCESS: Inspection completed: {topics_count} topics, {messages_count} messages"
        else:
            error = result.get('error', 'Unknown error')
            return f"ERROR: Inspection failed: {error}"
    
    @staticmethod
    def format_compress_result(result: Dict[str, Any]) -> str:
        """Format compress operation result"""
        if result.get('success'):
            success_count = result.get('success_count', 0)
            total_count = result.get('total_count', 0)
            compression = result.get('compression', 'unknown')
            return f"SUCCESS: Compressed {success_count}/{total_count} bags with {compression}"
        else:
            error = result.get('error', 'Unknown error')
            return f"ERROR: Compression failed: {error}"
    
    @staticmethod
    def format_data_result(result: Dict[str, Any]) -> str:
        """Format data export operation result"""
        if result.get('success'):
            row_count = result.get('row_count', 0)
            output_path = result.get('output_path', 'unknown')
            return f"SUCCESS: Exported {row_count} rows to {Path(output_path).name}"
        else:
            error = result.get('error', 'Unknown error')
            return f"ERROR: Data export failed: {error}"


if __name__ == "__main__":
    pass
