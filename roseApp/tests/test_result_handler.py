"""
Test cases for result_handler module
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from roseApp.core.result_handler import (
    ResultHandler, OutputFormat, RenderOptions, ExportOptions,
    YAML_AVAILABLE
)


class TestOutputFormat:
    """Test cases for OutputFormat enum"""
    
    def test_output_format_values(self):
        """Test output format enum values"""
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.YAML.value == "yaml"
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.XML.value == "xml"
        assert OutputFormat.HTML.value == "html"
        assert OutputFormat.MARKDOWN.value == "markdown"


class TestRenderOptions:
    """Test cases for RenderOptions class"""
    
    def test_render_options_defaults(self):
        """Test default render options"""
        options = RenderOptions()
        assert options.format == OutputFormat.TABLE
        assert options.verbose is False
        assert options.show_fields is False
        assert options.show_cache_stats is True
        assert options.show_summary is True
        assert options.color is True
        assert options.width is None
        assert options.title is None


class TestExportOptions:
    """Test cases for ExportOptions class"""
    
    def test_export_options_defaults(self):
        """Test default export options"""
        options = ExportOptions()
        assert options.format == OutputFormat.JSON
        assert options.pretty is True
        assert options.include_metadata is True
        assert options.compress is False


class TestResultHandler:
    """Test cases for ResultHandler class"""
    
    def test_handler_initialization(self):
        """Test basic handler initialization"""
        handler = ResultHandler()
        assert handler is not None
    
    def test_prepare_serializable_result(self):
        """Test preparing result for serialization"""
        handler = ResultHandler()
        
        # Test with Path objects
        result = {
            'bag_info': {
                'file_path': Path('/tmp/test.bag'),
                'file_name': 'test.bag'
            },
            'topics': [
                {'name': '/topic1', 'message_count': 100}
            ]
        }
        
        serializable = handler._prepare_serializable_result(result)
        assert serializable['bag_info']['file_path'] == '/tmp/test.bag'
        assert isinstance(serializable['bag_info']['file_path'], str)
    
    def test_format_size(self):
        """Test size formatting"""
        handler = ResultHandler()
        
        assert handler._format_size(500) == "500.0 B"
        assert handler._format_size(1024) == "1.0 KB"
        assert handler._format_size(1024 * 1024) == "1.0 MB"
        assert handler._format_size(1024 * 1024 * 1024) == "1.0 GB"
    
    def test_get_timestamp(self):
        """Test timestamp generation"""
        handler = ResultHandler()
        timestamp = handler._get_timestamp()
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0
    
    def test_render_table(self, sample_analysis_result):
        """Test rendering results as table"""
        handler = ResultHandler()
        
        options = RenderOptions(format=OutputFormat.TABLE)
        result_str = handler.render(sample_analysis_result, options)
        
        # Table rendering outputs to console, returns empty string
        assert result_str == ""
    
    def test_render_list(self, sample_analysis_result):
        """Test rendering results as list"""
        handler = ResultHandler()
        
        options = RenderOptions(format=OutputFormat.LIST)
        result_str = handler.render(sample_analysis_result, options)
        
        # List rendering outputs to console, returns empty string
        assert result_str == ""
    
    def test_render_summary(self, sample_analysis_result):
        """Test rendering results as summary"""
        handler = ResultHandler()
        
        options = RenderOptions(format=OutputFormat.SUMMARY)
        result_str = handler.render(sample_analysis_result, options)
        
        # Summary rendering outputs to console, returns empty string
        assert result_str == ""
    
    def test_render_json(self, sample_analysis_result):
        """Test rendering results as JSON"""
        handler = ResultHandler()
        
        options = RenderOptions(format=OutputFormat.JSON)
        result_str = handler.render(sample_analysis_result, options)
        
        assert isinstance(result_str, str)
        assert '"bag_info"' in result_str
        assert '"topics"' in result_str
    
    def test_render_yaml(self, sample_analysis_result):
        """Test rendering results as YAML"""
        handler = ResultHandler()
        
        if YAML_AVAILABLE:
            options = RenderOptions(format=OutputFormat.YAML)
            result_str = handler.render(sample_analysis_result, options)
            
            assert isinstance(result_str, str)
            assert 'bag_info:' in result_str
        else:
            pytest.skip("YAML library not available")
    
    def test_render_yaml_not_available(self, sample_analysis_result):
        """Test YAML rendering when library not available"""
        with patch('roseApp.core.result_handler.YAML_AVAILABLE', False):
            handler = ResultHandler()
            
            options = RenderOptions(format=OutputFormat.YAML)
            result_str = handler.render(sample_analysis_result, options)
            
            assert result_str == ""
    
    def test_render_markdown(self, sample_analysis_result):
        """Test rendering results as Markdown"""
        handler = ResultHandler()
        
        options = RenderOptions(format=OutputFormat.MARKDOWN)
        result_str = handler.render(sample_analysis_result, options)
        
        assert isinstance(result_str, str)
        assert "# Bag Analysis Report" in result_str
        assert "| Topic | Message Type | Count | Frequency |" in result_str
    
    def test_export_json(self, temp_dir, sample_analysis_result):
        """Test exporting results as JSON"""
        handler = ResultHandler()
        
        output_file = temp_dir / "output.json"
        options = ExportOptions(
            format=OutputFormat.JSON,
            output_file=output_file,
            pretty=True
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert '"bag_info"' in content
        assert '"topics"' in content
    
    def test_export_yaml(self, temp_dir, sample_analysis_result):
        """Test exporting results as YAML"""
        if not YAML_AVAILABLE:
            pytest.skip("YAML library not available")
        
        handler = ResultHandler()
        
        output_file = temp_dir / "output.yaml"
        options = ExportOptions(
            format=OutputFormat.YAML,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert 'bag_info:' in content
    
    def test_export_csv(self, temp_dir, sample_analysis_result):
        """Test exporting results as CSV"""
        handler = ResultHandler()
        
        output_file = temp_dir / "output.csv"
        options = ExportOptions(
            format=OutputFormat.CSV,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert 'topic,message_type,message_count,frequency' in content
        assert '/topic1' in content
    
    def test_export_xml(self, temp_dir, sample_analysis_result):
        """Test exporting results as XML"""
        handler = ResultHandler()
        
        output_file = temp_dir / "output.xml"
        options = ExportOptions(
            format=OutputFormat.XML,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert '<bag_analysis>' in content
        assert '<topics>' in content
    
    def test_export_html(self, temp_dir, sample_analysis_result):
        """Test exporting results as HTML"""
        handler = ResultHandler()
        
        output_file = temp_dir / "output.html"
        options = ExportOptions(
            format=OutputFormat.HTML,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert '<!DOCTYPE html>' in content
        assert 'ROS Bag Analysis Report' in content
    
    def test_export_markdown(self, temp_dir, sample_analysis_result):
        """Test exporting results as Markdown"""
        handler = ResultHandler()
        
        output_file = temp_dir / "output.md"
        options = ExportOptions(
            format=OutputFormat.MARKDOWN,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is True
        assert output_file.exists()
        
        content = output_file.read_text()
        assert '# Bag Analysis Report' in content
        assert '| Topic | Message Type | Count | Frequency |' in content
    
    def test_export_unsupported_format(self, sample_analysis_result):
        """Test handling unsupported export format"""
        handler = ResultHandler()
        
        # Create a mock format
        class MockFormat:
            value = "unsupported"
        
        options = ExportOptions(format=MockFormat())
        success = handler.export(sample_analysis_result, options)
        
        assert success is False
    
    def test_export_error_handling(self, temp_dir, sample_analysis_result):
        """Test handling export errors"""
        handler = ResultHandler()
        
        # Use invalid path to trigger error
        output_file = temp_dir / "nonexistent" / "output.json"
        options = ExportOptions(
            format=OutputFormat.JSON,
            output_file=output_file
        )
        
        success = handler.export(sample_analysis_result, options)
        
        assert success is False
    
    def test_convert_format(self, sample_analysis_result):
        """Test format conversion"""
        handler = ResultHandler()
        
        # Test JSON to JSON conversion
        json_str = handler.convert_format(
            sample_analysis_result,
            OutputFormat.JSON,
            OutputFormat.JSON
        )
        
        assert isinstance(json_str, str)
        assert '"bag_info"' in json_str
    
    def test_display_summary(self, sample_analysis_result):
        """Test displaying summary information"""
        handler = ResultHandler()
        
        # This is a private method that outputs to console
        # Just verify it doesn't raise exceptions
        bag_info = sample_analysis_result['bag_info']
        options = RenderOptions()
        
        try:
            handler._display_summary(bag_info, options)
        except Exception as e:
            pytest.fail(f"_display_summary raised exception: {e}")
    
    def test_display_field_analysis(self, sample_analysis_result):
        """Test displaying field analysis"""
        handler = ResultHandler()
        
        field_analysis = sample_analysis_result['field_analysis']
        
        try:
            handler._display_field_analysis(field_analysis)
        except Exception as e:
            pytest.fail(f"_display_field_analysis raised exception: {e}")
    
    def test_display_cache_stats(self, sample_analysis_result):
        """Test displaying cache statistics"""
        handler = ResultHandler()
        
        cache_stats = sample_analysis_result['cache_stats']
        
        try:
            handler._display_cache_stats(cache_stats)
        except Exception as e:
            pytest.fail(f"_display_cache_stats raised exception: {e}")
    
    def test_render_with_custom_console(self):
        """Test handler with custom console"""
        mock_console = Mock()
        handler = ResultHandler(console=mock_console)
        
        assert handler.console == mock_console