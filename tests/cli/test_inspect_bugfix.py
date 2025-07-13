#!/usr/bin/env python3
"""
Test inspect command bug fixes - verification of data structure fixes
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from roseApp.cli.inspect import (
    _create_json_structure
)


class TestInspectBugFixes:
    """Test inspect command bug fixes"""

    def test_create_json_structure_handles_missing_analysis_time(self):
        """Test that _create_json_structure handles missing analysis_time field safely"""
        test_bag_info = {
            'topics': ['/test_topic'],
            'connections': {'/test_topic': 'std_msgs/String'},
            'stats': {'/test_topic': {'count': 100, 'size': 1024}},
            'file_size': 2048,
            'total_messages': 100,
            'total_data_size': 1024,
            'duration': 10.0,
            'start_time': (1234567890, 0),
            'end_time': (1234567900, 0),
            'topic_count': 1,
            'is_lite_mode': False
            # Note: no 'analysis_time' field
        }
        
        # Should not raise KeyError
        result = _create_json_structure("test.bag", test_bag_info, ['/test_topic'], False)
        
        assert 'summary' in result
        assert 'topics' in result
        assert result['summary']['analysis_time'] == 0.0  # Default value

    def test_create_json_structure_handles_missing_stats_safely(self):
        """Test that _create_json_structure handles missing stats field safely"""
        test_bag_info = {
            'topics': ['/test_topic'],
            'connections': {'/test_topic': 'std_msgs/String'},
            # 'stats': {},  # Missing stats field
            'file_size': 2048,
            'total_messages': None,
            'total_data_size': None,
            'duration': 10.0,
            'start_time': (1234567890, 0),
            'end_time': (1234567900, 0),
            'topic_count': 1,
            'is_lite_mode': True
        }
        
        # Should not raise KeyError
        result = _create_json_structure("test.bag", test_bag_info, ['/test_topic'], True)
        
        assert 'summary' in result
        assert 'topics' in result
        assert len(result['topics']) == 1
        
        # Verify topic with default stats
        topic_data = result['topics'][0]
        assert topic_data['topic'] == '/test_topic'
        assert topic_data['count'] == 0  # Default when stats missing
        assert topic_data['size'] == 0   # Default when stats missing

    def test_data_structure_consistency(self):
        """Test that the expected data structure is consistent"""
        # This test verifies the expected structure without complex mocking
        test_bag_info = {
            'topics': ['/topic1', '/topic2'],  # List of topic names
            'connections': {'/topic1': 'type1', '/topic2': 'type2'},  # Dict mapping topics to types
            'stats': {'/topic1': {'count': 10, 'size': 100}, '/topic2': {'count': 20, 'size': 200}},
            'file_size': 2048,
            'total_messages': 30,
            'total_data_size': 300,
            'duration': 10.0,
            'start_time': (1234567890, 0),
            'end_time': (1234567900, 0),
            'topic_count': 2,
            'is_lite_mode': False
        }
        
        result = _create_json_structure("test.bag", test_bag_info, ['/topic1', '/topic2'], False)
        
        # Verify structure
        assert 'summary' in result
        assert 'topics' in result
        assert 'metadata' in result
        
        # Verify summary
        summary = result['summary']
        assert summary['topic_count'] == 2
        assert summary['total_messages'] == 30
        assert summary['file_size'] == 2048
        
        # Verify topics
        topics = result['topics']
        assert len(topics) == 2
        assert topics[0]['topic'] == '/topic1'
        assert topics[0]['count'] == 10
        assert topics[1]['topic'] == '/topic2'
        assert topics[1]['count'] == 20

    def test_lite_mode_vs_full_mode_structure(self):
        """Test that lite mode and full mode return compatible structures"""
        # Lite mode data (minimal)
        lite_data = {
            'topics': ['/test_topic'],
            'connections': {'/test_topic': 'std_msgs/String'},
            'stats': {},  # Empty in lite mode
            'file_size': 1024,
            'total_messages': None,  # Unknown in lite mode
            'total_data_size': None,  # Unknown in lite mode
            'duration': 10.0,
            'start_time': (1234567890, 0),
            'end_time': (1234567900, 0),
            'topic_count': 1,
            'is_lite_mode': True
        }
        
        # Full mode data (complete)
        full_data = {
            'topics': ['/test_topic'],
            'connections': {'/test_topic': 'std_msgs/String'},
            'stats': {'/test_topic': {'count': 100, 'size': 1024}},
            'file_size': 1024,
            'total_messages': 100,
            'total_data_size': 1024,
            'duration': 10.0,
            'start_time': (1234567890, 0),
            'end_time': (1234567900, 0),
            'topic_count': 1,
            'is_lite_mode': False
        }
        
        # Both should work without errors
        lite_result = _create_json_structure("test.bag", lite_data, ['/test_topic'], True)
        full_result = _create_json_structure("test.bag", full_data, ['/test_topic'], False)
        
        # Both should have same structure
        assert 'summary' in lite_result and 'summary' in full_result
        assert 'topics' in lite_result and 'topics' in full_result
        
        # Lite mode should have default values
        assert lite_result['topics'][0]['count'] == 0  # Default from empty stats
        assert full_result['topics'][0]['count'] == 100  # Actual value


if __name__ == "__main__":
    pytest.main([__file__]) 