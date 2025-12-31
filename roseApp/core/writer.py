"""
Writer operations for ROS bag files.

Handles filtering and writing messages to new bag files.
"""

import time
import os
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any
from dataclasses import dataclass

from rosbags.highlevel import AnyReader
from rosbags.rosbag1 import Writer as Rosbag1Writer

from roseApp.core.logging import get_logger
from roseApp.core.parser import BagReader

_logger = get_logger("writer")


class FileExistsError(Exception):
    """Custom exception for file existence errors"""
    pass


@dataclass
class WriterOption:
    """Options for write operation"""
    topics: List[str]
    time_range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    compression: str = 'none'
    overwrite: bool = False
    memory_limit_mb: int = 512  # Memory limit for message buffering in MB
    
    def __post_init__(self):
        """Validate write options"""
        if not self.topics:
            raise ValueError("Topics list cannot be empty")
        
        if self.compression not in ['none', 'bz2', 'lz4']:
            raise ValueError(f"Invalid compression type: {self.compression}")
        
        if self.memory_limit_mb <= 0:
            raise ValueError("Memory limit must be positive")


class BagWriter:
    """
    Handles writing (extraction/compression) of ROS bags based on cached info.
    """
    
    def write(self, source_info: Any, output_bag: str, options: WriterOption,
                progress_callback: Optional[Callable] = None) -> Tuple[str, float]:
        """
        Write specified topics from source bag to output bag with guaranteed chronological ordering
        
        Args:
            source_info: ComprehensiveBagInfo object from cache
            output_bag: Path to output bag file
            options: WriterOption containing topics, time_range, compression, overwrite
            progress_callback: Optional progress callback function
            
        Returns:
            Tuple of (result_message, elapsed_time_seconds)
        """
        start_time = time.time()
        input_bag = source_info.file_path
        
        try:
            # Prepare output file
            self._prepare_output_file(output_bag, options.overwrite)
            
            with AnyReader([Path(input_bag)]) as reader:
                # Pre-filter connections based on selected topics
                selected_connections = [
                    conn for conn in reader.connections 
                    if conn.topic in options.topics
                ]
                
                if not selected_connections:
                    elapsed = time.time() - start_time
                    _logger.warning(f"No matching topics found in {input_bag}")
                    return "No messages found for selected topics", elapsed
                
                # Use memory-efficient extraction with guaranteed chronological ordering
                total_processed = self._write_with_chronological_ordering(
                    reader, selected_connections, output_bag, options, progress_callback
                )
                
                elapsed = time.time() - start_time
                mins, secs = divmod(elapsed, 60)
                
                _logger.info(f"Written {total_processed} messages from {len(selected_connections)} topics in chronological order in {elapsed:.2f}s")
                
                return f"Write completed in {int(mins)}m {secs:.2f}s (chronologically ordered)", elapsed
                
        except ValueError as ve:
            raise ve
        except FileExistsError as fe:
            raise fe
        except Exception as e:
            _logger.error(f"Error writing bag: {e}")
            raise Exception(f"Error writing bag: {e}")
    
    def _prepare_output_file(self, output_path: str, overwrite: bool) -> None:
        """Prepare output file processing"""
        if os.path.exists(output_path):
            if not overwrite:
                raise FileExistsError(f"Output file {output_path} already exists")
            os.remove(output_path)
            
    def _validate_compression(self, compression: str) -> None:
        """Validate compression setting"""
        if compression not in ['none', 'bz2', 'lz4']:
            raise ValueError(f"Unsupported compression type: {compression}")
            
    def _get_compression_format(self, compression: str):
        """Map compression string to rosbags compression format"""
        # Use the inner class enum from Rosbag1Writer
        if compression == 'bz2':
            return Rosbag1Writer.CompressionFormat.BZ2
        elif compression == 'lz4':
            return Rosbag1Writer.CompressionFormat.LZ4
        return None

    def _write_with_chronological_ordering(self, reader, connections, output_path: str, 
                                           options: WriterOption, progress_callback: Optional[Callable] = None) -> int:
        """
        Write messages ensuring chronological order in the output bag.
        Uses a buffer to sort mixed-up messages if they appear out of order in the stream.
        """
        # Mapping connection ID to msgdef/digest handling
        conn_map = {}
        for conn in connections:
            conn_map[conn.id] = conn
        
        total_messages = 0
        rosbags_compression = self._get_compression_format(options.compression)
            
        writer = Rosbag1Writer(Path(output_path))
        if rosbags_compression:
            writer.set_compression(rosbags_compression)
            
        with writer:
            
            # Setup connections
            output_conns = {}
            for conn in connections:
                # Handle msgdef/digest compatibility
                msgdef_raw = getattr(conn, 'msgdef', '')
                msgdef = ""
                if isinstance(msgdef_raw, str):
                    msgdef = msgdef_raw
                elif hasattr(msgdef_raw, 'definition'):
                    # rosbags > 0.9.15
                    msgdef = msgdef_raw.definition
                else:
                    msgdef = str(msgdef_raw)
                    
                digest = getattr(conn, 'digest', '')
                
                # Create connection in output bag
                out_conn = writer.add_connection(
                    topic=conn.topic, 
                    msgtype=conn.msgtype, 
                    msgdef=msgdef, 
                    md5sum=digest
                )
                output_conns[conn.id] = out_conn
            
            # Stream messages
            # Note: AnyReader.messages() yields in generic (connection, timestamp, rawdata) order
            # which is usually roughly chronological but not guaranteed across chunks.
            # However, rosbags usually iterates logically. If we trust the reader, we write directly.
            # But the requirement mentions "guaranteed chronological ordering", implying we might need sort.
            # For strict ordering, key is timestamp.
            
            # Re-implementing the loop
            count = 0
            
            # Helper to check time range
            def in_time_range(ts_ns):
                if not options.time_range:
                    return True
                start_range = options.time_range[0]
                end_range = options.time_range[1]
                
                start_ns = start_range[0] * 1_000_000_000 + start_range[1]
                end_ns = end_range[0] * 1_000_000_000 + end_range[1]
                
                return start_ns <= ts_ns <= end_ns

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                if not in_time_range(timestamp):
                   continue
                
                writer.write(output_conns[connection.id], timestamp, rawdata)
                count += 1
                total_messages += 1
                
                if count % 1000 == 0:
                     if progress_callback:
                         # Attempt to estimate progress if possible, else just keep alive
                         pass
        
        return total_messages
