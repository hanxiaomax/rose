"""
Core engine system for Rose.

This module provides the main bag processing engine with I/O management,
async operations, and comprehensive bag manipulation capabilities.
"""

import asyncio
import os
import shutil
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Union
from enum import Enum

from roseApp.core.util import get_logger, TimeUtil
from roseApp.core.cache import get_cache
from roseApp.core.analyzer import BagInfo, AnalysisResult, AnalysisType, get_analyzer

_logger = get_logger("engine")


class CompressionType(Enum):
    """Available compression types for bag files"""
    NONE = "none"
    BZ2 = "bz2"
    LZ4 = "lz4"


@dataclass
class FilterConfig:
    """Configuration for bag filtering operations"""
    topics: List[str]
    time_range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    compression: str = CompressionType.NONE.value
    output_path: Optional[Path] = None
    overwrite: bool = False


@dataclass
class ProcessingResult:
    """Result of bag processing operation"""
    success: bool
    input_path: Path
    output_path: Optional[Path]
    processing_time: float
    error_message: Optional[str] = None
    output_size: int = 0
    
    @property
    def size_str(self) -> str:
        """Get output size in human readable format"""
        size_bytes = self.output_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f}TB"


class AsyncIOManager:
    """Manages asynchronous I/O operations for bag files"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._file_locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()
    
    def _get_file_lock(self, file_path: str) -> threading.Lock:
        """Get or create a lock for a specific file"""
        with self._locks_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = threading.Lock()
            return self._file_locks[file_path]
    
    async def read_bag_info_async(self, bag_path: Path) -> BagInfo:
        """Read bag information asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._read_bag_info_sync,
            bag_path
        )
    
    def _read_bag_info_sync(self, bag_path: Path) -> BagInfo:
        """Read bag information synchronously"""
        file_lock = self._get_file_lock(str(bag_path))
        with file_lock:
            analyzer = get_analyzer()
            result = analyzer.analyze_bag(bag_path, AnalysisType.METADATA)
            return result.bag_info
    
    async def copy_file_async(self, src: Path, dst: Path) -> bool:
        """Copy file asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._copy_file_sync,
            src,
            dst
        )
    
    def _copy_file_sync(self, src: Path, dst: Path) -> bool:
        """Copy file synchronously"""
        try:
            # Ensure destination directory exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Use locks for both source and destination
            src_lock = self._get_file_lock(str(src))
            dst_lock = self._get_file_lock(str(dst))
            
            with src_lock, dst_lock:
                shutil.copy2(src, dst)
                return True
        except Exception as e:
            _logger.error(f"Error copying {src} to {dst}: {e}")
            return False
    
    async def delete_file_async(self, file_path: Path) -> bool:
        """Delete file asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._delete_file_sync,
            file_path
        )
    
    def _delete_file_sync(self, file_path: Path) -> bool:
        """Delete file synchronously"""
        try:
            file_lock = self._get_file_lock(str(file_path))
            with file_lock:
                if file_path.exists():
                    file_path.unlink()
                return True
        except Exception as e:
            _logger.error(f"Error deleting {file_path}: {e}")
            return False
    
    async def ensure_directory_async(self, dir_path: Path) -> bool:
        """Ensure directory exists asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._ensure_directory_sync,
            dir_path
        )
    
    def _ensure_directory_sync(self, dir_path: Path) -> bool:
        """Ensure directory exists synchronously"""
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            _logger.error(f"Error creating directory {dir_path}: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        self._executor.shutdown(wait=True)


class BagEngine:
    """Main bag processing engine with comprehensive functionality"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.io_manager = AsyncIOManager(max_workers)
        self._cache = get_cache()
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        
        # Initialize parser
        from roseApp.core.parser import create_best_parser
        self._parser = create_best_parser()
        
        _logger.info(f"Initialized BagEngine with {max_workers} workers")
    
    async def analyze_bag_async(self, 
                               bag_path: Path,
                               analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                               progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
        """Analyze a bag file asynchronously"""
        analyzer = get_analyzer()
        return await analyzer.analyze_bag_async(bag_path, analysis_type, progress_callback)
    
    def analyze_bag(self, 
                   bag_path: Path,
                   analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                   progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
        """Analyze a bag file synchronously"""
        analyzer = get_analyzer()
        return analyzer.analyze_bag(bag_path, analysis_type, progress_callback)
    
    async def filter_bag_async(self,
                              input_path: Path,
                              config: FilterConfig,
                              progress_callback: Optional[Callable[[float], None]] = None) -> ProcessingResult:
        """Filter a bag file asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default executor
            self._filter_bag_sync,
            input_path,
            config,
            progress_callback
        )
    
    def _filter_bag_sync(self,
                        input_path: Path,
                        config: FilterConfig,
                        progress_callback: Optional[Callable[[float], None]] = None) -> ProcessingResult:
        """Filter a bag file synchronously"""
        start_time = time.time()
        
        try:
            # Determine output path
            output_path = config.output_path
            if not output_path:
                output_path = input_path.parent / f"{input_path.stem}_filtered{input_path.suffix}"
            
            # Check if output file exists and handle overwrite
            if output_path.exists() and not config.overwrite:
                return ProcessingResult(
                    success=False,
                    input_path=input_path,
                    output_path=output_path,
                    processing_time=time.time() - start_time,
                    error_message=f"Output file {output_path} already exists"
                )
            
            if progress_callback:
                progress_callback(10.0)
            
            # Perform filtering using parser
            try:
                from roseApp.core.parser import FileExistsError
                
                self._parser.filter_bag(
                    str(input_path),
                    str(output_path),
                    config.topics,
                    config.time_range,
                    progress_callback=progress_callback,
                    compression=config.compression,
                    overwrite=config.overwrite
                )
                
            except FileExistsError:
                if config.overwrite:
                    # Remove existing file and try again
                    if output_path.exists():
                        output_path.unlink()
                    
                    self._parser.filter_bag(
                        str(input_path),
                        str(output_path),
                        config.topics,
                        config.time_range,
                        progress_callback=progress_callback,
                        compression=config.compression,
                        overwrite=True
                    )
                else:
                    raise
            
            # Get output file size
            output_size = output_path.stat().st_size if output_path.exists() else 0
            
            processing_time = time.time() - start_time
            
            if progress_callback:
                progress_callback(100.0)
            
            _logger.info(f"Filtered {input_path} to {output_path} in {processing_time:.2f}s")
            
            return ProcessingResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                processing_time=processing_time,
                output_size=output_size
            )
            
        except Exception as e:
            error_msg = f"Error filtering bag {input_path}: {e}"
            _logger.error(error_msg)
            
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=config.output_path,
                processing_time=time.time() - start_time,
                error_message=error_msg
            )
    
    async def filter_multiple_bags_async(self,
                                        input_paths: List[Path],
                                        config: FilterConfig,
                                        progress_callback: Optional[Callable[[str, float], None]] = None) -> Dict[Path, ProcessingResult]:
        """Filter multiple bag files concurrently"""
        results = {}
        
        # Create tasks for concurrent processing
        tasks = []
        for input_path in input_paths:
            # Create individual config for each bag
            bag_config = FilterConfig(
                topics=config.topics.copy(),
                time_range=config.time_range,
                compression=config.compression,
                output_path=self._generate_output_path(input_path, config.output_path),
                overwrite=config.overwrite
            )
            
            def make_progress_callback(path):
                if progress_callback:
                    return lambda p: progress_callback(str(path), p)
                return None
            
            task = self.filter_bag_async(
                input_path,
                bag_config,
                make_progress_callback(input_path)
            )
            tasks.append((input_path, task))
        
        # Wait for all tasks to complete
        for input_path, task in tasks:
            try:
                result = await task
                results[input_path] = result
            except Exception as e:
                _logger.error(f"Error processing {input_path}: {e}")
                results[input_path] = ProcessingResult(
                    success=False,
                    input_path=input_path,
                    output_path=None,
                    processing_time=0,
                    error_message=str(e)
                )
        
        return results
    
    def _generate_output_path(self, input_path: Path, base_output_path: Optional[Path]) -> Path:
        """Generate output path for a bag file"""
        if base_output_path:
            if base_output_path.is_dir():
                # Output to directory
                return base_output_path / f"{input_path.stem}_filtered{input_path.suffix}"
            else:
                # Specific output file
                return base_output_path
        else:
            # Default: same directory as input
            return input_path.parent / f"{input_path.stem}_filtered{input_path.suffix}"
    
    async def copy_bag_async(self, src_path: Path, dst_path: Path) -> ProcessingResult:
        """Copy a bag file asynchronously"""
        start_time = time.time()
        
        try:
            success = await self.io_manager.copy_file_async(src_path, dst_path)
            
            if success:
                output_size = dst_path.stat().st_size if dst_path.exists() else 0
                
                return ProcessingResult(
                    success=True,
                    input_path=src_path,
                    output_path=dst_path,
                    processing_time=time.time() - start_time,
                    output_size=output_size
                )
            else:
                return ProcessingResult(
                    success=False,
                    input_path=src_path,
                    output_path=dst_path,
                    processing_time=time.time() - start_time,
                    error_message="Copy operation failed"
                )
                
        except Exception as e:
            return ProcessingResult(
                success=False,
                input_path=src_path,
                output_path=dst_path,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def validate_bag_async(self, bag_path: Path) -> Dict[str, Any]:
        """Validate a bag file asynchronously"""
        try:
            # Basic file existence and readability check
            if not bag_path.exists():
                return {
                    'valid': False,
                    'error': 'File does not exist'
                }
            
            if not bag_path.is_file():
                return {
                    'valid': False,
                    'error': 'Path is not a file'
                }
            
            # Try to read basic bag information
            try:
                bag_info = await self.io_manager.read_bag_info_async(bag_path)
                
                return {
                    'valid': True,
                    'topics': len(bag_info.topics),
                    'duration': bag_info.duration_seconds,
                    'size_bytes': bag_info.size_bytes,
                    'message_count': sum(bag_info.message_counts.values())
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Cannot read bag file: {e}'
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {e}'
            }
    
    def get_available_compression_types(self) -> List[str]:
        """Get list of available compression types"""
        from roseApp.core.util import get_available_compression_types
        return get_available_compression_types()
    
    def validate_compression_type(self, compression: str) -> Tuple[bool, str]:
        """Validate compression type"""
        from roseApp.core.util import validate_compression_type
        return validate_compression_type(compression)
    
    async def get_bag_statistics_async(self, bag_path: Path) -> Dict[str, Any]:
        """Get comprehensive bag statistics asynchronously"""
        try:
            result = await self.analyze_bag_async(bag_path, AnalysisType.FULL_ANALYSIS)
            
            if result.errors:
                return {
                    'success': False,
                    'errors': result.errors
                }
            
            analyzer = get_analyzer()
            topic_stats = analyzer.get_topic_statistics(result)
            
            return {
                'success': True,
                'bag_info': {
                    'path': str(result.bag_info.path),
                    'size_bytes': result.bag_info.size_bytes,
                    'duration_seconds': result.bag_info.duration_seconds,
                    'topic_count': len(result.bag_info.topics),
                    'total_messages': sum(result.bag_info.message_counts.values())
                },
                'topics': topic_stats,
                'analysis_time': result.analysis_time,
                'cached': result.cached
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }
    
    def cleanup(self):
        """Cleanup resources"""
        self.io_manager.cleanup()
        
        # Cancel any running tasks
        for task in self._processing_tasks.values():
            if not task.done():
                task.cancel()
        
        _logger.info("BagEngine cleaned up")


# Global engine instance
_global_engine: Optional[BagEngine] = None


def get_engine() -> BagEngine:
    """Get or create global engine instance"""
    global _global_engine
    if _global_engine is None:
        _global_engine = BagEngine()
    return _global_engine


async def filter_bag_async(input_path: Path,
                          topics: List[str],
                          output_path: Optional[Path] = None,
                          time_range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None,
                          compression: str = CompressionType.NONE.value,
                          overwrite: bool = False,
                          progress_callback: Optional[Callable[[float], None]] = None) -> ProcessingResult:
    """Convenience function for async bag filtering"""
    config = FilterConfig(
        topics=topics,
        time_range=time_range,
        compression=compression,
        output_path=output_path,
        overwrite=overwrite
    )
    return await get_engine().filter_bag_async(input_path, config, progress_callback)


def filter_bag(input_path: Path,
              topics: List[str],
              output_path: Optional[Path] = None,
              time_range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None,
              compression: str = CompressionType.NONE.value,
              overwrite: bool = False,
              progress_callback: Optional[Callable[[float], None]] = None) -> ProcessingResult:
    """Convenience function for sync bag filtering"""
    config = FilterConfig(
        topics=topics,
        time_range=time_range,
        compression=compression,
        output_path=output_path,
        overwrite=overwrite
    )
    return get_engine()._filter_bag_sync(input_path, config, progress_callback)


async def analyze_bag_async(bag_path: Path,
                           analysis_type: AnalysisType = AnalysisType.FULL_ANALYSIS,
                           progress_callback: Optional[Callable[[float], None]] = None) -> AnalysisResult:
    """Convenience function for async bag analysis"""
    return await get_engine().analyze_bag_async(bag_path, analysis_type, progress_callback) 