"""
Unified Bag Manager - High-level interface for all bag operations
Provides a single entry point for CLI commands to interact with ROS bags
Includes unified cache management with persistent storage
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
import time
import json
import hashlib
import pickle
import tempfile
import os

from .parser import BagParser, ComprehensiveBagInfo, ExtractOption, AnalysisLevel
from .ui_control import UIControl, OutputFormat, RenderOptions, ExportOptions


@dataclass
class CachedMessageData:
    """Cached message traversal data"""
    topic: str
    message_type: str
    timestamp: float
    message_data: Dict[str, Any]  # Serialized message content
    

@dataclass
class BagCacheEntry:
    """Complete bag cache entry with metadata and message data"""
    bag_info: ComprehensiveBagInfo
    cached_messages: Dict[str, List[CachedMessageData]]  # topic -> messages
    cache_timestamp: float
    file_mtime: float
    file_size: int
    
    def is_valid(self, bag_path: Path) -> bool:
        """Check if cache entry is still valid"""
        if not bag_path.exists():
            return False
        
        stat = bag_path.stat()
        return (stat.st_mtime == self.file_mtime and 
                stat.st_size == self.file_size)
    
    def get_cache_key(self, bag_path: Path) -> str:
        """Generate cache key for this bag"""
        return hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()


class UnifiedCacheManager:
    """Unified cache manager for bag analysis and message data"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.logger = logging.getLogger(f"{__name__}.cache")
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "rose_bag_cache"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for fast access
        self._memory_cache: Dict[str, BagCacheEntry] = {}
        
        # Cache configuration
        self.max_memory_entries = 50
        self.max_cached_messages_per_topic = 1000
        
        self.logger.debug(f"Initialized cache manager with dir: {self.cache_dir}")
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key"""
        return self.cache_dir / f"{cache_key}.cache"
    
    def _load_from_disk(self, cache_key: str) -> Optional[BagCacheEntry]:
        """Load cache entry from disk"""
        cache_file = self._get_cache_file_path(cache_key)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load cache from {cache_file}: {e}")
            return None
    
    def _save_to_disk(self, cache_key: str, entry: BagCacheEntry):
        """Save cache entry to disk"""
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(entry, f)
            self.logger.debug(f"Saved cache to {cache_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save cache to {cache_file}: {e}")
    
    def get(self, bag_path: Path) -> Optional[BagCacheEntry]:
        """Get cache entry for bag file"""
        cache_key = hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()
        
        # Try memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if entry.is_valid(bag_path):
                return entry
            else:
                # Remove invalid entry
                del self._memory_cache[cache_key]
        
        # Try disk cache
        entry = self._load_from_disk(cache_key)
        if entry and entry.is_valid(bag_path):
            # Load into memory cache
            self._memory_cache[cache_key] = entry
            return entry
        
        return None
    
    def put(self, bag_path: Path, bag_info: ComprehensiveBagInfo, 
           cached_messages: Optional[Dict[str, List[CachedMessageData]]] = None):
        """Store cache entry for bag file"""
        cache_key = hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()
        
        if not bag_path.exists():
            return
        
        stat = bag_path.stat()
        entry = BagCacheEntry(
            bag_info=bag_info,
            cached_messages=cached_messages or {},
            cache_timestamp=time.time(),
            file_mtime=stat.st_mtime,
            file_size=stat.st_size
        )
        
        # Store in memory cache
        self._memory_cache[cache_key] = entry
        
        # Manage memory cache size
        if len(self._memory_cache) > self.max_memory_entries:
            # Remove oldest entries
            sorted_entries = sorted(
                self._memory_cache.items(),
                key=lambda x: x[1].cache_timestamp
            )
            for old_key, _ in sorted_entries[:len(self._memory_cache) - self.max_memory_entries]:
                del self._memory_cache[old_key]
        
        # Save to disk
        self._save_to_disk(cache_key, entry)
    
    def add_cached_messages(self, bag_path: Path, topic: str, messages: List[CachedMessageData]):
        """Add cached messages for a topic"""
        entry = self.get(bag_path)
        if entry is None:
            return
        
        # Limit number of cached messages per topic
        if len(messages) > self.max_cached_messages_per_topic:
            messages = messages[:self.max_cached_messages_per_topic]
        
        entry.cached_messages[topic] = messages
        
        # Update cache
        self.put(bag_path, entry.bag_info, entry.cached_messages)
    
    def get_cached_messages(self, bag_path: Path, topic: str) -> Optional[List[CachedMessageData]]:
        """Get cached messages for a topic"""
        entry = self.get(bag_path)
        if entry is None:
            return None
        
        return entry.cached_messages.get(topic)
    
    def clear(self, bag_path: Optional[Path] = None):
        """Clear cache entries"""
        if bag_path is None:
            # Clear all caches
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to remove cache file {cache_file}: {e}")
        else:
            # Clear specific bag cache
            cache_key = hashlib.md5(str(bag_path.absolute()).encode()).hexdigest()
            
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            
            cache_file = self._get_cache_file_path(cache_key)
            if cache_file.exists():
                try:
                    cache_file.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to remove cache file {cache_file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        disk_cache_count = len(list(self.cache_dir.glob("*.cache")))
        
        return {
            'memory_entries': len(self._memory_cache),
            'disk_entries': disk_cache_count,
            'cache_dir': str(self.cache_dir),
            'max_memory_entries': self.max_memory_entries,
            'max_cached_messages_per_topic': self.max_cached_messages_per_topic
        }


@dataclass
class InspectOptions:
    """Options for bag inspection"""
    topics: Optional[List[str]] = None
    topic_filter: Optional[str] = None
    show_fields: bool = False
    sort_by: str = "size"  # Default to size sorting
    reverse_sort: bool = False
    limit: Optional[int] = None
    output_format: OutputFormat = OutputFormat.TABLE
    output_file: Optional[Path] = None
    verbose: bool = False
    no_cache: bool = False


@dataclass
class ExtractOptions:
    """Options for bag extraction"""
    topics: Optional[List[str]] = None
    topic_filter: Optional[str] = None
    output_path: Optional[Path] = None
    compression: str = "none"
    overwrite: bool = False
    dry_run: bool = False
    reverse: bool = False
    no_cache: bool = False


@dataclass
class ProfileOptions:
    """Options for bag profiling"""
    topics: Optional[List[str]] = None
    time_window: float = 1.0
    show_statistics: bool = True
    show_timeline: bool = False
    output_format: OutputFormat = OutputFormat.TABLE
    output_file: Optional[Path] = None


@dataclass
class DiagnoseOptions:
    """Options for bag diagnosis"""
    check_integrity: bool = True
    check_timestamps: bool = True
    check_message_counts: bool = True
    check_duplicates: bool = False
    detailed: bool = False
    output_format: OutputFormat = OutputFormat.TABLE


class BagManager:
    """
    Unified manager for all ROS bag operations
    Provides high-level interface for CLI commands with async capabilities and unified caching
    """
    
    def __init__(self, max_workers: int = 4, cache_dir: Optional[Path] = None):
        """Initialize the bag manager"""
        self.logger = logging.getLogger(__name__)
        self.parser = BagParser()
        self.cache_manager = UnifiedCacheManager(cache_dir)
        self.ui_control = UIControl()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        self.logger.debug(f"Initialized BagManager with {max_workers} workers")
        
    async def inspect_bag(
        self, 
        bag_path: Union[str, Path], 
        options: Optional[InspectOptions] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Inspect a ROS bag file and return analysis results
        
        Args:
            bag_path: Path to the bag file
            options: Inspection options
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary containing inspection results
        """
        if options is None:
            options = InspectOptions()
            
        bag_path = Path(bag_path)
        start_time = time.time()
        
        # Clear cache if requested
        if options.no_cache:
            self.cache_manager.clear(bag_path)
            self.parser.clear()
        
        # Report progress for initial setup
        if progress_callback:
            progress_callback(10.0)
        
        # Try to get from cache first
        cached_entry = self.cache_manager.get(bag_path)
        bag_details = None
        
        if cached_entry and cached_entry.bag_info.analysis_level != AnalysisLevel.NONE:
            bag_details = cached_entry.bag_info
            self.logger.info(f"Using cached analysis for {bag_path}")
            
            # Check if we need full analysis but only have quick analysis cached
            if (options.show_fields or options.sort_by == "size") and not bag_details.has_full_analysis():
                # Need to perform full analysis
                bag_details = None
        
        if bag_details is None:
            # Get bag details using parser - run in executor for non-blocking
            loop = asyncio.get_event_loop()
            
            # Determine if full analysis is needed
            need_full_analysis = options.show_fields or options.sort_by == "size"
            if need_full_analysis:
                bag_details, analysis_time = await loop.run_in_executor(
                    self.executor,
                    self.parser.get_bag_details,
                    str(bag_path),
                )
            else:
                bag_details, analysis_time = await loop.run_in_executor(
                    self.executor,
                    self.parser.get_bag_summary,
                    str(bag_path),
                )
            
            # Cache the result using our unified cache manager
            cached_messages_dict = {}
            if bag_details.has_cached_messages() and bag_details.cached_messages:
                # Convert parser's CachedMessage to our CachedMessageData format
                for topic, parser_messages in bag_details.cached_messages.items():
                    cached_messages_dict[topic] = [
                        CachedMessageData(
                            topic=msg.topic,
                            message_type=msg.message_type,
                            timestamp=msg.timestamp,
                            message_data=msg.message_data
                        ) for msg in parser_messages
                    ]
            
            self.cache_manager.put(bag_path, bag_details, cached_messages_dict)
        
        if progress_callback:
            progress_callback(70.0)
        
        # Apply topic filtering if specified
        filtered_topics = self._filter_topics(
            bag_details.topics or [], 
            options.topics, 
            options.topic_filter
        )
        
        # Calculate total messages for filtered topics
        total_messages = 0
        if bag_details.message_counts:
            total_messages = sum(bag_details.message_counts.get(topic, 0) for topic in filtered_topics)
        
        if progress_callback:
            progress_callback(90.0)
        
        # Prepare inspection results
        inspection_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path.absolute()),
                'file_size': bag_path.stat().st_size if bag_path.exists() else 0,
                'topics_count': len(filtered_topics),
                'total_messages': total_messages,
                'duration_seconds': bag_details.duration_seconds or 0.0,
                'time_range': bag_details.time_range,
                'analysis_time': time.time() - start_time,
                'cached': cached_entry is not None
            },
            'topics': [],
            'field_analysis': {},
            'cache_stats': self.cache_manager.get_stats()
        }
        
        # Build topic information
        topics_with_info = []
        for topic in filtered_topics:
            message_type = bag_details.connections.get(topic, 'Unknown') if bag_details.connections else 'Unknown'
            message_count = bag_details.message_counts.get(topic, 0) if bag_details.message_counts else 0
            frequency = message_count / bag_details.duration_seconds if bag_details.duration_seconds and bag_details.duration_seconds > 0 else 0
            size_bytes = bag_details.topic_sizes.get(topic, 0) if bag_details.topic_sizes else 0
            
            topic_info = {
                'name': topic,
                'message_type': message_type,
                'message_count': message_count,
                'frequency': frequency,
                'size_bytes': size_bytes
            }
            topics_with_info.append(topic_info)
        
        # Sort topics based on sort_by option
        topics_with_info = self._sort_topics_with_info(topics_with_info, options.sort_by, options.reverse_sort)
        
        # Apply limit and add to result
        for topic_info in topics_with_info:
            if options.limit and len(inspection_result['topics']) >= options.limit:
                break
            
            # Add field analysis if requested
            if options.show_fields:
                topic_name = topic_info['name']
                message_type = topic_info['message_type']
                
                # Get field paths from parser
                field_paths = bag_details.get_topic_field_paths(topic_name)
                
                if field_paths:
                    topic_info['field_paths'] = field_paths
                    
                    # Add to field analysis summary
                    inspection_result['field_analysis'][topic_name] = {
                        'message_type': message_type,
                        'field_paths': field_paths,
                        'field_count': len(field_paths),
                        'samples_analyzed': 1  # Parser gets this from message definitions
                    }
                    
                    self.logger.debug(f"Added field analysis for {topic_name}: {len(field_paths)} fields")
                else:
                    self.logger.warning(f"No field information available for topic {topic_name}")
            
            inspection_result['topics'].append(topic_info)
        
        if progress_callback:
            progress_callback(100.0)
        
        return inspection_result
    
    
    async def extract_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[ExtractOptions] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Extract topics from a ROS bag file
        
        Args:
            bag_path: Path to the source bag file
            options: Extraction options
            progress_callback: Optional progress callback (can be simple float callback or enhanced topic callback)
            
        Returns:
            Dictionary containing extraction results
        """
        if options is None:
            options = ExtractOptions()
            
        bag_path = Path(bag_path)
        
        # Clear cache if requested
        if options.no_cache:
            self.cache_manager.clear(bag_path)
            self.parser.clear()
        
        # Detect callback type and create appropriate wrapper
        simple_progress_callback = None
        if progress_callback:
            import inspect
            sig = inspect.signature(progress_callback)
            param_count = len(sig.parameters)
            
            if param_count == 1:
                # Simple float progress callback
                simple_progress_callback = progress_callback
            elif param_count >= 2:
                # Enhanced topic callback - create wrapper that provides realistic phases
                phase_start_time = time.time()
                
                def realistic_wrapper(progress: float):
                    nonlocal phase_start_time
                    current_time = time.time()
                    
                    # Map progress to realistic extraction phases
                    if progress <= 10:
                        phase = "analyzing"
                        topic_name = "bag metadata"
                        messages_processed = 0
                        total_messages = 0
                    elif progress <= 30:
                        phase = "filtering"  
                        topic_name = "connections"
                        messages_processed = 0
                        total_messages = 0
                        if progress == 30:
                            phase_start_time = current_time  # Reset for next phase
                    elif progress <= 50:
                        phase = "collecting"
                        topic_name = "messages"
                        # Estimate message collection progress
                        messages_processed = int((progress - 30) / 20 * 1000)  # Rough estimate
                        total_messages = 1000
                    elif progress <= 90:
                        if progress == 70:
                            phase = "sorting"
                            topic_name = "chronologically"
                            messages_processed = 1000
                            total_messages = 1000
                            phase_start_time = current_time  # Reset for sorting phase
                        else:
                            phase = "writing"
                            topic_name = "output file"
                            # Estimate writing progress
                            messages_processed = int((progress - 70) / 20 * 1000)
                            total_messages = 1000
                    else:
                        if progress >= 95:
                            phase = "finalizing" if progress < 100 else "completed"
                            topic_name = "output"
                            messages_processed = 1000
                            total_messages = 1000
                        else:
                            phase = "writing"
                            topic_name = "output file"
                            messages_processed = int((progress - 70) / 20 * 1000)
                            total_messages = 1000
                    
                    try:
                        progress_callback(0, topic_name, messages_processed, total_messages, phase)
                    except Exception as e:
                        self.logger.warning(f"Progress callback failed: {e}")
                
                simple_progress_callback = realistic_wrapper
        
        # Phase 1: Analyzing (0-10%)
        if simple_progress_callback:
            simple_progress_callback(5.0)
        
        # Get bag metadata first - run in executor for non-blocking
        loop = asyncio.get_event_loop()
        bag_details, _ = await loop.run_in_executor(
            self.executor,
            self.parser.get_bag_summary,
            str(bag_path)
        )
        
        # Phase 2: Filtering connections (10-30%)
        if simple_progress_callback:
            simple_progress_callback(30.0)
        
        # Apply topic filtering
        topics_to_extract = self._filter_topics(
            bag_details.topics or [],
            options.topics,
            options.topic_filter
        )
        
        # Prepare extraction parameters
        output_path = options.output_path or bag_path.parent / f"{bag_path.stem}_filtered.bag"
        
        # Create ExtractOption for parser
        extract_option = ExtractOption(
            topics=topics_to_extract,
            time_range=None,  # BagManager.ExtractOptions doesn't provide time_range
                compression=options.compression,
                overwrite=options.overwrite,
            memory_limit_mb=512  # Default memory limit
        )
        
        # Phase 3: Starting extraction (30-50%)
        if simple_progress_callback:
            simple_progress_callback(50.0)
        
        # Perform extraction if not dry run - run in executor for non-blocking
        extraction_error = None
        if not options.dry_run:
            try:
                # Create a wrapper that provides realistic extraction progress
                def extract_with_realistic_progress():
                    # The parser's extract method will handle the detailed phases
                    # We'll provide periodic updates during the actual extraction
                    
                    if simple_progress_callback:
                        # Phase 4: Collecting messages (50-70%)
                        simple_progress_callback(70.0)
                    
                    result = self.parser.extract(str(bag_path), str(output_path), extract_option)
                    
                    if simple_progress_callback:
                        # Phase 5: Writing complete (70-95%)
                        simple_progress_callback(95.0)
                    
                    return result
                
                _, extract_time = await loop.run_in_executor(
                    self.executor,
                    extract_with_realistic_progress
                )
            except Exception as e:
                self.logger.error(f"Extraction failed: {e}")
                extraction_error = str(e)
                extract_time = 0.0
            else:
                extract_time = 0.0
        
        # Phase 6: Finalizing (95-100%)
        if simple_progress_callback:
            simple_progress_callback(100.0)
        
        # Calculate extraction statistics
        total_messages = sum(bag_details.message_counts.get(topic, 0) for topic in topics_to_extract) if bag_details.message_counts else 0
        
        # Determine success status
        success = options.dry_run or (not options.dry_run and extraction_error is None and output_path.exists())
        
        # Determine message
        if options.dry_run:
            message = 'Dry run completed - no files were created'
        elif extraction_error:
            message = f'Extraction failed: {extraction_error}'
        elif success:
            message = f'Successfully extracted {len(topics_to_extract)} topics to {output_path}'
        else:
            message = 'Extraction failed: output file was not created'
        
        extraction_result = {
            'success': success,
            'dry_run': options.dry_run,
            'message': message,
            'error': extraction_error,
            'source_bag': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'total_topics': len(bag_details.topics or []),
                'total_messages': sum(bag_details.message_counts.values()) if bag_details.message_counts else 0
            },
            'extraction_config': {
                'output_path': str(output_path),
                'topics_extracted': topics_to_extract,
                'compression': options.compression,
                'dry_run': options.dry_run,
                'overwrite': options.overwrite
            },
            'extraction_stats': {
                'topics_count': len(topics_to_extract),
                'messages_extracted': total_messages,
                'extraction_time': extract_time,
                'output_file_exists': output_path.exists() if not options.dry_run else False
            }
        }
        
        if simple_progress_callback:
            simple_progress_callback(100.0)
            
        return extraction_result
    
    
    
    async def get_messages(
        self,
        bag_path: Union[str, Path],
        topic: str,
        limit: Optional[int] = None,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> List[CachedMessageData]:
        """
        Get messages from a topic using parser interface with caching support
        
        Args:
            bag_path: Path to the bag file
            topic: Topic name to get messages from
            limit: Maximum number of messages to return
            use_cache: Whether to use cached messages if available
            progress_callback: Optional progress callback
            
        Returns:
            List of cached message data
        """
        bag_path = Path(bag_path)
        
        # Check unified cache first if enabled
        if use_cache:
            cached_messages = self.cache_manager.get_cached_messages(bag_path, topic)
            if cached_messages:
                self.logger.info(f"Using {len(cached_messages)} cached messages for {topic}")
                if limit:
                    cached_messages = cached_messages[:limit]
                return cached_messages
        
        # Use parser interface to get messages
        if progress_callback:
            progress_callback(10.0)
        
        loop = asyncio.get_event_loop()
        parser_messages, _ = await loop.run_in_executor(
            self.executor,
            self.parser.get_messages,
            str(bag_path),
            topic,
            limit
        )
        
        # Convert parser messages to our format
        messages = [
            CachedMessageData(
                topic=msg.topic,
                message_type=msg.message_type,
                timestamp=msg.timestamp,
                message_data=msg.message_data
            ) for msg in parser_messages
        ]
        
        # Cache the messages if we got any
        if messages and use_cache:
            self.cache_manager.add_cached_messages(bag_path, topic, messages)
        
        if progress_callback:
            progress_callback(100.0)
        
        return messages
    
    def _traverse_messages(
        self,
        bag_path: str,
        topic: str,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> List[CachedMessageData]:
        """
        DEPRECATED: Use parser.get_messages instead
        This method is kept for backward compatibility but delegates to parser
        """
        self.logger.warning("_traverse_messages is deprecated, use get_messages instead")
        
        # Delegate to parser
        parser_messages, _ = self.parser.get_messages(bag_path, topic, limit)
        
        # Convert to our format
        return [
            CachedMessageData(
                topic=msg.topic,
                message_type=msg.message_type,
                timestamp=msg.timestamp,
                message_data=msg.message_data
            ) for msg in parser_messages
        ]
    
    def _serialize_message(self, msg) -> Dict[str, Any]:
        """
        DEPRECATED: Use parser._serialize_message_for_cache instead
        This method is kept for backward compatibility but delegates to parser
        """
        self.logger.warning("_serialize_message is deprecated, parser handles serialization")
        return self.parser._serialize_message_for_cache(msg)
    
    async def sample_messages(
        self,
        bag_path: Union[str, Path],
        topic: str,
        sample_count: int = 10,
        use_cache: bool = True
    ) -> List[CachedMessageData]:
        """
        Get a sample of messages from a topic
        
        Args:
            bag_path: Path to the bag file
            topic: Topic name
            sample_count: Number of sample messages
            use_cache: Whether to use cached messages
            
        Returns:
            List of sample messages
        """
        # Get all cached messages first
        messages = await self.get_messages(bag_path, topic, use_cache=use_cache)
        
        if not messages:
            return []
        
        # Sample messages evenly distributed
        if len(messages) <= sample_count:
            return messages
        
        step = len(messages) // sample_count
        sampled = []
        for i in range(0, len(messages), step):
            if len(sampled) >= sample_count:
                break
            sampled.append(messages[i])
        
        return sampled
    
    def clear_message_cache(self, bag_path: Optional[Union[str, Path]] = None):
        """
        Clear message cache
        
        Args:
            bag_path: Specific bag to clear cache for, or None for all
        """
        if bag_path:
            self.cache_manager.clear(Path(bag_path))
        else:
            self.cache_manager.clear()
    
    def _filter_topics(
        self, 
        all_topics: List[str], 
        selected_topics: Optional[List[str]], 
        topic_filter: Optional[str]
    ) -> List[str]:
        """Filter topics based on selection criteria with smart matching"""
        if selected_topics:
            # Smart matching: try exact match first, then fuzzy match
            filtered = []
            for pattern in selected_topics:
                # First try exact match
                exact_matches = [topic for topic in all_topics if topic == pattern]
                if exact_matches:
                    filtered.extend(exact_matches)
                else:
                    # If no exact match, try fuzzy matching (contains)
                    fuzzy_matches = [topic for topic in all_topics if pattern.lower() in topic.lower()]
                    filtered.extend(fuzzy_matches)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_filtered = []
            for topic in filtered:
                if topic not in seen:
                    seen.add(topic)
                    unique_filtered.append(topic)
            
            return unique_filtered
        elif topic_filter:
            # Use fuzzy matching
            return [topic for topic in all_topics if topic_filter.lower() in topic.lower()]
        else:
            # Return all topics
            return all_topics
    
    def _sort_topics(self, topics: List[str], sort_by: str, reverse: bool) -> List[str]:
        """Sort topics based on specified criteria"""
        if sort_by == "name":
            return sorted(topics, reverse=reverse)
        else:
            # Default to name sorting
            return sorted(topics, reverse=reverse)
    
    def _sort_topics_with_info(self, topics: List[Dict[str, Any]], sort_by: str, reverse: bool) -> List[Dict[str, Any]]:
        """Sort topics with full information based on criteria"""
        if sort_by == "name":
            return sorted(topics, key=lambda x: x['name'], reverse=reverse)
        elif sort_by == "count":
            return sorted(topics, key=lambda x: x['message_count'], reverse=reverse)
        elif sort_by == "frequency":
            return sorted(topics, key=lambda x: x['frequency'], reverse=reverse)
        elif sort_by == "size":
            return sorted(topics, key=lambda x: x['size_bytes'], reverse=reverse)
        else:
            # Default to size sorting (descending by default for size)
            if sort_by == "size" or not sort_by:
                return sorted(topics, key=lambda x: x['size_bytes'], reverse=True)
            else:
                return sorted(topics, key=lambda x: x['name'], reverse=reverse)
    
    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return self.cache_manager.get_stats()
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate percentage"""
        stats = self._get_cache_stats()
        total_entries = stats.get('memory_entries', 0) + stats.get('disk_entries', 0)
        if total_entries == 0:
            return 0.0
        return (stats.get('memory_entries', 0) / total_entries) * 100
    
    def _check_file_integrity(self, bag_path: Path, bag_details: ComprehensiveBagInfo) -> Dict[str, Any]:
        """Check bag file integrity"""
        check_result = {
            'name': 'File Integrity',
            'description': 'Verify bag file can be read and parsed correctly',
            'passed': True,
            'message': 'Bag file integrity is good'
        }
        
        if not bag_path.exists():
            check_result.update({
                'passed': False,
                'message': f'Bag file does not exist: {bag_path}'
            })
        elif not bag_details.topics:
            check_result.update({
                'passed': False,
                'message': 'Bag file appears to be empty or corrupted'
            })
        
        return check_result
    
    def _check_timestamps(self, bag_details: ComprehensiveBagInfo) -> Dict[str, Any]:
        """Check timestamp consistency"""
        check_result = {
            'name': 'Timestamp Consistency',
            'description': 'Verify timestamps are in chronological order',
            'passed': True,
            'message': 'Timestamps appear consistent'
        }
        
        if bag_details.time_range:
            start_time, end_time = bag_details.time_range
            if start_time >= end_time:
                check_result.update({
                    'passed': False,
                    'message': f'Invalid time range: start ({start_time}) >= end ({end_time})'
                })
        
        return check_result
    
    def _check_message_counts(self, bag_details: ComprehensiveBagInfo) -> Dict[str, Any]:
        """Check message count consistency"""
        check_result = {
            'name': 'Message Counts',
            'description': 'Verify message counts are reasonable',
            'passed': True,
            'message': 'Message counts appear normal'
        }
        
        if bag_details.message_counts:
            total_messages = sum(bag_details.message_counts.values())
        if total_messages == 0:
            check_result.update({
                'passed': False,
                'message': 'Bag file contains no messages'
            })
        elif total_messages > 1000000:  # Arbitrary large number threshold
            check_result.update({
                'passed': True,  # Warning, not error
                'message': f'Large number of messages detected: {total_messages:,}'
                })
        else:
            check_result.update({
                'passed': False,
                'message': 'No message count information available'
            })
        
        return check_result
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self.parser, 'clear'):
            self.parser.clear()
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True) 