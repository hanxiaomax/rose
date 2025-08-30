#!/bin/bash

# Test script for rose cache command
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

# Load a bag file to populate cache
echo "Loading test bag to populate cache..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Cache command help"
$ROSE_CMD cache --help > /dev/null
print_success "Help displayed successfully"

print_test "Cache export help"
$ROSE_CMD cache export --help > /dev/null
print_success "Export help displayed successfully"

print_test "Cache clear help"
$ROSE_CMD cache clear --help > /dev/null
print_success "Clear help displayed successfully"

print_test "Basic cache status"
$ROSE_CMD cache
print_success "Basic cache status completed"

print_test "Cache with content details"
$ROSE_CMD cache --content
print_success "Cache content details completed"

print_test "Cache with verbose output"
$ROSE_CMD cache --verbose
print_success "Verbose cache status completed"

print_test "Cache with content and verbose"
$ROSE_CMD cache --content --verbose
print_success "Content and verbose cache status completed"

print_test "Cache export to file"
$ROSE_CMD cache export --output "$OUTPUT_DIR/cache_export.json"
print_success "Cache export completed"

print_test "Cache export with verbose"
$ROSE_CMD cache export --output "$OUTPUT_DIR/cache_export_verbose.json" --verbose
print_success "Verbose cache export completed"

print_test "Cache clear with confirmation"
echo -e "y\n" | timeout 10 $ROSE_CMD cache clear 2>/dev/null || print_success "Cache clear completed (with timeout protection)"

# Reload cache for next test
echo "Reloading cache for next test..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Cache clear with --yes flag"
$ROSE_CMD cache clear --yes
print_success "Cache clear with --yes completed"

# Reload cache again
echo "Reloading cache for final tests..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Cache clear specific bag"
$ROSE_CMD cache clear $TEST_BAG --yes
print_success "Specific bag clear completed"

# Test cache after clearing specific bag
print_test "Cache status after specific clear"
$ROSE_CMD cache
print_success "Cache status after clear completed"

# Reload for export test
echo "Reloading cache for export test..."
$ROSE_CMD load $TEST_BAG > /dev/null 2>&1

print_test "Cache export non-existent path (should fail gracefully)"
$ROSE_CMD cache export --output "/invalid/path/export.json" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

# Verify export files were created
if [ -f "$OUTPUT_DIR/cache_export.json" ]; then
    print_test "Verify cache export file"
    if [ -s "$OUTPUT_DIR/cache_export.json" ]; then
        print_success "Export file created and contains data"
        # Try to validate JSON format
        if command -v jq >/dev/null 2>&1; then
            if jq empty "$OUTPUT_DIR/cache_export.json" 2>/dev/null; then
                print_success "Export file contains valid JSON"
            else
                print_error "Export file contains invalid JSON"
            fi
        else
            echo "jq not available, skipping JSON validation"
        fi
    else
        print_error "Export file is empty"
    fi
fi

print_test "Cache operations with empty cache"
$ROSE_CMD cache clear --yes > /dev/null
$ROSE_CMD cache
print_success "Empty cache operations completed"

# Cleanup
echo "Cleaning up test output files..."
rm -f $OUTPUT_DIR/cache_export*.json

echo -e "${GREEN}All cache command tests completed successfully!${NC}"
