#!/bin/bash

# Smoke test for rose plugin command
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

print_test "Plugin command help"
run_cmd_silent "python -m roseApp.rose plugin --help" "Help works" "Help failed"

print_test "Plugin list"
run_cmd_silent "python -m roseApp.rose plugin list" "Plugin list works" "Plugin list failed"

print_test "Plugin info"
run_cmd_silent "python -m roseApp.rose plugin info" "Plugin info works" "Plugin info failed"

print_test "Plugin create help"
run_cmd_silent "python -m roseApp.rose plugin create --help" "Plugin create help works" "Plugin create help failed"

print_test "Plugin install help"
run_cmd_silent "python -m roseApp.rose plugin install --help" "Plugin install help works" "Plugin install help failed"

print_test "Plugin remove help"
run_cmd_silent "python -m roseApp.rose plugin remove --help" "Plugin remove help works" "Plugin remove help failed"

echo -e "${GREEN}Plugin command smoke tests passed!${NC}"