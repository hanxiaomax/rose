#!/usr/bin/env python3
"""
Bag Loader Component - Handle bag loading with cache check and user confirmation
"""

from typing import Optional
from pathlib import Path
from rich.console import Console
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from roseApp.core.parser import BagParser
from roseApp.core.cache import create_bag_cache_manager
from roseApp.core.model import ComprehensiveBagInfo
from roseApp.ui.theme import get_color
from roseApp.ui.common_ui import Message


class BagLoader:
    """Handle bag file loading with cache awareness and user interaction"""
    
    def __init__(self, console: Console):
        """
        Initialize bag loader
        
        Args:
            console: Rich console for output
        """
        self.console = console
        self.cache_manager = create_bag_cache_manager()
    
    def load_bag_interactive(
        self,
        bag_path: Path,
        force_reload: bool = False
    ) -> Optional[ComprehensiveBagInfo]:
        """
        Load bag file with cache check and user confirmation
        
        Workflow:
        1. Check if bag is in cache using BagCacheEntry
        2. If cached and valid: Load from cache
        3. If not cached: Ask user whether to:
           - Load without index (faster, recommended)
           - Load with index (slower, detailed statistics)
        
        Args:
            bag_path: Path to bag file
            force_reload: Force reload even if cached
            
        Returns:
            ComprehensiveBagInfo if loaded, None if failed or cancelled
        """
        if not bag_path.exists():
            Message.error(f"Bag file not found: {bag_path}", self.console)
            return None
        
        # Check cache using BagCacheEntry
        if not force_reload:
            cached_entry = self.cache_manager.get_analysis(bag_path)
            if cached_entry and cached_entry.is_valid(bag_path):
                # Load from cache
                try:
                    Message.success(f"Found cached analysis for: {bag_path.name}", self.console)
                    return cached_entry.bag_info
                except Exception as e:
                    Message.warning(f"Cache load failed, will reload: {e}", self.console)
        
        # Not in cache or cache failed - ask user how to load
        return self._load_bag_with_prompt(bag_path)
    
    def _load_bag_with_prompt(
        self,
        bag_path: Path
    ) -> Optional[ComprehensiveBagInfo]:
        """
        Load bag with user prompt for options
        
        Args:
            bag_path: Path to bag file
            
        Returns:
            ComprehensiveBagInfo if loaded successfully
        """
        self.console.print()
        Message.warning(f"Bag not in cache: {bag_path.name}", self.console)
        
        # Ask user how to load
        choice = inquirer.select(
            message="Would you like to load this bag?",
            choices=[
                Choice("quick", "Load without index (faster, recommended)"),
                Choice("full", "Load with index (slower, detailed statistics)"),
                Choice("cancel", "Cancel operation")
            ],
            default="quick"
        ).execute()
        
        if choice == "cancel":
            Message.warning("Bag loading cancelled", self.console)
            return None
        
        build_index = (choice == "full")
        
        try:
            # Load bag using BagParser
            Message.info(f"Loading {bag_path.name}...", self.console)
            
            parser = BagParser()
            
            # Load bag asynchronously with proper async handling
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Load and cache the bag
            bag_info, elapsed = loop.run_until_complete(
                parser.load_bag_async(str(bag_path), build_index=build_index)
            )
            
            if not bag_info:
                Message.error(f"Failed to load bag: {bag_path}", self.console)
                return None
            
            Message.success(f"Successfully loaded {bag_path.name} in {elapsed:.2f}s", self.console)
            
            # Show basic info
            self.console.print()
            self.console.print(f"  [{get_color('accent')}]•[/{get_color('accent')}] "
                             f"Topics: {len(bag_info.topics) if bag_info.topics else 0}")
            self.console.print(f"  [{get_color('accent')}]•[/{get_color('accent')}] "
                             f"Duration: {bag_info.duration_seconds:.2f}s" if bag_info.duration_seconds else "  Duration: Unknown")
            if hasattr(bag_info, 'message_count') and bag_info.message_count:
                self.console.print(f"  [{get_color('accent')}]•[/{get_color('accent')}] "
                                 f"Messages: {bag_info.message_count:,}")
            self.console.print()
            
            return bag_info
            
        except Exception as e:
            from roseApp.core.util import get_logger
            logger = get_logger('bag_loader')
            logger.error(f"Error loading bag: {e}", exc_info=True)
            Message.error(f"Failed to load bag: {e}", self.console)
            return None


def create_bag_loader(console: Console) -> BagLoader:
    """
    Create a BagLoader instance
    
    Args:
        console: Rich console instance
        
    Returns:
        BagLoader instance
    """
    return BagLoader(console)

