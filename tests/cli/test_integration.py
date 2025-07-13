#!/usr/bin/env python3
"""
Integration tests for inspect and plot commands - basic functionality verification
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from roseApp.cli.inspect import app as inspect_app
from roseApp.cli.plot import app as plot_app
from roseApp.rose import app as main_app
from typer.testing import CliRunner


class TestInspectIntegration:
    """Integration tests for inspect command"""
    
    def test_inspect_help(self):
        """Test inspect help command"""
        runner = CliRunner()
        result = runner.invoke(inspect_app, ["--help"])
        assert result.exit_code == 0
        assert "Fast inspection of ROS bag files" in result.output

    def test_inspect_command_available_in_main_app(self):
        """Test that inspect command is available in main app"""
        runner = CliRunner()
        result = runner.invoke(main_app, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "Fast inspection of ROS bag files" in result.output

    def test_inspect_nonexistent_file(self):
        """Test inspect with non-existent file"""
        runner = CliRunner()
        result = runner.invoke(inspect_app, ["inspect", "nonexistent.bag"])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_inspect_csv_without_output(self):
        """Test inspect CSV format without output file"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(inspect_app, ["inspect", str(tmp_path), "--as", "csv"])
            assert result.exit_code == 1
            assert "requires --output" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_inspect_html_without_output(self):
        """Test inspect HTML format without output file"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(inspect_app, ["inspect", str(tmp_path), "--as", "html"])
            assert result.exit_code == 1
            assert "requires --output" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)


class TestPlotIntegration:
    """Integration tests for plot command"""
    
    def test_plot_help(self):
        """Test plot help command"""
        runner = CliRunner()
        result = runner.invoke(plot_app, ["--help"])
        assert result.exit_code == 0
        assert "Generate data visualization plots" in result.output

    def test_plot_command_available_in_main_app(self):
        """Test that plot command is available in main app"""
        runner = CliRunner()
        result = runner.invoke(main_app, ["plot", "--help"])
        assert result.exit_code == 0
        assert "Generate data visualization plots" in result.output

    def test_plot_nonexistent_file(self):
        """Test plot with non-existent file"""
        runner = CliRunner()
        result = runner.invoke(plot_app, ["plot", "nonexistent.bag", "--series", "/test:field", "--output", "out.png"])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_plot_no_series(self):
        """Test plot without series parameter"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(plot_app, ["plot", str(tmp_path), "--output", "out.png"])
            assert result.exit_code == 1
            assert "At least one --series must be specified" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_plot_invalid_series_format(self):
        """Test plot with invalid series format"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(plot_app, ["plot", str(tmp_path), "--series", "invalid", "--output", "out.png"])
            assert result.exit_code == 1
            assert "Invalid series format" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_plot_invalid_type(self):
        """Test plot with invalid plot type"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(plot_app, ["plot", str(tmp_path), "--series", "/test:field", "--output", "out.png", "--type", "invalid"])
            assert result.exit_code == 1
            assert "must be one of: line, scatter" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_plot_invalid_format(self):
        """Test plot with invalid output format"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            runner = CliRunner()
            result = runner.invoke(plot_app, ["plot", str(tmp_path), "--series", "/test:field", "--output", "out.xyz", "--as", "invalid"])
            assert result.exit_code == 1
            assert "must be one of: png, svg, pdf, html" in result.output
        finally:
            tmp_path.unlink(missing_ok=True)


class TestMainAppIntegration:
    """Integration tests for main app with new commands"""
    
    def test_main_app_help_includes_new_commands(self):
        """Test that main app help includes inspect and plot commands"""
        runner = CliRunner()
        result = runner.invoke(main_app, ["--help"])
        assert result.exit_code == 0
        assert "inspect" in result.output
        assert "plot" in result.output

    def test_main_app_inspect_subcommand(self):
        """Test inspect subcommand through main app"""
        runner = CliRunner()
        result = runner.invoke(main_app, ["inspect", "--help"])
        assert result.exit_code == 0
        assert "Fast inspection of ROS bag files" in result.output

    def test_main_app_plot_subcommand(self):
        """Test plot subcommand through main app"""
        runner = CliRunner()
        result = runner.invoke(main_app, ["plot", "--help"])
        assert result.exit_code == 0
        assert "Generate data visualization plots" in result.output


if __name__ == "__main__":
    pytest.main([__file__]) 