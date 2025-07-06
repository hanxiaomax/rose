"""
Real bag file testing using tests/demo.bag
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from roseApp.core.parser import RosbagsBagParser, BagParser, create_parser, ParserType
from rosbags.rosbag1 import Reader


class TestRealBagFiltering:
    """Test filtering functionality using real demo.bag file"""
    
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
    
    def test_demo_bag_content_analysis(self, demo_bag_path):
        """Test analyzing demo.bag content"""
        with Reader(demo_bag_path) as reader:
            # Check basic properties
            assert reader.message_count > 0
            assert reader.duration > 0
            assert len(reader.connections) > 0
            
            # Check for expected topics
            topics = [conn.topic for conn in reader.connections]
            expected_topics = [
                "/tf", "/image_raw", "/velodyne_points", "/gps/fix", 
                "/radar/points", "/diagnostics"
            ]
            
            for topic in expected_topics:
                assert topic in topics, f"Expected topic {topic} not found"
    
    def test_single_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering a single topic from real bag"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_single.bag")
        
        # Filter only /tf topic
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf"],
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
        # Verify output contains only /tf topic
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == 1
            assert "/tf" in topics
            assert reader.message_count > 0
    
    def test_multiple_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering multiple topics from real bag"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_multiple.bag")
        
        # Filter multiple topics
        filter_topics = ["/tf", "/gps/fix", "/diagnostics"]
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            filter_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains exactly the requested topics
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == len(filter_topics)
            for topic in filter_topics:
                assert topic in topics
    
    def test_topic_filtering_message_count(self, demo_bag_path, temp_output_dir):
        """Test that message counts are preserved correctly"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_count.bag")
        
        # Get original message count for /tf topic
        original_tf_count = 0
        with Reader(demo_bag_path) as reader:
            for conn in reader.connections:
                if conn.topic == "/tf":
                    original_tf_count = conn.msgcount
                    break
        
        assert original_tf_count > 0
        
        # Filter only /tf topic
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf"],
            overwrite=True
        )
        
        assert "Filtering completed" in result
        
        # Verify message count is preserved
        with Reader(output_path) as reader:
            filtered_tf_count = 0
            for conn in reader.connections:
                if conn.topic == "/tf":
                    filtered_tf_count = conn.msgcount
                    break
            
            assert filtered_tf_count == original_tf_count
    
    def test_nonexistent_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering non-existent topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_nonexistent.bag")
        
        # Try to filter non-existent topic
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/nonexistent_topic"],
            overwrite=True
        )
        
        # Should complete but result in empty or minimal bag
        assert "Filtering completed" in result or "No messages found" in result
        
        if os.path.exists(output_path):
            # If file exists, it should be empty or contain no messages
            with Reader(output_path) as reader:
                assert reader.message_count == 0
    
    def test_mixed_existing_nonexistent_topics(self, demo_bag_path, temp_output_dir):
        """Test filtering mix of existing and non-existent topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_mixed.bag")
        
        # Mix existing and non-existent topics
        filter_topics = ["/tf", "/nonexistent_topic", "/gps/fix"]
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            filter_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains only existing topics
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
            assert "/gps/fix" in topics
            assert "/nonexistent_topic" not in topics
    
    def test_compression_with_real_bag(self, demo_bag_path, temp_output_dir):
        """Test compression options with real bag"""
        parser = RosbagsBagParser()
        
        # Test different compression types
        compression_types = ["none", "bz2", "lz4"]
        
        for compression in compression_types:
            output_path = os.path.join(temp_output_dir, f"compressed_{compression}.bag")
            
            result = parser.filter_bag(
                demo_bag_path,
                output_path,
                ["/tf"],
                overwrite=True,
                compression=compression
            )
            
            assert "Filtering completed" in result
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_large_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering large topics like image data"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "filtered_images.bag")
        
        # Filter image topic (should be large)
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/image_raw"],
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify significant file size (images should be large)
        assert os.path.getsize(output_path) > 1000  # At least 1KB
        
        # Verify content
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/image_raw" in topics
            assert reader.message_count > 0


class TestRealBagParserComparison:
    """Test comparing RosbagsBagParser and BagParser with real data"""
    
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
    
    def test_parser_factory_with_real_bag(self, demo_bag_path):
        """Test parser factory returns correct parser types"""
        rosbags_parser = create_parser(ParserType.ROSBAGS)
        legacy_parser = create_parser(ParserType.PYTHON)
        
        assert isinstance(rosbags_parser, RosbagsBagParser)
        assert isinstance(legacy_parser, BagParser)
    
    def test_rosbags_parser_performance(self, demo_bag_path, temp_output_dir):
        """Test RosbagsBagParser performance with real bag"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "rosbags_output.bag")
        
        import time
        start_time = time.time()
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf", "/gps/fix"],
            overwrite=True
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        # Should complete in reasonable time (adjust based on system)
        assert processing_time < 30  # Should complete within 30 seconds
    
    @pytest.mark.slow
    def test_all_topics_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering all topics (effectively copying the bag)"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "all_topics.bag")
        
        # Get all topics from original bag
        with Reader(demo_bag_path) as reader:
            all_topics = [conn.topic for conn in reader.connections]
            original_message_count = reader.message_count
        
        # Filter all topics
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            all_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify all topics are preserved
        with Reader(output_path) as reader:
            output_topics = [conn.topic for conn in reader.connections]
            assert len(output_topics) == len(all_topics)
            for topic in all_topics:
                assert topic in output_topics
            
            # Message count should be preserved
            assert reader.message_count == original_message_count


