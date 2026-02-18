#!/usr/bin/env python3
"""
WhatsApp Watcher Setup Script for AI Employee Zoya

This script helps you set up WhatsApp Web integration:
1. Checks if Playwright is installed
2. Installs Chromium browser if needed
3. Opens WhatsApp Web for QR code scanning
4. Saves the session for future use

Prerequisites:
    - Python 3.8+
    - Playwright library

Usage:
    python setup_whatsapp.py
"""

import os
import sys
import time
from pathlib import Path


def check_dependencies():
    """Check if required packages are installed."""
    print("Checking dependencies...")

    # Check Playwright
    try:
        from playwright.sync_api import sync_playwright
        print("  [OK] playwright")
        return True
    except ImportError:
        print("  [MISSING] playwright")
        print("\nPlaywright is not installed.")
        print("Install with:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return False


def install_browser():
    """Install Chromium browser for Playwright."""
    print("\nChecking Chromium browser...")

    try:
        import subprocess
        result = subprocess.run(
            ['playwright', 'install', 'chromium'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("  [OK] Chromium browser installed")
            return True
        else:
            print(f"  [ERROR] Failed to install browser: {result.stderr}")
            return False

    except Exception as e:
        print(f"  [ERROR] Could not install browser: {e}")
        print("\nTry running manually:")
        print("  playwright install chromium")
        return False


def setup_session_folder():
    """Create session folder for WhatsApp data."""
    session_path = Path("credentials/whatsapp_session")
    session_path.mkdir(parents=True, exist_ok=True)

    # Add to .gitignore if credentials folder exists
    gitignore = Path("credentials/.gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        if 'whatsapp_session' not in content:
            gitignore.write_text(content + "\nwhatsapp_session/\n")
            print("Updated credentials/.gitignore")

    return session_path


def authenticate_whatsapp(session_path: Path):
    """Open WhatsApp Web and wait for QR code scan."""
    print("\n" + "=" * 50)
    print("WhatsApp Web Authentication")
    print("=" * 50)

    from playwright.sync_api import sync_playwright

    print("\nOpening WhatsApp Web...")
    print("Please scan the QR code with your phone:")
    print("  1. Open WhatsApp on your phone")
    print("  2. Go to Settings > Linked Devices")
    print("  3. Tap 'Link a Device'")
    print("  4. Scan the QR code in the browser\n")

    with sync_playwright() as p:
        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            headless=False,  # Must be visible for QR scanning
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ],
            viewport={'width': 1280, 'height': 800}
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Navigate to WhatsApp Web
        page.goto('https://web.whatsapp.com', wait_until='networkidle')

        # Wait for authentication
        print("Waiting for authentication...")
        print("(This window will close automatically after successful login)\n")

        authenticated = False
        timeout = 120  # 2 minutes
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check if chat list is visible (authenticated)
                chat_list = page.query_selector('div[data-testid="chatlist-header"]')
                if chat_list:
                    print("\n[SUCCESS] WhatsApp Web authenticated!")
                    authenticated = True
                    break

                # Check if QR code is displayed
                qr = page.query_selector('canvas[aria-label="Scan me!"]')
                if qr:
                    print("\rWaiting for QR code scan...", end='')

                time.sleep(2)

            except Exception as e:
                time.sleep(2)

        if authenticated:
            # Keep session alive briefly to ensure it's saved
            print("Saving session...")
            time.sleep(3)
            print("[OK] Session saved successfully")
        else:
            print("\n[TIMEOUT] Authentication timed out")
            print("Please try again")

        context.close()

        return authenticated


def test_connection(session_path: Path):
    """Test the saved session by connecting to WhatsApp."""
    print("\nTesting saved session...")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            headless=True,  # Can be headless now
            args=['--disable-blink-features=AutomationControlled']
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://web.whatsapp.com', wait_until='networkidle', timeout=30000)

        # Wait a bit for potential session restore
        time.sleep(5)

        # Check if authenticated
        chat_list = page.query_selector('div[data-testid="chatlist-header"]')

        context.close()

        if chat_list:
            print("[OK] Session valid - can connect without QR code")
            return True
        else:
            print("[WARNING] Session may have expired")
            return False


def print_usage_instructions():
    """Print instructions for using the WhatsApp watcher."""
    print("\n" + "=" * 60)
    print("WHATSAPP WATCHER USAGE INSTRUCTIONS")
    print("=" * 60)
    print("""
The WhatsApp Watcher monitors your WhatsApp Web for new messages
and creates action files in the obsidian_vault/needs_action/ folder.

Starting the Watcher:
  The watcher starts automatically with the AI Employee:
    python start_agent.py

  Or run standalone for testing:
    python skills/whatsapp_watcher.py

Configuration (in start_agent.py):
  - check_interval: How often to check (default: 30 seconds)
  - headless: Run without browser window (default: True)
  - max_messages_per_chat: Messages per chat to process (default: 5)

Priority Detection:
  HIGH: Multiple urgent keywords or VIP contact
  MEDIUM: Single urgent keyword or business keyword
  LOW: Regular messages

Urgent Keywords:
  urgent, asap, immediately, critical, emergency, invoice,
  payment, deadline, overdue, action required, time sensitive,
  important, priority, help, issue, pricing, quote, order,
  delivery, meeting, call me

Business Keywords:
  project, contract, proposal, budget, timeline, deliverable,
  milestone, client, customer, vendor

Workflow:
  1. New WhatsApp message arrives
  2. Watcher detects message (within check_interval)
  3. High/Medium priority messages create action files
  4. Task processor creates execution plan
  5. Human reviews and moves to /Approved
  6. Execution engine processes (e.g., drafts response)

Security Notes:
  - Session data stored locally in credentials/whatsapp_session/
  - WhatsApp ToS: Use responsibly for personal/business automation
  - All reply actions require Human-in-the-Loop approval
  - Session may expire; re-run setup if needed

Troubleshooting:
  - QR code not appearing: Close other WhatsApp Web sessions
  - Session expired: Run 'python setup_whatsapp.py' again
  - Browser issues: Run 'playwright install chromium'
""")


def main():
    """Main setup function."""
    print("=" * 60)
    print("WhatsApp Watcher Setup for AI Employee Zoya")
    print("=" * 60)

    # Step 1: Check dependencies
    if not check_dependencies():
        print("\nPlease install Playwright and run again:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    # Step 2: Install browser if needed
    install_browser()

    # Step 3: Setup session folder
    session_path = setup_session_folder()
    print(f"\nSession will be stored in: {session_path}")

    # Step 4: Check if session already exists
    session_file = session_path / "Default" / "Cookies"
    if session_file.exists():
        print("\nExisting session found. Testing...")
        if test_connection(session_path):
            print("\nSession is still valid!")
            response = input("Re-authenticate anyway? (y/N): ").strip().lower()
            if response != 'y':
                print_usage_instructions()
                return

    # Step 5: Authenticate
    if authenticate_whatsapp(session_path):
        # Step 6: Verify session
        print("\nVerifying session...")
        if test_connection(session_path):
            print("\n[SUCCESS] WhatsApp setup complete!")
            print_usage_instructions()
        else:
            print("\n[WARNING] Session verification failed")
            print("The watcher may require re-authentication")
    else:
        print("\n[FAILED] WhatsApp authentication failed")
        print("Please try again")
        sys.exit(1)


if __name__ == "__main__":
    main()
