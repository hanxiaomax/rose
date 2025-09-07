#!/usr/bin/env python3
"""
Command handlers for Rose interactive run environment
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit.shortcuts import confirm
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
import typer

from ...ui.theme import get_color
from ...ui.common_ui import Message
from ..util import check_and_load_bag_cache
from .run_cli_adapter import CLIAdapter


class RunCommandHandlers:
    """Command handlers for the interactive run environment"""
    
    def __init__(self, runner):
        self.runner = runner
        self.console = runner.console
        self.state = runner.state
        self.cli_adapter = CLIAdapter(runner)
        self.cache_manager = runner.cache_manager
        self.task_queue = runner.task_queue
        self.running_tasks = runner.running_tasks
        self.rose_dirs = runner.rose_dirs
    
    # =============================================================================
    # Core Command Handlers
    # =============================================================================
    
    def handle_ask(self, query: str):
        """Handle ask/help queries with intelligent suggestions"""
        if not query:
            self.console.print("[yellow]What would you like to know? Try asking about bag operations, or use /help for commands.[/yellow]")
            return
        
        # Analyze query and provide contextual help
        suggestions = self._analyze_query_and_suggest(query)
        
        if suggestions:
            self.console.print(f"[cyan]Based on your question about '{query}', here are some suggestions:[/cyan]\n")
            
            for i, suggestion in enumerate(suggestions, 1):
                self.console.print(f"{i}. {suggestion['description']}")
                self.console.print(f"   Command: [bold]{suggestion['command']}[/bold]")
                if suggestion.get('example'):
                    self.console.print(f"   Example: [dim]{suggestion['example']}[/dim]")
                self.console.print()
            
            # Ask if user wants to run any suggestion
            if len(suggestions) == 1:
                if confirm(f"Would you like to run: {suggestions[0]['command']}?"):
                    self.runner._dispatch_command(suggestions[0]['command'])
            elif len(suggestions) > 1:
                choices = [Choice(value=s['command'], name=f"{i+1}. {s['description']}") 
                          for i, s in enumerate(suggestions)]
                choices.append(Choice(value=None, name="Cancel"))
                
                selected = inquirer.select(
                    message="Select a command to run:",
                    choices=choices
                ).execute()
                
                if selected:
                    self.runner._dispatch_command(selected)
        else:
            self.console.print(f"[yellow]I'm not sure how to help with '{query}'. Try /help for available commands.[/yellow]")
    
    def handle_run(self, operation: str):
        """Handle background task execution"""
        if not operation:
            self._show_run_help()
            return
        
        # Parse operation
        parts = operation.split()
        if not parts:
            self.console.print("[red]No operation specified[/red]")
            return
        
        op_type = parts[0]
        
        if op_type == "load":
            result = self.cli_adapter.interactive_load(parts[1:])
            self._show_operation_result('load', result)
        elif op_type == "extract":
            result = self.cli_adapter.interactive_extract(parts[1:])
            self._show_operation_result('extract', result)
        elif op_type == "inspect":
            result = self.cli_adapter.interactive_inspect(parts[1:])
            self._show_operation_result('inspect', result)
        elif op_type == "compress":
            result = self.cli_adapter.interactive_compress(parts[1:])
            self._show_operation_result('compress', result)
        elif op_type == "data":
            result = self.cli_adapter.interactive_data(parts[1:])
            self._show_operation_result('data', result)
        elif op_type == "cache":
            result = self.cli_adapter.interactive_cache(parts[1:])
            self._show_operation_result('cache', result)
        elif op_type == "plugin":
            result = self.cli_adapter.interactive_plugin(parts[1:])
            self._show_operation_result('plugin', result)
        else:
            self.console.print(f"[red]Unknown operation: {op_type}[/red]")
            self._show_run_help()
    
    def _show_operation_result(self, operation: str, result: Dict[str, Any]):
        """Display operation result with appropriate formatting"""
        if result.get('success'):
            message = result.get('message', f'{operation.title()} completed successfully')
            self.console.print(f"[green]SUCCESS: {message}[/green]")
        else:
            error = result.get('error', 'Unknown error')
            self.console.print(f"[red]ERROR: {operation.title()} failed: {error}[/red]")
    
    def handle_undo(self, args: str):
        """Handle undo operations"""
        if not self.state.undo_stack:
            self.console.print("[yellow]Nothing to undo[/yellow]")
            return
        
        # Restore previous state
        previous_state = self.state.undo_stack.pop()
        
        # Create undo info
        current_time = time.strftime("%H:%M:%S")
        self.console.print(f"[green]✓ Undid operation from {current_time}[/green]")
        
        # Apply state changes
        if 'current_bags' in previous_state:
            self.state.current_bags = previous_state['current_bags']
        if 'selected_topics' in previous_state:
            self.state.selected_topics = previous_state['selected_topics']
        
        self._show_status_summary()
    
    def handle_cancel(self, args: str):
        """Handle task cancellation"""
        if not self.running_tasks:
            self.console.print("[yellow]No running tasks to cancel[/yellow]")
            return
        
        if args:
            # Cancel specific task
            task_id = args.strip()
            if task_id in self.running_tasks:
                self.running_tasks[task_id].status = 'cancelled'
                self.console.print(f"[yellow]Cancelled task: {task_id}[/yellow]")
            else:
                self.console.print(f"[red]Task not found: {task_id}[/red]")
        else:
            # Cancel all tasks
            if self.running_tasks:
                cancelled_count = len(self.running_tasks)
                for task in self.running_tasks.values():
                    task.status = 'cancelled'
                self.running_tasks.clear()
                self.console.print(f"[yellow]Cancelled {cancelled_count} running tasks[/yellow]")
    
    def handle_status(self, args: str):
        """Show current status and running tasks"""
        self._show_status_summary()
        
        # Show running tasks
        if self.running_tasks:
            self.console.print("\n[bold]Running Tasks:[/bold]")
            for task_id, task in self.running_tasks.items():
                elapsed = time.time() - (task.start_time or time.time())
                self.console.print(f"  {task_id}: {task.command} ([yellow]{elapsed:.1f}s[/yellow])")
        
        # Show recent completed tasks
        recent_tasks = [t for t in self.state.task_history[-5:] if t.status in ['completed', 'failed']]
        if recent_tasks:
            self.console.print("\n[bold]Recent Tasks:[/bold]")
            for task in recent_tasks:
                status_color = 'green' if task.status == 'completed' else 'red'
                elapsed = (task.end_time or time.time()) - (task.start_time or time.time())
                self.console.print(f"  {task.task_id}: {task.command} ([{status_color}]{task.status}[/{status_color}], {elapsed:.1f}s)")
    
    def handle_note(self, note_text: str):
        """Add a note to current session"""
        if not note_text:
            note_text = inquirer.text(message="Enter note:").execute()
            if not note_text:
                return
        
        timestamp = time.strftime("%H:%M:%S")
        note_with_time = f"[{timestamp}] {note_text}"
        self.state.notes.append(note_with_time)
        
        self.console.print(f"[green]✓ Note added: {note_text}[/green]")
    
    def handle_notes(self, args: str):
        """Show all notes"""
        if not self.state.notes:
            self.console.print("[yellow]No notes in current session[/yellow]")
            return
        
        self.console.print("[bold]Session Notes:[/bold]")
        for i, note in enumerate(self.state.notes, 1):
            self.console.print(f"  {i}. {note}")
    
    def handle_workspace(self, args: str):
        """Handle workspace operations"""
        if args == "info":
            self._show_workspace_info()
        elif args.startswith("cd "):
            new_path = args[3:].strip()
            self._change_workspace(new_path)
        else:
            self._show_workspace_info()
    
    def handle_bags(self, args: str):
        """Handle bag file operations"""
        if not args:
            self._show_bags_interactive()
        elif args == "list":
            self._list_current_bags()
        elif args == "clear":
            self.state.current_bags.clear()
            self.state.loaded_bags.clear()
            self.console.print("[green]✓ Cleared all bags from workspace[/green]")
        elif args.startswith("add "):
            bag_path = args[4:].strip()
            self._add_bag_to_workspace(bag_path)
        else:
            self.console.print("[red]Unknown bags command. Use: list, add <path>, clear[/red]")
    
    def handle_topics(self, args: str):
        """Handle topic operations"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /bags to add bag files first.[/yellow]")
            return
        
        self._show_topics_interactive()
    
    def handle_help(self, args: str):
        """Show detailed help"""
        self._show_detailed_help()
    
    def handle_clear(self, args: str):
        """Clear console"""
        self.console.clear()
        self.runner._show_welcome()
    
    def handle_save(self, args: str):
        """Save current session"""
        if not args:
            args = f"session_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        session_file = self.rose_dirs.get_config_file(args)
        try:
            with open(session_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2, default=str)
            self.console.print(f"[green]✓ Session saved to: {session_file}[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to save session: {e}[/red]")
    
    def handle_load_session(self, args: str):
        """Load saved session"""
        if not args:
            # List available sessions
            config_dir = self.rose_dirs.config_dir
            session_files = list(config_dir.glob("session_*.json"))
            
            if not session_files:
                self.console.print("[yellow]No saved sessions found[/yellow]")
                return
            
            choices = [Choice(value=str(f), name=f.name) for f in session_files]
            selected = inquirer.select(
                message="Select session to load:",
                choices=choices
            ).execute()
            
            if not selected:
                return
            
            args = selected
        
        try:
            session_file = Path(args)
            if not session_file.exists():
                session_file = self.rose_dirs.get_config_file(args)
            
            with open(session_file, 'r') as f:
                state_data = json.load(f)
            
            # Restore state by updating current state attributes
            for key, value in state_data.items():
                if hasattr(self.runner.state, key):
                    setattr(self.runner.state, key, value)
            self.state = self.runner.state  # Update reference
            
            self.console.print(f"[green]✓ Session loaded from: {session_file}[/green]")
            self._show_status_summary()
            
        except Exception as e:
            self.console.print(f"[red]Failed to load session: {e}[/red]")
    
    def handle_export(self, args: str):
        """Handle export operations"""
        if not args:
            self.console.print("[yellow]Specify export type: notes, session, results[/yellow]")
            return
        
        export_type = args.split()[0]
        output_file = args.split()[1] if len(args.split()) > 1 else None
        
        if export_type == "notes":
            self._export_notes(output_file)
        elif export_type == "session":
            self._export_session(output_file)
        elif export_type == "results":
            self._export_results(output_file)
        else:
            self.console.print(f"[red]Unknown export type: {export_type}[/red]")
    
    def handle_exit(self, args: str):
        """Handle exit command"""
        if self.running_tasks:
            self.console.print(f"[yellow]Warning: {len(self.running_tasks)} tasks still running[/yellow]")
            if not confirm("Exit anyway?"):
                return
        
        self.console.print("[cyan]Goodbye! Your session has been auto-saved.[/cyan]")
        
        # Auto-save session
        try:
            auto_save_file = self.rose_dirs.get_config_file("last_session.json")
            with open(auto_save_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2, default=str)
        except Exception as e:
            from ...core.util import get_logger
            logger = get_logger("run")
            logger.warning(f"Failed to auto-save session: {e}")
        
        raise typer.Exit(0)
    
    # =============================================================================
    # Operation Handlers
    # =============================================================================
    
    def _run_load_operation(self, args: List[str]):
        """Handle load operation in background"""
        if not args:
            # Interactive file selection
            bag_path = self._select_bag_file()
            if not bag_path:
                return
        else:
            bag_path = args[0]
        
        if not Path(bag_path).exists():
            self.console.print(f"[red]Bag file not found: {bag_path}[/red]")
            return
        
        task_id = f"load_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'load',
            {'bag_path': bag_path, 'build_index': True},
            self.runner._on_load_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started loading {Path(bag_path).name} in background (task: {task_id})[/cyan]")
    
    def _run_extract_operation(self, args: List[str]):
        """Handle extract operation in background"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Interactive parameter collection
        topics = self._select_topics_for_operation("extract")
        if not topics:
            return
        
        output_path = inquirer.text(
            message="Output file pattern:",
            default="{input}_extracted_{timestamp}.bag"
        ).execute()
        
        if not output_path:
            return
        
        task_id = f"extract_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'extract',
            {
                'bags': self.state.current_bags.copy(),
                'topics': topics,
                'output_pattern': output_path
            },
            self.runner._on_extract_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started extracting {len(topics)} topics from {len(self.state.current_bags)} bags (task: {task_id})[/cyan]")
    
    def _run_inspect_operation(self, args: List[str]):
        """Handle inspect operation"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Select bag to inspect
        if len(self.state.current_bags) == 1:
            bag_path = self.state.current_bags[0]
        else:
            choices = [Choice(value=bag, name=Path(bag).name) for bag in self.state.current_bags]
            bag_path = inquirer.select(
                message="Select bag to inspect:",
                choices=choices
            ).execute()
            
            if not bag_path:
                return
        
        task_id = f"inspect_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'inspect',
            {'bag_path': bag_path, 'verbose': True},
            self.runner._on_inspect_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started inspecting {Path(bag_path).name} (task: {task_id})[/cyan]")
    
    def _run_compress_operation(self, args: List[str]):
        """Handle compress operation in background"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Select compression type
        compression = inquirer.select(
            message="Select compression type:",
            choices=[
                Choice(value="lz4", name="LZ4 (fast, good compression)"),
                Choice(value="bz2", name="BZ2 (slower, better compression)")
            ]
        ).execute()
        
        if not compression:
            return
        
        task_id = f"compress_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'compress',
            {
                'bags': self.state.current_bags.copy(),
                'compression': compression,
                'output_pattern': "{input}_{compression}_{timestamp}.bag"
            },
            self.runner._on_compress_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started compressing {len(self.state.current_bags)} bags with {compression} (task: {task_id})[/cyan]")
    
    def _run_data_operation(self, args: List[str]):
        """Handle data export operation"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded. Use /run load <bag_path> first.[/yellow]")
            return
        
        # Interactive data export configuration
        topics = self._select_topics_for_operation("export")
        if not topics:
            return
        
        output_path = inquirer.text(
            message="Output CSV file:",
            default="bag_data_{timestamp}.csv"
        ).execute()
        
        if not output_path:
            return
        
        task_id = f"data_{self.runner.task_counter}"
        self.runner.task_counter += 1
        
        # Add to task queue
        self.runner.task_queue.put((
            task_id,
            'data',
            {
                'bags': self.state.current_bags.copy(),
                'topics': topics,
                'output_path': output_path
            },
            self.runner._on_data_complete
        ))
        
        self.console.print(f"[cyan]🔄 Started exporting data for {len(topics)} topics (task: {task_id})[/cyan]")
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def _analyze_query_and_suggest(self, query: str) -> List[Dict[str, str]]:
        """Analyze user query and suggest relevant commands"""
        query_lower = query.lower()
        suggestions = []
        
        # Bag file operations
        if any(word in query_lower for word in ['load', 'open', 'bag', 'file']):
            suggestions.append({
                'description': 'Load a bag file into workspace',
                'command': '/run load',
                'example': '/run load data.bag'
            })
        
        if any(word in query_lower for word in ['extract', 'filter', 'topic']):
            suggestions.append({
                'description': 'Extract specific topics from bags',
                'command': '/run extract',
                'example': 'Will prompt for topics and output settings'
            })
        
        if any(word in query_lower for word in ['inspect', 'analyze', 'info', 'statistics']):
            suggestions.append({
                'description': 'Inspect bag file contents and statistics',
                'command': '/run inspect',
                'example': 'Shows detailed bag analysis'
            })
        
        if any(word in query_lower for word in ['compress', 'shrink', 'reduce']):
            suggestions.append({
                'description': 'Compress bag files to reduce size',
                'command': '/run compress',
                'example': 'Will prompt for compression type'
            })
        
        if any(word in query_lower for word in ['export', 'csv', 'data']):
            suggestions.append({
                'description': 'Export bag data to CSV format',
                'command': '/run data',
                'example': 'Will prompt for topics and export settings'
            })
        
        # Session operations
        if any(word in query_lower for word in ['status', 'running', 'task']):
            suggestions.append({
                'description': 'Show current workspace status and running tasks',
                'command': '/status',
                'example': 'Shows loaded bags, selected topics, and task status'
            })
        
        if any(word in query_lower for word in ['note', 'remember', 'write']):
            suggestions.append({
                'description': 'Add a note to current session',
                'command': '/note',
                'example': '/note Remember to check GPS data quality'
            })
        
        # If no specific suggestions, provide general help
        if not suggestions:
            suggestions.append({
                'description': 'Show all available commands',
                'command': '/help',
                'example': 'Lists all slash commands and their usage'
            })
        
        return suggestions[:3]  # Limit to top 3 suggestions
    
    def _show_status_summary(self):
        """Show concise status summary"""
        status = Text()
        status.append("Current Status:\n", style="bold")
        
        # Workspace info
        status.append(f"📁 Workspace: {os.path.basename(self.state.workspace_path)}\n", style="dim")
        
        # Bags info
        if self.state.current_bags:
            status.append(f"📦 Bags: {len(self.state.current_bags)} loaded", style="green")
            if len(self.state.current_bags) <= 3:
                bag_names = [Path(bag).name for bag in self.state.current_bags]
                status.append(f" ({', '.join(bag_names)})", style="dim")
            status.append("\n")
        else:
            status.append("📦 Bags: None loaded\n", style="yellow")
        
        # Topics info
        if self.state.selected_topics:
            status.append(f"🏷️  Topics: {len(self.state.selected_topics)} selected", style="green")
            if len(self.state.selected_topics) <= 3:
                status.append(f" ({', '.join(self.state.selected_topics)})", style="dim")
            status.append("\n")
        
        # Tasks info
        if self.running_tasks:
            status.append(f"⚡ Tasks: {len(self.running_tasks)} running\n", style="cyan")
        
        # Notes info
        if self.state.notes:
            status.append(f"📝 Notes: {len(self.state.notes)} saved\n", style="blue")
        
        panel = Panel(status, title="Workspace Status", border_style=get_color('primary'))
        self.console.print(panel)
    
    def _show_run_help(self):
        """Show help for /run command with actual CLI command support"""
        help_text = """[bold]Available /run operations:[/bold]

[cyan]/run load [patterns][/cyan]      - Load bag files (supports glob: *.bag, regex patterns)
[cyan]/run extract[/cyan]              - Extract specific topics from bags (interactive selection)
[cyan]/run inspect topics[/cyan]       - Show topic information and statistics
[cyan]/run inspect info[/cyan]         - Show comprehensive bag file information  
[cyan]/run inspect timeline[/cyan]     - Show message timeline and frequency
[cyan]/run compress[/cyan]             - Compress bags with bz2/lz4 (interactive options)
[cyan]/run data export[/cyan]          - Export topic data to CSV/JSON
[cyan]/run data convert[/cyan]         - Convert between data formats
[cyan]/run cache clear[/cyan]          - Clear analysis cache
[cyan]/run cache info[/cyan]           - Show cache statistics
[cyan]/run cache list[/cyan]           - List cached bag files
[cyan]/run plugin list[/cyan]          - List available plugins
[cyan]/run plugin info <name>[/cyan]   - Show plugin information
[cyan]/run plugin run <name>[/cyan]    - Execute plugin on loaded bags

[bold]Examples:[/bold]
  /run load *.bag                      # Load all bags in directory
  /run extract                         # Interactive topic extraction
  /run inspect topics                  # Show topic details
  /run data export                     # Export to CSV with interactive options

All operations use interactive prompts for parameter collection.
"""
        self.console.print(Markdown(help_text))
    
    def _show_detailed_help(self):
        """Show comprehensive help"""
        help_content = """# Rose Interactive Environment Help

## Core Commands

### Navigation & Status
- `/status` - Show workspace status, running tasks, and recent operations
- `/workspace info` - Show detailed workspace information  
- `/workspace cd <path>` - Change workspace directory
- `/clear` - Clear console and show welcome message

### Bag File Management
- `/bags` - Interactive bag file management
- `/bags list` - List currently loaded bags
- `/bags add <path>` - Add bag file to workspace
- `/bags clear` - Remove all bags from workspace

### Topic Operations  
- `/topics` - Interactive topic selection and management
- `/run extract` - Extract selected topics from bags
- `/run data` - Export topic data to CSV format

### Background Operations
- `/run load <bag>` - Load bag file into cache (background)
- `/run inspect` - Analyze bag contents (background)
- `/run compress` - Compress bag files (background)
- `/cancel [task_id]` - Cancel running tasks
- `/undo` - Undo last operation

### Session Management
- `/note <text>` - Add note to current session
- `/notes` - Show all session notes
- `/save [filename]` - Save current session
- `/load [filename]` - Load saved session
- `/export <type>` - Export notes/session/results

### Help & Exit
- `/help` - Show this help message
- `/ask <question>` - Get contextual help and suggestions
- `/exit` or `/quit` - Exit interactive mode

## Special Symbols

### @ Symbol - Bag File References
- `@<bag_name>` - Reference cached bag files by name
- Examples: `@test.bag`, `@demo3_filtered_20250901_233347`
- Automatically resolves to full path of cached bag files
- Works with both full filename and stem (without extension)

### ! Symbol - Native Shell Commands
- `!<command>` - Execute native bash/shell commands
- Examples: `!ls -la`, `!pwd`, `!find . -name "*.bag"`
- Runs in current working directory
- Shows command output and exit codes

## Usage Tips

1. **Natural Questions**: Just type your question without /ask
2. **Background Tasks**: Long operations run in background, you can continue working
3. **Context Aware**: Commands adapt based on current workspace state
4. **File References**: Use @symbol for cached bags, !commands for shell operations
4. **Undo Support**: Most operations can be undone with /undo
5. **Auto-complete**: Use Tab for command and file completion

## Examples

```
> load my_data.bag
> What topics are in this bag?
> /run extract  
> /note GPS data looks good
> /status
```
"""
        
        self.console.print(Markdown(help_content))
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def _select_bag_file(self) -> Optional[str]:
        """Interactive bag file selection"""
        # Look for bag files in current directory
        current_dir = Path('.')
        bag_files = list(current_dir.glob('*.bag'))
        
        if not bag_files:
            # Ask user for file path
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag')
            ).execute()
            return bag_path
        
        # Show available files
        choices = [Choice(value=str(bag), name=f"{bag.name} ({bag.stat().st_size // (1024*1024)} MB)") 
                  for bag in bag_files]
        choices.append(Choice(value="browse", name="Browse for other file..."))
        
        selected = inquirer.select(
            message="Select bag file:",
            choices=choices
        ).execute()
        
        if selected == "browse":
            bag_path = inquirer.filepath(
                message="Enter bag file path:",
                validate=lambda path: Path(path).exists() and path.endswith('.bag')
            ).execute()
            return bag_path
        
        return selected
    
    def _select_topics_for_operation(self, operation: str) -> Optional[List[str]]:
        """Interactive topic selection for operations"""
        if not self.state.current_bags:
            return None
        
        # Get all available topics from loaded bags
        all_topics = set()
        for bag_path in self.state.current_bags:
            if bag_path in self.state.loaded_bags:
                bag_info = self.state.loaded_bags[bag_path]
                bag_topics = bag_info.get('topics', [])
                all_topics.update(bag_topics)
        
        if not all_topics:
            self.console.print("[yellow]No topics available. Load bags first.[/yellow]")
            return None
        
        topics_list = sorted(list(all_topics))
        
        # Use fuzzy selector
        from ..util import ask_topics_with_fuzzy
        
        selected_topics = ask_topics_with_fuzzy(
            console=self.console,
            topics=topics_list,
            message=f"Select topics for {operation}:",
            require_selection=True,
            show_instructions=True
        )
        
        if selected_topics:
            self.state.selected_topics = selected_topics
        
        return selected_topics
    
    def _show_bags_interactive(self):
        """Interactive bag management interface"""
        while True:
            action = inquirer.select(
                message="Bag Management:",
                choices=[
                    Choice(value="list", name="1. List loaded bags"),
                    Choice(value="add", name="2. Add bag file"),
                    Choice(value="remove", name="3. Remove bag file"),
                    Choice(value="clear", name="4. Clear all bags"),
                    Choice(value="back", name="5. Back")
                ]
            ).execute()
            
            if action == "back":
                break
            elif action == "list":
                self._list_current_bags()
            elif action == "add":
                bag_path = self._select_bag_file()
                if bag_path:
                    self._add_bag_to_workspace(bag_path)
            elif action == "remove":
                self._remove_bag_interactive()
            elif action == "clear":
                if confirm("Clear all bags from workspace?"):
                    self.state.current_bags.clear()
                    self.state.loaded_bags.clear()
                    self.console.print("[green]✓ Cleared all bags[/green]")
    
    def _show_topics_interactive(self):
        """Interactive topic management interface"""
        # Get all available topics
        all_topics = set()
        for bag_path in self.state.current_bags:
            if bag_path in self.state.loaded_bags:
                bag_info = self.state.loaded_bags[bag_path]
                bag_topics = bag_info.get('topics', [])
                all_topics.update(bag_topics)
        
        if not all_topics:
            self.console.print("[yellow]No topics available. Load bags first.[/yellow]")
            return
        
        topics_list = sorted(list(all_topics))
        
        action = inquirer.select(
            message="Topic Operations:",
            choices=[
                Choice(value="select", name="1. Select topics for operations"),
                Choice(value="show", name="2. Show selected topics"),
                Choice(value="clear", name="3. Clear topic selection"),
                Choice(value="back", name="4. Back")
            ]
        ).execute()
        
        if action == "select":
            selected = self._select_topics_for_operation("selection")
            if selected:
                self.console.print(f"[green]✓ Selected {len(selected)} topics[/green]")
        elif action == "show":
            if self.state.selected_topics:
                self.console.print("[bold]Selected Topics:[/bold]")
                for topic in self.state.selected_topics:
                    self.console.print(f"  • {topic}")
            else:
                self.console.print("[yellow]No topics selected[/yellow]")
        elif action == "clear":
            self.state.selected_topics.clear()
            self.console.print("[green]✓ Cleared topic selection[/green]")
    
    def _list_current_bags(self):
        """List currently loaded bags"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags loaded in workspace[/yellow]")
            return
        
        self.console.print("\n[bold]Loaded Bags:[/bold]")
        
        for i, bag_path in enumerate(self.state.current_bags, 1):
            bag_name = Path(bag_path).name
            
            if bag_path in self.state.loaded_bags:
                bag_info = self.state.loaded_bags[bag_path]
                status = "[green]✓ Cached[/green]"
                topics_count = len(bag_info.get('topics', []))
                size_mb = bag_info.get('file_size_mb', 0)
                size_str = f"{size_mb:.1f} MB"
                
                self.console.print(
                    f"  {i:2d}. [cyan]{bag_name}[/cyan] - {status} "
                    f"({topics_count} topics, {size_str})"
                )
            else:
                status = "[yellow]⏳ Loading...[/yellow]"
                self.console.print(
                    f"  {i:2d}. [cyan]{bag_name}[/cyan] - {status}"
                )
    
    def _add_bag_to_workspace(self, bag_path: str):
        """Add bag file to workspace"""
        if bag_path in self.state.current_bags:
            self.console.print(f"[yellow]Bag already in workspace: {Path(bag_path).name}[/yellow]")
            return
        
        self.state.current_bags.append(bag_path)
        self.console.print(f"[green]✓ Added bag to workspace: {Path(bag_path).name}[/green]")
        
        # Suggest loading if not cached
        cached_entry = self.cache_manager.get_analysis(Path(bag_path))
        if not cached_entry or not cached_entry.is_valid(Path(bag_path)):
            self.console.print(f"[cyan]💡 Tip: Use '/run load {bag_path}' to load it into cache[/cyan]")
    
    def _remove_bag_interactive(self):
        """Remove bag file interactively"""
        if not self.state.current_bags:
            self.console.print("[yellow]No bags to remove[/yellow]")
            return
        
        choices = [Choice(value=bag, name=Path(bag).name) for bag in self.state.current_bags]
        
        selected = inquirer.select(
            message="Select bag to remove:",
            choices=choices
        ).execute()
        
        if selected:
            self.state.current_bags.remove(selected)
            if selected in self.state.loaded_bags:
                del self.state.loaded_bags[selected]
            self.console.print(f"[green]✓ Removed bag: {Path(selected).name}[/green]")
    
    def _show_workspace_info(self):
        """Show detailed workspace information"""
        info = Text()
        info.append("Workspace Information:\n\n", style="bold")
        info.append(f"📁 Path: {self.state.workspace_path}\n")
        info.append(f"⏰ Session started: {time.ctime(self.state.created_at)}\n")
        info.append(f"📦 Loaded bags: {len(self.state.current_bags)}\n")
        info.append(f"🏷️  Selected topics: {len(self.state.selected_topics)}\n")
        info.append(f"📝 Notes: {len(self.state.notes)}\n")
        info.append(f"🔄 Task history: {len(self.state.task_history)}\n")
        info.append(f"↩️  Undo levels: {len(self.state.undo_stack)}\n")
        
        panel = Panel(info, title="Workspace", border_style=get_color('accent'))
        self.console.print(panel)
    
    def _change_workspace(self, new_path: str):
        """Change workspace directory"""
        new_path = Path(new_path).expanduser().resolve()
        
        if not new_path.exists():
            self.console.print(f"[red]Directory does not exist: {new_path}[/red]")
            return
        
        if not new_path.is_dir():
            self.console.print(f"[red]Not a directory: {new_path}[/red]")
            return
        
        old_path = self.state.workspace_path
        self.state.workspace_path = str(new_path)
        os.chdir(new_path)
        
        self.console.print(f"[green]✓ Changed workspace: {old_path} → {new_path}[/green]")
    
    # =============================================================================
    # Export Functions
    # =============================================================================
    
    def _export_notes(self, output_file: Optional[str]):
        """Export session notes"""
        if not self.state.notes:
            self.console.print("[yellow]No notes to export[/yellow]")
            return
        
        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"notes_{timestamp}.md"
        
        try:
            with open(output_file, 'w') as f:
                f.write("# Session Notes\n\n")
                f.write(f"Created: {time.ctime(self.state.created_at)}\n")
                f.write(f"Workspace: {self.state.workspace_path}\n\n")
                
                for note in self.state.notes:
                    f.write(f"- {note}\n")
            
            self.console.print(f"[green]✓ Notes exported to: {output_file}[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to export notes: {e}[/red]")
    
    def _export_session(self, output_file: Optional[str]):
        """Export complete session state"""
        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"session_{timestamp}.json"
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2, default=str)
            
            self.console.print(f"[green]✓ Session exported to: {output_file}[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to export session: {e}[/red]")
    
    def _export_results(self, output_file: Optional[str]):
        """Export task results"""
        if not self.state.task_history:
            self.console.print("[yellow]No task results to export[/yellow]")
            return
        
        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"results_{timestamp}.json"
        
        try:
            from dataclasses import asdict
            results_data = [asdict(task) for task in self.state.task_history]
            with open(output_file, 'w') as f:
                json.dump(results_data, f, indent=2, default=str)
            
            self.console.print(f"[green]✓ Results exported to: {output_file}[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to export results: {e}[/red]")
