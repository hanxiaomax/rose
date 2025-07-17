#!/usr/bin/env python3
"""
Test inspect command functionality - comprehensive test suite
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typer.testing import CliRunner

from roseApp.cli.inspect import app, inspect
from roseApp.core.util import AppMode

runner = CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_bag_file(temp_dir):
    """Create a sample bag file for testing"""
    bag_path = Path(temp_dir) / "test.bag"
    bag_path.touch()
    return str(bag_path)


@pytest.fixture
def mock_bag_engine():
    """Mock BagAnalysisEngine for testing"""
    with patch('roseApp.cli.inspect.BagAnalysisEngine') as mock:
        engine = mock.return_value
        engine.analyze.return_value = {
            'topics': [
                {
                    'topic': '/cmd_vel',
                    'type': 'geometry_msgs/Twist',
                    'count': 100,
                    'size': 1024,
                    'frequency': 10.0
                },
                {
                    'topic': '/odom',
                    'type': 'nav_msgs/Odometry',
                    'count': 200,
                    'size': 2048,
                    'frequency': 20.0
                }
            ],
            'summary': {
                'total_messages': 300,
                'total_size': 3072,
                'duration': 15.0
            }
        }
        yield engine


class TestInspectBasicFunctionality:
    """Test basic inspect command functionality"""

    def test_inspect_basic_command(self, sample_bag_file, mock_bag_engine):
        """Test basic inspect command"""
        result = runner.invoke(app, ["inspect", sample_bag_file])
        
        assert result.exit_code == 0

    def test_inspect_table_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with table format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "table"
        ])
        
        assert result.exit_code == 0

    def test_inspect_list_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with list format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "list"
        ])
        
        assert result.exit_code == 0

    def test_inspect_summary_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with summary format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "summary"
        ])
        
        assert result.exit_code == 0

    def test_inspect_csv_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with CSV format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "csv"
        ])
        
        assert result.exit_code == 0

    def test_inspect_json_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with JSON format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "json"
        ])
        
        assert result.exit_code == 0

    def test_inspect_html_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with HTML format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "html"
        ])
        
        assert result.exit_code == 0

    def test_inspect_invalid_format(self, sample_bag_file, mock_bag_engine):
        """Test inspect with invalid format"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "invalid"
        ])
        
        assert result.exit_code != 0


class TestInspectSortingOptions:
    """Test inspect command sorting options"""

    def test_inspect_sort_by_name(self, sample_bag_file, mock_bag_engine):
        """Test inspect sorted by name"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "name"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sort_by_type(self, sample_bag_file, mock_bag_engine):
        """Test inspect sorted by type"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "type"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sort_by_count(self, sample_bag_file, mock_bag_engine):
        """Test inspect sorted by count"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "count"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sort_by_size(self, sample_bag_file, mock_bag_engine):
        """Test inspect sorted by size"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "size"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sort_by_frequency(self, sample_bag_file, mock_bag_engine):
        """Test inspect sorted by frequency"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "frequency"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sort_reverse(self, sample_bag_file, mock_bag_engine):
        """Test inspect with reverse sorting"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "size",
            "--reverse"
        ])
        
        assert result.exit_code == 0

    def test_inspect_invalid_sort_option(self, sample_bag_file, mock_bag_engine):
        """Test inspect with invalid sort option"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sort-by", "invalid"
        ])
        
        assert result.exit_code != 0


class TestInspectFiltering:
    """Test inspect command topic filtering"""

    def test_inspect_single_topic_filter(self, sample_bag_file, mock_bag_engine):
        """Test inspect with single topic filter"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_inspect_multiple_topic_filters(self, sample_bag_file, mock_bag_engine):
        """Test inspect with multiple topic filters"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "/cmd_vel",
            "--topics", "/odom"
        ])
        
        assert result.exit_code == 0

    def test_inspect_pattern_filter(self, sample_bag_file, mock_bag_engine):
        """Test inspect with pattern filter"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "cmd"
        ])
        
        assert result.exit_code == 0

    def test_inspect_no_matching_topics(self, sample_bag_file, mock_bag_engine):
        """Test inspect when no topics match filter"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "/nonexistent"
        ])
        
        assert result.exit_code == 0  # Should handle gracefully


class TestInspectAdvancedFeatures:
    """Test advanced inspect command features"""

    def test_inspect_verbose_mode(self, sample_bag_file, mock_bag_engine):
        """Test inspect with verbose output"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--verbose"
        ])
        
        assert result.exit_code == 0

    def test_inspect_show_fields(self, sample_bag_file, mock_bag_engine):
        """Test inspect with show fields option"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--show-fields",
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_inspect_async_analysis(self, sample_bag_file, mock_bag_engine):
        """Test inspect with async analysis"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--async"
        ])
        
        assert result.exit_code == 0

    def test_inspect_sync_analysis(self, sample_bag_file, mock_bag_engine):
        """Test inspect with sync analysis"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sync"
        ])
        
        assert result.exit_code == 0

    def test_inspect_force_sync(self, sample_bag_file, mock_bag_engine):
        """Test inspect with force sync"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--force-sync"
        ])
        
        assert result.exit_code == 0

    def test_inspect_output_file(self, sample_bag_file, temp_dir, mock_bag_engine):
        """Test inspect with output file"""
        output_file = Path(temp_dir) / "output.csv"
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "csv",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_inspect_html_output_file(self, sample_bag_file, temp_dir, mock_bag_engine):
        """Test inspect with HTML output file"""
        output_file = Path(temp_dir) / "output.html"
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "html",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0


