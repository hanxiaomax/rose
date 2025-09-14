#!/usr/bin/env python3
"""
Enhanced path completion for Rose interactive environment
Provides intelligent file and directory completion for all input fields
"""

import os
import glob
from pathlib import Path
from typing import List, Optional, Iterator
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ...core.util import get_logger

logger = get_logger("run_path_completer")


class BagFileCompleter(Completer):
    """Custom completer for bag files with path completion"""
    
    def get_completions(self, document: Document, complete_event):
        """Generate completions for bag files"""
        try:
            text = document.text_before_cursor
            
            # Handle different completion scenarios
            if not text:
                # Show common patterns and files in current directory
                completions = ['*.bag', '**/*.bag', 'roseApp/tests/*.bag']
                # Add actual bag files in current directory
                for bag_file in Path('.').glob('*.bag'):
                    completions.append(str(bag_file))
                # Add bag files from common directories
                for bag_file in Path('.').glob('**/test*.bag'):
                    completions.append(str(bag_file))
            else:
                # Get matches based on current input
                completions = self._get_path_completions(text)
            
            for completion in completions:
                yield Completion(
                    text=completion,
                    start_position=-len(text),
                    display=completion
                )
                
        except Exception as e:
            logger.debug(f"Completion error: {e}")
    
    def _get_path_completions(self, text: str) -> List[str]:
        """Get path completions for the given text"""
        completions = []
        
        try:
            # If text contains wildcards, try to expand glob
            if '*' in text or '?' in text:
                try:
                    # Try exact glob match first
                    matches = glob.glob(text)
                    bag_matches = [m for m in matches if m.endswith('.bag')]
                    completions.extend(bag_matches)
                    
                    # Also try adding wildcard for partial patterns
                    if not text.endswith('*'):
                        extended_matches = glob.glob(text + '*')
                        bag_extended = [m for m in extended_matches if m.endswith('.bag') or os.path.isdir(m)]
                        completions.extend(bag_extended)
                except:
                    pass
            
            # Try directory and file completion
            path_obj = Path(text)
            
            if text.endswith('/'):
                # User typed a directory path ending with /
                search_dir = Path(text.rstrip('/'))
                if search_dir.exists() and search_dir.is_dir():
                    for item in search_dir.glob('*'):
                        if item.is_file() and item.suffix == '.bag':
                            completions.append(str(item))
                        elif item.is_dir():
                            completions.append(str(item) + '/')
            elif path_obj.exists() and path_obj.is_dir():
                # Existing directory without trailing slash
                for item in path_obj.glob('*'):
                    if item.is_file() and item.suffix == '.bag':
                        completions.append(str(item))
                    elif item.is_dir():
                        completions.append(str(item) + '/')
            else:
                # Partial filename/path completion
                parent_dir = path_obj.parent if path_obj.parent != path_obj else Path('.')
                name_start = path_obj.name
                
                # Complete files and directories
                if parent_dir.exists():
                    for item in parent_dir.glob(name_start + '*'):
                        if item.is_file() and item.suffix == '.bag':
                            completions.append(str(item))
                        elif item.is_dir():
                            completions.append(str(item) + '/')
                
                # Add pattern suggestions for common paths
                if text.startswith('r') and not completions:
                    completions.append('roseApp/tests/*.bag')
                elif not text and not completions:
                    completions.extend(['*.bag', '**/*.bag', 'roseApp/tests/*.bag'])
            
        except Exception as e:
            logger.debug(f"Path completion error: {e}")
        
        return list(set(completions))  # Remove duplicates


