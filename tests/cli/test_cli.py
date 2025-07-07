"""
Basic CLI functionality tests using real demo.bag file
"""
import pytest
import os
import tempfile
import shutil
from typer.testing import CliRunner
from roseApp.cli.filter import app
from rosbags.rosbag1 import Reader


class TestCLIBasic:
    """Test basic CLI functionality"""
    
    @pytest.fixture
    def runner(self):
        """CLI test runner"""
        return CliRunner()
    
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
    
    def test_cli_help(self, runner):
        """Test CLI help command"""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "--topics" in result.stdout
        assert "--compression" in result.stdout
        assert "--whitelist" in result.stdout
    
    def test_cli_single_topic_filtering(self, runner, demo_bag_path, temp_output_dir):
        """Test basic CLI filtering with single topic"""
        output_path = os.path.join(temp_output_dir, "cli_filtered.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # Verify output contains only requested topic
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
            assert len(topics) == 1
    
    def test_cli_multiple_topics(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI filtering with multiple topics"""
        output_path = os.path.join(temp_output_dir, "cli_multi.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf",
            "--topics", "/gps/fix"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # Verify output contains requested topics
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
            assert "/gps/fix" in topics
            assert len(topics) == 2
    
    def test_cli_with_whitelist(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with whitelist file"""
        output_path = os.path.join(temp_output_dir, "cli_whitelist.bag")
        whitelist_path = "tests/fixtures/test_whitelist.txt"
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--whitelist", whitelist_path
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # Verify output contains whitelist topics
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            
            # Should contain some of the whitelist topics
            expected_topics = ["/tf", "/gps/fix"]
            for topic in expected_topics:
                if topic in topics:
                    assert True
                    break
            else:
                assert False, "No expected topics found in output"
    
    def test_cli_compression(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with compression option"""
        output_path = os.path.join(temp_output_dir, "cli_compressed.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf",
            "--compression", "none"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
    
    def test_cli_dry_run(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI dry run mode"""
        output_path = os.path.join(temp_output_dir, "cli_dry_run.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf",
            "--dry-run"
        ])
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout or "dry run" in result.stdout.lower()
        
        # Output file should NOT be created in dry run
        assert not os.path.exists(output_path)
    
    def test_cli_directory_output(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with directory as output"""
        result = runner.invoke(app, [
            demo_bag_path,
            temp_output_dir,
            "--topics", "/tf"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        
        # Should create output file in directory
        output_files = [f for f in os.listdir(temp_output_dir) if f.endswith('.bag')]
        assert len(output_files) > 0
        
        # Check the created file
        output_path = os.path.join(temp_output_dir, output_files[0])
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
    
    def test_cli_invalid_topic(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with invalid/non-existent topic"""
        output_path = os.path.join(temp_output_dir, "cli_invalid.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/nonexistent_topic"
        ])
        
        # Should fail with error when no messages found
        assert result.exit_code != 0
        assert "No messages found" in result.stdout or "Error:" in result.stdout
    
    def test_cli_missing_topics(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI without specifying topics"""
        output_path = os.path.join(temp_output_dir, "cli_no_topics.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path
        ])
        
        # Should fail when no topics specified
        assert result.exit_code != 0
        assert "No topics specified" in result.stdout or "Error:" in result.stdout 