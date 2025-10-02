#!/bin/bash

# Smoke test for rose cache command
# Simple and direct testing

# Note: Not using set -e to allow error testing

# Load common functions
source "$(dirname "$0")/common_functions.sh"

# Parse command line arguments
parse_test_args "$@"

# Show test configuration
show_test_config

# Setup
cd /workspaces/rose

print_test "Cache command help"
run_cmd_silent "python -m roseApp.rose cache --help" "Help works" "Help failed"

print_test "Cache status"
run_cmd_silent "python -m roseApp.rose cache" "Cache status works" "Cache status failed"

print_test "Cache clear"
run_cmd_silent "python -m roseApp.rose cache --clear" "Cache clear works" "Cache clear failed"

print_test "Cache rebuild"
run_cmd_silent "python -m roseApp.rose cache --rebuild \"$TEST_BAG\"" "Cache rebuild works" "Cache rebuild failed"

print_test "Cache info"
run_cmd_silent "python -m roseApp.rose cache --info \"$TEST_BAG\"" "Cache info works" "Cache info failed"

print_test "Cache non-existent bag (error handling)"
run_cmd_expect_error "python -m roseApp.rose cache --info \"non_existent.bag\"" "Error handling works" "Should fail with non-existent bag"

echo -e "${GREEN}Cache command smoke tests passed!${NC}"