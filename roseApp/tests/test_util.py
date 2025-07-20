"""
Test cases for util module
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from roseApp.core.util import (
    TimeUtil, get_logger, setup_logging, log_cli_error,
    check_compression_availability, get_available_compression_types,
    validate_compression_type, get_preferred_parser_type
)


class TestTimeUtil:
    """Test cases for TimeUtil class"""
    
    def test_to_datetime_valid(self):
        """Test converting time tuple to datetime string"""
        result = TimeUtil.to_datetime((123456789, 123456789))
        assert "09/02/73 03:46:29" in result
    
    def test_to_datetime_invalid(self):
        """Test handling invalid time tuple"""
        assert TimeUtil.to_datetime(None) == "N.A"
        assert TimeUtil.to_datetime((123456789,)) == "N.A"
        assert TimeUtil.to_datetime(()) == "N.A"
    
    def test_from_datetime_valid(self):
        """Test converting datetime string to time tuple"""
        result = TimeUtil.from_datetime("09/02/73 03:46:29")
        assert result == (123456789, 0)
    
    def test_from_datetime_invalid(self):
        """Test handling invalid datetime string"""
        with pytest.raises(ValueError, match="Invalid time format"):
            TimeUtil.from_datetime("invalid format")
    
    def test_convert_time_range_to_tuple(self):
        """Test converting time range strings to tuple"""
        result = TimeUtil.convert_time_range_to_tuple(
            "09/02/73 03:46:29", 
            "09/02/73 03:46:30"
        )
        
        assert len(result) == 2
        start, end = result
        assert start[0] == 123456788  # Adjusted by -1
        assert end[0] == 123456791   # Adjusted by +1
    
    def test_convert_time_range_invalid(self):
        """Test handling invalid time range"""
        with pytest.raises(ValueError, match="Invalid time range format"):
            TimeUtil.convert_time_range_to_tuple("invalid", "09/02/73 03:46:30")


class TestLogging:
    """Test cases for logging functionality"""
    
    def test_get_logger_creation(self):
        """Test logger creation"""
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name.endswith("test_module")
    
    def test_setup_logging(self):
        """Test setup logging (backward compatibility)"""
        logger = setup_logging()
        assert logger is not None
    
    def test_log_cli_error(self):
        """Test CLI error logging"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            result = log_cli_error(e)
            assert "Test error" in result
            assert "Error:" in result


class TestCompression:
    """Test cases for compression utilities"""
    
    @patch('rosbags.rosbag1.Writer')
    def test_check_compression_availability(self, mock_writer):
        """Test checking compression availability"""
        mock_writer.CompressionFormat.LZ4 = "LZ4"
        
        with patch('tempfile.TemporaryDirectory') as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = "/tmp"
            
            # Mock successful LZ4 test
            with patch('pathlib.Path') as mock_path:
                mock_path.return_value = Mock()
                
                availability = check_compression_availability()
                
                assert "none" in availability
                assert "bz2" in availability
                assert "lz4" in availability
                assert availability["none"] is True
                assert availability["bz2"] is True
    
    def test_get_available_compression_types(self):
        """Test getting available compression types"""
        with patch('roseApp.core.util.check_compression_availability') as mock_check:
            mock_check.return_value = {
                'none': True,
                'bz2': True,
                'lz4': False
            }
            
            available = get_available_compression_types()
            assert "none" in available
            assert "bz2" in available
            assert "lz4" not in available
    
    def test_validate_compression_type_valid(self):
        """Test validating valid compression types"""
        with patch('roseApp.core.util.get_available_compression_types') as mock_get:
            mock_get.return_value = ['none', 'bz2', 'lz4']
            
            valid, error = validate_compression_type('bz2')
            assert valid is True
            assert error == ""
    
    def test_validate_compression_type_invalid(self):
        """Test validating invalid compression type"""
        with patch('roseApp.core.util.get_available_compression_types') as mock_get:
            mock_get.return_value = ['none', 'bz2']
            
            valid, error = validate_compression_type('invalid')
            assert valid is False
            assert "Invalid compression type" in error
    
    def test_validate_compression_type_lz4_unavailable(self):
        """Test validating LZ4 when unavailable"""
        with patch('roseApp.core.util.get_available_compression_types') as mock_get:
            mock_get.return_value = ['none', 'bz2']
            
            valid, error = validate_compression_type('lz4')
            assert valid is False
            assert "LZ4 compression is not available" in error
    
    def test_get_preferred_parser_type(self):
        """Test getting preferred parser type"""
        parser_type = get_preferred_parser_type()
        assert parser_type == 'rosbags'