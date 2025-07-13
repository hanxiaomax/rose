#!/usr/bin/env python3
"""
Test suite for plot command functionality
"""

import os
import tempfile
import pytest
from pathlib import Path
from typer.testing import CliRunner
from roseApp.rose import app


class TestPlotFunctionality:
    """Test the plot command functionality"""
    
    def setup_method(self):
        """Setup test runner"""
        self.runner = CliRunner()
        
    def test_plot_basic_line_chart(self):
        """Test basic line chart generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_line.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_scatter_chart(self):
        """Test scatter chart generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_scatter.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path,
                "--type", "scatter"
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_multiple_series(self):
        """Test plotting multiple series"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_multi.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--series", "/tf:transform.translation.y",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_html_output(self):
        """Test HTML interactive plot generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_interactive.html")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path,
                "--as", "html"
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 1000  # HTML should be larger
    
    def test_plot_svg_output(self):
        """Test SVG format output"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_plot.svg")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path,
                "--as", "svg"
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_pdf_output(self):
        """Test PDF format output"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_plot.pdf")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path,
                "--as", "pdf"
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_nonexistent_topic_warning(self):
        """Test warning for nonexistent topics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_warning.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/nonexistent:field",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "Warning: The following topics were not found" in result.output
            assert "/nonexistent" in result.output
            assert "Available topics:" in result.output
            assert os.path.exists(output_path)  # Should still create empty plot
    
    def test_plot_nested_field_access(self):
        """Test accessing nested fields with dot notation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_nested.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_auto_field_detection(self):
        """Test automatic numeric field detection when no fields specified"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_auto.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:",  # No fields specified
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_progress_display(self):
        """Test that progress is displayed during plotting"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_progress.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "Analyzing bag file" in result.output
            assert "Extracting /tf" in result.output
            assert "Creating line plot" in result.output
            assert "✓ Plot saved to:" in result.output
    
    def test_plot_output_directory_creation(self):
        """Test that output directories are created automatically"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "subdir", "nested", "test.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_plot_field_validation(self):
        """Test plotting with various field formats"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_fields.png")
            
            result = self.runner.invoke(app, [
                "plot", "tests/demo.bag", 
                "--series", "/tf:transform.translation.x,transform.translation.y",
                "--output", output_path
            ])
            
            assert result.exit_code == 0
            assert "✓ Plot saved to:" in result.output
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0


class TestPlotErrorHandling:
    """Test plot command error handling"""
    
    def setup_method(self):
        """Setup test runner"""
        self.runner = CliRunner()
    
    def test_plot_file_not_found(self):
        """Test error when bag file doesn't exist"""
        result = self.runner.invoke(app, [
            "plot", "nonexistent.bag", 
            "--series", "/tf:transform.translation.x",
            "--output", "test.png"
        ])
        
        assert result.exit_code == 1
        assert "Error: Bag file not found" in result.output
    
    def test_plot_missing_series(self):
        """Test error when no series specified"""
        result = self.runner.invoke(app, [
            "plot", "tests/demo.bag", 
            "--output", "test.png"
        ])
        
        assert result.exit_code == 1
        assert "Error: Missing required option: --series" in result.output
        assert "Examples:" in result.output
    
    def test_plot_invalid_series_format(self):
        """Test error with invalid series format"""
        result = self.runner.invoke(app, [
            "plot", "tests/demo.bag", 
            "--series", "invalid_format",
            "--output", "test.png"
        ])
        
        assert result.exit_code == 1
        assert "Error: Invalid series format" in result.output
        assert "Expected format: topic:field1,field2" in result.output
    
    def test_plot_invalid_output_format(self):
        """Test error with invalid output format"""
        result = self.runner.invoke(app, [
            "plot", "tests/demo.bag", 
            "--series", "/tf:transform.translation.x",
            "--output", "test.xyz",
            "--as", "invalid"
        ])
        
        assert result.exit_code == 1
        assert "Error: Invalid value for --as: 'invalid'" in result.output
        assert "Valid options:" in result.output
    
    def test_plot_invalid_plot_type(self):
        """Test error with invalid plot type"""
        result = self.runner.invoke(app, [
            "plot", "tests/demo.bag", 
            "--series", "/tf:transform.translation.x",
            "--output", "test.png",
            "--type", "invalid"
        ])
        
        assert result.exit_code == 1
        assert "Error: Invalid value for --type: 'invalid'" in result.output
        assert "Valid options:" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 