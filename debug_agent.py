import os
import sys
import traceback
from skills.filesystem_watcher import FilesystemWatcher
from skills.task_processor import TaskProcessorMonitor

def main():
    # Define paths
    inbox_path = "obsidian_vault/inbox"
    needs_action_path = "obsidian_vault/needs_action"
    plans_path = "obsidian_vault/Plans"

    try:
        # Create the watcher instance for inbox
        watcher = FilesystemWatcher(inbox_path, needs_action_path)
        
        # Create the task processor monitor
        task_processor = TaskProcessorMonitor(needs_action_path, plans_path)

        # Start monitoring
        watcher.start_monitoring()
        task_processor.start_monitoring()
        print("AI Employee Zoya is now monitoring the inbox and processing tasks...")
        print("Press Ctrl+C to stop the agent.")

        # Keep the script running
        import time
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    main()