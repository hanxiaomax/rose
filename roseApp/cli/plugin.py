#!/usr/bin/env python3
"""
Plugin management commands for Rose
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..core.plugins import get_plugin_manager, BasePlugin, BaseScriptPlugin, PluginInfo, HookType, PluginType
from ..core.directories import get_rose_directories
from ..ui.common_ui import Message
from ..ui.theme import get_color

app = typer.Typer(help="Plugin management commands")
console = Console()


@app.command(name="list")
def list_plugins(
    enabled_only: bool = typer.Option(False, "--enabled", help="Show only enabled plugins"),
    plugin_type: Optional[str] = typer.Option(None, "--type", help="Filter by plugin type (hook, script)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """List all available plugins"""
    manager = get_plugin_manager()
    
    # Get plugins based on filters
    if enabled_only:
        hook_plugins = manager.get_enabled_plugins()
        script_plugins = manager.get_enabled_script_plugins()
    else:
        hook_plugins = list(manager.hook_plugins.values())
        script_plugins = list(manager.script_plugins.values())
    
    # Filter by type if specified
    if plugin_type:
        if plugin_type.lower() == "hook":
            plugins = hook_plugins
        elif plugin_type.lower() == "script":
            plugins = script_plugins
        else:
            Message.error(f"Invalid plugin type: {plugin_type}. Use 'hook' or 'script'", console)
            raise typer.Exit(1)
    else:
        plugins = hook_plugins + script_plugins
    
    if not plugins:
        if enabled_only:
            Message.warning("No enabled plugins found", console)
        else:
            Message.warning("No plugins found", console)
        Message.info(f"Plugin directory: {manager.plugin_dir}", console)
        return
    
    # Create plugins table
    table = Table(title="Rose Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Version", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Description", style="white")
    
    if verbose:
        table.add_column("Author", style="dim")
        table.add_column("Hooks", style="yellow")
    
    for plugin in plugins:
        info = plugin.plugin_info
        status = "✓ Enabled" if plugin.is_enabled() else "✗ Disabled"
        
        # Determine plugin type
        plugin_name = info.name
        plugin_type_enum = manager.get_plugin_type(plugin_name)
        type_str = plugin_type_enum.value.title() if plugin_type_enum else "Unknown"
        
        if verbose:
            if isinstance(plugin, BaseScriptPlugin):
                hooks_str = "Script Plugin"
            else:
                hooks_str = ", ".join([h.value for h in info.supported_hooks]) if info.supported_hooks else "None"
            
            table.add_row(
                info.name,
                type_str,
                info.version,
                status,
                info.description[:50] + "..." if len(info.description) > 50 else info.description,
                info.author,
                hooks_str
            )
        else:
            table.add_row(
                info.name,
                type_str,
                info.version,
                status,
                info.description[:60] + "..." if len(info.description) > 60 else info.description
            )
    
    console.print(table)
    
    if verbose:
        console.print(f"\nPlugin directory: {manager.plugin_dir}")
        console.print(f"Total plugins: {len(manager.hook_plugins) + len(manager.script_plugins)}")
        console.print(f"Hook plugins: {len(manager.hook_plugins)} ({len(manager.get_enabled_plugins())} enabled)")
        console.print(f"Script plugins: {len(manager.script_plugins)} ({len(manager.get_enabled_script_plugins())} enabled)")


@app.command()
def info(
    plugin_name: str = typer.Argument(..., help="Plugin name to show information for")
):
    """Show detailed information about a specific plugin"""
    manager = get_plugin_manager()
    plugin = manager.get_any_plugin(plugin_name)
    
    if not plugin:
        Message.error(f"Plugin '{plugin_name}' not found", console)
        raise typer.Exit(1)
    
    info = plugin.plugin_info
    
    # Create info panel
    info_text = Text()
    info_text.append(f"Name: {info.name}\n", style="bold cyan")
    
    # Show plugin type
    plugin_type = manager.get_plugin_type(plugin_name)
    type_str = plugin_type.value.title() if plugin_type else "Unknown"
    info_text.append(f"Type: {type_str}\n", style="blue")
    
    info_text.append(f"Version: {info.version}\n", style="magenta")
    info_text.append(f"Author: {info.author}\n", style="white")
    info_text.append(f"Description: {info.description}\n", style="white")
    
    if info.homepage:
        info_text.append(f"Homepage: {info.homepage}\n", style="blue")
    
    info_text.append(f"Status: {'Enabled' if plugin.is_enabled() else 'Disabled'}\n", 
                    style="green" if plugin.is_enabled() else "red")
    
    info_text.append(f"Requires Pandas: {'Yes' if info.requires_pandas else 'No'}\n", style="yellow")
    info_text.append(f"Requires Cache: {'Yes' if info.requires_cache else 'No'}\n", style="yellow")
    
    # Show different information based on plugin type
    if isinstance(plugin, BaseScriptPlugin):
        info_text.append("Plugin Type: Script Plugin\n", style="bold green")
        info_text.append("Execution: Can be run as standalone script\n", style="dim")
    else:
        if info.supported_hooks:
            info_text.append("Supported Hooks:\n", style="bold")
            for hook in info.supported_hooks:
                info_text.append(f"  • {hook.value}\n", style="dim")
        else:
            info_text.append("Supported Hooks: None\n", style="dim")
    
    # Show plugin file path
    if plugin_name in manager.plugin_paths:
        info_text.append(f"\nFile: {manager.plugin_paths[plugin_name]}", style="dim")
    
    panel = Panel(info_text, title=f"Plugin Information", border_style=get_color('primary'))
    console.print(panel)


@app.command()
def enable(
    plugin_name: str = typer.Argument(..., help="Plugin name to enable")
):
    """Enable a plugin"""
    manager = get_plugin_manager()
    
    if manager.enable_plugin(plugin_name):
        Message.success(f"Plugin '{plugin_name}' enabled", console)
    else:
        Message.error(f"Plugin '{plugin_name}' not found", console)
        raise typer.Exit(1)


@app.command()
def disable(
    plugin_name: str = typer.Argument(..., help="Plugin name to disable")
):
    """Disable a plugin"""
    manager = get_plugin_manager()
    
    if manager.disable_plugin(plugin_name):
        Message.warning(f"Plugin '{plugin_name}' disabled", console)
    else:
        Message.error(f"Plugin '{plugin_name}' not found", console)
        raise typer.Exit(1)


@app.command()
def reload(
    plugin_name: str = typer.Argument(..., help="Plugin name to reload")
):
    """Reload a plugin from file"""
    manager = get_plugin_manager()
    
    if manager.reload_plugin(plugin_name):
        Message.success(f"Plugin '{plugin_name}' reloaded", console)
    else:
        Message.error(f"Failed to reload plugin '{plugin_name}'", console)
        raise typer.Exit(1)


@app.command()
def install(
    plugin_file: Path = typer.Argument(..., help="Path to plugin file to install"),
    name: Optional[str] = typer.Option(None, "--name", help="Custom plugin name (defaults to filename)")
):
    """Install a plugin from file"""
    manager = get_plugin_manager()
    
    if not plugin_file.exists():
        Message.error(f"Plugin file not found: {plugin_file}", console)
        raise typer.Exit(1)
    
    # Determine target name
    target_name = name or plugin_file.stem
    target_path = manager.plugin_dir / f"{target_name}.py"
    
    if target_path.exists():
        Message.warning(f"Plugin file already exists: {target_path}", console)
        if not typer.confirm("Overwrite existing plugin?", default=False):
            Message.info("Installation cancelled", console)
            return
    
    try:
        # Copy plugin file
        shutil.copy2(plugin_file, target_path)
        Message.success(f"Plugin file copied to: {target_path}", console)
        
        # Try to load the plugin
        plugin = manager.load_plugin_from_file(target_path)
        if plugin:
            Message.success(f"Plugin '{plugin.plugin_info.name}' installed and loaded successfully", console)
        else:
            Message.error("Plugin file copied but failed to load", console)
            
    except Exception as e:
        Message.error(f"Failed to install plugin: {e}", console)
        raise typer.Exit(1)


@app.command()
def uninstall(
    plugin_name: str = typer.Argument(..., help="Plugin name to uninstall"),
    force: bool = typer.Option(False, "--force", help="Force uninstall without confirmation")
):
    """Uninstall a plugin"""
    manager = get_plugin_manager()
    
    if plugin_name not in manager.plugins:
        Message.error(f"Plugin '{plugin_name}' not found", console)
        raise typer.Exit(1)
    
    if not force:
        if not typer.confirm(f"Are you sure you want to uninstall plugin '{plugin_name}'?", default=False):
            Message.info("Uninstall cancelled", console)
            return
    
    try:
        # Get plugin file path
        plugin_path = manager.plugin_paths.get(plugin_name)
        
        # Unload plugin
        if manager.unload_plugin(plugin_name):
            Message.success(f"Plugin '{plugin_name}' unloaded", console)
        
        # Remove plugin file
        if plugin_path and plugin_path.exists():
            plugin_path.unlink()
            Message.success(f"Plugin file removed: {plugin_path}", console)
        
        Message.success(f"Plugin '{plugin_name}' uninstalled successfully", console)
        
    except Exception as e:
        Message.error(f"Failed to uninstall plugin: {e}", console)
        raise typer.Exit(1)


@app.command()
def run(
    plugin_name: str = typer.Argument(..., help="Plugin name to run"),
    command: Optional[str] = typer.Argument(None, help="Plugin command to execute (for hook plugins)"),
    bag_path: Optional[Path] = typer.Option(None, "--bag", help="Bag file path for plugin operation"),
    topics: Optional[List[str]] = typer.Option(None, "--topics", "-t", help="Topics to process"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Run a plugin command or execute a script plugin"""
    manager = get_plugin_manager()
    plugin = manager.get_any_plugin(plugin_name)
    
    if not plugin:
        Message.error(f"Plugin '{plugin_name}' not found", console)
        raise typer.Exit(1)
    
    if not plugin.is_enabled():
        Message.error(f"Plugin '{plugin_name}' is disabled", console)
        raise typer.Exit(1)
    
    plugin_type = manager.get_plugin_type(plugin_name)
    
    if plugin_type == PluginType.SCRIPT:
        # Execute script plugin
        args = {
            'bag_path': bag_path,
            'topics': topics or [],
            'output': output,
        }
        
        success = manager.execute_script_plugin(plugin_name, args, console)
        if success:
            Message.success(f"Script plugin '{plugin_name}' completed successfully", console)
        else:
            Message.error(f"Script plugin '{plugin_name}' execution failed", console)
            raise typer.Exit(1)
        return
    
    # Handle hook plugin CLI commands
    hook_plugin = manager.get_plugin(plugin_name)
    
    # Get plugin CLI commands
    cli_commands = plugin.get_cli_commands()
    
    if not cli_commands:
        Message.error(f"Plugin '{plugin_name}' does not provide CLI commands", console)
        raise typer.Exit(1)
    
    if command is None:
        # List available commands
        Message.info(f"Available commands for plugin '{plugin_name}':", console)
        for cmd_name in cli_commands.keys():
            console.print(f"  • {cmd_name}")
        return
    
    if command not in cli_commands:
        Message.error(f"Command '{command}' not found in plugin '{plugin_name}'", console)
        Message.info(f"Available commands: {', '.join(cli_commands.keys())}", console)
        raise typer.Exit(1)
    
    try:
        # Prepare context
        context = {
            'bag_path': bag_path,
            'topics': topics or [],
            'output': output,
            'console': console
        }
        
        # Execute plugin command
        cmd_func = cli_commands[command]
        result = cmd_func(context)
        
        if result:
            Message.success(f"Plugin command '{plugin_name}:{command}' completed successfully", console)
        
    except Exception as e:
        Message.error(f"Plugin command failed: {e}", console)
        raise typer.Exit(1)


