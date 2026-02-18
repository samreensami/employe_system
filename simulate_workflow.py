#!/usr/bin/env python3

import os
import time
from skills.filesystem_watcher import FilesystemWatcher
from skills.task_processor import TaskProcessorMonitor

def simulate_full_workflow():
    print("Simulating the full workflow...")
    
    # Define paths
    inbox_path = "obsidian_vault/inbox"
    needs_action_path = "obsidian_vault/needs_action"
    plans_path = "obsidian_vault/Plans"
    
    # Clean up any existing test files
    for path in [f"{needs_action_path}/test_task_metadata.md", f"{inbox_path}/test_task.md", f"{plans_path}/PLAN_test_task_metadata.md"]:
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed existing file: {path}")
    
    # Step 1: Create the initial task file in inbox
    task_content = "Task: Research top 3 MCP servers for Gmail integration and list their features."
    with open(f"{inbox_path}/test_task.md", 'w') as f:
        f.write(task_content)
    print("Step 1: Created test_task.md in inbox")
    
    # Step 2: Start the task processor monitor first
    task_processor = TaskProcessorMonitor(needs_action_path, plans_path)
    task_processor.start_monitoring()
    print("Step 2: Started task processor monitor")
    
    # Give it a moment to start monitoring
    time.sleep(1)
    
    # Step 3: Now create the metadata file via the filesystem watcher
    watcher = FilesystemWatcher(inbox_path, needs_action_path)
    watcher.handle_new_file(f"{inbox_path}/test_task.md")
    print("Step 3: Filesystem watcher created metadata file in needs_action")
    
    # Wait for the task processor to detect and process the new file
    time.sleep(3)
    
    # Stop monitoring
    task_processor.stop_monitoring()
    
    print("Step 4: Task processor should have created plan in Plans folder")
    
    # Check results
    print("\nResults:")
    needs_action_files = os.listdir(needs_action_path) if os.path.exists(needs_action_path) else []
    plans_files = os.listdir(plans_path) if os.path.exists(plans_path) else []
    
    print(f"Files in needs_action: {needs_action_files}")
    print(f"Files in Plans: {plans_files}")
    
    # Show the plan content if it was created
    if plans_files:
        plan_file = plans_files[0]
        with open(f"{plans_path}/{plan_file}", 'r') as f:
            content = f.read()
        print(f"\nContent of {plan_file}:")
        print(content)
    else:
        print("\nNo plan file was created!")

if __name__ == "__main__":
    simulate_full_workflow()