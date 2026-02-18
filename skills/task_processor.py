import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime


class TaskProcessor:
    """
    Processes tasks in the Needs_Action folder and creates plans in the Plans folder.
    """
    
    def __init__(self, needs_action_path: str, plans_path: str):
        self.needs_action_path = needs_action_path
        self.plans_path = plans_path
        self.processed_files = set()
        
        # Ensure directories exist
        os.makedirs(self.needs_action_path, exist_ok=True)
        os.makedirs(self.plans_path, exist_ok=True)
    
    def process_task_file(self, task_file_path: str):
        """
        Process a task file from Needs_Action and create a plan in Plans.
        """
        if task_file_path in self.processed_files:
            return
            
        self.processed_files.add(task_file_path)
        
        # Extract task name from file path
        task_filename = os.path.basename(task_file_path)
        task_name = os.path.splitext(task_filename)[0]
        
        # Create plan filename
        plan_filename = f"PLAN_{task_name}.md"
        plan_path = os.path.join(self.plans_path, plan_filename)
        
        # Read the task content
        with open(task_file_path, 'r', encoding='utf-8') as f:
            task_content = f.read()
        
        # Create the plan content
        plan_content = f"""# PLAN_{task_name}

## Original Task Content:
{task_content}

## Task Analysis
- [ ] Analyze the requirements
- [ ] Identify resources needed
- [ ] Determine potential challenges

## Proposed Action
- [ ] Define specific steps to complete the task
- [ ] Assign responsibilities if needed
- [ ] Set timeline for completion

## Status
- [ ] Pending
- [ ] In Progress
- [ ] Completed

---
*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Write the plan file
        with open(plan_path, 'w', encoding='utf-8') as f:
            f.write(plan_content)
        
        print(f"Created plan: {plan_filename}")
        
        # Optionally, mark the original task as processed by moving it or renaming it
        # For now, we'll just create the plan alongside the original task file


class TaskProcessingHandler(FileSystemEventHandler):
    """
    Event handler for processing new task files in Needs_Action.
    """
    
    def __init__(self, processor: TaskProcessor):
        self.processor = processor
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            print(f"New task detected in Needs_Action: {os.path.basename(event.src_path)}")
            self.processor.process_task_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            # Handle modifications too, in case a file is created empty and then filled
            if event.src_path not in self.processor.processed_files:
                print(f"Modified task detected in Needs_Action: {os.path.basename(event.src_path)}")
                self.processor.process_task_file(event.src_path)


class TaskProcessorMonitor:
    """
    Monitors the Needs_Action folder and processes new task files.
    """
    
    def __init__(self, needs_action_path: str, plans_path: str):
        self.needs_action_path = needs_action_path
        self.plans_path = plans_path
        self.processor = TaskProcessor(needs_action_path, plans_path)
        self.observer = Observer()
        self.handler = TaskProcessingHandler(self.processor)
    
    def start_monitoring(self):
        """
        Start monitoring the Needs_Action folder for new task files.
        """
        self.observer.schedule(self.handler, self.needs_action_path, recursive=False)
        self.observer.start()
        print(f"Started monitoring {self.needs_action_path} for task processing...")
        
    def stop_monitoring(self):
        """
        Stop monitoring the Needs_Action folder.
        """
        self.observer.stop()
        self.observer.join()
        print("Stopped task processing monitor.")