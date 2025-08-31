#!/usr/bin/env python3
"""
Interactive Run command for ROS bag analysis - Claude Code style interface
Provides REPL-style interface with slash commands, session state, and background tasks
"""

import os
import json
import time
import asyncio
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from copy import deepcopy
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.table import Table
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.shortcuts import confirm
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ..core.parser import create_parser
from ..core.cache import create_bag_cache_manager
from ..core.directories import get_rose_directories
from ..core.util import get_logger
from ..ui.common_ui import Message
from ..ui.theme import get_color
from .util import filter_topics, check_and_load_bag_cache

logger = get_logger("run")

app = typer.Typer(name="run", help="Interactive run environment with Claude Code style interface")


# =============================================================================
# Data Models & State Management
# =============================================================================

@dataclass
class TaskResult:
    """Result of a background task execution"""
    task_id: str
    command: str
    status: str  # 'running', 'completed', 'failed', 'cancelled'
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class SessionState:
    """Current session state including workspace, notes, and history"""
    workspace_path: str
    current_bags: List[str]
    loaded_bags: Dict[str, Dict[str, Any]]  # bag_path -> bag_info
    selected_topics: List[str]
    notes: List[str]
    task_history: List[TaskResult]
    undo_stack: List[Dict[str, Any]]
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        return cls(**data)


# =============================================================================
# Interactive Runner Class
# =============================================================================

