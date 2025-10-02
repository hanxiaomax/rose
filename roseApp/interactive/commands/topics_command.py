#!/usr/bin/env python3
"""
Topics Command - Internal topic management
"""

from typing import Dict, Any, List
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from .base_command import BaseCommand


class TopicsCommand(BaseCommand):
    """Internal topics command - manages topic selection for operations"""
    
    def __init__(self, cli_executor, runner_state=None):
        super().__init__(cli_executor)
        self.runner_state = runner_state
    
    def get_command_name(self) -> str:
        return "topics"
    
    def execute(self, interactive_args: str) -> Dict[str, Any]:
        """
        Execute topics command - manage topic selection
        
        This is an internal command that doesn't delegate to CLI
        """
        try:
            args = interactive_args.strip().split() if interactive_args.strip() else []
            
            # Check if bags are loaded first
            if not self.runner_state or not self.runner_state.current_bags:
                self.result_formatter.format_warning("No bags loaded. Use /load to add bag files first.")
                return {
                    'success': False,
                    'error': 'No bags loaded',
                    'stdout': '',
                    'stderr': '',
                    'returncode': 1
                }
            
            if not args:
                # No arguments - show interactive interface
                self._show_topics_interactive()
            elif args[0] == "list":
                self._show_topics_list()
            elif args[0] == "select":
                self._select_topics(args[1:])
            elif args[0] == "clear":
                self._clear_topics()
            elif args[0] == "add" and len(args) > 1:
                self._add_topic(args[1])
            elif args[0] == "remove" and len(args) > 1:
                self._remove_topic(args[1])
            else:
                self._show_topics_help()
            
            return {
                'success': True,
                'message': 'Topics command completed',
                'stdout': '',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Topics command failed: {e}",
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _show_topics_interactive(self):
        """Interactive topic management interface"""
        # Get all available topics
        all_topics = set()
        for bag_path in self.runner_state.current_bags:
            if bag_path in (self.runner_state.loaded_bags or {}):
                bag_info = self.runner_state.loaded_bags[bag_path]
                bag_topics = bag_info.get('topics', [])
                all_topics.update(bag_topics)
        
        if not all_topics:
            self.result_formatter.format_warning("No topics available. Load bags first.")
            return
        
        topics_list = sorted(list(all_topics))
        
        action = inquirer.select(
            message="Topic Operations:",
            choices=[
                Choice(value="select", name="1. Select topics for operations"),
                Choice(value="show", name="2. Show selected topics"),
                Choice(value="clear", name="3. Clear topic selection"),
                Choice(value="back", name="4. Back")
            ]
        ).execute()
        
        if action == "select":
            selected = self._select_topics_for_operation("selection", topics_list)
            if selected:
                self.result_formatter.format_info(f"Selected {len(selected)} topics")
        elif action == "show":
            if self.runner_state.selected_topics:
                self.result_formatter.format_section_header("Selected Topics")
                for topic in self.runner_state.selected_topics:
                    self.result_formatter.console.print(f"  • {topic}")
            else:
                self.result_formatter.format_warning("No topics selected")
        elif action == "clear":
            self.runner_state.selected_topics.clear()
            self.result_formatter.format_info("Cleared topic selection")
    
    def _show_topics_list(self):
        """Display list of selected topics"""
        self.result_formatter.format_section_header("Topic Selection")
        
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        if not self.runner_state.selected_topics:
            self.result_formatter.format_info("No topics currently selected")
            self.result_formatter.format_muted("Use '/topics select <topics>' or '/topics add <topic>' to select topics")
            return
        
        self.result_formatter.format_list_items("Selected Topics", self.runner_state.selected_topics)
        
        # Show available topics from loaded bags
        available_topics = self._get_available_topics()
        if available_topics:
            self.result_formatter.format_section_header("Available Topics")
            self.result_formatter.format_list_items("From Loaded Bags", available_topics[:10])  # Limit display
            if len(available_topics) > 10:
                self.result_formatter.format_muted(f"... and {len(available_topics) - 10} more topics")
    
    def _select_topics(self, topic_names: List[str]):
        """Select topics for operations"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        if not topic_names:
            self.result_formatter.format_warning("No topics specified")
            return
        
        # Clear existing selection and add new topics
        self.runner_state.selected_topics.clear()
        for topic in topic_names:
            if topic not in self.runner_state.selected_topics:
                self.runner_state.selected_topics.append(topic)
        
        self.result_formatter.console.print(f"[green]✓[/green] Selected {len(topic_names)} topic(s)")
        self.result_formatter.format_list_items("Selected Topics", self.runner_state.selected_topics)
    
    def _add_topic(self, topic_name: str):
        """Add topic to selection"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        if topic_name in self.runner_state.selected_topics:
            self.result_formatter.format_warning(f"Topic already selected: {topic_name}")
            return
        
        self.runner_state.selected_topics.append(topic_name)
        self.result_formatter.console.print(f"[green]✓[/green] Added topic: {topic_name}")
    
    def _remove_topic(self, topic_identifier: str):
        """Remove topic from selection"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        topic_to_remove = None
        
        # Try as index first
        if topic_identifier.isdigit():
            index = int(topic_identifier) - 1
            if 0 <= index < len(self.runner_state.selected_topics):
                topic_to_remove = self.runner_state.selected_topics[index]
        
        # Try as topic name
        if not topic_to_remove:
            for topic in self.runner_state.selected_topics:
                if topic_identifier in topic:
                    topic_to_remove = topic
                    break
        
        if topic_to_remove:
            self.runner_state.selected_topics.remove(topic_to_remove)
            self.result_formatter.console.print(f"[green]✓[/green] Removed topic: {topic_to_remove}")
        else:
            self.result_formatter.format_warning(f"Topic not found: {topic_identifier}")
    
    def _clear_topics(self):
        """Clear all selected topics"""
        if not self.runner_state:
            self.result_formatter.format_warning("Runner state not available")
            return
        
        if not self.runner_state.selected_topics:
            self.result_formatter.format_info("No topics to clear")
            return
        
        count = len(self.runner_state.selected_topics)
        self.runner_state.selected_topics.clear()
        self.result_formatter.console.print(f"[green]✓[/green] Cleared {count} selected topic(s)")
    
    def _get_available_topics(self) -> List[str]:
        """Get available topics from loaded bags"""
        if not self.runner_state or not self.runner_state.loaded_bags:
            return []
        
        topics = set()
        for bag_info in self.runner_state.loaded_bags.values():
            if isinstance(bag_info, dict) and 'topics' in bag_info:
                if isinstance(bag_info['topics'], list):
                    topics.update(bag_info['topics'])
                elif isinstance(bag_info['topics'], dict):
                    topics.update(bag_info['topics'].keys())
        
        return sorted(list(topics))
    
    def _show_topics_help(self):
        """Show topics command help"""
        self.result_formatter.format_section_header("Topics Command Help")
        
        help_text = """Available operations:
  /topics list                List selected topics and available topics (default)
  /topics select <topics>     Select specific topics (replaces current selection)
  /topics add <topic>         Add topic to current selection
  /topics remove <topic>      Remove topic from selection (by name or index)
  /topics clear               Clear all selected topics

Examples:
  /topics                     Show current selection
  /topics select /gps /camera Select GPS and camera topics
  /topics add /imu            Add IMU topic to selection
  /topics remove 1            Remove first selected topic
  /topics clear               Clear all selections"""
        
        self.result_formatter.console.print(help_text)
    
    def get_help_text(self) -> str:
        return """Manage topic selection for operations

Usage: /topics [operation] [args]

Operations:
  list     - List selected and available topics (default)
  select   - Select specific topics (replaces selection)
  add      - Add topic to current selection
  remove   - Remove topic by name or index
  clear    - Clear all selected topics

This is an internal command for topic selection management."""
    
    def _select_topics_for_operation(self, operation: str, topics_list: List[str]) -> List[str]:
        """Interactive topic selection for operations using fuzzy search"""
        try:
            # Try to use fuzzy selector from util
            from ...util import ask_topics_with_fuzzy
            
            selected_topics = ask_topics_with_fuzzy(
                console=self.result_formatter.console,
                topics=topics_list,
                message=f"Select topics for {operation}:",
                require_selection=True,
                show_instructions=True
            )
            
            if selected_topics:
                self.runner_state.selected_topics = selected_topics
            
            return selected_topics
            
        except ImportError:
            # Fallback to simple multi-select
            selected_topics = inquirer.checkbox(
                message=f"Select topics for {operation}:",
                choices=topics_list,
                validate=lambda result: len(result) > 0,
                invalid_message="At least one topic must be selected"
            ).execute()
            
            if selected_topics:
                self.runner_state.selected_topics = selected_topics
            
            return selected_topics
