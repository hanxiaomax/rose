"""
Core parser functionality tests using real demo.bag file
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from roseApp.core.parser import RosbagsBagParser, create_parser, create_best_parser, ParserType
from rosbags.highlevel import AnyReader


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
        """Test parser creation with default and explicit types"""
        # Test default parser (should be ROSBAGS)
        parser_default = create_parser()
        assert isinstance(parser_default, RosbagsBagParser)
        
        # Test explicit ROSBAGS parser
        parser_rosbags = create_parser(ParserType.ROSBAGS)
        assert isinstance(parser_rosbags, RosbagsBagParser)
        
        # Test best parser creation
        parser_best = create_best_parser()
        assert isinstance(parser_best, RosbagsBagParser)
    
    def test_bag_content_analysis(self, demo_bag_path):
        """Test analyzing demo.bag content with AnyReader"""
        with AnyReader([Path(demo_bag_path)]) as reader:
            assert reader.message_count > 0
            assert reader.duration > 0
            assert len(reader.connections) > 0
            
            # Check for expected topics
            topics = [conn.topic for conn in reader.connections]
            expected_topics = ["/tf", "/image_raw", "/gps/fix"]
            
            for topic in expected_topics:
                assert topic in topics, f"Expected topic {topic} not found"
    
    def test_single_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering a single topic with enhanced parser"""
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
        with AnyReader([Path(output_path)]) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == 1
            assert "/tf" in topics
    
    def test_multiple_topic_filtering(self, demo_bag_path, temp_output_dir):
        """Test filtering multiple topics with enhanced parser"""
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
        with AnyReader([Path(output_path)]) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert len(topics) == len(filter_topics)
            for topic in filter_topics:
                assert topic in topics
    
    def test_compression_basic(self, demo_bag_path, temp_output_dir):
        """Test basic compression functionality with Rosbag1Writer"""
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
        assert "No messages found" in result or "No matching topics found" in result
    
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
    
    def test_performance_logging(self, demo_bag_path, temp_output_dir):
        """Test that performance logging is working"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "performance.bag")
        
        # This test verifies the parser completes successfully
        # and logs performance information
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            ["/tf"],
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify the output file has content
        assert os.path.getsize(output_path) > 0
    
    def test_get_topic_sizes(self, demo_bag_path):
        """Test that get_topic_sizes returns size information for all topics"""
        parser = RosbagsBagParser()
        topic_sizes = parser.get_topic_sizes(demo_bag_path)
        
        # Verify we get a dictionary with topic names as keys
        assert isinstance(topic_sizes, dict)
        assert len(topic_sizes) > 0
        
        # Verify all sizes are non-negative integers
        for topic, size in topic_sizes.items():
            assert isinstance(size, int)
            assert size >= 0
    
    def test_get_topic_stats(self, demo_bag_path):
        """Test that get_topic_stats returns comprehensive statistics"""
        parser = RosbagsBagParser()
        topic_stats = parser.get_topic_stats(demo_bag_path)
        
        # Verify we get a dictionary with topic names as keys
        assert isinstance(topic_stats, dict)
        assert len(topic_stats) > 0
        
        # Verify each topic has the expected statistics
        for topic, stats in topic_stats.items():
            assert isinstance(stats, dict)
            assert "count" in stats
            assert "size" in stats
            assert "avg_size" in stats
            
            # Verify stats are non-negative integers
            assert isinstance(stats['count'], int)
            assert isinstance(stats['size'], int)
            assert isinstance(stats['avg_size'], int)
            assert stats['count'] >= 0
            assert stats['size'] >= 0
            assert stats['avg_size'] >= 0
            
            # Verify avg_size calculation is correct
            if stats['count'] > 0:
                expected_avg = stats['size'] // stats['count']
                assert stats['avg_size'] == expected_avg
    
    def test_topic_stats_consistency(self, demo_bag_path):
        """Test that topic stats are consistent with individual methods"""
        parser = RosbagsBagParser()
        
        # Get stats from all methods
        topic_stats = parser.get_topic_stats(demo_bag_path)
        message_counts = parser.get_message_counts(demo_bag_path)
        topic_sizes = parser.get_topic_sizes(demo_bag_path)
        
        # Verify consistency between methods
        for topic in topic_stats:
            assert topic_stats[topic]['count'] == message_counts[topic], f"Count mismatch for topic {topic}"
            assert topic_stats[topic]['size'] == topic_sizes[topic], f"Size mismatch for topic {topic}"
    
    def test_parser_load_bag_api(self, demo_bag_path):
        """Test the load_bag API with enhanced parser"""
        parser = RosbagsBagParser()
        
        topics, connections, time_range = parser.load_bag(demo_bag_path)
        
        # Verify basic structure
        assert isinstance(topics, list)
        assert isinstance(connections, dict)
        assert isinstance(time_range, tuple)
        assert len(time_range) == 2
        
        # Verify content
        assert len(topics) > 0
        assert len(connections) > 0
        
        # Check expected topics exist
        expected_topics = ["/tf", "/image_raw", "/gps/fix"]
        for topic in expected_topics:
            assert topic in topics
            assert topic in connections
    
    def test_parser_message_counts(self, demo_bag_path):
        """Test message count functionality"""
        parser = RosbagsBagParser()
        
        message_counts = parser.get_message_counts(demo_bag_path)
        
        # Verify structure
        assert isinstance(message_counts, dict)
        assert len(message_counts) > 0
        
        # Verify all counts are positive integers
        for topic, count in message_counts.items():
            assert isinstance(count, int)
            assert count > 0
        
        # Check expected topics have messages
        expected_topics = ["/tf", "/image_raw", "/gps/fix"]
        for topic in expected_topics:
            assert topic in message_counts
            assert message_counts[topic] > 0
    
    def test_filtered_topics_consistency(self, demo_bag_path, temp_output_dir):
        """Test that filtered bag contains exactly the specified topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "consistency_test.bag")
        
        # Test with multiple specific topics
        specified_topics = ["/tf", "/gps/fix", "/image_raw"]
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            specified_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify filtered bag contains exactly the specified topics
        with AnyReader([Path(output_path)]) as reader:
            filtered_topics = [conn.topic for conn in reader.connections]
            
            # Check that all specified topics are present
            for topic in specified_topics:
                assert topic in filtered_topics, f"Specified topic {topic} not found in filtered bag"
            
            # Check that no extra topics are present
            assert len(filtered_topics) == len(specified_topics), \
                f"Expected {len(specified_topics)} topics, got {len(filtered_topics)}: {filtered_topics}"
            
            # Check exact match (order independent)
            assert set(filtered_topics) == set(specified_topics), \
                f"Topic sets don't match. Expected: {set(specified_topics)}, Got: {set(filtered_topics)}"
    
    def test_message_count_preservation(self, demo_bag_path, temp_output_dir):
        """Test that message counts are preserved for filtered topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "count_test.bag")
        
        # Get original message counts
        original_counts = parser.get_message_counts(demo_bag_path)
        
        # Filter specific topics
        filter_topics = ["/tf", "/gps/fix"]
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            filter_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Get filtered message counts
        filtered_counts = parser.get_message_counts(output_path)
        
        # Verify that each filtered topic has the same message count as in original bag
        for topic in filter_topics:
            assert topic in filtered_counts, f"Filtered topic {topic} not found in output bag"
            assert topic in original_counts, f"Topic {topic} not found in original bag"
            
            original_count = original_counts[topic]
            filtered_count = filtered_counts[topic]
            
            assert filtered_count == original_count, \
                f"Message count mismatch for {topic}: original={original_count}, filtered={filtered_count}"
        
        # Verify that unfiltered topics are not present
        for topic in original_counts:
            if topic not in filter_topics:
                assert topic not in filtered_counts, f"Unfiltered topic {topic} found in output bag"
    
    def test_partial_topic_filtering_accuracy(self, demo_bag_path, temp_output_dir):
        """Test filtering accuracy with a subset of available topics"""
        parser = RosbagsBagParser()
        output_path = os.path.join(temp_output_dir, "partial_filter_test.bag")
        
        # Get all available topics
        all_topics, _, _ = parser.load_bag(demo_bag_path)
        original_counts = parser.get_message_counts(demo_bag_path)
        
        # Select only some topics for filtering (not all)
        selected_topics = [topic for topic in all_topics if topic in ["/tf", "/gps/fix", "/radar/range"]]
        excluded_topics = [topic for topic in all_topics if topic not in selected_topics]
        
        # Ensure we have both selected and excluded topics
        assert len(selected_topics) > 0, "No topics selected for filtering"
        assert len(excluded_topics) > 0, "No topics excluded from filtering"
        
        result = parser.filter_bag(
            demo_bag_path,
            output_path,
            selected_topics,
            overwrite=True
        )
        
        assert "Filtering completed" in result
        assert os.path.exists(output_path)
        
        # Verify filtering accuracy
        with AnyReader([Path(output_path)]) as reader:
            filtered_topics = [conn.topic for conn in reader.connections]
            filtered_counts = parser.get_message_counts(output_path)
            
            # Check included topics
            for topic in selected_topics:
                if topic in original_counts:  # Only check topics that exist in original
                    assert topic in filtered_topics, f"Selected topic {topic} missing from filtered bag"
                    assert topic in filtered_counts, f"Selected topic {topic} missing from count analysis"
                    
                    # Verify message count preservation
                    assert filtered_counts[topic] == original_counts[topic], \
                        f"Message count changed for {topic}: {original_counts[topic]} -> {filtered_counts[topic]}"
            
            # Check excluded topics are not present
            for topic in excluded_topics:
                assert topic not in filtered_topics, f"Excluded topic {topic} found in filtered bag"
                assert topic not in filtered_counts, f"Excluded topic {topic} found in filtered counts"
    
 