#!/usr/bin/env python3
"""
CLI Adapter for Rose Interactive Run Environment
Adapts existing CLI commands to work in interactive mode
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from rich.console import Console
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from ...core.util import get_logger

logger = get_logger("run_cli_adapter")


class CLIAdapter:
    """Adapter to integrate existing CLI commands into interactive environment"""
    
    def __init__(self, runner):
        self.runner = runner
        self.console = runner.console
        
        # Initialize path selector for enhanced file completion
        try:
            from .run_path_completer import InteractivePathSelector
            self.path_selector = InteractivePathSelector(self.console)
        except Exception as e:
            logger.warning(f"Could not initialize path selector: {e}")
            self.path_selector = None
    
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
        """Interactive version of extract command"""
        from ..extract import _extract_topics_impl
        
        params = self._collect_extract_parameters(args)
        if not params:
            return {'success': False, 'error': 'Operation cancelled'}
        
        try:
            _extract_topics_impl(
                input_bags=params['input_bags'],
                topics=params['topics'],
                output=params.get('output'),
                workers=params.get('workers'),
                reverse=params.get('reverse', False),
                compression=params.get('compression', 'none'),
                dry_run=params.get('dry_run', False),
                yes=True,  # Auto-confirm in interactive mode
                verbose=params.get('verbose', False)
            )
            return {'success': True, 'message': 'Extract completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_extract_parameters(self, args: List[str]) -> Optional[Dict[str, Any]]:
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
            self.console.print("[yellow]No bags loaded. Use /run load first.[/yellow]")
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
        
        # Advanced options
        if inquirer.confirm("Configure advanced options?", default=False).execute():
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
            self.console.print("[yellow]No topics available[/yellow]")
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
        """Interactive version of compress command"""
        from ..compress import compress as compress_command
        
        params = self._collect_compress_parameters(args)
        if not params:
            return {'success': False, 'error': 'Operation cancelled'}
        
        try:
            compress_command(
                input_bags=params['input_bags'],
                compression=params['compression'],
                output=params.get('output'),
                workers=params.get('workers'),
                yes=True,  # Auto-confirm in interactive mode
                verbose=params.get('verbose', False)
            )
            return {'success': True, 'message': 'Compression completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_compress_parameters(self, args: List[str]) -> Optional[Dict[str, Any]]:
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
        """Interactive version of inspect command"""
        from ..inspect import inspect as inspect_command
        
        # Collect parameters for inspect command
        params = self._collect_inspect_parameters(args)
        if not params:
            return {'success': False, 'error': 'Operation cancelled'}
        
        try:
            # Execute inspect command
            inspect_command(
                bag_path=Path(params['bag_file']),
                topics=params.get('topics'),
                show_fields=params.get('show_fields', False),
                verbose=params.get('verbose', False)
            )
            return {'success': True, 'message': 'Inspect completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_inspect_parameters(self, args: List[str]) -> Optional[Dict[str, Any]]:
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
                self.console.print("[yellow]No bag files found in current directory[/yellow]")
                return None
            
            choices = [Choice(value=str(f), name=f.name) for f in bag_files]
            selected = inquirer.select(
                message="Select bag file to inspect:",
                choices=choices
            ).execute()
            if not selected:
                return None
            params['bag_file'] = selected
        
        # Advanced options
        if inquirer.confirm("Configure advanced options?", default=False).execute():
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
        
        subcommand = args[0]
        subargs = args[1:]
        
        if subcommand == 'export':
            return self._data_export(subargs)
        elif subcommand == 'info':
            return self._data_info(subargs)
        else:
            return self._show_data_menu()
    
    def _show_data_menu(self) -> Dict[str, Any]:
        """Show data command menu"""
        choices = [
            Choice(value='export', name='📤 Export - Export topic data to CSV'),
            Choice(value='info', name='ℹ️  Info - Show bag data information')
        ]
        
        selected = inquirer.select(
            message="Select data operation:",
            choices=choices
        ).execute()
        
        if selected:
            return getattr(self, f'_data_{selected}')([])
        
        return {'success': False, 'error': 'No operation selected'}
    
    def _data_export(self, args: List[str]) -> Dict[str, Any]:
        """Interactive data export"""
        try:
            from ..data import export as data_export_cmd
            
            # Collect parameters
            params = self._collect_data_export_parameters(args)
            if not params:
                return {'success': False, 'error': 'Operation cancelled'}
            
            # Data export only supports single bag, use first one
            input_bag = params['input_bags'][0] if params['input_bags'] else ""
            data_export_cmd(
                input_bag=input_bag,
                topics=params['topics'],
                output_csv=params['output'],
                yes=True
            )
            
            return {'success': True, 'message': 'Data export completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _collect_data_export_parameters(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Collect data export parameters"""
        params = {}
        
        # Input bags
        if self.runner.state.current_bags:
            params['input_bags'] = self.runner.state.current_bags
        else:
            self.console.print("[yellow]No bags loaded. Use /run load first.[/yellow]")
            return None
        
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
        
        # Format selection
        params['format'] = inquirer.select(
            message="Export format:",
            choices=[
                Choice(value='csv', name='CSV format'),
                Choice(value='json', name='JSON format')
            ],
            default='csv'
        ).execute()
        
        # Advanced options
        if inquirer.confirm("Configure advanced options?", default=False).execute():
            params['workers'] = inquirer.number(
                message="Number of workers:",
                default=None,
                min_allowed=1,
                max_allowed=16
            ).execute()
            
            params['verbose'] = inquirer.confirm("Verbose output?", default=False).execute()
        
        return params
    
    def _data_info(self, args: List[str]) -> Dict[str, Any]:
        """Interactive data info"""
        try:
            from ..data import info as data_info_cmd
            
            # Select bag file
            if self.runner.state.current_bags:
                if len(self.runner.state.current_bags) == 1:
                    input_bag = self.runner.state.current_bags[0]
                else:
                    choices = [Choice(value=bag, name=Path(bag).name) for bag in self.runner.state.current_bags]
                    input_bag = inquirer.select(
                        message="Select bag file for data info:",
                        choices=choices
                    ).execute()
                    if not input_bag:
                        return {'success': False, 'error': 'No bag selected'}
            else:
                self.console.print("[yellow]No bags loaded. Use /load first.[/yellow]")
                return {'success': False, 'error': 'No bags loaded'}
            
            # Advanced options
            show_columns = False
            show_sample = False
            if inquirer.confirm("Show advanced data info?", default=False).execute():
                show_columns = inquirer.confirm("Show DataFrame columns?", default=False).execute()
                show_sample = inquirer.confirm("Show sample data?", default=False).execute()
            
            data_info_cmd(
                input_bag=input_bag,
                topics=None,  # Show all topics
                show_columns=show_columns,
                show_sample=show_sample
            )
            
            return {'success': True, 'message': 'Data info completed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # =============================================================================
    # Cache Command Adaptation
    # =============================================================================
    
    def interactive_cache(self, args: List[str]) -> Dict[str, Any]:
        """Interactive version of cache command"""
        if not args:
            return self._show_cache_menu()
        
        subcommand = args[0]
        
        if subcommand == 'clear':
            return self._cache_clear()
        elif subcommand == 'export':
            return self._cache_export()
        else:
            return self._show_cache_menu()
    
    def _show_cache_menu(self) -> Dict[str, Any]:
        """Show cache management menu"""
        choices = [
            Choice(value='export', name='📤 Export - Export cache entries to file'),
            Choice(value='clear', name='🗑️  Clear - Clear cache data')
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
            
            if inquirer.confirm("Clear all cache data?", default=False).execute():
                cache_clear_cmd(yes=True)
                return {'success': True, 'message': 'Cache cleared'}
            else:
                return {'success': False, 'error': 'Operation cancelled'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _cache_export(self) -> Dict[str, Any]:
        """Export cache data"""
        try:
            from ..cache import cache_export as cache_export_cmd
            
            # Get export parameters
            output_file = inquirer.text(
                message="Output file path:",
                default="cache_export.json"
            ).execute()
            if not output_file:
                return {'success': False, 'error': 'No output file specified'}
            
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
                
                include_messages = inquirer.confirm("Include message data?", default=False).execute()
                
                cache_export_cmd(
                    output_file=output_file,
                    format=format_choice,
                    include_messages=include_messages
                )
            else:
                cache_export_cmd(output_file=output_file)
            
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
        else:
            return self._show_plugin_menu()
    
    def _show_plugin_menu(self) -> Dict[str, Any]:
        """Show plugin management menu"""
        choices = [
            Choice(value='list', name='📋 List - List available plugins'),
            Choice(value='info', name='ℹ️  Info - Show plugin information'),
            Choice(value='run', name='▶️  Run - Execute a plugin'),
            Choice(value='enable', name='✅ Enable - Enable a plugin'),
            Choice(value='disable', name='❌ Disable - Disable a plugin')
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


if __name__ == "__main__":
    pass