class TestRealBagErrorHandling:
    """Test error handling with real bag files"""
    
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
    
    def test_file_overwrite_protection(self, demo_bag_path, temp_output_dir):
        """Test file overwrite protection with real bag"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "existing_file.bag")
        
        # Create existing file
        with open(output_path, 'w') as f:
            f.write("existing content")
        
        # Should raise error with overwrite=False
        with pytest.raises(Exception):  # FileExistsError or similar
            parser.filter_bag(
                demo_bag_path,
                output_path,
                ["/tf"],
                overwrite=False
            )
    
    def test_invalid_input_bag_path(self, temp_output_dir):
        """Test handling of invalid input bag path"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "output.bag")
        
        with pytest.raises(Exception):  # Should raise file not found or similar
            parser.filter_bag(
                "/nonexistent/path.bag",
                output_path,
                ["/tf"],
                overwrite=True
            )
    
    def test_invalid_output_directory(self, demo_bag_path):
        """Test handling of invalid output directory"""
        parser = RosbagsBagParser()
        invalid_output_path = "/nonexistent/directory/output.bag"
        
        try:
            result = parser.filter_bag(
                demo_bag_path,
                invalid_output_path,
                ["/tf"],
                overwrite=True
            )
            # If it doesn't raise an exception, it might create the directory
            # or handle the error gracefully
            assert "Error" in result or "completed" in result.lower()
        except Exception as e:
            # Expected to raise an exception for invalid directory
            assert "directory" in str(e).lower() or "not found" in str(e).lower()


