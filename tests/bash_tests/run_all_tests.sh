#!/bin/bash

# Main test runner for all Rose command tests
# Runs all individual command test scripts

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSE_ROOT="$(cd "$TEST_DIR/../.." && pwd)"

# Helper functions
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE} $1 ${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Change to Rose root directory
cd "$ROSE_ROOT"

print_header "Rose Command Test Suite"
echo "Test directory: $TEST_DIR"
echo "Rose root: $ROSE_ROOT"
echo "Test bag: roseApp/tests/demo3.bag"
echo ""

# Check if test bag exists
if [ ! -f "roseApp/tests/demo3.bag" ]; then
    print_error "Test bag file not found: roseApp/tests/demo3.bag"
    exit 1
fi

print_info "Test bag found and ready"

# Make all test scripts executable
chmod +x "$TEST_DIR"/*.sh

# List of test scripts to run
TEST_SCRIPTS=(
    "test_load.sh"
    "test_extract.sh"
    "test_compress.sh"
    "test_inspect.sh"
    "test_data.sh"
    "test_cache.sh"
    "test_plugin.sh"
)

# Track results
PASSED_TESTS=0
FAILED_TESTS=0
TOTAL_TESTS=${#TEST_SCRIPTS[@]}

echo ""
print_header "Running Individual Command Tests"

# Run each test script
for script in "${TEST_SCRIPTS[@]}"; do
    script_path="$TEST_DIR/$script"
    
    if [ -f "$script_path" ]; then
        echo ""
        print_info "Running $script..."
        echo "----------------------------------------"
        
        # Run the test script and capture exit code
        set +e  # Temporarily disable exit on error
        bash "$script_path"
        exit_code=$?
        set -e  # Re-enable exit on error
        
        if [ $exit_code -eq 0 ]; then
            print_success "$script completed successfully"
            ((PASSED_TESTS++))
        else
            print_error "$script failed (exit code: $exit_code)"
            ((FAILED_TESTS++))
        fi
    else
        print_error "Test script not found: $script_path"
        ((FAILED_TESTS++))
    fi
done

echo ""
print_header "Test Summary"
echo "Total tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    print_success "All tests passed! 🎉"
    echo ""
    print_info "Rose command test suite completed successfully"
    exit 0
else
    echo ""
    print_error "Some tests failed! 😞"
    echo ""
    print_info "Check the output above for details"
    exit 1
fi
