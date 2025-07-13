#!/usr/bin/env python3
"""
Test suite for simplified error handling in CLI commands
"""

import os
import tempfile
import pytest
from unittest.mock import patch, Mock
from typer.testing import CliRunner
from roseApp.cli.error_handling import (
    ValidationError, validate_file_exists, validate_choice, 
    validate_series_format, validate_output_requirement, handle_runtime_error
)
from roseApp.rose import app


class TestValidationFunctions:
    """Test the validation functions"""
    
    def test_validate_file_exists_success(self):
        """Test file validation with existing file"""
        # Should not raise any exception
        validate_file_exists("tests/demo.bag", "bag file")
    
    def test_validate_file_exists_missing(self):
        """Test file validation with missing file"""
        with pytest.raises(ValidationError, match="Bag file not found"):
            validate_file_exists("nonexistent.bag", "bag file")
    
    def test_validate_file_exists_directory(self):
        """Test file validation when path is directory"""
        with pytest.raises(ValidationError, match="Expected a file.*is a directory"):
            validate_file_exists("tests", "bag file")
    
    def test_validate_choice_success(self):
        """Test choice validation with valid value"""
        # Should not raise any exception
        validate_choice("png", ["png", "svg", "pdf"], "--as")
    
    def test_validate_choice_invalid(self):
        """Test choice validation with invalid value"""
        with pytest.raises(ValidationError, match="Invalid --as.*Valid choices"):
            validate_choice("invalid", ["png", "svg", "pdf"], "--as")
    
    def test_validate_series_format_success(self):
        """Test series format validation with valid format"""
        # Should not raise any exception
        validate_series_format(["/tf:transform.translation.x", "/odom:pose.position.y"])
    
    def test_validate_series_format_no_colon(self):
        """Test series format validation without colon"""
        with pytest.raises(ValidationError, match="Invalid series format.*Expected format"):
            validate_series_format(["invalid_format"])
    
    def test_validate_series_format_no_slash(self):
        """Test series format validation without leading slash"""
        with pytest.raises(ValidationError, match="Topic must start with"):
            validate_series_format(["topic:field"])
    
    def test_validate_output_requirement_success(self):
        """Test output requirement validation when output provided"""
        # Should not raise any exception
        validate_output_requirement("csv", "output.csv")
        validate_output_requirement("table", None)  # table doesn't require output
    
    def test_validate_output_requirement_missing(self):
        """Test output requirement validation when output missing"""
        with pytest.raises(ValidationError, match="--as=csv requires --output"):
            validate_output_requirement("csv", None)


class TestCLIIntegration:
    """Test CLI integration with simplified error handling"""
    
    def setup_method(self):
        """Setup test runner"""
        self.runner = CliRunner()
    
    def test_main_help_shows_commands(self):
        """Test that main help shows command list"""
        result = self.runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Available commands:" in result.output
        assert "inspect" in result.output
        assert "plot" in result.output
        assert "filter-bag" in result.output
    
    def test_inspect_file_not_found(self):
        """Test inspect command with nonexistent file"""
        result = self.runner.invoke(app, ["inspect", "nonexistent.bag"])
        assert result.exit_code == 1
        assert "Error: Bag file not found" in result.output
    
    def test_inspect_invalid_format(self):
        """Test inspect command with invalid format"""
        result = self.runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid --as: 'invalid'" in result.output
    
    def test_plot_missing_series_typer_error(self):
        """Test that typer handles missing required series parameter"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--output", "test.png"])
        assert result.exit_code == 2  # typer/click error code for missing required parameter
        assert "Missing option" in result.output or "required" in result.output.lower()
    
    def test_plot_missing_output_typer_error(self):
        """Test that typer handles missing required output parameter"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--series", "/tf:transform"])
        assert result.exit_code == 2  # typer/click error code for missing required parameter
        assert "Missing option" in result.output or "required" in result.output.lower()
    
    def test_plot_invalid_series_format(self):
        """Test plot command with invalid series format"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--series", "invalid", "--output", "test.png"])
        assert result.exit_code == 1
        assert "Error: Invalid series format" in result.output
    
    def test_plot_topic_without_slash(self):
        """Test plot command with topic not starting with slash"""
        result = self.runner.invoke(app, ["plot", "tests/demo.bag", "--series", "topic:field", "--output", "test.png"])
        assert result.exit_code == 1
        assert "Error: Topic must start with '/'" in result.output
    
    def test_filter_invalid_compression(self):
        """Test filter command with invalid compression"""
        result = self.runner.invoke(app, ["filter-bag", "tests/demo.bag", "output/", "--compression", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid --compression" in result.output
    
    def test_filter_invalid_sort(self):
        """Test filter command with invalid sort option"""
        result = self.runner.invoke(app, ["filter-bag", "tests/demo.bag", "output/", "--sort-by", "invalid"])
        assert result.exit_code == 1
        assert "Error: Invalid --sort-by" in result.output


class TestErrorMessageQuality:
    """Test the quality and simplicity of error messages"""
    
    def test_validation_errors_are_clean(self):
        """Test that validation errors are clean and simple"""
        runner = CliRunner()
        
        # Test file not found message
        result = runner.invoke(app, ["inspect", "nonexistent.bag"])
        assert "Error: Bag file not found" in result.output
        assert "Context: Parameter validation" in result.output
        
        # Test invalid option message
        result = runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "invalid"])
        assert "Error: Invalid --as" in result.output
        assert "Valid choices:" in result.output
    
    def test_typer_handles_missing_required_params(self):
        """Test that typer naturally handles missing required parameters"""
        runner = CliRunner()
        
        # Test missing required output parameter (typer handles this)
        result = runner.invoke(app, ["plot", "tests/demo.bag", "--series", "/tf:transform"])
        assert result.exit_code == 2  # typer error code
        assert "Missing option" in result.output or "required" in result.output.lower()
        
        # Test missing required series parameter (typer handles this too)
        result = runner.invoke(app, ["plot", "tests/demo.bag", "--output", "test.png"])
        assert result.exit_code == 2  # typer error code
        assert "Missing option" in result.output or "required" in result.output.lower()
    
    def test_no_tracebacks_in_runtime_errors(self):
        """Test that runtime errors don't show Python tracebacks"""
        runner = CliRunner()
        
        # Test various error conditions don't show tracebacks
        error_commands = [
            ["inspect", "nonexistent.bag"],
            ["inspect", "tests/demo.bag", "--as", "invalid"],
            ["plot", "tests/demo.bag", "--series", "invalid", "--output", "test.png"],
            ["filter-bag", "nonexistent.bag", "output/"],
            ["filter-bag", "tests/demo.bag", "output/", "--compression", "invalid"]
        ]
        
        for cmd in error_commands:
            result = runner.invoke(app, cmd)
            # Runtime validation errors should have exit code 1
            if result.exit_code == 1:
                # Should not contain Python traceback indicators
                assert "Traceback" not in result.output
                assert "File \"" not in result.output
                assert "line " not in result.output
                # Should contain clean error message
                assert "Error:" in result.output


class TestHandleRuntimeError:
    """Test the handle_runtime_error function"""
    
    def test_handle_runtime_error_simple(self, capsys):
        """Test runtime error handling with simple message"""
        error = Exception("Something went wrong")
        
        # handle_runtime_error raises typer.Exit which is click.exceptions.Exit
        from click.exceptions import Exit
        with pytest.raises(Exit):
            handle_runtime_error(error, "Test operation")
        
        # Note: We can't easily test rich console output in pytest
        # The function works correctly as demonstrated in integration tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 