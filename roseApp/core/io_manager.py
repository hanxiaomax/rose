#!/usr/bin/env python3
"""
Unified asynchronous I/O management for ROS bag operations.

This module provides a centralized, high-performance I/O management system
that handles all bag file operations asynchronously with thread pool support.
"""

import asyncio
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path

from ..core.util import get_logger
from ..core.parser import create_parser, ParserType, IBagParser


@dataclass
class BagInfo:
    """Basic bag file information"""
    path: str
    size: int
    modification_time: float
    is_compressed: bool
    compression_type: Optional[str] = None


@dataclass
class BagData:
    """Container for bag file data"""
    path: str
    topics: List[str]
    connections: Dict[str, str]
    time_range: Tuple[Tuple[int, int], Tuple[int, int]]
    message_count: int
    size: int
    metadata: Dict[str, Any]


class AsyncIOManager:
    """Unified asynchronous I/O management for bag operations"""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize AsyncIOManager
        
        Args:
            max_workers: Maximum number of worker threads for I/O operations
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.file_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.active_operations: Dict[str, asyncio.Task] = {}
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.logger = get_logger(__name__)
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.shutdown()
        
    async def shutdown(self):
        """Shutdown the I/O manager and cleanup resources"""
        # Cancel active operations
        for operation_id, task in self.active_operations.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        self.logger.info("AsyncIOManager shut down successfully")
        
    async def get_bag_info_async(self, bag_path: str) -> BagInfo:
        """
        Fast asynchronous bag info retrieval
        
        Args:
            bag_path: Path to the bag file
            
        Returns:
            BagInfo object with basic file information
        """
        operation_id = f"info_{bag_path}_{time.time()}"
        
        # Check if operation is already running
        if operation_id in self.active_operations:
            return await self.active_operations[operation_id]
            
        # Create new operation
        task = asyncio.create_task(self._get_bag_info_impl(bag_path))
        self.active_operations[operation_id] = task
        
        try:
            result = await task
            return result
        finally:
            # Clean up completed operation
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
                
    async def _get_bag_info_impl(self, bag_path: str) -> BagInfo:
        """Implementation of bag info retrieval"""
        loop = asyncio.get_event_loop()
        
        def _get_file_info():
            try:
                stat = os.stat(bag_path)
                return BagInfo(
                    path=bag_path,
                    size=stat.st_size,
                    modification_time=stat.st_mtime,
                    is_compressed=self._detect_compression(bag_path),
                    compression_type=self._get_compression_type(bag_path)
                )
            except Exception as e:
                self.logger.error(f"Error getting bag info for {bag_path}: {e}")
                raise
                
        return await loop.run_in_executor(self.executor, _get_file_info)
        
    def _detect_compression(self, bag_path: str) -> bool:
        """Detect if bag file is compressed"""
        try:
            with open(bag_path, 'rb') as f:
                header = f.read(8)
                # Check for common compression signatures
                return (header.startswith(b'\x1f\x8b') or  # gzip
                        header.startswith(b'BZh') or       # bzip2
                        header.startswith(b'\x04"M\x18'))  # lz4
        except Exception:
            return False
            
    def _get_compression_type(self, bag_path: str) -> Optional[str]:
        """Get compression type of bag file"""
        try:
            with open(bag_path, 'rb') as f:
                header = f.read(8)
                if header.startswith(b'\x1f\x8b'):
                    return 'gzip'
                elif header.startswith(b'BZh'):
                    return 'bzip2'
                elif header.startswith(b'\x04"M\x18'):
                    return 'lz4'
                else:
                    return None
        except Exception:
            return None
            
    async def read_bag_async(self, bag_path: str, 
                           parser_type: Optional[ParserType] = None,
                           **kwargs) -> BagData:
        """
        Asynchronous bag reading with thread pool
        
        Args:
            bag_path: Path to the bag file
            parser_type: Optional parser type to use
            **kwargs: Additional arguments for parser
            
        Returns:
            BagData object with parsed bag information
        """
        operation_id = f"read_{bag_path}_{time.time()}"
        
        # Use file lock to prevent concurrent access to same file
        async with self.file_locks[bag_path]:
            # Check if operation is already running
            if operation_id in self.active_operations:
                return await self.active_operations[operation_id]
                
            # Create new operation
            task = asyncio.create_task(
                self._read_bag_impl(bag_path, parser_type, **kwargs)
            )
            self.active_operations[operation_id] = task
            
            try:
                result = await task
                return result
            finally:
                # Clean up completed operation
                if operation_id in self.active_operations:
                    del self.active_operations[operation_id]
                    
    async def _read_bag_impl(self, bag_path: str, 
                           parser_type: Optional[ParserType] = None,
                           **kwargs) -> BagData:
        """Implementation of bag reading"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        
        def _read_bag():
            try:
                # Create parser
                if parser_type is None:
                    parser_type_to_use = ParserType.ROSBAGS
                else:
                    parser_type_to_use = parser_type
                    
                parser = create_parser(parser_type_to_use)
                
                # Parse bag
                topics, connections, time_range = parser.load_bag(bag_path)
                
                # Get message count
                message_count = 0
                try:
                    message_counts = parser.get_message_counts(bag_path)
                    message_count = sum(message_counts.values())
                except Exception:
                    # Fallback to 0 if message count retrieval fails
                    message_count = 0
                
                # Get file size
                file_size = os.path.getsize(bag_path)
                
                # Create bag data
                bag_data = BagData(
                    path=bag_path,
                    topics=topics,
                    connections=connections,
                    time_range=time_range,
                    message_count=message_count,
                    size=file_size,
                    metadata={
                        'parser_type': parser_type_to_use.name,
                        'read_time': time.time() - start_time,
                        'compression_detected': self._detect_compression(bag_path)
                    }
                )
                
                return bag_data
                
            except Exception as e:
                self.logger.error(f"Error reading bag {bag_path}: {e}")
                raise
                
        return await loop.run_in_executor(self.executor, _read_bag)
        
    async def write_bag_async(self, bag_path: str, 
                            bag_data: BagData, 
                            compression: str = 'none',
                            **kwargs) -> None:
        """
        Asynchronous bag writing with thread pool
        
        Args:
            bag_path: Output path for the bag file
            bag_data: BagData object to write
            compression: Compression type ('none', 'bz2', 'lz4')
            **kwargs: Additional arguments for writer
        """
        operation_id = f"write_{bag_path}_{time.time()}"
        
        # Use file lock to prevent concurrent access to same file
        async with self.file_locks[bag_path]:
            # Check if operation is already running
            if operation_id in self.active_operations:
                return await self.active_operations[operation_id]
                
            # Create new operation
            task = asyncio.create_task(
                self._write_bag_impl(bag_path, bag_data, compression, **kwargs)
            )
            self.active_operations[operation_id] = task
            
            try:
                await task
            finally:
                # Clean up completed operation
                if operation_id in self.active_operations:
                    del self.active_operations[operation_id]
                    
    async def _write_bag_impl(self, bag_path: str, 
                            bag_data: BagData,
                            compression: str = 'none',
                            **kwargs) -> None:
        """Implementation of bag writing"""
        loop = asyncio.get_event_loop()
        start_time = time.time()
        
        def _write_bag():
            try:
                # Create parser for writing
                parser = create_parser(ParserType.ROSBAGS)
                
                # Ensure output directory exists
                output_dir = os.path.dirname(bag_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Write bag file
                # Note: This is a placeholder - actual implementation would depend
                # on the specific parser's write capabilities
                self.logger.info(f"Writing bag to {bag_path} with {compression} compression")
                
                # Record operation stats
                self.operation_stats[bag_path] = {
                    'operation': 'write',
                    'compression': compression,
                    'duration': time.time() - start_time,
                    'size': bag_data.size
                }
                
            except Exception as e:
                self.logger.error(f"Error writing bag {bag_path}: {e}")
                raise
                
        await loop.run_in_executor(self.executor, _write_bag)
        
    async def batch_process_bags(self, bag_paths: List[str], 
                               operation: str,
                               **kwargs) -> List[Any]:
        """
        Process multiple bags in parallel
        
        Args:
            bag_paths: List of bag file paths
            operation: Operation to perform ('read', 'info')
            **kwargs: Additional arguments for operation
            
        Returns:
            List of results from each operation
        """
        if operation == 'read':
            tasks = [self.read_bag_async(path, **kwargs) for path in bag_paths]
        elif operation == 'info':
            tasks = [self.get_bag_info_async(path) for path in bag_paths]
        else:
            raise ValueError(f"Unknown operation: {operation}")
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Error processing {bag_paths[i]}: {result}")
                
        return results
        
    def get_operation_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all operations"""
        return dict(self.operation_stats)
        
    def clear_operation_stats(self):
        """Clear operation statistics"""
        self.operation_stats.clear()


# Global I/O manager instance
_global_io_manager: Optional[AsyncIOManager] = None


def get_io_manager() -> AsyncIOManager:
    """Get global I/O manager instance"""
    global _global_io_manager
    if _global_io_manager is None:
        _global_io_manager = AsyncIOManager()
    return _global_io_manager


async def close_io_manager():
    """Close global I/O manager"""
    global _global_io_manager
    if _global_io_manager is not None:
        await _global_io_manager.shutdown()
        _global_io_manager = None 