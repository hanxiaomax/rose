#!/bin/bash

# Function to print colored text
print_color() {
    local color=$1
    local text=$2
    echo -e "\033[${color}m${text}\033[0m"
}

# Check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_color "31" "Error: Command '$1' not found"
        print_color "33" "Please install $1 first"
        exit 1
    fi
}

# Check TERM environment variable
check_term() {
    if [[ "$TERM" != "xterm-256color" ]]; then
        print_color "33" "Warning: TERM environment variable is not set to xterm-256color"
        print_color "36" "Consider adding the following line to your ~/.bashrc or ~/.zshrc:"
        echo 'export TERM=xterm-256color'
        
        read -p "Would you like to add it to ~/.bashrc now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo 'export TERM=xterm-256color' >> ~/.bashrc
            print_color "32" "Added to ~/.bashrc"
            print_color "33" "Please run 'source ~/.bashrc' to apply the changes"
        fi
    fi
}

# Main installation process
main() {
    print_color "36" "Starting ROSE installation..."
    
    # Check required commands
    check_command python3
    check_command pip

    # Install the package in development mode
    print_color "36" "Installing ROSE..."
    pip install -e .
    
    # Check installation
    if command -v rose &> /dev/null; then
        print_color "32" "ROSE installed successfully!"
    else
        print_color "31" "ROSE installation failed, please check error messages"
        exit 1
    fi
    
    # Check TERM environment variable
    check_term
    
    print_color "36" "You can now use ROSE with the following commands:"
    print_color "32" "rose tui    # Launch TUI interface"
    print_color "32" "rose --help # Show help information"
}

# Run main function
main 