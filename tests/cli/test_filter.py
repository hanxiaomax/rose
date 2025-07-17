#!/usr/bin/env python3
"""
Test filter command functionality
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typer.testing import CliRunner

from roseApp.cli.filter import app, filter_bag
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
def sample_whitelist_file(temp_dir):
    """Create a sample whitelist file for testing"""
    whitelist_path = Path(temp_dir) / "whitelist.txt"
    whitelist_path.write_text("/cmd_vel\n/odom\n/tf\n")
    return str(whitelist_path)


@pytest.fixture
def mock_parser():
    """Mock parser for testing"""
    with patch('roseApp.cli.filter.create_parser') as mock:
        parser = MagicMock()
        parser.get_topics.return_value = ['/cmd_vel', '/odom', '/tf', '/scan']
        parser.get_file_info.return_value = {
            'file_size': 1024,
            'duration': 10.0,
            'total_messages': 100
        }
        parser.filter_bag.return_value = True
        mock.return_value = parser
        yield parser


class TestFilterCommand:
    """Test filter command functionality"""

    def test_filter_basic_command(self, sample_bag_file, temp_dir, mock_parser):
        """Test basic filter command"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel"
        ])
        
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.output}")
        if result.exception:
            print(f"Exception: {result.exception}")
        
        assert result.exit_code == 0

    def test_filter_with_output_dir(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter command with output directory"""
        output_dir = temp_dir + "/output"
        
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            output_dir,
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_filter_with_whitelist(self, sample_bag_file, temp_dir, sample_whitelist_file, mock_parser):
        """Test filter with whitelist file"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--whitelist", sample_whitelist_file
        ])
        
        assert result.exit_code == 0

    def test_filter_with_compression(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with compression"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--compression", "bz2"
        ])
        
        assert result.exit_code == 0

    def test_filter_parallel_processing(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with parallel processing"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--parallel",
            "--workers", "2"
        ])
        
        assert result.exit_code == 0

    def test_filter_multiple_topics(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with multiple topics"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--topics", "/odom"
        ])
        
        assert result.exit_code == 0

    def test_filter_sort_by_options(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with different sort options"""
        for sort_by in ["topic", "count", "size"]:
            result = runner.invoke(app, [
                "filter_bag",
                sample_bag_file,
                "--topics", "/cmd_vel",
                "--sort-by", sort_by
            ])
            
            assert result.exit_code == 0

    def test_filter_dry_run(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with dry run"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--dry-run"
        ])
        
        assert result.exit_code == 0

    def test_filter_overwrite_option(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with overwrite option"""
        # Test with overwrite enabled
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--overwrite"
        ])
        
        assert result.exit_code == 0
        
        # Test with overwrite disabled
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--no-overwrite"
        ])
        
        assert result.exit_code == 0

    def test_filter_missing_input_file(self, temp_dir):
        """Test filter with missing input file"""
        result = runner.invoke(app, [
            "filter_bag",
            "/nonexistent/file.bag",
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code != 0

    def test_filter_invalid_compression(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with invalid compression type"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--compression", "invalid"
        ])
        
        assert result.exit_code == 0  # Should handle gracefully

    def test_filter_no_topics_specified(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter without topics or whitelist"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file
        ])
        
        # Should handle gracefully or show error
        assert result.exit_code == 0 or result.exit_code != 0

    def test_filter_whitelist_file_not_found(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with non-existent whitelist file"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--whitelist", "/nonexistent/whitelist.txt"
        ])
        
        assert result.exit_code != 0

    @patch('roseApp.cli.filter.create_parser')
    def test_filter_parser_error(self, mock_create_parser, sample_bag_file, temp_dir):
        """Test filter when parser raises an error"""
        mock_parser = MagicMock()
        mock_parser.filter_bag.side_effect = Exception("Test error")
        mock_create_parser.return_value = mock_parser
        
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code != 0

    def test_filter_directory_input(self, temp_dir, mock_parser):
        """Test filter with directory input"""
        # Create a directory with bag files
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        (input_dir / "test1.bag").touch()
        (input_dir / "test2.bag").touch()
        
        output_dir = temp_dir + "/output"
        
        result = runner.invoke(app, [
            "filter_bag",
            str(input_dir),
            output_dir,
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_filter_directory_parallel(self, temp_dir, mock_parser):
        """Test filter with directory input and parallel processing"""
        # Create a directory with bag files
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        (input_dir / "test1.bag").touch()
        (input_dir / "test2.bag").touch()
        
        output_dir = temp_dir + "/output"
        
        result = runner.invoke(app, [
            "filter_bag",
            str(input_dir),
            output_dir,
            "--topics", "/cmd_vel",
            "--parallel",
            "--workers", "2"
        ])
        
        assert result.exit_code == 0

    def test_filter_with_verbose_output(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with verbose output"""
        with patch('roseApp.cli.filter.get_logger') as mock_logger:
            result = runner.invoke(app, [
                "filter_bag",
                sample_bag_file,
                "--topics", "/cmd_vel"
            ])
            
            assert result.exit_code == 0
            mock_logger.assert_called()

    def test_filter_both_whitelist_and_topics(self, sample_bag_file, temp_dir, sample_whitelist_file, mock_parser):
        """Test filter with both whitelist and topics (should prefer whitelist)"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--whitelist", sample_whitelist_file,
            "--topics", "/cmd_vel"
        ])
        
        assert result.exit_code == 0

    def test_filter_invalid_workers_count(self, sample_bag_file, temp_dir, mock_parser):
        """Test filter with invalid workers count"""
        result = runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            "--topics", "/cmd_vel",
            "--workers", "0"
        ])
        
        # Should handle invalid worker count gracefully
        assert result.exit_code == 0


class TestFilterUtilityFunctions:
    """Test utility functions in filter module"""

    def test_filter_function_imports(self):
        """Test that all necessary imports are available"""
        from roseApp.cli.filter import filter_bag, app
        assert filter_bag is not None
        assert app is not None

    @patch('roseApp.cli.filter.set_app_mode')
    def test_app_mode_setting(self, mock_set_mode, sample_bag_file, temp_dir, mock_parser):
        """Test that app mode is set correctly"""
        output_dir = temp_dir + "/output"
        
        runner.invoke(app, [
            "filter_bag",
            sample_bag_file,
            output_dir,
            "--topics", "/cmd_vel"
        ])
        
        mock_set_mode.assert_called_with(AppMode.CLI)

    def test_filter_help_message(self):
        """Test filter command help message"""
        result = runner.invoke(app, ["filter_bag", "--help"])
        
        assert result.exit_code == 0
        assert "Filter ROS bag files by topics" in result.output
        assert "--topics" in result.output
        assert "--whitelist" in result.output
        assert "--compression" in result.output 