#!/bin/bash

# Quick smoke test - basic functionality verification
# Simple and direct testing for current CLI system

set -e

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSE_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
ROSE_CMD="python -m roseApp.rose"

# Helper functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Change to Rose root directory
cd "$ROSE_ROOT"

# Show test configuration
show_test_config "Quick Smoke Test"

print_header "Rose Quick Smoke Test"
echo "Testing basic CLI functionality..."
echo ""

# Test 0: Main help
print_header "Testing main CLI"
run_cmd_silent $ROSE_CMD --help
print_success "Main CLI help works"

# Test 1: Load (migrated command)
print_header "Testing load command"
run_cmd_silent $ROSE_CMD load --help
print_success "Load help works"

run_cmd_silent $ROSE_CMD load $TEST_BAG
print_success "Basic load works"

# Test 2: Inspect  
print_header "Testing inspect command"
run_cmd_silent $ROSE_CMD inspect --help
print_success "Inspect help works"

run_cmd_silent $ROSE_CMD inspect $TEST_BAG
print_success "Basic inspect works"

# Test 3: Extract
print_header "Testing extract command"
run_cmd_silent $ROSE_CMD extract --help
print_success "Extract help works"

# Test 4: Compress
print_header "Testing compress command"
run_cmd_silent $ROSE_CMD compress --help
print_success "Compress help works"

# Test 5: Data
print_header "Testing data command"
run_cmd_silent $ROSE_CMD data --help
print_success "Data help works"

# Test 6: Cache
print_header "Testing cache command"
run_cmd_silent $ROSE_CMD cache --help
print_success "Cache help works"

run_cmd_silent $ROSE_CMD cache
print_success "Cache status works"

# Test 7: Plugin
print_header "Testing plugin command"
run_cmd_silent $ROSE_CMD plugin --help
print_success "Plugin help works"

echo ""
print_header "Smoke Test Summary"
print_success "All basic CLI commands are functional!"
echo "✓ CLI system is working correctly"
