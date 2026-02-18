#!/usr/bin/env python3
"""
Gmail API Setup Script for AI Employee Zoya

This script helps you set up Gmail API integration:
1. Checks if required packages are installed
2. Verifies credentials file exists
3. Runs the OAuth2 authentication flow
4. Tests the connection by fetching recent emails

Prerequisites:
    1. Create a Google Cloud Project: https://console.cloud.google.com/
    2. Enable the Gmail API
    3. Create OAuth2 credentials (Desktop Application)
    4. Download credentials as 'gmail_credentials.json'
    5. Place in the 'credentials/' folder

Usage:
    python setup_gmail.py
"""

import os
import sys
from pathlib import Path


def check_dependencies():
    """Check if required Google API packages are installed."""
    print("Checking dependencies...")

    required_packages = [
        ('google.auth', 'google-auth'),
        ('google_auth_oauthlib', 'google-auth-oauthlib'),
        ('googleapiclient', 'google-api-python-client')
    ]

    missing = []
    for module, package in required_packages:
        try:
            __import__(module)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [MISSING] {package}")
            missing.append(package)

    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Install with:")
        print(f"  pip install {' '.join(missing)}")
        return False

    print("All dependencies installed!")
    return True


def setup_credentials_folder():
    """Create credentials folder if it doesn't exist."""
    creds_path = Path("credentials")
    creds_path.mkdir(exist_ok=True)

    # Create .gitignore to prevent credentials from being committed
    gitignore_path = creds_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("# Ignore all credential files\n*\n!.gitignore\n")
        print("Created credentials/.gitignore")

    return creds_path


def check_credentials_file(creds_path: Path):
    """Check if OAuth2 credentials file exists."""
    creds_file = creds_path / "gmail_credentials.json"

    if creds_file.exists():
        print(f"[OK] Found credentials file: {creds_file}")
        return True
    else:
        print(f"\n[MISSING] Credentials file not found: {creds_file}")
        print("\nTo create credentials:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a new project (or select existing)")
        print("  3. Enable the Gmail API:")
        print("     - Go to 'APIs & Services' > 'Library'")
        print("     - Search for 'Gmail API' and enable it")
        print("  4. Create OAuth2 credentials:")
        print("     - Go to 'APIs & Services' > 'Credentials'")
        print("     - Click 'Create Credentials' > 'OAuth client ID'")
        print("     - Choose 'Desktop application'")
        print("     - Download the JSON file")
        print(f"  5. Rename to 'gmail_credentials.json' and place in '{creds_path}/'")
        return False


def run_authentication():
    """Run the OAuth2 authentication flow."""
    print("\nRunning OAuth2 authentication...")

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        creds_file = Path("credentials/gmail_credentials.json")
        token_file = Path("credentials/gmail_token.json")

        creds = None

        # Check for existing token
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            print("Found existing token")

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("Starting OAuth2 flow (browser will open)...")
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
            print(f"Saved token to {token_file}")

        # Test the connection
        print("\nTesting Gmail API connection...")
        service = build('gmail', 'v1', credentials=creds)

        # Get profile info
        profile = service.users().getProfile(userId='me').execute()
        print(f"  Connected as: {profile['emailAddress']}")
        print(f"  Total messages: {profile['messagesTotal']}")
        print(f"  Total threads: {profile['threadsTotal']}")

        # Fetch a few recent messages as test
        results = service.users().messages().list(userId='me', maxResults=3).execute()
        messages = results.get('messages', [])
        print(f"  Recent messages found: {len(messages)}")

        print("\n[SUCCESS] Gmail API setup complete!")
        print("\nYou can now start the AI Employee with Gmail monitoring:")
        print("  python start_agent.py")

        return True

    except Exception as e:
        print(f"\n[ERROR] Authentication failed: {e}")
        return False


def print_usage_instructions():
    """Print instructions for using the Gmail watcher."""
    print("\n" + "=" * 60)
    print("GMAIL WATCHER USAGE INSTRUCTIONS")
    print("=" * 60)
    print("""
The Gmail Watcher monitors your inbox for new emails and creates
action files in the obsidian_vault/needs_action/ folder.

Configuration options (in start_agent.py or when initializing):
  - check_interval: How often to check for new emails (default: 120s)
  - max_results: Maximum emails to fetch per check (default: 10)

Priority Detection:
  - HIGH: Multiple urgent keywords, VIP senders, or Gmail important label
  - MEDIUM: Single urgent keyword or important label
  - LOW: Regular emails

Urgent Keywords:
  urgent, asap, immediately, critical, emergency, invoice,
  payment, deadline, overdue, action required, time sensitive,
  important, priority, help, issue

Workflow:
  1. New email arrives in Gmail
  2. Watcher detects email (within check_interval seconds)
  3. Action file created in obsidian_vault/needs_action/
  4. Task processor creates execution plan
  5. Human reviews and moves to /Approved
  6. Execution engine processes approved actions

Security Notes:
  - Gmail Watcher uses READ-ONLY access
  - It cannot send, delete, or modify emails
  - All actions requiring email responses go through HITL approval
  - Credentials are stored locally and never transmitted
""")


def main():
    """Main setup function."""
    print("=" * 60)
    print("Gmail API Setup for AI Employee Zoya")
    print("=" * 60)

    # Step 1: Check dependencies
    if not check_dependencies():
        print("\nPlease install missing packages and run again.")
        sys.exit(1)

    # Step 2: Setup credentials folder
    creds_path = setup_credentials_folder()

    # Step 3: Check for credentials file
    if not check_credentials_file(creds_path):
        print("\nPlease add credentials file and run again.")
        sys.exit(1)

    # Step 4: Run authentication
    if not run_authentication():
        print("\nAuthentication failed. Please check errors above.")
        sys.exit(1)

    # Print usage instructions
    print_usage_instructions()


if __name__ == "__main__":
    main()