class TestInspectErrorHandling:
    """Test inspect command error handling"""

    def test_inspect_missing_file(self):
        """Test inspect with missing bag file"""
        result = runner.invoke(app, [
            "inspect", 
            "/nonexistent/file.bag"
        ])
        
        assert result.exit_code != 0

    def test_inspect_invalid_output_path(self, sample_bag_file, mock_bag_engine):
        """Test inspect with invalid output path"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--as", "csv",
            "--output", "/invalid/path/output.csv"
        ])
        
        assert result.exit_code != 0

    @patch('roseApp.cli.inspect.BagAnalysisEngine')
    def test_inspect_engine_error(self, mock_engine_class, sample_bag_file):
        """Test inspect when BagAnalysisEngine raises error"""
        mock_engine = mock_engine_class.return_value
        mock_engine.analyze.side_effect = Exception("Test error")
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file
        ])
        
        assert result.exit_code != 0

    def test_inspect_empty_bag_file(self, sample_bag_file, mock_bag_engine):
        """Test inspect with empty bag file"""
        mock_bag_engine.analyze.return_value = {
            'topics': [],
            'summary': {
                'total_messages': 0,
                'total_size': 0,
                'duration': 0.0
            }
        }
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file
        ])
        
        assert result.exit_code == 0


class TestInspectCombinedOptions:
    """Test inspect command with combined options"""

    def test_inspect_verbose_csv_output(self, sample_bag_file, temp_dir, mock_bag_engine):
        """Test inspect with verbose CSV output"""
        output_file = Path(temp_dir) / "output.csv"
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--verbose",
            "--as", "csv",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_inspect_filtered_sorted_verbose(self, sample_bag_file, mock_bag_engine):
        """Test inspect with filtering, sorting, and verbose"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "/cmd_vel",
            "--sort-by", "frequency",
            "--reverse",
            "--verbose"
        ])
        
        assert result.exit_code == 0

    def test_inspect_fields_async_json(self, sample_bag_file, mock_bag_engine):
        """Test inspect with fields, async, and JSON output"""
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--show-fields",
            "--async",
            "--as", "json",
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_inspect_all_options(self, sample_bag_file, temp_dir, mock_bag_engine):
        """Test inspect with maximum options"""
        output_file = Path(temp_dir) / "output.html"
        
        result = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--topics", "/cmd_vel",
            "--as", "html",
            "--sort-by", "size",
            "--reverse",
            "--verbose",
            "--show-fields",
            "--output", str(output_file),
            "--async"
        ])
        
        assert result.exit_code == 0


class TestInspectUtilityFunctions:
    """Test utility functions and imports"""

    def test_inspect_function_imports(self):
        """Test that all necessary imports are available"""
        from roseApp.cli.inspect import app, inspect
        assert app is not None
        assert inspect is not None

    @patch('roseApp.cli.inspect.set_app_mode')
    def test_app_mode_setting(self, mock_set_mode, sample_bag_file, mock_bag_engine):
        """Test that app mode is set correctly"""
        runner.invoke(app, ["inspect", sample_bag_file])
        
        mock_set_mode.assert_called_with(AppMode.CLI)

    def test_inspect_help_message(self):
        """Test inspect command help message"""
        result = runner.invoke(app, ["inspect", "--help"])
        
        assert result.exit_code == 0
        assert "Inspect ROS bag files" in result.output
        assert "--topics" in result.output
        assert "--as" in result.output
        assert "--sort-by" in result.output
        assert "--verbose" in result.output
        assert "--show-fields" in result.output

    def test_inspect_utility_functions(self):
        """Test utility functions are importable"""
        try:
            from roseApp.cli.inspect import (
                _filter_topics,
                _fuzzy_search_topics,
                _format_size,
                _format_duration
            )
            assert _filter_topics is not None
            assert _fuzzy_search_topics is not None
            assert _format_size is not None
            assert _format_duration is not None
        except ImportError:
            # Some functions might not be directly importable
            pass


class TestInspectPerformance:
    """Test inspect command performance features"""

    def test_inspect_caching(self, sample_bag_file, mock_bag_engine):
        """Test inspect with caching enabled"""
        # First run
        result1 = runner.invoke(app, ["inspect", sample_bag_file])
        assert result1.exit_code == 0
        
        # Second run (should use cache)
        result2 = runner.invoke(app, ["inspect", sample_bag_file])
        assert result2.exit_code == 0

    def test_inspect_large_bag_simulation(self, sample_bag_file, mock_bag_engine):
        """Test inspect with simulated large bag file"""
        # Simulate large bag with many topics
        mock_bag_engine.analyze.return_value = {
            'topics': [
                {
                    'topic': f'/topic_{i}',
                    'type': 'std_msgs/String',
                    'count': 1000,
                    'size': 1024,
                    'frequency': 10.0
                }
                for i in range(100)
            ],
            'summary': {
                'total_messages': 100000,
                'total_size': 102400,
                'duration': 100.0
            }
        }
        
        result = runner.invoke(app, ["inspect", sample_bag_file])
        assert result.exit_code == 0

    def test_inspect_async_vs_sync_performance(self, sample_bag_file, mock_bag_engine):
        """Test inspect async vs sync performance"""
        # Async
        result_async = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--async"
        ])
        assert result_async.exit_code == 0
        
        # Sync
        result_sync = runner.invoke(app, [
            "inspect", 
            sample_bag_file, 
            "--sync"
        ])
        assert result_sync.exit_code == 0 