
import os
import glob
import pickle
from pathlib import Path
import typer
from typing import List, Tuple, Optional
from ..core.output import get_output
from ..core.cache import get_cache
from ..core.model import BagInfo
from ..tui.dialogs import ask_question
from ..tui.widgets.question import Answer

def select_bags_interactive(
    initial_input: Optional[List[str]] = None,
    default_build_index: Optional[bool] = None,
    allow_multiple: bool = True,
    require_index: bool = False,
    ignore_cache: bool = False,
) -> Tuple[List[str], bool]:
    """
    Interactive bag selection with cache prioritization and glob support.
    
    Args:
        initial_input: List of input patterns or paths provided by CLI args.
        default_build_index: Default value for build_index flag.
        allow_multiple: Whether to allow selecting multiple files.
        require_index: Whether to only show bags with message index.
        ignore_cache: Whether to ignore cached bags and go straight to picker.
        
    Returns:
        Tuple[List[str], bool]: (Selected bag files, key 'build_index' flag)
    """
    out = get_output()
    try:
        from ..tui.dialogs import ask_selection
        from ..tui.widgets.multi_selection import SelectionItem
    except ImportError:
        # Should not happen if app is installed correctly
        raise typer.Exit(1)

    # 0. If initial input provided, try to resolve it first
    resolved_files = []
    if initial_input:
        if len(initial_input) == 1 and os.path.isdir(initial_input[0]):
             # If exact directory, treat as start path for picker later, 
             # BUT user might want to load all bags in it?
             # For now, let's assume directory input implies "start here in picker"
             # unless we want to support "rose load ./dir/" -> load all.
             # Current logic: assume navigation.
             pass 
        else:
            for pattern in initial_input:
                matches = glob.glob(pattern)
                if matches:
                    resolved_files.extend(matches)
                elif os.path.exists(pattern):
                     resolved_files.append(pattern)
            
            # If we resolved files from args, we verify count if single select
            if resolved_files:
                if not allow_multiple and len(resolved_files) > 1:
                    out.warning(f"Input matches {len(resolved_files)} files but command requires single file.")
                    out.info("Starting interactive selection...")
                    resolved_files = [] # Discard and fall through to picker
                else:
                    return resolved_files, (default_build_index or False)

    # 1. Fetch Cached Bags
    cached_options = []
    if not ignore_cache:
        try:
            cache = get_cache()
            if hasattr(cache, 'cache_dir') and cache.cache_dir.exists():
                for pkl_path in cache.cache_dir.glob("*.pkl"):
                    try:
                        with open(pkl_path, 'rb') as f:
                            data = pickle.load(f)
                        
                        if isinstance(data, BagInfo):
                            if require_index and not data.has_message_index():
                                continue
                                
                            path = getattr(data, 'file_path', 'unknown')
                            size_mb = data.file_size / (1024*1024) if hasattr(data, 'file_size') else 0
                            name = f"{os.path.basename(path)} ({size_mb:.1f} MB)"
                            cached_options.append(SelectionItem(text=name, id=path))
                    except:
                        continue
        except Exception as e:
            # Ignore cache errors, fallback to picker
            pass

    # 2. Main Selection Loop (if no args resolved)
    
    # Define actions
    LOAD_NEW_VAL = "__LOAD_NEW__"
    
    choices = []
    if cached_options:
        choices.extend(cached_options)
    
    choices.append(SelectionItem(text="Load New File(s)...", id=LOAD_NEW_VAL))
    
    selected_values = []
    
    # If no cached bags, skip straight to file picker?
    # Maybe user wants to see "Load New" explicitly? 
    # If empty cache, just go to picker to save strict.
    if not cached_options:
        selected_values = [LOAD_NEW_VAL]
    else:
        out.print("Select bags to process (supports fuzzy search):")
        result = ask_selection(
            message="Select bags:",
            options=choices
        )
        # ask_selection returns list of IDs
        
        selected_values = result

    # Process Selection
    final_files = []
    launch_picker = False
    
    for val in selected_values:
        if val == LOAD_NEW_VAL:
            launch_picker = True
        elif val: # Valid cached path
            final_files.append(val)
            
    if launch_picker:
        # Launch File Picker Logic
        picker_files = _launch_file_picker(out, initial_input, allow_multiple)
        final_files.extend(picker_files)

    # De-duplicate
    final_files = list(set(final_files))
    
    if not final_files:
        raise typer.Exit(0)

    # 3. Confirmation & Index Prompt
    # Only if we used interactive picker (arg resolution returns early)
    
    # Double check standard single-select constraint (should be handled by picker/validator, but safety net)
    if not allow_multiple and len(final_files) > 1:
        out.error(f"Selected {len(final_files)} files but command requires single file.")
        raise typer.Exit(1)

    out.newline()
    out.section("Selected Bags")
    display_limit = 10
    for f in final_files[:display_limit]:
        out.print(f"  - {f}")
    if len(final_files) > display_limit:
        out.print(f"  ... and {len(final_files)-display_limit} more")
    
    # Check if all selected bags are already indexed in cache
    all_indexed = False
    try:
        cache = get_cache()
        indexed_count = 0
        for fpath in final_files:
            # We need to find the cache entry for this path
            # BagCacheManager keys are hashed paths
            bag_p = Path(fpath)
            if hasattr(cache, 'get_bag_analysis'):
                 info = cache.get_bag_analysis(bag_p)
                 if info and info.has_message_index():
                     indexed_count += 1
        
        if indexed_count == len(final_files) and len(final_files) > 0:
            all_indexed = True
    except:
        pass

    if all_indexed:
        out.info("All selected bags have message index. Loading with index enabled.")
        return final_files, True
    
    out.newline()
    choice_answer = ask_question(
        question="Do you want to build message index?",
        options=[
            Answer("Load (Quick Analysis)", "quick"),
            Answer("Load + Build Message Index (TUI Ready)", "index"),
            Answer("Cancel", "cancel"),
        ]
    )
    
    if not choice_answer or choice_answer.id == "cancel":
         out.info("Cancelled")
         raise typer.Exit(0)
    
    choice = choice_answer.id
    
    build_index = (choice == "index")
    return final_files, build_index

