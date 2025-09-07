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

from ...core.parser import create_parser
from ...core.cache import create_bag_cache_manager
from ...core.directories import get_rose_directories
from ...core.util import get_logger
from ...ui.common_ui import Message
from ...ui.theme import get_color
from ..util import filter_topics, check_and_load_bag_cache

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
        
        # Command routing - independent commands like CLI
        self.commands = {
            "/ask": self.handle_ask,
            "/load": self.handle_load,
            "/extract": self.handle_extract,
            "/inspect": self.handle_inspect,
            "/compress": self.handle_compress,
            "/data": self.handle_data,
            "/cache": self.handle_cache,
            "/plugin": self.handle_plugin,
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
            "/session": self.handle_load_session,
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
            from .run_cli_adapter import CLIAdapter
            
            logger.debug("Initializing handlers...")
            self.handlers = RunCommandHandlers(self)
            
            logger.debug("Initializing task executor...")
            self.task_executor = TaskExecutor(self)
            
            logger.debug("Initializing session manager...")
            self.session_manager = SessionManager(self)
            
            logger.debug("Initializing CLI adapter...")
            self.cli_adapter = CLIAdapter(self)
            
            logger.debug("Starting background task processor...")
            self._start_task_processor()
            
            logger.debug("All components initialized successfully")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            # Continue with basic functionality
            self.handlers = None
            self.task_executor = None
            self.session_manager = None
            self.cli_adapter = None
    
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
            
            # Create session with safe configuration
            session_kwargs = {
                'multiline': False,  # 关键修复: 单行模式
                'complete_style': 'column'
            }
            
            # Add optional features safely
            try:
                session_kwargs['history'] = FileHistory(str(history_file))
            except Exception as e:
                logger.warning(f"Could not setup history: {e}")
            
            if completer:
                session_kwargs['completer'] = completer
            
            try:
                session_kwargs['auto_suggest'] = AutoSuggestFromHistory()
            except Exception as e:
                logger.warning(f"Could not setup auto-suggest: {e}")
            
            self.session = PromptSession(**session_kwargs)
            logger.debug("Advanced prompt session initialized")
        except Exception as e:
            logger.warning(f"Could not setup advanced prompt features: {e}")
            # Fallback to basic prompt
            self.session = PromptSession()
            logger.debug("Basic prompt session initialized")
    
    def _create_completer(self) -> Optional[Completer]:
        """Create safe completer that won't crash"""
        try:
            # Try enhanced completer first
            from .run_path_completer import EnhancedRoseCompleter
            return EnhancedRoseCompleter(self)
        except Exception as e:
            logger.warning(f"Enhanced completer failed: {e}")
            
            try:
                # Try simple completer
                from .run_simple_completer import create_safe_completer
                return create_safe_completer(self)
            except Exception as e2:
                logger.warning(f"Simple completer failed: {e2}")
                
                try:
                    # Ultimate fallback
                    commands = list(self.commands.keys())
                    return WordCompleter(commands, ignore_case=True)
                except Exception as e3:
                    logger.warning(f"All completers failed: {e3}")
                    return None
    
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
                    self.console.print("\n[cyan]Goodbye![/cyan]")
                    break
        
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            logger.error(f"Interactive runner error: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    def _show_welcome(self):
        """Show welcome message and interface overview"""
        welcome = Text()
        welcome.append("Welcome to Rose Interactive Environment\n\n", style="bold cyan")
        welcome.append("Available commands:\n", style="bold")
        welcome.append("/load [files]       - Load bag files (supports glob patterns, Tab completion)\n", style="dim")
        welcome.append("/extract [args]     - Extract topics from bags (interactive selection)\n", style="dim")
        welcome.append("/inspect            - Inspect bag contents\n", style="dim")
        welcome.append("/compress [args]    - Compress bag files (bz2/lz4 options)\n", style="dim")
        welcome.append("/data [export|info] - Data operations with CSV/JSON export\n", style="dim")
        welcome.append("/cache [export|clear] - Cache management operations\n", style="dim")
        welcome.append("/plugin [list|info|run|enable|disable|reload|install|uninstall|create] - Plugin operations\n", style="dim")
        welcome.append("/status             - Show workspace status\n", style="dim")
        welcome.append("/bags               - Manage loaded bags\n", style="dim")
        welcome.append("/topics             - Manage topic selection\n", style="dim")
        welcome.append("/note <text>        - Add session note\n", style="dim")
        welcome.append("/help               - Show this help\n", style="dim")
        welcome.append("/exit               - Exit interactive mode\n\n", style="dim")
        welcome.append("All commands support Tab completion for files and paths!", style="green")
        
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
    
    def _resolve_at_symbols(self, user_input: str) -> str:
        """Resolve @ symbols to full bag paths"""
        if '@' not in user_input:
            return user_input
        
        try:
            # Get cached bags
            cached_bags = self._get_cached_bags()
            
            # Split input into words and process each one
            words = user_input.split()
            resolved_words = []
            
            for word in words:
                if word.startswith('@'):
                    bag_name = word[1:]  # Remove @ symbol
                    
                    # Find matching bag by name
                    matching_bag = None
                    for bag_path in cached_bags:
                        from pathlib import Path
                        bag_file = Path(bag_path)
                        # Try exact name match, stem match, and case-insensitive matches
                        if (bag_file.name == bag_name or 
                            bag_file.stem == bag_name or
                            bag_file.name.lower() == bag_name.lower() or
                            bag_file.stem.lower() == bag_name.lower()):
                            matching_bag = bag_path
                            logger.debug(f"Matched @{bag_name} to {bag_path}")
                            break
                    
                    if matching_bag:
                        resolved_words.append(matching_bag)
                        logger.debug(f"Resolved @{bag_name} to {matching_bag}")
                    else:
                        # Keep original if no match found
                        resolved_words.append(word)
                        logger.warning(f"Could not resolve @{bag_name} to a cached bag")
                else:
                    resolved_words.append(word)
            
            return ' '.join(resolved_words)
            
        except Exception as e:
            logger.debug(f"Error resolving @ symbols: {e}")
            return user_input  # Return original on error
    
    def _get_cached_bags(self):
        """Get cached bags (same logic as in completer)"""
        try:
            from ...core.cache import get_cache
            cache = get_cache()
            
            cached_bags = []
            if hasattr(cache, 'cache_dir') and cache.cache_dir.exists():
                import pickle
                for cache_file in cache.cache_dir.glob("*.pkl"):
                    try:
                        with open(cache_file, 'rb') as f:
                            cached_data = pickle.load(f)
                        
                        # Extract original bag path with multiple fallback methods
                        bag_path = None
                        
                        # Debug: print what we found
                        logger.debug(f"Processing cache file: {cache_file.name}")
                        logger.debug(f"Cached data type: {type(cached_data)}")
                        
                        if hasattr(cached_data, 'original_path') and cached_data.original_path:
                            bag_path = cached_data.original_path
                            logger.debug(f"Found original_path: {bag_path}")
                        elif hasattr(cached_data, 'bag_info') and cached_data.bag_info:
                            bag_info = cached_data.bag_info
                            if hasattr(bag_info, 'file_path') and bag_info.file_path:
                                bag_path = str(bag_info.file_path)
                                # If it's a relative path, make it absolute
                                if not bag_path.startswith('/'):
                                    bag_path = f"/workspaces/rose/{bag_path}"
                                logger.debug(f"Found bag_info.file_path: {bag_path}")
                            elif hasattr(bag_info, 'file_info'):
                                file_info = bag_info.file_info
                                if isinstance(file_info, dict):
                                    # Try different possible keys
                                    for key in ['path', 'file_path', 'absolute_path', 'name']:
                                        if key in file_info and file_info[key]:
                                            bag_path = file_info[key]
                                            logger.debug(f"Found file_info[{key}]: {bag_path}")
                                            break
                        
                        # If still no path, try to infer from cache filename
                        if not bag_path:
                            # Cache filename might give us a clue
                            cache_stem = cache_file.stem
                            # Look for .bag files that match the cache stem
                            from pathlib import Path
                            possible_paths = [
                                f"{cache_stem}.bag",
                                f"roseApp/tests/{cache_stem}.bag",
                                f"/workspaces/rose/roseApp/tests/{cache_stem}.bag"
                            ]
                            for possible_path in possible_paths:
                                if Path(possible_path).exists():
                                    bag_path = str(Path(possible_path).absolute())
                                    break
                        
                        if bag_path:
                            cached_bags.append(bag_path)
                            logger.debug(f"Found cached bag: {bag_path}")
                            
                    except Exception as e:
                        logger.debug(f"Could not process cache file {cache_file}: {e}")
                        continue
            
            return list(set(cached_bags))
            
        except Exception as e:
            logger.debug(f"Could not get cached bags: {e}")
            return []
    
    def _dispatch_command(self, user_input: str):
        """Dispatch user input to appropriate handler"""
        # Handle native shell commands with ! prefix
        if user_input.startswith('!'):
            self._handle_shell_command(user_input[1:].strip())
            return
        
        # Resolve @ symbols to full paths before processing commands
        resolved_input = self._resolve_at_symbols(user_input)
        
        # Check for slash commands
        for cmd_prefix, handler in self.commands.items():
            if resolved_input.startswith(cmd_prefix):
                args = resolved_input[len(cmd_prefix):].strip()
                try:
                    # Call handler directly (they're all methods of this class)
                    handler(args)
                except Exception as e:
                    self.console.print(f"[red]Command error: {e}[/red]")
                    logger.error(f"Command {cmd_prefix} error: {e}", exc_info=True)
                return
        
        # Default to ask handler for natural language
        self.handle_ask(resolved_input)
    
    def _handle_shell_command(self, command: str):
        """Handle native shell command execution"""
        if not command:
            self.console.print("[yellow]Usage: !<command>[/yellow]")
            self.console.print("[dim]Example: !ls -la[/dim]")
            return
        
        try:
            import subprocess
            import shlex
            
            # Show what command we're executing
            self.console.print(f"[dim]$ {command}[/dim]")
            
            # Execute command in native shell
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=None  # Use current working directory
            )
            
            # Display output
            if result.stdout:
                self.console.print(result.stdout.rstrip())
            
            if result.stderr:
                self.console.print(f"[red]{result.stderr.rstrip()}[/red]")
            
            # Show exit code if non-zero
            if result.returncode != 0:
                self.console.print(f"[red]Command exited with code {result.returncode}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]Shell command error: {e}[/red]")
            logger.error(f"Shell command error: {e}", exc_info=True)
    
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
    
    def handle_load(self, args: str):
        """Handle load command - load bag files"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_load(args.split() if args else [])
            self._show_operation_result('load', result)
        else:
            self.console.print(f"[yellow]Load: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_extract(self, args: str):
        """Handle extract command - extract topics"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_extract(args.split() if args else [])
            self._show_operation_result('extract', result)
        else:
            self.console.print(f"[yellow]Extract: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_inspect(self, args: str):
        """Handle inspect command - inspect bag contents"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_inspect(args.split() if args else [])
            self._show_operation_result('inspect', result)
        else:
            self.console.print(f"[yellow]Inspect: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_compress(self, args: str):
        """Handle compress command - compress bag files"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_compress(args.split() if args else [])
            self._show_operation_result('compress', result)
        else:
            self.console.print(f"[yellow]Compress: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_data(self, args: str):
        """Handle data command - data operations"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_data(args.split() if args else [])
            self._show_operation_result('data', result)
        else:
            self.console.print(f"[yellow]Data: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_cache(self, args: str):
        """Handle cache command - cache management"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_cache(args.split() if args else [])
            self._show_operation_result('cache', result)
        else:
            self.console.print(f"[yellow]Cache: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def handle_plugin(self, args: str):
        """Handle plugin command - plugin operations"""
        if hasattr(self, 'cli_adapter'):
            result = self.cli_adapter.interactive_plugin(args.split() if args else [])
            self._show_operation_result('plugin', result)
        else:
            self.console.print(f"[yellow]Plugin: {args}[/yellow]")
            self.console.print("[dim]CLI adapter not initialized yet[/dim]")
    
    def _show_operation_result(self, operation: str, result: Dict[str, Any]):
        """Display operation result with appropriate formatting"""
        if result.get('success'):
            message = result.get('message', f'{operation.title()} completed successfully')
            self.console.print(f"[green]SUCCESS: {message}[/green]")
        else:
            error = result.get('error', 'Unknown error')
            self.console.print(f"[red]ERROR: {operation.title()} failed: {error}[/red]")
    
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
        self.console.print("[cyan]Goodbye! Session auto-saved.[/cyan]")
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
            self.console.print(f"\n[red]ERROR: Failed to load bag: {result.error}[/red]")
    
    def _on_extract_complete(self, result: TaskResult):
        """Called when extract task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_extract_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]ERROR: Extraction failed: {result.error}[/red]")
    
    def _on_inspect_complete(self, result: TaskResult):
        """Called when inspect task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_inspect_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]ERROR: Inspection failed: {result.error}[/red]")
    
    def _on_compress_complete(self, result: TaskResult):
        """Called when compress task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_compress_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]ERROR: Compression failed: {result.error}[/red]")
    
    def _on_data_complete(self, result: TaskResult):
        """Called when data export task completes"""
        from .run_output import ResultFormatter
        
        if result.result:
            formatted_result = ResultFormatter.format_data_result(result.result)
            self.console.print(f"\n{formatted_result}")
        elif result.status == 'failed':
            self.console.print(f"\n[red]ERROR: Data export failed: {result.error}[/red]")


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