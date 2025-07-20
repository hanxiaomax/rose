"""
Test cases for parser module
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch

from roseApp.core.parser import (
    ParserType, ParserHealth, IBagParser,
    RosbagsBagParser, LegacyBagParser, ParserHealthChecker,
    create_parser, create_best_parser, get_parser_health,
    get_all_parser_health, check_parser_availability,
    FileExistsError
)


class TestParserType:
    """Test cases for ParserType enum"""
    
    def test_parser_type_values(self):
        """Test parser type enum values"""
        assert ParserType.ROSBAGS.value == "rosbags"
        assert ParserType.LEGACY.value == "legacy"


class TestParserHealth:
    """Test cases for ParserHealth class"""
    
    def test_parser_health_creation(self):
        """Test basic ParserHealth creation"""
        health = ParserHealth(
            parser_type=ParserType.ROSBAGS,
            available=True,
            version="1.0.0",
            performance_score=100.0
        )
        
        assert health.parser_type == ParserType.ROSBAGS
        assert health.available
        assert health.version == "1.0.0"
        assert health.performance_score == 100.0
        assert health.is_healthy()
    
    def test_parser_health_unhealthy(self):
        """Test unhealthy parser health"""
        health = ParserHealth(
            parser_type=ParserType.ROSBAGS,
            available=False,
            error_message="Import failed"
        )
        
        assert not health.is_healthy()


class TestRosbagsBagParser:
    """Test cases for RosbagsBagParser"""
    
    def test_parser_initialization(self):
        """Test basic parser initialization"""
        parser = RosbagsBagParser()
        assert parser is not None
    
    def test_load_whitelist(self, temp_dir):
        """Test loading topics from whitelist file"""
        whitelist_path = temp_dir / "whitelist.txt"
        whitelist_path.write_text("/topic1\n/topic2\n# This is a comment\n/topic3\n")
        
        parser = RosbagsBagParser()
        topics = parser.load_whitelist(str(whitelist_path))
        
        assert len(topics) == 3
        assert "/topic1" in topics
        assert "/topic2" in topics
        assert "/topic3" in topics
    
    @patch('rosbags.highlevel.AnyReader')
    def test_load_bag(self, mock_any_reader, temp_dir):
        """Test loading bag file"""
        mock_reader = Mock()
        mock_reader.connections = [
            Mock(topic="/topic1", msgtype="std_msgs/String"),
            Mock(topic="/topic2", msgtype="geometry_msgs/Twist")
        ]
        mock_reader.start_time = 1234567890000000000
        mock_reader.end_time = 1234567900000000000
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = RosbagsBagParser()
        topics, connections, time_range = parser.load_bag(str(bag_path))
        
        assert len(topics) == 2
        assert "/topic1" in topics
        assert connections["/topic1"] == "std_msgs/String"
        assert time_range == ((123456789, 0), (123456790, 0))
    
    @patch('rosbags.highlevel.AnyReader')
    def test_get_message_counts(self, mock_any_reader, temp_dir):
        """Test getting message counts"""
        mock_reader = Mock()
        mock_connection1 = Mock(topic="/topic1")
        mock_connection2 = Mock(topic="/topic2")
        mock_reader.connections = [mock_connection1, mock_connection2]
        mock_reader.messages.side_effect = [
            [(None, None, None)] * 100,  # 100 messages for topic1
            [(None, None, None)] * 50    # 50 messages for topic2
        ]
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = RosbagsBagParser()
        counts = parser.get_message_counts(str(bag_path))
        
        assert counts["/topic1"] == 100
        assert counts["/topic2"] == 50
    
    @patch('rosbags.highlevel.AnyReader')
    def test_get_topic_sizes(self, mock_any_reader, temp_dir):
        """Test getting topic sizes"""
        mock_reader = Mock()
        mock_connection1 = Mock(topic="/topic1")
        mock_connection2 = Mock(topic="/topic2")
        mock_reader.connections = [mock_connection1, mock_connection2]
        mock_reader.messages.side_effect = [
            [(None, None, b"data" * 100)] * 10,  # 1000 bytes for topic1
            [(None, None, b"data" * 50)] * 5    # 250 bytes for topic2
        ]
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = RosbagsBagParser()
        sizes = parser.get_topic_sizes(str(bag_path))
        
        assert sizes["/topic1"] == 4000  # 10 * 400 bytes
        assert sizes["/topic2"] == 1000  # 5 * 200 bytes
    
    @patch('rosbags.highlevel.AnyReader')
    def test_get_topic_stats(self, mock_any_reader, temp_dir):
        """Test getting comprehensive topic statistics"""
        mock_reader = Mock()
        mock_connection = Mock(topic="/topic1")
        mock_reader.connections = [mock_connection]
        mock_reader.messages.return_value = [(None, None, b"data" * 100)] * 10
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = RosbagsBagParser()
        stats = parser.get_topic_stats(str(bag_path))
        
        assert "/topic1" in stats
        assert stats["/topic1"]["count"] == 10
        assert stats["/topic1"]["size"] == 4000
        assert stats["/topic1"]["avg_size"] == 400
    
    @patch('rosbags.highlevel.AnyReader')
    def test_read_messages(self, mock_any_reader, temp_dir):
        """Test reading messages from bag"""
        mock_reader = Mock()
        mock_connection = Mock(topic="/topic1", msgtype="std_msgs/String")
        mock_reader.connections = [mock_connection]
        mock_reader.messages.return_value = [
            (mock_connection, 1234567890000000000, b"message_data")
        ]
        mock_reader.deserialize.return_value = Mock(data="test_message")
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = RosbagsBagParser()
        messages = list(parser.read_messages(str(bag_path), ["/topic1"]))
        
        assert len(messages) == 1
        timestamp, message = messages[0]
        assert timestamp == (123456789, 0)
        assert message.data == "test_message"
    
    @patch('rosbags.rosbag1.Writer')
    @patch('rosbags.highlevel.AnyReader')
    def test_filter_bag(self, mock_any_reader, mock_writer, temp_dir):
        """Test filtering bag file"""
        # Mock AnyReader
        mock_reader = Mock()
        mock_connection = Mock(
            topic="/topic1",
            msgtype="std_msgs/String",
            msgdef="string data",
            digest="992ce8a1687cec8c8bd883ec73ca41d1"
        )
        mock_reader.connections = [mock_connection]
        mock_reader.messages.return_value = [
            (mock_connection, 1234567890000000000, b"message_data")
        ]
        mock_any_reader.return_value.__enter__.return_value = mock_reader
        
        # Mock Writer
        mock_writer_instance = Mock()
        mock_writer.return_value.__enter__.return_value = mock_writer_instance
        
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        
        parser = RosbagsBagParser()
        result = parser.filter_bag(
            str(input_path),
            str(output_path),
            ["/topic1"],
            compression="bz2"
        )
        
        assert "completed" in result.lower()
    
    def test_get_compression_format(self):
        """Test compression format conversion"""
        parser = RosbagsBagParser()
        
        with patch('rosbags.rosbag1.Writer') as mock_writer:
            mock_writer.CompressionFormat.BZ2 = "BZ2"
            mock_writer.CompressionFormat.LZ4 = "LZ4"
            
            assert parser._get_compression_format("bz2") == "BZ2"
            assert parser._get_compression_format("lz4") == "LZ4"
            assert parser._get_compression_format("none") is None
    
    def test_filter_bag_file_exists_error(self, temp_dir):
        """Test error when output file exists"""
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        output_path.touch()
        
        parser = RosbagsBagParser()
        
        with pytest.raises(FileExistsError, match="already exists"):
            parser.filter_bag(str(input_path), str(output_path), ["/topic1"])


class TestLegacyBagParser:
    """Test cases for LegacyBagParser"""
    
    def test_parser_initialization(self):
        """Test basic parser initialization"""
        parser = LegacyBagParser()
        assert parser is not None
    
    def test_load_whitelist(self, temp_dir):
        """Test loading topics from whitelist file"""
        whitelist_path = temp_dir / "whitelist.txt"
        whitelist_path.write_text("/topic1\n/topic2\n# This is a comment\n/topic3\n")
        
        parser = LegacyBagParser()
        topics = parser.load_whitelist(str(whitelist_path))
        
        assert len(topics) == 3
        assert "/topic1" in topics
        assert "/topic2" in topics
        assert "/topic3" in topics
    
    @patch('rosbag.Bag')
    def test_load_bag(self, mock_bag_class, temp_dir):
        """Test loading bag file with legacy parser"""
        mock_bag = Mock()
        mock_bag.get_type_and_topic_info.return_value = Mock(
            topics={
                "/topic1": Mock(msg_type="std_msgs/String"),
                "/topic2": Mock(msg_type="geometry_msgs/Twist")
            }
        )
        mock_bag.get_start_time.return_value = 123456789.0
        mock_bag.get_end_time.return_value = 123456790.0
        mock_bag_class.return_value.__enter__.return_value = mock_bag
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = LegacyBagParser()
        topics, connections, time_range = parser.load_bag(str(bag_path))
        
        assert len(topics) == 2
        assert "/topic1" in topics
        assert connections["/topic1"] == "std_msgs/String"
        assert time_range == ((123456789, 0), (123456790, 0))
    
    @patch('rosbag.Bag')
    def test_get_message_counts(self, mock_bag_class, temp_dir):
        """Test getting message counts with legacy parser"""
        mock_bag = Mock()
        mock_bag.get_type_and_topic_info.return_value = Mock(
            topics={
                "/topic1": Mock(message_count=100),
                "/topic2": Mock(message_count=50)
            }
        )
        mock_bag_class.return_value.__enter__.return_value = mock_bag
        
        bag_path = temp_dir / "test.bag"
        bag_path.touch()
        
        parser = LegacyBagParser()
        counts = parser.get_message_counts(str(bag_path))
        
        assert counts["/topic1"] == 100
        assert counts["/topic2"] == 50
    
    @patch('rosbag.Bag')
    def test_filter_bag(self, mock_bag_class, temp_dir):
        """Test filtering bag with legacy parser"""
        mock_input_bag = Mock()
        mock_output_bag = Mock()
        
        # Mock input bag messages
        mock_input_bag.read_messages.return_value = [
            ("/topic1", Mock(), Mock(secs=123456789, nsecs=0))
        ]
        
        mock_bag_class.side_effect = [
            mock_input_bag,  # Input bag
            mock_output_bag  # Output bag
        ]
        
        input_path = temp_dir / "input.bag"
        output_path = temp_dir / "output.bag"
        input_path.touch()
        
        parser = LegacyBagParser()
        result = parser.filter_bag(
            str(input_path),
            str(output_path),
            ["/topic1"],
            compression="bz2"
        )
        
        assert "completed" in result.lower()
        mock_output_bag.write.assert_called_once()


class TestParserHealthChecker:
    """Test cases for ParserHealthChecker"""
    
    def test_health_checker_initialization(self):
        """Test basic health checker initialization"""
        checker = ParserHealthChecker()
        assert checker is not None
    
    @patch('rosbags.highlevel.AnyReader')
    def test_check_rosbags_health_success(self, mock_any_reader):
        """Test rosbags health check success"""
        mock_any_reader.return_value = Mock()
        
        checker = ParserHealthChecker()
        health = checker._check_rosbags_health()
        
        assert health.parser_type == ParserType.ROSBAGS
        assert health.available
        assert health.performance_score == 100.0
    
    def test_check_rosbags_health_failure(self):
        """Test rosbags health check failure"""
        with patch.dict('sys.modules', {'rosbags': None}):
            checker = ParserHealthChecker()
            health = checker._check_rosbags_health()
            
            assert not health.available
            assert "rosbags not available" in health.error_message
    
    @patch('rosbag.Bag')
    def test_check_legacy_health_success(self, mock_bag):
        """Test legacy health check success"""
        checker = ParserHealthChecker()
        health = checker._check_legacy_health()
        
        assert health.parser_type == ParserType.LEGACY
        assert health.available
        assert health.performance_score == 30.0
    
    def test_check_legacy_health_failure(self):
        """Test legacy health check failure"""
        with patch.dict('sys.modules', {'rosbag': None}):
            checker = ParserHealthChecker()
            health = checker._check_legacy_health()
            
            assert not health.available
            assert "legacy rosbag not available" in health.error_message
    
    def test_get_best_parser(self):
        """Test getting best available parser"""
        checker = ParserHealthChecker()
        
        with patch.object(checker, 'check_parser_health') as mock_check:
            # Mock rosbags as healthy
            mock_check.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True
            )
            
            best_type = checker.get_best_parser()
            assert best_type == ParserType.ROSBAGS
    
    def test_get_best_parser_fallback(self):
        """Test fallback to legacy parser"""
        checker = ParserHealthChecker()
        
        with patch.object(checker, 'check_parser_health') as mock_check:
            def mock_health_check(parser_type):
                if parser_type == ParserType.ROSBAGS:
                    return ParserHealth(
                        parser_type=ParserType.ROSBAGS,
                        available=False,
                        error_message="rosbags not available"
                    )
                else:
                    return ParserHealth(
                        parser_type=ParserType.LEGACY,
                        available=True
                    )
            
            mock_check.side_effect = mock_health_check
            best_type = checker.get_best_parser()
            assert best_type == ParserType.LEGACY
    
    def test_get_all_health_status(self):
        """Test getting all parser health status"""
        checker = ParserHealthChecker()
        
        with patch.object(checker, 'check_parser_health') as mock_check:
            mock_check.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True
            )
            
            health_status = checker.get_all_health_status()
            assert ParserType.ROSBAGS in health_status
            assert ParserType.LEGACY in health_status


class TestGlobalFunctions:
    """Test cases for global functions"""
    
    def test_create_parser_rosbags(self):
        """Test creating rosbags parser"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.check_parser_health.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True
            )
            mock_checker.return_value = mock_instance
            
            parser = create_parser(ParserType.ROSBAGS)
            assert isinstance(parser, RosbagsBagParser)
    
    def test_create_parser_legacy(self):
        """Test creating legacy parser"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.check_parser_health.return_value = ParserHealth(
                parser_type=ParserType.LEGACY,
                available=True
            )
            mock_checker.return_value = mock_instance
            
            parser = create_parser(ParserType.LEGACY)
            assert isinstance(parser, LegacyBagParser)
    
    def test_create_parser_unhealthy(self):
        """Test creating parser with unhealthy status"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.check_parser_health.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=False,
                error_message="Import failed"
            )
            mock_checker.return_value = mock_instance
            
            with pytest.raises(RuntimeError, match="not healthy"):
                create_parser(ParserType.ROSBAGS)
    
    def test_create_best_parser(self):
        """Test creating best available parser"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.get_best_parser.return_value = ParserType.ROSBAGS
            mock_instance.check_parser_health.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True
            )
            mock_checker.return_value = mock_instance
            
            parser = create_best_parser()
            assert isinstance(parser, RosbagsBagParser)
    
    def test_get_parser_health(self):
        """Test getting parser health"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.check_parser_health.return_value = ParserHealth(
                parser_type=ParserType.ROSBAGS,
                available=True
            )
            mock_checker.return_value = mock_instance
            
            health = get_parser_health(ParserType.ROSBAGS)
            assert health.parser_type == ParserType.ROSBAGS
            assert health.available
    
    def test_get_all_parser_health(self):
        """Test getting all parser health"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.get_all_health_status.return_value = {
                ParserType.ROSBAGS: ParserHealth(
                    parser_type=ParserType.ROSBAGS,
                    available=True
                ),
                ParserType.LEGACY: ParserHealth(
                    parser_type=ParserType.LEGACY,
                    available=True
                )
            }
            mock_checker.return_value = mock_instance
            
            health_status = get_all_parser_health()
            assert len(health_status) == 2
            assert ParserType.ROSBAGS in health_status
            assert ParserType.LEGACY in health_status
    
    def test_check_parser_availability(self):
        """Test checking parser availability"""
        with patch('roseApp.core.parser.ParserHealthChecker') as mock_checker:
            mock_instance = Mock()
            mock_instance.get_all_health_status.return_value = {
                ParserType.ROSBAGS: ParserHealth(
                    parser_type=ParserType.ROSBAGS,
                    available=True
                ),
                ParserType.LEGACY: ParserHealth(
                    parser_type=ParserType.LEGACY,
                    available=False
                )
            }
            mock_checker.return_value = mock_instance
            
            availability = check_parser_availability()
            assert availability["rosbags"] is True
            assert availability["legacy"] is False