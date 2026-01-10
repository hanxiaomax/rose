"""
Simplified cache management system for Rose.

This module provides a streamlined caching solution focused on bag analysis data.
Removes unnecessary complexity while maintaining core functionality.
"""

import hashlib
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

from roseApp.core.logging import get_logger
from .model import BagInfo
from .config import get_cache_dir

_logger = get_logger("cache")


# ===== UNIFIED CACHE SYSTEM =====

class Cache:
    """Simplified cache system with file persistence"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = get_cache_dir()  # config.py returns Path object directly
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        _logger.debug(f"Initialized Cache with dir: {cache_dir}")
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key"""
        filename = f"{hashlib.md5(key.encode()).hexdigest()}.pkl"
        return self.cache_dir / filename
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    value = pickle.load(f)
                return value
            except Exception as e:
                _logger.warning(f"Error loading cache file {key}: {e}")
                file_path.unlink(missing_ok=True)
        
        return None
    
    def put(self, key: str, value: Any, **kwargs) -> None:
        """Store value in cache"""
        try:
            file_path = self._get_file_path(key)
            with open(file_path, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            _logger.error(f"Error storing cache entry {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def clear(self, pattern: Optional[str] = None) -> None:
        """Clear cache entries"""
        if pattern is None:
            # Clear all
            for file_path in self.cache_dir.glob("*.pkl"):
                file_path.unlink()
        else:
            # Simple pattern matching for bag keys is not easily supported in hashed filenames
            # So we clear all if pattern is provided (for now, mainly used for bag_ prefix)
            # A more robust impl would query content, but for cleanup "clear all" is usually fine.
            # Or we iterate and check content type.
            for file_path in self.cache_dir.glob("*.pkl"):
                file_path.unlink()
    
    # ===== BAG-SPECIFIC CACHE INTERFACE =====
    
    def get_bag_cache_key(self, bag_path: Path) -> str:
        """Generate cache key for bag file"""
        return f"bag_{hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()}"
    
    def get_bag_analysis(self, bag_path: Path) -> Optional[BagInfo]:
        """Get cached bag analysis data"""
        if not bag_path.exists():
            return None
            
        cache_key = self.get_bag_cache_key(bag_path)
        cached_data = self.get(cache_key)
        
        if cached_data and isinstance(cached_data, BagInfo):
            # Validate cache against current file state
            stat = bag_path.stat()
            if (cached_data.file_size == stat.st_size and 
                cached_data.file_mtime == stat.st_mtime):
                return cached_data
            else:
                # Remove invalid cache
                _logger.info(f"Cache invalid for {bag_path.name} (size/mtime mismatch)")
                self.delete(cache_key)
        
        return None
    
    def put_bag_analysis(self, bag_path: Path, bag_info: BagInfo, **kwargs) -> None:
        """Store bag analysis data in cache"""
        if not bag_path.exists():
            return
        
        cache_key = self.get_bag_cache_key(bag_path)
        self.put(cache_key, bag_info)
    
    def clear_bag_cache(self, bag_path: Optional[Path] = None) -> None:
        """Clear bag-specific cache entries"""
        if bag_path is None:
            self.clear("bag_")
        else:
            cache_key = self.get_bag_cache_key(bag_path)
            self.delete(cache_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get basic cache statistics"""
        cache_files = list(self.cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'entry_count': len(cache_files),
            'total_size_bytes': total_size,
            'cache_dir': str(self.cache_dir)
        }


# ===== GLOBAL CACHE INSTANCE =====

_global_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = Cache()
    return _global_cache


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    return get_cache().get_stats()


# ===== SIMPLIFIED BAG CACHE MANAGER =====

class BagCacheManager:
    """Simplified interface for bag-specific caching operations"""
    
    def __init__(self, cache: Optional[Cache] = None):
        self.cache = cache or get_cache()
    
    def get_analysis(self, bag_path: Path) -> Optional[BagInfo]:
        """Get cached bag analysis"""
        return self.cache.get_bag_analysis(bag_path)
    
    def put_analysis(self, bag_path: Path, bag_info: BagInfo, **kwargs) -> None:
        """Store bag analysis in cache"""
        self.cache.put_bag_analysis(bag_path, bag_info)
    
    def clear(self, bag_path: Optional[Path] = None) -> None:
        """Clear bag cache"""
        self.cache.clear_bag_cache(bag_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()

def create_bag_cache_manager() -> BagCacheManager:
    """Create a new bag cache manager instance"""
    return BagCacheManager()