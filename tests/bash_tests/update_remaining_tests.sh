#!/bin/bash

# Script to update remaining test scripts with command logging

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Test scripts to update (excluding already updated ones)
SCRIPTS=(
    "test_compress.sh"
    "test_inspect.sh"
    "test_data.sh"
    "test_cache.sh"
    "test_plugin.sh"
)

print_info "Updating remaining test scripts with command logging..."

for script in "${SCRIPTS[@]}"; do
    print_info "Updating $script..."
    
    # Add common functions source
    sed -i '/# Load common functions/d' "$script"
    sed -i '/source.*common_functions.sh/d' "$script"
    sed -i '7i\\n# Load common functions\nsource "$(dirname "$0")/common_functions.sh"' "$script"
    
    # Remove old color definitions and helper functions
    sed -i '/# Colors for output/,/^$/d' "$script"
    sed -i '/# Helper functions/,/^}$/d' "$script"
    
    # Update command executions
    sed -i 's/\$ROSE_CMD \([^>]*\) > \/dev\/null 2>&1/run_cmd_silent $ROSE_CMD \1/g' "$script"
    sed -i 's/\$ROSE_CMD \([^>]*\) > \/dev\/null/run_cmd_silent $ROSE_CMD \1/g' "$script"
    sed -i 's/\$ROSE_CMD \([^>]*\) 2>\/dev\/null && print_error "Should fail" || print_success "Error handling works"/run_cmd_expect_error $ROSE_CMD \1/g' "$script"
    
    print_success "$script updated"
done

print_success "All remaining test scripts updated with command logging!"
