"""
Unit tests for the data CLI module.

Tests data manipulation functionality including:
- DataFrame export to CSV
- Topic merging
- Filtering and searching
- Interactive and non-interactive modes
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Skip pandas-dependent tests if pandas is not available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from roseApp.cli.data import DataProcessor
from roseApp.core.model import ComprehensiveBagInfo, TopicInfo, TimeRange


class TestDataProcessor(unittest.TestCase):
    """Test cases for DataProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = DataProcessor()
        
        # Create mock bag info with topics
        self.mock_bag_info = ComprehensiveBagInfo(
            file_path="/test/test.bag",
            file_size=1024,
            time_range=TimeRange(
                start_time=(1000, 0),
                end_time=(2000, 0)
            ),
            topics=[
                TopicInfo(
                    name="/test/topic1",
                    message_type="sensor_msgs/PointCloud2",
                    message_count=100,
                    message_frequency=10.0
                ),
                TopicInfo(
                    name="/test/topic2",
                    message_type="geometry_msgs/Twist",
                    message_count=200,
                    message_frequency=20.0
                )
            ],
            total_messages=300,
            analysis_level="full"
        )
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_get_topic_dataframes(self):
        """Test retrieving DataFrames for specified topics"""
        # Create mock DataFrames
        mock_df1 = pd.DataFrame({
            'x': [1, 2, 3],
            'y': [4, 5, 6],
            'timestamp_ns': [1000000000, 2000000000, 3000000000]
        })
        mock_df2 = pd.DataFrame({
            'linear_x': [0.1, 0.2, 0.3],
            'angular_z': [0.5, 0.6, 0.7],
            'timestamp_ns': [1500000000, 2500000000, 3500000000]
        })
        
        # Set DataFrames on topic info
        self.mock_bag_info.topics[0].set_dataframe(mock_df1)
        self.mock_bag_info.topics[1].set_dataframe(mock_df2)
        
        # Test getting DataFrames
        topic_names = ["/test/topic1", "/test/topic2"]
        dataframes = self.processor.get_topic_dataframes(self.mock_bag_info, topic_names)
        
        self.assertEqual(len(dataframes), 2)
        self.assertIn("/test/topic1", dataframes)
        self.assertIn("/test/topic2", dataframes)
        
        # Verify DataFrame content
        pd.testing.assert_frame_equal(dataframes["/test/topic1"], mock_df1)
        pd.testing.assert_frame_equal(dataframes["/test/topic2"], mock_df2)
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_merge_topic_dataframes_stack(self):
        """Test stacking DataFrames by timestamp"""
        # Create test DataFrames with timestamp index
        df1 = pd.DataFrame({
            'x': [1, 2, 3],
            'y': [4, 5, 6]
        }, index=pd.to_datetime([1000000000, 2000000000, 3000000000], unit='ns'))
        
        df2 = pd.DataFrame({
            'linear_x': [0.1, 0.2],
            'angular_z': [0.5, 0.6]
        }, index=pd.to_datetime([1500000000, 2500000000], unit='ns'))
        
        dataframes = {
            "/test/topic1": df1,
            "/test/topic2": df2
        }
        
        stacked_df = self.processor.merge_topic_dataframes(dataframes)
        
        # Check that stacked DataFrame has expected structure
        self.assertIsInstance(stacked_df, pd.DataFrame)
        self.assertEqual(len(stacked_df), 5)  # Total rows from both DataFrames
        self.assertIn("topic", stacked_df.columns)  # Topic source column
        
        # Check that data is sorted by timestamp
        timestamps = stacked_df.index
        self.assertTrue(timestamps.is_monotonic_increasing)
    

    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_filter_dataframe_time_range(self):
        """Test filtering DataFrame by time range"""
        # Create test DataFrame with timestamp index
        timestamps = pd.to_datetime([1000000000, 2000000000, 3000000000, 4000000000], unit='ns')
        df = pd.DataFrame({
            'value': [1, 2, 3, 4]
        }, index=timestamps)
        
        # Apply time range filter
        filters = {
            'start_time': pd.to_datetime(1500000000, unit='ns'),
            'end_time': pd.to_datetime(3500000000, unit='ns')
        }
        
        filtered_df = self.processor.filter_dataframe(df, filters)
        
        # Should keep rows with timestamps between start and end
        self.assertEqual(len(filtered_df), 2)
        self.assertEqual(filtered_df['value'].tolist(), [2, 3])
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_filter_dataframe_column_filters(self):
        """Test filtering DataFrame by column values"""
        df = pd.DataFrame({
            'value': [1, 2, 3, 4, 5],
            'category': ['A', 'B', 'A', 'C', 'B']
        })
        
        # Apply column range filter
        filters = {
            'column_filters': {
                'value': {'min': 2, 'max': 4}
            }
        }
        
        filtered_df = self.processor.filter_dataframe(df, filters)
        
        # Should keep rows with values between 2 and 4
        self.assertEqual(len(filtered_df), 3)
        self.assertEqual(filtered_df['value'].tolist(), [2, 3, 4])
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_filter_dataframe_text_search(self):
        """Test filtering DataFrame by text search"""
        df = pd.DataFrame({
            'message': ['Hello world', 'Goodbye world', 'Hello there', 'Test message'],
            'value': [1, 2, 3, 4]
        })
        
        # Apply text search filter
        filters = {
            'search_text': 'hello'
        }
        
        filtered_df = self.processor.filter_dataframe(df, filters)
        
        # Should keep rows containing 'hello' (case insensitive)
        self.assertEqual(len(filtered_df), 2)
        self.assertTrue(all('hello' in msg.lower() for msg in filtered_df['message']))
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_process_timestamp_columns(self):
        """Test merging timestamp_sec and timestamp_ns columns"""
        # Test with both timestamp columns
        df = pd.DataFrame({
            'timestamp_sec': [1490150278, 1490150279, 1490150280],
            'timestamp_ns': [94034595, 169991489, 245123456],
            'x': [1, 2, 3],
            'y': [4, 5, 6]
        })
        
        processed_df = self.processor._process_timestamp_columns(df)
        
        # Check that timestamp columns are merged
        self.assertIn('timestamp', processed_df.columns)
        self.assertNotIn('timestamp_sec', processed_df.columns)
        self.assertNotIn('timestamp_ns', processed_df.columns)
        
        # Check that timestamp is the first column
        self.assertEqual(processed_df.columns[0], 'timestamp')
        
        # Check timestamp values (should be sec + ns/1e9)
        expected_timestamps = [1490150278.094034595, 1490150279.169991489, 1490150280.245123456]
        pd.testing.assert_series_equal(
            processed_df['timestamp'], 
            pd.Series(expected_timestamps, name='timestamp'),
            check_exact=False
        )
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_process_timestamp_columns_sec_only(self):
        """Test processing with only timestamp_sec column"""
        df = pd.DataFrame({
            'timestamp_sec': [1490150278, 1490150279],
            'x': [1, 2]
        })
        
        processed_df = self.processor._process_timestamp_columns(df)
        
        self.assertIn('timestamp', processed_df.columns)
        self.assertNotIn('timestamp_sec', processed_df.columns)
        self.assertEqual(processed_df.columns[0], 'timestamp')
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_process_timestamp_columns_ns_only(self):
        """Test processing with only timestamp_ns column"""
        df = pd.DataFrame({
            'timestamp_ns': [1490150278094034595, 1490150279169991489],
            'x': [1, 2]
        })
        
        processed_df = self.processor._process_timestamp_columns(df)
        
        self.assertIn('timestamp', processed_df.columns)
        self.assertNotIn('timestamp_ns', processed_df.columns)
        self.assertEqual(processed_df.columns[0], 'timestamp')
        
        # Check conversion from nanoseconds to seconds
        expected_timestamps = [1490150278.094034595, 1490150279.169991489]
        pd.testing.assert_series_equal(
            processed_df['timestamp'], 
            pd.Series(expected_timestamps, name='timestamp'),
            check_exact=False
        )
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    def test_export_to_csv(self):
        """Test exporting DataFrame to CSV file with timestamp processing"""
        df = pd.DataFrame({
            'timestamp_sec': [1490150278, 1490150279, 1490150280],
            'timestamp_ns': [94034595, 169991489, 245123456],
            'x': [1, 2, 3],
            'y': [4, 5, 6]
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Test CSV export with timestamp processing
            success = self.processor.export_to_csv(df, output_path, include_index=True)
            
            self.assertTrue(success)
            self.assertTrue(os.path.exists(output_path))
            
            # Verify CSV content (no index_col since we excluded index)
            exported_df = pd.read_csv(output_path)
            self.assertEqual(len(exported_df), 3)
            
            # Check that timestamp is the first column and properly merged
            self.assertEqual(exported_df.columns[0], 'timestamp')
            self.assertNotIn('timestamp_sec', exported_df.columns)
            self.assertNotIn('timestamp_ns', exported_df.columns)
            
            # Verify timestamp values are correctly merged
            self.assertTrue(all(isinstance(val, float) for val in exported_df['timestamp']))
            self.assertTrue(all(val > 1490150000 for val in exported_df['timestamp']))  # Reasonable timestamp values
            
        finally:
            # Clean up
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_to_csv_no_pandas(self):
        """Test CSV export when pandas is not available"""
        with patch('roseApp.cli.data.PANDAS_AVAILABLE', False):
            success = self.processor.export_to_csv(None, "test.csv")
            self.assertFalse(success)
    
    @patch('roseApp.cli.data.create_parser')
    @patch('roseApp.cli.data.create_bag_cache_manager')
    def test_processor_initialization(self, mock_cache_manager, mock_parser):
        """Test DataProcessor initialization"""
        processor = DataProcessor()
        
        # Verify that parser and cache manager are created
        mock_parser.assert_called_once()
        mock_cache_manager.assert_called_once()
        
        self.assertIsNotNone(processor.parser)
        self.assertIsNotNone(processor.cache_manager)
        self.assertIsNone(processor.current_bag_info)
        self.assertIsNone(processor.current_bag_path)


class TestDataProcessorIntegration(unittest.TestCase):
    """Integration tests for DataProcessor with mocked dependencies"""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies"""
        self.patcher_parser = patch('roseApp.cli.data.create_parser')
        self.patcher_cache = patch('roseApp.cli.data.create_bag_cache_manager')
        
        self.mock_parser = self.patcher_parser.start()
        self.mock_cache_manager = self.patcher_cache.start()
        
        # Set up mock parser instance
        self.mock_parser_instance = Mock()
        self.mock_parser.return_value = self.mock_parser_instance
        
        # Set up mock cache manager instance
        self.mock_cache_instance = Mock()
        self.mock_cache_manager.return_value = self.mock_cache_instance
        
        self.processor = DataProcessor()
    
    def tearDown(self):
        """Clean up patches"""
        self.patcher_parser.stop()
        self.patcher_cache.stop()
    
    @unittest.skipIf(not PANDAS_AVAILABLE, "Pandas not available")
    @patch('roseApp.cli.data.DataProcessor._run_async')
    def test_load_bag_sync(self, mock_run_async):
        """Test synchronous bag loading with DataFrame generation"""
        # Set up mock bag info
        mock_bag_info = ComprehensiveBagInfo(
            file_path="/test/test.bag",
            file_size=1024,
            time_range=TimeRange(
                start_time=(1000, 0),
                end_time=(2000, 0)
            ),
            topics=[
                TopicInfo(
                    name="/test/topic1",
                    message_type="sensor_msgs/PointCloud2",
                    message_count=100
                )
            ],
            total_messages=100,
            analysis_level="index"
        )
        
        mock_run_async.return_value = mock_bag_info
        
        # Test loading
        result = self.processor.load_bag_sync("/test/test.bag")
        
        self.assertEqual(result, mock_bag_info)
        # Note: current_bag_info and current_bag_path are set in the actual async method
        # which we're mocking, so we can't test them here without more complex setup


if __name__ == '__main__':
    # Run tests
    unittest.main()
