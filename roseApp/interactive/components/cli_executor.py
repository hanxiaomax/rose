#!/usr/bin/env python3
"""
CLI Executor - Core component that delegates work to actual CLI commands
"""

import sys
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

from ...core.util import get_logger

logger = get_logger("cli_executor")


class CLIExecutor:
    """CLI command executor - delegates to actual command line"""
    
    def __init__(self):
        self.rose_module = "roseApp.rose"
        
    def execute_command(self, command: str, args: List[str]) -> Dict[str, Any]:
        """
        Execute actual rose command line using subprocess
        
        Args:
            command: The rose command to execute (e.g., 'load', 'extract')
            args: List of arguments for the command
            
        Returns:
            Dict with execution results:
            {
                'success': bool,
                'stdout': str,
                'stderr': str,
                'returncode': int,
                'error': Optional[str]
            }
        """
        try:
            # Build command: python -m roseApp.rose <command> <args>
            cmd_parts = [sys.executable, '-m', self.rose_module, command] + args
            
            logger.debug(f"Executing command: {' '.join(cmd_parts)}")
            
            # Execute command
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            # Build result
            execution_result = {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'error': None
            }
            
            # Add error message if command failed
            if not execution_result['success']:
                # Prefer stdout for error messages (Rose uses stdout for formatted errors)
                error_content = result.stdout.strip() if result.stdout.strip() else result.stderr.strip()
                execution_result['error'] = (
                    error_content if error_content 
                    else f"Command failed with exit code {result.returncode}"
                )
            
            logger.debug(f"Command result: success={execution_result['success']}, "
                        f"returncode={result.returncode}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"CLI execution error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'error': f"Execution failed: {e}"
            }
    
    def execute_command_interactive(self, command: str, args: List[str]) -> Dict[str, Any]:
        """
        Execute command with interactive output (no capture)
        
        For commands that need real-time user interaction or output streaming.
        """
        try:
            # Build command: python -m roseApp.rose <command> <args>
            cmd_parts = [sys.executable, '-m', self.rose_module, command] + args
            
            logger.debug(f"Executing interactive command: {' '.join(cmd_parts)}")
            
            # Execute command without capturing output
            result = subprocess.run(
                cmd_parts,
                cwd=Path.cwd()
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': '',
                'stderr': '',
                'returncode': result.returncode,
                'error': None if result.returncode == 0 else f"Command failed with exit code {result.returncode}"
            }
            
        except Exception as e:
            logger.error(f"Interactive CLI execution error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'error': f"Execution failed: {e}"
            }