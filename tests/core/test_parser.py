"""
Core parser functionality tests using real demo.bag file
"""
import pytest
import os
import tempfile
import shutil
from roseApp.core.parser import RosbagsBagParser, create_parser, ParserType
from rosbags.rosbag1 import Reader


class TestParserCore:
    """Test core parser functionality"""
    
    @pytest.fixture
    def demo_bag_path(self):
        """Path to the demo bag file"""
        return "tests/demo.bag"
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary directory for output files"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_demo_bag_exists(self, demo_bag_path):
        """Test that demo.bag file exists and is readable"""
        assert os.path.exists(demo_bag_path)
        assert os.path.isfile(demo_bag_path)
        assert os.path.getsize(demo_bag_path) > 0
    
    def test_parser_creation(self):
        """Test parser creation"""
        parser = create_parser(ParserType.ROSBAGS)
        assert isinstance(parser, RosbagsBagParser)
    
    def test_bag_content_analysis(self, demo_bag_path):
        """Test analyzing demo.bag content"""
        with Reader(demo_bag_path) as reader:
            assert reader.message_count > 0
            assert reader.duration > 0
            assert len(reader.connections) > 0
            
            # Check for expected topics
            topics = [conn.topic for conn in reader.connections]
            expected_topics = ["/tf", "/image_raw", "/gps/fix"]
            
            for topic in expected_topics:
                assert topic in topics, f"Expected topic {topic} not found"
    
    def test_single_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering a single topic"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered.bag")
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf"],
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains only /tf topic
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == 1
            assert "/tf" in topics
    
    def test_multiple_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering multiple topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "multi_filtered.bag")
        
        filter_topics = ["/tf", "/gps/fix"]
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            filter_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains requested topics
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == len(filter_topics)
            for topic in filter_topics:
                assert topic in topics
    
    def test_compression_basic(self, demo_bag_path, temp_output_dir):
        """Test basic compression functionality"""
        parser = RosbagsBagParser()
        
        # Test none compression
        output_path = os.path.join(temp_output_dir, "compressed_none.bag")
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf"],
            overwrite=True,
            compression="none"
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
    
    def test_whitelist_loading(self):
        """Test loading topics from whitelist file"""
        parser = RosbagsBagParser()
        whitelist_path = "tests/fixtures/test_whitelist.txt"
        
        topics = parser.load_whitelist(whitelist_path)
        
        assert isinstance(topics, list)
        assert len(topics) > 0
        assert "/tf" in topics
        assert "/gps/fix" in topics
    
    def test_nonexistent_topic(self, demo_bag_path, temp_output_dir):
        """Test filtering non-existent topic"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "nonexistent.bag")
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/nonexistent_topic"],
            overwrite=True
        )
        
        # Should complete but with no messages
        assert "No messages found" in result or "completed" in result.lower()
    
    def test_invalid_input_path(self, temp_output_dir):
        """Test error handling for invalid input path"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "output.bag")
        
        with pytest.raises(Exception):
            parser.filter_bag(
                "/nonexistent/path.bag",
                output_path,
                ["/tf"],
                overwrite=True
            )
    
    def test_file_overwrite_protection(self, demo_bag_path, temp_output_dir):
        """Test file overwrite protection"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "existing.bag")
        
        # Create existing file
        with open(output_path, 'w') as f:
            f.write("existing content")
        
        # Should raise error with overwrite=False
        with pytest.raises(Exception):
            parser.filter_bag(
                demo_bag_path,
                output_path,
                ["/tf"],
                overwrite=False
            ) 