#!/usr/bin/env python3
"""
Odoo Setup Script for AI Employee Zoya

This script helps you set up Odoo Community Edition integration:
1. Tests connection to your Odoo server
2. Verifies API access
3. Creates configuration file
4. Tests basic operations

Prerequisites:
    - Odoo Community Edition 19+ running (local or remote)
    - API access enabled
    - User with accounting permissions

Usage:
    python setup_odoo.py
"""

import os
import sys
import json
from pathlib import Path
from getpass import getpass


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def get_odoo_config() -> dict:
    """Interactively get Odoo configuration."""
    print_header("Odoo Connection Configuration")

    print("\nEnter your Odoo server details:")
    print("(Press Enter to use default values shown in brackets)\n")

    url = input("Odoo URL [http://localhost:8069]: ").strip()
    url = url or "http://localhost:8069"

    database = input("Database name [odoo]: ").strip()
    database = database or "odoo"

    username = input("Username (email) [admin]: ").strip()
    username = username or "admin"

    password = getpass("Password or API Key: ")

    return {
        'url': url,
        'database': database,
        'username': username,
        'password': password,
        'timeout': 30
    }


def test_connection(config: dict) -> bool:
    """Test connection to Odoo server."""
    print_header("Testing Connection")

    try:
        from skills.odoo_client import OdooClient

        print(f"\nConnecting to {config['url']}...")
        print(f"Database: {config['database']}")
        print(f"Username: {config['username']}")

        client = OdooClient(
            url=config['url'],
            database=config['database'],
            username=config['username'],
            password=config['password'],
            timeout=config['timeout']
        )

        result = client.test_connection()

        if result.get('connected'):
            print("\n[SUCCESS] Connection established!")
            print(f"  Server Version: {result.get('server_version')}")
            print(f"  User: {result.get('user_name')}")
            print(f"  Company: {result.get('company')}")
            return True
        else:
            print(f"\n[FAILED] Connection failed: {result.get('error')}")
            return False

    except ImportError:
        print("\n[ERROR] Could not import OdooClient.")
        print("Make sure you're running from the project directory.")
        return False
    except Exception as e:
        print(f"\n[ERROR] Connection test failed: {e}")
        return False


def test_permissions(config: dict) -> bool:
    """Test that user has required permissions."""
    print_header("Testing Permissions")

    try:
        from skills.odoo_client import OdooClient

        client = OdooClient(
            url=config['url'],
            database=config['database'],
            username=config['username'],
            password=config['password']
        )

        client.authenticate()

        # Test partner read
        print("\nTesting Partner access...", end=" ")
        partners = client.search_partners(limit=1)
        print(f"[OK] Found {len(partners)} partner(s)")

        # Test invoice read
        print("Testing Invoice access...", end=" ")
        invoices = client.search_invoices(limit=1)
        print(f"[OK] Found {len(invoices)} invoice(s)")

        # Test payment read
        print("Testing Payment access...", end=" ")
        payments = client.search_payments(limit=1)
        print(f"[OK] Found {len(payments)} payment(s)")

        print("\n[SUCCESS] All permission checks passed!")
        return True

    except Exception as e:
        print(f"\n[ERROR] Permission test failed: {e}")
        print("\nMake sure your user has:")
        print("  - Invoicing / Billing access")
        print("  - Contact management access")
        return False


def save_config(config: dict) -> Path:
    """Save configuration to file."""
    print_header("Saving Configuration")

    # Create credentials directory
    creds_path = Path("credentials")
    creds_path.mkdir(exist_ok=True)

    # Save config (without password for security)
    config_file = creds_path / "odoo_config.json"
    safe_config = {k: v for k, v in config.items() if k != 'password'}
    safe_config['password'] = '***STORED_IN_ENV***'

    with open(config_file, 'w') as f:
        json.dump(safe_config, f, indent=2)

    print(f"\nConfiguration saved to: {config_file}")

    # Create/update .env file
    env_file = Path(".env")
    env_content = ""

    if env_file.exists():
        env_content = env_file.read_text()
        # Remove existing Odoo settings
        lines = [l for l in env_content.split('\n')
                 if not l.startswith('ODOO_')]
        env_content = '\n'.join(lines)

    # Add Odoo settings
    odoo_env = f"""
# Odoo Configuration (added by setup_odoo.py)
ODOO_URL={config['url']}
ODOO_DATABASE={config['database']}
ODOO_USERNAME={config['username']}
ODOO_PASSWORD={config['password']}
ODOO_TIMEOUT={config['timeout']}
"""

    env_content = env_content.strip() + odoo_env

    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"Environment variables saved to: {env_file}")
    print("\n[WARNING] The .env file contains your password.")
    print("          Make sure it's in .gitignore!")

    return config_file


