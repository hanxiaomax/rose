"""
CLI parameter validation and handling tests
"""
import pytest
import os
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from roseApp.cli.filter import app


class TestParameterValidation:
    """Test CLI parameter validation"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_required_input_parameter(self, runner):
        """Test that input parameter is required"""
        result = runner.invoke(app, ["filter"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output
    
    def test_input_path_validation(self, runner):
        """Test input path validation"""
        # Test non-existent input
        result = runner.invoke(app, [
            "filter",
            "nonexistent.bag",
            "output.bag",
            "--topics", "/test"
        ])
        assert result.exit_code == 1
        assert "does not exist" in result.output
    
    def test_bag_file_extension_validation(self, runner):
        """Test bag file extension validation"""
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True):
            
            result = runner.invoke(app, [
                "filter",
                "input.txt",  # Wrong extension
                "output.bag",
                "--topics", "/test"
            ])
            
            assert result.exit_code == 1
            assert "not a bag file" in result.output
    
    def test_compression_type_validation(self, runner):
        """Test compression type validation"""
        valid_compressions = ["none", "bz2", "lz4"]
        invalid_compressions = ["gzip", "zip", "invalid", ""]
        
        # Test valid compressions
        for compression in valid_compressions:
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
                    "--topics", "/test",
                    "--compression", compression
                ])
                
                assert result.exit_code == 0, f"Valid compression {compression} should succeed"
        
        # Test invalid compressions
        for compression in invalid_compressions:
            with patch('os.path.isfile', return_value=True), \
                 patch('os.path.exists', return_value=True):
                
                result = runner.invoke(app, [
                    "filter",
                    "input.bag",
                    "output.bag",
                    "--topics", "/test",
                    "--compression", compression
                ])
                
                assert result.exit_code == 1, f"Invalid compression {compression} should fail"
                assert "Invalid compression type" in result.output
    
    def test_topics_parameter_multiple_values(self, runner):
        """Test multiple topics parameter"""
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
                "--topics", "/topic2", 
                "--topics", "/topic3"
            ])
            
            assert result.exit_code == 0
    
    def test_whitelist_file_validation(self, runner, temp_dir):
        """Test whitelist file validation"""
        # Test valid whitelist file
        valid_whitelist = os.path.join(temp_dir, "valid.txt")
        with open(valid_whitelist, 'w') as f:
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
                "--whitelist", valid_whitelist
            ])
            
            assert result.exit_code == 0
        
        # Test non-existent whitelist file
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.load_whitelist.side_effect = FileNotFoundError("Whitelist not found")
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--whitelist", "nonexistent.txt"
            ])
            
            assert result.exit_code == 1
    
    def test_workers_parameter_validation(self, runner):
        """Test workers parameter validation"""
        with patch('os.path.isdir', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_create_parser.return_value = mock_parser
            
            # Test valid worker count
            result = runner.invoke(app, [
                "filter",
                "/input/dir",
                "/output/dir",
                "--topics", "/test",
                "--workers", "4"
            ])
            
            assert result.exit_code == 0
            
            # Test invalid worker count (negative)
            result = runner.invoke(app, [
                "filter",
                "/input/dir", 
                "/output/dir",
                "--topics", "/test",
                "--workers", "-1"
            ])
            
            # Typer should handle this validation
            assert result.exit_code != 0


class TestParameterCombinations:
    """Test various parameter combinations"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_topics_and_whitelist_conflict(self, runner, temp_dir):
        """Test behavior when both topics and whitelist are specified"""
        whitelist_path = os.path.join(temp_dir, "test.txt")
        with open(whitelist_path, 'w') as f:
            f.write("/whitelist_topic\n")
        
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.filter_bag.return_value = "Complete"
            mock_parser.load_whitelist.return_value = ["/whitelist_topic"]
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "input.bag",
                "output.bag",
                "--topics", "/cmd_topic",
                "--whitelist", whitelist_path
            ])
            
            # Should succeed - implementation should handle this gracefully
            assert result.exit_code == 0
    
    def test_parallel_with_single_file(self, runner):
        """Test parallel flag with single file (should be ignored)"""
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
                "--topics", "/test",
                "--parallel"  # Should be ignored for single file
            ])
            
            assert result.exit_code == 0
    
    def test_workers_without_parallel(self, runner):
        """Test workers parameter without parallel flag"""
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
                "--topics", "/test",
                "--workers", "4"
                # No --parallel flag
            ])
            
            assert result.exit_code == 0
    
    def test_all_parameters_combined(self, runner, temp_dir):
        """Test all parameters used together"""
        whitelist_path = os.path.join(temp_dir, "test.txt")
        with open(whitelist_path, 'w') as f:
            f.write("/test_topic\n")
        
        with patch('os.path.isdir', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('roseApp.cli.filter.create_parser') as mock_create_parser:
            
            mock_parser = MagicMock()
            mock_parser.load_whitelist.return_value = ["/test_topic"]
            mock_create_parser.return_value = mock_parser
            
            result = runner.invoke(app, [
                "filter",
                "/input/dir",
                "/output/dir",
                "--whitelist", whitelist_path,
                "--compression", "lz4",
                "--parallel",
                "--workers", "4",
                "--dry-run"
            ])
            
            assert result.exit_code == 0


class TestParameterDefaults:
    """Test parameter default values"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_compression_default(self, runner):
        """Test that compression defaults to 'none'"""
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
                "--topics", "/test"
                # No compression specified
            ])
            
            assert result.exit_code == 0
    
    def test_parallel_default(self, runner):
        """Test that parallel defaults to False"""
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
                "--topics", "/test"
                # No parallel flag
            ])
            
            assert result.exit_code == 0
    
    def test_dry_run_default(self, runner):
        """Test that dry_run defaults to False"""
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
                "--topics", "/test"
                # No dry-run flag
            ])
            
            assert result.exit_code == 0
            # filter_bag should be called (not in dry-run mode)
            mock_parser.filter_bag.assert_called()


class TestParameterHelp:
    """Test parameter help and documentation"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_help_message_contains_all_parameters(self, runner):
        """Test that help message documents all parameters"""
        result = runner.invoke(app, ["filter", "--help"])
        assert result.exit_code == 0
        
        # Check that all parameters are documented
        expected_params = [
            "input_path", "output_dir", "whitelist", "topics", 
            "compression", "parallel", "workers", "dry-run"
        ]
        
        for param in expected_params:
            assert param in result.output or param.replace("_", "-") in result.output
    
    def test_parameter_descriptions(self, runner):
        """Test that parameters have meaningful descriptions"""
        result = runner.invoke(app, ["filter", "--help"])
        assert result.exit_code == 0
        
        # Check for key description words
        expected_descriptions = [
            "Topics to include", "Compression type", "parallel", 
            "workers", "dry run", "whitelist"
        ]
        
        for desc in expected_descriptions:
            assert desc.lower() in result.output.lower()
