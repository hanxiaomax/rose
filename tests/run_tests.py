#!/usr/bin/env python3
"""
Test runner for Rose ROS Bag Tool

This script provides convenient ways to run different test suites:
- Core functionality tests (unit tests)
- CLI integration tests  
- All tests with coverage reporting
- Specific test categories
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(cmd, description="Running command"):
    """Run a command and return the result"""
    print(f"\n{description}...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    print("-" * 60)
    if result.returncode == 0:
        print(f"✅ {description} completed successfully")
    else:
        print(f"❌ {description} failed with exit code {result.returncode}")
    
    return result.returncode


def run_core_tests():
    """Run core functionality tests"""
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/core/", 
        "-v", 
        "--tb=short",
        "-m", "unit"
    ]
    return run_command(cmd, "Core functionality tests")


def run_cli_tests():
    """Run CLI integration tests"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/cli/",
        "-v",
        "--tb=short", 
        "-m", "integration"
    ]
    return run_command(cmd, "CLI integration tests")


def run_all_tests():
    """Run all tests"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "All tests")


def run_tests_with_coverage():
    """Run all tests with coverage reporting"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=roseApp",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-branch"
    ]
    return run_command(cmd, "All tests with coverage")


def run_specific_test(test_path):
    """Run a specific test file or test function"""
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, f"Specific test: {test_path}")


def run_tests_by_marker(marker):
    """Run tests by pytest marker"""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m", marker
    ]
    return run_command(cmd, f"Tests with marker: {marker}")


def main():
    parser = argparse.ArgumentParser(description="Run Rose ROS Bag Tool tests")
    parser.add_argument(
        "test_type",
        choices=["core", "cli", "all", "coverage", "specific", "marker"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--path",
        help="Path to specific test file or function (for 'specific' type)"
    )
    parser.add_argument(
        "--marker",
        help="Pytest marker to filter tests (for 'marker' type)"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies before running tests"
    )
    
    args = parser.parse_args()
    
    # Install test dependencies if requested
    if args.install_deps:
        install_cmd = [
            sys.executable, "-m", "pip", "install", 
            "pytest", "pytest-cov", "pytest-mock"
        ]
        run_command(install_cmd, "Installing test dependencies")
    
    # Change to project root directory
    os.chdir(project_root)
    
    # Run the requested tests
    if args.test_type == "core":
        exit_code = run_core_tests()
    elif args.test_type == "cli":
        exit_code = run_cli_tests()
    elif args.test_type == "all":
        exit_code = run_all_tests()
    elif args.test_type == "coverage":
        exit_code = run_tests_with_coverage()
    elif args.test_type == "specific":
        if not args.path:
            print("Error: --path is required for 'specific' test type")
            sys.exit(1)
        exit_code = run_specific_test(args.path)
    elif args.test_type == "marker":
        if not args.marker:
            print("Error: --marker is required for 'marker' test type")
            sys.exit(1)
        exit_code = run_tests_by_marker(args.marker)
    
    # Print summary
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("🎉 All tests completed successfully!")
    else:
        print("💥 Some tests failed!")
    print("=" * 60)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
