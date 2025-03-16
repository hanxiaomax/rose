import os
import time
from typing import Optional, List
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import typer
from InquirerPy.validator import PathValidator

from ..core.parser import create_parser, ParserType
from ..core.util import get_logger
from .theme import style, GREEN, YELLOW, BLUE, PURPLE, ORANGE  # Import colors and style
from .util import (build_banner, 
                   collect_bag_files, 
                   print_usage_instructions, 
                   print_bag_info, 
                   print_filter_stats,
                   print_batch_filter_summary)
logger = get_logger("RoseCLI-Tool")

app = typer.Typer(help="ROS Bag Filter Tool")


class CliTool:
    def __init__(self):
        self.console = Console()
        self.parser = create_parser(ParserType.PYTHON)
        self.topics = None
        self.connections = None
        self.time_range = None
 
    def ask_for_bag(self, message: str = "Enter bag file path:") -> Optional[str]:
        """Ask user to input a bag file path"""
        while True:
            input_bag = inquirer.filepath(
                message=message,
                validate=PathValidator(is_file=True, message="File does not exist"),
                filter=lambda x: x if x.endswith('.bag') else None,
                invalid_message="File must be a .bag file",
                style=style
            ).execute()
            
            if input_bag is None:  # User cancelled
                return None
                
            return input_bag
    
    def show_loading(self, message: str):
        """Show a loading spinner with message"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        )
    
    def run_cli(self):
        """Run the CLI tool with improved menu logic"""
        try:
            # Show banner
            self.console.print(build_banner())
            
            while True:
                # Show main menu
                action = inquirer.select(
                    message="Select action:",
                    choices=[
                        Choice(value="filter", name="1. Bag Editor - View and filter bag files"),
                        Choice(value="whitelist", name="2. Whitelist - Manage topic whitelists"),
                        Choice(value="exit", name="3. Exit")
                    ],
                    style=style
                ).execute()
                
                if action == "exit":
                    break
                elif action == "filter":
                    self._run_interactive_filter()
                elif action == "whitelist":
                    self._run_whitelist_manager()
                
        except KeyboardInterrupt:
            self.console.print("\nOperation cancelled by user", style=YELLOW)
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.console.print(f"\nError: {str(e)}", style="red")


    def _run_interactive_filter(self):
        """Run quick filter workflow"""
        while True:
            # Ask for input bag file or directory
            input_path = inquirer.filepath(
                message="Load Bag file(s):\n • Please specify the bag file or a directory to search \n • Leave blank to return to main menu\nFilename/Directory:",
                validate=lambda x: os.path.exists(x) or "Path does not exist",
                style=style
            ).execute()
            
            if not input_path:
                return  # Return to main menu
                
            # Check if input is a file or directory
            if os.path.isfile(input_path):
                # Single bag file processing
                if not input_path.endswith('.bag'):
                    self.console.print("File must be a .bag file", style="red")
                    continue
                    
                # Load bag info
                with self.show_loading("Loading bag file...") as progress:
                    progress.add_task(description="Loading...")
                    self.topics, self.connections, self.time_range = self.parser.load_bag(input_path)
                
                # Create a loop for bag operations
                while True:
                    # Ask user what to do next
                    next_action = inquirer.select(
                        message="What would you like to do?",
                        choices=[
                            Choice(value="info", name="1. Show bag information"),
                            Choice(value="filter", name="2. Filter bag file"),
                            Choice(value="back", name="3. Back to file selection")
                        ],
                        style=style
                    ).execute()
                    
                    if next_action == "back":
                        break  # Go back to input selection
                    elif next_action == "info":
                        print_bag_info(self.console, input_path, self.topics, self.connections, self.time_range)
                        continue  # Stay in the current menu
                    elif next_action == "filter":
                        # Get output bag
                        output_bag = inquirer.filepath(
                            message="Enter output bag file path:",
                            default=os.path.splitext(input_path)[0] + "_filtered.bag",
                            validate=lambda x: x.endswith('.bag') or "File must be a .bag file",
                            style=style
                        ).execute()
                        
                        if not output_bag:
                            continue  # Stay in the current menu
                            
                        # Get filter method
                        filter_method = inquirer.select(
                            message="Select filter method:",
                            choices=[
                                Choice(value="whitelist", name="1. Use whitelist"),
                                Choice(value="manual", name="2. Select topics manually"),
                                Choice(value="back", name="3. Back")
                            ],
                            style=style
                        ).execute()
                        
                        if not filter_method or filter_method == "back":
                            continue  # Stay in the current menu
                            
                        # Process single file
                        self._process_single_bag(input_path, output_bag, filter_method)
                        # Continue in the same menu after processing
                
            else:  # Directory processing
                # Find and select bag files
                bag_files = collect_bag_files(input_path)
                if not bag_files:
                    self.console.print("No bag files found in directory", style="red")
                    continue  # Go back to input selection
                    
                # Create file selection choices
                file_choices = [
                    Choice(
                        value=f,
                        name=f"{os.path.relpath(f, input_path)} ({os.path.getsize(f)/1024/1024:.1f} MB)"
                    ) for f in bag_files
                ]
                
                def bag_list_transformer(result):
                    return f"{len(result)} files selected\n" + '\n'.join([f"• {os.path.basename(bag)}" for bag in result])
                
                print_usage_instructions(self.console)

                selected_files = inquirer.checkbox(
                    message="Select bag files to process:",
                    choices=file_choices,
                    instruction="",
                    validate=lambda result: len(result) > 0,
                    invalid_message="Please select at least one file",
                    transformer=bag_list_transformer,
                    style=style
                ).execute()
                
                if not selected_files:
                    continue  # Go back to input selection
                    
                # Get filter method
                filter_method = inquirer.select(
                    message="Select filter method:",
                    choices=[
                        Choice(value="whitelist", name="1. Use whitelist"),
                        Choice(value="manual", name="2. Select topics manually"),
                        Choice(value="back", name="3. Back")
                    ],
                    style=style
                ).execute()
                
                if not filter_method or filter_method == "back":
                    continue  # Go back to input selection
                    
                

                # Load first bag file to get topics for selection
                whitelist = None
                if filter_method == "whitelist":
                    # Get whitelist file
                    whitelist_dir = "whitelists"
                    if not os.path.exists(whitelist_dir):
                        self.console.print("No whitelists found", style=YELLOW)
                        continue  # Go back to input selection
                        
                    whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
                    if not whitelists:
                        self.console.print("No whitelists found", style=YELLOW)
                        continue  # Go back to input selection
                        
                    # Select whitelist to use
                    selected = inquirer.select(
                        message="Select whitelist to use:",
                        choices=whitelists,
                        style=style
                    ).execute()
                    
                    if not selected:
                        continue  # Go back to input selection
                        
                    # Load selected whitelist
                    whitelist_path = os.path.join(whitelist_dir, selected)
                    whitelist = self.parser.load_whitelist(whitelist_path)
                    if not whitelist:
                        continue  # Go back to input selection
                        
                elif filter_method == "manual":
                    # Load all bag files to get the union of topics
                    all_topics = set()
                    all_connections = {}
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Loading bag files for topic selection...", total=len(selected_files))
                        
                        for i, bag_file in enumerate(selected_files):
                            progress.update(task, description=f"Loading {i+1}/{len(selected_files)}: {os.path.basename(bag_file)}")
                            try:
                                topics, connections, _ = self.parser.load_bag(bag_file)
                                all_topics.update(topics)
                                all_connections.update(connections)
                                progress.advance(task)
                            except Exception as e:
                                self.console.print(f"Error loading {bag_file}: {str(e)}", style="red")
                                # Continue with other files
                    
                    if not all_topics:
                        self.console.print("No topics found in selected bag files", style="red")
                        continue  # Go back to input selection
                    
                    self.console.print(f"Found {len(all_topics)} unique topics across {len(selected_files)} bag files", style=GREEN)
                    whitelist = self._select_topics(list(all_topics), all_connections)
                    if not whitelist:
                        continue  # Go back to input selection
                
                # Create progress display for all files
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=False,
                ) as progress:
                    # Create tasks for all files
                    tasks = {}
                    for bag_file in selected_files:
                        rel_path = os.path.relpath(bag_file, input_path)
                        task = progress.add_task(
                            f"Waiting: {rel_path}",
                            total=100,
                            style="dim"
                        )
                        tasks[bag_file] = task
                    
                    # Process each file
                    for bag_file in selected_files:
                        rel_path = os.path.relpath(bag_file, input_path)
                        task = tasks[bag_file]
                        
                        try:
                            # Update task to show it's being processed
                            progress.update(task, description=f"Processing: {rel_path}", style="yellow")
                            
                            # Create output path
                            output_bag = os.path.splitext(bag_file)[0] + "_filtered.bag"
                            
                            # Process file with the selected whitelist
                            self._process_single_bag(
                                bag_file,
                                output_bag,
                                filter_method,
                                whitelist=whitelist,  # Pass the pre-selected whitelist
                                progress_context=progress,
                                task_id=task
                            )
                            
                            # Update task to show success with green color
                            progress.update(task, description=f"[green]✓ {rel_path}[/green]")
                            
                        except Exception as e:
                            # Update task to show failure with red color
                            progress.update(task, description=f"[red]✗ {rel_path}: {str(e)}[/red]")
                            logger.error(f"Error processing {bag_file}: {str(e)}", exc_info=True)
                        
                        # Update progress
                        progress.update(task, completed=100)
                        
                # Show final summary with color-coded results
                print_batch_filter_summary(self.console, tasks, progress)
                
                # Ask if user wants to continue or go back to main menu
                continue_action = inquirer.select(
                    message="What would you like to do next?",
                    choices=[
                        Choice(value="continue", name="1. Process more files"),
                        Choice(value="main", name="2. Return to main menu")
                    ],
                    style=style
                ).execute()
                
                if continue_action == "main":
                    return  # Return to main menu

    def _process_single_bag(self, input_bag: str, output_bag: str, filter_method: str, 
                          whitelist: Optional[List[str]] = None,
                          progress_context: Optional[Progress] = None, task_id: Optional[int] = None):
        """Process a single bag file"""
        # Load bag info
        if progress_context:
            # In batch mode, use the provided progress context
            progress_context.update(task_id, description=f"Loading: {os.path.basename(input_bag)}")
            self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
        else:
            # In single file mode, use independent loading animation
            with self.show_loading("Loading bag file...") as progress:
                progress.add_task(description="Loading...")
                self.topics, self.connections, self.time_range = self.parser.load_bag(input_bag)
        
        # Get filter parameters based on method if not provided
        if whitelist is None:
            if filter_method == "whitelist":
                # Get whitelist file
                whitelist_dir = "whitelists"
                if not os.path.exists(whitelist_dir):
                    self.console.print("No whitelists found", style="yellow")
                    return
                    
                whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
                if not whitelists:
                    self.console.print("No whitelists found", style="yellow")
                    return
                    
                # Select whitelist to use
                selected = inquirer.select(
                    message="Select whitelist to use:",
                    choices=whitelists,
                    style=style
                ).execute()
                
                if not selected:
                    return
                    
                # Load selected whitelist
                whitelist_path = os.path.join(whitelist_dir, selected)
                whitelist = self.parser.load_whitelist(whitelist_path)
                if not whitelist:
                    return
                    
            elif filter_method == "manual":
                whitelist = self._select_topics(self.topics, self.connections)
                if not whitelist:
                    return
                
        # Filter bag
        if progress_context:
            # In batch mode, use the provided progress context
            progress_context.update(task_id, description=f"Filtering: {os.path.basename(input_bag)}")
            self.parser.filter_bag(input_bag, output_bag, whitelist)
        else:
            # In single file mode, use independent loading animation
            with self.show_loading("Filtering bag file...") as progress:
                progress.add_task(description="Processing...")
                self.parser.filter_bag(input_bag, output_bag, whitelist)
        
        # Show results
        if not progress_context:  # Only show stats for single file processing
            print_filter_stats(self.console, input_bag, output_bag)
            
        
    def _run_whitelist_manager(self):
        """Run whitelist management workflow"""
        while True:
            action = inquirer.select(
                message="Whitelist Management:",
                choices=[
                    Choice(value="create", name="1. Create new whitelist"),
                    Choice(value="view", name="2. View whitelist"),
                    Choice(value="delete", name="3. Delete whitelist"),
                    Choice(value="back", name="4. Back")
                ],
                style=style
            ).execute()
            
            if action == "back":
                return
            elif action == "create":
                self._create_whitelist_workflow()
            elif action == "view":
                self._browse_whitelists()
            elif action == "delete":
                self._delete_whitelist()
    
    def _create_whitelist_workflow(self):
        """Create whitelist workflow"""
        # Get bag file
        input_bag = self.ask_for_bag("Enter bag file path to create whitelist from:")
        if not input_bag:
            return
            
        # Load bag file
        with self.show_loading("Loading bag file...") as progress:
            progress.add_task(description="Loading...")
            topics, connections, _ = self.parser.load_bag(input_bag)
        
        # Select topics
        selected_topics = self._select_topics(topics, connections)
        if not selected_topics:
            return
            
        # Save whitelist
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_path = f"whitelists/whitelist_{timestamp}.txt"
        
        use_default = inquirer.confirm(
            message=f"Use default path? ({default_path})",
            default=True,
            style=style
        ).execute()
        
        if use_default:
            output = default_path
        else:
            output = inquirer.filepath(
                message="Enter save path:",
                default="whitelists/my_whitelist.txt",
                validate=lambda x: x.endswith('.txt') or "File must be a .txt file",
                style=style
            ).execute()
            
            if not output:
                return
        
        # Save whitelist
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else '.', exist_ok=True)
        with open(output, 'w') as f:
            f.write("# Generated by rose cli-tool\n")
            f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            for topic in sorted(selected_topics):
                f.write(f"{topic}\n")
        
        self.console.print(f"\nSaved whitelist to: {output}", style="green")
        
        # Ask what to do next
        next_action = inquirer.select(
            message="What would you like to do next?",
            choices=[
                Choice(value="continue", name="1. Create another whitelist"),
                Choice(value="back", name="2. Back")
            ],
            style=style
        ).execute()
        
        if next_action == "continue":
            self._create_whitelist_workflow()
    
    def _browse_whitelists(self):
        """Browse and view whitelist files"""
        # Get all whitelist files
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style="yellow")
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style="yellow")
            return
            
        # Select whitelist to view
        selected = inquirer.select(
            message="Select whitelist to view:",
            choices=whitelists,
            style=style
        ).execute()
        
        if not selected:
            return
            
        # Show whitelist contents
        path = os.path.join(whitelist_dir, selected)
        with open(path) as f:
            content = f.read()
            
        self.console.print(f"\nWhitelist: {selected}", style="bold green")
        self.console.print("─" * 80)
        self.console.print(content)
    
    def _select_topics(self, topics: List[str], connections: dict) -> Optional[List[str]]:
        """Select topics manually"""
        topic_choices = sorted(topics)
        
        # Display usage instructions
        print_usage_instructions(self.console, is_fuzzy=True)
        
        selected_topics = inquirer.fuzzy(
            message="Select topics to include:",
            choices=topic_choices,
            multiselect=True,
            validate=lambda result: len(result) > 0,
            invalid_message="Please select at least one topic",
            transformer=lambda result: f"{len(result)} topic{'s' if len(result) > 1 else ''} selected",
            max_height="70%",
            instruction="",
            marker="● ",
            border=True,
            cycle=True,
            style=style
        ).execute()
        
        return selected_topics
    

        
    def _delete_whitelist(self):
        """Delete a whitelist file"""
        whitelist_dir = "whitelists"
        if not os.path.exists(whitelist_dir):
            self.console.print("No whitelists found", style=YELLOW)
            return
            
        whitelists = [f for f in os.listdir(whitelist_dir) if f.endswith('.txt')]
        if not whitelists:
            self.console.print("No whitelists found", style=YELLOW)
            return
            
        # Select whitelist to delete
        selected = inquirer.select(
            message="Select whitelist to delete:",
            choices=whitelists,
            style=style
        ).execute()
        
        if not selected:
            return
            
        # Confirm deletion
        if not inquirer.confirm(
            message=f"Are you sure you want to delete '{selected}'?",
            default=False,
            style=style
        ).execute():
            return
            
        # Delete the file
        path = os.path.join(whitelist_dir, selected)
        try:
            os.remove(path)
            self.console.print(f"\nDeleted whitelist: {selected}", style=GREEN)
        except Exception as e:
            self.console.print(f"\nError deleting whitelist: {str(e)}", style="red")

# Typer commands
@app.command()
def cli():
    """Interactive CLI mode with menu interface"""
    tool = CliTool()
    tool.run_cli()


def main():
    """Entry point for the CLI tool"""
    app()

if __name__ == "__main__":
    main() 