"""
WhatsApp Watcher - Monitors WhatsApp Web for new messages and creates action files.

This watcher uses Playwright to automate WhatsApp Web and monitors for incoming
messages containing important keywords. It creates actionable markdown files
in the Obsidian vault for processing by the AI Employee.

Requirements:
    - Playwright browser automation library
    - First run requires QR code scan to authenticate
    - Session is persisted for subsequent runs

Note: Be aware of WhatsApp's terms of service when using automation.
This is intended for personal/business use monitoring your own messages.
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Set
from dataclasses import dataclass, asdict

# Playwright imports - graceful handling if not installed
try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from skills.base_watcher import BaseWatcher

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class WhatsAppMessage:
    """Represents a WhatsApp message."""
    message_id: str
    sender: str
    sender_number: str
    content: str
    timestamp: str
    is_group: bool
    group_name: str
    has_media: bool
    priority: str


class WhatsAppWatcher(BaseWatcher):
    """
    Concrete implementation of BaseWatcher that monitors WhatsApp Web for new messages.

    Features:
        - Playwright-based WhatsApp Web automation
        - Persistent session (no QR scan after first auth)
        - Keyword-based priority detection
        - Creates action files in needs_action folder
        - Tracks processed messages to avoid duplicates
        - Configurable check interval
        - Thread-safe operation
    """

    # Keywords that indicate urgent/important messages
    URGENT_KEYWORDS = [
        'urgent', 'asap', 'immediately', 'critical', 'emergency',
        'invoice', 'payment', 'deadline', 'overdue', 'action required',
        'time sensitive', 'important', 'priority', 'help', 'issue',
        'pricing', 'quote', 'order', 'delivery', 'meeting', 'call me'
    ]

    # Business-related keywords that should be flagged
    BUSINESS_KEYWORDS = [
        'project', 'contract', 'proposal', 'budget', 'timeline',
        'deliverable', 'milestone', 'client', 'customer', 'vendor'
    ]

    # VIP contacts that should always be flagged (add phone numbers or names)
    VIP_CONTACTS: List[str] = []

    # WhatsApp Web selectors (may need updates if WhatsApp changes their UI)
    SELECTORS = {
        'qr_code': 'canvas[aria-label="Scan me!"]',
        'search_box': 'div[contenteditable="true"][data-tab="3"]',
        'chat_list': 'div[aria-label="Chat list"]',
        'unread_chat': 'span[aria-label*="unread message"]',
        'chat_item': 'div[data-testid="cell-frame-container"]',
        'message_in': 'div[data-testid="msg-container"] div.message-in',
        'message_text': 'span.selectable-text',
        'sender_name': 'span[data-testid="author"]',
        'timestamp': 'span[data-testid="msg-time"]',
        'chat_header': 'header span[data-testid="conversation-info-header-chat-title"]',
        'main_panel': 'div[data-testid="conversation-panel-wrapper"]',
        'side_panel': 'div[data-testid="chatlist-header"]',
    }

    def __init__(
        self,
        output_path: str,
        session_path: str = "credentials/whatsapp_session",
        check_interval: int = 30,
        headless: bool = True,
        max_messages_per_chat: int = 5
    ):
        """
        Initialize the WhatsApp Watcher.

        Args:
            output_path: Path to the needs_action folder for output files
            session_path: Path to store browser session data
            check_interval: Seconds between message checks (default: 30)
            headless: Run browser in headless mode (default: True)
            max_messages_per_chat: Max messages to process per chat (default: 5)
        """
        super().__init__(output_path)

        self.output_path = Path(output_path)
        self.session_path = Path(session_path)
        self.check_interval = check_interval
        self.headless = headless
        self.max_messages_per_chat = max_messages_per_chat

        # Track processed message IDs to avoid duplicates
        self.processed_ids: Set[str] = set()
        self.processed_ids_file = Path("logs/whatsapp_processed_ids.json")

        # Playwright instances
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Threading
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # State tracking
        self.is_authenticated = False
        self.last_check_time = None

        # Load previously processed IDs
        self._load_processed_ids()

        # Ensure directories exist
        self.ensure_directory_exists(str(self.output_path))
        self.ensure_directory_exists(str(self.session_path))

        logger.info(f"WhatsAppWatcher initialized. Output: {self.output_path}")

    def _load_processed_ids(self) -> None:
        """Load previously processed message IDs from file."""
        try:
            if self.processed_ids_file.exists():
                with open(self.processed_ids_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_ids = set(data.get('processed_ids', []))
                    logger.info(f"Loaded {len(self.processed_ids)} processed WhatsApp message IDs")
        except Exception as e:
            logger.warning(f"Could not load processed IDs: {e}")
            self.processed_ids = set()

    def _save_processed_ids(self) -> None:
        """Save processed message IDs to file for persistence."""
        try:
            self.ensure_directory_exists(str(self.processed_ids_file.parent))
            # Keep only last 500 IDs to prevent unbounded growth
            ids_list = list(self.processed_ids)[-500:]
            with open(self.processed_ids_file, 'w') as f:
                json.dump({
                    'processed_ids': ids_list,
                    'updated': datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Could not save processed IDs: {e}")

    def _initialize_browser(self) -> bool:
        """Initialize Playwright browser with persistent context."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        try:
            self.playwright = sync_playwright().start()

            # Use persistent context to maintain WhatsApp session
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ],
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

            logger.info("Browser initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    def _navigate_to_whatsapp(self) -> bool:
        """Navigate to WhatsApp Web and wait for load."""
        try:
            self.page.goto('https://web.whatsapp.com', wait_until='networkidle', timeout=60000)
            logger.info("Navigated to WhatsApp Web")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to WhatsApp Web: {e}")
            return False

    def _wait_for_authentication(self, timeout: int = 120) -> bool:
        """
        Wait for user to scan QR code or for existing session to load.

        Args:
            timeout: Maximum seconds to wait for authentication

        Returns:
            True if authenticated, False if timeout
        """
        logger.info("Waiting for WhatsApp authentication...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check if we're already logged in (chat list visible)
                chat_list = self.page.query_selector(self.SELECTORS['side_panel'])
                if chat_list:
                    logger.info("WhatsApp Web authenticated successfully")
                    self.is_authenticated = True
                    return True

                # Check if QR code is displayed
                qr_code = self.page.query_selector(self.SELECTORS['qr_code'])
                if qr_code:
                    if self.headless:
                        logger.warning("QR code displayed but running in headless mode!")
                        logger.warning("Run with headless=False for first authentication")
                        logger.warning("Or run: python setup_whatsapp.py")
                    else:
                        logger.info("Please scan the QR code with your phone...")

                time.sleep(2)

            except Exception as e:
                logger.debug(f"Auth check error: {e}")
                time.sleep(2)

        logger.error("Authentication timeout - QR code not scanned in time")
        return False

    def _get_unread_chats(self) -> List[Dict]:
        """
        Get list of chats with unread messages.

        Returns:
            List of chat dictionaries with name and element
        """
        unread_chats = []

        try:
            # Wait for chat list to be available
            self.page.wait_for_selector(self.SELECTORS['chat_list'], timeout=10000)

            # Find all chat items with unread indicators
            chat_items = self.page.query_selector_all(self.SELECTORS['chat_item'])

            for chat in chat_items:
                try:
                    # Check for unread indicator
                    unread = chat.query_selector(self.SELECTORS['unread_chat'])
                    if unread:
                        # Get chat name
                        name_elem = chat.query_selector('span[title]')
                        chat_name = name_elem.get_attribute('title') if name_elem else 'Unknown'

                        # Get unread count
                        unread_text = unread.inner_text()
                        unread_count = int(unread_text) if unread_text.isdigit() else 1

                        unread_chats.append({
                            'name': chat_name,
                            'element': chat,
                            'unread_count': unread_count
                        })

                except Exception as e:
                    logger.debug(f"Error processing chat item: {e}")
                    continue

            if unread_chats:
                logger.info(f"Found {len(unread_chats)} chats with unread messages")

        except PlaywrightTimeoutError:
            logger.warning("Timeout waiting for chat list")
        except Exception as e:
            logger.error(f"Error getting unread chats: {e}")

        return unread_chats

    def _open_chat(self, chat_element) -> bool:
        """Open a specific chat by clicking on it."""
        try:
            chat_element.click()
            time.sleep(1)  # Wait for chat to open
            self.page.wait_for_selector(self.SELECTORS['main_panel'], timeout=5000)
            return True
        except Exception as e:
            logger.error(f"Failed to open chat: {e}")
            return False

    def _extract_messages(self, chat_name: str, max_messages: int = 5) -> List[WhatsAppMessage]:
        """
        Extract recent messages from the currently open chat.

        Args:
            chat_name: Name of the chat
            max_messages: Maximum messages to extract

        Returns:
            List of WhatsAppMessage objects
        """
        messages = []

        try:
            # Get incoming messages
            msg_containers = self.page.query_selector_all(self.SELECTORS['message_in'])

            # Process only recent messages (from the end)
            recent_msgs = msg_containers[-max_messages:] if len(msg_containers) > max_messages else msg_containers

            for msg in recent_msgs:
                try:
                    # Extract message text
                    text_elem = msg.query_selector(self.SELECTORS['message_text'])
                    content = text_elem.inner_text() if text_elem else ''

                    if not content:
                        continue

                    # Generate message ID
                    msg_id = f"wa_{hash(f'{chat_name}_{content[:50]}_{datetime.now().date()}')}"

                    if msg_id in self.processed_ids:
                        continue

                    # Extract sender (for groups)
                    sender_elem = msg.query_selector(self.SELECTORS['sender_name'])
                    sender = sender_elem.inner_text() if sender_elem else chat_name

                    # Extract timestamp
                    time_elem = msg.query_selector(self.SELECTORS['timestamp'])
                    timestamp = time_elem.inner_text() if time_elem else datetime.now().strftime('%H:%M')

                    # Check if group chat
                    is_group = sender_elem is not None

                    # Check for media
                    has_media = msg.query_selector('img, video, audio') is not None

                    # Determine priority
                    priority = self._determine_priority(content, sender)

                    message = WhatsAppMessage(
                        message_id=msg_id,
                        sender=sender,
                        sender_number='',  # Not easily accessible
                        content=content,
                        timestamp=timestamp,
                        is_group=is_group,
                        group_name=chat_name if is_group else '',
                        has_media=has_media,
                        priority=priority
                    )

                    messages.append(message)

                except Exception as e:
                    logger.debug(f"Error extracting message: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting messages: {e}")

        return messages

    def _determine_priority(self, content: str, sender: str) -> str:
        """
        Determine message priority based on content and sender.

        Returns:
            'high', 'medium', or 'low'
        """
        content_lower = content.lower()

        # Check for VIP sender
        is_vip = any(vip.lower() in sender.lower() for vip in self.VIP_CONTACTS)

        # Count urgent keywords
        urgent_count = sum(1 for kw in self.URGENT_KEYWORDS if kw in content_lower)

        # Count business keywords
        business_count = sum(1 for kw in self.BUSINESS_KEYWORDS if kw in content_lower)

        # Determine priority
        if urgent_count >= 2 or is_vip:
            return 'high'
        elif urgent_count >= 1 or business_count >= 2:
            return 'medium'
        else:
            return 'low'

    def check_for_updates(self) -> List[WhatsAppMessage]:
        """
        Check WhatsApp for new messages.

        Returns:
            List of new WhatsAppMessage objects
        """
        if not self.is_authenticated:
            logger.warning("Not authenticated to WhatsApp")
            return []

        all_messages = []

        try:
            # Get chats with unread messages
            unread_chats = self._get_unread_chats()

            for chat in unread_chats:
                if self._stop_event.is_set():
                    break

                # Open the chat
                if self._open_chat(chat['element']):
                    # Extract messages
                    messages = self._extract_messages(
                        chat['name'],
                        min(chat['unread_count'], self.max_messages_per_chat)
                    )
                    all_messages.extend(messages)

                    # Small delay between chats
                    time.sleep(0.5)

            self.last_check_time = datetime.now()

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

        return all_messages

    def create_action_file(self, message: WhatsAppMessage) -> Optional[Path]:
        """
        Create an action file in the needs_action folder.

        Args:
            message: WhatsAppMessage object

        Returns:
            Path to created file or None if failed
        """
        try:
            timestamp = datetime.now()

            # Generate filename
            safe_sender = "".join(c for c in message.sender[:20] if c.isalnum() or c in ' -_').strip()
            safe_sender = safe_sender.replace(' ', '_') or 'unknown'
            filename = f"WHATSAPP_{timestamp.strftime('%Y%m%d_%H%M%S')}_{safe_sender}.md"
            filepath = self.output_path / filename

            # Generate suggested actions
            suggested_actions = self._generate_suggested_actions(message)

            # Create markdown content
            content = f"""---
type: whatsapp
message_id: {message.message_id}
sender: {message.sender}
sender_number: {message.sender_number}
is_group: {message.is_group}
group_name: {message.group_name}
timestamp: {message.timestamp}
detected_at: {timestamp.isoformat()}
priority: {message.priority}
has_media: {message.has_media}
status: pending
---

# WhatsApp Message from {message.sender}

## Message Details
- **From:** {message.sender}
- **Time:** {message.timestamp}
- **Priority:** {message.priority.upper()}
- **Type:** {'Group Chat' if message.is_group else 'Direct Message'}
{f'- **Group:** {message.group_name}' if message.is_group else ''}
- **Has Media:** {'Yes' if message.has_media else 'No'}

## Message Content
{message.content}

## Suggested Actions
{suggested_actions}

## Processing Notes
- [ ] Review message content
- [ ] Determine appropriate response
- [ ] Move to /Approved when ready to act

---
*Detected by WhatsApp Watcher at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}*
*AI Employee Zoya - Automated Message Processing*
"""

            # Write the file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Created WhatsApp action file: {filename}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to create action file: {e}")
            return None

    def _generate_suggested_actions(self, message: WhatsAppMessage) -> str:
        """Generate suggested actions based on message content."""
        actions = []
        content_lower = message.content.lower()

        # Check for specific patterns
        if any(kw in content_lower for kw in ['invoice', 'payment', 'pay', 'price', 'cost', 'quote']):
            actions.append("- [ ] Review payment/pricing details")
            actions.append("- [ ] Prepare invoice or quote if needed")

        if any(kw in content_lower for kw in ['meeting', 'schedule', 'call', 'appointment', 'available']):
            actions.append("- [ ] Check calendar availability")
            actions.append("- [ ] Schedule meeting or call")

        if any(kw in content_lower for kw in ['deadline', 'due', 'urgent', 'asap']):
            actions.append("- [ ] Prioritize this request")
            actions.append("- [ ] Assess timeline and resources")

        if any(kw in content_lower for kw in ['help', 'support', 'issue', 'problem', 'error']):
            actions.append("- [ ] Investigate the issue")
            actions.append("- [ ] Provide support/assistance")

        if any(kw in content_lower for kw in ['order', 'delivery', 'shipping', 'tracking']):
            actions.append("- [ ] Check order status")
            actions.append("- [ ] Provide tracking/delivery information")

        if any(kw in content_lower for kw in ['project', 'proposal', 'contract']):
            actions.append("- [ ] Review project requirements")
            actions.append("- [ ] Prepare necessary documentation")

        if message.has_media:
            actions.append("- [ ] Review attached media")

        # Default actions
        if not actions:
            actions.append("- [ ] Read and assess message importance")
            actions.append("- [ ] Determine if response needed")

        actions.append("- [ ] Reply to sender (requires HITL approval)")
        actions.append("- [ ] Archive after processing")

        return '\n'.join(actions)

    def handle_new_file(self, file_path: str) -> None:
        """Handle a newly created action file (implements BaseWatcher interface)."""
        logger.info(f"WhatsApp message saved to: {file_path}")

    def start_monitoring(self) -> None:
        """Start the WhatsApp monitoring process."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Cannot start WhatsApp monitoring - Playwright not installed")
            logger.error("Run: pip install playwright && playwright install chromium")
            return

        if self.is_running:
            logger.warning("WhatsApp watcher is already running")
            return

        # Initialize browser
        if not self._initialize_browser():
            logger.error("Failed to initialize browser")
            return

        # Navigate to WhatsApp Web
        if not self._navigate_to_whatsapp():
            logger.error("Failed to navigate to WhatsApp Web")
            return

        # Wait for authentication
        if not self._wait_for_authentication():
            logger.error("WhatsApp authentication failed")
            return

        self.is_running = True
        self._stop_event.clear()

        # Start monitoring in a separate thread
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"Started WhatsApp monitoring (checking every {self.check_interval}s)")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in a separate thread."""
        logger.info("WhatsApp monitoring loop started")

        while not self._stop_event.is_set():
            try:
                # Check for new messages
                new_messages = self.check_for_updates()

                for message in new_messages:
                    if self._stop_event.is_set():
                        break

                    # Only process medium and high priority by default
                    # (can be changed to process all)
                    if message.priority in ['high', 'medium']:
                        filepath = self.create_action_file(message)

                        if filepath:
                            self.processed_ids.add(message.message_id)
                            self.handle_new_file(str(filepath))
                    else:
                        # Still mark as processed to avoid reprocessing
                        self.processed_ids.add(message.message_id)

                # Save processed IDs periodically
                if new_messages:
                    self._save_processed_ids()

            except Exception as e:
                logger.error(f"Error in WhatsApp monitoring loop: {e}")

            # Wait for next check interval
            self._stop_event.wait(self.check_interval)

        logger.info("WhatsApp monitoring loop stopped")

    def stop_monitoring(self) -> None:
        """Stop the WhatsApp monitoring process."""
        if not self.is_running:
            return

        logger.info("Stopping WhatsApp monitoring...")
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)

        # Close browser
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        self.is_running = False
        self.is_authenticated = False
        self._save_processed_ids()

        logger.info("WhatsApp monitoring stopped")

    def get_status(self) -> Dict:
        """Get current watcher status."""
        return {
            'running': self.is_running,
            'authenticated': self.is_authenticated,
            'processed_count': len(self.processed_ids),
            'check_interval': self.check_interval,
            'output_path': str(self.output_path),
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'headless': self.headless
        }


def main():
    """Main function for standalone testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("WhatsApp Watcher - Standalone Mode")
    print("=" * 40)

    watcher = WhatsAppWatcher(
        output_path="obsidian_vault/needs_action",
        session_path="credentials/whatsapp_session",
        check_interval=30,
        headless=False  # Show browser for QR code scanning
    )

    print("\nStarting WhatsApp Watcher...")
    print("You may need to scan the QR code with your phone.")
    print("Press Ctrl+C to stop\n")

    try:
        watcher.start_monitoring()

        # Keep running until interrupted
        while True:
            time.sleep(1)
            status = watcher.get_status()
            if status['running'] and status['authenticated']:
                if status['last_check']:
                    print(f"\rLast check: {status['last_check']} | Processed: {status['processed_count']}", end='')

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        watcher.stop_monitoring()
        print("WhatsApp Watcher stopped")


if __name__ == "__main__":
    main()
