"""
Async bag processing engine with intelligent I/O management
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from .parser import create_best_parser, IBagParser
from .analyzer import analyze_bag_async, AnalysisType
from .cache import get_cache
from .util import get_logger


class CompressionType(Enum):
    """Supported compression types"""
    NONE = "none"
    BZ2 = "bz2" 
    LZ4 = "lz4"


@dataclass
class FilterConfig:
    """Configuration for bag filtering"""
    topics: List[str]
    time_range: Optional[tuple] = None
    compression: str = CompressionType.NONE.value
    output_path: Optional[Path] = None
    overwrite: bool = False


@dataclass
class ProcessingResult:
    """Result of bag processing operation"""
    success: bool
    input_path: Path
    output_path: Optional[Path] = None
    processing_time: float = 0.0
    error_message: str = ""
    output_size: int = 0

    @property
    def size_str(self) -> str:
        """Human readable size string"""
        if self.output_size == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(self.output_size)
        
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {units[i]}"


class AsyncIOManager:
    """Async I/O manager for file operations"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = get_logger()
    
    async def copy_file_async(self, src: Path, dest: Path) -> bool:
        """Copy file asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _copy_file():
            try:
                import shutil
                shutil.copy2(src, dest)
                return True
            except Exception as e:
                self.logger.error(f"Failed to copy {src} to {dest}: {e}")
                return False
        
        return await loop.run_in_executor(self.executor, _copy_file)
    
    async def delete_file_async(self, file_path: Path) -> bool:
        """Delete file asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _delete_file():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                self.logger.error(f"Failed to delete {file_path}: {e}")
                return False
        
        return await loop.run_in_executor(self.executor, _delete_file)
    
    async def ensure_directory_async(self, dir_path: Path) -> bool:
        """Ensure directory exists asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _ensure_dir():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                return True
            except Exception as e:
                self.logger.error(f"Failed to create directory {dir_path}: {e}")
                return False
        
        return await loop.run_in_executor(self.executor, _ensure_dir)
    
    def cleanup(self):
        """Clean up resources"""
        self.executor.shutdown(wait=True)


class BagEngine:
    """Async bag processing engine - High-level workflow orchestration"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.io_manager = AsyncIOManager(max_workers=max_workers)
        self.cache = get_cache()
        self.logger = get_logger()
        self._parser: Optional[IBagParser] = None
    
    def _get_parser(self) -> IBagParser:
        """Get or create parser instance"""
        if self._parser is None:
            self._parser = create_best_parser()
        return self._parser
    
    async def analyze_bag_async(
        self,
        bag_path: Path,
        analysis_type: AnalysisType = AnalysisType.METADATA,
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        """Analyze bag file asynchronously"""
        return await analyze_bag_async(
            bag_path=bag_path,
            analysis_type=analysis_type,
            progress_callback=progress_callback
        )
    
    async def filter_bag_async(
        self,
        input_path: Path,
        topics: List[str],
        output_path: Optional[Path] = None,
        compression: str = CompressionType.NONE.value,
        time_range: Optional[tuple] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> ProcessingResult:
        """Filter bag file asynchronously - orchestrates the filtering workflow"""
        start_time = time.time()
        
        # Generate output path if not provided
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_filtered.bag"
        
        # Check if output exists and overwrite policy
        if output_path.exists() and not overwrite:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                processing_time=time.time() - start_time,
                error_message="Output file exists and overwrite is disabled"
            )
        
        try:
            if progress_callback:
                progress_callback(10.0)
            
            # Ensure output directory exists
            await self.io_manager.ensure_directory_async(output_path.parent)
            
            if progress_callback:
                progress_callback(20.0)
            
            # Perform filtering using parser in thread pool
            loop = asyncio.get_event_loop()
            parser = self._get_parser()
            
            def _filter_operation():
                return parser.filter_bag(
                    str(input_path),
                    str(output_path), 
                    topics,
                    compression=compression,
                    time_range=time_range,
                    overwrite=overwrite
                )
            
            if progress_callback:
                progress_callback(50.0)
            
            # Run filtering in executor
            await loop.run_in_executor(
                self.io_manager.executor,
                _filter_operation
            )
            
            if progress_callback:
                progress_callback(90.0)
            
            # Get output size
            output_size = output_path.stat().st_size if output_path.exists() else 0
            
            if progress_callback:
                progress_callback(100.0)
            
            self.logger.info(f"Filtered {input_path} -> {output_path} ({output_size} bytes)")
            
            return ProcessingResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                processing_time=time.time() - start_time,
                output_size=output_size
            )
            
        except Exception as e:
            self.logger.error(f"Failed to filter bag {input_path}: {e}")
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def filter_multiple_bags_async(
        self,
        input_paths: List[Path],
        config: FilterConfig,
        progress_callback: Optional[Callable[[Path, float], None]] = None
    ) -> Dict[Path, ProcessingResult]:
        """Filter multiple bags concurrently"""
        results = {}
        
        # Create tasks for concurrent processing
        async def process_bag(bag_path: Path) -> ProcessingResult:
            progress_cb: Optional[Callable[[float], None]] = None
            if progress_callback is not None:
                progress_cb = lambda p: progress_callback(bag_path, p)
            
            output_path = None
            if config.output_path:
                output_path = config.output_path / f"{bag_path.stem}_filtered.bag"
            
            return await self.filter_bag_async(
                input_path=bag_path,
                topics=config.topics,
                output_path=output_path,
                compression=config.compression,
                time_range=config.time_range,
                overwrite=config.overwrite,
                progress_callback=progress_cb
            )
        
        # Execute all tasks concurrently
        tasks = [process_bag(bag_path) for bag_path in input_paths]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for bag_path, result in zip(input_paths, task_results):
            if isinstance(result, Exception):
                results[bag_path] = ProcessingResult(
                    success=False,
                    input_path=bag_path,
                    error_message=str(result)
                )
            else:
                results[bag_path] = result
        
        return results
    
    async def copy_bag_async(
        self,
        input_path: Path,
        output_path: Path,
        overwrite: bool = False
    ) -> ProcessingResult:
        """Copy bag file asynchronously"""
        start_time = time.time()
        
        if output_path.exists() and not overwrite:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                processing_time=time.time() - start_time,
                error_message="Output file exists and overwrite is disabled"
            )
        
        try:
            # Ensure output directory exists
            await self.io_manager.ensure_directory_async(output_path.parent)
            
            # Copy the file
            success = await self.io_manager.copy_file_async(input_path, output_path)
            
            if success:
                output_size = output_path.stat().st_size
                return ProcessingResult(
                    success=True,
                    input_path=input_path,
                    output_path=output_path,
                    processing_time=time.time() - start_time,
                    output_size=output_size
                )
            else:
                return ProcessingResult(
                    success=False,
                    input_path=input_path,
                    output_path=output_path,
                    processing_time=time.time() - start_time,
                    error_message="Copy operation failed"
                )
                
        except Exception as e:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def validate_bag_async(self, bag_path: Path) -> Dict[str, Any]:
        """Validate bag file asynchronously using parser"""
        try:
            loop = asyncio.get_event_loop()
            parser = self._get_parser()
            
            def _validate():
                try:
                    topics, connections, time_range = parser.load_bag(str(bag_path))
                    message_counts = parser.get_message_counts(str(bag_path))
                    
                    return {
                        'valid': True,
                        'errors': [],
                        'message_count': sum(message_counts.values()),
                        'topic_count': len(topics),
                        'duration': time_range[1] - time_range[0] if time_range else 0,
                        'file_size': bag_path.stat().st_size
                    }
                except Exception as e:
                    return {
                        'valid': False,
                        'errors': [str(e)],
                        'message_count': 0,
                        'topic_count': 0
                    }
            
            return await loop.run_in_executor(self.io_manager.executor, _validate)
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [str(e)],
                'message_count': 0,
                'topic_count': 0
            }
    
    async def get_bag_statistics_async(self, bag_path: Path) -> Dict[str, Any]:
        """Get detailed bag statistics asynchronously using parser"""
        try:
            loop = asyncio.get_event_loop()
            parser = self._get_parser()
            
            def _get_stats():
                try:
                    topics, connections, time_range = parser.load_bag(str(bag_path))
                    topic_stats = parser.get_topic_stats(str(bag_path))
                    
                    total_messages = sum(stats['count'] for stats in topic_stats.values())
                    duration = time_range[1] - time_range[0] if time_range else 0
                    
                    stats = {
                        'file_path': str(bag_path),
                        'file_size': bag_path.stat().st_size,
                        'topic_count': len(topics),
                        'total_messages': total_messages,
                        'duration_seconds': duration,
                        'topics': {}
                    }
                    
                    # Add per-topic statistics
                    for topic in topics:
                        topic_stat = topic_stats.get(topic, {'count': 0})
                        msg_count = topic_stat['count']
                        msg_type = connections.get(topic, 'unknown')
                        frequency = msg_count / duration if duration > 0 else 0.0
                        
                        stats['topics'][topic] = {
                            'message_type': msg_type,
                            'message_count': msg_count,
                            'frequency_hz': frequency
                        }
                    
                    return stats
                    
                except Exception as e:
                    return {
                        'file_path': str(bag_path),
                        'error': str(e)
                    }
            
            return await loop.run_in_executor(self.io_manager.executor, _get_stats)
            
        except Exception as e:
            self.logger.error(f"Failed to get bag statistics: {e}")
            return {
                'file_path': str(bag_path),
                'error': str(e)
            }
    
    def cleanup(self):
        """Clean up resources"""
        self.io_manager.cleanup()


# Global engine instance
_engine = None


def get_engine() -> BagEngine:
    """Get or create global engine instance"""
    global _engine
    if _engine is None:
        _engine = BagEngine()
    return _engine


async def filter_bag_async(
    input_path: Path,
    topics: List[str],
    output_path: Optional[Path] = None,
    compression: str = CompressionType.NONE.value,
    time_range: Optional[tuple] = None,
    overwrite: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None
) -> ProcessingResult:
    """Filter bag file asynchronously - main public interface"""
    engine = get_engine()
    return await engine.filter_bag_async(
        input_path=input_path,
        topics=topics,
        output_path=output_path,
        compression=compression,
        time_range=time_range,
        overwrite=overwrite,
        progress_callback=progress_callback
    )


def cleanup_engine():
    """Clean up global engine"""
    global _engine
    if _engine:
        _engine.cleanup()
        _engine = None 