class InteractiveRunner:
    """Main interactive runner with Claude Code style interface"""
    
    def __init__(self):
        self.console = Console()
        self.rose_dirs = get_rose_directories()
        self.parser = create_parser()
        self.cache_manager = create_bag_cache_manager()
        
        # Session state
        self.state = SessionState(
            workspace_path=os.getcwd(),
            current_bags=[],
            loaded_bags={},
            selected_topics=[],
            notes=[],
            task_history=[],
            undo_stack=[],
            created_at=time.time()
        )
        
        # Background task management
        self.task_queue = queue.Queue()
        self.running_tasks = {}
        self.task_counter = 0
        self._stop_event = threading.Event()
        
        # Command routing
        self.commands = {
            "/ask": self.handle_ask,
            "/run": self.handle_run,
            "/undo": self.handle_undo,
            "/cancel": self.handle_cancel,
            "/status": self.handle_status,
            "/note": self.handle_note,
            "/notes": self.handle_notes,
            "/workspace": self.handle_workspace,
            "/bags": self.handle_bags,
            "/topics": self.handle_topics,
            "/help": self.handle_help,
            "/clear": self.handle_clear,
            "/save": self.handle_save,
            "/load": self.handle_load_session,
            "/export": self.handle_export,
            "/exit": self.handle_exit,
            "/quit": self.handle_exit
        }
        
        # Setup prompt session
        self._setup_prompt_session()
        
        # Initialize components with error handling
        try:
            from .run_handlers import RunCommandHandlers
            from .run_tasks import TaskExecutor
            from .run_session import SessionManager
            
            logger.debug("Initializing handlers...")
            self.handlers = RunCommandHandlers(self)
            
            logger.debug("Initializing task executor...")
            self.task_executor = TaskExecutor(self)
            
            logger.debug("Initializing session manager...")
            self.session_manager = SessionManager(self)
            
            logger.debug("Starting background task processor...")
            self._start_task_processor()
            
            logger.debug("All components initialized successfully")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            # Continue with basic functionality
            self.handlers = None
            self.task_executor = None
            self.session_manager = None
    
    def _setup_prompt_session(self):
        """Setup intelligent prompt session with history and completion"""
        try:
            history_file = self.rose_dirs.get_config_file('run_history.txt')
            
            # Create simple completer to avoid blocking
            try:
                completer = self._create_completer()
            except Exception as e:
                logger.warning(f"Completer creation failed: {e}")
                completer = None
            
            self.session = PromptSession(
                history=FileHistory(str(history_file)),
                completer=completer,
                auto_suggest=AutoSuggestFromHistory(),
                multiline=False,  # 修复: 设置为单行模式
                complete_style='column'  # 简化样式
            )
            logger.debug("Advanced prompt session initialized")
        except Exception as e:
            logger.warning(f"Could not setup advanced prompt features: {e}")
            # Fallback to basic prompt
            self.session = PromptSession()
            logger.debug("Basic prompt session initialized")
    
    def _create_completer(self) -> Completer:
        """Create intelligent completer for commands and context"""
        
        class RoseCompleter(Completer):
            def __init__(self, runner):
                self.runner = runner
                self.base_commands = list(runner.commands.keys())
                self.bag_commands = ['load', 'extract', 'inspect', 'compress', 'data']
                self.common_options = ['--help', '--verbose', '--dry-run', '--output']
            
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                
                # Complete slash commands
                if text.startswith('/'):
                    for cmd in self.base_commands:
                        if cmd.startswith(text):
                            yield Completion(cmd, start_position=-len(text))
                
                # Complete bag operations after /run
                elif text.startswith('/run '):
                    remaining = text[5:].strip()
                    for cmd in self.bag_commands:
                        if cmd.startswith(remaining):
                            yield Completion(cmd, start_position=-len(remaining))
                
                # Complete bag files
                elif 'bag' in text.lower():
                    try:
                        current_dir = Path('.')
                        for bag_file in current_dir.glob('*.bag'):
                            if str(bag_file).startswith(text.split()[-1]):
                                yield Completion(str(bag_file), start_position=-len(text.split()[-1]))
                    except:
                        pass
        
        return RoseCompleter(self)
    
    def _start_task_processor(self):
        """Start background task processor thread"""
        def processor():
            logger.debug("Task processor started")
            while not self._stop_event.is_set():
                try:
                    # Process task queue with timeout to avoid blocking
                    try:
                        task_id, command, args, callback = self.task_queue.get(timeout=0.5)
                        logger.debug(f"Processing task: {task_id} - {command}")
                        
                        # Execute task if executor is available
                        if self.task_executor:
                            self.task_executor.execute_task(task_id, command, args, callback)
                        else:
                            logger.warning(f"Task executor not available for task: {task_id}")
                            
                        self.task_queue.task_done()
                    except queue.Empty:
                        continue
                except Exception as e:
                    logger.error(f"Task processor error: {e}")
                    # Continue processing even if one task fails
            
            logger.debug("Task processor stopped")
        
        try:
            self.task_thread = threading.Thread(target=processor, daemon=True)
            self.task_thread.start()
            logger.debug("Task processor thread started")
        except Exception as e:
            logger.error(f"Failed to start task processor: {e}")
    
    def _execute_task_fallback(self, task_id: str, command: str, args: Dict[str, Any], callback):
        """Fallback task execution for early initialization"""
        try:
            result = TaskResult(
                task_id=task_id,
                command=command,
                status='failed',
                error="Task executor not yet initialized",
                start_time=time.time(),
                end_time=time.time()
            )
            
            if callback:
                callback(result)
                
        except Exception as e:
            logger.error(f"Fallback task execution error: {e}")
    
    def run_interactive(self):
        """Main interactive loop"""
        try:
            self._show_welcome()
            
            while True:
                try:
                    # Show prompt with current context
                    prompt_text = self._get_prompt_text()
                    
                    # Get user input with fallback
                    try:
                        if hasattr(self, 'session') and self.session:
                            user_input = self.session.prompt(prompt_text).strip()
                        else:
                            user_input = input(prompt_text).strip()
                    except Exception as e:
                        logger.warning(f"Prompt error, using basic input: {e}")
                        user_input = input(prompt_text).strip()
                    
                    if not user_input:
                        continue
                    
                    # Save state for undo (with error handling)
                    try:
                        self._save_state_for_undo()
                    except Exception as e:
                        logger.warning(f"Could not save state for undo: {e}")
                    
                    # Dispatch command
                    self._dispatch_command(user_input)
                    
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Use /exit to quit[/yellow]")
                    continue
                except EOFError:
                    self.console.print("\n[cyan]👋 Goodbye![/cyan]")
                    break
        
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            logger.error(f"Interactive runner error: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _show_welcome(self):
        """Show welcome message and interface overview"""
        welcome = Text()
        welcome.append("🌹 Welcome to Rose Interactive Environment\n\n", style="bold cyan")
        welcome.append("Available commands:\n", style="bold")
        welcome.append("/ask <question>     - Ask for help or guidance\n", style="dim")
        welcome.append("/run <operation>    - Execute bag operations in background\n", style="dim")
        welcome.append("/status            - Show running tasks and workspace status\n", style="dim")
        welcome.append("/bags              - Manage loaded bag files\n", style="dim")
        welcome.append("/topics            - Work with topics\n", style="dim")
        welcome.append("/note <text>       - Add a note to current session\n", style="dim")
        welcome.append("/undo              - Undo last operation\n", style="dim")
        welcome.append("/help              - Show detailed help\n", style="dim")
        welcome.append("/exit              - Exit interactive mode\n\n", style="dim")
        welcome.append("💡 Tip: Just type naturally for help, or use slash commands for actions", style="green")
        
        panel = Panel(welcome, title="Rose Interactive", border_style=get_color('primary'))
        self.console.print(panel)
    
    def _get_prompt_text(self) -> str:
        """Generate context-aware prompt"""
        # Build context indicators
        indicators = []
        
        if self.state.current_bags:
            indicators.append(f"{len(self.state.current_bags)} bags")
        
        if self.running_tasks:
            indicators.append(f"{len(self.running_tasks)} running")
        
        if self.state.selected_topics:
            indicators.append(f"{len(self.state.selected_topics)} topics")
        
        context = f"[{', '.join(indicators)}]" if indicators else ""
        
        return f"rose{context}> "
    
    def _dispatch_command(self, user_input: str):
        """Dispatch user input to appropriate handler"""
        # Check for slash commands
        for cmd_prefix, handler in self.commands.items():
            if user_input.startswith(cmd_prefix):
                args = user_input[len(cmd_prefix):].strip()
                try:
                    # Call handler directly (they're all methods of this class)
                    handler(args)
                except Exception as e:
                    self.console.print(f"[red]Command error: {e}[/red]")
                    logger.error(f"Command {cmd_prefix} error: {e}", exc_info=True)
                return
        
        # Default to ask handler for natural language
        self.handle_ask(user_input)
    
    # =============================================================================
    # Command Handler Stubs (delegated to handlers)
    # =============================================================================
    
    def handle_ask(self, query: str):
        """Handle ask command - natural language queries"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_ask(query)
        else:
            self.console.print(f"[yellow]You asked: {query}[/yellow]")
            self.console.print("[dim]Handlers not initialized yet[/dim]")
    
    def handle_run(self, operation: str):
        """Handle run command - execute operations"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_run(operation)
        else:
            self.console.print(f"[yellow]Run operation: {operation}[/yellow]")
            self.console.print("[dim]Handlers not initialized yet[/dim]")
    
    def handle_undo(self, args: str):
        """Handle undo command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_undo(args)
        else:
            self.console.print("[yellow]Undo not available yet[/yellow]")
    
    def handle_cancel(self, args: str):
        """Handle cancel command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_cancel(args)
        else:
            self.console.print("[yellow]Cancel not available yet[/yellow]")
    
    def handle_status(self, args: str):
        """Handle status command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_status(args)
        else:
            self.console.print("[yellow]Status: Interactive environment running[/yellow]")
    
    def handle_note(self, note_text: str):
        """Handle note command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_note(note_text)
        else:
            self.console.print(f"[yellow]Note: {note_text}[/yellow]")
    
    def handle_notes(self, args: str):
        """Handle notes command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_notes(args)
        else:
            self.console.print("[yellow]Notes management not available yet[/yellow]")
    
    def handle_workspace(self, args: str):
        """Handle workspace command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_workspace(args)
        else:
            self.console.print("[yellow]Workspace management not available yet[/yellow]")
    
    def handle_bags(self, args: str):
        """Handle bags command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_bags(args)
        else:
            self.console.print("[yellow]Bag management not available yet[/yellow]")
    
    def handle_topics(self, args: str):
        """Handle topics command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_topics(args)
        else:
            self.console.print("[yellow]Topic management not available yet[/yellow]")
    
    def handle_help(self, args: str):
        """Handle help command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_help(args)
        else:
            self._show_welcome()
    
    def handle_clear(self, args: str):
        """Handle clear command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_clear(args)
        else:
            self.console.clear()
    
    def handle_save(self, args: str):
        """Handle save command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_save(args)
        else:
            self.console.print("[yellow]Session save not available yet[/yellow]")
    
    def handle_load_session(self, args: str):
        """Handle load session command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_load_session(args)
        else:
            self.console.print("[yellow]Session load not available yet[/yellow]")
    
    def handle_export(self, args: str):
        """Handle export command"""
        if hasattr(self, 'handlers'):
            self.handlers.handle_export(args)
        else:
            self.console.print("[yellow]Export not available yet[/yellow]")
    
    def handle_exit(self, args: str):
        """Handle exit command - quit the interactive environment"""
        self.console.print("[cyan]👋 Goodbye! Session auto-saved.[/cyan]")
        try:
            self._cleanup()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        
        # Force exit with multiple methods
        try:
            raise EOFError  # This will exit the REPL loop
        except:
            # If EOFError doesn't work, force exit
            import os
            os._exit(0)
    
    def _save_state_for_undo(self, operation: str = "operation"):
        """Save current state for undo functionality"""
        if hasattr(self, 'session_manager'):
            self.session_manager.create_snapshot(operation)
        else:
            # Fallback to old method during initialization
            if len(self.state.undo_stack) >= 10:
                self.state.undo_stack.pop(0)
            
            snapshot = {
                'current_bags': self.state.current_bags.copy(),
                'selected_topics': self.state.selected_topics.copy(),
                'timestamp': time.time()
            }
            self.state.undo_stack.append(snapshot)
    
    def _cleanup(self):
        """Cleanup resources"""
        # Auto-save session before cleanup
        if hasattr(self, 'session_manager'):
            self.session_manager.auto_save_session()
        
        self._stop_event.set()
        if hasattr(self, 'task_thread'):
            self.task_thread.join(timeout=1.0)
    
    # =============================================================================
    # Task Completion Callbacks
    # =============================================================================
    
    def _on_load_complete(self, result: TaskResult):
        """Called when load task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_load_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]❌ Failed to load bag: {result.error}[/red]")
    
    def _on_extract_complete(self, result: TaskResult):
        """Called when extract task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_extract_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]❌ Extraction failed: {result.error}[/red]")
    
    def _on_inspect_complete(self, result: TaskResult):
        """Called when inspect task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_inspect_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]❌ Inspection failed: {result.error}[/red]")
    
    def _on_compress_complete(self, result: TaskResult):
        """Called when compress task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_compress_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]❌ Compression failed: {result.error}[/red]")
    
    def _on_data_complete(self, result: TaskResult):
        """Called when data export task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_data_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]❌ Data export failed: {result.error}[/red]")


# =============================================================================
# Typer Command Interface
# =============================================================================

@app.command()
def interactive():
    """
    Start interactive Claude Code style environment for ROS bag operations
    
    This mode provides:
    - REPL interface with slash commands (/ask, /run, /status, etc.)
    - Background task execution with real-time feedback
    - Session state management with undo/redo support
    - Intelligent auto-completion and command suggestions
    - Context-aware help and guidance
    - Workspace management with notes and export capabilities
    
    Key Features:
    - Natural language queries: Just ask questions directly
    - Slash commands: /run load, /run extract, /status, /note, etc.
    - Background processing: Long operations don't block the interface
    - Smart completion: Tab-completion for commands, files, and topics
    - Session persistence: Save and restore your work sessions
    
    Examples:
        > /run load data.bag
        > What topics are available in this bag?
        > /run extract  
        > /note GPS data quality looks good
        > /status
        > /save my_analysis_session
    """
    runner = InteractiveRunner()
    runner.run_interactive()


# Make interactive the default command
app.command(name="")(interactive)


if __name__ == "__main__":
    app()