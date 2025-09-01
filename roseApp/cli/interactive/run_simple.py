#!/usr/bin/env python3
"""
Simplified Rose Interactive Run Environment
Minimal version without complex dependencies for debugging
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ...core.util import get_logger
from ...core.directories import get_rose_directories
from ...ui.theme import get_color

logger = get_logger("run_simple")
app = typer.Typer(help="Rose Interactive Run Environment (Simple)")


@dataclass
class SimpleSessionState:
    """Simplified session state"""
    workspace_path: str = field(default_factory=lambda: str(Path.cwd()))
    current_bags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class SimpleInteractiveRunner:
    """Simplified interactive runner for debugging"""
    
    def __init__(self):
        self.console = Console()
        self.state = SimpleSessionState()
        self.rose_dirs = get_rose_directories()
        
        # Simple command mapping
        self.commands = {
            '/help': self.handle_help,
            '/status': self.handle_status,
            '/note': self.handle_note,
            '/clear': self.handle_clear,
            '/exit': self.handle_exit,
            '/quit': self.handle_exit,
        }
        
        logger.debug("Simple runner initialized")
    
    def run_interactive(self):
        """Run simplified interactive environment"""
        self._show_welcome()
        
        try:
            while True:
                try:
                    # Simple input without prompt_toolkit
                    prompt_text = self._get_simple_prompt()
                    user_input = input(prompt_text).strip()
                    
                    if not user_input:
                        continue
                    
                    # Dispatch command
                    self._dispatch_command(user_input)
                    
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Use /exit to quit[/yellow]")
                    continue
                except EOFError:
                    self.console.print("\n[cyan]👋 Goodbye![/cyan]")
                    break
                    
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            logger.error(f"Interactive error: {e}", exc_info=True)
    
    def _show_welcome(self):
        """Show simplified welcome message"""
        welcome = Text()
        welcome.append("🌹 Rose Interactive Environment (Simple Mode)\n\n", style="bold cyan")
        welcome.append("Available commands:\n", style="bold")
        welcome.append("/help     - Show this help\n", style="dim")
        welcome.append("/status   - Show current status\n", style="dim")
        welcome.append("/note     - Add a note\n", style="dim")
        welcome.append("/clear    - Clear screen\n", style="dim")
        welcome.append("/exit     - Exit interactive mode\n\n", style="dim")
        welcome.append("💡 Type any command to test functionality", style="green")
        
        panel = Panel(welcome, title="Rose Interactive (Simple)", border_style=get_color('primary'))
        self.console.print(panel)
    
    def _get_simple_prompt(self) -> str:
        """Generate simple prompt"""
        context = ""
        if self.state.current_bags:
            context = f"[{len(self.state.current_bags)} bags]"
        
        return f"rose{context}> "
    
    def _dispatch_command(self, user_input: str):
        """Dispatch user input to appropriate handler"""
        # Check for slash commands
        for cmd_prefix, handler in self.commands.items():
            if user_input.startswith(cmd_prefix):
                args = user_input[len(cmd_prefix):].strip()
                try:
                    handler(args)
                except Exception as e:
                    self.console.print(f"[red]Command error: {e}[/red]")
                    logger.error(f"Command {cmd_prefix} error: {e}", exc_info=True)
                return
        
        # Default response for natural language
        self.console.print(f"[yellow]You said: '{user_input}'[/yellow]")
        self.console.print("[dim]This is simple mode. Try /help for available commands.[/dim]")
    
    # Command handlers
    def handle_help(self, args: str):
        """Show help information"""
        self._show_welcome()
    
    def handle_status(self, args: str):
        """Show current status"""
        self.console.print("[bold]Current Status:[/bold]")
        self.console.print(f"Workspace: {self.state.workspace_path}")
        self.console.print(f"Bags loaded: {len(self.state.current_bags)}")
        self.console.print(f"Notes: {len(self.state.notes)}")
        self.console.print(f"Session age: {time.time() - self.state.created_at:.1f}s")
        
        if self.state.current_bags:
            self.console.print("\nLoaded bags:")
            for bag in self.state.current_bags:
                self.console.print(f"  • {Path(bag).name}")
        
        if self.state.notes:
            self.console.print("\nNotes:")
            for i, note in enumerate(self.state.notes[-5:], 1):
                self.console.print(f"  {i}. {note}")
    
    def handle_note(self, note_text: str):
        """Add a note"""
        if not note_text:
            note_text = input("Enter note: ").strip()
        
        if note_text:
            self.state.notes.append(note_text)
            self.console.print(f"[green]✓ Note added: {note_text}[/green]")
        else:
            self.console.print("[yellow]No note text provided[/yellow]")
    
    def handle_clear(self, args: str):
        """Clear screen"""
        self.console.clear()
        self._show_welcome()
    
    def handle_exit(self, args: str):
        """Exit interactive mode"""
        self.console.print("[cyan]👋 Goodbye! Simple mode exiting...[/cyan]")
        # Force exit
        sys.exit(0)


@app.command()
def simple():
    """
    Start simplified interactive environment for debugging
    """
    runner = SimpleInteractiveRunner()
    runner.run_interactive()


@app.command()
def debug():
    """
    Debug the interactive environment step by step
    """
    print("🔧 Rose Interactive Debug Mode")
    print("=" * 40)
    
    try:
        print("Testing simple interactive...")
        runner = SimpleInteractiveRunner()
        
        print("✅ Simple runner created successfully")
        print("Starting interactive mode...")
        
        runner.run_interactive()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


# Make simple the default command
app.command(name="")(simple)


if __name__ == "__main__":
    app()
