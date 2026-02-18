"""
Gmail Watcher - Monitors Gmail for new/important emails and creates action files.

This watcher uses the Google Gmail API to monitor incoming emails and creates
actionable markdown files in the Obsidian vault for processing by the AI Employee.

Requirements:
    - Google Cloud Project with Gmail API enabled
    - OAuth2 credentials (credentials.json)
    - First run requires browser authentication to generate token.json
"""

import os
import json
import time
import base64
import logging
import threading
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional, List, Dict, Set

# Google API imports - graceful handling if not installed
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from skills.base_watcher import BaseWatcher

# Configure logging
logger = logging.getLogger(__name__)


class GmailWatcher(BaseWatcher):
    """
    Concrete implementation of BaseWatcher that monitors Gmail for new emails.

    Features:
        - OAuth2 authentication with automatic token refresh
        - Keyword-based priority detection
        - Creates action files in needs_action folder
        - Tracks processed emails to avoid duplicates
        - Configurable check interval
        - Thread-safe operation
    """

    # Gmail API scopes - read-only for safety
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    # Keywords that indicate urgent/important messages
    URGENT_KEYWORDS = [
        'urgent', 'asap', 'immediately', 'critical', 'emergency',
        'invoice', 'payment', 'deadline', 'overdue', 'action required',
        'time sensitive', 'important', 'priority', 'help', 'issue'
    ]

    # Senders that should always be flagged as important
    VIP_SENDERS = []  # Add VIP email addresses here

    def __init__(
        self,
        output_path: str,
        credentials_path: str = "credentials/gmail_credentials.json",
        token_path: str = "credentials/gmail_token.json",
        check_interval: int = 120,
        max_results: int = 10
    ):
        """
        Initialize the Gmail Watcher.

        Args:
            output_path: Path to the needs_action folder for output files
            credentials_path: Path to OAuth2 credentials JSON file
            token_path: Path to store/load the authentication token
            check_interval: Seconds between email checks (default: 120)
            max_results: Maximum emails to fetch per check (default: 10)
        """
        # BaseWatcher expects monitored_path, we'll use output_path
        super().__init__(output_path)

        self.output_path = Path(output_path)
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.check_interval = check_interval
        self.max_results = max_results

        # Track processed message IDs to avoid duplicates
        self.processed_ids: Set[str] = set()
        self.processed_ids_file = Path("logs/gmail_processed_ids.json")

        # Service instance
        self.service = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Load previously processed IDs
        self._load_processed_ids()

        # Ensure output directory exists
        self.ensure_directory_exists(str(self.output_path))

        logger.info(f"GmailWatcher initialized. Output: {self.output_path}")

    def _load_processed_ids(self) -> None:
        """Load previously processed message IDs from file."""
        try:
            if self.processed_ids_file.exists():
                with open(self.processed_ids_file, 'r') as f:
                    data = json.load(f)
                    self.processed_ids = set(data.get('processed_ids', []))
                    logger.info(f"Loaded {len(self.processed_ids)} processed message IDs")
        except Exception as e:
            logger.warning(f"Could not load processed IDs: {e}")
            self.processed_ids = set()

    def _save_processed_ids(self) -> None:
        """Save processed message IDs to file for persistence."""
        try:
            self.ensure_directory_exists(str(self.processed_ids_file.parent))
            # Keep only last 1000 IDs to prevent unbounded growth
            ids_list = list(self.processed_ids)[-1000:]
            with open(self.processed_ids_file, 'w') as f:
                json.dump({'processed_ids': ids_list, 'updated': datetime.now().isoformat()}, f)
        except Exception as e:
            logger.error(f"Could not save processed IDs: {e}")

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.

        Returns:
            True if authentication successful, False otherwise
        """
        if not GOOGLE_API_AVAILABLE:
            logger.error("Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-api-python-client")
            return False

        creds = None

        # Check for existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
                logger.info("Loaded existing Gmail credentials")
            except Exception as e:
                logger.warning(f"Could not load existing token: {e}")

        # If no valid credentials, initiate OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed Gmail credentials")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    logger.error(f"Credentials file not found: {self.credentials_path}")
                    logger.error("Please download OAuth2 credentials from Google Cloud Console")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    logger.info("Completed OAuth2 authentication flow")
                except Exception as e:
                    logger.error(f"OAuth2 flow failed: {e}")
                    return False

            # Save credentials for future use
            try:
                self.ensure_directory_exists(str(self.token_path.parent))
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
                logger.info(f"Saved credentials to {self.token_path}")
            except Exception as e:
                logger.warning(f"Could not save credentials: {e}")

        # Build the Gmail service
        try:
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail API service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            return False

    def check_for_updates(self) -> List[Dict]:
        """
        Check Gmail for new unread/important messages.

        Returns:
            List of new message dictionaries
        """
        if not self.service:
            logger.warning("Gmail service not initialized")
            return []

        try:
            # Query for unread messages that are important or in inbox
            query = 'is:unread (is:important OR in:inbox)'

            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=self.max_results
            ).execute()

            messages = results.get('messages', [])

            # Filter out already processed messages
            new_messages = [
                msg for msg in messages
                if msg['id'] not in self.processed_ids
            ]

            if new_messages:
                logger.info(f"Found {len(new_messages)} new email(s) to process")

            return new_messages

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return []

    def get_message_details(self, message_id: str) -> Optional[Dict]:
        """
        Fetch full details of a specific message.

        Args:
            message_id: Gmail message ID

        Returns:
            Dictionary with message details or None if failed
        """
        if not self.service:
            return None

        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Extract headers
            headers = {}
            for header in msg['payload'].get('headers', []):
                headers[header['name'].lower()] = header['value']

            # Extract body (prefer plain text)
            body = self._extract_body(msg['payload'])

            # Determine priority based on keywords and labels
            priority = self._determine_priority(
                subject=headers.get('subject', ''),
                body=body,
                sender=headers.get('from', ''),
                labels=msg.get('labelIds', [])
            )

            return {
                'id': message_id,
                'thread_id': msg.get('threadId', ''),
                'from': headers.get('from', 'Unknown'),
                'to': headers.get('to', ''),
                'subject': headers.get('subject', 'No Subject'),
                'date': headers.get('date', ''),
                'snippet': msg.get('snippet', ''),
                'body': body[:2000] if body else '',  # Limit body size
                'labels': msg.get('labelIds', []),
                'priority': priority,
                'has_attachments': self._has_attachments(msg['payload'])
            }

        except HttpError as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting message details: {e}")
            return None

    def _extract_body(self, payload: Dict) -> str:
        """Extract plain text body from message payload."""
        body = ''

        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        elif 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    if 'body' in part and part['body'].get('data'):
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
                elif 'parts' in part:
                    body = self._extract_body(part)
                    if body:
                        break

        return body.strip()

    def _has_attachments(self, payload: Dict) -> bool:
        """Check if message has attachments."""
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    return True
                if 'parts' in part:
                    if self._has_attachments(part):
                        return True
        return False

    def _determine_priority(
        self,
        subject: str,
        body: str,
        sender: str,
        labels: List[str]
    ) -> str:
        """
        Determine email priority based on content and metadata.

        Returns:
            'high', 'medium', or 'low'
        """
        combined_text = f"{subject} {body}".lower()

        # Check for urgent keywords
        urgent_count = sum(1 for kw in self.URGENT_KEYWORDS if kw in combined_text)

        # Check for VIP sender
        is_vip = any(vip.lower() in sender.lower() for vip in self.VIP_SENDERS)

        # Check Gmail's importance label
        is_important = 'IMPORTANT' in labels

        # Determine priority
        if urgent_count >= 2 or is_vip or (urgent_count >= 1 and is_important):
            return 'high'
        elif urgent_count >= 1 or is_important:
            return 'medium'
        else:
            return 'low'

    def create_action_file(self, message: Dict) -> Optional[Path]:
        """
        Create an action file in the needs_action folder.

        Args:
            message: Message dictionary with details

        Returns:
            Path to created file or None if failed
        """
        try:
            timestamp = datetime.now()

            # Generate filename
            safe_subject = "".join(c for c in message['subject'][:30] if c.isalnum() or c in ' -_').strip()
            safe_subject = safe_subject.replace(' ', '_') or 'no_subject'
            filename = f"EMAIL_{timestamp.strftime('%Y%m%d_%H%M%S')}_{safe_subject}.md"
            filepath = self.output_path / filename

            # Determine suggested actions based on content
            suggested_actions = self._generate_suggested_actions(message)

            # Create markdown content
            content = f"""---
