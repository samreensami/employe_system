import os

def update_dashboard():
    # Define folder paths
    inbox_path = "obsidian_vault/inbox"
    needs_action_path = "obsidian_vault/needs_action"
    plans_path = "obsidian_vault/Plans"
    approved_path = "obsidian_vault/Approved"
    done_path = "obsidian_vault/Done"
    
    # Count files in each folder
    pending_count = len([f for f in os.listdir(inbox_path) if f.endswith('.md')])
    needs_action_count = len([f for f in os.listdir(needs_action_path) if f.endswith('.md')])
    plans_count = len([f for f in os.listdir(plans_path) if f.endswith('.md')])
    approved_count = len([f for f in os.listdir(approved_path) if f.endswith('.md')])
    done_count = len([f for f in os.listdir(done_path) if f.endswith('.md')])
    
    # Calculate total pending (inbox + needs_action + plans)
    total_pending = pending_count + needs_action_count + plans_count
    
    # Create dashboard content
    dashboard_content = f"""# Business Dashboard

## Summary
This dashboard provides an overview of business operations and key metrics.

## Tasks Status
- Pending: {total_pending}
- Approved: {approved_count}
- Done: {done_count}

## Recent Activity
- Last Updated: {get_current_date()}
- Next Review: {get_next_day()}

## Key Metrics
- Performance Score: 85%
- Efficiency Rating: High
- Priority Items: {total_pending + approved_count + done_count}
"""

    # Write to dashboard file
    with open("Dashboard.md", 'w') as f:
        f.write(dashboard_content)
    
    print("Dashboard updated successfully!")
    print(f"Current counts - Pending: {total_pending}, Approved: {approved_count}, Done: {done_count}")


def get_current_date():
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')


def get_next_day():
    from datetime import datetime, timedelta
    next_day = datetime.now() + timedelta(days=1)
    return next_day.strftime('%Y-%m-%d')


if __name__ == "__main__":
    update_dashboard()