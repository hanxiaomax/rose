#!/usr/bin/env python3
"""
Command builder utilities for interactive mode
Provides functionality to build and execute Rose commands from interactive input
"""

import subprocess
import sys
from typing import List, Dict, Any, Optional
from rich.console import Console

from .common_ui import Message
from .theme import get_color
from ..core.util import get_logger

logger = get_logger("CommandBuilder")


class CommandBuilder:
    """Builds and executes Rose commands from interactive input"""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def build_load_command(self, bag_files: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Build load command from interactive input
        
        Args:
            bag_files: List of bag file paths
            options: Dictionary of command options
            
        Returns:
            List of command parts ready for subprocess execution
        """
        cmd_parts = [sys.executable, "-m", "roseApp.rose", "load"]
        
        # Add bag files
        for bag_file in bag_files:
            cmd_parts.append(bag_file)
        
        # Add options
        if options.get("workers"):
            cmd_parts.extend(["--workers", str(options["workers"])])
        if options.get("verbose"):
            cmd_parts.append("--verbose")
        if options.get("force"):
            cmd_parts.append("--force")
        if options.get("dry_run"):
            cmd_parts.append("--dry-run")
        if options.get("build_index"):
            cmd_parts.append("--build-index")
        
        return cmd_parts
    
    def build_extract_command(self, bag_files: List[str], topics: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Build extract command from interactive input
        
        Args:
            bag_files: List of bag file paths
            topics: List of topics to extract
            options: Dictionary of command options
            
        Returns:
            List of command parts ready for subprocess execution
        """
        cmd_parts = [sys.executable, "-m", "roseApp.rose", "extract"]
        
        # Add bag files
        for bag_file in bag_files:
            cmd_parts.append(bag_file)
        
        # Add topics
        if topics:
            cmd_parts.append("--topics")
            cmd_parts.extend(topics)
        
        # Add options
        if options.get("output"):
            cmd_parts.extend(["--output", options["output"]])
        if options.get("workers"):
            cmd_parts.extend(["--workers", str(options["workers"])])
        if options.get("reverse"):
            cmd_parts.append("--reverse")
        if options.get("compression") and options["compression"] != "none":
            cmd_parts.extend(["--compression", options["compression"]])
        if options.get("dry_run"):
            cmd_parts.append("--dry-run")
        if options.get("verbose"):
            cmd_parts.append("--verbose")
        
        # Always add --yes for wizard execution
        cmd_parts.append("--yes")
        
        return cmd_parts
    
    def build_compress_command(self, bag_files: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Build compress command from interactive input
        
        Args:
            bag_files: List of bag file paths
            options: Dictionary of command options
            
        Returns:
            List of command parts ready for subprocess execution
        """
        cmd_parts = [sys.executable, "-m", "roseApp.rose", "compress"]
        
        # Add bag files
        for bag_file in bag_files:
            cmd_parts.append(bag_file)
        
        # Add options
        if options.get("output"):
            cmd_parts.extend(["--output", options["output"]])
        if options.get("workers"):
            cmd_parts.extend(["--workers", str(options["workers"])])
        if options.get("compression"):
            cmd_parts.extend(["--compression", options["compression"]])
        if options.get("validate"):
            cmd_parts.append("--validate")
        if options.get("dry_run"):
            cmd_parts.append("--dry-run")
        if options.get("verbose"):
            cmd_parts.append("--verbose")
        
        # Always add --yes for wizard execution
        cmd_parts.append("--yes")
        
        return cmd_parts
    
    def build_inspect_command(self, bag_files: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Build inspect command from interactive input
        
        Args:
            bag_files: List of bag file paths
            options: Dictionary of command options
            
        Returns:
            List of command parts ready for subprocess execution
        """
        cmd_parts = [sys.executable, "-m", "roseApp.rose", "inspect"]
        
        # Add bag files
        for bag_file in bag_files:
            cmd_parts.append(bag_file)
        
        # Add options
        if options.get("topics"):
            cmd_parts.append("--topics")
            cmd_parts.extend(options["topics"])
        if options.get("fields"):
            cmd_parts.append("--fields")
        if options.get("sort_by"):
            cmd_parts.extend(["--sort-by", options["sort_by"]])
        if options.get("output"):
            cmd_parts.extend(["--output", options["output"]])
        if options.get("verbose"):
            cmd_parts.append("--verbose")
        
        return cmd_parts
    
    def build_data_command(self, subcommand: str, bag_files: List[str], options: Dict[str, Any]) -> List[str]:
        """
        Build data command from interactive input
        
        Args:
            subcommand: Data subcommand (export, info)
            bag_files: List of bag file paths
            options: Dictionary of command options
            
        Returns:
            List of command parts ready for subprocess execution
        """
        cmd_parts = [sys.executable, "-m", "roseApp.rose", "data", subcommand]
        
        # Add bag files
        for bag_file in bag_files:
            cmd_parts.append(bag_file)
        
        # Add options based on subcommand
        if subcommand == "export":
            if options.get("topics"):
                cmd_parts.append("--topics")
                cmd_parts.extend(options["topics"])
            if options.get("output"):
                cmd_parts.extend(["--output", options["output"]])
            if options.get("start_time"):
                cmd_parts.extend(["--start-time", str(options["start_time"])])
            if options.get("end_time"):
                cmd_parts.extend(["--end-time", str(options["end_time"])])
            if options.get("search"):
                cmd_parts.extend(["--search", options["search"]])
            if options.get("include_index"):
                cmd_parts.append("--include-index")
            else:
                cmd_parts.append("--no-index")
        
        if options.get("verbose"):
            cmd_parts.append("--verbose")
        
        # Always add --yes for wizard execution
        cmd_parts.append("--yes")
        
        return cmd_parts
    
    def display_command_preview(self, cmd_parts: List[str]) -> None:
        """
        Display the generated command for user review
        
        Args:
            cmd_parts: List of command parts
        """
        command_line = " ".join(cmd_parts)
        self.console.print(f"\nGenerated command:")
        self.console.print(f"  {command_line}", style=get_color("info"))
    
    def execute_command(self, cmd_parts: List[str], capture_output: bool = False) -> bool:
        """
        Execute the built command
        
        Args:
            cmd_parts: List of command parts
            capture_output: Whether to capture command output
            
        Returns:
            True if command executed successfully, False otherwise
        """
        try:
            self.console.print("\nExecuting command...")
            result = subprocess.run(cmd_parts, capture_output=capture_output, text=True)
            
            if result.returncode == 0:
                Message.success("Command executed successfully!", self.console)
                return True
            else:
                Message.error(f"Command failed with exit code {result.returncode}", self.console)
                if capture_output and result.stderr:
                    self.console.print(f"Error output: {result.stderr}")
                return False
                
        except Exception as e:
            Message.error(f"Failed to execute command: {str(e)}", self.console)
            return False
    
    def build_and_execute_command(self, command_type: str, bag_files: List[str], 
                                options: Dict[str, Any], topics: Optional[List[str]] = None,
                                subcommand: Optional[str] = None) -> bool:
        """
        Build and execute command based on type
        
        Args:
            command_type: Type of command (load, extract, compress, inspect, data)
            bag_files: List of bag file paths
            options: Dictionary of command options
            topics: Optional list of topics (for extract, inspect, data)
            subcommand: Optional subcommand (for data)
            
        Returns:
            True if command executed successfully, False otherwise
        """
        # Build command based on type
        if command_type == "load":
            cmd_parts = self.build_load_command(bag_files, options)
        elif command_type == "extract":
            cmd_parts = self.build_extract_command(bag_files, topics or [], options)
        elif command_type == "compress":
            cmd_parts = self.build_compress_command(bag_files, options)
        elif command_type == "inspect":
            if topics:
                options["topics"] = topics
            cmd_parts = self.build_inspect_command(bag_files, options)
        elif command_type == "data":
            cmd_parts = self.build_data_command(subcommand or "info", bag_files, options)
        else:
            Message.error(f"Unknown command type: {command_type}", self.console)
            return False
        
        # Display command preview
        self.display_command_preview(cmd_parts)
        
        # Execute command
        return self.execute_command(cmd_parts)


class InteractiveWizard:
    """Base class for interactive command wizards"""
    
    def __init__(self, command_name: str, console: Optional[Console] = None):
        self.command_name = command_name
        self.console = console or Console()
        self.command_builder = CommandBuilder(self.console)
        
    def show_welcome(self, description: str) -> None:
        """Show welcome message for the wizard"""
        Message.info(f"Interactive {self.command_name.title()} Mode", self.console)
        self.console.print(f"{description}\n")
    
    def show_step(self, step_number: int, step_name: str) -> None:
        """Show current step information"""
        self.console.print(f"\nStep {step_number}: {step_name}")
    
    def show_summary(self, summary_data: Dict[str, Any]) -> None:
        """Show operation summary before execution"""
        self.console.print(f"\n{self.command_name.title()} Summary:")
        for key, value in summary_data.items():
            self.console.print(f"{key}: {value}")
    
    def show_exit_message(self) -> None:
        """Show exit message"""
        Message.info(f"Exiting interactive {self.command_name} mode", self.console)

