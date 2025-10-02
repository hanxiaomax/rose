#!/bin/bash

# Common functions for Rose bash tests
# Source this file in test scripts: source "$(dirname "$0")/common_functions.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

# Parse command line arguments for test scripts
parse_test_args() {
    # Default values
    DEFAULT_TEST_BAG="roseApp/tests/test.bag"
    TEST_BAG="$DEFAULT_TEST_BAG"
    VERBOSE_TESTS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --bag|-b)
                TEST_BAG="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE_TESTS=true
                shift
                ;;
            --help|-h)
                show_test_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_test_help
                exit 1
                ;;
        esac
    done
    
    # Validate bag file exists
    if [[ ! -f "$TEST_BAG" ]]; then
        print_error "Bag file not found: $TEST_BAG"
        echo "Available bag files:"
        find roseApp/tests -name "*.bag" -type f 2>/dev/null | head -10
        exit 1
    fi
    
    # Export for use in test scripts
    export TEST_BAG
    export VERBOSE_TESTS
}

# Show help for test scripts
show_test_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --bag, -b FILE     Use specific bag file for testing (default: roseApp/tests/test.bag)"
    echo "  --verbose, -v      Enable verbose test output"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use default bag file"
    echo "  $0 --bag roseApp/tests/test2.bag     # Use specific bag file"
    echo "  $0 -b test4.bag --verbose            # Use bag file with verbose output"
    echo ""
    echo "Available bag files:"
    find roseApp/tests -name "*.bag" -type f 2>/dev/null | head -10
}

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

print_cmd() {
    echo -e "${BLUE}→ $1${NC}"
}

# Execute command and print it (with output visible)
run_cmd() {
    local cmd="$1"
    print_cmd "$cmd"
    eval "$cmd"
}

# Execute command and print it (with output hidden)
run_cmd_silent() {
    local cmd="$1"
    local success_msg="$2"
    local error_msg="$3"
    
    print_cmd "$cmd"
    if eval "$cmd" > /dev/null 2>&1; then
        print_success "$success_msg"
    else
        print_error "$error_msg"
    fi
}

# Execute command and print it (with stderr hidden)
run_cmd_quiet() {
    local cmd="$1"
    print_cmd "$cmd"
    eval "$cmd" 2>/dev/null
}

# Execute command for error testing
run_cmd_expect_error() {
    local cmd="$1"
    local success_msg="$2"
    local error_msg="$3"
    
    print_cmd "$cmd"
    if eval "$cmd" 2>/dev/null; then
        print_error "$error_msg"
        return 1
    else
        print_success "$success_msg"
        return 0
    fi
}

# Show test configuration
show_test_config() {
    local script_name="$1"
    echo -e "${BLUE}=== $script_name Test Configuration ===${NC}"
    echo "Test bag: $TEST_BAG"
    echo "Verbose: $VERBOSE_TESTS"
    echo "Rose command: $ROSE_CMD"
    echo ""
}
