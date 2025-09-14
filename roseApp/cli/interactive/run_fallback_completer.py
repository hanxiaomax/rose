#!/usr/bin/env python3
"""
Fallback completer for Rose interactive environment
Provides basic command and file completion as a safe fallback when enhanced completers fail
"""

from pathlib import Path
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.completion import WordCompleter

from ...core.util import get_logger

logger = get_logger("run_fallback_completer")


class FallbackRoseCompleter(Completer):
    """Fallback completer that won't crash when enhanced completers fail"""
    
    def __init__(self, runner):
        self.runner = runner
        # Pre-define all completions to avoid runtime errors
        self.base_commands = [
            '/ask', '/load', '/extract', '/inspect', '/compress', 
            '/data', '/cache', '/plugin', '/status', '/bags', 
            '/topics', '/note', '/help', '/clear', '/exit', '/quit'
        ]
        
        self.inspect_subcommands = [
            '/inspect topics', '/inspect info', '/inspect timeline'
        ]
        
        self.data_subcommands = [
            '/data export', '/data convert'
        ]
        
        self.cache_subcommands = [
            '/cache clear', '/cache info', '/cache list'
        ]
        
        self.plugin_subcommands = [
            '/plugin list', '/plugin info', '/plugin run'
        ]
        
        # Combine all for simple word completion
        self.all_commands = (self.base_commands + self.inspect_subcommands + 
                           self.data_subcommands + self.cache_subcommands + 
                           self.plugin_subcommands)
    
    def get_completions(self, document, complete_event):
        """Safe completion that won't crash"""
        try:
            text = document.text_before_cursor
            
            if not text:
                return
            
            # Simple approach: complete any matching command
            for cmd in self.all_commands:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            
            # Add bag file completion for load-related commands
            if text.startswith('/load') or 'bag' in text.lower():
                self._safe_complete_bag_files(text, document)
        
        except Exception as e:
            # Log but don't crash
            logger.debug(f"Completion error (safe): {e}")
            return
    
    def _safe_complete_bag_files(self, text, document):
        """Safely complete bag files without crashing"""
        try:
            words = text.split()
            if len(words) >= 2:
                last_word = words[-1]
                
                # Find bag files
                current_dir = Path('.')
                for bag_file in current_dir.glob('*.bag'):
                    bag_name = bag_file.name
                    if bag_name.startswith(last_word):
                        yield Completion(bag_name, start_position=-len(last_word))
                
                # Add common patterns
                patterns = ['*.bag', '**/*.bag']
                for pattern in patterns:
                    if pattern.startswith(last_word):
                        yield Completion(pattern, start_position=-len(last_word))
        
        except Exception as e:
            logger.debug(f"Bag file completion error: {e}")
            return


def create_safe_completer(runner) -> Completer:
    """Create a safe completer that won't cause crashes"""
    try:
        return FallbackRoseCompleter(runner)
    except Exception as e:
        logger.warning(f"Could not create simple completer: {e}")
        # Ultimate fallback - just basic word completion
        try:
            basic_commands = ['/help', '/status', '/exit', '/load', '/extract']
            return WordCompleter(basic_commands, ignore_case=True)
        except Exception:
            # No completer if everything fails
            return None


if __name__ == "__main__":
    pass
