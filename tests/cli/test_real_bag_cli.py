"""
CLI tests using real demo.bag file
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from typer.testing import CliRunner
from roseApp.cli.filter import app
from rosbags.rosbag1 import Reader


class TestRealBagCLI:
    """Test CLI functionality with real demo.bag file"""
    
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
    
    def test_cli_basic_filtering(self, runner, demo_bag_path, temp_output_dir):
        """Test basic CLI filtering with real bag"""
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
            expected_topics = ["/tf", "/gps/fix", "/diagnostics"]
            for topic in expected_topics:
                if topic in topics:  # Topic exists in both bag and whitelist
                    assert True
                    break
            else:
                assert False, "No expected topics found in output"
    
    def test_cli_compression_options(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with different compression options"""
        compression_types = ["none", "bz2", "lz4"]
        
        for compression in compression_types:
            output_path = os.path.join(temp_output_dir, f"cli_compressed_{compression}.bag")
            
            result = runner.invoke(app, [
                demo_bag_path,
                output_path,
                "--topics", "/tf",
                "--compression", compression
            ])
            
            assert result.exit_code == 0
            assert "Filtering completed" in result.stdout
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_cli_parallel_processing(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with parallel processing option"""
        output_path = os.path.join(temp_output_dir, "cli_parallel.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf",
            "--parallel"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # Verify output contains requested topic
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
    
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
    
    def test_cli_workers_option(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI workers option"""
        output_path = os.path.join(temp_output_dir, "cli_workers.bag")
        
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf",
            "--workers", "2"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # Verify output contains requested topic
        with Reader(output_path) as reader:
            topics = [conn.topic for conn in reader.connections]
            assert "/tf" in topics
    
    def test_cli_with_existing_output(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI with existing output file"""
        output_path = os.path.join(temp_output_dir, "cli_existing.bag")
        
        # Create existing file
        with open(output_path, 'w') as f:
            f.write("existing content")
        
        # CLI should process and overwrite the existing file
        result = runner.invoke(app, [
            demo_bag_path,
            output_path,
            "--topics", "/tf"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout
        assert os.path.exists(output_path)
        
        # File should be overwritten with bag content
        assert os.path.getsize(output_path) > len("existing content")
    
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
        # Should have error message about no messages or file error
        assert "No messages found" in result.stdout or "Error:" in result.stdout
    
    def test_cli_help_command(self, runner):
        """Test CLI help command"""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert "--topics" in result.stdout
        assert "--compression" in result.stdout
        assert "--whitelist" in result.stdout
    
    def test_cli_show_completion(self, runner):
        """Test CLI show completion"""
        result = runner.invoke(app, ["--show-completion"])
        
        # Should show completion information
        assert result.exit_code == 0
        # Completion information should be present
        assert len(result.stdout.strip()) > 0


class TestRealBagCLIDirectory:
    """Test CLI functionality with directory operations"""
    
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
    
    def test_cli_batch_processing_simulation(self, runner, demo_bag_path, temp_output_dir):
        """Test CLI batch processing simulation"""
        # Create multiple copies of the demo bag for batch processing simulation
        bag_dir = os.path.join(temp_output_dir, "input_bags")
        os.makedirs(bag_dir)
        
        # Copy demo.bag to simulate multiple input files
        import shutil
        bag1_path = os.path.join(bag_dir, "bag1.bag")
        bag2_path = os.path.join(bag_dir, "bag2.bag")
        
        # Note: Copying large files might be slow, so just test with paths
        # In real scenario, you'd process directory of bags
        
        output_dir = os.path.join(temp_output_dir, "output_bags")
        os.makedirs(output_dir)
        
        # Process the demo bag as if it's batch processing
        result = runner.invoke(app, [
            demo_bag_path,
            output_dir,
            "--topics", "/tf"
        ])
        
        assert result.exit_code == 0
        assert "Filtering completed" in result.stdout 