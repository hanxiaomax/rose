#!/usr/bin/env python3
"""
ROS Bag File Validator

This module provides comprehensive validation for ROS bag files to ensure they are
properly formatted, readable, and contain valid data after extraction or conversion.
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .parser import create_best_parser, IBagParser
from .util import get_logger

_logger = get_logger(__name__)


class ValidationLevel(Enum):
    """Validation levels for bag files"""
    BASIC = "basic"          # File exists, can be opened
    STRUCTURAL = "structural"  # Valid bag structure, readable headers
    CONTENT = "content"      # Message content validation
    COMPREHENSIVE = "comprehensive"  # Full validation including data integrity


@dataclass
class ValidationResult:
    """Result of bag file validation"""
    file_path: Path
    validation_level: ValidationLevel
    is_valid: bool
    validation_time: float
    file_size_bytes: int
    
    # Basic validation results
    file_exists: bool = True
    file_readable: bool = True
    
    # Structural validation results
    valid_format: bool = True
    topics_count: int = 0
    total_messages: int = 0
    duration_seconds: float = 0.0
    connections_valid: bool = True
    
    # Content validation results
    message_types_valid: bool = True
    timestamps_valid: bool = True
    no_corruption: bool = True
    
    # Detailed information
    topics: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class BagValidator:
    """Comprehensive ROS bag file validator"""
    
    def __init__(self, parser: Optional[IBagParser] = None):
        """Initialize bag validator
        
        Args:
            parser: Optional parser instance. If None, will auto-select the best parser
        """
        self.parser = parser or create_best_parser()
        self.logger = get_logger(__name__)
    
    def validate_bag(self, bag_path: Path, 
                    validation_level: ValidationLevel = ValidationLevel.STRUCTURAL) -> ValidationResult:
        """
        Validate a ROS bag file
        
        Args:
            bag_path: Path to the bag file to validate
            validation_level: Level of validation to perform
            
        Returns:
            ValidationResult with detailed validation information
        """
        start_time = time.time()
        
        # Initialize result
        result = ValidationResult(
            file_path=bag_path,
            validation_level=validation_level,
            is_valid=True,
            validation_time=0.0,
            file_size_bytes=0
        )
        
        try:
            # Basic validation
            self._validate_basic(bag_path, result)
            
            if not result.is_valid or validation_level == ValidationLevel.BASIC:
                result.validation_time = time.time() - start_time
                return result
            
            # Structural validation
            if validation_level.value in ['structural', 'content', 'comprehensive']:
                self._validate_structural(bag_path, result)
            
            if not result.is_valid or validation_level == ValidationLevel.STRUCTURAL:
                result.validation_time = time.time() - start_time
                return result
            
            # Content validation
            if validation_level.value in ['content', 'comprehensive']:
                self._validate_content(bag_path, result)
            
            if not result.is_valid or validation_level == ValidationLevel.CONTENT:
                result.validation_time = time.time() - start_time
                return result
            
            # Comprehensive validation
            if validation_level == ValidationLevel.COMPREHENSIVE:
                self._validate_comprehensive(bag_path, result)
        
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Validation error: {str(e)}")
            self.logger.error(f"Validation failed for {bag_path}: {e}")
        
        result.validation_time = time.time() - start_time
        return result
    
    def _validate_basic(self, bag_path: Path, result: ValidationResult):
        """Perform basic file validation"""
        # Check if file exists
        if not bag_path.exists():
            result.file_exists = False
            result.is_valid = False
            result.errors.append(f"File does not exist: {bag_path}")
            return
        
        # Check file size
        try:
            result.file_size_bytes = bag_path.stat().st_size
            if result.file_size_bytes == 0:
                result.is_valid = False
                result.errors.append("File is empty")
                return
        except OSError as e:
            result.file_readable = False
            result.is_valid = False
            result.errors.append(f"Cannot access file: {e}")
            return
        
        # Check if file is readable
        try:
            with open(bag_path, 'rb') as f:
                # Try to read first few bytes
                header = f.read(1024)
                if not header:
                    result.file_readable = False
                    result.is_valid = False
                    result.errors.append("File is not readable")
                    return
        except (OSError, PermissionError) as e:
            result.file_readable = False
            result.is_valid = False
            result.errors.append(f"File read error: {e}")
    
    def _validate_structural(self, bag_path: Path, result: ValidationResult):
        """Perform structural validation"""
        try:
            # Try to load bag with parser
            topics, connections, time_range = self.parser.load_bag(str(bag_path))
            
            # Validate basic structure
            if not topics:
                result.warnings.append("No topics found in bag")
            else:
                result.topics_count = len(topics)
            
            if not connections:
                result.connections_valid = False
                result.warnings.append("No connections found in bag")
            
            # Get message counts
            try:
                message_counts = self.parser.get_message_counts(str(bag_path))
                result.total_messages = sum(message_counts.values())
                
                # Build topic information
                for topic in topics:
                    topic_info = {
                        'name': topic,
                        'message_type': connections.get(topic, 'Unknown'),
                        'message_count': message_counts.get(topic, 0)
                    }
                    result.topics.append(topic_info)
            
            except Exception as e:
                result.warnings.append(f"Could not get message counts: {e}")
            
            # Validate time range
            if time_range and len(time_range) >= 2:
                try:
                    start_time, end_time = time_range
                    if isinstance(start_time, tuple) and isinstance(end_time, tuple):
                        start_seconds = start_time[0] + start_time[1] / 1e9
                        end_seconds = end_time[0] + end_time[1] / 1e9
                        result.duration_seconds = end_seconds - start_seconds
                        
                        if result.duration_seconds < 0:
                            result.timestamps_valid = False
                            result.errors.append("Invalid time range: negative duration")
                            result.is_valid = False
                    else:
                        result.warnings.append("Unusual time range format")
                except Exception as e:
                    result.warnings.append(f"Could not validate time range: {e}")
            
        except Exception as e:
            result.valid_format = False
            result.is_valid = False
            result.errors.append(f"Structural validation failed: {e}")
    
    def _validate_content(self, bag_path: Path, result: ValidationResult):
        """Perform content validation"""
        try:
            # Sample some messages to check for corruption
            sample_count = min(100, result.total_messages // 10) if result.total_messages > 0 else 10
            sampled_messages = 0
            corrupted_messages = 0
            
            # Get first few topics for sampling
            topics_to_sample = [topic['name'] for topic in result.topics[:3]]
            
            if topics_to_sample:
                try:
                    for timestamp, message in self.parser.read_messages(str(bag_path), topics_to_sample):
                        sampled_messages += 1
                        
                        # Basic message validation
                        if message is None:
                            corrupted_messages += 1
                        
                        # Stop after sampling enough messages
                        if sampled_messages >= sample_count:
                            break
                
                except Exception as e:
                    result.warnings.append(f"Message sampling error: {e}")
                    corrupted_messages += 1
                
                # Check corruption rate
                if sampled_messages > 0:
                    corruption_rate = corrupted_messages / sampled_messages
                    if corruption_rate > 0.1:  # More than 10% corrupted
                        result.no_corruption = False
                        result.is_valid = False
                        result.errors.append(f"High message corruption rate: {corruption_rate:.1%}")
                    elif corruption_rate > 0:
                        result.warnings.append(f"Some corrupted messages found: {corruption_rate:.1%}")
        
        except Exception as e:
            result.warnings.append(f"Content validation error: {e}")
    
    def _validate_comprehensive(self, bag_path: Path, result: ValidationResult):
        """Perform comprehensive validation"""
        try:
            # Additional checks for comprehensive validation
            
            # Check for duplicate timestamps or out-of-order messages
            if result.topics:
                try:
                    first_topic = result.topics[0]['name']
                    prev_timestamp = None
                    out_of_order_count = 0
                    checked_messages = 0
                    
                    for timestamp, message in self.parser.read_messages(str(bag_path), [first_topic]):
                        if prev_timestamp is not None:
                            if timestamp < prev_timestamp:
                                out_of_order_count += 1
                        
                        prev_timestamp = timestamp
                        checked_messages += 1
                        
                        # Limit check to avoid performance issues
                        if checked_messages >= 1000:
                            break
                    
                    if out_of_order_count > 0:
                        if out_of_order_count / checked_messages > 0.05:  # More than 5%
                            result.timestamps_valid = False
                            result.errors.append(f"Significant timestamp ordering issues: {out_of_order_count}/{checked_messages}")
                        else:
                            result.warnings.append(f"Minor timestamp ordering issues: {out_of_order_count}/{checked_messages}")
                
                except Exception as e:
                    result.warnings.append(f"Timestamp validation error: {e}")
            
            # Validate file integrity by checking if we can read all connections
            try:
                all_topics = [topic['name'] for topic in result.topics]
                if all_topics:
                    # Try to read first message from each topic
                    for topic_info in result.topics:
                        topic_name = topic_info['name']
                        try:
                            for timestamp, message in self.parser.read_messages(str(bag_path), [topic_name]):
                                # Just check that we can read the first message
                                break
                        except Exception as e:
                            result.warnings.append(f"Could not read messages from topic {topic_name}: {e}")
            
            except Exception as e:
                result.warnings.append(f"Topic integrity check error: {e}")
        
        except Exception as e:
            result.warnings.append(f"Comprehensive validation error: {e}")
    
    def validate_extracted_bag(self, original_bag: Path, extracted_bag: Path, 
                             expected_topics: List[str]) -> ValidationResult:
        """
        Validate an extracted bag against its original
        
        Args:
            original_bag: Path to the original bag file
            extracted_bag: Path to the extracted bag file
            expected_topics: List of topics that should be in the extracted bag
            
        Returns:
            ValidationResult with comparison information
        """
        # Validate the extracted bag
        result = self.validate_bag(extracted_bag, ValidationLevel.STRUCTURAL)
        
        if not result.is_valid:
            return result
        
        try:
            # Additional checks specific to extracted bags
            extracted_topics = [topic['name'] for topic in result.topics]
            
            # Check if all expected topics are present
            missing_topics = set(expected_topics) - set(extracted_topics)
            if missing_topics:
                result.warnings.append(f"Missing expected topics: {list(missing_topics)}")
            
            # Check for unexpected topics
            unexpected_topics = set(extracted_topics) - set(expected_topics)
            if unexpected_topics:
                result.warnings.append(f"Unexpected topics found: {list(unexpected_topics)}")
            
            # Compare message counts if possible
            try:
                original_counts = self.parser.get_message_counts(str(original_bag))
                extracted_counts = self.parser.get_message_counts(str(extracted_bag))
                
                for topic in expected_topics:
                    original_count = original_counts.get(topic, 0)
                    extracted_count = extracted_counts.get(topic, 0)
                    
                    if extracted_count > original_count:
                        result.warnings.append(f"Topic {topic}: extracted has more messages than original ({extracted_count} > {original_count})")
                    elif extracted_count < original_count * 0.95:  # Allow 5% tolerance
                        result.warnings.append(f"Topic {topic}: significant message count difference ({extracted_count} vs {original_count})")
            
            except Exception as e:
                result.warnings.append(f"Could not compare message counts: {e}")
        
        except Exception as e:
            result.warnings.append(f"Extraction validation error: {e}")
        
        return result 