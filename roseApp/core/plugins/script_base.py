"""
Script plugin base class for Rose
Provides a simplified interface for writing script-like plugins
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
import sys

from .base import PluginInfo
from .data_interface import DataInterface

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """Types of plugins"""
    HOOK = "hook"        # Hook-based plugins that respond to events
    SCRIPT = "script"    # Script-based plugins that run independently


class ScriptContext:
    """
    Context object for script plugins providing Rose functions
    """
    
    def __init__(self, data_interface: DataInterface, console=None):
        self.data_interface = data_interface
        self.console = console
        self._current_bag = None
        self._current_topics = []
    
    def load_bag(self, bag_path: Union[str, Path], auto_load: bool = True) -> bool:
        """
        Load a bag file into Rose cache
        
        Args:
            bag_path: Path to bag file
            auto_load: Whether to auto-load if not in cache
            
        Returns:
            bool: True if bag is available in cache
        """
        if isinstance(bag_path, str):
            bag_path = Path(bag_path)
        
        self._current_bag = bag_path
        
        # Check if bag is cached
        if self.data_interface.is_bag_cached(bag_path):
            if self.console:
                self.console.print(f"[green]✓ Bag {bag_path.name} is already loaded[/green]")
            return True
        
        if auto_load:
            if self.console:
                self.console.print(f"[yellow]Loading bag file: {bag_path}...[/yellow]")
            
            # Use Rose's cache loading system
            from ...cli.util import check_and_load_bag_cache
            success = check_and_load_bag_cache(
                bag_path, 
                auto_load=True, 
                verbose=False, 
                build_index=True, 
                force_load=True
            )
            
            if success:
                if self.console:
                    self.console.print(f"[green]✓ Bag {bag_path.name} loaded successfully[/green]")
                return True
            else:
                if self.console:
                    self.console.print(f"[red]✗ Failed to load bag {bag_path.name}[/red]")
                return False
        else:
            if self.console:
                self.console.print(f"[yellow]Bag {bag_path.name} not in cache. Use auto_load=True to load it.[/yellow]")
            return False
    
    def get_bag_info(self, bag_path: Union[str, Path] = None):
        """Get bag information"""
        target_bag = Path(bag_path) if bag_path else self._current_bag
        if not target_bag:
            raise ValueError("No bag file specified")
        
        return self.data_interface.get_bag_info(target_bag)
    
    def get_topics(self, bag_path: Union[str, Path] = None) -> List[str]:
        """Get list of topics in bag"""
        target_bag = Path(bag_path) if bag_path else self._current_bag
        if not target_bag:
            raise ValueError("No bag file specified")
        
        topics = self.data_interface.get_topics(target_bag)
        self._current_topics = topics
        return topics
    
    def filter_topics(self, patterns: List[str], bag_path: Union[str, Path] = None) -> List[str]:
        """Filter topics using patterns"""
        target_bag = Path(bag_path) if bag_path else self._current_bag
        if not target_bag:
            raise ValueError("No bag file specified")
        
        filtered = self.data_interface.filter_topics(target_bag, patterns)
        self._current_topics = filtered
        return filtered
    
    def get_dataframe(self, topic: str, bag_path: Union[str, Path] = None):
        """Get DataFrame for a topic"""
        target_bag = Path(bag_path) if bag_path else self._current_bag
        if not target_bag:
            raise ValueError("No bag file specified")
        
        return self.data_interface.get_dataframe(target_bag, topic)
    
    def get_dataframes(self, topics: List[str] = None, bag_path: Union[str, Path] = None) -> Dict[str, Any]:
        """Get DataFrames for multiple topics"""
        target_bag = Path(bag_path) if bag_path else self._current_bag
        if not target_bag:
            raise ValueError("No bag file specified")
        
        target_topics = topics or self._current_topics
        if not target_topics:
            raise ValueError("No topics specified")
        
        return self.data_interface.get_multiple_dataframes(target_bag, target_topics)
    
    def merge_dataframes(self, dataframes: Dict[str, Any]):
        """Merge multiple DataFrames by timestamp"""
        return self.data_interface.merge_dataframes(dataframes)
    
    def filter_dataframe(self, df, filters: Dict[str, Any]):
        """Apply filters to DataFrame"""
        return self.data_interface.filter_dataframe(df, filters)
    
    def export_csv(self, df, output_path: Union[str, Path], include_index: bool = True) -> bool:
        """Export DataFrame to CSV"""
        success = self.data_interface.export_to_csv(df, output_path, include_index)
        if success and self.console:
            self.console.print(f"[green]✓ Exported to {output_path}[/green]")
        return success
    
    def print(self, *args, style: str = None):
        """Print with Rich formatting"""
        if self.console:
            if style:
                self.console.print(*args, style=style)
            else:
                self.console.print(*args)
        else:
            print(*args)
    
    def print_table(self, data: List[Dict[str, Any]], title: str = None):
        """Print data as a Rich table"""
        if not self.console:
            print(data)
            return
        
        from rich.table import Table
        
        if not data:
            self.console.print("[yellow]No data to display[/yellow]")
            return
        
        table = Table(title=title)
        
        # Add columns based on first row
        for key in data[0].keys():
            table.add_column(str(key), style="cyan")
        
        # Add rows
        for row in data:
            table.add_row(*[str(v) for v in row.values()])
        
        self.console.print(table)
    
    def ask_user(self, question: str, default: Any = None) -> str:
        """Ask user for input"""
        import typer
        
        if default is not None:
            prompt = f"{question} [{default}]: "
        else:
            prompt = f"{question}: "
        
        try:
            response = input(prompt).strip()
            return response if response else str(default) if default is not None else ""
        except (EOFError, KeyboardInterrupt):
            if self.console:
                self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(0)
    
    def confirm(self, question: str, default: bool = True) -> bool:
        """Ask user for confirmation"""
        import typer
        return typer.confirm(question, default=default)


class BaseScriptPlugin(ABC):
    """
    Base class for script-based plugins
    
    Script plugins are simpler than hook plugins and are designed to:
    1. Run as standalone scripts with Rose data access
    2. Provide interactive command-line tools
    3. Perform one-time data processing tasks
    4. Act as custom data analysis scripts
    """
    
    def __init__(self):
        self._plugin_info: Optional[PluginInfo] = None
        self._context: Optional[ScriptContext] = None
        self._enabled = True
    
    @property
    @abstractmethod
    def plugin_info(self) -> PluginInfo:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def run(self, context: ScriptContext, args: Dict[str, Any]) -> bool:
        """
        Main entry point for script execution
        
        Args:
            context: ScriptContext with Rose functions
            args: Command line arguments and parameters
            
        Returns:
            bool: True if script executed successfully
        """
        pass
    
    def initialize(self) -> bool:
        """
        Initialize the script plugin
        
        Returns:
            bool: True if initialization successful
        """
        return True
    
    def cleanup(self) -> None:
        """Clean up plugin resources"""
        pass
    
    def set_context(self, context: ScriptContext) -> None:
        """Set the script context"""
        self._context = context
    
    def get_context(self) -> Optional[ScriptContext]:
        """Get the script context"""
        return self._context
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled"""
        return self._enabled
    
    def enable(self) -> None:
        """Enable the plugin"""
        self._enabled = True
        logger.info(f"Script plugin {self.plugin_info.name} enabled")
    
    def disable(self) -> None:
        """Disable the plugin"""
        self._enabled = False
        logger.info(f"Script plugin {self.plugin_info.name} disabled")
    
    def validate_requirements(self) -> bool:
        """
        Validate that plugin requirements are met
        
        Returns:
            bool: True if all requirements are satisfied
        """
        try:
            if self.plugin_info.requires_pandas:
                import pandas as pd
                logger.debug(f"Script plugin {self.plugin_info.name}: pandas requirement satisfied")
            
            if self.plugin_info.requires_cache:
                from ..cache import create_bag_cache_manager
                cache_manager = create_bag_cache_manager()
                logger.debug(f"Script plugin {self.plugin_info.name}: cache requirement satisfied")
            
            return True
        except ImportError as e:
            logger.error(f"Script plugin {self.plugin_info.name} requirements not met: {e}")
            return False
    
    # Convenience methods for common operations
    
    def load_and_get_topics(self, bag_path: Union[str, Path]) -> List[str]:
        """Load bag and return topics"""
        if not self._context:
            raise RuntimeError("Script context not set")
        
        if self._context.load_bag(bag_path):
            return self._context.get_topics(bag_path)
        return []
    
    def quick_analysis(self, bag_path: Union[str, Path], topic_patterns: List[str] = None) -> Dict[str, Any]:
        """Perform quick analysis of bag data"""
        if not self._context:
            raise RuntimeError("Script context not set")
        
        # Load bag
        if not self._context.load_bag(bag_path):
            return {}
        
        # Get topics
        if topic_patterns:
            topics = self._context.filter_topics(topic_patterns, bag_path)
        else:
            topics = self._context.get_topics(bag_path)
        
        # Get basic statistics
        bag_info = self._context.get_bag_info(bag_path)
        
        analysis = {
            'bag_path': str(bag_path),
            'total_topics': len(topics),
            'selected_topics': topics,
            'bag_info': {
                'file_size_mb': bag_info.file_size_mb if bag_info else 0,
                'duration_seconds': bag_info.duration_seconds if bag_info else 0,
                'total_messages': bag_info.total_messages if bag_info else 0
            }
        }
        
        return analysis
    
    def interactive_topic_selection(self, bag_path: Union[str, Path]) -> List[str]:
        """Interactive topic selection"""
        if not self._context:
            raise RuntimeError("Script context not set")
        
        topics = self._context.get_topics(bag_path)
        if not topics:
            self._context.print("No topics found in bag file", style="red")
            return []
        
        self._context.print(f"\nAvailable topics ({len(topics)}):")
        for i, topic in enumerate(topics, 1):
            self._context.print(f"  {i:2d}. {topic}")
        
        # Ask user for selection
        selection = self._context.ask_user(
            "\nEnter topic numbers (comma-separated) or patterns", 
            "all"
        )
        
        if selection.lower() == "all":
            return topics
        
        # Parse selection
        selected_topics = []
        try:
            # Try to parse as numbers
            if ',' in selection:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                selected_topics = [topics[i] for i in indices if 0 <= i < len(topics)]
            else:
                # Single number or pattern
                try:
                    index = int(selection) - 1
                    if 0 <= index < len(topics):
                        selected_topics = [topics[index]]
                except ValueError:
                    # Treat as pattern
                    selected_topics = self._context.filter_topics([selection], bag_path)
        except (ValueError, IndexError):
            self._context.print("Invalid selection, using all topics", style="yellow")
            selected_topics = topics
        
        return selected_topics


class ScriptPluginError(Exception):
    """Base exception for script plugin errors"""
    pass


class ScriptExecutionError(ScriptPluginError):
    """Raised when script execution fails"""
    pass

