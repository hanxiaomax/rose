
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
        from ..tui.dialogs import ask_multi_selection, ask_path
        from ..tui.widgets.question import Answer
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
                            cached_options.append(Answer(text=name, id=path))
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
    # Always add "Load new bag..." option at the end
    choices.append(Answer(text="Load new bag...", id=LOAD_NEW_VAL))
    
    if len(choices) == 1:
        selected_values = [LOAD_NEW_VAL]
    else:
        out.print("Select bag(s) to process:")
        
        if allow_multiple:
            # Multi-select mode
            result = ask_multi_selection(
                question="Select bags:",
                options=choices,
            )
            # ask_multi_selection returns list of Answer
            selected_values = [a.id for a in result] if result else []
        else:
            # Single-select mode - use Question widget
            result = ask_question(
                question="Select a bag:",
                options=choices,
            )
            # ask_question returns single Answer or None
            selected_values = [result.id] if result else []

    # Process Selection
    final_files = []
    cached_files = []  # Track files from cache (already loaded)
    launch_picker = False
    
    for val in selected_values:
        if val == LOAD_NEW_VAL:
            launch_picker = True
        elif val: # Valid cached path
            final_files.append(val)
            cached_files.append(val)  # Mark as from cache
            
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
        out.print(f"  - {out.format_path(f)}")
    if len(final_files) > display_limit:
        out.print(f"  ... and {len(final_files)-display_limit} more")
    
    # If ALL files are from cache, skip the load prompt entirely
    all_from_cache = set(final_files) == set(cached_files) and len(cached_files) > 0
    
    if all_from_cache:
        # Check if all cached bags have index
        all_indexed = False
        try:
            cache = get_cache()
            indexed_count = 0
            for fpath in final_files:
                bag_p = Path(fpath)
                if hasattr(cache, 'get_bag_analysis'):
                    info = cache.get_bag_analysis(bag_p)
                    if info and info.has_message_index():
                        indexed_count += 1
            
            if indexed_count == len(final_files):
                all_indexed = True
        except:
            pass
        
        out.info("Using cached bags (already loaded).")
        return final_files, all_indexed
    
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
    # Use Textual PathInput
    from ..tui.dialogs import ask_bags
    
    start_path = "./"
    if initial_input and len(initial_input) == 1 and os.path.isdir(initial_input[0]):
         start_path = initial_input[0]
         if not start_path.endswith('/'):
             start_path += '/'
    
    picker_files = ask_bags(
        message=f"Enter path (Tab to complete) [Start: {start_path}]", 
        start_path=start_path, 
        allow_multiple=allow_multiple
    )

    if not picker_files:
        out.info("Cancelled")
        raise typer.Exit(0)
    
    return picker_files
