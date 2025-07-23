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

from .analyzer import BagAnalyzer, AnalysisResult, AnalysisType
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
    Unified high-level interface for all ROS bag operations
    
    This class provides a simple, consistent API for CLI commands to interact
    with ROS bags without needing to understand the underlying complexity.
    
    Example usage:
        manager = BagManager()
        result = await manager.inspect_bag("demo.bag", options)
        
        # Render results
        handler = manager.get_result_handler()
        handler.render(result, RenderOptions(format=OutputFormat.TABLE))
        
        # Export results
        handler.export(result, ExportOptions(format=OutputFormat.JSON, output_file=Path("report.json")))
    """
    
    def __init__(self, max_workers: int = 4):
        """Initialize the bag manager"""
        self.analyzer = BagAnalyzer(max_workers=max_workers)
        self.cache = get_cache()
        self.logger = logging.getLogger(__name__)
        self._result_handler = None
        
    def get_result_handler(self) -> UIControl:
        """Get the result handler instance for rendering and exporting"""
        if self._result_handler is None:
            self._result_handler = UIControl()
        return self._result_handler
        
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
            
        Returns:
            Dictionary containing inspection results
        """
        if options is None:
            options = InspectOptions()
            
        bag_path = Path(bag_path)
        
        # Determine analysis type based on options
        analysis_type = AnalysisType.FULL_ANALYSIS if options.show_fields else AnalysisType.METADATA
        
        # Perform bag analysis
        result = await self.analyzer.analyze_bag_async(
            bag_path, 
            analysis_type,
            progress_callback=progress_callback,
            no_cache=options.no_cache
        )
        
        # Apply topic filtering if specified
        filtered_topics = self._filter_topics(
            list(result.bag_info.topics), 
            options.topics, 
            options.topic_filter
        )
        
        # Prepare inspection results
        inspection_result = {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'file_size': bag_path.stat().st_size if bag_path.exists() else 0,
                'topics_count': len(filtered_topics),
                'total_messages': sum(result.bag_info.message_counts.get(topic, 0) for topic in filtered_topics),
                'duration_seconds': result.bag_info.duration_seconds,
                'time_range': result.bag_info.time_range,
                'analysis_time': result.analysis_time,
                'cached': result.cached
            },
            'topics': [],
            'field_analysis': {},
            'cache_stats': self._get_cache_stats()
        }
        
        # Get topic sizes using parser
        topic_sizes = {}
        try:
            from .parser import create_parser, ParserType
            parser = create_parser(ParserType.ROSBAGS)
            topic_stats = parser.get_topic_stats(str(bag_path))
            topic_sizes = {topic: stats.get('size', 0) for topic, stats in topic_stats.items()}
        except Exception as e:
            self.logger.warning(f"Could not get topic sizes: {e}")
        
        # Build topic information with size data
        topics_with_info = []
        for topic in filtered_topics:
            message_type = result.bag_info.connections.get(topic, 'Unknown')
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            size_bytes = topic_sizes.get(topic, 0)
            
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
            if options.show_fields and result.message_types:
                topic_name = topic_info['name']
                field_paths = result.get_topic_field_paths(topic_name)
                if field_paths:
                    topic_info['field_paths'] = field_paths
                    inspection_result['field_analysis'][topic_name] = {
                        'message_type': message_type,
                        'field_paths': field_paths,
                        'samples_analyzed': len([t for t in filtered_topics if result.bag_info.connections.get(t) == message_type])
                    }
            
            inspection_result['topics'].append(topic_info)
        
        return inspection_result
    
    async def get_topics(
        self,
        bag_path: Union[str, Path],
        patterns: Optional[List[str]] = None,
        exact_match: bool = False,
        progress_callback: Optional[Callable[[float], None]] = None,
        no_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get available topics from a ROS bag file with optional filtering
        
        Args:
            bag_path: Path to the bag file
            patterns: Optional list of patterns to match against topic names
            exact_match: If True, use exact matching; if False, use fuzzy matching
            no_cache: If True, skip cache and reparse the bag file
            
        Returns:
            Dictionary containing topic information
        """
        bag_path = Path(bag_path)
        
        if not bag_path.exists():
            raise FileNotFoundError(f"Bag file not found: {bag_path}")
        
        # Analyze the bag to get available topics
        result = await self.analyzer.analyze_bag_async(
            bag_path, 
            AnalysisType.METADATA,
            progress_callback=progress_callback,
            no_cache=no_cache
        )
        
        all_topics = list(result.bag_info.topics)
        
        # Apply filtering if patterns are provided
        if patterns:
            if exact_match:
                filtered_topics = [topic for topic in all_topics if topic in patterns]
            else:
                # Use the same fuzzy matching logic as _filter_topics
                filtered_topics = self._filter_topics(all_topics, patterns, None)
        else:
            filtered_topics = all_topics
        
        # Get topic sizes using parser
        topic_sizes = {}
        try:
            from .parser import create_parser, ParserType
            parser = create_parser(ParserType.ROSBAGS)
            topic_stats = parser.get_topic_stats(str(bag_path))
            topic_sizes = {topic: stats.get('size', 0) for topic, stats in topic_stats.items()}
        except Exception as e:
            self.logger.warning(f"Could not get topic sizes: {e}")
        
        # Build topic information
        topics_info = []
        for topic in filtered_topics:
            message_type = result.bag_info.connections.get(topic, 'Unknown')
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            estimated_size_bytes = topic_sizes.get(topic, 0)
            
            topics_info.append({
                'name': topic,
                'message_type': message_type,
                'message_count': message_count,
                'frequency': frequency,
                'estimated_size_bytes': estimated_size_bytes
            })
        
        # Sort topics by name
        topics_info.sort(key=lambda x: x['name'])
        
        return {
            'bag_info': {
                'file_name': bag_path.name,
                'file_path': str(bag_path),
                'total_topics': len(all_topics),
                'filtered_topics': len(filtered_topics),
                'duration_seconds': result.bag_info.duration_seconds,
                'analysis_time': result.analysis_time,
                'cached': result.cached
            },
            'topics': topics_info,
            'patterns': patterns or [],
            'exact_match': exact_match,
            'cache_stats': self._get_cache_stats()
        }
    
    async def extract_bag(
        self,
        bag_path: Union[str, Path],
        options: ExtractOptions,
        progress_callback: Optional[Union[Callable[[float], None], Callable[[int, str, int, int, str], None]]] = None
    ) -> Dict[str, Any]:
        """
        Extract specific topics from a ROS bag file
        
        Args:
            bag_path: Path to the input bag file
            options: Extraction options including topics, output path, etc.
            
        Returns:
            Dictionary containing extraction results
        """
        bag_path = Path(bag_path)
        
        if not bag_path.exists():
            raise FileNotFoundError(f"Bag file not found: {bag_path}")
        
        if not options.output_path:
            raise ValueError("Output path is required for extraction")
        
        # Analyze the bag to get available topics
        result = await self.analyzer.analyze_bag_async(
            bag_path, 
            AnalysisType.METADATA,
            no_cache=options.no_cache
        )
        
        # Apply topic filtering using the same logic as inspect
        topics_to_extract = self._filter_topics(
            list(result.bag_info.topics),
            options.topics,
            options.topic_filter
        )
        
        if not topics_to_extract:
            return {
                'success': False,
                'error': 'No matching topics found',
                'available_topics': list(result.bag_info.topics),
                'requested_patterns': options.topics or [],
                'filter': options.topic_filter
            }
        
        # Calculate extraction statistics
        total_messages = sum(result.bag_info.message_counts.values())
        extract_messages = sum(result.bag_info.message_counts.get(topic, 0) for topic in topics_to_extract)
        
        # Get topic sizes using parser
        topic_sizes = {}
        try:
            from .parser import create_parser, ParserType
            parser = create_parser(ParserType.ROSBAGS)
            topic_stats = parser.get_topic_stats(str(bag_path))
            topic_sizes = {topic: stats.get('size', 0) for topic, stats in topic_stats.items()}
        except Exception as e:
            self.logger.warning(f"Could not get topic sizes: {e}")
        
        # Build all_topics information (needed for the summary table)
        all_topics = []
        for topic in result.bag_info.topics:
            message_type = result.bag_info.connections.get(topic, 'Unknown')
            message_count = result.bag_info.message_counts.get(topic, 0)
            estimated_size_bytes = topic_sizes.get(topic, 0)
            
            all_topics.append({
                'name': topic,
                'message_type': message_type,
                'message_count': message_count,
                'estimated_size_bytes': estimated_size_bytes
            })
        
        extraction_result = {
            'input_file': str(bag_path),
            'output_file': str(options.output_path),
            'compression': options.compression,
            'success': True,
            'dry_run': options.dry_run,
            'topics_to_extract': topics_to_extract,
            'all_topics': all_topics,
            'bag_info': {
                'input_file': str(bag_path),
                'output_file': str(options.output_path),
                'total_topics': len(result.bag_info.topics),
                'extracted_topics': len(topics_to_extract),
                'total_messages': total_messages,
                'extracted_messages': extract_messages,
                'extraction_percentage': (extract_messages / total_messages * 100) if total_messages > 0 else 0,
                'duration_seconds': result.bag_info.duration_seconds,
                'compression': options.compression
            },
            'statistics': {
                'total_topics': len(result.bag_info.topics),
                'selected_topics': len(topics_to_extract),
                'excluded_topics': len(result.bag_info.topics) - len(topics_to_extract),
                'total_messages': total_messages,
                'selected_messages': extract_messages,
                'selection_percentage': (len(topics_to_extract) / len(result.bag_info.topics) * 100) if len(result.bag_info.topics) > 0 else 0,
                'message_percentage': (extract_messages / total_messages * 100) if total_messages > 0 else 0
            },
            'topics': []
        }
        
        # Build topic information
        for topic in topics_to_extract:
            message_type = result.bag_info.connections.get(topic, 'Unknown')
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            
            topic_info = {
                'name': topic,
                'message_type': message_type,
                'message_count': message_count,
                'frequency': frequency,
                'size_percentage': (message_count / extract_messages * 100) if extract_messages > 0 else 0
            }
            extraction_result['topics'].append(topic_info)
        
        # If dry run, return without actual extraction
        if options.dry_run:
            extraction_result['message'] = 'Dry run completed - no files were created'
            return extraction_result
        
        # Perform the actual extraction using the analyzer
        try:
            from .parser import create_parser, ParserType
            parser = create_parser(ParserType.ROSBAGS)
            
            # Create output directory if needed
            options.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if output file exists and handle overwrite
            if options.output_path.exists() and not options.overwrite:
                raise FileExistsError(f"Output file already exists: {options.output_path}")
            
            # Use parser to filter/extract the bag with topic-level progress
            if hasattr(parser, 'filter_bag_with_topic_progress') and callable(getattr(parser, 'filter_bag_with_topic_progress')):
                # Use enhanced topic progress if available
                filter_result = parser.filter_bag_with_topic_progress(
                    str(bag_path),
                    str(options.output_path),
                    topics_to_extract,
                    compression=options.compression,
                    overwrite=options.overwrite,
                    topic_progress_callback=progress_callback
                )
            else:
                # Fall back to regular progress callback
                filter_result = parser.filter_bag(
                    str(bag_path),
                    str(options.output_path),
                    topics_to_extract,
                    compression=options.compression,
                    overwrite=options.overwrite,
                    progress_callback=progress_callback
                )
            
            # Calculate output file size and statistics
            if options.output_path.exists():
                input_size = bag_path.stat().st_size
                output_size = options.output_path.stat().st_size
                size_reduction = (1 - output_size / input_size) * 100 if input_size > 0 else 0
                
                extraction_result.update({
                    'file_stats': {
                        'input_size_bytes': input_size,
                        'output_size_bytes': output_size,
                        'size_reduction_percent': size_reduction
                    },
                    'message': f'Successfully extracted {len(topics_to_extract)} topics to {options.output_path}'
                })
                
                # Perform automatic validation of the extracted bag
                try:
                    from .bag_validator import BagValidator, ValidationLevel
                    validator = BagValidator(parser)
                    validation_result = validator.validate_extracted_bag(
                        bag_path, options.output_path, topics_to_extract
                    )
                    
                    # Add validation results to extraction result
                    extraction_result['validation'] = {
                        'is_valid': validation_result.is_valid,
                        'validation_time': validation_result.validation_time,
                        'topics_count': validation_result.topics_count,
                        'total_messages': validation_result.total_messages,
                        'duration_seconds': validation_result.duration_seconds,
                        'file_size_bytes': validation_result.file_size_bytes,
                        'errors': validation_result.errors or [],
                        'warnings': validation_result.warnings or [],
                        'validation_level': validation_result.validation_level.value
                    }
                    
                    # Log validation results
                    if validation_result.is_valid:
                        self.logger.info(f"Bag validation passed for {options.output_path}")
                        if validation_result.warnings:
                            self.logger.warning(f"Validation warnings: {validation_result.warnings}")
                    else:
                        self.logger.error(f"Bag validation failed for {options.output_path}: {validation_result.errors}")
                        
                except Exception as validation_error:
                    self.logger.warning(f"Could not validate extracted bag: {validation_error}")
                    extraction_result['validation'] = {
                        'is_valid': False,
                        'validation_time': 0.0,
                        'errors': [f"Validation failed: {validation_error}"],
                        'warnings': [],
                        'validation_level': 'none'
                    }
                
            else:
                extraction_result.update({
                    'success': False,
                    'error': 'Output file was not created',
                    'message': 'Extraction may have failed'
                })
            
        except Exception as e:
            extraction_result.update({
                'success': False,
                'error': str(e),
                'message': f'Extraction failed: {e}'
            })
            
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
            
        # Analyze the bag for profiling
        result = await self.analyzer.analyze_bag_async(Path(bag_path), AnalysisType.METADATA)
        
        # Apply topic filtering
        topics_to_profile = self._filter_topics(
            list(result.bag_info.topics),
            options.topics,
            None
        )
        
        # Build profiling results
        profile_result = {
            'bag_info': {
                'file_name': Path(bag_path).name,
                'total_topics': len(topics_to_profile),
                'total_messages': sum(result.bag_info.message_counts.get(topic, 0) for topic in topics_to_profile),
                'duration_seconds': result.bag_info.duration_seconds,
                'average_rate': sum(result.bag_info.message_counts.values()) / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            },
            'topic_statistics': [],
            'performance_metrics': {
                'analysis_time': result.analysis_time,
                'cached': result.cached,
                'cache_hit_rate': self._get_cache_hit_rate()
            }
        }
        
        # Calculate topic statistics
        for topic in topics_to_profile:
            message_count = result.bag_info.message_counts.get(topic, 0)
            frequency = message_count / result.bag_info.duration_seconds if result.bag_info.duration_seconds > 0 else 0
            
            topic_stats = {
                'topic': topic,
                'message_type': result.bag_info.connections.get(topic, 'Unknown'),
                'message_count': message_count,
                'frequency': frequency,
                'percentage': (message_count / sum(result.bag_info.message_counts.values())) * 100 if sum(result.bag_info.message_counts.values()) > 0 else 0
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
        
        # Perform bag analysis for diagnosis
        result = await self.analyzer.analyze_bag_async(bag_path, AnalysisType.METADATA)
        
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
        
        # File integrity check
        if options.check_integrity:
            integrity_check = self._check_file_integrity(bag_path, result)
            diagnosis_result['checks'].append(integrity_check)
            if not integrity_check['passed']:
                diagnosis_result['issues'].append(integrity_check['message'])
        
        # Timestamp consistency check  
        if options.check_timestamps:
            timestamp_check = self._check_timestamps(result)
            diagnosis_result['checks'].append(timestamp_check)
            if not timestamp_check['passed']:
                diagnosis_result['issues'].append(timestamp_check['message'])
        
        # Message count validation
        if options.check_message_counts:
            count_check = self._check_message_counts(result)
            diagnosis_result['checks'].append(count_check)
            if not count_check['passed']:
                diagnosis_result['warnings'].append(count_check['message'])
        
        # Update summary
        diagnosis_result['summary']['total_checks'] = len(diagnosis_result['checks'])
        diagnosis_result['summary']['passed_checks'] = sum(1 for check in diagnosis_result['checks'] if check['passed'])
        diagnosis_result['summary']['failed_checks'] = sum(1 for check in diagnosis_result['checks'] if not check['passed'])
        diagnosis_result['summary']['warnings_count'] = len(diagnosis_result['warnings'])
        
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
    
    def _check_file_integrity(self, bag_path: Path, result: AnalysisResult) -> Dict[str, Any]:
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
        elif len(result.errors) > 0:
            check_result.update({
                'passed': False,
                'message': f'Bag file has parsing errors: {", ".join(result.errors)}'
            })
        
        return check_result
    
    def _check_timestamps(self, result: AnalysisResult) -> Dict[str, Any]:
        """Check timestamp consistency"""
        check_result = {
            'name': 'Timestamp Consistency',
            'description': 'Verify timestamps are in chronological order',
            'passed': True,
            'message': 'Timestamps appear consistent'
        }
        
        if result.bag_info.time_range:
            start_time, end_time = result.bag_info.time_range
            if start_time >= end_time:
                check_result.update({
                    'passed': False,
                    'message': f'Invalid time range: start ({start_time}) >= end ({end_time})'
                })
        
        return check_result
    
    def _check_message_counts(self, result: AnalysisResult) -> Dict[str, Any]:
        """Check message count consistency"""
        check_result = {
            'name': 'Message Counts',
            'description': 'Verify message counts are reasonable',
            'passed': True,
            'message': 'Message counts appear normal'
        }
        
        total_messages = sum(result.bag_info.message_counts.values())
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
        
        return check_result
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self.analyzer, 'cleanup'):
            self.analyzer.cleanup() 