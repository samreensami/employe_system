#!/usr/bin/env python3

import os
import time
from skills.filesystem_watcher import FilesystemWatcher
from skills.task_processor import TaskProcessorMonitor
from skills.execution_engine import ExecutionEngine
from skills.social_manager import SocialManager

def run_full_linkedin_workflow():
    print("Running full LinkedIn task workflow...")
    
    # Define paths
    inbox_path = "obsidian_vault/inbox"
    needs_action_path = "obsidian_vault/needs_action"
    plans_path = "obsidian_vault/Plans"
    approved_path = "obsidian_vault/Approved"
    done_path = "obsidian_vault/Done"
    
    # Ensure the LinkedIn task file exists
    linkedin_task_file = f"{inbox_path}/linkedin_update_task.md"
    if not os.path.exists(linkedin_task_file):
        with open(linkedin_task_file, 'w') as f:
            f.write("Task: Post a business update on LinkedIn about our successful Gold Tier deployment.")
        print("Created LinkedIn task file in inbox")
    
    # Start the task processor monitor first
    task_processor = TaskProcessorMonitor(needs_action_path, plans_path)
    task_processor.start_monitoring()
    print("Started task processor monitor")
    
    # Give it a moment to start monitoring
    time.sleep(1)
    
    # Now create the metadata file via the filesystem watcher
    watcher = FilesystemWatcher(inbox_path, needs_action_path)
    watcher.handle_new_file(linkedin_task_file)
    print("Filesystem watcher created metadata file in needs_action")
    
    # Wait for the task processor to detect and process the new file
    time.sleep(3)
    
    # Stop monitoring
    task_processor.stop_monitoring()
    
    # Check if plan was created
    plan_files = [f for f in os.listdir(plans_path) if f.startswith("PLAN_") and "linkedin" in f.lower()]
    if plan_files:
        plan_file = plan_files[0]
        print(f"Plan created: {plan_file}")
        
        # Move the plan to approved to trigger execution
        approved_plan_path = os.path.join(approved_path, plan_file)
        os.rename(os.path.join(plans_path, plan_file), approved_plan_path)
        print(f"Moved plan to approved: {plan_file}")
        
        # Execute the approved plan
        execution_engine = ExecutionEngine(approved_path, done_path)
        
        # Find the approved plan and execute it
        approved_files = [f for f in os.listdir(approved_path) if f.startswith("PLAN_")]
        for approved_file in approved_files:
            approved_file_path = os.path.join(approved_path, approved_file)
            execution_engine.execute_plan(approved_file_path)
            print(f"Executed plan: {approved_file}")
        
        # Generate the LinkedIn post
        social_manager = SocialManager()
        post_content = social_manager.generate_linkedin_post("Post a business update on LinkedIn about our successful Gold Tier deployment.")
        social_manager.save_post_draft(post_content, os.path.join(done_path, "linkedin_post_draft.md"))
        print("Generated and saved LinkedIn post draft to Done folder")
        
    else:
        print("No LinkedIn plan file was created!")
        
        # Check all plan files to see what was created
        all_plans = os.listdir(plans_path) if os.path.exists(plans_path) else []
        print(f"All plan files: {all_plans}")

if __name__ == "__main__":
    run_full_linkedin_workflow()