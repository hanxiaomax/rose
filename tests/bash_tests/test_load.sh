#!/bin/bash

# Test script for rose load command
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

# Clear cache before tests
echo "Clearing cache before tests..."
$ROSE_CMD cache clear --yes > /dev/null 2>&1 || true

print_test "Load command help"
$ROSE_CMD load --help > /dev/null
print_success "Help displayed successfully"

print_test "Basic load"
$ROSE_CMD load $TEST_BAG
print_success "Basic load completed"

print_test "Load with verbose output"
$ROSE_CMD load $TEST_BAG --verbose
print_success "Verbose load completed"

print_test "Load with force reload"
$ROSE_CMD load $TEST_BAG --force
print_success "Force reload completed"

print_test "Load with build index"
$ROSE_CMD load $TEST_BAG --build-index
print_success "Load with index build completed"

print_test "Load with dry-run"
$ROSE_CMD load $TEST_BAG --dry-run
print_success "Dry-run completed"

print_test "Load with workers option"
$ROSE_CMD load $TEST_BAG --workers 2
print_success "Load with 2 workers completed"

print_test "Load with verbose and force combined"
$ROSE_CMD load $TEST_BAG --verbose --force
print_success "Verbose + force load completed"

print_test "Load with all options combined"
$ROSE_CMD load $TEST_BAG --verbose --force --build-index --workers 1
print_success "All options combined completed"

print_test "Load non-existent file (should fail gracefully)"
$ROSE_CMD load "non_existent.bag" 2>/dev/null && print_error "Should have failed" || print_success "Failed gracefully as expected"

print_test "Load with glob pattern (dry-run)"
$ROSE_CMD load "roseApp/tests/*.bag" --dry-run
print_success "Glob pattern dry-run completed"

echo -e "${GREEN}All load command tests completed successfully!${NC}"

