from skills.execution_engine import ExecutionEngine
import os

# Define paths
approved_path = "obsidian_vault/Approved"
done_path = "obsidian_vault/Done"

# Create execution engine
engine = ExecutionEngine(approved_path, done_path)

# Find and execute any plan in the approved folder
approved_files = [f for f in os.listdir(approved_path) if f.endswith('.md')]
if approved_files:
    plan_file = os.path.join(approved_path, approved_files[0])
    print(f"Found plan file: {plan_file}")
    engine.execute_plan(plan_file)
    print("Plan executed successfully!")
else:
    print("No plan files found in Approved folder")