@app.command()
def create(
    name: str = typer.Argument(..., help="Plugin name"),
    template: str = typer.Option("basic", "--template", help="Plugin template (basic, data_processor, hook_example, script_basic, script_analyzer)")
):
    """Create a new plugin from template"""
    manager = get_plugin_manager()
    
    plugin_path = manager.plugin_dir / f"{name}.py"
    if plugin_path.exists():
        Message.error(f"Plugin file already exists: {plugin_path}", console)
        raise typer.Exit(1)
    
    # Generate plugin template
    template_content = _generate_plugin_template(name, template)
    
    try:
        plugin_path.write_text(template_content)
        Message.success(f"Plugin template created: {plugin_path}", console)
        Message.info(f"Edit the file to implement your plugin functionality", console)
        
        # Try to load the new plugin
        plugin = manager.load_plugin_from_file(plugin_path)
        if plugin:
            Message.success(f"Plugin '{name}' loaded successfully", console)
        
    except Exception as e:
        Message.error(f"Failed to create plugin: {e}", console)
        raise typer.Exit(1)


def _generate_plugin_template(name: str, template: str) -> str:
    """Generate plugin template code"""
    
    if template == "basic":
        return f'''"""
{name} plugin for Rose bag processing tool
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from roseApp.core.plugins import BasePlugin, PluginInfo, HookType


class {name.title()}Plugin(BasePlugin):
    """Basic plugin template"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="{name}",
            version="1.0.0",
            description="A basic Rose plugin",
            author="Your Name",
            homepage="https://github.com/your-username/rose-{name}-plugin",
            requires_pandas=False,
            requires_cache=True,
            supported_hooks=[HookType.AFTER_LOAD]
        )
    
    def initialize(self) -> bool:
        """Initialize the plugin"""
        print(f"Initializing {{self.plugin_info.name}} plugin...")
        
        # Register hooks
        self.register_hook(HookType.AFTER_LOAD, self.on_bag_loaded)
        
        return True
    
    def on_bag_loaded(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called after a bag file is loaded"""
        bag_path = context.get('bag_path')
        print(f"{{self.plugin_info.name}}: Bag loaded - {{bag_path}}")
        return context
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """Return custom CLI commands"""
        return {{
            "hello": self.hello_command,
            "process": self.process_command
        }}
    
    def hello_command(self, context: Dict[str, Any]) -> bool:
        """Simple hello command"""
        console = context.get('console')
        if console:
            console.print(f"[green]Hello from {{self.plugin_info.name}} plugin![/green]")
        return True
    
    def process_command(self, context: Dict[str, Any]) -> bool:
        """Process bag data command"""
        bag_path = context.get('bag_path')
        topics = context.get('topics', [])
        console = context.get('console')
        
        if not bag_path:
            if console:
                console.print("[red]No bag file specified[/red]")
            return False
        
        # Use data interface to access bag data
        data_interface = self.get_data_interface()
        if data_interface:
            bag_info = data_interface.get_bag_info(bag_path)
            if bag_info:
                if console:
                    console.print(f"[green]Processing bag: {{bag_path}}[/green]")
                    console.print(f"Topics: {{len(bag_info.topics)}}")
                return True
        
        if console:
            console.print("[red]Failed to access bag data[/red]")
        return False
'''
    
    elif template == "data_processor":
        return f'''"""
{name} data processing plugin for Rose
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from roseApp.core.plugins import BasePlugin, PluginInfo, HookType

logger = logging.getLogger(__name__)


class {name.title()}DataPlugin(BasePlugin):
    """Data processing plugin template"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="{name}",
            version="1.0.0",
            description="A data processing plugin for Rose",
            author="Your Name",
            requires_pandas=True,
            requires_cache=True,
            supported_hooks=[HookType.AFTER_LOAD, HookType.BEFORE_EXPORT]
        )
    
    def initialize(self) -> bool:
        """Initialize the plugin"""
        if not PANDAS_AVAILABLE:
            logger.error("Pandas is required for this plugin")
            return False
        
        # Register hooks
        self.register_hook(HookType.AFTER_LOAD, self.analyze_data)
        self.register_hook(HookType.BEFORE_EXPORT, self.preprocess_data)
        
        logger.info(f"{{self.plugin_info.name}} data plugin initialized")
        return True
    
    def analyze_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze bag data after loading"""
        bag_path = context.get('bag_path')
        if not bag_path:
            return context
        
        data_interface = self.get_data_interface()
        if data_interface and data_interface.has_dataframes(bag_path):
            topics = data_interface.get_topics(bag_path)
            logger.info(f"{{self.plugin_info.name}}: Analyzed {{len(topics)}} topics in {{bag_path}}")
            
            # Add analysis results to context
            context['plugin_analysis'] = {{
                'plugin': self.plugin_info.name,
                'topics_analyzed': len(topics),
                'has_dataframes': True
            }}
        
        return context
    
    def preprocess_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess data before export"""
        bag_path = context.get('bag_path')
        topics = context.get('topics', [])
        
        if bag_path and topics:
            logger.info(f"{{self.plugin_info.name}}: Preprocessing {{len(topics)}} topics")
            # Add preprocessing info to context
            context['preprocessing'] = {{
                'plugin': self.plugin_info.name,
                'processed_topics': topics
            }}
        
        return context
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """Return data processing commands"""
        return {{
            "analyze": self.analyze_command,
            "export_custom": self.export_custom_command
        }}
    
    def analyze_command(self, context: Dict[str, Any]) -> bool:
        """Analyze bag data"""
        bag_path = context.get('bag_path')
        console = context.get('console')
        
        if not bag_path:
            if console:
                console.print("[red]No bag file specified[/red]")
            return False
        
        data_interface = self.get_data_interface()
        if data_interface:
            stats = data_interface.get_bag_statistics(bag_path)
            if stats and console:
                console.print(f"[green]Bag Analysis by {{self.plugin_info.name}}:[/green]")
                console.print(f"  File: {{stats.get('file_path')}}")
                console.print(f"  Size: {{stats.get('file_size_mb', 0):.2f}} MB")
                console.print(f"  Topics: {{stats.get('topics_count', 0)}}")
                console.print(f"  Messages: {{stats.get('total_messages', 0)}}")
                console.print(f"  Duration: {{stats.get('duration_seconds', 0):.2f}}s")
                return True
        
        if console:
            console.print("[red]Failed to analyze bag data[/red]")
        return False
    
    def export_custom_command(self, context: Dict[str, Any]) -> bool:
        """Export data in custom format"""
        bag_path = context.get('bag_path')
        topics = context.get('topics', [])
        output = context.get('output')
        console = context.get('console')
        
        if not all([bag_path, topics, output]):
            if console:
                console.print("[red]Missing required parameters: bag_path, topics, output[/red]")
            return False
        
        data_interface = self.get_data_interface()
        if data_interface:
            # Get DataFrames for topics
            dataframes = data_interface.get_multiple_dataframes(bag_path, topics)
            if dataframes:
                # Merge dataframes
                merged_df = data_interface.merge_dataframes(dataframes)
                
                # Export using custom logic
                success = data_interface.export_to_csv(merged_df, output)
                if success and console:
                    console.print(f"[green]Custom export completed: {{output}}[/green]")
                return success
        
        if console:
            console.print("[red]Failed to export data[/red]")
        return False
'''
    
    elif template == "hook_example":
        return f'''"""
{name} hook example plugin for Rose
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import logging

from roseApp.core.plugins import BasePlugin, PluginInfo, HookType

logger = logging.getLogger(__name__)


class {name.title()}HookPlugin(BasePlugin):
    """Example plugin demonstrating hook usage"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="{name}",
            version="1.0.0",
            description="Example plugin showing hook usage",
            author="Your Name",
            requires_pandas=False,
            requires_cache=True,
            supported_hooks=[
                HookType.BEFORE_LOAD,
                HookType.AFTER_LOAD,
                HookType.BEFORE_INSPECT,
                HookType.AFTER_INSPECT,
                HookType.BEFORE_EXTRACT,
                HookType.AFTER_EXTRACT
            ]
        )
    
    def initialize(self) -> bool:
        """Initialize and register all hooks"""
        # Register hooks for different operations
        self.register_hook(HookType.BEFORE_LOAD, self.before_load_hook)
        self.register_hook(HookType.AFTER_LOAD, self.after_load_hook)
        self.register_hook(HookType.BEFORE_INSPECT, self.before_inspect_hook)
        self.register_hook(HookType.AFTER_INSPECT, self.after_inspect_hook)
        self.register_hook(HookType.BEFORE_EXTRACT, self.before_extract_hook)
        self.register_hook(HookType.AFTER_EXTRACT, self.after_extract_hook)
        
        logger.info(f"{{self.plugin_info.name}} hook plugin initialized with {{len(self.plugin_info.supported_hooks)}} hooks")
        return True
    
    def before_load_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called before loading a bag file"""
        bag_path = context.get('bag_path')
        logger.info(f"{{self.plugin_info.name}}: About to load bag {{bag_path}}")
        
        # You can modify context or perform pre-processing
        context['plugin_metadata'] = {{
            'processed_by': self.plugin_info.name,
            'hook_type': 'before_load'
        }}
        return context
    
    def after_load_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called after loading a bag file"""
        bag_path = context.get('bag_path')
        logger.info(f"{{self.plugin_info.name}}: Bag loaded {{bag_path}}")
        
        # Access loaded data through data interface
        data_interface = self.get_data_interface()
        if data_interface:
            stats = data_interface.get_bag_statistics(bag_path)
            logger.info(f"{{self.plugin_info.name}}: Loaded bag has {{stats.get('topics_count', 0)}} topics")
        
        return context
    
    def before_inspect_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called before inspecting a bag file"""
        logger.info(f"{{self.plugin_info.name}}: Before inspect operation")
        return context
    
    def after_inspect_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called after inspecting a bag file"""
        logger.info(f"{{self.plugin_info.name}}: After inspect operation")
        return context
    
    def before_extract_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called before extracting topics"""
        topics = context.get('topics', [])
        logger.info(f"{{self.plugin_info.name}}: About to extract {{len(topics)}} topics")
        return context
    
    def after_extract_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called after extracting topics"""
        output_path = context.get('output_path')
        logger.info(f"{{self.plugin_info.name}}: Extraction completed to {{output_path}}")
        return context
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """Return hook-related commands"""
        return {{
            "status": self.status_command,
            "test_hooks": self.test_hooks_command
        }}
    
    def status_command(self, context: Dict[str, Any]) -> bool:
        """Show hook plugin status"""
        console = context.get('console')
        if console:
            console.print(f"[green]{{self.plugin_info.name}} Hook Plugin Status:[/green]")
            console.print(f"  Registered hooks: {{len(self._hooks)}}")
            for hook_type, callbacks in self._hooks.items():
                console.print(f"    • {{hook_type.value}}: {{len(callbacks)}} callback(s)")
        return True
    
    def test_hooks_command(self, context: Dict[str, Any]) -> bool:
        """Test hook execution"""
        console = context.get('console')
        if console:
            console.print(f"[yellow]Testing hooks for {{self.plugin_info.name}}...[/yellow]")
            
            # Simulate hook execution
            test_context = {{'test': True, 'plugin': self.plugin_info.name}}
            for hook_type in self.plugin_info.supported_hooks:
                callbacks = self.get_hooks(hook_type)
                if callbacks:
                    console.print(f"  Testing {{hook_type.value}}: {{len(callbacks)}} callback(s)")
        return True
'''
    
    elif template == "script_basic":
        return f'''"""
{name} script plugin for Rose
"""

from pathlib import Path
from typing import Dict, Any
from roseApp.core.plugins import BaseScriptPlugin, PluginInfo, ScriptContext


class {name.title()}ScriptPlugin(BaseScriptPlugin):
    """Basic script plugin template"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="{name}",
            version="1.0.0",
            description="A basic Rose script plugin",
            author="Your Name",
            requires_pandas=False,
            requires_cache=True
        )
    
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """
        Main script execution
        
        Args:
            context: ScriptContext with Rose functions
            args: Command line arguments
            
        Returns:
            bool: True if successful
        """
        context.print(f"[green]Hello from {{self.plugin_info.name}} script plugin![/green]")
        
        # Get bag file from arguments
        bag_path = args.get('bag_path')
        if not bag_path:
            context.print("[yellow]No bag file specified. Usage: --bag path/to/file.bag[/yellow]")
            return True
        
        # Load bag file
        context.print(f"[cyan]Loading bag file: {{bag_path}}[/cyan]")
        if not context.load_bag(bag_path):
            context.print("[red]Failed to load bag file[/red]")
            return False
        
        # Get topics
        topics = context.get_topics()
        context.print(f"[green]Found {{len(topics)}} topics in bag file[/green]")
        
        # Display topics
        for i, topic in enumerate(topics[:10], 1):  # Show first 10
            context.print(f"  {{i:2d}}. {{topic}}")
        
        if len(topics) > 10:
            context.print(f"  ... and {{len(topics) - 10}} more topics")
        
        # Get bag statistics
        bag_info = context.get_bag_info()
        if bag_info:
            context.print(f"\\n[bold]Bag Statistics:[/bold]")
            context.print(f"  File size: {{bag_info.file_size_mb:.2f}} MB")
            context.print(f"  Duration: {{bag_info.duration_seconds:.2f}} seconds")
            context.print(f"  Total messages: {{bag_info.total_messages}}")
        
        return True
'''
    
    elif template == "script_analyzer":
        return f'''"""
{name} data analysis script plugin for Rose
"""

from pathlib import Path
from typing import Dict, Any, List
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from roseApp.core.plugins import BaseScriptPlugin, PluginInfo, ScriptContext

logger = logging.getLogger(__name__)


class {name.title()}AnalyzerPlugin(BaseScriptPlugin):
    """Data analysis script plugin"""
    
    @property
    def plugin_info(self) -> PluginInfo:
        return PluginInfo(
            name="{name}",
            version="1.0.0",
            description="Data analysis script for Rose bag files",
            author="Your Name",
            requires_pandas=True,
            requires_cache=True
        )
    
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """
        Main data analysis script
        """
        if not PANDAS_AVAILABLE:
            context.print("[red]Pandas is required for this plugin[/red]")
            return False
        
        bag_path = args.get('bag_path')
        if not bag_path:
            context.print("[yellow]No bag file specified. Usage: --bag path/to/file.bag[/yellow]")
            return True
        
        # Load bag
        context.print(f"[cyan]Analyzing bag file: {{bag_path}}[/cyan]")
        if not context.load_bag(bag_path):
            context.print("[red]Failed to load bag file[/red]")
            return False
        
        # Interactive topic selection
        selected_topics = self.select_topics_for_analysis(context)
        if not selected_topics:
            context.print("[yellow]No topics selected for analysis[/yellow]")
            return True
        
        # Analyze each topic
        analysis_results = []
        for topic in selected_topics:
            context.print(f"[cyan]Analyzing topic: {{topic}}[/cyan]")
            result = self.analyze_topic(context, topic)
            if result:
                analysis_results.append(result)
        
        # Display results
        self.display_analysis_results(context, analysis_results)
        
        # Save results if requested
        output_path = args.get('output')
        if output_path:
            self.save_results(context, analysis_results, output_path)
        
        return True
    
    def select_topics_for_analysis(self, context: ScriptContext) -> List[str]:
        """Interactive topic selection for analysis"""
        all_topics = context.get_topics()
        
        # Filter for numeric topics (likely sensor data)
        numeric_topics = []
        for topic in all_topics:
            df = context.get_dataframe(topic)
            if df is not None and len(df) > 0:
                # Check if topic has numeric columns
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    numeric_topics.append(topic)
        
        if not numeric_topics:
            context.print("[yellow]No topics with numeric data found[/yellow]")
            return []
        
        context.print(f"\\n[bold]Topics with numeric data ({{len(numeric_topics)}}):[/bold]")
        for i, topic in enumerate(numeric_topics, 1):
            context.print(f"  {{i:2d}}. {{topic}}")
        
        # Ask user for selection
        selection = context.ask_user("Enter topic numbers (comma-separated) or 'all'", "all")
        
        if selection.lower() == "all":
            return numeric_topics
        
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            return [numeric_topics[i] for i in indices if 0 <= i < len(numeric_topics)]
        except (ValueError, IndexError):
            context.print("[yellow]Invalid selection, using all topics[/yellow]")
            return numeric_topics
    
    def analyze_topic(self, context: ScriptContext, topic: str) -> Dict[str, Any]:
        """Analyze a single topic"""
        df = context.get_dataframe(topic)
        if df is None or len(df) == 0:
            return None
        
        # Basic statistics
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) == 0:
            return None
        
        stats = {{
            'topic': topic,
            'message_count': len(df),
            'numeric_columns': len(numeric_cols),
            'time_span': self.calculate_time_span(df),
            'column_stats': {{}}
        }}
        
        # Analyze each numeric column
        for col in numeric_cols[:5]:  # Limit to first 5 columns
            col_stats = {{
                'mean': df[col].mean(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'null_count': df[col].isnull().sum()
            }}
            stats['column_stats'][col] = col_stats
        
        return stats
    
    def calculate_time_span(self, df) -> float:
        """Calculate time span of data"""
        if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
            try:
                return float(df.index.max() - df.index.min())
            except:
                pass
        return 0.0
    
    def display_analysis_results(self, context: ScriptContext, results: List[Dict[str, Any]]):
        """Display analysis results"""
        if not results:
            return
        
        context.print("\\n[bold green]Analysis Results:[/bold green]")
        
        # Create summary table
        table_data = []
        for result in results:
            table_data.append({{
                'Topic': result['topic'],
                'Messages': result['message_count'],
                'Columns': result['numeric_columns'],
                'Time Span': f"{{result['time_span']:.1f}}s"
            }})
        
        context.print_table(table_data, "Topic Analysis Summary")
        
        # Show detailed stats for each topic
        for result in results:
            context.print(f"\\n[cyan]Detailed stats for {{result['topic']}}:[/cyan]")
            for col, stats in result['column_stats'].items():
                context.print(f"  {{col}}:")
                context.print(f"    Mean: {{stats['mean']:.3f}}")
                context.print(f"    Std:  {{stats['std']:.3f}}")
                context.print(f"    Range: [{{stats['min']:.3f}}, {{stats['max']:.3f}}]")
                if stats['null_count'] > 0:
                    context.print(f"    Nulls: {{stats['null_count']}}")
    
    def save_results(self, context: ScriptContext, results: List[Dict[str, Any]], output_path: Path):
        """Save analysis results to file"""
        try:
            import json
            
            # Convert results to JSON-serializable format
            json_results = []
            for result in results:
                json_result = result.copy()
                # Convert numpy types to Python types
                for col, stats in json_result['column_stats'].items():
                    for key, value in stats.items():
                        if hasattr(value, 'item'):
                            stats[key] = value.item()
                json_results.append(json_result)
            
            with open(output_path, 'w') as f:
                json.dump(json_results, f, indent=2)
            
            context.print(f"[green]Results saved to {{output_path}}[/green]")
            
        except Exception as e:
            context.print(f"[red]Failed to save results: {{e}}[/red]")
'''
    
    else:
        # Default to basic template
        return _generate_plugin_template(name, "basic")
