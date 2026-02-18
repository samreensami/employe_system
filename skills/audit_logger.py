import json
import os
from datetime import datetime
from enum import Enum


class ActionType(Enum):
    FILE_CREATED = "file_created"
    FILE_MOVED = "file_moved"
    FILE_PROCESSED = "file_processed"
    PLAN_GENERATED = "plan_generated"
    TASK_EXECUTED = "task_executed"
    PAYMENT_APPROVAL = "payment_approval"
    CONTACT_INTERACTION = "contact_interaction"
    SYSTEM_ERROR = "system_error"
    SECURITY_CHECK = "security_check"


class AuditLogger:
    """
    Logs all actions in JSON format to /logs/audit_log.json
    """
    
    def __init__(self, log_path="logs/audit_log.json"):
        self.log_path = log_path
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
    def log_action(self, action_type: ActionType, actor: str, status: str, details: dict = None):
        """
        Log an action to the audit log
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type.value,
            "actor": actor,
            "status": status,
            "details": details or {}
        }
        
        # Read existing log entries
        existing_logs = []
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        existing_logs = json.loads(content)
                        if not isinstance(existing_logs, list):
                            existing_logs = [existing_logs]
            except (json.JSONDecodeError, ValueError):
                existing_logs = []
        
        # Append new log entry
        existing_logs.append(log_entry)
        
        # Write back to file
        with open(self.log_path, 'w', encoding='utf-8') as f:
            json.dump(existing_logs, f, indent=2)
        
        return log_entry
    
    def log_file_operation(self, operation: str, file_path: str, actor: str, status: str = "success", additional_details: dict = None):
        """
        Convenience method to log file operations
        """
        details = {
            "file_path": file_path,
            "operation": operation
        }
        if additional_details:
            details.update(additional_details)
        
        action_type = ActionType.FILE_CREATED if operation == "created" else \
                     ActionType.FILE_MOVED if operation == "moved" else \
                     ActionType.FILE_PROCESSED if operation == "processed" else \
                     ActionType.SYSTEM_ERROR if status == "error" else \
                     ActionType.FILE_MOVED  # default fallback
        
        return self.log_action(action_type, actor, status, details)
    
    def log_security_event(self, event_type: str, actor: str, status: str = "alert", details: dict = None):
        """
        Log a security-related event
        """
        security_details = {
            "event_type": event_type,
            "security_relevant": True
        }
        if details:
            security_details.update(details)
        
        return self.log_action(ActionType.SECURITY_CHECK, actor, status, security_details)
    
    def log_payment_activity(self, amount: float, description: str, actor: str, status: str = "pending_approval"):
        """
        Log payment-related activities
        """
        details = {
            "amount": amount,
            "description": description,
            "requires_approval": amount > 100  # Based on Company_Handbook.md Section 6.4
        }
        
        action_type = ActionType.PAYMENT_APPROVAL
        return self.log_action(action_type, actor, status, details)
    
    def log_contact_interaction(self, contact_info: str, interaction_type: str, actor: str, status: str = "pending_approval"):
        """
        Log contact interaction activities
        """
        details = {
            "contact_info": contact_info,
            "interaction_type": interaction_type,
            "requires_approval": True  # All new contact interactions require approval per handbook
        }
        
        action_type = ActionType.CONTACT_INTERACTION
        return self.log_action(action_type, actor, status, details)


def main():
    """Example usage of the audit logger"""
    logger = AuditLogger()
    
    # Example log entries
    logger.log_action(ActionType.FILE_CREATED, "AI_Employee_Zoya", "success", {
        "file_path": "obsidian_vault/inbox/new_task.md",
        "task_description": "Research project"
    })
    
    logger.log_payment_activity(150.00, "AWS Service Upgrade", "AI_Employee_Zoya", "pending_approval")
    
    logger.log_contact_interaction("vendor@example.com", "email", "AI_Employee_Zoya", "pending_approval")
    
    print(f"Audit log entries created in {logger.log_path}")


if __name__ == "__main__":
    main()