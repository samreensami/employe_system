import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path
from skills.filesystem_watcher import FilesystemWatcher
from skills.task_processor import TaskProcessorMonitor
from skills.execution_engine import ExecutionMonitor
from skills.health_monitor import HealthMonitor
from skills.persistence_loop import PersistenceLoop

# Optional Gmail watcher - graceful handling if not configured
try:
    from skills.gmail_watcher import GmailWatcher
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Optional WhatsApp watcher - graceful handling if not configured
try:
    from skills.whatsapp_watcher import WhatsAppWatcher
    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False

# Optional Odoo watcher - graceful handling if not configured
try:
    from skills.odoo_watcher import OdooWatcher
    ODOO_AVAILABLE = True
except ImportError:
    ODOO_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/start_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Orchestrates all agent components with health monitoring and auto-restart capabilities.

    Platinum Tier Components:
    - FilesystemWatcher: Monitors inbox for new task files
    - GmailWatcher: Monitors Gmail for new emails (if configured)
    - WhatsAppWatcher: Monitors WhatsApp for new messages (if configured)
    - OdooWatcher: Monitors Odoo approvals and posts documents (if configured)
    - TaskProcessorMonitor: Creates execution plans from tasks
    - ExecutionMonitor: Executes approved plans
    - HealthMonitor: Monitors system health
    """

    def __init__(self):
        self.watcher = None
        self.gmail_watcher = None
        self.whatsapp_watcher = None
        self.odoo_watcher = None
        self.task_processor = None
        self.execution_monitor = None
        self.health_monitor = None
        self.persistence_loop = None  # Ralph Wiggum Loop
        self.running = False
        self.restart_count = 0
        self.max_restarts = 10  # Prevent infinite restart loops
        self.gmail_enabled = False
        self.whatsapp_enabled = False
        self.odoo_enabled = False
        
    def initialize_components(self):
        """Initialize all agent components"""
        try:
            # Define paths
            inbox_path = "obsidian_vault/inbox"
            needs_action_path = "obsidian_vault/needs_action"
            plans_path = "obsidian_vault/Plans"
            approved_path = "obsidian_vault/Approved"
            done_path = "obsidian_vault/Done"

            # Ensure all directories exist
            for path in [inbox_path, needs_action_path, plans_path, approved_path, done_path]:
                os.makedirs(path, exist_ok=True)

            # Create the filesystem watcher instance for inbox
            self.watcher = FilesystemWatcher(inbox_path, needs_action_path)

            # Initialize Gmail watcher if available and configured
            if GMAIL_AVAILABLE:
                gmail_creds = Path("credentials/gmail_credentials.json")
                gmail_token = Path("credentials/gmail_token.json")

                if gmail_creds.exists() or gmail_token.exists():
                    try:
                        self.gmail_watcher = GmailWatcher(
                            output_path=needs_action_path,
                            credentials_path=str(gmail_creds),
                            token_path=str(gmail_token),
                            check_interval=120,  # Check every 2 minutes
                            max_results=10
                        )
                        self.gmail_enabled = True
                        logger.info("Gmail watcher initialized")
                    except Exception as e:
                        logger.warning(f"Gmail watcher initialization failed: {e}")
                        logger.info("Continuing without Gmail monitoring")
                else:
                    logger.info("Gmail credentials not found - Gmail monitoring disabled")
                    logger.info("Run 'python setup_gmail.py' to configure Gmail integration")
            else:
                logger.info("Gmail watcher not available - install google-api-python-client")

            # Initialize WhatsApp watcher if available and configured
            if WHATSAPP_AVAILABLE:
                whatsapp_session = Path("credentials/whatsapp_session")

                if whatsapp_session.exists() and any(whatsapp_session.iterdir()):
                    try:
                        self.whatsapp_watcher = WhatsAppWatcher(
                            output_path=needs_action_path,
                            session_path=str(whatsapp_session),
                            check_interval=30,  # Check every 30 seconds
                            headless=True,  # Run in background
                            max_messages_per_chat=5
                        )
                        self.whatsapp_enabled = True
                        logger.info("WhatsApp watcher initialized")
                    except Exception as e:
                        logger.warning(f"WhatsApp watcher initialization failed: {e}")
                        logger.info("Continuing without WhatsApp monitoring")
                else:
                    logger.info("WhatsApp session not found - WhatsApp monitoring disabled")
                    logger.info("Run 'python setup_whatsapp.py' to configure WhatsApp integration")
            else:
                logger.info("WhatsApp watcher not available - install playwright")

            # Initialize Odoo watcher if available and configured
            if ODOO_AVAILABLE:
                odoo_url = os.getenv('ODOO_URL')
                if odoo_url:
                    try:
                        self.odoo_watcher = OdooWatcher(
                            vault_path="obsidian_vault",
                            check_interval=10
                        )
                        self.odoo_enabled = True
                        logger.info("Odoo watcher initialized")
                    except Exception as e:
                        logger.warning(f"Odoo watcher initialization failed: {e}")
                        logger.info("Continuing without Odoo integration")
                else:
                    logger.info("Odoo not configured - Odoo integration disabled")
                    logger.info("Run 'python setup_odoo.py' to configure Odoo integration")
            else:
                logger.info("Odoo watcher not available")

            # Create the task processor monitor
            self.task_processor = TaskProcessorMonitor(needs_action_path, plans_path)

            # Create the execution monitor
            self.execution_monitor = ExecutionMonitor(approved_path, done_path)

            # Create the health monitor
            self.health_monitor = HealthMonitor()

            # Create the persistence loop (Ralph Wiggum Loop)
            # Monitors /Plans, /Approved, and /Pending_Approval/odoo
            self.persistence_loop = PersistenceLoop(
                plans_path=plans_path,
                approved_path=approved_path,
                pending_odoo_path="obsidian_vault/Pending_Approval/odoo",
                done_path=done_path,
                check_interval=5
            )
            logger.info("Ralph Wiggum persistence loop initialized")

            logger.info("All components initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            return False
    
    def start_components(self):
        """Start all agent components"""
        try:
            # Start filesystem watcher
            self.watcher.start_monitoring()

            # Start Gmail watcher if enabled
            if self.gmail_enabled and self.gmail_watcher:
                try:
                    self.gmail_watcher.start_monitoring()
                    logger.info("Gmail watcher started - monitoring for new emails")
                except Exception as e:
                    logger.warning(f"Failed to start Gmail watcher: {e}")
                    self.gmail_enabled = False

            # Start WhatsApp watcher if enabled
            if self.whatsapp_enabled and self.whatsapp_watcher:
                try:
                    self.whatsapp_watcher.start_monitoring()
                    logger.info("WhatsApp watcher started - monitoring for new messages")
                except Exception as e:
                    logger.warning(f"Failed to start WhatsApp watcher: {e}")
                    self.whatsapp_enabled = False

            # Start Odoo watcher if enabled
            if self.odoo_enabled and self.odoo_watcher:
                try:
                    self.odoo_watcher.start_monitoring()
                    logger.info("Odoo watcher started - monitoring for approved actions")
                except Exception as e:
                    logger.warning(f"Failed to start Odoo watcher: {e}")
                    self.odoo_enabled = False

            # Start task processor and execution monitor
            self.task_processor.start_monitoring()
            self.execution_monitor.start_monitoring()

            # Log startup summary
            components = ["filesystem_watcher", "task_processor", "execution_monitor", "persistence_loop"]
            if self.gmail_enabled:
                components.append("gmail_watcher")
            if self.whatsapp_enabled:
                components.append("whatsapp_watcher")
            if self.odoo_enabled:
                components.append("odoo_watcher")
            logger.info(f"AI Employee Zoya started with components: {', '.join(components)}")
            logger.info("Now monitoring inbox, processing tasks, and executing approved plans...")

            # Log persistence loop status
            if self.persistence_loop:
                status = self.persistence_loop.get_status()
                logger.info(f"Ralph Wiggum Loop monitoring: Plans={status['plans_pending']}, Approved={status['approved_pending']}, Odoo={status['odoo_pending']}")

            # Start health monitoring in a separate thread
            import threading
            health_thread = threading.Thread(target=self.health_monitor.start_monitoring, daemon=True)
            health_thread.start()
            logger.info("Health monitoring started")

            return True

        except Exception as e:
            logger.error(f"Failed to start components: {str(e)}")
            return False
    
    def stop_components(self):
        """Gracefully stop all agent components"""
        try:
            if self.watcher:
                self.watcher.stop_monitoring()
            if self.gmail_watcher:
                self.gmail_watcher.stop_monitoring()
            if self.whatsapp_watcher:
                self.whatsapp_watcher.stop_monitoring()
            if self.odoo_watcher:
                self.odoo_watcher.stop_monitoring()
            if self.task_processor:
                self.task_processor.stop_monitoring()
            if self.execution_monitor:
                self.execution_monitor.stop_monitoring()
            if self.health_monitor:
                self.health_monitor.stop_monitoring()
            if self.persistence_loop:
                self.persistence_loop.stop()
                logger.info("Ralph Wiggum persistence loop stopped")

            logger.info("All components stopped gracefully")

        except Exception as e:
            logger.error(f"Error stopping components: {str(e)}")
    
    def run(self):
        """Main run loop with error handling and auto-restart"""
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        while self.running and self.restart_count < self.max_restarts:
            try:
                logger.info(f"Starting AI Employee Zoya (restart #{self.restart_count})...")
                
                if not self.initialize_components():
                    logger.error("Component initialization failed, exiting...")
                    break
                
                if not self.start_components():
                    logger.error("Component startup failed, exiting...")
                    break
                
                logger.info("AI Employee Zoya is running in Background Mode with auto-restart enabled...")

                # Main loop - keep running until stopped
                status_interval = 60  # Log status every 60 seconds
                seconds_since_status = 0

                while self.running:
                    time.sleep(1)
                    seconds_since_status += 1

                    # Periodically log persistence loop status
                    if seconds_since_status >= status_interval and self.persistence_loop:
                        status = self.persistence_loop.get_status()
                        if status['total_pending'] > 0:
                            logger.info(f"[Ralph Wiggum] Pending work: Plans={status['plans_pending']}, Approved={status['approved_pending']}, Odoo={status['odoo_pending']}")
                        seconds_since_status = 0

                break  # Exit loop if self.running becomes False
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                self.restart_count += 1
                logger.error(f"Agent crashed with error: {str(e)}")
                logger.info(f"Restarting agent... (attempt {self.restart_count}/{self.max_restarts})")
                
                # Clean up before restart
                try:
                    self.stop_components()
                except:
                    pass  # Ignore errors during cleanup
                
                time.sleep(5)  # Wait before restart
        
        # Final cleanup
        self.stop_components()
        logger.info("AI Employee Zoya stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False


def main():
    orchestrator = AgentOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()