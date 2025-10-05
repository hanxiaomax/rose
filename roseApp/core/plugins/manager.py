"""
Plugin manager for loading, managing and executing plugins
"""

import os
import sys
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Type
import logging

from .base import BasePlugin, PluginInfo, HookType, PluginError, PluginLoadError
from .script_base import BaseScriptPlugin, ScriptContext, PluginType
from .data_interface import DataInterface
from ..directories import get_rose_directories

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages loading, registration, and execution of plugins
    """
    
    def __init__(self):
        self.hook_plugins: Dict[str, BasePlugin] = {}
        self.script_plugins: Dict[str, BaseScriptPlugin] = {}
        self.plugin_paths: Dict[str, Path] = {}
        self.plugin_types: Dict[str, PluginType] = {}
        self.data_interface = DataInterface()
        self.hooks: Dict[HookType, List[Callable]] = {}
        self._initialized = False
        
        # Get plugin directory from Rose directories
        rose_dirs = get_rose_directories()
        self.plugin_dir = rose_dirs.cache_dir / "plugins"
        self.plugin_dir.mkdir(exist_ok=True)
        
        logger.debug(f"PluginManager initialized with plugin directory: {self.plugin_dir}")
    
    def initialize(self) -> None:
        """Initialize the plugin manager and discover plugins"""
        if self._initialized:
            return
        
        self.discover_plugins()
        self.load_all_plugins()
        self._initialized = True
        total_plugins = len(self.hook_plugins) + len(self.script_plugins)
        logger.info(f"PluginManager initialized with {total_plugins} plugins ({len(self.hook_plugins)} hook, {len(self.script_plugins)} script)")
    
    def discover_plugins(self) -> List[Path]:
        """
        Discover plugin files in the plugin directory
        
        Returns:
            List of plugin file paths
        """
        plugin_files = []
        
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory does not exist: {self.plugin_dir}")
            return plugin_files
        
        # Look for Python files in plugin directory
        for file_path in self.plugin_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue  # Skip __init__.py, __pycache__, etc.
            
            plugin_files.append(file_path)
            logger.debug(f"Discovered plugin file: {file_path}")
        
        # Look for plugin directories with __init__.py
        for dir_path in self.plugin_dir.iterdir():
            if dir_path.is_dir() and (dir_path / "__init__.py").exists():
                plugin_files.append(dir_path / "__init__.py")
                logger.debug(f"Discovered plugin directory: {dir_path}")
        
        return plugin_files
    
    def load_plugin_from_file(self, plugin_path: Path) -> Optional[BasePlugin]:
        """
        Load a single plugin from file
        
        Args:
            plugin_path: Path to plugin file
            
        Returns:
            BasePlugin instance if successful, None otherwise
        """
        try:
            # Generate module name
            module_name = f"rose_plugin_{plugin_path.stem}"
            
            # Load module from file
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {plugin_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class (should inherit from BasePlugin or BaseScriptPlugin)
            hook_plugin_class = None
            script_plugin_class = None
            
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BasePlugin) and 
                    obj is not BasePlugin and 
                    not inspect.isabstract(obj)):
                    hook_plugin_class = obj
                elif (issubclass(obj, BaseScriptPlugin) and 
                      obj is not BaseScriptPlugin and 
                      not inspect.isabstract(obj)):
                    script_plugin_class = obj
            
            # Determine plugin type and class
            if hook_plugin_class and script_plugin_class:
                raise PluginLoadError(f"Plugin file {plugin_path} contains both hook and script plugin classes")
            elif hook_plugin_class:
                plugin_class = hook_plugin_class
                plugin_type = PluginType.HOOK
            elif script_plugin_class:
                plugin_class = script_plugin_class
                plugin_type = PluginType.SCRIPT
            else:
                raise PluginLoadError(f"No valid plugin class found in {plugin_path}")
            
            # Create plugin instance
            plugin_instance = plugin_class()
            
            # Validate plugin
            if not plugin_instance.validate_requirements():
                raise PluginLoadError(f"Plugin requirements not satisfied for {plugin_path}")
            
            # Initialize plugin
            if not plugin_instance.initialize():
                raise PluginLoadError(f"Plugin initialization failed for {plugin_path}")
            
            # Register plugin based on type
            plugin_name = plugin_instance.plugin_info.name
            self.plugin_paths[plugin_name] = plugin_path
            self.plugin_types[plugin_name] = plugin_type
            
            if plugin_type == PluginType.HOOK:
                # Hook plugin setup
                plugin_instance.set_data_interface(self.data_interface)
                self.hook_plugins[plugin_name] = plugin_instance
                self._register_plugin_hooks(plugin_instance)
                
            elif plugin_type == PluginType.SCRIPT:
                # Script plugin setup
                script_context = ScriptContext(self.data_interface)
                plugin_instance.set_context(script_context)
                self.script_plugins[plugin_name] = plugin_instance
            
            logger.info(f"Successfully loaded plugin: {plugin_name} from {plugin_path}")
            return plugin_instance
            
        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}")
            return None
    
    def load_all_plugins(self) -> None:
        """Load all discovered plugins"""
        plugin_files = self.discover_plugins()
        
        for plugin_path in plugin_files:
            try:
                self.load_plugin_from_file(plugin_path)
            except Exception as e:
                logger.error(f"Error loading plugin {plugin_path}: {e}")
    
    def _register_plugin_hooks(self, plugin: BasePlugin) -> None:
        """Register hooks from a plugin"""
        plugin_hooks = plugin.get_all_hooks()
        
        for hook_type, callbacks in plugin_hooks.items():
            if hook_type not in self.hooks:
                self.hooks[hook_type] = []
            
            for callback in callbacks:
                self.hooks[hook_type].append(callback)
                logger.debug(f"Registered hook {hook_type.value} from plugin {plugin.plugin_info.name}")
    
    def execute_hooks(self, hook_type: HookType, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all registered hooks of a specific type
        
        Args:
            hook_type: Type of hook to execute
            context: Context data to pass to hooks
            
        Returns:
            Modified context after all hooks have been executed
        """
        if hook_type not in self.hooks:
            return context
        
        for callback in self.hooks[hook_type]:
            try:
                result = callback(context)
                if isinstance(result, dict):
                    context.update(result)
                logger.debug(f"Executed hook {hook_type.value}")
            except Exception as e:
                logger.error(f"Error executing hook {hook_type.value}: {e}")
        
        return context
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get hook plugin by name"""
        return self.hook_plugins.get(name)
    
    def get_script_plugin(self, name: str) -> Optional[BaseScriptPlugin]:
        """Get script plugin by name"""
        return self.script_plugins.get(name)
    
    def get_any_plugin(self, name: str):
        """Get plugin of any type by name"""
        return self.hook_plugins.get(name) or self.script_plugins.get(name)
    
    def get_plugin_type(self, name: str) -> Optional[PluginType]:
        """Get plugin type by name"""
        return self.plugin_types.get(name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """Get list of all plugin information"""
        all_plugins = list(self.hook_plugins.values()) + list(self.script_plugins.values())
        return [plugin.plugin_info for plugin in all_plugins]
    
    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get list of enabled hook plugins"""
        return [plugin for plugin in self.hook_plugins.values() if plugin.is_enabled()]
    
    def get_enabled_script_plugins(self) -> List[BaseScriptPlugin]:
        """Get list of enabled script plugins"""
        return [plugin for plugin in self.script_plugins.values() if plugin.is_enabled()]
    
    def get_all_enabled_plugins(self):
        """Get all enabled plugins of both types"""
        return self.get_enabled_plugins() + self.get_enabled_script_plugins()
    
    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin by name"""
        plugin = self.get_any_plugin(name)
        if plugin:
            plugin.enable()
            return True
        return False
    
    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin by name"""
        plugin = self.get_any_plugin(name)
        if plugin:
            plugin.disable()
            return True
        return False
    
    def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin
        
        Args:
            name: Plugin name
            
        Returns:
            bool: True if successful
        """
        plugin_type = self.plugin_types.get(name)
        if not plugin_type:
            return False
        
        try:
            if plugin_type == PluginType.HOOK:
                plugin = self.hook_plugins.get(name)
                if plugin:
                    plugin.cleanup()
                    if hasattr(plugin, 'on_unload'):
                        plugin.on_unload({})
                    
                    # Remove from hooks
                    for hook_type, callbacks in self.hooks.items():
                        plugin_hooks = plugin.get_hooks(hook_type)
                        for hook in plugin_hooks:
                            if hook in callbacks:
                                callbacks.remove(hook)
                    
                    del self.hook_plugins[name]
                    
            elif plugin_type == PluginType.SCRIPT:
                plugin = self.script_plugins.get(name)
                if plugin:
                    plugin.cleanup()
                    del self.script_plugins[name]
            
            # Remove common data
            if name in self.plugin_paths:
                del self.plugin_paths[name]
            if name in self.plugin_types:
                del self.plugin_types[name]
            
            logger.info(f"Unloaded plugin: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {name}: {e}")
            return False
    
    def reload_plugin(self, name: str) -> bool:
        """
        Reload a plugin
        
        Args:
            name: Plugin name
            
        Returns:
            bool: True if successful
        """
        if name not in self.plugin_paths:
            logger.error(f"Cannot reload plugin {name}: path not found")
            return False
        
        plugin_path = self.plugin_paths[name]
        
        # Unload first
        if not self.unload_plugin(name):
            return False
        
        # Reload
        plugin = self.load_plugin_from_file(plugin_path)
        return plugin is not None
    
    def create_plugin_context(self, bag_path: Path, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Create context for plugin operations
        
        Args:
            bag_path: Path to bag file
            operation: Operation name
            **kwargs: Additional parameters
            
        Returns:
            Context dict
        """
        return {
            'bag_path': bag_path,
            'operation': operation,
            'data_interface': self.data_interface,
            'parameters': kwargs,
            'plugin_manager': self
        }
    
    def execute_script_plugin(self, name: str, args: Dict[str, Any], console=None) -> bool:
        """
        Execute a script plugin
        
        Args:
            name: Script plugin name
            args: Arguments to pass to script
            console: Rich console for output
            
        Returns:
            bool: True if execution successful
        """
        script_plugin = self.get_script_plugin(name)
        if not script_plugin:
            logger.error(f"Script plugin '{name}' not found")
            return False
        
        if not script_plugin.is_enabled():
            logger.error(f"Script plugin '{name}' is disabled")
            return False
        
        try:
            # Create script context with console
            script_context = ScriptContext(self.data_interface, console)
            script_plugin.set_context(script_context)
            
            # Execute script
            return script_plugin.run(script_context, args)
            
        except Exception as e:
            logger.error(f"Script plugin execution failed: {e}")
            return False
    
    def get_plugin_cli_commands(self) -> Dict[str, Callable]:
        """Get all CLI commands provided by hook plugins"""
        commands = {}
        
        for plugin in self.get_enabled_plugins():
            plugin_commands = plugin.get_cli_commands()
            if plugin_commands:
                for cmd_name, cmd_func in plugin_commands.items():
                    # Prefix with plugin name to avoid conflicts
                    full_cmd_name = f"{plugin.plugin_info.name}:{cmd_name}"
                    commands[full_cmd_name] = cmd_func
        
        return commands


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.initialize()
    return _plugin_manager


def execute_hooks(hook_type: HookType, context: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to execute hooks"""
    manager = get_plugin_manager()
    return manager.execute_hooks(hook_type, context)
