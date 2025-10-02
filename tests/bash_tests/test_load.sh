#!/bin/bash

# Smoke test for rose load command
# Simple and direct testing

# Note: Not using set -e to allow error testing

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Test configuration
ROSE_CMD="python -m roseApp.rose"

cd /workspaces/rose

# Show test configuration
show_test_config "Load Command"

print_test "Load command help"
run_cmd_silent $ROSE_CMD load --help
print_success "Help works"

print_test "Basic load"
run_cmd_silent $ROSE_CMD load $TEST_BAG
print_success "Basic load works"

print_test "Load with verbose"
run_cmd_silent $ROSE_CMD load $TEST_BAG --verbose
print_success "Verbose load works"

print_test "Load with force"
run_cmd_silent $ROSE_CMD load $TEST_BAG --force
print_success "Force load works"

print_test "Load with dry-run"
run_cmd_silent $ROSE_CMD load $TEST_BAG --dry-run
print_success "Dry-run works"

print_test "Load with build-index"
run_cmd_silent $ROSE_CMD load $TEST_BAG --build-index
print_success "Build-index works"

print_test "Load with workers"
run_cmd_silent $ROSE_CMD load $TEST_BAG --workers 2
print_success "Workers option works"

print_test "Load non-existent file (error handling)"
run_cmd_expect_error $ROSE_CMD load "non_existent.bag"

print_test "Load with glob pattern"
run_cmd_silent $ROSE_CMD load "roseApp/tests/*.bag" --dry-run
print_success "Glob pattern works"

echo -e "${GREEN}Load command smoke tests passed!${NC}"