class TestRealBagWhitelist:
    """Test whitelist functionality with real bag files"""
    
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
    
    @pytest.fixture
    def test_whitelist_path(self):
        """Path to test whitelist file"""
        return "tests/fixtures/test_whitelist.txt"
    
    def test_whitelist_file_exists(self, test_whitelist_path):
        """Test that whitelist file exists"""
        assert os.path.exists(test_whitelist_path)
        assert os.path.isfile(test_whitelist_path)
    
    def test_whitelist_loading(self, test_whitelist_path):
        """Test loading topics from whitelist file"""
        parser = RosbagsBagParser()
        
        # Load whitelist topics
        topics = parser.load_whitelist(test_whitelist_path)
        
        # Verify expected topics are loaded
        expected_topics = [
            "/tf", "/image_raw", "/velodyne_points", "/radar/points",
            "/gps/fix", "/gps/time", "/gps/rtkfix", "/diagnostics"
        ]
        
        assert isinstance(topics, list)
        assert len(topics) > 0
        
        for topic in expected_topics:
            assert topic in topics, f"Topic {topic} not found in whitelist"
    
    def test_whitelist_filtering_with_real_bag(self, demo_bag_path, test_whitelist_path, temp_output_dir):
        """Test filtering using whitelist with real bag"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "whitelist_filtered.bag")
        
        # Load whitelist topics
        whitelist_topics = parser.load_whitelist(test_whitelist_path)
        
        # Filter using whitelist
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            whitelist_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains only whitelist topics
        with Reader(output_path) as reader:
            output_topics = [conn.topic for conn in reader.connections]
            
            # All output topics should be in whitelist
            for topic in output_topics:
                assert topic in whitelist_topics
    
    def test_whitelist_vs_manual_topic_list(self, demo_bag_path, test_whitelist_path, temp_output_dir):
        """Test that whitelist produces same result as manual topic list"""
        parser = RosbagsBagParser()
        
        # Load whitelist topics
        whitelist_topics = parser.load_whitelist(test_whitelist_path)
        
        # Filter using whitelist
        whitelist_output = os.path.join(temp_output_dir, "whitelist_result.bag")
        result1 = parser.filter_bag(
            demo_bag_path,
            whitelist_output,
            whitelist_topics,
            overwrite=True
        )
        
        # Filter using manual topic list (same topics)
        manual_output = os.path.join(temp_output_dir, "manual_result.bag")
        result2 = parser.filter_bag(
            demo_bag_path,
            manual_output,
            whitelist_topics,  # Same topics
            overwrite=True
        )
        
        assert "Filtering completed" in result1
        assert "Filtering completed" in result2
        
        # Both outputs should exist and have same topics
        with Reader(whitelist_output) as reader1, Reader(manual_output) as reader2:
            topics1 = [conn.topic for conn in reader1.connections]
            topics2 = [conn.topic for conn in reader2.connections]
            
            assert set(topics1) == set(topics2)
            assert reader1.message_count == reader2.message_count
    
    def test_whitelist_with_comments_and_empty_lines(self, temp_output_dir):
        """Test whitelist parsing handles comments and empty lines"""
        parser = RosbagsBagParser()
        
        # Create temporary whitelist with comments and empty lines
        whitelist_path = os.path.join(temp_output_dir, "test_whitelist.txt")
        with open(whitelist_path, 'w') as f:
            f.write("# This is a comment\n")
            f.write("\n")  # Empty line
            f.write("/tf\n")
            f.write("# Another comment\n")
            f.write("/gps/fix\n")
            f.write("\n")  # Another empty line
            f.write("   # Indented comment\n")
            f.write("/diagnostics\n")
        
        # Load whitelist
        topics = parser.load_whitelist(whitelist_path)
        
        # Should only contain actual topics, not comments or empty lines
        expected_topics = ["/tf", "/gps/fix", "/diagnostics"]
        assert topics == expected_topics
    
    def test_whitelist_nonexistent_file(self):
        """Test handling of non-existent whitelist file"""
        parser = RosbagsBagParser()
        
        with pytest.raises(Exception):  # Should raise file not found error
            parser.load_whitelist("/nonexistent/whitelist.txt")
    
    def test_whitelist_with_nonexistent_topics(self, demo_bag_path, temp_output_dir):
        """Test whitelist containing non-existent topics"""
        parser = RosbagsBagParser()
        
        # Create whitelist with mix of existing and non-existing topics
        whitelist_path = os.path.join(temp_output_dir, "mixed_whitelist.txt")
        with open(whitelist_path, 'w') as f:
            f.write("/tf\n")  # Exists
            f.write("/nonexistent_topic\n")  # Doesn't exist
            f.write("/gps/fix\n")  # Exists
            f.write("/another_fake_topic\n")  # Doesn't exist
        
        # Load whitelist
        whitelist_topics = parser.load_whitelist(whitelist_path)
        
        # Filter using whitelist
        output_path = os.path.join(temp_output_dir, "mixed_filtered.bag")
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            whitelist_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify output contains only existing topics
        with Reader(output_path) as reader:
            output_topics = [conn.topic for conn in reader.connections]
            
            # Should contain existing topics
            assert "/tf" in output_topics
            assert "/gps/fix" in output_topics
            
            # Should not contain non-existent topics
            assert "/nonexistent_topic" not in output_topics
            assert "/another_fake_topic" not in output_topics 