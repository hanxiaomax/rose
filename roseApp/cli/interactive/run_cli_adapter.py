#!/usr/bin/env python3
"""
CLI Adapter for Rose Interactive Run Environment
Adapts existing CLI commands to work in interactive mode
"""

import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
from rich.console import Console
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ...core.util import get_logger
from .interactive_ui import InteractiveUI

logger = get_logger("run_cli_adapter")


class CLIAdapter:
    """Adapter to integrate existing CLI commands into interactive environment"""
    
    def __init__(self, runner):
        self.runner = runner
        self.console = runner.console
        self.ui = runner.ui  # Use UI from runner
    
    def _proxy_to_native_cli(self, command_parts: List[str]) -> Dict[str, Any]:
        """Generic proxy to native CLI commands"""
        try:
            import subprocess
            cmd = [sys.executable, '-m', 'roseApp.rose'] + command_parts
            result = subprocess.run(
                cmd,
                capture_output=False,  # Let output go directly to console
                cwd=Path.cwd()
            )
            
            if result.returncode == 0:
                return {'success': True, 'message': f'Command {" ".join(command_parts)} completed'}
            else:
                return {'success': False, 'error': f'Command failed with code {result.returncode}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _select_input_bag(self, message: str = "Select bag file:") -> Optional[str]:
        """Common method to select input bag file with completion support"""
        # First try to use loaded bags
        if self.runner.state.current_bags:
            if len(self.runner.state.current_bags) == 1:
                # Only one loaded bag, use it
                return self.runner.state.current_bags[0]
            else:
                # Multiple loaded bags, let user choose
                choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
                choices.append(Choice(value='__browse__', name='Browse for different file...'))
                
                selected = inquirer.select(
                    message=message,
                    choices=choices
                ).execute()
                
                if selected and selected != '__browse__':
                    return selected
        
        # No loaded bags or user chose to browse - use unified path input with completion
        return self._ask_for_path(
            message="Enter bag file path (Tab for completion):",
            default="*.bag",
            file_type="bag"
        )
    
    def _ask_for_path(self, message: str, default: str = "", file_type: str = "bag") -> Optional[str]:
        """Unified path input function with completion support (like /load command)"""
        try:
            # Choose appropriate completer based on file type
            if file_type == "bag":
                from .run_path_completer import BagFileCompleter
                completer = BagFileCompleter()
            else:
                # For other file types, use BagFileCompleter as it provides general path completion
                from .run_path_completer import BagFileCompleter
                completer = BagFileCompleter()
            
            path = inquirer.text(
                message=message,
                default=default,
                completer=completer
            ).execute()
            
            return path if path and path.strip() else None
            
        except Exception as e:
            logger.warning(f"Path completion failed: {e}")
            # Fallback to simple text input without completion
            path = inquirer.text(
                message=message,
                default=default
            ).execute()
            
            return path if path and path.strip() else None
    
    # =============================================================================
    # Load Command Adaptation
    # =============================================================================
    
    def interactive_load(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of load command"""
        from ..load import load as load_command
        
        # Collect parameters interactively
        params = self._collect_load_parameters(args)
        if not params:
            return {'success': False, 'error': 'Operation cancelled'}
        
        try:
            # Execute load command with collected parameters
            load_command(
                input=params['input_patterns'],
                workers=params.get('workers'),
                verbose=params.get('verbose', False),
                force=params.get('force', False),
                dry_run=params.get('dry_run', False),
                build_index=params.get('build_index', True)
            )
            
            # Update runner state with loaded bags
            if not params.get('dry_run', False):
                import glob
                from pathlib import Path
                
                loaded_files = []
                for pattern in params['input_patterns']:
                    if '*' in pattern or '?' in pattern:
                        loaded_files.extend(glob.glob(pattern))
                    else:
                        loaded_files.append(pattern)
                
                # Update current bags in runner state
                for bag_file in loaded_files:
                    if bag_file not in self.runner.state.current_bags:
                        self.runner.state.current_bags.append(bag_file)
                    
                    # Also update loaded_bags with basic info
                    if bag_file not in self.runner.state.loaded_bags:
                        self.runner.state.loaded_bags[bag_file] = {
                            'path': bag_file,
                            'name': Path(bag_file).name,
                            'topics': [],  # Will be populated by cache
                            'loaded_at': 'now'
                        }
            
            return {'success': True, 'message': 'Load completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_load_parameters(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Collect load command parameters interactively"""
        params = {}
        
        # Input patterns with enhanced path completion
        if args:
            params['input_patterns'] = args
        else:
            # Use enhanced path completion with BagFileCompleter
            from .run_path_completer import BagFileCompleter
            
            pattern = inquirer.text(
                message="Enter bag file path or pattern (Tab for completion):",
                default="*.bag",
                completer=BagFileCompleter()
            ).execute()
            
            if not pattern:
                return None
            params['input_patterns'] = [pattern]
        
        # Optional parameters - only ask if no args provided initially
        if not args and inquirer.confirm("Configure advanced options?", default=False).execute():
            params['workers'] = inquirer.number(
                message="Number of workers:",
                default=None,
                min_allowed=1,
                max_allowed=16
            ).execute()
            
            params['verbose'] = inquirer.confirm("Verbose output?", default=False).execute()
            params['force'] = inquirer.confirm("Force reload?", default=False).execute()
            params['dry_run'] = inquirer.confirm("Dry run (preview only)?", default=False).execute()
            params['build_index'] = inquirer.confirm("Build topic index?", default=True).execute()
        
        return params
    
    # =============================================================================
    # Extract Command Adaptation
    # =============================================================================
    
    def interactive_extract(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of extract command - proxy to native CLI"""
        # If args provided, use them directly
        if args:
            return self._proxy_to_native_cli(['extract'] + args + ['--yes'])
        
        # No args - need to collect bag file and topics
        bag_file = None
        
        # Get bag file
        if self.runner.state.current_bags:
            # Use first loaded bag
            bag_file = self.runner.state.current_bags[0]
        else:
            # Prompt for bag file using unified path input
            bag_file = self._ask_for_path("Enter bag file path (Tab for completion):")
            
            if not bag_file:
                return {'success': False, 'error': 'No bag file specified'}
        
        # Show available topics first
        self.ui.msg.info(f"Showing available topics in {bag_file}...")
        inspect_result = self._proxy_to_native_cli(['inspect', bag_file])
        
        # Prompt for topics
        topics_input = inquirer.text(
            message="Enter topics to extract (space-separated, use names from above):"
        ).execute()
        
        if not topics_input:
            return {'success': False, 'error': 'No topics specified'}
        
        topics = topics_input.split()
        
        # Build and execute command
        cmd_args = ['extract', bag_file, '--topics'] + topics + ['--yes']
        return self._proxy_to_native_cli(cmd_args)
    
    def _collect_extract_parameters_DEPRECATED(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Collect extract command parameters interactively"""
        params = {}
        
        # Input bags
        if args:
            params['input_bags'] = args
        elif self.runner.state.current_bags:
            # Use loaded bags
            choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
            
            selected = inquirer.select(
                message="Select bags to extract from:",
                choices=choices,
                multiselect=True
            ).execute()
            
            if not selected:
                return None
            params['input_bags'] = selected
        else:
            self.ui.msg.warning("No bags loaded. Use /load first.")
            return None
        
        # Topics selection
        if self.runner.state.selected_topics:
            use_selected = inquirer.confirm(
                f"Use currently selected topics ({len(self.runner.state.selected_topics)})?",
                default=True
            ).execute()
            
            if use_selected:
                params['topics'] = self.runner.state.selected_topics
            else:
                params['topics'] = self._select_topics_for_extract()
        else:
            params['topics'] = self._select_topics_for_extract()
        
        if not params['topics']:
            return None
        
        # Output pattern
        params['output'] = inquirer.text(
            message="Output pattern:",
            default="{input}_extracted_{timestamp}.bag",
            instruction="Use {input} for input filename, {timestamp} for timestamp"
        ).execute()
        
        # Advanced options - only ask if no args and not using loaded bags
        if not args and not self.runner.state.current_bags and inquirer.confirm("Configure advanced options?", default=False).execute():
            params['compression'] = inquirer.select(
                message="Compression type:",
                choices=[
                    Choice(value='none', name='No compression'),
                    Choice(value='bz2', name='BZ2 compression'),
                    Choice(value='lz4', name='LZ4 compression')
                ],
                default='none'
            ).execute()
            
            params['reverse'] = inquirer.confirm("Reverse selection (exclude topics)?", default=False).execute()
            params['dry_run'] = inquirer.confirm("Dry run (preview only)?", default=False).execute()
            params['verbose'] = inquirer.confirm("Verbose output?", default=False).execute()
            
            params['workers'] = inquirer.number(
                message="Number of workers:",
                default=None,
                min_allowed=1,
                max_allowed=16
            ).execute()
        
        return params
    
    def _select_topics_for_extract(self) -> List[str]:
        """Select topics for extraction"""
        # Get available topics from loaded bags
        all_topics = set()
        for bag_path in self.runner.state.current_bags:
            if bag_path in self.runner.state.loaded_bags:
                bag_info = self.runner.state.loaded_bags[bag_path]
                all_topics.update(bag_info.get('topics', []))
        
        if not all_topics:
            self.ui.msg.warning("No topics available")
            return []
        
        # Use fuzzy search
        from ..util import ask_topics_with_fuzzy
        return ask_topics_with_fuzzy(
            console=self.console,
            topics=sorted(list(all_topics)),
            message="Select topics to extract:",
            require_selection=True
        )
    
    # =============================================================================
    # Compress Command Adaptation
    # =============================================================================
    
    def interactive_compress(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of compress command - proxy to native CLI"""
        # If no args provided, use loaded bags or prompt
        if not args:
            if self.runner.state.current_bags:
                # Use loaded bags and add --yes for auto-confirm
                cmd_args = ['compress'] + self.runner.state.current_bags + ['--yes']
                return self._proxy_to_native_cli(cmd_args)
            else:
                # Prompt for bag file
                bag_file = self._ask_for_path("Enter bag file path (Tab for completion):")
                
                if not bag_file:
                    return {'success': False, 'error': 'No bag file specified'}
                
                cmd_args = ['compress', bag_file, '--yes']
                return self._proxy_to_native_cli(cmd_args)
        else:
            # Use provided arguments directly, add --yes for auto-confirm
            return self._proxy_to_native_cli(['compress'] + args + ['--yes'])
    
    def _collect_compress_parameters_DEPRECATED(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Collect compress command parameters interactively"""
        params = {}
        
        # Input bags
        if args:
            params['input_bags'] = args
        elif self.runner.state.current_bags:
            choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
            
            selected = inquirer.select(
                message="Select bags to compress:",
                choices=choices,
                multiselect=True
            ).execute()
            
            if not selected:
                return None
            params['input_bags'] = selected
        else:
            pattern = inquirer.text(
                message="Enter bag file pattern:",
                default="*.bag"
            ).execute()
            if not pattern:
                return None
            params['input_bags'] = [pattern]
        
        # Compression type
        params['compression'] = inquirer.select(
            message="Select compression type:",
            choices=[
                Choice(value='bz2', name='BZ2 compression (good compression ratio)'),
                Choice(value='lz4', name='LZ4 compression (faster)'),
                Choice(value='none', name='No compression')
            ],
            default='bz2'
        ).execute()
        
        # Optional parameters
        if inquirer.confirm("Configure advanced options?", default=False).execute():
            params['output'] = inquirer.text(
                message="Output pattern:",
                default="{input}_{compression}.bag"
            ).execute()
            
            params['workers'] = inquirer.number(
                message="Number of workers:",
                default=None,
                min_allowed=1,
                max_allowed=16
            ).execute()
            
            params['verbose'] = inquirer.confirm("Verbose output?", default=False).execute()
        
        return params
    
    # =============================================================================
    # Inspect Command Adaptation
    # =============================================================================
    
    def interactive_inspect(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of inspect command - proxy to native CLI"""
        # If no args provided, try to use loaded bags or prompt for bag file
        if not args:
            if self.runner.state.current_bags:
                # Use first loaded bag
                bag_file = self.runner.state.current_bags[0]
                return self._proxy_to_native_cli(['inspect', bag_file])
            else:
                # Prompt for bag file
                bag_file = self._ask_for_path("Enter bag file path (Tab for completion):")
                
                if not bag_file:
                    return {'success': False, 'error': 'No bag file specified'}
                
                return self._proxy_to_native_cli(['inspect', bag_file])
        else:
            # Use provided arguments directly
            return self._proxy_to_native_cli(['inspect'] + args)
    
    def _collect_inspect_parameters_DEPRECATED(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Collect inspect command parameters interactively"""
        params = {}
        
        # Select bag file
        if args:
            params['bag_file'] = args[0]
        elif self.runner.state.current_bags:
            if len(self.runner.state.current_bags) == 1:
                params['bag_file'] = self.runner.state.current_bags[0]
            else:
                choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
                selected = inquirer.select(
                    message="Select bag file to inspect:",
                    choices=choices
                ).execute()
                if not selected:
                    return None
                params['bag_file'] = selected
        else:
            bag_files = list(Path('.').glob('*.bag'))
            if not bag_files:
                from ...ui.theme import get_color
                self.console.print(f"[{get_color('warning')}]No bag files found in current directory[/{get_color('warning')}]")
                return None
            
            choices = [Choice(value=str(f), name=f.name) for f in bag_files]
            selected = inquirer.select(
                message="Select bag file to inspect:",
                choices=choices
            ).execute()
            if not selected:
                return None
            params['bag_file'] = selected
        
        # Advanced options - only ask if no args and not using loaded bags
        if not args and not self.runner.state.current_bags and inquirer.confirm("Configure advanced options?", default=False).execute():
            params['show_fields'] = inquirer.confirm("Show field analysis?", default=False).execute()
            params['verbose'] = inquirer.confirm("Verbose output?", default=False).execute()
        
        return params
    
    # =============================================================================
    # Data Command Adaptation  
    # =============================================================================
    
    def interactive_data(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of data command"""
        if not args:
            return self._show_data_menu()
        
        # Handle subcommands
        subcommand = args[0]
        remaining_args = args[1:]
        
        if subcommand == 'export':
            return self._data_export(remaining_args)
        elif subcommand == 'info':
            return self._data_info(remaining_args)
        else:
            # Unknown subcommand, proxy to CLI for error handling
            return self._proxy_to_native_cli(['data'] + args)
    
    def _show_data_menu(self) -> Dict[str, Any]:
        """Show data command menu"""
        choices = [
            Choice(value='export', name='Export - Export topic data to CSV'),
            Choice(value='info', name='Info - Show bag data information')
        ]
        
        selected = inquirer.select(
            message="Select data operation:",
            choices=choices
        ).execute()
        
        if selected:
            return getattr(self, f'_data_{selected}')([])
        
        return {'success': False, 'error': 'No operation selected'}
    
    def _data_export(self, args: List[str]) -> Dict[str, Any]:
        """Interactive data export - builds CLI command"""
        try:
            # If bag file provided as argument, use it; otherwise collect parameters
            if args and not args[0].startswith('-'):
                # Bag file provided as argument
                input_bag = args[0]
                # Remove bag file from args for parameter collection
                remaining_args = args[1:]
            else:
                # No bag file provided, need to collect parameters including bag selection
                input_bag = None
                remaining_args = args
            
            # Collect parameters
            params = self._collect_data_export_parameters(remaining_args, input_bag)
            if not params:
                return {'success': False, 'error': 'Operation cancelled'}
            
            # Build CLI command arguments
            cli_args = ['data', 'export']
            
            # Add input bag (data export only supports single bag)
            input_bag = params['input_bag']
            if input_bag:
                cli_args.append(input_bag)
            
            # Add topics
            if params.get('topics'):
                for topic in params['topics']:
                    cli_args.extend(['-t', topic])
            
            # Add output file
            if params.get('output'):
                cli_args.extend(['-o', params['output']])
            
            # Add time filters if specified
            if params.get('start_time'):
                cli_args.extend(['--start-time', params['start_time']])
            
            if params.get('end_time'):
                cli_args.extend(['--end-time', params['end_time']])
            
            # Add search filter if specified
            if params.get('search'):
                cli_args.extend(['--search', params['search']])
            
            # Add auto-yes flag for smoother experience
            cli_args.append('-y')
            
            # Show constructed command for debugging
            cmd_str = ' '.join(cli_args)
            self.console.print(f"[dim]Executing: rose {cmd_str}[/dim]")
            
            # Execute via CLI proxy
            return self._proxy_to_native_cli(cli_args)
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_data_export_parameters(self, args: List[str], provided_bag: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Collect data export parameters"""
        params = {}
        
        # Input bag
        if provided_bag:
            # Bag file was provided as argument
            params['input_bag'] = provided_bag
        else:
            # Need to select bag file
            input_bag = self._select_input_bag("Select bag file for data export:")
            if not input_bag:
                return None
            params['input_bag'] = input_bag
        
        # Topics selection
        if self.runner.state.selected_topics:
            use_selected = inquirer.confirm(
                f"Use selected topics ({len(self.runner.state.selected_topics)})?",
                default=True
            ).execute()
            
            if use_selected:
                params['topics'] = self.runner.state.selected_topics
            else:
                params['topics'] = self._select_topics_for_extract()
        else:
            params['topics'] = self._select_topics_for_extract()
        
        if not params['topics']:
            return None
        
        # Output file with path completion
        if self.path_selector:
            params['output'] = self.path_selector.select_output_path(
                message="Output file path:",
                default="bag_data_{timestamp}.csv",
                extension=".csv"
            )
        else:
            params['output'] = inquirer.text(
                message="Output file path:",
                default="bag_data_{timestamp}.csv"
            ).execute()
        
        # Advanced filtering options
        if inquirer.confirm("Configure time filters or search?", default=False).execute():
            # Time filters
            start_time = inquirer.text(
                message="Start time (ISO format or seconds, leave empty to skip):",
                default=""
            ).execute()
            if start_time:
                params['start_time'] = start_time
            
            end_time = inquirer.text(
                message="End time (ISO format or seconds, leave empty to skip):",
                default=""
            ).execute()
            if end_time:
                params['end_time'] = end_time
            
            # Search filter
            search_text = inquirer.text(
                message="Search text in string columns (leave empty to skip):",
                default=""
            ).execute()
            if search_text:
                params['search'] = search_text
        
        return params
    
    def _data_info(self, args: List[str]) -> Dict[str, Any]:
        """Interactive data info - builds CLI command"""
        try:
            # Get input bag file
            if args and not args[0].startswith('-'):
                # Bag file provided as argument
                input_bag = args[0]
                remaining_args = args[1:]
            else:
                # Need to select bag file
                input_bag = self._select_input_bag("Select bag file for data info:")
                if not input_bag:
                    return {'success': False, 'error': 'No bag selected'}
                remaining_args = args
            
            # Build CLI command arguments
            cli_args = ['data', 'info', str(input_bag)]
            
            # Advanced options
            if inquirer.confirm("Show advanced data info?", default=False).execute():
                if inquirer.confirm("Show DataFrame columns?", default=False).execute():
                    cli_args.append('-c')
                
                if inquirer.confirm("Show sample data?", default=False).execute():
                    cli_args.append('-s')
            
            # Show constructed command for debugging
            cmd_str = ' '.join(cli_args)
            self.console.print(f"[dim]Executing: rose {cmd_str}[/dim]")
            
            # Execute via CLI proxy
            return self._proxy_to_native_cli(cli_args)
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # =============================================================================
    # Cache Command Adaptation
    # =============================================================================
    
    def interactive_cache(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of cache command"""
        if not args:
            # Default behavior: show cache info (like native CLI)
            return self._cache_show_info()
        
        subcommand = args[0]
        
        if subcommand == 'clear':
            return self._cache_clear()
        elif subcommand == 'export':
            return self._cache_export()
        else:
            return self._show_cache_menu()
    
    def _cache_show_info(self) -> Dict[str, Any]:
        """Show cache information (default behavior) - proxy to native CLI"""
        return self._proxy_to_native_cli(['cache'])
    
    def _show_cache_menu(self) -> Dict[str, Any]:
        """Show cache management menu"""
        choices = [
            Choice(value='export', name='Export - Export cache entries to file'),
            Choice(value='clear', name='Clear - Clear cache data')
        ]
        
        selected = inquirer.select(
            message="Select cache operation:",
            choices=choices
        ).execute()
        
        if selected == 'export':
            return self._cache_export()
        elif selected == 'clear':
            return self._cache_clear()
        
        return {'success': False, 'error': 'No operation selected'}
    
    def _cache_clear(self) -> Dict[str, Any]:
        """Clear cache interactively"""
        try:
            from ..cache import cache_clear as cache_clear_cmd
            
            # Ask what to clear
            clear_type = inquirer.select(
                message="What to clear?",
                choices=[
                    Choice(value='all', name='Clear all cache data'),
                    Choice(value='specific', name='Clear cache for specific bag')
                ]
            ).execute()
            
            if clear_type == 'all':
                if inquirer.confirm("Clear all cache data?", default=False).execute():
                    cache_clear_cmd(yes=True)
                    return {'success': True, 'message': 'All cache cleared'}
                else:
                    return {'success': False, 'error': 'Operation cancelled'}
            
            elif clear_type == 'specific':
                # Select bag to clear cache for
                if self.runner.state.current_bags:
                    choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
                    selected_bag = inquirer.select(
                        message="Select bag to clear cache for:",
                        choices=choices
                    ).execute()
                    
                    if selected_bag:
                        # Ensure selected_bag is a string, not OptionInfo object
                        bag_path_str = str(selected_bag)
                        cache_clear_cmd(bag_path=bag_path_str, yes=True)
                        return {'success': True, 'message': f'Cache cleared for {Path(bag_path_str).name}'}
                    else:
                        return {'success': False, 'error': 'No bag selected'}
                else:
                    # Manual input
                    bag_path = self._ask_for_path("Enter bag file path (Tab for completion):")
                    
                    if bag_path:
                        # Ensure bag_path is a string, not OptionInfo object
                        bag_path_str = str(bag_path).strip()
                        if bag_path_str:
                            cache_clear_cmd(bag_path=bag_path_str, yes=True)
                            return {'success': True, 'message': f'Cache cleared for {Path(bag_path_str).name}'}
                        else:
                            return {'success': False, 'error': 'No bag path specified'}
                    else:
                        return {'success': False, 'error': 'No bag path specified'}
            
            return {'success': False, 'error': 'Operation cancelled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _cache_export(self) -> Dict[str, Any]:
        """Export cache data"""
        try:
            from ..cache import cache_export as cache_export_cmd
            from pathlib import Path
            
            # Get export parameters
            output_file = inquirer.text(
                message="Output file path:",
                default="cache_export.json"
            ).execute()
            if not output_file:
                return {'success': False, 'error': 'No output file specified'}
            
            # Export scope selection
            export_scope = inquirer.select(
                message="What to export?",
                choices=[
                    Choice(value='all', name='Export all cache data'),
                    Choice(value='bag', name='Export cache for specific bag'),
                    Choice(value='name', name='Export cache by name/key')
                ]
            ).execute()
            
            # Prepare parameters
            export_params = {'output_file': output_file}
            
            if export_scope == 'bag':
                # Select bag to export cache for
                if self.runner.state.current_bags:
                    choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
                    selected_bag = inquirer.select(
                        message="Select bag to export cache for:",
                        choices=choices
                    ).execute()
                    if selected_bag:
                        export_params['bag_path'] = selected_bag
                    else:
                        return {'success': False, 'error': 'No bag selected'}
                else:
                    # Manual input
                    bag_path = self._ask_for_path("Enter bag file path (Tab for completion):")
                    if bag_path:
                        export_params['bag_path'] = bag_path
                    else:
                        return {'success': False, 'error': 'No bag path specified'}
            
            elif export_scope == 'name':
                cache_name = inquirer.text(
                    message="Enter cache key/name:",
                    default=""
                ).execute()
                if cache_name:
                    export_params['name'] = cache_name
                else:
                    return {'success': False, 'error': 'No cache name specified'}
            
            # Advanced options
            if inquirer.confirm("Configure export options?", default=False).execute():
                format_choice = inquirer.select(
                    message="Export format:",
                    choices=[
                        Choice(value='json', name='JSON format'),
                        Choice(value='yaml', name='YAML format'),
                        Choice(value='pickle', name='Pickle format')
                    ],
                    default='json'
                ).execute()
                export_params['format'] = format_choice
                
                include_messages = inquirer.confirm("Include message data?", default=False).execute()
                export_params['include_messages'] = include_messages
            
            # Execute export command
            cache_export_cmd(**export_params)
            
            return {'success': True, 'message': 'Cache export completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # =============================================================================
    # Plugin Command Adaptation
    # =============================================================================
    
    def interactive_plugin(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of plugin command"""
        if not args:
            return self._show_plugin_menu()
        
        subcommand = args[0]
        
        if subcommand == 'list':
            return self._plugin_list()
        elif subcommand == 'info':
            return self._plugin_info(args[1:])
        elif subcommand == 'run':
            return self._plugin_run(args[1:])
        elif subcommand == 'enable':
            return self._plugin_enable(args[1:])
        elif subcommand == 'disable':
            return self._plugin_disable(args[1:])
        elif subcommand == 'reload':
            return self._plugin_reload(args[1:])
        elif subcommand == 'install':
            return self._plugin_install(args[1:])
        elif subcommand == 'uninstall':
            return self._plugin_uninstall(args[1:])
        elif subcommand == 'create':
            return self._plugin_create(args[1:])
        else:
            return self._show_plugin_menu()
    
    def _show_plugin_menu(self) -> Dict[str, Any]:
        """Show plugin management menu"""
        choices = [
            Choice(value='list', name='List - List available plugins'),
            Choice(value='info', name='Info - Show plugin information'),
            Choice(value='run', name='Run - Execute a plugin'),
            Choice(value='enable', name='Enable - Enable a plugin'),
            Choice(value='disable', name='Disable - Disable a plugin'),
            Choice(value='reload', name='Reload - Reload plugins'),
            Choice(value='install', name='Install - Install a plugin'),
            Choice(value='uninstall', name='Uninstall - Uninstall a plugin'),
            Choice(value='create', name='Create - Create a new plugin')
        ]
        
        selected = inquirer.select(
            message="Select plugin operation:",
            choices=choices
        ).execute()
        
        if selected == 'list':
            return self._plugin_list()
        elif selected == 'info':
            return self._plugin_info([])
        elif selected == 'run':
            return self._plugin_run([])
        elif selected == 'enable':
            return self._plugin_enable([])
        elif selected == 'disable':
            return self._plugin_disable([])
        elif selected == 'reload':
            return self._plugin_reload([])
        elif selected == 'install':
            return self._plugin_install([])
        elif selected == 'uninstall':
            return self._plugin_uninstall([])
        elif selected == 'create':
            return self._plugin_create([])
        
        return {'success': False, 'error': 'No operation selected'}
    
    def _plugin_list(self) -> Dict[str, Any]:
        """List available plugins"""
        try:
            from ..plugin import list_plugins as plugin_list_cmd
            plugin_list_cmd()
            return {'success': True, 'message': 'Plugin list displayed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_info(self, args: List[str]) -> Dict[str, Any]:
        """Show plugin info"""
        try:
            from ..plugin import info as plugin_info_cmd
            
            if not args:
                # Interactive plugin selection
                plugin_name = inquirer.text(
                    message="Enter plugin name for info:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin specified'}
                args = [plugin_name]
            
            plugin_info_cmd(plugin_name=args[0])
            return {'success': True, 'message': 'Plugin info displayed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_run(self, args: List[str]) -> Dict[str, Any]:
        """Run plugin interactively"""
        try:
            from ..plugin import run as plugin_run_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name to run:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin specified'}
                args = [plugin_name]
            
            # For simplicity, run with current bags if available
            bag_files = self.runner.state.current_bags if self.runner.state.current_bags else []
            
            plugin_run_cmd(
                plugin_name=args[0],
                input=bag_files,
                verbose=False
            )
            
            return {'success': True, 'message': 'Plugin execution completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_enable(self, args: List[str]) -> Dict[str, Any]:
        """Enable a plugin"""
        try:
            from ..plugin import enable as plugin_enable_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name to enable:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin specified'}
                args = [plugin_name]
            
            plugin_enable_cmd(plugin_name=args[0])
            return {'success': True, 'message': 'Plugin enabled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_disable(self, args: List[str]) -> Dict[str, Any]:
        """Disable a plugin"""
        try:
            from ..plugin import disable as plugin_disable_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name to disable:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin specified'}
                args = [plugin_name]
            
            plugin_disable_cmd(plugin_name=args[0])
            return {'success': True, 'message': 'Plugin disabled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_reload(self, args: List[str]) -> Dict[str, Any]:
        """Reload plugins"""
        try:
            from ..plugin import reload as plugin_reload_cmd
            plugin_reload_cmd()
            return {'success': True, 'message': 'Plugins reloaded'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_install(self, args: List[str]) -> Dict[str, Any]:
        """Install a plugin"""
        try:
            from ..plugin import install as plugin_install_cmd
            
            if not args:
                plugin_path = inquirer.text(
                    message="Enter plugin path or URL:"
                ).execute()
                if not plugin_path:
                    return {'success': False, 'error': 'No plugin path specified'}
                args = [plugin_path]
            
            plugin_install_cmd(plugin_path=args[0])
            return {'success': True, 'message': 'Plugin installed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_uninstall(self, args: List[str]) -> Dict[str, Any]:
        """Uninstall a plugin"""
        try:
            from ..plugin import uninstall as plugin_uninstall_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name to uninstall:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin specified'}
                args = [plugin_name]
            
            plugin_uninstall_cmd(plugin_name=args[0])
            return {'success': True, 'message': 'Plugin uninstalled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _plugin_create(self, args: List[str]) -> Dict[str, Any]:
        """Create a new plugin"""
        try:
            from ..plugin import create as plugin_create_cmd
            
            if not args:
                plugin_name = inquirer.text(
                    message="Enter plugin name:"
                ).execute()
                if not plugin_name:
                    return {'success': False, 'error': 'No plugin name specified'}
                args = [plugin_name]
            
            # Ask for template type
            template = inquirer.select(
                message="Select plugin template:",
                choices=[
                    Choice(value='hook', name='Hook Plugin'),
                    Choice(value='script', name='Script Plugin'),
                    Choice(value='data', name='Data Plugin')
                ],
                default='hook'
            ).execute()
            
            plugin_create_cmd(name=args[0], template=template)
            return {'success': True, 'message': 'Plugin created'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    pass