type: email
message_id: {message['id']}
thread_id: {message['thread_id']}
from: {message['from']}
to: {message['to']}
subject: {message['subject']}
received: {message['date']}
detected_at: {timestamp.isoformat()}
priority: {message['priority']}
has_attachments: {message['has_attachments']}
status: pending
---

# Email: {message['subject']}

## Sender Information
- **From:** {message['from']}
- **Date:** {message['date']}
- **Priority:** {message['priority'].upper()}
- **Has Attachments:** {'Yes' if message['has_attachments'] else 'No'}

## Email Preview
{message['snippet']}

## Full Content
{message['body'] if message['body'] else '*No plain text content available*'}

## Suggested Actions
{suggested_actions}

## Processing Notes
- [ ] Review email content
- [ ] Determine appropriate response
- [ ] Move to /Approved when ready to act

---
*Detected by Gmail Watcher at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}*
*AI Employee Zoya - Automated Email Processing*
"""

            # Write the file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Created action file: {filename}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to create action file: {e}")
            return None

    def _generate_suggested_actions(self, message: Dict) -> str:
        """Generate suggested actions based on email content."""
        actions = []
        combined_text = f"{message['subject']} {message['body']}".lower()

        # Check for specific patterns
        if any(kw in combined_text for kw in ['invoice', 'payment', 'pay']):
            actions.append("- [ ] Review payment/invoice details")
            actions.append("- [ ] Verify amount and recipient")
            actions.append("- [ ] Process payment if approved (requires HITL)")

        if any(kw in combined_text for kw in ['meeting', 'schedule', 'calendar', 'appointment']):
            actions.append("- [ ] Check calendar availability")
            actions.append("- [ ] Schedule/confirm meeting")

        if any(kw in combined_text for kw in ['deadline', 'due', 'overdue']):
            actions.append("- [ ] Review deadline requirements")
            actions.append("- [ ] Prioritize task completion")

        if any(kw in combined_text for kw in ['question', 'help', 'support', 'issue', 'problem']):
            actions.append("- [ ] Draft helpful response")
            actions.append("- [ ] Gather relevant information")

        if message['has_attachments']:
            actions.append("- [ ] Review attachments")

        # Default actions
        if not actions:
            actions.append("- [ ] Read and assess email importance")
            actions.append("- [ ] Determine if response needed")

        actions.append("- [ ] Reply to sender (if needed)")
        actions.append("- [ ] Archive after processing")

        return '\n'.join(actions)

    def handle_new_file(self, file_path: str) -> None:
        """
        Handle a newly detected email (implements BaseWatcher interface).

        Note: For Gmail, this is called internally after processing messages.
        """
        logger.info(f"Processed email saved to: {file_path}")

    def start_monitoring(self) -> None:
        """Start the Gmail monitoring process."""
        if not GOOGLE_API_AVAILABLE:
            logger.error("Cannot start Gmail monitoring - Google API libraries not installed")
            logger.error("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
            return

        if self.is_running:
            logger.warning("Gmail watcher is already running")
            return

        # Authenticate first
        if not self.authenticate():
            logger.error("Gmail authentication failed - cannot start monitoring")
            return

        self.is_running = True
        self._stop_event.clear()

        # Start monitoring in a separate thread
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()

        logger.info(f"Started Gmail monitoring (checking every {self.check_interval}s)")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in a separate thread."""
        logger.info("Gmail monitoring loop started")

        while not self._stop_event.is_set():
            try:
                # Check for new messages
                new_messages = self.check_for_updates()

                for msg_stub in new_messages:
                    if self._stop_event.is_set():
                        break

                    # Get full message details
                    message = self.get_message_details(msg_stub['id'])

                    if message:
                        # Create action file
                        filepath = self.create_action_file(message)

                        if filepath:
                            # Mark as processed
                            self.processed_ids.add(msg_stub['id'])
                            self.handle_new_file(str(filepath))

                # Save processed IDs periodically
                if new_messages:
                    self._save_processed_ids()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Wait for next check interval
            self._stop_event.wait(self.check_interval)

        logger.info("Gmail monitoring loop stopped")

    def stop_monitoring(self) -> None:
        """Stop the Gmail monitoring process."""
        if not self.is_running:
            return

        logger.info("Stopping Gmail monitoring...")
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)

        self.is_running = False
        self._save_processed_ids()

        logger.info("Gmail monitoring stopped")

    def get_status(self) -> Dict:
        """Get current watcher status."""
        return {
            'running': self.is_running,
            'authenticated': self.service is not None,
            'processed_count': len(self.processed_ids),
            'check_interval': self.check_interval,
            'output_path': str(self.output_path)
        }


def main():
    """Main function for standalone testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    watcher = GmailWatcher(
        output_path="obsidian_vault/needs_action",
        credentials_path="credentials/gmail_credentials.json",
        token_path="credentials/gmail_token.json",
        check_interval=60  # Check every minute for testing
    )

    print("Starting Gmail Watcher...")
    print("Press Ctrl+C to stop")

    try:
        watcher.start_monitoring()

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        watcher.stop_monitoring()
        print("Gmail Watcher stopped")


if __name__ == "__main__":
    main()
