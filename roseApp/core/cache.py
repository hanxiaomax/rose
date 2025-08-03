"""
Simplified cache management system for Rose.

This module provides a streamlined caching solution focused on bag analysis data.
Removes unnecessary complexity while maintaining core functionality.
"""

import hashlib
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import tempfile

from roseApp.core.util import get_logger
from .model import ComprehensiveBagInfo

_logger = get_logger("cache")


# Simple cache entry for internal use
@dataclass
class _CacheEntry:
    """Internal cache entry (simplified)"""
    value: Any
    timestamp: float


# ===== BAG-SPECIFIC CACHE DATA STRUCTURES =====

@dataclass
class BagCacheEntry:
    """Simplified bag cache entry"""
    bag_info: ComprehensiveBagInfo
    cache_timestamp: float
    cache_file_path: str
    file_mtime: float
    file_size: int
    original_path: str

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size / (1024 * 1024)

    @property
    def cache_file_size_mb(self) -> float:
        """Get cache file size in KB"""
        self.cache_file_size = self.cache_path.stat().st_size
        return self.cache_file_size / 1024
    
    @property 
    def cache_path(self) -> Path:
        """Get cache file path as Path object"""
        return Path(self.cache_file_path)
    
    def is_valid(self, bag_path: Path) -> bool:
        """Check if cache entry is still valid"""
        if not bag_path.exists():
            return False
        
        if str(bag_path.absolute()) != self.original_path:
            return False
        
        stat = bag_path.stat()
        return (stat.st_mtime == self.file_mtime and 
                stat.st_size == self.file_size)


# ===== UNIFIED CACHE SYSTEM =====

class UnifiedCache:
    """Unified cache system with file persistence and memory acceleration"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "rose_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, _CacheEntry] = {}
        
        _logger.info(f"Initialized UnifiedCache with dir: {cache_dir}")
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key"""
        filename = f"{hashlib.md5(key.encode()).hexdigest()}.pkl"
        return self.cache_dir / filename
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Try memory first
        if key in self._memory_cache:
            return self._memory_cache[key].value
        
        # Try file cache
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    value = pickle.load(f)
                
                # Cache in memory for next access
                self._memory_cache[key] = _CacheEntry(value=value, timestamp=time.time())
                return value
            except Exception as e:
                _logger.warning(f"Error loading cache file {key}: {e}")
                file_path.unlink(missing_ok=True)
        
        return None
    
    def put(self, key: str, value: Any, **kwargs) -> None:
        """Store value in cache (ignores unused kwargs for compatibility)"""
        try:
            # Store in file
            file_path = self._get_file_path(key)
            with open(file_path, 'wb') as f:
                pickle.dump(value, f)
            
            # Store in memory
            self._memory_cache[key] = _CacheEntry(value=value, timestamp=time.time())
            
        except Exception as e:
            _logger.error(f"Error storing cache entry {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        deleted = False
        
        # Remove from memory
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
        
        # Remove file
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()
            deleted = True
        
        return deleted
    
    def clear(self, pattern: Optional[str] = None) -> None:
        """Clear cache entries"""
        if pattern is None:
            # Clear all
            self._memory_cache.clear()
            for file_path in self.cache_dir.glob("*.pkl"):
                file_path.unlink()
        else:
            # Simple pattern matching for bag keys
            if pattern == "bag_":
                keys_to_delete = []
                for file_path in self.cache_dir.glob("*.pkl"):
                    try:
                        # Load and check if it's a BagCacheEntry
                        with open(file_path, 'rb') as f:
                            value = pickle.load(f)
                        if isinstance(value, BagCacheEntry):
                            key = file_path.stem
                            keys_to_delete.append(key)
                    except:
                        continue
                
                for key in keys_to_delete:
                    self.delete(key)
    
    # ===== BAG-SPECIFIC CACHE INTERFACE =====
    
    def get_bag_cache_key(self, bag_path: Path) -> str:
        """Generate cache key for bag file"""
        return f"bag_{hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()}"
    
    def get_bag_analysis(self, bag_path: Path) -> Optional[BagCacheEntry]:
        """Get cached bag analysis data"""
        cache_key = self.get_bag_cache_key(bag_path)
        cached_data = self.get(cache_key)
        
        if cached_data and isinstance(cached_data, BagCacheEntry):
            if cached_data.is_valid(bag_path):
                return cached_data
            else:
                # Remove invalid cache
                self.delete(cache_key)
        
        return None
    
    def put_bag_analysis(self, bag_path: Path, bag_info: Any, **kwargs) -> None:
        """Store bag analysis data in cache"""
        if not bag_path.exists():
            return
        
        cache_key = self.get_bag_cache_key(bag_path)
        stat = bag_path.stat()
        
        cache_entry = BagCacheEntry(
            bag_info=bag_info,
            cache_timestamp=time.time(),
            cache_file_path=str(self._get_file_path(cache_key)),
            file_mtime=stat.st_mtime,
            file_size=stat.st_size,
            original_path=str(bag_path.absolute())
        )
        
        self.put(cache_key, cache_entry)
    
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
            'cache_dir': str(self.cache_dir),
            'memory_entries': len(self._memory_cache)
        }
    def get_all_cache_entries(self) -> List[Tuple[str, Any]]:
        """Get all cache entries"""
        return list(self._memory_cache.items())


# ===== GLOBAL CACHE INSTANCE =====

_global_cache: Optional[UnifiedCache] = None


def get_cache() -> UnifiedCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = UnifiedCache()
    return _global_cache


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    return get_cache().get_stats()


# ===== SIMPLIFIED BAG CACHE MANAGER =====

class BagCacheManager:
    """Simplified interface for bag-specific caching operations"""
    
    def __init__(self, cache: Optional[UnifiedCache] = None):
        self.cache = cache or get_cache()
    
    def get_analysis(self, bag_path: Path) -> Optional[BagCacheEntry]:
        """Get cached bag analysis"""
        return self.cache.get_bag_analysis(bag_path)
    
    def put_analysis(self, bag_path: Path, bag_info: Any, **kwargs) -> None:
        """Store bag analysis in cache"""
        self.cache.put_bag_analysis(bag_path, bag_info)
    
    def clear(self, bag_path: Optional[Path] = None) -> None:
        """Clear bag cache"""
        self.cache.clear_bag_cache(bag_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def get_all_cache_entries(self) -> List[Tuple[str, Any]]:
        """Get all cache entries"""
        return self.cache.get_all_cache_entries()


def create_bag_cache_manager() -> BagCacheManager:
    """Create a new bag cache manager instance"""
    return BagCacheManager() 