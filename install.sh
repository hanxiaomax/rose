#!/bin/bash

# Define color codes
COLOR_RED="31"
COLOR_GREEN="32"
COLOR_YELLOW="33"
COLOR_BLUE="34"
COLOR_MAGENTA="35"
COLOR_CYAN="36"
COLOR_WHITE="37"

# Function to print colored text
print_color() {
    local color=$1
    local text=$2
    echo -e "\033[${color}m${text}\033[0m"
}

# Check and set TERM environment variable
setup_term() {
    if [[ -z "$TERM" || "$TERM" != "xterm-256color" ]]; then
        print_color $COLOR_YELLOW "TERM environment variable needs to be set for proper color display."

        print_color $COLOR_CYAN "Would you like to add this to your ~/.bashrc? (y/n)"
        read -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if ! grep -q "export TERM=xterm-256color" ~/.bashrc; then
                echo 'export TERM=xterm-256color' >> ~/.bashrc
                print_color $COLOR_GREEN "Added to ~/.bashrc"
                print_color $COLOR_YELLOW "Please run 'source ~/.bashrc' or restart your terminal"
            else
                print_color $COLOR_YELLOW "TERM setting already exists in ~/.bashrc"
            fi
        else
            print_color $COLOR_YELLOW "Please remember to set TERM=xterm-256color manually before running rose"
        fi
        print_color $COLOR_CYAN "Please run the following command in your shell or start a new shell:"
        print_color $COLOR_GREEN "    export TERM=xterm-256color"
    fi
}

# Check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_color $COLOR_RED "Error: Command '$1' not found"
        print_color $COLOR_YELLOW "Please install $1 first"
        exit 1
    fi
}

# Main installation process
main() {
    print_color $COLOR_CYAN "Starting ROSE installation..."
    
    # Check required commands
    check_command python3
    check_command pip

    # Install the package in development mode
    print_color $COLOR_CYAN "Installing ROSE..."
    pip install -e .
    
    # Check installation
    if command -v rose &> /dev/null; then
        print_color $COLOR_GREEN "ROSE installed successfully!"
    else
        print_color $COLOR_RED "ROSE installation failed, please check error messages"
        exit 1
    fi
    
    print_color $COLOR_CYAN "You can now use ROSE with the following commands:"
    print_color $COLOR_GREEN "rose tui    # Launch TUI interface"
    print_color $COLOR_GREEN "rose --help # Show help information"
    # Setup TERM environment variable
    setup_term
}

# Run main function
main 