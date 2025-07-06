"""
Filter command core functionality tests
"""
import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch, call
from typer.testing import CliRunner
from roseApp.cli.filter import app


class TestFilterCommandBasics:
    """Test basic filter command functionality"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @pytest.fixture
    def mock_create_parser(self):
        with patch('roseApp.cli.filter.create_parser') as mock:
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Filtering completed in 1.23s"
            mock_parser.load_whitelist.return_value = ["/test_topic"]
            mock.return_value = mock_parser
            yield mock
    
    def test_filter_command_exists(self, runner):
        """Test that filter command exists and shows help"""
        result = runner.invoke(app, ["filter", "--help"])
        assert result.exit_code == 0
        assert "Filter topics from one or more ROS bag files" in result.output
    
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_single_file_processing(self, mock_exists, mock_isfile, runner, mock_create_parser):
        """Test processing a single bag file"""
        # Mock file existence
        mock_exists.return_value = True
        mock_isfile.return_value = True
        
        result = runner.invoke(app, [
            "filter",
            "input.bag",
            "output.bag", 
            "--topics", "/test_topic",
            "--compression", "none"
        ])
        
        assert result.exit_code == 0
        mock_create_parser.assert_called_once()
    
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.path.exists') 
    @patch('os.makedirs')
    def test_directory_processing(self, mock_makedirs, mock_exists, mock_isdir, mock_isfile, runner, mock_create_parser):
        """Test processing a directory of bag files"""
        # Mock directory structure
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        mock_exists.return_value = True
        
        result = runner.invoke(app, [
            "filter",
            "/input/dir",
            "/output/dir",
            "--topics", "/test_topic",
            "--compression", "none"
        ])
        
        assert result.exit_code == 0
        mock_makedirs.assert_called()
    
    def test_missing_input_file_error(self, runner, mock_create_parser):
        """Test error handling for missing input file"""
        result = runner.invoke(app, [
            "filter",
            "nonexistent.bag",
            "output.bag",
            "--topics", "/test_topic"
        ])
        
        assert result.exit_code == 1
        assert "does not exist" in result.output
    
    def test_invalid_compression_error(self, runner, mock_create_parser):
        """Test error handling for invalid compression type"""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.exists', return_value=True):
                result = runner.invoke(app, [
                    "filter",
                    "input.bag",
                    "output.bag",
                    "--topics", "/test_topic",
                    "--compression", "invalid"
                ])
        
        assert result.exit_code == 1
        assert "Invalid compression type" in result.output


class TestFilterCommandParameters:
    """Test filter command parameter handling"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_topics_parameter(self, runner):
        """Test --topics parameter"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Complete"
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--topics", "/topic1",
                "--topics", "/topic2"
            ])
            
            assert result.exit_code == 0
    
    def test_whitelist_parameter(self, runner, temp_dir):
        """Test --whitelist parameter"""
        # Create test whitelist file
        whitelist_path = os.path.join(temp_dir, "test.txt")
        with open(whitelist_path, 'w') as f:
            f.write("/test_topic\n")
        
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Complete"
            mock_parser.load_whitelist.return_value = ["/test_topic"]
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--whitelist", whitelist_path
            ])
            
            assert result.exit_code == 0
            mock_parser.load_whitelist.assert_called_with(whitelist_path)
    
    def test_compression_parameter(self, runner):
        """Test --compression parameter with different values"""
        compression_types = ["none", "bz2", "lz4"]
        
        for compression in compression_types:
            with patch('os.path.isfile', return_value=True), \
                 patch('os.path.exists', return_value=True), \
                 patch('roseApp.cli.filter.create_parser') as mock_create_parser:
                
                mock_parser = MagicMock()
                mock_parser.filter_bag.return_value = "Complete"
                mock_create_parser.return_value = mock_parser
                
                result = runner.invoke(app, [
                    "filter",
                    "input.bag",
                    "output.bag", 
                    "--topics", "/test_topic",
                    "--compression", compression
                ])
                
                assert result.exit_code == 0
    
    def test_parallel_parameter(self, runner):
        """Test --parallel parameter"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "/input/dir",
                "/output/dir",
                "--topics", "/test_topic",
                "--parallel"
            ])
            
            assert result.exit_code == 0
    
    def test_workers_parameter(self, runner):
        """Test --workers parameter"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock() 
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "/input/dir",
                "/output/dir",
                "--topics", "/test_topic",
                "--workers", "4"
            ])
            
            assert result.exit_code == 0
    
    def test_dry_run_parameter(self, runner):
        """Test --dry-run parameter"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--topics", "/test_topic",
                "--dry-run"
            ])
            
            assert result.exit_code == 0
            # In dry run mode, filter_bag should not be called
            mock_parser.filter_bag.assert_not_called()


class TestFilterCommandOutputHandling:
    """Test output path handling logic"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_output_file_specified(self, runner):
        """Test when output file is explicitly specified"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs') as mock_makedirs, \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Complete"
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "specific_output.bag",
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 0
    
    def test_output_directory_specified(self, runner):
        """Test when output directory is specified"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.isdir', return_value=False), \
             patch('os.makedirs') as mock_makedirs, \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Complete" 
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "/output/dir",
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 0
            mock_makedirs.assert_called()
    
    def test_output_dir_required_for_directory_input(self, runner):
        """Test that output directory is required when input is directory"""
        with patch('os.path.isfile', return_value=False), \
             patch('os.path.isdir', return_value=True), \
             patch('os.path.exists', return_value=True):
            
            # Missing output directory should cause error
            result = runner.invoke(app, [
                "filter", 
                "/input/dir",
                # No output directory specified
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 1
            assert "Output directory is required" in result.output


class TestFilterCommandErrorHandling:
    """Test error handling in filter command"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_non_bag_file_error(self, runner):
        """Test error when input file is not a bag file"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True):
            
            result = runner.invoke(app, [
                "filter",
                "input.txt",  # Not a .bag file
                "output.bag",
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 1
            assert "not a bag file" in result.output
    
    def test_output_file_conflict_error(self, runner):
        """Test error when output path conflicts with existing file"""
        with patch('os.path.isfile') as mock_isfile, \
             patch('os.path.exists', return_value=True):
            
            # First call: input is file, second call: output is existing file
            mock_isfile.side_effect = [True, True]
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "existing_file",  # This exists and is not .bag
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 1
            assert "existing file" in result.output
    
    def test_parser_error_handling(self, runner):
        """Test handling of parser errors"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.side_effect = Exception("Parser error")
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--topics", "/test_topic"
            ])
            
            assert result.exit_code == 1
            assert "Error:" in result.output
