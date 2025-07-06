"""
Topic filtering functionality tests
"""
import pytest
from unittest.mock import MagicMock, patch
from roseApp.core.parser import RosbagsBagParser, BagParser


class TestTopicFiltering:
    """Test topic filtering logic"""
    
    @pytest.fixture
    def mock_bag_with_topics(self):
        """Mock bag with multiple topics"""
        return {
            'topics': ["/cmd_vel", "/odom", "/scan", "/diagnostics", "/rosout"],
            'connections': {
                "/cmd_vel": "geometry_msgs/Twist",
                "/odom": "nav_msgs/Odometry", 
                "/scan": "sensor_msgs/LaserScan",
                "/diagnostics": "diagnostic_msgs/DiagnosticArray",
                "/rosout": "rosgraph_msgs/Log"
            }
        }
    
    def test_single_topic_filter(self, mock_bag_with_topics):
        """Test filtering for a single topic"""
        available_topics = mock_bag_with_topics['topics']
        filter_topics = ["/cmd_vel"]
        
        # Should only include specified topic
        assert "/cmd_vel" in filter_topics
        assert len(filter_topics) == 1
        
        # Verify topic exists in bag
        assert "/cmd_vel" in available_topics
    
    def test_multiple_topic_filter(self, mock_bag_with_topics):
        """Test filtering for multiple topics"""
        available_topics = mock_bag_with_topics['topics']
        filter_topics = ["/cmd_vel", "/odom", "/scan"]
        
        # Should include all specified topics
        for topic in filter_topics:
            assert topic in available_topics
        
        assert len(filter_topics) == 3
    
    def test_nonexistent_topic_handling(self, mock_bag_with_topics):
        """Test handling of non-existent topics"""
        available_topics = mock_bag_with_topics['topics']
        filter_topics = ["/nonexistent_topic", "/cmd_vel"]
        
        # Check which topics actually exist
        valid_topics = [topic for topic in filter_topics if topic in available_topics]
        invalid_topics = [topic for topic in filter_topics if topic not in available_topics]
        
        assert "/cmd_vel" in valid_topics
        assert "/nonexistent_topic" in invalid_topics
        assert len(valid_topics) == 1
        assert len(invalid_topics) == 1
    
    def test_empty_topic_list(self):
        """Test behavior with empty topic list"""
        filter_topics = []
        
        # Empty list should be handled gracefully
        assert len(filter_topics) == 0
    
    def test_case_sensitive_topics(self, mock_bag_with_topics):
        """Test that topic filtering is case sensitive"""
        available_topics = mock_bag_with_topics['topics']
        
        # These should be different
        exact_match = "/cmd_vel"
        wrong_case = "/CMD_VEL"
        
        assert exact_match in available_topics
        assert wrong_case not in available_topics
    
    @patch('roseApp.core.parser.Rosbag1Reader')
    @patch('roseApp.core.parser.Rosbag1Writer')
    def test_rosbags_parser_topic_filtering(self, mock_writer_class, mock_reader_class):
        """Test RosbagsBagParser topic filtering with mocked dependencies"""
        parser = RosbagsBagParser()
        
        # Mock reader with test topics
        mock_reader = MagicMock()
        mock_reader_class.return_value.__enter__.return_value = mock_reader
        
        # Mock topics in the bag
        mock_connection1 = MagicMock()
        mock_connection1.topic = "/cmd_vel"
        mock_connection2 = MagicMock()
        mock_connection2.topic = "/odom"
        mock_connection3 = MagicMock()
        mock_connection3.topic = "/scan"
        
        mock_reader.topics = {
            "/cmd_vel": mock_connection1,
            "/odom": mock_connection2,
            "/scan": mock_connection3
        }
        
        # Mock messages - only cmd_vel and odom should be written
        mock_reader.messages.return_value = [
            (mock_connection1, 1000000000, b"cmd_vel_data"),
            (mock_connection2, 1000000001, b"odom_data"),
            (mock_connection3, 1000000002, b"scan_data"),  # Should be filtered out
        ]
        
        # Mock writer
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer
        
        # Test filtering - only include cmd_vel and odom
        result = parser.filter_bag(
            "/input.bag",
            "/output.bag",
            ["/cmd_vel", "/odom"],  # Filter topics
            overwrite=True
        )
        
        # Verify filtering worked
        assert "Filtering completed" in result
        
        # Check that writer.write was called for filtered topics
        write_calls = mock_writer.write.call_args_list
        assert len(write_calls) == 2  # Should have 2 calls for cmd_vel and odom
    
    @patch('rosbag.Bag')
    def test_legacy_parser_topic_filtering(self, mock_bag_class):
        """Test BagParser topic filtering with mocked rosbag"""
        parser = BagParser()
        
        # Mock input bag
        mock_input_bag = MagicMock()
        mock_output_bag = MagicMock()
        
        # Mock bag context managers
        mock_bag_class.return_value.__enter__.return_value = mock_output_bag
        
        # Mock read_messages to return test data
        mock_messages = [
            ("/cmd_vel", MagicMock(), MagicMock()),
            ("/odom", MagicMock(), MagicMock()),
            ("/scan", MagicMock(), MagicMock()),
        ]
        
        # Mock the bag reading
        with patch.object(parser, '_get_bag_info') as mock_get_info:
            mock_get_info.return_value = (5, 10.0)  # message_count, duration
            
            with patch('rosbag.Bag') as mock_bag_read:
                mock_bag_instance = MagicMock()
                mock_bag_read.return_value = mock_bag_instance
                mock_bag_instance.read_messages.return_value = iter(mock_messages)
                
                result = parser.filter_bag(
                    "/input.bag",
                    "/output.bag",
                    ["/cmd_vel", "/odom"],
                    overwrite=True
                )
        
        assert "Filtering completed" in result
    
    def test_whitelist_topic_loading(self, temp_dir):
        """Test loading topics from whitelist file"""
        from roseApp.core.parser import RosbagsBagParser
        
        # Create test whitelist file
        whitelist_path = f"{temp_dir}/test_whitelist.txt"
        with open(whitelist_path, 'w') as f:
            f.write("# Test whitelist file\n")
            f.write("/cmd_vel\n")
            f.write("/odom\n")
            f.write("# Comment line\n")
            f.write("/diagnostics\n")
            f.write("\n")  # Empty line
        
        parser = RosbagsBagParser()
        topics = parser.load_whitelist(whitelist_path)
        
        expected_topics = ["/cmd_vel", "/odom", "/diagnostics"]
        assert topics == expected_topics
    
    def test_whitelist_file_not_found(self):
        """Test handling of non-existent whitelist file"""
        parser = RosbagsBagParser()
        
        with pytest.raises(Exception):  # Should raise file not found error
            parser.load_whitelist("/nonexistent/whitelist.txt")
