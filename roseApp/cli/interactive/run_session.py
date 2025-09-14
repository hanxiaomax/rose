#!/usr/bin/env python3
"""
Session state management for Rose interactive run environment
Handles session persistence, undo/redo operations, and workspace management
"""

import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from copy import deepcopy

from ...core.directories import get_rose_directories
from ...core.util import get_logger

logger = get_logger("run_session")


@dataclass
class SessionSnapshot:
    """Snapshot of session state for undo functionality"""
    timestamp: float
    operation: str
    state_data: Dict[str, Any]
    description: str


class SessionManager:
    """Manages session state, persistence, and undo operations"""
    
    def __init__(self, runner):
        self.runner = runner
        self.rose_dirs = get_rose_directories()
        self.snapshots = []  # Undo stack
        self.max_snapshots = 20  # Limit memory usage
        
        # Auto-load last session if available (with error handling)
        try:
            self._try_auto_load_last_session()
        except Exception as e:
            logger.warning(f"Could not auto-load session: {e}")
    
    def create_snapshot(self, operation: str, description: str = ""):
        """Create a snapshot of current state for undo"""
        snapshot = SessionSnapshot(
            timestamp=time.time(),
            operation=operation,
            state_data=self._serialize_state(),
            description=description or f"Before {operation}"
        )
        
        self.snapshots.append(snapshot)
        
        # Limit snapshots to prevent memory bloat
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)
        
        logger.debug(f"Created snapshot for operation: {operation}")
    
    def undo_last_operation(self) -> bool:
        """Undo the last operation"""
        if not self.snapshots:
            return False
        
        # Get the last snapshot
        snapshot = self.snapshots.pop()
        
        # Restore state
        self._restore_state(snapshot.state_data)
        
        logger.info(f"Undid operation: {snapshot.operation}")
        return True
    
    def save_session(self, name: Optional[str] = None) -> str:
        """Save current session to file"""
        if not name:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            name = f"session_{timestamp}.json"
        
        if not name.endswith('.json'):
            name += '.json'
        
        session_file = self.rose_dirs.get_config_file(name)
        
        # Create session data
        session_data = {
            'metadata': {
                'name': name,
                'created': self.runner.state.created_at,
                'saved': time.time(),
                'version': '1.0'
            },
            'state': self._serialize_state(),
            'snapshots': [asdict(snapshot) for snapshot in self.snapshots[-5:]]  # Save last 5 snapshots
        }
        
        # Save to file
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        logger.info(f"Session saved to: {session_file}")
        return str(session_file)
    
    def load_session(self, name_or_path: str) -> bool:
        """Load session from file"""
        try:
            # Determine file path
            if Path(name_or_path).exists():
                session_file = Path(name_or_path)
            else:
                if not name_or_path.endswith('.json'):
                    name_or_path += '.json'
                session_file = self.rose_dirs.get_config_file(name_or_path)
            
            if not session_file.exists():
                logger.error(f"Session file not found: {session_file}")
                return False
            
            # Load session data
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Restore state
            state_data = session_data.get('state', {})
            self._restore_state(state_data)
            
            # Restore snapshots if available
            snapshot_data = session_data.get('snapshots', [])
            self.snapshots = []
            for snap_dict in snapshot_data:
                snapshot = SessionSnapshot(
                    timestamp=snap_dict['timestamp'],
                    operation=snap_dict['operation'],
                    state_data=snap_dict['state_data'],
                    description=snap_dict['description']
                )
                self.snapshots.append(snapshot)
            
            logger.info(f"Session loaded from: {session_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
    
    def list_available_sessions(self) -> List[str]:
        """List all available session files"""
        try:
            config_dir = self.rose_dirs.config_dir
            session_files = list(config_dir.glob("session_*.json"))
            return [f.name for f in session_files]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def auto_save_session(self):
        """Auto-save current session"""
        try:
            auto_save_file = self.rose_dirs.get_config_file("last_session.json")
            
            session_data = {
                'metadata': {
                    'auto_saved': True,
                    'saved': time.time(),
                    'version': '1.0'
                },
                'state': self._serialize_state()
            }
            
            with open(auto_save_file, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)
            
            logger.debug("Auto-saved session")
            
        except Exception as e:
            logger.warning(f"Failed to auto-save session: {e}")
    
    def _try_auto_load_last_session(self):
        """Try to auto-load the last session"""
        try:
            auto_save_file = self.rose_dirs.get_config_file("last_session.json")
            
            if not auto_save_file.exists():
                return
            
            # Check if file is recent (within 24 hours)
            file_age = time.time() - auto_save_file.stat().st_mtime
            if file_age > 24 * 3600:  # 24 hours
                return
            
            with open(auto_save_file, 'r') as f:
                session_data = json.load(f)
            
            # Only restore basic state, not full session
            state_data = session_data.get('state', {})
            if state_data.get('current_bags') or state_data.get('notes'):
                # Only restore if there's meaningful data
                self._restore_state(state_data, partial=True)
                logger.info("Auto-loaded previous session")
            
        except Exception as e:
            logger.debug(f"Could not auto-load last session: {e}")
    
    def _serialize_state(self) -> Dict[str, Any]:
        """Serialize current state to dictionary"""
        return {
            'workspace_path': self.runner.state.workspace_path,
            'current_bags': self.runner.state.current_bags.copy(),
            'loaded_bags': deepcopy(self.runner.state.loaded_bags),
            'selected_topics': self.runner.state.selected_topics.copy(),
            'notes': self.runner.state.notes.copy(),
            'created_at': self.runner.state.created_at
        }
    
    def _restore_state(self, state_data: Dict[str, Any], partial: bool = False):
        """Restore state from dictionary"""
        try:
            if 'workspace_path' in state_data and not partial:
                self.runner.state.workspace_path = state_data['workspace_path']
                # Change to that directory if it exists
                if Path(state_data['workspace_path']).exists():
                    os.chdir(state_data['workspace_path'])
            
            if 'current_bags' in state_data:
                self.runner.state.current_bags = state_data['current_bags']
            
            if 'loaded_bags' in state_data:
                self.runner.state.loaded_bags = state_data['loaded_bags']
            
            if 'selected_topics' in state_data:
                self.runner.state.selected_topics = state_data['selected_topics']
            
            if 'notes' in state_data:
                self.runner.state.notes = state_data['notes']
            
            if 'created_at' in state_data and not partial:
                self.runner.state.created_at = state_data['created_at']
            
            logger.debug("State restored successfully")
            
        except Exception as e:
            logger.error(f"Failed to restore state: {e}")
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about current session"""
        return {
            'workspace': self.runner.state.workspace_path,
            'session_age': time.time() - self.runner.state.created_at,
            'bags_loaded': len(self.runner.state.current_bags),
            'topics_selected': len(self.runner.state.selected_topics),
            'notes_count': len(self.runner.state.notes),
            'undo_levels': len(self.snapshots),
            'running_tasks': len(self.runner.running_tasks),
            'task_history': len(self.runner.state.task_history)
        }
    
    def export_session_summary(self, output_file: Optional[str] = None) -> str:
        """Export session summary as markdown"""
        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"session_summary_{timestamp}.md"
        
        info = self.get_session_info()
        
        # Create markdown content
        content = f"""# Rose Session Summary

Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}

