#!/usr/bin/env python3
"""
Test suite for friendly error handling in CLI commands
"""

import os
import tempfile
import pytest
from unittest.mock import patch, Mock
from typer.testing import CliRunner
from roseApp.cli.error_handling import FriendlyErrorHandler, CommandErrorHandlers
from roseApp.rose import app


class TestFriendlyErrorHandler:
    """Test the FriendlyErrorHandler class"""
    
    def test_file_not_found_error(self):
        """Test file not found error handling"""
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            FriendlyErrorHandler.file_not_found("nonexistent.bag", "bag file")
    
    def test_missing_required_option_error(self):
        """Test missing required option error handling"""
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            FriendlyErrorHandler.missing_required_option(
                "--series", "plot", ["--series /topic:field"]
            )
    
    def test_invalid_option_value_error(self):
        """Test invalid option value error handling"""
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            FriendlyErrorHandler.invalid_option_value(
                "--as", "invalid", ["table", "list"], "inspect"
            )
    
    def test_dependency_missing_error(self):
        """Test missing dependency error handling"""
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            FriendlyErrorHandler.dependency_missing(
                "matplotlib", "pip install matplotlib", "plotting"
            )
    
    def test_find_similar_files(self):
        """Test similar file finding functionality"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_files = ["demo.bag", "test.bag", "sample.bag"]
            for filename in test_files:
                with open(os.path.join(tmpdir, filename), 'w') as f:
                    f.write("test")
            
            # Test finding similar files
            similar = FriendlyErrorHandler._find_similar_files(
                os.path.join(tmpdir, "demo_missing.bag")
            )
            assert len(similar) > 0
            assert any("demo.bag" in f for f in similar)
    
    def test_find_closest_match(self):
        """Test closest match finding"""
        valid_options = ["table", "list", "summary", "csv", "html"]
        
        # Test exact prefix match
        match = FriendlyErrorHandler._find_closest_match("tab", valid_options)
        assert match == "table"
        
        # Test partial match
        match = FriendlyErrorHandler._find_closest_match("summ", valid_options)
        assert match == "summary"
        
        # Test no match
        match = FriendlyErrorHandler._find_closest_match("xyz", valid_options)
        assert match is None


class TestCommandErrorHandlers:
    """Test command-specific error handlers"""
    
    def test_inspect_command_errors(self):
        """Test inspect command error validation"""
        # Test file not found
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.inspect_command_errors(
                "nonexistent.bag", "table", "size", None
            )
        
        # Test invalid format
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.inspect_command_errors(
                "tests/demo.bag", "invalid", "size", None
            )
    
    def test_plot_command_errors(self):
        """Test plot command error validation"""
        # Test missing series
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.plot_command_errors(
                "tests/demo.bag", [], "output.png", "line", "png"
            )
        
        # Test invalid series format
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.plot_command_errors(
                "tests/demo.bag", ["invalid_format"], "output.png", "line", "png"
            )
        
        # Test topic without slash
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.plot_command_errors(
                "tests/demo.bag", ["topic:field"], "output.png", "line", "png"
            )
    
    def test_filter_command_errors(self):
        """Test filter command error validation"""
        # Test invalid compression
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.filter_command_errors(
                "tests/demo.bag", "output/", None, None, "invalid", "size"
            )
        
        # Test invalid sort option
        with pytest.raises(Exception):  # typer.Exit is a subclass of Exception
            CommandErrorHandlers.filter_command_errors(
                "tests/demo.bag", "output/", None, None, "none", "invalid"
            )


class TestCLIIntegration:
    """Test CLI integration with friendly error handling"""
    
    def setup_method(self):
        """Setup test runner"""
        self.runner = CliRunner()
    
    def test_main_help_shows_friendly_commands(self):
        """Test that main help shows friendly command list"""
        result = self.runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Available commands:" in result.output
        assert "inspect" in result.output
        assert "plot" in result.output
        assert "filter" in result.output  # Changed from "filter-bag" to "filter"
    
    def test_inspect_file_not_found(self):
        """Test inspect command with nonexistent file"""
        result = self.runner.invoke(app, ["inspect", "nonexistent.bag"])
        assert result.exit_code == 1
        assert "Error: Bag file not found" in result.output
        assert "Path: nonexistent.bag" in result.output
    
    def test_inspect_invalid_format(self):
        """Test inspect command with invalid format"""
        result = self.runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid value for --as: 'invalid'" in result.output
        assert "Valid options:" in result.output
    
    def test_plot_missing_series(self):
        """Test plot command with missing series"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--output", "test.png"])
        assert result.exit_code == 1
        assert "Error: Missing required option: --series" in result.output
        assert "Examples:" in result.output
    
    def test_plot_invalid_series_format(self):
        """Test plot command with invalid series format"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--series", "invalid", "--output", "test.png"])
        assert result.exit_code == 1
        assert "Error: Invalid series format: 'invalid'" in result.output
        assert "Expected format: topic:field1,field2" in result.output
    
    def test_plot_topic_without_slash(self):
        """Test plot command with topic not starting with slash"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--series", "topic:field", "--output", "test.png"])
        assert result.exit_code == 1
        assert "Error: Topic must start with '/': 'topic'" in result.output
        assert "Correct format: /topic:field" in result.output
    
    def test_filter_invalid_compression(self):
        """Test filter command with invalid compression"""
        result = self.runner.invoke(app, ["filter-bag", "tests/demo.bag", "output/", "--compression", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid value for --compression: 'invalid'" in result.output
        assert "Valid options:" in result.output
    
    def test_filter_invalid_sort(self):
        """Test filter command with invalid sort option"""
        result = self.runner.invoke(app, ["filter-bag", "tests/demo.bag", "output/", "--sort-by", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid value for --sort-by: 'invalid'" in result.output
        assert "Valid options:" in result.output


class TestErrorMessageQuality:
    """Test the quality and friendliness of error messages"""
    
    def test_error_messages_are_clear(self):
        """Test that error messages are clear and helpful"""
        runner = CliRunner()
        
        # Test file not found message
        result = runner.invoke(app, ["inspect", "nonexistent.bag"])
        assert "Error: Bag file not found" in result.output
        assert "Path:" in result.output
        
        # Test missing option message
        result = runner.invoke(app, ["plot", "tests/demo.bag", "--output", "test.png"])
        assert "Error: Missing required option" in result.output
        assert "Examples:" in result.output
        assert "Use --help" in result.output
    
    def test_error_messages_provide_examples(self):
        """Test that error messages provide helpful examples"""
        runner = CliRunner()
        
        # Test plot command provides examples
        result = runner.invoke(app, ["plot", "tests/demo.bag", "--output", "test.png"])
        assert "Examples:" in result.output
        assert "/odom:pose.pose.position.x" in result.output
        
        # Test series format error provides examples
        result = runner.invoke(app, ["plot", "tests/demo.bag", "--series", "invalid", "--output", "test.png"])
        assert "Examples:" in result.output
        assert "/odom:pose.pose.position.x" in result.output
    
    def test_error_messages_suggest_alternatives(self):
        """Test that error messages suggest valid alternatives"""
        runner = CliRunner()
        
        # Test invalid format suggests alternatives
        result = runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "invalid"])
        assert "Valid options:" in result.output
        assert "table" in result.output
        assert "list" in result.output
        assert "summary" in result.output
    
    def test_no_tracebacks_in_friendly_errors(self):
        """Test that friendly errors don't show Python tracebacks"""
        runner = CliRunner()
        
        # Test various error conditions don't show tracebacks
        error_commands = [
            ["inspect", "nonexistent.bag"],
            ["inspect", "tests/demo.bag", "--as", "invalid"],
            ["plot", "tests/demo.bag", "--output", "test.png"],
            ["plot", "tests/demo.bag", "--series", "invalid", "--output", "test.png"],
            ["filter-bag", "nonexistent.bag", "output/"],
            ["filter-bag", "tests/demo.bag", "output/", "--compression", "invalid"]
        ]
        
        for cmd in error_commands:
            result = runner.invoke(app, cmd)
            assert result.exit_code == 1
            # Should not contain Python traceback indicators
            assert "Traceback" not in result.output
            assert "File \"" not in result.output
            assert "line " not in result.output
            assert "Exception" not in result.output or "Error:" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 