class PathCompleter:
    """Enhanced path completion utilities"""
    
    @staticmethod
    def complete_bag_files(partial_path: str = "", include_patterns: bool = True) -> List[str]:
        """Complete bag file paths with glob pattern support"""
        try:
            if not partial_path:
                # Return all bag files in current directory
                return [str(f) for f in Path('.').glob('*.bag')]
            
            path_obj = Path(partial_path)
            
            # If it's a directory, list bag files in it
            if path_obj.is_dir():
                return [str(f) for f in path_obj.glob('*.bag')]
            
            # If it contains wildcards, expand glob
            if '*' in partial_path or '?' in partial_path:
                try:
                    matches = glob.glob(partial_path)
                    bag_matches = [m for m in matches if m.endswith('.bag')]
                    return bag_matches
                except:
                    pass
            
            # Partial filename completion
            parent_dir = path_obj.parent if path_obj.parent != path_obj else Path('.')
            name_start = path_obj.name
            
            matches = []
            for bag_file in parent_dir.glob('*.bag'):
                if bag_file.name.startswith(name_start):
                    matches.append(str(bag_file))
            
            # Add common patterns if requested
            if include_patterns and not matches:
                patterns = ['*.bag', '**/*.bag', 'data/*.bag', 'bags/*.bag']
                for pattern in patterns:
                    if pattern.startswith(partial_path):
                        matches.append(pattern)
            
            return matches
            
        except Exception as e:
            logger.debug(f"Bag file completion error: {e}")
            return []
    
    @staticmethod
    def complete_directories(partial_path: str = "") -> List[str]:
        """Complete directory paths"""
        try:
            if not partial_path:
                return [str(d) for d in Path('.').iterdir() if d.is_dir()]
            
            path_obj = Path(partial_path)
            
            if path_obj.is_dir():
                # List subdirectories
                return [str(d) for d in path_obj.iterdir() if d.is_dir()]
            
            # Partial directory name completion
            parent_dir = path_obj.parent if path_obj.parent != path_obj else Path('.')
            name_start = path_obj.name
            
            matches = []
            for item in parent_dir.iterdir():
                if item.is_dir() and item.name.startswith(name_start):
                    matches.append(str(item))
            
            return matches
            
        except Exception as e:
            logger.debug(f"Directory completion error: {e}")
            return []
    
    @staticmethod
    def complete_any_files(partial_path: str = "", extensions: Optional[List[str]] = None) -> List[str]:
        """Complete any file paths, optionally filtered by extensions"""
        try:
            if not partial_path:
                files = [str(f) for f in Path('.').iterdir() if f.is_file()]
            else:
                path_obj = Path(partial_path)
                
                if path_obj.is_dir():
                    files = [str(f) for f in path_obj.iterdir() if f.is_file()]
                else:
                    parent_dir = path_obj.parent if path_obj.parent != path_obj else Path('.')
                    name_start = path_obj.name
                    
                    files = []
                    for item in parent_dir.iterdir():
                        if item.is_file() and item.name.startswith(name_start):
                            files.append(str(item))
            
            # Filter by extensions if specified
            if extensions:
                filtered_files = []
                for file_path in files:
                    if any(file_path.endswith(ext) for ext in extensions):
                        filtered_files.append(file_path)
                return filtered_files
            
            return files
            
        except Exception as e:
            logger.debug(f"File completion error: {e}")
            return []


class InteractivePathSelector:
    """Interactive path selection with completion support"""
    
    def __init__(self, console):
        self.console = console
    
    def select_bag_files(self, message: str = "Select bag files:", multiselect: bool = True) -> List[str]:
        """Interactive bag file selection with fuzzy search"""
        bag_files = PathCompleter.complete_bag_files()
        
        if not bag_files:
            self.console.print("[yellow]No bag files found in current directory[/yellow]")
            # Allow manual input
            manual_path = inquirer.text(
                message="Enter bag file path or pattern:",
                completer=self._create_path_completer('bag')
            ).execute()
            return [manual_path] if manual_path else []
        
        choices = [Choice(value=str(f), name=Path(f).name) for f in bag_files]
        choices.append(Choice(value='__custom__', name='📝 Enter custom path/pattern...'))
        
        if multiselect:
            selected = inquirer.select(
                message=message,
                choices=choices,
                multiselect=True,
                instruction="(Space to select, Enter to confirm)"
            ).execute()
        else:
            selected = [inquirer.select(
                message=message,
                choices=choices
            ).execute()]
        
        if not selected:
            return []
        
        # Handle custom input
        if '__custom__' in selected:
            custom_path = inquirer.text(
                message="Enter bag file path or pattern:",
                completer=self._create_path_completer('bag')
            ).execute()
            
            if custom_path:
                selected = [s for s in selected if s != '__custom__']
                selected.append(custom_path)
        
        return [s for s in selected if s != '__custom__']
    
    def select_output_path(self, message: str = "Output path:", default: str = "", extension: str = "") -> Optional[str]:
        """Interactive output path selection with completion"""
        return inquirer.text(
            message=message,
            default=default,
            completer=self._create_path_completer('file', extension)
        ).execute()
    
    def select_directory(self, message: str = "Select directory:") -> Optional[str]:
        """Interactive directory selection"""
        directories = PathCompleter.complete_directories()
        
        if directories:
            choices = [Choice(value=str(d), name=Path(d).name) for d in directories]
            choices.append(Choice(value='__custom__', name='📝 Enter custom path...'))
            
            selected = inquirer.select(
                message=message,
                choices=choices
            ).execute()
            
            if selected == '__custom__':
                return inquirer.text(
                    message="Enter directory path:",
                    completer=self._create_path_completer('dir')
                ).execute()
            
            return selected
        else:
            return inquirer.text(
                message=message,
                completer=self._create_path_completer('dir')
            ).execute()
    
    def _create_path_completer(self, path_type: str, extension: str = ""):
        """Create path completer for inquirer"""
        class PathCompleterForInquirer:
            def __init__(self, path_type, extension):
                self.path_type = path_type
                self.extension = extension
            
            def __call__(self, text):
                if self.path_type == 'bag':
                    return PathCompleter.complete_bag_files(text)
                elif self.path_type == 'dir':
                    return PathCompleter.complete_directories(text)
                elif self.path_type == 'file':
                    extensions = [self.extension] if self.extension else None
                    return PathCompleter.complete_any_files(text, extensions)
                else:
                    return []
        
        return PathCompleterForInquirer(path_type, extension)


