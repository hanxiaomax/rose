import sys
from pathlib import Path
import os

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from roseApp.core.events import LogEvent, ProgressEvent, ResultEvent
from roseApp.core.pipeline import step_find_bags, step_load_bag, load_orchestrator, extract_orchestrator, compress_orchestrator

def test_events():
    print("Testing SDK Events...")
    
    print("\n--- Testing step_find_bags ---")
    gen = step_find_bags(["*.bag"]) 
    for event in gen:
        print(f"Event: {event}")

    print("\n--- Testing step_load_bag (Mocked) ---")
    dummy_path = Path("non_existent.bag")
    gen2 = step_load_bag(dummy_path)
    for event in gen2:
        print(f"Event: {event}")

    print("\n--- Testing extract_orchestrator (Mocked) ---")
    # This will fail to find bags but will execute the pipeline logic
    gen3 = extract_orchestrator(["*.bag"], ["topic1"], output_pattern="output_{timestamp}")
    for event in gen3:
        print(f"Event: {event}")

    print("\n--- Testing compress_orchestrator (Mocked) ---")
    gen4 = compress_orchestrator(["*.bag"], output_pattern="output_{timestamp}")
    for event in gen4:
        print(f"Event: {event}")

if __name__ == "__main__":
    test_events()
