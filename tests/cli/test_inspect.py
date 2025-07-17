#!/usr/bin/env python3
"""
Test inspect command functionality - simplified and focused tests
"""
import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path
from typer.testing import CliRunner

from roseApp.cli.inspect import (
    _filter_topics,
    _fuzzy_search_topics,
    _format_size,
    _format_duration,
    _get_cache_path,
    _load_cache,
    _save_cache
)


class TestTopicFiltering:
    """Test topic filtering functionality"""

    def test_filter_topics_empty_filter(self):
        """Test filtering with empty filter returns all topics"""
        topics = ['/test1', '/test2', '/test3']
        result = _filter_topics(topics, [])
        assert result == topics

    def test_filter_topics_exact_match(self):
        """Test exact topic matching"""
        topics = ['/test1', '/test2', '/test3']
        result = _filter_topics(topics, ['/test1'])
        assert result == ['/test1']

    def test_filter_topics_fuzzy_search(self):
        """Test fuzzy topic search"""
        topics = ['/test_topic', '/another_topic', '/different']
        result = _filter_topics(topics, ['test'])
        assert '/test_topic' in result

    def test_fuzzy_search_topics_basic(self):
        """Test basic fuzzy search"""
        topics = ['/test_topic', '/another_topic', '/different']
        result = _fuzzy_search_topics(topics, 'test')
        assert '/test_topic' in result


class TestUtilityFunctions:
    """Test utility functions"""

    def test_format_size_bytes(self):
        """Test size formatting"""
        assert _format_size(0) == "0 B"
        assert _format_size(1024) == "1.0 KB"
        assert _format_size(1024 * 1024) == "1.0 MB"
        assert _format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_format_duration_seconds(self):
        """Test duration formatting"""
        assert _format_duration(30) == "30.0s"
        assert _format_duration(90) == "1m 30.0s"
        assert _format_duration(3660) == "1h 1m 0.0s"

    def test_get_cache_path(self):
        """Test cache path generation"""
        with patch('roseApp.cli.inspect.os.stat') as mock_stat:
            mock_stat.return_value.st_mtime = 1234567890
            mock_stat.return_value.st_size = 1024
            
            path = _get_cache_path("test.bag")
            assert path.suffix == ".pkl"
            assert path.parent.name == "bag_analysis"

    def test_load_cache_nonexistent(self):
        """Test loading non-existent cache"""
        result = _load_cache(Path("nonexistent.pkl"))
        assert result is None

    def test_save_cache_basic(self):
        """Test basic cache saving"""
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            data = {'test': 'data'}
            _save_cache(tmp_path, data)
            
            # Should not raise exception
            loaded = _load_cache(tmp_path)
            assert loaded == data
        finally:
            tmp_path.unlink(missing_ok=True)


class TestInspectIntegration:
    """Integration tests for inspect command"""

    def test_inspect_file_not_found(self):
        """Test inspect command with non-existent file"""
        from roseApp.rose import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["inspect", "nonexistent.bag"])
        
        # Should fail with non-existent file
        assert result.exit_code != 0

    def test_inspect_not_a_file(self):
        """Test inspect command with directory instead of file"""
        from roseApp.rose import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["inspect", "/tmp"])
        
        # Should fail with directory instead of file
        assert result.exit_code != 0

    def test_inspect_csv_without_output(self):
        """Test inspect command with CSV format but no output file"""
        from roseApp.rose import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "csv"])
        
        # Should fail without output file for CSV format
        assert result.exit_code != 0

    def test_inspect_html_without_output(self):
        """Test inspect command with HTML format but no output file"""
        from roseApp.rose import app
        
        runner = CliRunner()
        result = runner.invoke(app, ["inspect", "tests/demo.bag", "--as", "html"])
        
        # Should fail without output file for HTML format
        assert result.exit_code != 0


if __name__ == "__main__":
    pytest.main([__file__]) 