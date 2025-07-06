"""
Compression functionality tests
"""
import pytest
from unittest.mock import MagicMock, patch
from roseApp.core.parser import RosbagsBagParser, BagParser
from roseApp.core.util import validate_compression_type, get_available_compression_types


class TestCompressionValidation:
    """Test compression type validation"""
    
    def test_valid_compression_types(self):
        """Test validation of valid compression types"""
        valid_types = ["none", "bz2", "lz4"]
        
        for compression_type in valid_types:
            is_valid, error_msg = validate_compression_type(compression_type)
            assert is_valid
            assert error_msg == ""
    
    def test_invalid_compression_types(self):
        """Test validation of invalid compression types"""
        invalid_types = ["gzip", "zip", "rar", "invalid", ""]
        
        for compression_type in invalid_types:
            is_valid, error_msg = validate_compression_type(compression_type)
            assert not is_valid
            assert len(error_msg) > 0
    
    def test_case_insensitive_validation(self):
        """Test that compression validation is case insensitive"""
        test_cases = [
            ("NONE", True),
            ("BZ2", True), 
            ("LZ4", True),
            ("None", True),
            ("Bz2", True),
            ("Lz4", True),
            ("INVALID", False)
        ]
        
        for compression_type, expected_valid in test_cases:
            is_valid, _ = validate_compression_type(compression_type)
            assert is_valid == expected_valid


class TestCompressionAvailability:
    """Test compression availability detection"""
    
    def test_get_available_compression_types(self):
        """Test getting available compression types"""
        available = get_available_compression_types()
        
        # 'none' should always be available
        assert "none" in available
        assert isinstance(available, dict)
        
        # Check that bz2 and lz4 have boolean values
        assert isinstance(available.get("bz2", False), bool)
        assert isinstance(available.get("lz4", False), bool)
    
    @patch('roseApp.core.util.importlib.util.find_spec')
    def test_compression_availability_with_missing_deps(self, mock_find_spec):
        """Test compression availability when dependencies are missing"""
        # Mock rosbags as not available
        mock_find_spec.return_value = None
        
        # Should fall back to testing with legacy rosbag
        available = get_available_compression_types()
        assert "none" in available


class TestRosbagsParserCompression:
    """Test RosbagsBagParser compression functionality"""
    
    @pytest.fixture
    def parser(self):
        return RosbagsBagParser()
    
    def test_compression_format_conversion(self, parser):
        """Test compression format conversion"""
        # Test internal conversion method
        assert parser._convert_compression_format("none") == "none"
        assert parser._convert_compression_format("bz2") == "bz2" 
        assert parser._convert_compression_format("lz4") == "lz4"
        
        # Test unknown compression defaults to none
        assert parser._convert_compression_format("unknown") == "none"
    
    @patch('roseApp.core.parser.Rosbag1Writer')
    def test_compression_format_enum(self, mock_writer_class, parser):
        """Test getting rosbags compression format enum"""
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        
        # Test that compression format methods exist
        assert hasattr(parser, '_get_compression_format')
        
        # Test with different compression types
        for compression in ["none", "bz2", "lz4"]:
            format_enum = parser._get_compression_format(compression)
            # Should return None for 'none', or proper enum for others
            if compression == "none":
                assert format_enum is None
            # Note: Actual enum testing would require rosbags to be available
    
    @patch('roseApp.core.parser.Rosbag1Reader')
    @patch('roseApp.core.parser.Rosbag1Writer')
    def test_filter_bag_with_compression(self, mock_writer_class, mock_reader_class, parser):
        """Test filter_bag with different compression types"""
        # Mock reader
        mock_reader = MagicMock()
        mock_reader_class.return_value.__enter__.return_value = mock_reader
        mock_reader.topics = {"/test_topic": MagicMock()}
        mock_reader.messages.return_value = []
        
        # Mock writer
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        
        # Test with different compression types
        for compression in ["none", "bz2", "lz4"]:
            result = parser.filter_bag(
                "/input.bag",
                "/output.bag",
                ["/test_topic"],
                compression=compression,
                overwrite=True
            )
            
            assert "Filtering completed" in result
            
            # Verify writer was called
            mock_writer_class.assert_called()
            
            # If compression is not 'none', set_compression should be called
            if compression != "none":
                # Note: This would need proper mocking of rosbags enums
                pass


class TestLegacyParserCompression:
    """Test BagParser compression functionality"""
    
    @pytest.fixture  
    def parser(self):
        return BagParser()
    
    @patch('rosbag.Bag')
    def test_legacy_compression_support(self, mock_bag_class, parser):
        """Test that legacy parser supports compression parameter"""
        mock_input_bag = MagicMock()
        mock_output_bag = MagicMock()
        
        # Mock bag creation with compression
        mock_bag_class.return_value.__enter__.return_value = mock_output_bag
        
        with patch.object(parser, '_get_bag_info') as mock_get_info:
            mock_get_info.return_value = (0, 0.0)
            
            with patch('rosbag.Bag') as mock_bag_read:
                mock_bag_instance = MagicMock()
                mock_bag_read.return_value = mock_bag_instance
                mock_bag_instance.read_messages.return_value = iter([])
                
                # Test that compression parameter is passed to rosbag.Bag
                result = parser.filter_bag(
                    "/input.bag",
                    "/output.bag", 
                    ["/test_topic"],
                    compression="bz2",
                    overwrite=True
                )
        
        assert "Filtering completed" in result
        
        # Verify that Bag was called with compression parameter
        # The exact call depends on implementation details
        mock_bag_class.assert_called()
    
    def test_compression_validation_in_filter(self, parser):
        """Test compression validation in filter_bag method"""
        # Invalid compression should raise ValueError
        with pytest.raises(ValueError, match="Invalid compression type"):
            parser.filter_bag(
                "/input.bag",
                "/output.bag",
                ["/test_topic"], 
                compression="invalid_compression"
            )


class TestCompressionIntegration:
    """Test compression integration across components"""
    
    def test_compression_parameter_flow(self):
        """Test that compression parameter flows correctly through system"""
        # This tests the integration between validation, parser, and actual compression
        
        # Test valid flow
        compression = "lz4"
        is_valid, _ = validate_compression_type(compression)
        assert is_valid
        
        # Test that both parsers accept the parameter
        rosbags_parser = RosbagsBagParser()
        legacy_parser = BagParser()
        
        import inspect
        
        # Check method signatures include compression parameter
        rosbags_sig = inspect.signature(rosbags_parser.filter_bag)
        legacy_sig = inspect.signature(legacy_parser.filter_bag)
        
        assert 'compression' in rosbags_sig.parameters
        assert 'compression' in legacy_sig.parameters
        
        # Check default values
        assert rosbags_sig.parameters['compression'].default == 'none'
        assert legacy_sig.parameters['compression'].default == 'none'
    
    def test_compression_error_handling(self):
        """Test error handling for compression issues"""
        # Test that validation catches errors before they reach parsers
        invalid_compression = "nonexistent"
        
        is_valid, error_msg = validate_compression_type(invalid_compression)
        assert not is_valid
        assert "Invalid compression type" in error_msg
        
        # Test that parsers handle validation errors appropriately
        for parser_class in [RosbagsBagParser, BagParser]:
            parser = parser_class()
            
            with pytest.raises(ValueError):
                parser.filter_bag(
                    "/input.bag",
                    "/output.bag",
                    ["/test_topic"],
                    compression=invalid_compression
                )