def _launch_file_picker(out, initial_input, allow_multiple):
    from InquirerPy import inquirer
    from InquirerPy.validator import Validator
    from prompt_toolkit.validation import ValidationError
    
    class GlobPathValidator(Validator):
        def __init__(self, allow_multiple=True):
            self.allow_multiple = allow_multiple

        def validate(self, document):
            text = document.text
            if os.path.isfile(text):
                return True
            
            matches = glob.glob(text)
            if matches:
                # If valid matches found
                if not self.allow_multiple and len(matches) > 1:
                    raise ValidationError(message=f"Ambiguous glob: matches {len(matches)} files. Please select a single specific file.")
                return True
            
            if not text:
                return False 
            raise ValidationError(message="Input must be a file or valid glob pattern matching files")

    start_path = "./"
    if initial_input and len(initial_input) == 1 and os.path.isdir(initial_input[0]):
         start_path = initial_input[0]
         if not start_path.endswith('/'):
             start_path += '/'
    
    out.print(f"Select bag file or enter glob pattern (Start: {start_path})")
    out.print("  [Tab]: Complete/Expand  [Enter]: Select")
    
    selected_path = inquirer.filepath(
        message="Bag/Glob:",
        default=start_path,
        validate=GlobPathValidator(allow_multiple=allow_multiple),
        only_files=False,
    ).execute()
    
    resolved = []
    if selected_path:
        matches = glob.glob(selected_path)
        if matches:
            resolved = matches
        elif os.path.isfile(selected_path):
            resolved = [selected_path]
        else:
             out.error(f"No files matched pattern: {selected_path}")
             raise typer.Exit(1)
             
    if not resolved:
        out.info("No file selected.")
        raise typer.Exit(0)
        
    return resolved
