"""
Odoo Watcher - Monitors approved actions and posts them to Odoo.

This watcher monitors the /Approved/odoo/ folder for approved accounting
actions (invoices, bills, payments) and posts them to Odoo. It integrates
with the Human-in-the-Loop workflow.

Features:
    - Monitors /Approved/odoo/ for new approval files
    - Posts approved invoices, bills, and payments
    - Moves completed actions to /Done/
    - Logs all operations to audit trail
    - Integrates with financial auditor for CEO briefings
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from skills.base_watcher import BaseWatcher

# Configure logging
logger = logging.getLogger(__name__)

# Try to import Odoo components
try:
    from skills.odoo_mcp_server import OdooMCPServer, OdooConfig
    ODOO_AVAILABLE = True
except ImportError:
    ODOO_AVAILABLE = False
    logger.warning("Odoo MCP Server not available")


class OdooApprovalHandler(FileSystemEventHandler):
    """
    Handles file system events for Odoo approval files.
    """

    def __init__(self, watcher: 'OdooWatcher'):
        self.watcher = watcher

    def on_created(self, event):
        """Handle new approval file."""
        if not event.is_directory and event.src_path.endswith('.md'):
            filename = os.path.basename(event.src_path)
            if filename.startswith('ODOO_'):
                logger.info(f"New Odoo approval detected: {filename}")
                time.sleep(1)  # Brief delay to ensure file is fully written
                self.watcher.process_approval_file(event.src_path)

    def on_moved(self, event):
        """Handle file moved into approved folder."""
        if not event.is_directory and event.dest_path.endswith('.md'):
            filename = os.path.basename(event.dest_path)
            if filename.startswith('ODOO_'):
                logger.info(f"Odoo approval file moved in: {filename}")
                time.sleep(1)
                self.watcher.process_approval_file(event.dest_path)


class OdooWatcher(BaseWatcher):
    """
    Watches for approved Odoo actions and processes them.

    This watcher:
    1. Monitors /Approved/odoo/ for approval files
    2. Parses the approval file to extract action details
    3. Calls the appropriate Odoo MCP method to post the document
    4. Moves completed files to /Done/
    5. Logs all actions to audit trail
    """

    def __init__(
        self,
        vault_path: str = "obsidian_vault",
        check_interval: int = 10
    ):
        """
        Initialize Odoo Watcher.

        Args:
            vault_path: Path to Obsidian vault
            check_interval: Seconds between manual checks
        """
        self.vault_path = Path(vault_path)
        self.approved_path = self.vault_path / "Approved" / "odoo"
        self.done_path = self.vault_path / "Done"
        self.logs_path = Path("logs")

        super().__init__(str(self.approved_path))

        self.check_interval = check_interval
        self.mcp_server: Optional[OdooMCPServer] = None
        self.observer: Optional[Observer] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Ensure directories exist
        self.ensure_directory_exists(str(self.approved_path))
        self.ensure_directory_exists(str(self.done_path))
        self.ensure_directory_exists(str(self.logs_path))

        logger.info(f"OdooWatcher initialized. Monitoring: {self.approved_path}")

    def _initialize_mcp_server(self) -> bool:
        """Initialize connection to Odoo MCP Server."""
        if not ODOO_AVAILABLE:
            logger.error("Odoo MCP Server not available")
            return False

        try:
            # Try to load config from environment
            self.mcp_server = OdooMCPServer()

            if self.mcp_server.connect():
                logger.info("Connected to Odoo MCP Server")
                return True
            else:
                logger.error("Failed to connect to Odoo MCP Server")
                return False

        except Exception as e:
            logger.error(f"Error initializing Odoo MCP Server: {e}")
            return False

    def process_approval_file(self, filepath: str) -> Dict:
        """
        Process an approved Odoo action file.

        Args:
            filepath: Path to the approval file

        Returns:
            Processing result dictionary
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return {'success': False, 'error': 'File not found'}

        try:
            content = filepath.read_text()

            # Parse the YAML frontmatter
            action_type = self._extract_field(content, 'action')
            odoo_id = int(self._extract_field(content, 'odoo_id'))
            amount = float(self._extract_field(content, 'amount') or 0)

            logger.info(f"Processing: {action_type} for Odoo ID {odoo_id}")

            # Ensure MCP server is connected
            if not self.mcp_server or not self.mcp_server.connected:
                if not self._initialize_mcp_server():
                    return {'success': False, 'error': 'Cannot connect to Odoo'}

            # Process based on action type
            result = self._execute_odoo_action(action_type, odoo_id)

            if result.get('success'):
                # Move to Done folder
                done_file = self.done_path / filepath.name
                filepath.rename(done_file)

                # Log to audit
                self._log_action(action_type, odoo_id, amount, result)

                logger.info(f"Successfully processed: {filepath.name}")
            else:
                logger.error(f"Failed to process: {filepath.name} - {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            return {'success': False, 'error': str(e)}

    def _extract_field(self, content: str, field: str) -> Optional[str]:
        """Extract a field value from YAML frontmatter."""
        pattern = rf'^{field}:\s*(.+)$'
        match = re.search(pattern, content, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _execute_odoo_action(self, action_type: str, odoo_id: int) -> Dict:
        """Execute the appropriate Odoo action."""
        try:
            if action_type in ['invoice_post', 'bill_post']:
                return self.mcp_server.post_invoice(odoo_id)
            elif action_type == 'payment_post':
                return self.mcp_server.post_payment(odoo_id)
            else:
                return {'success': False, 'error': f'Unknown action type: {action_type}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _log_action(self, action_type: str, odoo_id: int, amount: float, result: Dict):
        """Log the action to audit trail."""
        try:
            audit_file = self.logs_path / "odoo_audit.json"

            # Load existing log
            entries = []
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    entries = json.load(f)

            # Add new entry
            entries.append({
                'timestamp': datetime.now().isoformat(),
                'action_type': action_type,
                'odoo_id': odoo_id,
                'amount': amount,
                'result': result.get('success'),
                'message': result.get('message', result.get('error', ''))
            })

            # Keep last 1000 entries
            entries = entries[-1000:]

            with open(audit_file, 'w') as f:
                json.dump(entries, f, indent=2)

        except Exception as e:
            logger.error(f"Error logging action: {e}")

    def handle_new_file(self, file_path: str):
        """Handle a newly detected file (implements BaseWatcher interface)."""
        logger.info(f"Odoo approval processed: {file_path}")

    def start_monitoring(self):
        """Start monitoring for approved Odoo actions."""
        if self.is_running:
            logger.warning("Odoo watcher is already running")
            return

        # Initialize MCP server
        if not self._initialize_mcp_server():
            logger.warning("Could not connect to Odoo - will retry on file detection")

        self.is_running = True
        self._stop_event.clear()

        # Start file system observer
        self.observer = Observer()
        handler = OdooApprovalHandler(self)
        self.observer.schedule(handler, str(self.approved_path), recursive=False)
        self.observer.start()

        # Start background thread for periodic checks
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"Started Odoo watcher (monitoring {self.approved_path})")

    def _monitoring_loop(self):
        """Background monitoring loop for periodic checks."""
        while not self._stop_event.is_set():
            try:
                # Process any existing files that might have been missed
                self._process_existing_files()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            self._stop_event.wait(self.check_interval)

    def _process_existing_files(self):
        """Process any existing approval files."""
        for filepath in self.approved_path.glob("ODOO_*.md"):
            self.process_approval_file(str(filepath))

    def stop_monitoring(self):
        """Stop monitoring."""
        if not self.is_running:
            return

        logger.info("Stopping Odoo watcher...")
        self._stop_event.set()

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        if self.mcp_server:
            self.mcp_server.disconnect()

        self.is_running = False
        logger.info("Odoo watcher stopped")

    def get_status(self) -> Dict:
        """Get watcher status."""
        pending_count = len(list(self.approved_path.glob("ODOO_*.md")))

        return {
            'running': self.is_running,
            'connected': self.mcp_server.connected if self.mcp_server else False,
            'pending_approvals': pending_count,
            'approved_path': str(self.approved_path)
        }


def main():
    """Test the Odoo watcher."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Odoo Watcher - Test Mode")
    print("=" * 40)

    watcher = OdooWatcher()

    print("\nStarting Odoo Watcher...")
    print(f"Monitoring: {watcher.approved_path}")
    print("Press Ctrl+C to stop\n")

    try:
        watcher.start_monitoring()

        while True:
            time.sleep(1)
            status = watcher.get_status()
            print(f"\rStatus: {'Running' if status['running'] else 'Stopped'} | "
                  f"Connected: {status['connected']} | "
                  f"Pending: {status['pending_approvals']}", end='')

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        watcher.stop_monitoring()
        print("Odoo Watcher stopped")


if __name__ == "__main__":
    main()