## Session Information

- **Workspace:** {info['workspace']}
- **Session Duration:** {info['session_age'] / 3600:.1f} hours
- **Bags Loaded:** {info['bags_loaded']}
- **Topics Selected:** {info['topics_selected']}
- **Notes:** {info['notes_count']}
- **Completed Tasks:** {info['task_history']}

## Loaded Bags

"""
        
        for bag_path in self.runner.state.current_bags:
            bag_name = Path(bag_path).name
            if bag_path in self.runner.state.loaded_bags:
                bag_info = self.runner.state.loaded_bags[bag_path]
                content += f"- **{bag_name}**\n"
                content += f"  - Topics: {len(bag_info.get('topics', []))}\n"
                content += f"  - Size: {bag_info.get('file_size_mb', 0):.1f} MB\n"
                content += f"  - Duration: {bag_info.get('duration_seconds', 0):.1f}s\n"
            else:
                content += f"- **{bag_name}** (not loaded)\n"
        
        if self.runner.state.selected_topics:
            content += "\n## Selected Topics\n\n"
            for topic in self.runner.state.selected_topics:
                content += f"- {topic}\n"
        
        if self.runner.state.notes:
            content += "\n## Session Notes\n\n"
            for note in self.runner.state.notes:
                content += f"- {note}\n"
        
        if self.runner.state.task_history:
            content += "\n## Task History\n\n"
            for task in self.runner.state.task_history[-10:]:  # Last 10 tasks
                status_icon = "[OK]" if task.status == 'completed' else "[ERR]" if task.status == 'failed' else "[...]"
                content += f"- {status_icon} {task.command} ({task.task_id})\n"
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(content)
        
        logger.info(f"Session summary exported to: {output_file}")
        return output_file


if __name__ == "__main__":
    pass
