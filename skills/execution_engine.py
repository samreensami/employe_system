import os
import re
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ExecutionEngine:
    """
    Executes approved plans by performing the required actions.
    For now, simulates sending an email by logging the final research.
    """

    def __init__(self, approved_path: str, done_path: str):
        self.approved_path = approved_path
        self.done_path = done_path
        self.executed_plans = set()

        # Ensure directories exist
        os.makedirs(self.approved_path, exist_ok=True)
        os.makedirs(self.done_path, exist_ok=True)

    def execute_plan(self, plan_file_path: str):
        """
        Execute a plan from the Approved folder.
        For now, extracts research content and simulates sending an email.
        """
        if plan_file_path in self.executed_plans:
            return

        self.executed_plans.add(plan_file_path)

        # Extract plan name from file path
        plan_filename = os.path.basename(plan_file_path)
        plan_name = os.path.splitext(plan_filename)[0]

        # Read the plan content
        with open(plan_file_path, 'r', encoding='utf-8') as f:
            plan_content = f.read()

        # Extract the original task content (this would contain the research request)
        original_task_match = re.search(r'## Original Task Content:\n(.+?)\n## Task Analysis', plan_content, re.DOTALL)
        original_task = original_task_match.group(1).strip() if original_task_match else "Task content not found"

        # Simulate performing the research task
        print(f"Executing plan: {plan_name}")
        print(f"Original task: {original_task}")
        
        # For demonstration purposes, we'll simulate research results
        simulated_research_results = self._perform_research_simulation(original_task)
        
        # Simulate sending an email with the research results
        self._send_email_simulation(simulated_research_results, plan_name)
        
        # Move the executed plan to the Done folder
        done_plan_path = os.path.join(self.done_path, plan_filename)
        os.rename(plan_file_path, done_plan_path)
        
        print(f"Plan {plan_name} executed and moved to Done folder.")
        
        # Create a log entry
        self._create_execution_log(plan_name, original_task, simulated_research_results)

    def _perform_research_simulation(self, task_description: str):
        """
        Simulate performing research based on the task description.
        """
        # This is a simplified simulation - in a real system, this would perform actual research
        if "Gmail integration" in task_description and "MCP servers" in task_description:
            return """
Top 3 MCP Servers for Gmail Integration:

1. **Zimbra Collaboration Suite**
   - Features: Full email/calendar/groupware solution, Gmail-like interface, strong admin controls
   - Integration: IMAP/POP support, Google Workspace sync options
   - Pros: Open source community edition, enterprise features available
   - Cons: Resource intensive, complex setup

2. **Mailcow**
   - Features: Docker-based email suite, modern web interface, comprehensive admin panel
   - Integration: Standard email protocols, can connect to Gmail accounts
   - Pros: Easy deployment with Docker, frequent updates, active community
   - Cons: Requires Docker knowledge, limited native Google integration

3. **Kolab Server**
   - Features: Enterprise groupware solution, strong security focus, GDPR compliance
   - Integration: IMAP/CalDAV/CardDAV protocols, can sync with Gmail
   - Pros: Excellent privacy controls, modular architecture
   - Cons: Complex administration, steeper learning curve
"""
        else:
            return f"Simulated research results for: {task_description}"

    def _send_email_simulation(self, research_results: str, plan_name: str):
        """
        Simulate sending an email with research results.
        """
        print(f"SIMULATED EMAIL SENT:")
        print(f"To: manager@company.com")
        print(f"Subject: Research Results - {plan_name.replace('PLAN_', '').replace('_', ' ').title()}")
        print(f"Body:\n{research_results}")
        print("--- Email simulation complete ---")

    def _create_execution_log(self, plan_name: str, original_task: str, research_results: str):
        """
        Create an execution log for the completed task.
        """
        log_entry = f"""# Execution Log: {plan_name}

**Execution Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Original Task:** {original_task}

**Research Results:**
{research_results}

---
*Execution completed by AI Employee Zoya*
"""

        log_filename = f"{plan_name}_execution_log.md"
        log_path = os.path.join(self.done_path, log_filename)
        
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(log_entry)

        print(f"Execution log created: {log_filename}")


class ExecutionHandler(FileSystemEventHandler):
    """
    Event handler for executing approved plans.
    """

    def __init__(self, execution_engine: ExecutionEngine):
        self.execution_engine = execution_engine

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            print(f"New approved plan detected: {os.path.basename(event.src_path)}")
            self.execution_engine.execute_plan(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.md'):
            print(f"Approved plan moved for execution: {os.path.basename(event.dest_path)}")
            self.execution_engine.execute_plan(event.dest_path)


class ExecutionMonitor:
    """
    Monitors the Approved folder and executes plans when they appear.
    """

    def __init__(self, approved_path: str, done_path: str):
        self.approved_path = approved_path
        self.done_path = done_path
        self.execution_engine = ExecutionEngine(approved_path, done_path)
        self.observer = Observer()
        self.handler = ExecutionHandler(self.execution_engine)

    def start_monitoring(self):
        """
        Start monitoring the Approved folder for new plan files.
        """
        self.observer.schedule(self.handler, self.approved_path, recursive=False)
        self.observer.start()
        print(f"Started monitoring {self.approved_path} for plan execution...")

    def stop_monitoring(self):
        """
        Stop monitoring the Approved folder.
        """
        self.observer.stop()
        self.observer.join()
        print("Stopped execution monitor.")