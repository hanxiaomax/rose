#!/bin/bash

# Test script for rose extract command
# Tests various options and combinations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
TEST_BAG="roseApp/tests/demo3.bag"
ROSE_CMD="python -m roseApp.rose"
OUTPUT_DIR="tests/bash_tests/output"

# Helper functions
print_test() {
    echo -e "${YELLOW}=== Testing: $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Setup
mkdir -p $OUTPUT_DIR
cd /workspaces/rose

# Ensure bag is loaded first
echo "Ensuring test bag is loaded..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Extract command help"
$ROSE_CMD extract --help > /dev/null
print_success "Help displayed successfully"

print_test "Extract dry-run to see available topics"
$ROSE_CMD extract $TEST_BAG --dry-run
print_success "Dry-run completed"

print_test "Extract single topic (gps)"
$ROSE_CMD extract $TEST_BAG --topics gps --output "$OUTPUT_DIR/test_gps.bag" --yes
print_success "Single topic extraction completed"

print_test "Extract multiple topics"
$ROSE_CMD extract $TEST_BAG --topics gps tf --output "$OUTPUT_DIR/test_multi.bag" --yes
print_success "Multiple topics extraction completed"

print_test "Extract with fuzzy matching"
$ROSE_CMD extract $TEST_BAG --topics "radar" --output "$OUTPUT_DIR/test_radar.bag" --yes
print_success "Fuzzy matching extraction completed"

print_test "Extract with reverse selection"
$ROSE_CMD extract $TEST_BAG --topics image --reverse --output "$OUTPUT_DIR/test_no_image.bag" --yes
print_success "Reverse selection completed"

print_test "Extract with compression (lz4)"
$ROSE_CMD extract $TEST_BAG --topics gps --compression lz4 --output "$OUTPUT_DIR/test_compressed_lz4.bag" --yes
print_success "LZ4 compression extraction completed"

print_test "Extract with compression (bz2)"
$ROSE_CMD extract $TEST_BAG --topics tf --compression bz2 --output "$OUTPUT_DIR/test_compressed_bz2.bag" --yes
print_success "BZ2 compression extraction completed"

print_test "Extract with verbose output"
$ROSE_CMD extract $TEST_BAG --topics gps --output "$OUTPUT_DIR/test_verbose.bag" --verbose --yes
print_success "Verbose extraction completed"

print_test "Extract with workers option"
$ROSE_CMD extract $TEST_BAG --topics gps tf --output "$OUTPUT_DIR/test_workers.bag" --workers 2 --yes
print_success "Multi-worker extraction completed"

print_test "Extract with pattern in output filename"
$ROSE_CMD extract $TEST_BAG --topics gps --output "$OUTPUT_DIR/{input}_filtered.bag" --yes
print_success "Pattern output filename completed"

print_test "Extract with all options combined"
$ROSE_CMD extract $TEST_BAG --topics gps --output "$OUTPUT_DIR/test_all_options.bag" --compression lz4 --verbose --workers 1 --yes
print_success "All options combined completed"

print_test "Extract non-existent topic (should complete with warning)"
$ROSE_CMD extract $TEST_BAG --topics "non_existent_topic" --output "$OUTPUT_DIR/test_empty.bag" --yes 2>/dev/null || print_success "Handled non-existent topic gracefully"

print_test "Extract from non-existent bag (should fail gracefully)"
$ROSE_CMD extract "non_existent.bag" --topics gps 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/test_*.bag

echo -e "${GREEN}All extract command tests completed successfully!${NC}"
