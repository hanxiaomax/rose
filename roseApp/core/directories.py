"""
Directory management for Rose application
Handles configuration and cache directories in user home directory
"""

import os
from pathlib import Path
from typing import Optional
from .util import get_logger

logger = get_logger(__name__)

class RoseDirectories:
    """Manages Rose application directories in user home"""
    
    def __init__(self):
        self.home_dir = Path.home()
        self.rose_dir = self.home_dir / ".rose"
        
        # Subdirectories
        self.config_dir = self.rose_dir / "config"
        self.cache_dir = self.rose_dir / "cache"
        self.whitelists_dir = self.rose_dir / "whitelists"
        self.temp_dir = self.rose_dir / "temp"
        self.logs_dir = self.rose_dir / "logs"
        
        # Initialize directories
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        directories = [
            self.rose_dir,
            self.config_dir,
            self.cache_dir,
            self.whitelists_dir,
            self.temp_dir,
            self.logs_dir
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                raise
    
    def get_cache_dir(self) -> str:
        """Get cache directory path as string"""
        return str(self.cache_dir)
    
    def get_whitelists_dir(self) -> str:
        """Get whitelists directory path as string"""
        return str(self.whitelists_dir)
    
    def get_config_dir(self) -> str:
        """Get config directory path as string"""
        return str(self.config_dir)
    
    def get_temp_dir(self) -> str:
        """Get temp directory path as string"""
        return str(self.temp_dir)
    
    def get_logs_dir(self) -> str:
        """Get logs directory path as string"""
        return str(self.logs_dir)
    
    def get_config_file(self, filename: str) -> str:
        """Get path to a config file"""
        return str(self.config_dir / filename)
    
    def get_whitelist_file(self, filename: str) -> str:
        """Get path to a whitelist file"""
        if not filename.endswith('.txt'):
            filename += '.txt'
        return str(self.whitelists_dir / filename)
    
    def list_whitelists(self) -> list:
        """List all whitelist files"""
        try:
            return [f.name for f in self.whitelists_dir.glob('*.txt')]
        except Exception as e:
            logger.error(f"Failed to list whitelists: {e}")
            return []
    
    def cleanup_temp(self):
        """Clean up temporary files older than 24 hours"""
        try:
            import time
            current_time = time.time()
            
            for temp_file in self.temp_dir.glob('*'):
                if temp_file.is_file():
                    file_age = current_time - temp_file.stat().st_mtime
                    if file_age > 24 * 3600:  # 24 hours
                        temp_file.unlink()
                        logger.debug(f"Cleaned up old temp file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")

# Global instance
_rose_dirs: Optional[RoseDirectories] = None

def get_rose_directories() -> RoseDirectories:
    """Get the global RoseDirectories instance"""
    global _rose_dirs
    if _rose_dirs is None:
        _rose_dirs = RoseDirectories()
    return _rose_dirs

def get_cache_dir() -> str:
    """Get cache directory path"""
    return get_rose_directories().get_cache_dir()

def get_whitelists_dir() -> str:
    """Get whitelists directory path"""
    return get_rose_directories().get_whitelists_dir()

def get_config_dir() -> str:
    """Get config directory path"""
    return get_rose_directories().get_config_dir()
