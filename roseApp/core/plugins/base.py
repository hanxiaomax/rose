"""
Base plugin class and interfaces for Rose plugin system
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HookType(Enum):
    """Types of hooks that plugins can register for"""
    BEFORE_LOAD = "before_load"
    AFTER_LOAD = "after_load"
    BEFORE_INSPECT = "before_inspect"
    AFTER_INSPECT = "after_inspect"
    BEFORE_EXTRACT = "before_extract"
    AFTER_EXTRACT = "after_extract"
    BEFORE_EXPORT = "before_export"
    AFTER_EXPORT = "after_export"
    BEFORE_COMPRESS = "before_compress"
    AFTER_COMPRESS = "after_compress"


@dataclass
class PluginInfo:
    """Plugin metadata information"""
    name: str
    version: str
    description: str
    author: str
    homepage: Optional[str] = None
    requires_pandas: bool = False
    requires_cache: bool = True
    supported_hooks: List[HookType] = None
    
    def __post_init__(self):
        if self.supported_hooks is None:
            self.supported_hooks = []


class BasePlugin(ABC):
    """
    Base class for all Rose plugins
    
    Plugins can:
    1. Register hooks to be called before/after Rose operations
    2. Access bag data through DataInterface
    3. Provide custom CLI commands
    4. Export/import custom data formats
    """
    
    def __init__(self):
        self._plugin_info: Optional[PluginInfo] = None
        self._data_interface: Optional['DataInterface'] = None
        self._hooks: Dict[HookType, List[Callable]] = {}
        self._enabled = True
    
    @property
    @abstractmethod
    def plugin_info(self) -> PluginInfo:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    def cleanup(self) -> None:
        """Clean up plugin resources"""
        pass
    
    def set_data_interface(self, data_interface: 'DataInterface') -> None:
        """Set the data interface for accessing Rose data"""
        self._data_interface = data_interface
    
    def get_data_interface(self) -> Optional['DataInterface']:
        """Get the data interface"""
        return self._data_interface
    
    def register_hook(self, hook_type: HookType, callback: Callable) -> None:
        """
        Register a hook callback
        
        Args:
            hook_type: Type of hook to register for
            callback: Function to call when hook is triggered
        """
        if hook_type not in self._hooks:
            self._hooks[hook_type] = []
        self._hooks[hook_type].append(callback)
        logger.debug(f"Plugin {self.plugin_info.name} registered hook {hook_type.value}")
    
    def get_hooks(self, hook_type: HookType) -> List[Callable]:
        """Get all registered hooks for a specific type"""
        return self._hooks.get(hook_type, [])
    
    def get_all_hooks(self) -> Dict[HookType, List[Callable]]:
        """Get all registered hooks"""
        return self._hooks.copy()
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled"""
        return self._enabled
    
    def enable(self) -> None:
        """Enable the plugin"""
        self._enabled = True
        logger.info(f"Plugin {self.plugin_info.name} enabled")
    
    def disable(self) -> None:
        """Disable the plugin"""
        self._enabled = False
        logger.info(f"Plugin {self.plugin_info.name} disabled")
    
    def validate_requirements(self) -> bool:
        """
        Validate that plugin requirements are met
        
        Returns:
            bool: True if all requirements are satisfied
        """
        try:
            if self.plugin_info.requires_pandas:
                import pandas as pd
                logger.debug(f"Plugin {self.plugin_info.name}: pandas requirement satisfied")
            
            if self.plugin_info.requires_cache:
                # Check if cache system is available
                from ..cache import create_bag_cache_manager
                cache_manager = create_bag_cache_manager()
                logger.debug(f"Plugin {self.plugin_info.name}: cache requirement satisfied")
            
            return True
        except ImportError as e:
            logger.error(f"Plugin {self.plugin_info.name} requirements not met: {e}")
            return False
    
    # Optional methods that plugins can override
    
    def on_load(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called when plugin is loaded
        
        Args:
            context: Context information
            
        Returns:
            Dict with any modifications to context
        """
        return context
    
    def on_unload(self, context: Dict[str, Any]) -> None:
        """Called when plugin is unloaded"""
        pass
    
    def get_cli_commands(self) -> Optional[Dict[str, Callable]]:
        """
        Return custom CLI commands provided by this plugin
        
        Returns:
            Dict mapping command names to callable functions, or None
        """
        return None
    
    def process_bag_data(self, bag_path: Path, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process bag data and return results
        
        Args:
            bag_path: Path to the bag file
            context: Processing context
            
        Returns:
            Dict with processing results
        """
        return {}
    
    def export_data(self, data: Any, output_path: Path, format_type: str = "csv") -> bool:
        """
        Export data in custom format
        
        Args:
            data: Data to export (usually pandas DataFrame)
            output_path: Output file path
            format_type: Format type (csv, json, parquet, etc.)
            
        Returns:
            bool: True if export successful
        """
        return False
    
    def import_data(self, input_path: Path, format_type: str = "csv") -> Any:
        """
        Import data from custom format
        
        Args:
            input_path: Input file path
            format_type: Format type
            
        Returns:
            Imported data (usually pandas DataFrame)
        """
        return None


class PluginError(Exception):
    """Base exception for plugin-related errors"""
    pass


class PluginLoadError(PluginError):
    """Raised when plugin fails to load"""
    pass


class PluginValidationError(PluginError):
    """Raised when plugin validation fails"""
    pass
