import threading
import time
import sys
import os
# Add the skills directory to the path so we can import the modules
sys.path.append(os.path.dirname(__file__))
from filesystem_watcher import FilesystemWatcher
from task_processor import TaskProcessorMonitor


class SkillManager:
    """
    Master skill coordinator that manages all other skills and watchers.
    """
    
    def __init__(self):
        self.skills = {}
        self.threads = {}
        self.running = False
        
    def register_skill(self, name: str, skill):
        """
        Register a skill with the manager.
        """
        self.skills[name] = skill
        print(f"Registered skill: {name}")
    
    def start_skill(self, name: str):
        """
        Start a registered skill in a separate thread.
        """
        if name not in self.skills:
            raise ValueError(f"Skill '{name}' not registered")
        
        skill = self.skills[name]
        if hasattr(skill, 'start_monitoring'):
            # For watcher-type skills
            thread = threading.Thread(target=self._run_watcher, args=(skill, name))
        else:
            # For other types of skills
            thread = threading.Thread(target=skill.run)  # Assuming skill has a run method
        
        thread.daemon = True
        thread.start()
        self.threads[name] = thread
        print(f"Started skill: {name}")
    
    def _run_watcher(self, watcher, name):
        """
        Helper method to run watcher skills.
        """
        try:
            watcher.start_monitoring()
            # Keep the thread alive
            while self.running:
                time.sleep(1)
        except Exception as e:
            print(f"Error running skill {name}: {e}")
    
    def start_all_skills(self):
        """
        Start all registered skills.
        """
        self.running = True
        for name in self.skills:
            self.start_skill(name)
        print("All skills started")
    
    def stop_all_skills(self):
        """
        Stop all running skills.
        """
        self.running = False
        # Give threads a moment to stop gracefully
        time.sleep(1)
        print("All skills stopped")
    
    def setup_default_watchers(self):
        """
        Set up the default watchers for the AI Employee.
        """
        # Create the filesystem watcher for inbox
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))  # Add skills directory to path
        from filesystem_watcher import FilesystemWatcher
        inbox_watcher = FilesystemWatcher(
            monitored_path="../obsidian_vault/inbox",
            output_path="../obsidian_vault/Needs_Action"
        )
        self.register_skill("inbox_watcher", inbox_watcher)
        
        # Create the task processor monitor
        from task_processor import TaskProcessorMonitor
        task_processor = TaskProcessorMonitor(
            needs_action_path="../obsidian_vault/Needs_Action",
            plans_path="../obsidian_vault/Plans"
        )
        self.register_skill("task_processor", task_processor)


def main():
    """
    Main function to run the skill manager.
    """
    manager = SkillManager()
    
    # Set up default watchers
    manager.setup_default_watchers()
    
    try:
        # Start all skills
        manager.start_all_skills()
        
        print("AI Employee Zoya is now operational!")
        print("Skills active:")
        print("- Inbox monitoring: Watching for new tasks")
        print("- Task processing: Creating plans from tasks")
        print("\nPress Ctrl+C to stop the agent.")
        
        # Keep the main thread alive
        while manager.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping AI Employee Zoya...")
        manager.stop_all_skills()
        print("Agent stopped.")


if __name__ == "__main__":
    main()