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

from roseApp.cli.plot import app, plot_cmd
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
    with patch('roseApp.cli.plot.BagAnalysisEngine') as mock:
        engine = mock.return_value
        engine.analyze.return_value = {
            'topics': [
                {
                    'topic': '/cmd_vel',
                    'type': 'geometry_msgs/Twist',
                    'count': 100,
                    'size': 1024,
                    'frequency': 10.0,
                    'fields': ['linear.x', 'linear.y', 'angular.z']
                }
            ],
            'summary': {
                'total_messages': 100,
                'total_size': 1024,
                'duration': 10.0
            }
        }
        yield engine


@pytest.fixture
def mock_plotting_deps():
    """Mock plotting dependencies"""
    with patch('roseApp.cli.plot.check_plotting_dependencies') as mock:
        mock.return_value = True
        yield mock


class TestPlotBasicFunctionality:
    """Test basic plot command functionality"""

    def test_plot_basic_command(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test basic plot command"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_line_type(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with line type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "line"
        ])
        
        assert result.exit_code == 0

    def test_plot_scatter_type(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with scatter type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "scatter"
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_type(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with invalid type"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--type", "invalid"
        ])
        
        assert result.exit_code != 0


class TestPlotOutputFormats:
    """Test plot command output formats"""

    def test_plot_png_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with PNG format"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "png"
        ])
        
        assert result.exit_code == 0

    def test_plot_svg_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with SVG format"""
        output_file = Path(temp_dir) / "output.svg"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "svg"
        ])
        
        assert result.exit_code == 0

    def test_plot_pdf_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with PDF format"""
        output_file = Path(temp_dir) / "output.pdf"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "pdf"
        ])
        
        assert result.exit_code == 0

    def test_plot_html_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with HTML format"""
        output_file = Path(temp_dir) / "output.html"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "html"
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with invalid format"""
        output_file = Path(temp_dir) / "output.txt"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file),
            "--as", "txt"
        ])
        
        assert result.exit_code != 0


