"""
Core parser functionality tests
"""
import pytest
import tempfile
from unittest.mock import MagicMock, patch, call
from roseApp.core.parser import RosbagsBagParser, BagParser, create_parser, ParserType, FileExistsError


class TestParserCreation:
    """Test parser factory and creation"""
    
    def test_create_rosbags_parser(self):
        """Test creating RosbagsBagParser"""
        parser = create_parser(ParserType.ROSBAGS)
        assert isinstance(parser, RosbagsBagParser)
    
    def test_create_legacy_parser(self):
        """Test creating BagParser"""
        parser = create_parser(ParserType.PYTHON)
        assert isinstance(parser, BagParser)
    
    def test_invalid_parser_type(self):
        """Test creating parser with invalid type"""
        with pytest.raises(ValueError):
            create_parser(ParserType.CPP)  # Not implemented


class TestRosbagsBagParser:
    """Test RosbagsBagParser functionality"""
    
    @pytest.fixture
    def parser(self):
        return RosbagsBagParser()
    
    def test_filter_bag_signature(self, parser):
        """Test filter_bag method signature"""
        import inspect
        sig = inspect.signature(parser.filter_bag)
        
        # Check required parameters
        expected_params = ['input_bag', 'output_bag', 'topics']
        for param in expected_params:
            assert param in sig.parameters
        
        # Check optional parameters with defaults
        assert sig.parameters['overwrite'].default == False
        assert sig.parameters['compression'].default == 'none'
    
    def test_filter_bag_overwrite_false_raises_error(self, parser, test_bag_file):
        """Test that overwrite=False raises FileExistsError when file exists"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            with pytest.raises(FileExistsError):
                parser.filter_bag(
                    test_bag_file, 
                    output_path, 
                    ["/test_topic"], 
                    overwrite=False
                )
        finally:
            import os
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    @patch('roseApp.core.parser.Rosbag1Reader')
    @patch('roseApp.core.parser.Rosbag1Writer')
    def test_filter_bag_basic_functionality(self, mock_writer_class, mock_reader_class, parser):
        """Test basic filter_bag functionality with mocked rosbags"""
        # Mock reader
        mock_reader = MagicMock()
        mock_reader_class.return_value.__enter__.return_value = mock_reader
        mock_reader.topics = {"/test_topic": MagicMock()}
        mock_reader.messages.return_value = [
            (MagicMock(topic="/test_topic"), 1000000000, b"test_data")
        ]
        
        # Mock writer
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        
        # Test filtering
        result = parser.filter_bag(
            "/input.bag",
            "/output.bag", 
            ["/test_topic"],
            overwrite=True
        )
        
        # Verify result
        assert "Filtering completed" in result
        mock_writer.write.assert_called()
    
    def test_compression_validation(self, parser):
        """Test compression parameter validation"""
        from roseApp.core.util import validate_compression_type
        
        valid_compressions = ["none", "bz2", "lz4"]
        for compression in valid_compressions:
            is_valid, _ = validate_compression_type(compression)
            assert is_valid
        
        # Test invalid compression
        is_valid, error_msg = validate_compression_type("invalid")
        assert not is_valid
        assert "invalid" in error_msg.lower()


class TestBagParser:
    """Test BagParser (legacy) functionality"""
    
    @pytest.fixture
    def parser(self):
        return BagParser()
    
    def test_filter_bag_signature(self, parser):
        """Test filter_bag method signature"""
        import inspect
        sig = inspect.signature(parser.filter_bag)
        
        # Check parameters match RosbagsBagParser
        expected_params = ['input_bag', 'output_bag', 'topics']
        for param in expected_params:
            assert param in sig.parameters
        
        assert sig.parameters['overwrite'].default == False
        assert sig.parameters['compression'].default == 'none'
    
    def test_filter_bag_overwrite_false_raises_error(self, parser, test_bag_file):
        """Test that overwrite=False raises FileExistsError when file exists"""
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            with pytest.raises(FileExistsError):
                parser.filter_bag(
                    test_bag_file,
                    output_path,
                    ["/test_topic"],
                    overwrite=False
                )
        finally:
            import os
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestFileExistsError:
    """Test custom FileExistsError exception"""
    
    def test_exception_creation(self):
        """Test FileExistsError can be created and raised"""
        with pytest.raises(FileExistsError) as exc_info:
            raise FileExistsError("Test error message")
        
        assert str(exc_info.value) == "Test error message"
    
    def test_exception_inheritance(self):
        """Test FileExistsError inherits from Exception"""
        assert issubclass(FileExistsError, Exception)
