"""
Plugin system for Rose bag processing tool
"""

from .base import BasePlugin, PluginInfo, HookType
from .script_base import BaseScriptPlugin, ScriptContext, PluginType
from .manager import PluginManager, get_plugin_manager
from .data_interface import DataInterface, PluginDataContext

__all__ = [
    'BasePlugin',
    'BaseScriptPlugin',
    'PluginInfo', 
    'HookType',
    'PluginType',
    'ScriptContext',
    'PluginManager',
    'get_plugin_manager',
    'DataInterface',
    'PluginDataContext'
]
