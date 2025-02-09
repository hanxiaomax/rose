#!/bin/bash

# Function to print colored text
print_color() {
    local color=$1
    local text=$2
    echo -e "\033[${color}m${text}\033[0m"
}

# Check and set TERM environment variable
setup_term() {
    if [[ -z "$TERM" || "$TERM" != "xterm-256color" ]]; then
        print_color "33" "TERM environment variable needs to be set for proper color display."

        
        print_color "36" "Would you like to add this to your ~/.bashrc? (y/n)"
        read -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if ! grep -q "export TERM=xterm-256color" ~/.bashrc; then
                echo 'export TERM=xterm-256color' >> ~/.bashrc
                print_color "32" "Added to ~/.bashrc"
                print_color "33" "Please run 'source ~/.bashrc' or restart your terminal"
            else
                print_color "33" "TERM setting already exists in ~/.bashrc"
            fi
        else
            print_color "33" "Please remember to set TERM=xterm-256color manually before running rose"
        fi
        print_color "36" "Please run the following command in your shell or start a new shell:"
        print_color "32" "    export TERM=xterm-256color"
    fi
    
}

# Check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_color "31" "Error: Command '$1' not found"
        print_color "33" "Please install $1 first"
        exit 1
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
    
    print_color "36" "You can now use ROSE with the following commands:"
    print_color "32" "rose tui    # Launch TUI interface"
    print_color "32" "rose --help # Show help information"
    # Setup TERM environment variable
    setup_term
}

# Run main function
main 