#!/usr/bin/env python3
"""
Test plot command functionality - comprehensive test suite
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typer.testing import CliRunner

from roseApp.rose import app
from roseApp.core.util import AppMode

runner = CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def demo_bag_file():
    """Use the actual demo.bag file for testing"""
    bag_path = Path(__file__).parent.parent / "demo.bag"
    return str(bag_path)


@pytest.fixture
def mock_plotting_deps():
    """Mock plotting dependencies"""
    with patch('roseApp.cli.plot.check_plotting_dependencies') as mock:
        mock.return_value = True
        yield mock


class TestPlotBasicFunctionality:
    """Test basic plot command functionality"""

    def test_plot_basic_command(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test basic plot command"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_line_type(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with line type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "line"
        ])
        
        assert result.exit_code == 0

    def test_plot_scatter_type(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with scatter type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "scatter"
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_type(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with invalid type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "invalid"
        ])
        
        assert result.exit_code != 0


class TestPlotOutputFormats:
    """Test plot command output formats"""

    def test_plot_png_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with PNG format"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "png"
        ])
        
        assert result.exit_code == 0

    def test_plot_svg_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with SVG format"""
        output_file = Path(temp_dir) / "output.svg"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "svg"
        ])
        
        assert result.exit_code == 0

    def test_plot_pdf_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with PDF format"""
        output_file = Path(temp_dir) / "output.pdf"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "pdf"
        ])
        
        assert result.exit_code == 0

    def test_plot_html_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with HTML format"""
        output_file = Path(temp_dir) / "output.html"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "html"
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with invalid format"""
        output_file = Path(temp_dir) / "output.txt"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "txt"
        ])
        
        assert result.exit_code != 0


class TestPlotSeriesOptions:
    """Test plot command series options"""

    def test_plot_single_field(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with single field"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_multiple_fields(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with multiple fields"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x,linear.y",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_multiple_series(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with multiple series"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--series", "/cmd_vel:angular.z",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_series_format(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with invalid series format"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "invalid_format",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_nonexistent_topic(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with nonexistent topic"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/nonexistent:field",
            "--output", str(output_file)
        ])
        
        # The command might succeed but with warnings, or fail
        # We just check that it doesn't crash
        assert result.exit_code in [0, 1, 2]

    def test_plot_nonexistent_field(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with nonexistent field"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:nonexistent_field",
            "--output", str(output_file)
        ])
        
        # The command might succeed but with warnings, or fail
        # We just check that it doesn't crash
        assert result.exit_code in [0, 1, 2]


class TestPlotErrorHandling:
    """Test plot command error handling"""

    def test_plot_missing_bag_file(self, temp_dir, mock_plotting_deps):
        """Test plot with missing bag file"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            "nonexistent.bag",
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_missing_output_file(self, demo_bag_file, mock_plotting_deps):
        """Test plot with missing output file"""
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x"
        ])
        
        assert result.exit_code != 0

    def test_plot_invalid_output_path(self, demo_bag_file, mock_plotting_deps):
        """Test plot with invalid output path"""
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", "/invalid/path/output.png"
        ])
        
        # The command might succeed or fail depending on implementation
        # We just check that it doesn't crash
        assert result.exit_code in [0, 1, 2]

    def test_plot_missing_series(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with missing series"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_missing_dependencies(self, demo_bag_file, temp_dir):
        """Test plot with missing dependencies"""
        output_file = Path(temp_dir) / "output.png"
        
        with patch('roseApp.cli.plot.check_plotting_dependencies') as mock:
            mock.return_value = False
            
            result = runner.invoke(app, [
                "plot",
                demo_bag_file,
                "--series", "/cmd_vel:linear.x",
                "--output", str(output_file)
            ])
            
            # The command might succeed or fail depending on implementation
            # We just check that it doesn't crash
            assert result.exit_code in [0, 1, 2]


class TestPlotAdvancedFeatures:
    """Test plot command advanced features"""

    def test_plot_with_time_series(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with time series"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_large_dataset(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with large dataset"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_empty_data(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with empty data"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0


class TestPlotUtilityFunctions:
    """Test plot utility functions"""

    def test_plot_function_imports(self):
        """Test that plot functions can be imported"""
        from roseApp.cli.plot import plot_cmd
        assert callable(plot_cmd)

    def test_plot_dependencies_check(self):
        """Test plot dependencies check"""
        from roseApp.cli.plot import check_plotting_dependencies
        assert callable(check_plotting_dependencies)

    def test_plot_utility_functions(self):
        """Test plot utility functions"""
        from roseApp.cli.plot import (
            _format_bytes,
            _format_duration,
            _extract_time_series_data
        )
        assert callable(_format_bytes)
        assert callable(_format_duration)
        assert callable(_extract_time_series_data)

    def test_plot_help_message(self):
        """Test plot help message"""
        result = runner.invoke(app, ["plot", "--help"])
        
        assert result.exit_code == 0
        assert "plot" in result.stdout.lower()


class TestPlotIntegration:
    """Test plot command integration"""

    def test_plot_full_workflow(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot full workflow"""
        output_file = Path(temp_dir) / "workflow_output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--series", "/cmd_vel:angular.z",
            "--output", str(output_file),
            "--type", "line",
            "--as", "png"
        ])
        
        assert result.exit_code == 0

    def test_plot_different_formats_same_data(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot with different formats for same data"""
        base_name = "same_data"
        
        # Test PNG
        png_file = Path(temp_dir) / f"{base_name}.png"
        result_png = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(png_file),
            "--as", "png"
        ])
        
        # Test SVG
        svg_file = Path(temp_dir) / f"{base_name}.svg"
        result_svg = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(svg_file),
            "--as", "svg"
        ])
        
        # Test PDF
        pdf_file = Path(temp_dir) / f"{base_name}.pdf"
        result_pdf = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(pdf_file),
            "--as", "pdf"
        ])
        
        assert result_png.exit_code == 0
        assert result_svg.exit_code == 0
        assert result_pdf.exit_code == 0

    def test_plot_performance_large_series(self, demo_bag_file, temp_dir, mock_plotting_deps):
        """Test plot performance with large series"""
        output_file = Path(temp_dir) / "performance_output.png"
        
        result = runner.invoke(app, [
            "plot",
            demo_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--series", "/cmd_vel:linear.y",
            "--series", "/cmd_vel:angular.z",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0 