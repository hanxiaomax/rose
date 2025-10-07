#!/usr/bin/env python3
"""
Topic Selector Component - Reusable fuzzy search component for topic selection
"""

from typing import List, Optional
from rich.console import Console
from roseApp.cli.util import ask_topics_with_fuzzy


def select_topics_interactive(
    console: Console,
    topics: List[str],
    message: str = "Select topics:",
    require_selection: bool = True,
    show_instructions: bool = True,
    preselected: Optional[List[str]] = None,
    parser=None,
    bag_path: Optional[str] = None
) -> List[str]:
    """
    Interactive topic selector with fuzzy search
    
    This is a reusable component that can be used across all interactive commands
    that need topic selection functionality.
    
    Args:
        console: Rich console instance for displaying messages
        topics: List of available topics to select from
        message: Prompt message to display
        require_selection: Whether to require at least one topic to be selected
        show_instructions: Whether to show usage instructions
        preselected: List of topics to preselect
        parser: Parser instance for getting topic statistics
        bag_path: Path to bag file for getting topic statistics
        
    Returns:
        List of selected topics
        
    Examples:
        # Basic usage
        selected = select_topics_interactive(console, ['/gps', '/imu', '/camera'])
        
        # With preselection
        selected = select_topics_interactive(
            console, topics, 
            preselected=['/gps'],
            message="Select additional topics:"
        )
        
        # With statistics
        selected = select_topics_interactive(
            console, topics,
            parser=parser,
            bag_path=bag_path
        )
    """
    if not topics:
        from roseApp.ui.common_ui import Message
        Message.warning("No topics available", console)
        return []
    
    # Delegate to the established fuzzy search utility
    return ask_topics_with_fuzzy(
        console=console,
        topics=topics,
        message=message,
        require_selection=require_selection,
        show_instructions=show_instructions,
        preselected=preselected,
        parser=parser,
        bag_path=bag_path
    )


def get_topics_from_bags(loaded_bags: dict) -> List[str]:
    """
    Extract all topics from loaded bag information
    
    Args:
        loaded_bags: Dictionary of loaded bag information
        
    Returns:
        Sorted list of unique topics
    """
    all_topics = set()
    
    for bag_info in loaded_bags.values():
        if isinstance(bag_info, dict) and 'topics' in bag_info:
            if isinstance(bag_info['topics'], list):
                all_topics.update(bag_info['topics'])
            elif isinstance(bag_info['topics'], dict):
                all_topics.update(bag_info['topics'].keys())
    
    return sorted(list(all_topics))

