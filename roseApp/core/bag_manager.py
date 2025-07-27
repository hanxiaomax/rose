"""
Unified Bag Manager - High-level interface for all bag operations
Provides a single entry point for CLI commands to interact with ROS bags
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from .parser import BagParser, ComprehensiveBagInfo, ExtractOption
from .cache import get_cache
from .ui_control import UIControl, OutputFormat, RenderOptions, ExportOptions


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
    Provides high-level interface for CLI commands
    """
    
    def __init__(self, max_workers: int = 4):
        """Initialize the bag manager"""
        self.logger = logging.getLogger(__name__)
        self.parser = BagParser()
        self.cache = get_cache()
        self.ui_control = UIControl()
        self.max_workers = max_workers
        
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
        
        # Clear cache if requested
        if options.no_cache:
            self.parser.clear()
        
        # Get bag details first
        bag_details, analysis_time = self.parser.get_bag_details(str(bag_path))
        
        # Perform full analysis if we need topic sizes or field analysis
        if options.show_fields or options.sort_by == "size":
            bag_details, full_analysis_time = self.parser.analyze_bag_full(str(bag_path))
            analysis_time += full_analysis_time
        
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
                'analysis_time': analysis_time,
                'cached': bag_details.analysis_level.value != "none"
            },
            'topics': [],
            'field_analysis': {},
            'cache_stats': self._get_cache_stats()
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
        
        return inspection_result
    
    async def list_topics(
        self,
        bag_path: Union[str, Path],
        patterns: Optional[List[str]] = None,
        exact_match: bool = False,
        progress_callback: Optional[Callable[[float], None]] = None,
        no_cache: bool = False
    ) -> Dict[str, Any]:
        """
        List topics in a ROS bag file with optional filtering
        
        Args:
            bag_path: Path to the bag file
            patterns: Optional list of topic patterns to match
            exact_match: If True, use exact matching instead of fuzzy matching
            progress_callback: Optional progress callback
            no_cache: If True, bypass cache
            
        Returns:
            Dictionary containing topic listing results
        """
        bag_path = Path(bag_path)
        
        if not bag_path.exists():
            raise FileNotFoundError(f"Bag file not found: {bag_path}")
        
        # Clear cache if requested
        if no_cache:
            self.parser.clear()
        
        # Get bag details
        bag_details, analysis_time = self.parser.get_bag_details(str(bag_path))
        
        all_topics = bag_details.topics or []
        
        # Apply filtering if patterns are provided
        if patterns:
            if exact_match:
                filtered_topics = [topic for topic in all_topics if topic in patterns]
            else:
                # Use the same fuzzy matching logic as _filter_topics
                filtered_topics = self._filter_topics(all_topics, patterns, None)
        else:
            filtered_topics = all_topics
        
        # Build topic listing results
        listing_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'total_topics': len(all_topics),
                'filtered_topics': len(filtered_topics),
                'analysis_time': analysis_time
            },
            'topics': [],
            'filtering': {
                'patterns': patterns or [],
                'exact_match': exact_match,
                'matched_topics': len(filtered_topics)
            }
        }
        
        # Add topic information
        for topic in filtered_topics:
            message_type = bag_details.connections.get(topic, 'Unknown') if bag_details.connections else 'Unknown'
            message_count = bag_details.message_counts.get(topic, 0) if bag_details.message_counts else 0
            
            topic_info = {
                'name': topic,
                'message_type': message_type,
                'message_count': message_count
            }
            listing_result['topics'].append(topic_info)
        
        return listing_result
    
    async def extract_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[ExtractOptions] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Extract topics from a ROS bag file
        
        Args:
            bag_path: Path to the source bag file
            options: Extraction options
            
        Returns:
            Dictionary containing extraction results
        """
        if options is None:
            options = ExtractOptions()
            
        bag_path = Path(bag_path)
        
        # Clear cache if requested
        if options.no_cache:
            self.parser.clear()
        
        # Get bag metadata first
        bag_details, _ = self.parser.get_bag_details(str(bag_path))
        
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
        
        # Perform extraction if not dry run
        extraction_error = None
        if not options.dry_run:
            try:
                _, extract_time = self.parser.extract(str(bag_path), str(output_path), extract_option, progress_callback)
            except Exception as e:
                self.logger.error(f"Extraction failed: {e}")
                extraction_error = str(e)
                extract_time = 0.0
        else:
            extract_time = 0.0
        
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
        
        return extraction_result
    
    async def profile_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[ProfileOptions] = None
    ) -> Dict[str, Any]:
        """
        Profile a ROS bag file to analyze performance characteristics
        
        Args:
            bag_path: Path to the bag file
            options: Profiling options
            
        Returns:
            Dictionary containing profiling results
        """
        if options is None:
            options = ProfileOptions()
            
        # Get bag details for profiling
        bag_details, analysis_time = self.parser.get_bag_details(str(bag_path))
        
        # Apply topic filtering
        topics_to_profile = self._filter_topics(
            bag_details.topics or [],
            options.topics,
            None
        )
        
        # Calculate average rate
        total_messages = sum(bag_details.message_counts.values()) if bag_details.message_counts else 0
        average_rate = total_messages / bag_details.duration_seconds if bag_details.duration_seconds and bag_details.duration_seconds > 0 else 0
        
        # Build profiling results
        profile_result = {
            'bag_info': {
                'file_name': Path(bag_path).name,
                'total_topics': len(topics_to_profile),
                'total_messages': sum(bag_details.message_counts.get(topic, 0) for topic in topics_to_profile) if bag_details.message_counts else 0,
                'duration_seconds': bag_details.duration_seconds or 0.0,
                'average_rate': average_rate
            },
            'topic_statistics': [],
            'performance_metrics': {
                'analysis_time': analysis_time,
                'cached': bag_details.analysis_level.value != "none",
                'cache_hit_rate': self._get_cache_hit_rate()
            }
        }
        
        # Calculate topic statistics
        for topic in topics_to_profile:
            message_count = bag_details.message_counts.get(topic, 0) if bag_details.message_counts else 0
            frequency = message_count / bag_details.duration_seconds if bag_details.duration_seconds and bag_details.duration_seconds > 0 else 0
            
            topic_stats = {
                'topic': topic,
                'message_type': bag_details.connections.get(topic, 'Unknown') if bag_details.connections else 'Unknown',
                'message_count': message_count,
                'frequency': frequency,
                'percentage': (message_count / total_messages) * 100 if total_messages > 0 else 0
            }
            
            profile_result['topic_statistics'].append(topic_stats)
        
        return profile_result
    
    async def diagnose_bag(
        self,
        bag_path: Union[str, Path],
        options: Optional[DiagnoseOptions] = None
    ) -> Dict[str, Any]:
        """
        Diagnose a ROS bag file for potential issues
        
        Args:
            bag_path: Path to the bag file
            options: Diagnosis options
            
        Returns:
            Dictionary containing diagnosis results
        """
        if options is None:
            options = DiagnoseOptions()
            
        bag_path = Path(bag_path)
        
        # Get bag details for diagnosis
        bag_details, _ = self.parser.get_bag_details(str(bag_path))
        
        diagnosis_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'file_exists': bag_path.exists(),
                'file_size': bag_path.stat().st_size if bag_path.exists() else 0
            },
            'checks': [],
            'issues': [],
            'warnings': [],
            'summary': {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 0,
                'warnings_count': 0
            }
        }
        
        # Perform various diagnostic checks
        checks = [
            self._check_file_integrity(bag_path, bag_details),
            self._check_timestamps(bag_details),
            self._check_message_counts(bag_details)
        ]
        
        # Process check results
        for check in checks:
            diagnosis_result['checks'].append(check)
            diagnosis_result['summary']['total_checks'] += 1
            
            if check['passed']:
                diagnosis_result['summary']['passed_checks'] += 1
            else:
                diagnosis_result['summary']['failed_checks'] += 1
                diagnosis_result['issues'].append({
                    'check': check['name'],
                    'message': check['message']
                })
        
        return diagnosis_result
    
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
        try:
            if hasattr(self.cache, 'get_stats'):
                stats = self.cache.get_stats()
                # Extract unified stats from the complex structure
                unified_stats = stats.get('unified', {})
                return {
                    'hit_rate': unified_stats.get('hit_rate', 0.0),
                    'total_requests': unified_stats.get('hits', 0) + unified_stats.get('misses', 0),
                    'cache_hits': unified_stats.get('hits', 0),
                    'cache_misses': unified_stats.get('misses', 0)
                }
            else:
                return {'hit_rate': 0.0, 'total_requests': 0, 'cache_hits': 0, 'cache_misses': 0}
        except Exception as e:
            # Log the error for debugging but don't crash
            self.logger.warning(f"Error getting cache stats: {e}")
            return {'hit_rate': 0.0, 'total_requests': 0, 'cache_hits': 0, 'cache_misses': 0}
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate percentage"""
        stats = self._get_cache_stats()
        return stats['hit_rate']
    
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