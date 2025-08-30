#!/bin/bash

# Quick test runner - runs a subset of tests from each script to verify functionality
# This is used for quick validation, not comprehensive testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSE_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
TEST_BAG="roseApp/tests/demo3.bag"
ROSE_CMD="python -m roseApp.rose"

# Helper functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Change to Rose root directory
cd "$ROSE_ROOT"

print_header "Rose Quick Test Suite"
echo "Testing basic functionality of all commands..."
echo ""

# Clear cache first
echo "Clearing cache..."
$ROSE_CMD cache clear --yes > /dev/null 2>&1 || true

# Test 1: Load
print_header "Testing load command"
$ROSE_CMD load --help > /dev/null
print_success "Load help works"

$ROSE_CMD load $TEST_BAG > /dev/null
print_success "Basic load works"

# Test 2: Inspect  
print_header "Testing inspect command"
$ROSE_CMD inspect --help > /dev/null
print_success "Inspect help works"

$ROSE_CMD inspect $TEST_BAG > /dev/null
print_success "Basic inspect works"

# Test 3: Extract
print_header "Testing extract command"
$ROSE_CMD extract --help > /dev/null
print_success "Extract help works"

$ROSE_CMD extract $TEST_BAG --topics gps --dry-run > /dev/null
print_success "Extract dry-run works"

# Test 4: Compress
print_header "Testing compress command"
$ROSE_CMD compress --help > /dev/null
print_success "Compress help works"

$ROSE_CMD compress $TEST_BAG --dry-run > /dev/null
print_success "Compress dry-run works"

# Test 5: Data (requires DataFrame index)
print_header "Testing data command"
$ROSE_CMD data --help > /dev/null
print_success "Data help works"

$ROSE_CMD load $TEST_BAG --build-index > /dev/null
$ROSE_CMD data info $TEST_BAG > /dev/null
print_success "Data info works"

# Test 6: Cache
print_header "Testing cache command"
$ROSE_CMD cache --help > /dev/null
print_success "Cache help works"

$ROSE_CMD cache > /dev/null
print_success "Cache status works"

# Test 7: Plugin
print_header "Testing plugin command"
$ROSE_CMD plugin --help > /dev/null
print_success "Plugin help works"

$ROSE_CMD plugin list > /dev/null
print_success "Plugin list works"

echo ""
print_header "Quick Test Summary"
print_success "All basic command functionality verified!"
echo "Run 'bash tests/bash_tests/run_all_tests.sh' for comprehensive testing."