def create_approval_folders():
    """Create approval workflow folders."""
    print_header("Creating Approval Folders")

    folders = [
        "obsidian_vault/Pending_Approval/odoo",
        "obsidian_vault/Approved/odoo",
        "obsidian_vault/Rejected"
    ]

    for folder in folders:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {folder}")

    print("\n[OK] Approval workflow folders ready")


def test_mcp_server(config: dict) -> bool:
    """Test the MCP server functionality."""
    print_header("Testing MCP Server")

    try:
        from skills.odoo_mcp_server import OdooMCPServer, OdooConfig

        odoo_config = OdooConfig(
            url=config['url'],
            database=config['database'],
            username=config['username'],
            password=config['password'],
            timeout=config['timeout']
        )

        server = OdooMCPServer(config=odoo_config)

        if server.connect():
            print("\n[OK] MCP Server connected")

            # Get status
            status = server.get_status()
            print(f"\nServer Status:")
            print(f"  Connected: {status['connected']}")
            print(f"  URL: {status['odoo_url']}")
            print(f"  Database: {status['database']}")
            print(f"  Approval Threshold: ${status['approval_threshold']}")

            # Get financial summary
            print("\nFetching financial summary...")
            summary = server.get_financial_summary()

            print(f"\nFinancial Summary:")
            print(f"  Revenue: ${summary['revenue']['net_revenue']:,.2f}")
            print(f"  Expenses: ${summary['expenses']['net_expenses']:,.2f}")
            print(f"  Net Income: ${summary['net_income']:,.2f}")
            print(f"  Overdue Invoices: {summary['overdue_invoices']['count']}")

            server.disconnect()
            return True
        else:
            print("\n[FAILED] MCP Server connection failed")
            return False

    except Exception as e:
        print(f"\n[ERROR] MCP Server test failed: {e}")
        return False


def print_usage_instructions():
    """Print usage instructions."""
    print_header("ODOO INTEGRATION USAGE INSTRUCTIONS")
    print("""
The Odoo MCP Server integrates accounting operations with the AI Employee.

Workflow:
  1. AI creates draft invoices/payments in Odoo
  2. Approval file created in /Pending_Approval/odoo/
  3. Human reviews and moves to /Approved/odoo/
  4. Odoo watcher detects and posts the document
  5. Posted documents logged in /Done/

Available Operations:
  - Create draft customer invoices
  - Create draft vendor bills
  - Create draft payments (inbound/outbound)
  - Query financial summaries
  - Generate CEO briefing data
  - List unpaid/overdue invoices

Security:
  - All documents created as DRAFT (cannot post directly)
  - Amounts >= $100 require explicit approval
  - All actions logged in audit trail

Starting the Integration:
  The Odoo integration starts automatically with the AI Employee:
    python start_agent.py

  Or test standalone:
    python -c "from skills.odoo_mcp_server import OdooMCPServer; s=OdooMCPServer(); s.connect(); print(s.get_financial_summary())"

CEO Briefing with Odoo Data:
  The financial auditor will now pull data from Odoo when available,
  providing accurate revenue, expenses, and outstanding amounts.

Troubleshooting:
  - "Connection refused": Check Odoo is running on the specified URL
  - "Authentication failed": Verify username and password/API key
  - "Access denied": User needs Invoicing/Accounting permissions
  - "Database not found": Check database name in configuration
""")


def main():
    """Main setup function."""
    print_header("Odoo Setup for AI Employee Zoya")

    print("""
This setup will configure Odoo Community Edition integration.

Requirements:
  - Odoo Community Edition 19+ running
  - User with Invoicing/Accounting access
  - Network access to Odoo server

If you don't have Odoo installed, you can:
  1. Use Docker: docker run -d -p 8069:8069 odoo:19
  2. Install locally: https://www.odoo.com/documentation/19.0/administration/install.html
  3. Use Odoo.sh cloud trial
""")

    proceed = input("\nDo you have Odoo ready? (y/N): ").strip().lower()
    if proceed != 'y':
        print("\nSetup cancelled. Install Odoo first and run again.")
        sys.exit(0)

    # Get configuration
    config = get_odoo_config()

    # Test connection
    if not test_connection(config):
        print("\nConnection failed. Please check your settings and try again.")
        sys.exit(1)

    # Test permissions
    if not test_permissions(config):
        print("\nPermission test failed. Please check user access rights.")
        sys.exit(1)

    # Save configuration
    save_config(config)

    # Create approval folders
    create_approval_folders()

    # Test MCP server
    test_mcp_server(config)

    # Print instructions
    print_usage_instructions()

    print("\n" + "=" * 60)
    print("[SUCCESS] Odoo setup complete!")
    print("=" * 60)
    print("\nYou can now start the AI Employee with Odoo integration:")
    print("  python start_agent.py")


if __name__ == "__main__":
    main()