class EnhancedRoseCompleter(Completer):
    """Enhanced completer with comprehensive path completion"""
    
    def __init__(self, runner):
        self.runner = runner
        self.base_commands = list(runner.commands.keys())
        self.inspect_commands = ['topics', 'info', 'timeline']
        self.data_commands = ['export', 'convert']
        self.cache_commands = ['clear', 'info', 'list']
        self.plugin_commands = ['list', 'info', 'run']
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()
        
        try:
            # Complete loaded bags when @ is typed
            if '@' in text:
                yield from self._complete_loaded_bags(text, document)
            
            # Complete shell commands when ! is typed
            elif text.startswith('!'):
                yield from self._complete_shell_commands(text, document)
            
            # Complete slash commands
            elif text.startswith('/'):
                yield from self._complete_commands(text, words, document)
            
            # Complete file paths for any command
            elif words:
                yield from self._complete_file_paths(text, words, document)
        except Exception as e:
            # Prevent completer from crashing
            logger.debug(f"Completion error: {e}")
            return
    
    def _complete_loaded_bags(self, text, document):
        """Complete with loaded bag files when @ is detected"""
        try:
            # Find the position of @ in the text
            at_pos = text.rfind('@')
            if at_pos == -1:
                return
            
            # Get the text after @
            after_at = text[at_pos + 1:]
            
            # Get loaded bags from cache directly (more reliable than runner state)
            loaded_bags = self._get_cached_bags()
            
            if not loaded_bags:
                # Show hint if no bags are loaded
                yield Completion(
                    text='<no bags loaded>',
                    start_position=-len(after_at),
                    display='<no bags loaded - use /load first>',
                    style='class:completion.hint'
                )
                return
            
            # Filter bags based on input after @
            for bag_path in loaded_bags:
                bag_name = Path(bag_path).name
                bag_stem = Path(bag_path).stem  # filename without extension
                
                # Match against both full name and stem
                if (not after_at or 
                    bag_name.lower().startswith(after_at.lower()) or 
                    bag_stem.lower().startswith(after_at.lower())):
                    
                    yield Completion(
                        text=bag_name,
                        start_position=-len(after_at),
                        display=f'{bag_name} ({bag_path})',
                        style='class:completion.bag'
                    )
                
        except Exception as e:
            logger.debug(f"Loaded bags completion error: {e}")
    
    def _complete_shell_commands(self, text, document):
        """Complete shell commands when ! is detected"""
        try:
            # Remove the ! prefix
            after_bang = text[1:]
            
            # Common shell commands to suggest
            common_commands = [
                'ls', 'pwd', 'cd', 'find', 'grep', 'cat', 'head', 'tail',
                'ps', 'top', 'df', 'du', 'which', 'whereis', 'history',
                'mkdir', 'rmdir', 'rm', 'cp', 'mv', 'chmod', 'chown',
                'tar', 'gzip', 'gunzip', 'zip', 'unzip',
                'python', 'python3', 'pip', 'pip3', 'git'
            ]
            
            # Filter commands based on input
            for cmd in common_commands:
                if not after_bang or cmd.startswith(after_bang.lower()):
                    yield Completion(
                        text=cmd,
                        start_position=-len(after_bang),
                        display=f'{cmd}',
                        style='class:completion.shell'
                    )
            
            # If there's already a command, try to complete file paths
            words = after_bang.split()
            if len(words) > 1:
                # Complete file paths for shell command arguments
                from pathlib import Path
                current_path = words[-1] if words else ''
                
                try:
                    if '/' in current_path:
                        parent_dir = Path(current_path).parent
                        filename_start = Path(current_path).name
                    else:
                        parent_dir = Path('.')
                        filename_start = current_path
                    
                    if parent_dir.exists() and parent_dir.is_dir():
                        for item in parent_dir.iterdir():
                            if filename_start and not item.name.startswith(filename_start):
                                continue
                            
                            display_name = item.name
                            if item.is_dir():
                                display_name += '/'
                            
                            yield Completion(
                                text=item.name,
                                start_position=-len(filename_start),
                                display=display_name,
                                style='class:completion.file'
                            )
                except Exception:
                    pass  # Ignore file completion errors
                    
        except Exception as e:
            logger.debug(f"Shell command completion error: {e}")
    
    def _get_cached_bags(self):
        """Get bags from cache directly (more reliable than runner state)"""
        try:
            from ...core.cache import get_cache
            cache = get_cache()
            
            # Get all cache files
            cached_bags = []
            if hasattr(cache, 'cache_dir') and cache.cache_dir.exists():
                import pickle
                for cache_file in cache.cache_dir.glob("*.pkl"):
                    try:
                        with open(cache_file, 'rb') as f:
                            cached_data = pickle.load(f)
                        
                        # Extract original bag path with multiple fallback methods
                        bag_path = None
                        
                        if hasattr(cached_data, 'original_path'):
                            bag_path = cached_data.original_path
                        elif hasattr(cached_data, 'bag_info'):
                            bag_info = cached_data.bag_info
                            if hasattr(bag_info, 'file_path'):
                                bag_path = str(bag_info.file_path)
                            elif hasattr(bag_info, 'file_info'):
                                file_info = bag_info.file_info
                                if isinstance(file_info, dict):
                                    # Try different possible keys
                                    for key in ['path', 'file_path', 'absolute_path', 'name']:
                                        if key in file_info:
                                            bag_path = file_info[key]
                                            break
                        
                        # If still no path, try to infer from cache filename
                        if not bag_path:
                            # Cache filename might give us a clue
                            cache_stem = cache_file.stem
                            # Look for .bag files that match the cache stem
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
            
            # Remove duplicates and return
            return list(set(cached_bags))
            
        except Exception as e:
            logger.debug(f"Could not get cached bags: {e}")
            
            # Fallback to runner state if cache access fails
            if hasattr(self.runner, 'state') and hasattr(self.runner.state, 'current_bags'):
                return self.runner.state.current_bags or []
            
            return []
    
    def _complete_commands(self, text, words, document):
        """Complete slash commands and sub-commands"""
        try:
            if len(words) == 1:
                # Complete base commands
                cmd_part = words[0]
                for cmd in self.base_commands:
                    if cmd.startswith(cmd_part):
                        yield Completion(cmd, start_position=-len(cmd_part))
            
            elif len(words) >= 2:
                # Complete sub-commands
                main_cmd = words[0]
                sub_part = words[1]
                
                if main_cmd == '/inspect':
                    for subcmd in self.inspect_commands:
                        if subcmd.startswith(sub_part):
                            yield Completion(subcmd, start_position=-len(sub_part))
                elif main_cmd == '/data':
                    for subcmd in self.data_commands:
                        if subcmd.startswith(sub_part):
                            yield Completion(subcmd, start_position=-len(sub_part))
                elif main_cmd == '/cache':
                    for subcmd in self.cache_commands:
                        if subcmd.startswith(sub_part):
                            yield Completion(subcmd, start_position=-len(sub_part))
                elif main_cmd == '/plugin':
                    for subcmd in self.plugin_commands:
                        if subcmd.startswith(sub_part):
                            yield Completion(subcmd, start_position=-len(sub_part))
                
                # Also complete file paths for commands that need them
                yield from self._complete_file_paths(text, words, document)
        except Exception as e:
            logger.debug(f"Command completion error: {e}")
            return
    
    def _complete_file_paths(self, text, words, document):
        """Complete file paths based on command context"""
        try:
            if not words:
                return
            
            main_cmd = words[0] if words else ''
            last_word = words[-1] if words else ''
            
            # Commands that primarily work with bag files
            if main_cmd in ['/load', '/extract', '/compress']:
                for bag_file in PathCompleter.complete_bag_files(last_word):
                    yield Completion(bag_file, start_position=-len(last_word))
            
            # Commands that work with directories
            elif main_cmd in ['/workspace']:
                for directory in PathCompleter.complete_directories(last_word):
                    yield Completion(directory, start_position=-len(last_word))
            
            # Commands that work with any files
            elif main_cmd in ['/data', '/export'] or any(keyword in text.lower() for keyword in ['output', 'file', 'path']):
                for file_path in PathCompleter.complete_any_files(last_word):
                    yield Completion(file_path, start_position=-len(last_word))
            
            # General bag file completion if 'bag' mentioned
            elif 'bag' in text.lower():
                for bag_file in PathCompleter.complete_bag_files(last_word):
                    yield Completion(bag_file, start_position=-len(last_word))
        except Exception as e:
            logger.debug(f"File path completion error: {e}")
            return


if __name__ == "__main__":
    pass