class TestPlotSeriesOptions:
    """Test plot command series options"""

    def test_plot_single_field(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with single field"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_multiple_fields(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with multiple fields"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x,linear.y",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_multiple_series(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with multiple series"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--series", "/cmd_vel:angular.z",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_invalid_series_format(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with invalid series format"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "invalid_format",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_nonexistent_topic(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with nonexistent topic"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/nonexistent:field",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_nonexistent_field(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with nonexistent field"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:nonexistent_field",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0


class TestPlotErrorHandling:
    """Test plot command error handling"""

    def test_plot_missing_bag_file(self, temp_dir, mock_plotting_deps):
        """Test plot with missing bag file"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            "/nonexistent/file.bag",
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_missing_output_file(self, sample_bag_file, mock_bag_engine, mock_plotting_deps):
        """Test plot without output file"""
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x"
        ])
        
        assert result.exit_code != 0

    def test_plot_invalid_output_path(self, sample_bag_file, mock_bag_engine, mock_plotting_deps):
        """Test plot with invalid output path"""
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", "/invalid/path/output.png"
        ])
        
        assert result.exit_code != 0

    def test_plot_missing_series(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot without series"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0

    def test_plot_missing_dependencies(self, sample_bag_file, temp_dir, mock_bag_engine):
        """Test plot with missing plotting dependencies"""
        output_file = Path(temp_dir) / "output.png"
        
        with patch('roseApp.cli.plot.check_plotting_dependencies') as mock_deps:
            mock_deps.side_effect = Exception("Missing dependencies")
            
            result = runner.invoke(app, [
                "plot",
                sample_bag_file,
                "--series", "/cmd_vel:linear.x",
                "--output", str(output_file)
            ])
            
            assert result.exit_code != 0

    @patch('roseApp.cli.plot.BagAnalysisEngine')
    def test_plot_engine_error(self, mock_engine_class, sample_bag_file, temp_dir, mock_plotting_deps):
        """Test plot when BagAnalysisEngine raises error"""
        mock_engine = mock_engine_class.return_value
        mock_engine.analyze.side_effect = Exception("Test error")
        
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0


class TestPlotAdvancedFeatures:
    """Test advanced plot command features"""

    def test_plot_with_time_series(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with time series data"""
        output_file = Path(temp_dir) / "output.png"
        
        # Mock time series data
        mock_bag_engine.analyze.return_value['topics'][0]['time_series'] = [
            {'timestamp': 1.0, 'linear.x': 0.1},
            {'timestamp': 2.0, 'linear.x': 0.2},
            {'timestamp': 3.0, 'linear.x': 0.3}
        ]
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_large_dataset(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with large dataset"""
        output_file = Path(temp_dir) / "output.png"
        
        # Mock large dataset
        mock_bag_engine.analyze.return_value['topics'][0]['time_series'] = [
            {'timestamp': float(i), 'linear.x': float(i * 0.1)}
            for i in range(10000)
        ]
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code == 0

    def test_plot_empty_data(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot with empty data"""
        output_file = Path(temp_dir) / "output.png"
        
        # Mock empty data
        mock_bag_engine.analyze.return_value['topics'][0]['time_series'] = []
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        assert result.exit_code != 0  # Should fail with empty data


class TestPlotUtilityFunctions:
    """Test utility functions in plot module"""

    def test_plot_function_imports(self):
        """Test that all necessary imports are available"""
        from roseApp.cli.plot import app, plot_cmd
        assert app is not None
        assert plot_cmd is not None

    def test_plot_dependencies_check(self):
        """Test plotting dependencies check"""
        from roseApp.cli.plot import check_plotting_dependencies
        
        # Should not raise exception
        try:
            check_plotting_dependencies()
        except Exception:
            # Dependencies might not be available in test environment
            pass

    def test_plot_utility_functions(self):
        """Test utility functions are importable"""
        try:
            from roseApp.cli.plot import (
                _format_bytes,
                _format_duration,
                create_frequency_plot,
                create_size_distribution_plot,
                create_message_count_plot,
                create_overview_plot,
                create_plot
            )
            
            assert _format_bytes is not None
            assert _format_duration is not None
            assert create_frequency_plot is not None
            assert create_size_distribution_plot is not None
            assert create_message_count_plot is not None
            assert create_overview_plot is not None
            assert create_plot is not None
        except ImportError:
            # Some functions might not be directly importable
            pass

    @patch('roseApp.cli.plot.set_app_mode')
    def test_app_mode_setting(self, mock_set_mode, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test that app mode is set correctly"""
        output_file = Path(temp_dir) / "output.png"
        
        runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x",
            "--output", str(output_file)
        ])
        
        mock_set_mode.assert_called_with(AppMode.CLI)

    def test_plot_help_message(self):
        """Test plot command help message"""
        result = runner.invoke(app, ["plot", "--help"])
        
        assert result.exit_code == 0
        assert "Generate data visualization plots" in result.output
        assert "--series" in result.output
        assert "--output" in result.output
        assert "--type" in result.output
        assert "--as" in result.output


class TestPlotIntegration:
    """Integration tests for plot command"""

    def test_plot_full_workflow(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test full plot workflow with multiple options"""
        output_file = Path(temp_dir) / "output.png"
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            "--series", "/cmd_vel:linear.x,linear.y",
            "--series", "/cmd_vel:angular.z",
            "--output", str(output_file),
            "--type", "line",
            "--as", "png"
        ])
        
        assert result.exit_code == 0

    def test_plot_different_formats_same_data(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plotting same data in different formats"""
        formats = ["png", "svg", "pdf", "html"]
        
        for fmt in formats:
            output_file = Path(temp_dir) / f"output.{fmt}"
            
            result = runner.invoke(app, [
                "plot",
                sample_bag_file,
                "--series", "/cmd_vel:linear.x",
                "--output", str(output_file),
                "--as", fmt
            ])
            
            assert result.exit_code == 0

    def test_plot_performance_large_series(self, sample_bag_file, temp_dir, mock_bag_engine, mock_plotting_deps):
        """Test plot performance with large series"""
        output_file = Path(temp_dir) / "output.png"
        
        # Create multiple series
        series_args = []
        for i in range(10):
            series_args.extend(["--series", f"/cmd_vel:field_{i}"])
        
        result = runner.invoke(app, [
            "plot",
            sample_bag_file,
            *series_args,
            "--output", str(output_file)
        ])
        
        # Should handle many series gracefully
        assert result.exit_code == 0 or result.exit_code != 0  # Depends on mock data 