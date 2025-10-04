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
run_cmd_silent "$ROSE_CMD load --help" "Help works" "Help failed"

print_test "Basic load"
run_cmd_silent "$ROSE_CMD load $TEST_BAG" "Basic load works" "Basic load failed"

print_test "Load with verbose"
run_cmd_silent "$ROSE_CMD load $TEST_BAG --verbose" "Verbose load works" "Verbose load failed"

print_test "Load with force"
run_cmd_silent "$ROSE_CMD load $TEST_BAG --force" "Force load works" "Force load failed"

print_test "Load with dry-run"
run_cmd_silent "$ROSE_CMD load $TEST_BAG --dry-run" "Dry-run works" "Dry-run failed"

print_test "Load with build-index"
run_cmd_silent "$ROSE_CMD load $TEST_BAG --build-index" "Build-index works" "Build-index failed"

print_test "Load with workers"
run_cmd_silent "$ROSE_CMD load $TEST_BAG --workers 2" "Workers option works" "Workers option failed"

print_test "Load non-existent file (error handling)"
run_cmd_expect_error "$ROSE_CMD load non_existent.bag" "Error handling works" "Should fail with non-existent file"

print_test "Load with glob pattern"
run_cmd_silent "$ROSE_CMD load 'roseApp/tests/*.bag' --dry-run" "Glob pattern works" "Glob pattern failed"

echo -e "${GREEN}Load command smoke tests passed!${NC}"

