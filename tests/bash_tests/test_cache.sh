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
run_cmd "python -m roseApp.rose cache --help" "Help works" "Help failed"

print_test "Cache status"
run_cmd "python -m roseApp.rose cache" "Cache status works" "Cache status failed"

print_test "Cache clear"
run_cmd_expect_error "python -m roseApp.rose cache clear" "Cache clear no confirmation works" "Cache clear no confirmation failed"

print_test "Cache clear with confirmation"
run_cmd "python -m roseApp.rose cache clear --yes " "Cache clear works" "Cache clear failed"

echo -e "${GREEN}Cache command smoke tests passed!${NC}"