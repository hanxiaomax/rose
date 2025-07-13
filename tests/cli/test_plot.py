#!/usr/bin/env python3
"""
Test plot command functionality - simplified and focused tests
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

from roseApp.cli.plot import (
    plot_cmd,
    check_plotting_dependencies,
    PlottingError,
    _format_bytes,
    _format_duration,
    create_frequency_plot,
    create_size_distribution_plot,
    create_message_count_plot,
    create_overview_plot,
    create_plot
)


@pytest.fixture
def mock_json_data():
    """Mock JSON data for plotting tests"""
    return {
        'summary': {
            'file_name': 'test.bag',
            'file_path': '/path/to/test.bag',
            'topic_count': 2,
            'total_messages': 300,
            'file_size': 1024,
            'file_size_formatted': '1.0 KB',
            'duration': 10.0,
            'duration_formatted': '10.0s',
            'avg_rate': 30.0,
            'avg_rate_formatted': '30.0 Hz'
        },
        'topics': [
            {
                'topic': '/test_topic1',
                'count': 100,
                'size': 512,
                'size_formatted': '512 B',
                'frequency': 10.0,
                'frequency_formatted': '10.0 Hz'
            },
            {
                'topic': '/test_topic2',
                'count': 200,
                'size': 1024,
                'size_formatted': '1.0 KB',
                'frequency': 20.0,
                'frequency_formatted': '20.0 Hz'
            }
        ]
    }


class TestPlotCommand:
    """Test plot command functionality"""

    @patch('roseApp.cli.plot.typer.echo')
    @patch('roseApp.cli.plot.os.path.exists')
    def test_plot_file_not_found(self, mock_exists, mock_echo):
        """Test plot command with non-existent file"""
        mock_exists.return_value = False
        
        with pytest.raises(SystemExit):
            plot_cmd("nonexistent.bag", series=["/test:field"], output="output.png")
        
        mock_echo.assert_called_with("Error: Input path 'nonexistent.bag' does not exist", err=True)

    @patch('roseApp.cli.plot.typer.echo')
    @patch('roseApp.cli.plot.os.path.exists')
    @patch('roseApp.cli.plot.os.path.isfile')
    def test_plot_not_a_file(self, mock_isfile, mock_exists, mock_echo):
        """Test plot command with directory instead of file"""
        mock_exists.return_value = True
        mock_isfile.return_value = False
        
        with pytest.raises(SystemExit):
            plot_cmd("/tmp/directory", series=["/test:field"], output="output.png")
        
        mock_echo.assert_called_with("Error: Input path '/tmp/directory' is not a file", err=True)

    @patch('roseApp.cli.plot.typer.echo')
    @patch('roseApp.cli.plot.os.path.exists')
    @patch('roseApp.cli.plot.os.path.isfile')
    def test_plot_no_series(self, mock_isfile, mock_exists, mock_echo):
        """Test plot command without series parameter"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        
        with pytest.raises(SystemExit):
            plot_cmd("test.bag", series=[], output="output.png")
        
        mock_echo.assert_called_with("Error: At least one --series must be specified", err=True)

    @patch('roseApp.cli.plot.typer.echo')
    @patch('roseApp.cli.plot.os.path.exists')
    @patch('roseApp.cli.plot.os.path.isfile')
    def test_plot_invalid_series_format(self, mock_isfile, mock_exists, mock_echo):
        """Test plot command with invalid series format"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        
        with pytest.raises(SystemExit):
            plot_cmd("test.bag", series=["invalid_format"], output="output.png")
        
        mock_echo.assert_called_with("Error: Invalid series format 'invalid_format'. Expected format: topic:field1,field2", err=True)


class TestPlottingDependencies:
    """Test plotting dependencies checking"""

    @patch('roseApp.cli.plot.MATPLOTLIB_AVAILABLE', True)
    @patch('roseApp.cli.plot.PLOTLY_AVAILABLE', True)
    @patch('roseApp.cli.plot.PANDAS_AVAILABLE', True)
    def test_check_plotting_dependencies_all_available(self):
        """Test when all plotting dependencies are available"""
        # Should not raise exception
        check_plotting_dependencies()

    @patch('roseApp.cli.plot.MATPLOTLIB_AVAILABLE', False)
    @patch('roseApp.cli.plot.PLOTLY_AVAILABLE', True)
    @patch('roseApp.cli.plot.PANDAS_AVAILABLE', True)
    def test_check_plotting_dependencies_missing_matplotlib(self):
        """Test when matplotlib is missing"""
        with pytest.raises(PlottingError) as exc_info:
            check_plotting_dependencies()
        assert "matplotlib" in str(exc_info.value)

    @patch('roseApp.cli.plot.MATPLOTLIB_AVAILABLE', False)
    @patch('roseApp.cli.plot.PLOTLY_AVAILABLE', False)
    @patch('roseApp.cli.plot.PANDAS_AVAILABLE', False)
    def test_check_plotting_dependencies_all_missing(self):
        """Test when all plotting dependencies are missing"""
        with pytest.raises(PlottingError) as exc_info:
            check_plotting_dependencies()
        assert "matplotlib" in str(exc_info.value)
        assert "plotly" in str(exc_info.value)
        assert "pandas" in str(exc_info.value)


class TestPlotCreation:
    """Test plot creation functionality"""

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_frequency_plot(self, mock_check_deps, mock_json_data):
        """Test frequency plot creation"""
        mock_check_deps.return_value = None
        
        with patch('roseApp.cli.plot._create_frequency_plot_matplotlib') as mock_create:
            mock_create.return_value = "output.png"
            
            result = create_frequency_plot(mock_json_data, "output.png", "png")
            assert result == "output.png"
            mock_create.assert_called_once()

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_size_distribution_plot(self, mock_check_deps, mock_json_data):
        """Test size distribution plot creation"""
        mock_check_deps.return_value = None
        
        with patch('roseApp.cli.plot._create_size_plot_matplotlib') as mock_create:
            mock_create.return_value = "output.png"
            
            result = create_size_distribution_plot(mock_json_data, "output.png", "png")
            assert result == "output.png"
            mock_create.assert_called_once()

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_message_count_plot(self, mock_check_deps, mock_json_data):
        """Test message count plot creation"""
        mock_check_deps.return_value = None
        
        with patch('roseApp.cli.plot._create_count_plot_matplotlib') as mock_create:
            mock_create.return_value = "output.png"
            
            result = create_message_count_plot(mock_json_data, "output.png", "png")
            assert result == "output.png"
            mock_create.assert_called_once()

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_overview_plot(self, mock_check_deps, mock_json_data):
        """Test overview plot creation"""
        mock_check_deps.return_value = None
        
        with patch('roseApp.cli.plot._create_overview_plot_matplotlib') as mock_create:
            mock_create.return_value = "output.png"
            
            result = create_overview_plot(mock_json_data, "output.png", "png")
            assert result == "output.png"
            mock_create.assert_called_once()

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_plot_invalid_type(self, mock_check_deps, mock_json_data):
        """Test creating plot with invalid type"""
        mock_check_deps.return_value = None
        
        with pytest.raises(PlottingError) as exc_info:
            create_plot(mock_json_data, "invalid_type", "output.png", "png")
        assert "Unknown plot type" in str(exc_info.value)

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_plot_frequency(self, mock_check_deps, mock_json_data):
        """Test creating frequency plot"""
        mock_check_deps.return_value = None
        
        with patch('roseApp.cli.plot.create_frequency_plot') as mock_create:
            mock_create.return_value = "output.png"
            
            result = create_plot(mock_json_data, "frequency", "output.png", "png")
            assert result == "output.png"
            mock_create.assert_called_once()


class TestPlotWithNoData:
    """Test plot creation when data is missing"""

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_frequency_plot_no_data(self, mock_check_deps):
        """Test frequency plot creation with no frequency data"""
        mock_check_deps.return_value = None
        
        json_data = {
            'topics': [
                {'topic': '/test', 'frequency': None}
            ],
            'summary': {'file_name': 'test.bag'}
        }
        
        with pytest.raises(PlottingError) as exc_info:
            create_frequency_plot(json_data, "output.png", "png")
        assert "No frequency data available" in str(exc_info.value)

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_size_plot_no_data(self, mock_check_deps):
        """Test size plot creation with no size data"""
        mock_check_deps.return_value = None
        
        json_data = {
            'topics': [
                {'topic': '/test', 'size': None}
            ],
            'summary': {'file_name': 'test.bag'}
        }
        
        with pytest.raises(PlottingError) as exc_info:
            create_size_distribution_plot(json_data, "output.png", "png")
        assert "No size data available" in str(exc_info.value)

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_count_plot_no_data(self, mock_check_deps):
        """Test count plot creation with no count data"""
        mock_check_deps.return_value = None
        
        json_data = {
            'topics': [
                {'topic': '/test', 'count': None}
            ],
            'summary': {'file_name': 'test.bag'}
        }
        
        with pytest.raises(PlottingError) as exc_info:
            create_message_count_plot(json_data, "output.png", "png")
        assert "No message count data available" in str(exc_info.value)

    @patch('roseApp.cli.plot.check_plotting_dependencies')
    def test_create_overview_plot_no_data(self, mock_check_deps):
        """Test overview plot creation with incomplete data"""
        mock_check_deps.return_value = None
        
        json_data = {
            'topics': [
                {'topic': '/test', 'count': None, 'size': None, 'frequency': None}
            ],
            'summary': {'file_name': 'test.bag'}
        }
        
        with pytest.raises(PlottingError) as exc_info:
            create_overview_plot(json_data, "output.png", "png")
        assert "No complete data available" in str(exc_info.value)


class TestUtilityFunctions:
    """Test utility functions"""

    def test_format_bytes(self):
        """Test bytes formatting"""
        assert _format_bytes(0) == "0 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(1024 * 1024 * 1024) == "1.0 GB"

    def test_format_duration(self):
        """Test duration formatting"""
        assert _format_duration(30) == "30.0s"
        assert _format_duration(90) == "1.5m"
        assert _format_duration(3600) == "1.0h"


if __name__ == "__main__":
    pytest.main([__file__]) 