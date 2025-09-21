#!/usr/bin/env python3
"""
Path Completer - Handles intelligent path completion and @ reference resolution
"""

import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any

from ...core.util import get_logger
from ...core.cache import get_cache

logger = get_logger("path_completer")


class PathCompleter:
    """Path completion with @ reference resolution"""
    
    def __init__(self):
        self._cached_bags = None
        self._cache_timestamp = None
    
    def resolve_at_references(self, input_text: str) -> str:
        """
        Resolve @symbol references to actual file paths
        
        Args:
            input_text: Input text that may contain @ references
            
        Returns:
            Resolved text with @ references replaced by actual paths
        """
        if '@' not in input_text:
            return input_text
        
        try:
            # Get cached bags
            cached_bags = self._get_cached_bags()
            
            # Split input into words and process each one
            words = input_text.split()
            resolved_words = []
            
            for word in words:
                if word.startswith('@'):
                    bag_name = word[1:]  # Remove @ symbol
                    resolved_path = self._resolve_bag_reference(bag_name, cached_bags)
                    resolved_words.append(resolved_path or word)
                else:
                    resolved_words.append(word)
            
            return ' '.join(resolved_words)
            
        except Exception as e:
            logger.debug(f"Error resolving @ symbols: {e}")
            return input_text  # Return original on error
    
    def complete_bag_files(self, partial_path: str) -> List[str]:
        """
        Return completion suggestions for bag files
        
        Args:
            partial_path: Partial path to complete
            
        Returns:
            List of completion suggestions
        """
        suggestions = []
        
        try:
            # Handle @ references
            if partial_path.startswith('@'):
                bag_name_partial = partial_path[1:]
                cached_bags = self._get_cached_bags()
                
                for bag_path in cached_bags:
                    bag_file = Path(bag_path)
                    # Match against filename or stem
                    if (bag_file.name.lower().startswith(bag_name_partial.lower()) or
                        bag_file.stem.lower().startswith(bag_name_partial.lower())):
                        suggestions.append(f"@{bag_file.stem}")
                
                return suggestions
            
            # Handle regular path completion
            try:
                path = Path(partial_path)
                parent = path.parent if path.is_absolute() or '/' in partial_path else Path.cwd()
                
                if parent.exists():
                    for item in parent.iterdir():
                        if item.name.lower().startswith(path.name.lower()):
                            if item.is_dir():
                                suggestions.append(str(item) + '/')
                            elif item.suffix == '.bag':
                                suggestions.append(str(item))
                
            except Exception as e:
                logger.debug(f"Path completion error: {e}")
            
        except Exception as e:
            logger.debug(f"Completion error: {e}")
        
        return suggestions[:10]  # Limit suggestions
    
    def _resolve_bag_reference(self, bag_name: str, cached_bags: List[str]) -> Optional[str]:
        """
        Resolve a bag name to its full path
        
        Args:
            bag_name: Name of the bag to resolve
            cached_bags: List of cached bag paths
            
        Returns:
            Full path if found, None otherwise
        """
        for bag_path in cached_bags:
            bag_file = Path(bag_path)
            # Try exact name match, stem match, and case-insensitive matches
            if (bag_file.name == bag_name or 
                bag_file.stem == bag_name or
                bag_file.name.lower() == bag_name.lower() or
                bag_file.stem.lower() == bag_name.lower()):
                logger.debug(f"Resolved @{bag_name} to {bag_path}")
                return bag_path
        
        logger.warning(f"Could not resolve @{bag_name} to a cached bag")
        return None
    
    def _get_cached_bags(self) -> List[str]:
        """
        Get cached bags with caching to avoid repeated file system access
        
        Returns:
            List of cached bag file paths
        """
        try:
            cache = get_cache()
            
            # Check if we need to refresh cache
            current_time = Path().stat().st_mtime if Path().exists() else 0
            if (self._cached_bags is None or 
                self._cache_timestamp is None or 
                current_time > self._cache_timestamp):
                
                self._cached_bags = self._load_cached_bags(cache)
                self._cache_timestamp = current_time
            
            return self._cached_bags or []
            
        except Exception as e:
            logger.debug(f"Could not get cached bags: {e}")
            return []
    
    def _load_cached_bags(self, cache) -> List[str]:
        """
        Load cached bags from cache directory
        
        Args:
            cache: Cache instance
            
        Returns:
            List of cached bag file paths
        """
        cached_bags = []
        
        if not hasattr(cache, 'cache_dir') or not cache.cache_dir.exists():
            return cached_bags
        
        for cache_file in cache.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                
                # Extract original bag path with multiple fallback methods
                bag_path = self._extract_bag_path(cached_data, cache_file)
                
                if bag_path:
                    cached_bags.append(bag_path)
                    logger.debug(f"Found cached bag: {bag_path}")
                    
            except Exception as e:
                logger.debug(f"Could not process cache file {cache_file}: {e}")
                continue
        
        return list(set(cached_bags))  # Remove duplicates
    
    def _extract_bag_path(self, cached_data: Any, cache_file: Path) -> Optional[str]:
        """
        Extract bag path from cached data with multiple fallback strategies
        
        Args:
            cached_data: Cached data object
            cache_file: Cache file path for fallback inference
            
        Returns:
            Bag file path if found, None otherwise
        """
        bag_path = None
        
        # Strategy 1: Direct original_path attribute
        if hasattr(cached_data, 'original_path') and cached_data.original_path:
            bag_path = cached_data.original_path
            logger.debug(f"Found original_path: {bag_path}")
        
        # Strategy 2: bag_info.file_path
        elif hasattr(cached_data, 'bag_info') and cached_data.bag_info:
            bag_info = cached_data.bag_info
            if hasattr(bag_info, 'file_path') and bag_info.file_path:
                bag_path = str(bag_info.file_path)
                # If it's a relative path, make it absolute
                if not bag_path.startswith('/'):
                    bag_path = f"/workspaces/rose/{bag_path}"
                logger.debug(f"Found bag_info.file_path: {bag_path}")
            
            # Strategy 3: bag_info.file_info dictionary
            elif hasattr(bag_info, 'file_info') and isinstance(bag_info.file_info, dict):
                file_info = bag_info.file_info
                for key in ['path', 'file_path', 'absolute_path', 'name']:
                    if key in file_info and file_info[key]:
                        bag_path = file_info[key]
                        logger.debug(f"Found file_info[{key}]: {bag_path}")
                        break
        
        # Strategy 4: Infer from cache filename
        if not bag_path:
            cache_stem = cache_file.stem
            possible_paths = [
                f"{cache_stem}.bag",
                f"roseApp/tests/{cache_stem}.bag",
                f"/workspaces/rose/roseApp/tests/{cache_stem}.bag"
            ]
            for possible_path in possible_paths:
                if Path(possible_path).exists():
                    bag_path = str(Path(possible_path).absolute())
                    logger.debug(f"Inferred path: {bag_path}")
                    break
        
        return bag_path
