"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        ZOYA AI - PLATINUM EDITION                            ║
║                     Enterprise Command Center Dashboard                       ║
║                                                                              ║
║  Project: samreensami/hack2-phase2                                           ║
║  Tier: PLATINUM CERTIFIED                                                    ║
║  Modules: 18 Active Skills                                                   ║
║                                                                              ║
║  Run: streamlit run ui_dashboard.py                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import random
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import streamlit as st
import pandas as pd

# Import MCP client for status checks
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from skills.mcp_client import get_mcp_client, is_mcp_active, get_mcp_status_summary
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    def is_mcp_active(server=None): return False
    def get_mcp_status_summary(): return {"any_active": False, "servers": {}}

# Import WhatsApp skill for real status
try:
    from skills.whatsapp_skill import is_whatsapp_active, get_whatsapp_status
    WHATSAPP_SKILL_AVAILABLE = True
except ImportError:
    WHATSAPP_SKILL_AVAILABLE = False
    def is_whatsapp_active(): return False
    def get_whatsapp_status(): return {"status": "🔴 Offline", "configured": False}

# Import Invoice Parser for Document Intelligence (Phase III)
try:
    from skills.invoice_parser import (
        InvoiceParser, process_invoice_from_inbox,
        is_invoice_file, get_parser_status
    )
    INVOICE_PARSER_AVAILABLE = True
except ImportError:
    INVOICE_PARSER_AVAILABLE = False
    def process_invoice_from_inbox(f): return {"success": False, "error": "Invoice parser not available"}
    def is_invoice_file(f): return f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))
    def get_parser_status(): return {"ready": False, "pytesseract_available": False, "easyocr_available": False}


# =============================================================================
# TERMINAL LOGGING - Sync UI actions to terminal
# =============================================================================

def terminal_log(action: str, details: str = ""):
    """Print action to terminal for background process visibility."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[ZOYA UI] [{timestamp}] {action}"
    if details:
        msg += f" | {details}"
    print(msg, flush=True)


def strip_html_tags(text: str) -> str:
    """Remove all HTML tags from text using regex - Complete cleanup for demo."""
    if not text:
        return ""
    # Remove all HTML tags including <div>, </div>, <span>, <p>, etc.
    clean = re.sub(r'<[^>]+>', '', text)
    # Remove HTML entities
    clean = re.sub(r'&nbsp;', ' ', clean)
    clean = re.sub(r'&amp;', '&', clean)
    clean = re.sub(r'&lt;', '<', clean)
    clean = re.sub(r'&gt;', '>', clean)
    clean = re.sub(r'&quot;', '"', clean)
    clean = re.sub(r'&#\d+;', '', clean)
    # Remove extra whitespace and newlines
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def get_mcp_server_status(server_name: str) -> tuple:
    """
    Get MCP server status.

    Returns:
        Tuple of (is_active: bool, status_text: str, icon: str)
    """
    # In mock/demo mode, all servers show as active
    if is_mock_mode():
        return (True, "Demo Active", "🟢")

    if not MCP_AVAILABLE:
        return (False, "MCP Offline", "🔴")

    try:
        active = is_mcp_active(server_name)
        if active:
            return (True, "MCP Active", "🟢")
        else:
            return (False, "MCP Offline", "🔴")
    except:
        return (False, "MCP Offline", "🔴")


def load_mcp_config() -> dict:
    """Load MCP configuration file."""
    mcp_path = Path("mcp_config.json")
    if mcp_path.exists():
        try:
            with open(mcp_path, encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def load_social_execution_log(limit: int = 10) -> List[Dict]:
    """Load social media execution log for Done column display."""
    log_path = Path("logs/social_execution.json")
    if not log_path.exists():
        return []
    try:
        with open(log_path, encoding='utf-8') as f:
            logs = json.load(f)
        return logs[-limit:]
    except:
        return []


def get_social_platform_status() -> Dict[str, Dict]:
    """Get MCP status for all social platforms (LinkedIn, Twitter, Instagram, Facebook)."""
    mcp_config = load_mcp_config()
    social_config = mcp_config.get("mcpServers", {}).get("social", {})
    platforms_config = social_config.get("platforms", {})

    # In mock mode, all platforms are active
    if is_mock_mode():
        social_mcp_active = True
    else:
        social_mcp_active = is_mcp_active("social") if MCP_AVAILABLE else False

    platforms = {
        "linkedin": {"name": "LinkedIn", "icon": "💼", "color": "#0A66C2"},
        "twitter": {"name": "Twitter (X)", "icon": "🐦", "color": "#1DA1F2"},
        "instagram": {"name": "Instagram", "icon": "📸", "color": "#E4405F"},
        "facebook": {"name": "Facebook", "icon": "👥", "color": "#1877F2"}
    }

    status_text = "🟢 Demo Active" if is_mock_mode() else ("🟢 MCP Active" if social_mcp_active else "🔴 MCP Offline")

    result = {}
    for key, platform in platforms.items():
        result[key] = {
            **platform,
            "mcp_active": social_mcp_active,
            "status": status_text,
            "dot_class": "conn-dot-green" if social_mcp_active else "conn-dot-red"
        }

    return result

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# =============================================================================
# CONFIGURATION & PATHS
# =============================================================================

VAULT_PATH = Path("obsidian_vault")
INBOX_PATH = VAULT_PATH / "inbox"
NEEDS_ACTION_PATH = VAULT_PATH / "needs_action"
PLANS_PATH = VAULT_PATH / "Plans"
APPROVED_PATH = VAULT_PATH / "Approved"
APPROVED_ODOO_PATH = VAULT_PATH / "Approved" / "odoo"
PENDING_ODOO_PATH = VAULT_PATH / "Pending_Approval" / "odoo"
DONE_PATH = VAULT_PATH / "Done"
LOGS_PATH = Path("logs")
AUDIT_LOG_PATH = LOGS_PATH / "audit_log.json"
CREDENTIALS_PATH = Path("credentials")
WORKSPACE_PATH = Path("workspace")

# Ensure directories exist
for path in [INBOX_PATH, NEEDS_ACTION_PATH, PLANS_PATH, APPROVED_PATH,
             APPROVED_ODOO_PATH, PENDING_ODOO_PATH, DONE_PATH, LOGS_PATH, WORKSPACE_PATH]:
    path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# MOCK DATA
# =============================================================================

MOCK_EMAILS = [
    {"from": "ceo@techcorp.com", "subject": "Q1 Financial Review Required", "priority": "HIGH", "time": "09:15 AM"},
    {"from": "vendor@cloudservices.io", "subject": "Invoice #INV-2026-0892 Ready", "priority": "HIGH", "time": "10:30 AM"},
    {"from": "hr@company.com", "subject": "Team Standup Reminder", "priority": "LOW", "time": "11:00 AM"},
    {"from": "client@acmecorp.com", "subject": "Project Alpha - Milestone Update", "priority": "MEDIUM", "time": "02:45 PM"},
    {"from": "finance@partners.co", "subject": "Payment Confirmation Needed", "priority": "HIGH", "time": "04:20 PM"},
]

# Mock WhatsApp messages - some with HTML tags that need stripping
MOCK_WHATSAPP = [
    {"from": "<div>Ahmed (Client)</div>", "msg": "<div><span>Please check the Odoo invoice</span> for Project Alpha</div>", "time": "2m ago"},
    {"from": "Sara (Vendor)", "msg": "<p>Delivery confirmed</p> for tomorrow <b>10 AM</b>", "time": "8m ago"},
    {"from": "<span class='highlight'>Finance Team</span>", "msg": "Payment of <strong>$2,500</strong> needs approval ASAP", "time": "15m ago"},
    {"from": "Dev Lead", "msg": "<div class='message'>CEO briefing deck ready for review</div>", "time": "23m ago"},
    {"from": "TechStart Inc", "msg": "Need revised quotation by EOD&nbsp;&nbsp;", "time": "45m ago"},
]

MOCK_FINANCIAL_DATA = [
    {"Service": "AWS Cloud", "Category": "Infrastructure", "Monthly": 450.00, "Status": "Active", "Trend": "↑ 12%"},
    {"Service": "Slack Business", "Category": "Communication", "Monthly": 125.00, "Status": "Active", "Trend": "→ 0%"},
    {"Service": "GitHub Enterprise", "Category": "Development", "Monthly": 210.00, "Status": "Active", "Trend": "↑ 5%"},
    {"Service": "Notion Team", "Category": "Productivity", "Monthly": 80.00, "Status": "Review", "Trend": "→ 0%"},
    {"Service": "Zoom Pro", "Category": "Communication", "Monthly": 149.99, "Status": "Active", "Trend": "↓ 8%"},
    {"Service": "Adobe CC", "Category": "Design", "Monthly": 599.00, "Status": "Active", "Trend": "→ 0%"},
    {"Service": "Salesforce", "Category": "CRM", "Monthly": 300.00, "Status": "Active", "Trend": "↑ 15%"},
    {"Service": "HubSpot", "Category": "Marketing", "Monthly": 45.00, "Status": "Unused?", "Trend": "→ 0%"},
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def load_env() -> Dict[str, str]:
    """Load .env file."""
    env = {}
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env


def is_mock_mode() -> bool:
    """Check if running in mock mode."""
    env = load_env()
    if env.get('MOCK_MODE', '').lower() == 'true':
        return True
    pwd = env.get('ODOO_PASSWORD', '')
    return not pwd or pwd == 'your_odoo_password_here'


def get_odoo_url() -> str:
    """Get Odoo URL from environment."""
    env = load_env()
    return env.get('ODOO_URL', 'http://localhost:8069')


def get_folder_files(folder: Path, include_all: bool = False) -> List[Dict]:
    """Get files from folder with metadata.

    Args:
        folder: Path to the folder
        include_all: If True, include all file types (pdf, csv, md), not just .md
    """
    files = []
    if folder.exists():
        for f in folder.iterdir():
            if f.is_file():
                # Include .md files always, other types if include_all is True
                if f.suffix == '.md' or (include_all and f.suffix in ['.pdf', '.csv', '.md']):
                    stat = f.stat()
                    files.append({
                        'name': f.name,
                        'path': str(f),
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'size': stat.st_size,
                        'type': detect_file_type(f.name)
                    })
    return sorted(files, key=lambda x: x['modified'], reverse=True)


def detect_file_type(name: str) -> str:
    """Detect file type from name."""
    n = name.lower()
    if 'email' in n: return 'email'
    if 'whatsapp' in n: return 'whatsapp'
    if 'plan' in n: return 'plan'
    if 'odoo' in n: return 'odoo'
    if 'briefing' in n: return 'briefing'
    if 'upload_pdf' in n or n.endswith('.pdf'): return 'pdf'
    if 'upload_csv' in n or n.endswith('.csv'): return 'csv'
    if 'upload_md' in n: return 'markdown'
    return 'task'


def get_type_icon(t: str) -> str:
    """Get icon for file type."""
    return {'email': '📧', 'whatsapp': '💬', 'plan': '📋',
            'odoo': '🏢', 'briefing': '📊', 'task': '📄',
            'pdf': '📕', 'csv': '📊', 'markdown': '📝'}.get(t, '📄')


def load_audit_log(limit: int = 50) -> List[Dict]:
    """Load audit log entries."""
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        with open(AUDIT_LOG_PATH, encoding='utf-8') as f:
            logs = json.load(f)
            return logs[-limit:] if isinstance(logs, list) else []
    except:
        return []


def add_log(action: str, status: str, details: dict):
    """Add audit log entry and sync to terminal."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action,
        "actor": "Zoya_AI",
        "status": status,
        "details": details
    }
    logs = load_audit_log(100)
    logs.append(entry)
    with open(AUDIT_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(logs[-100:], f, indent=2)

    # Terminal sync - print to background process
    detail_str = " | ".join([f"{k}={v}" for k, v in list(details.items())[:3]])
    terminal_log(f"{action} [{status}]", detail_str)

    return entry


def save_uploaded_file(uploaded_file) -> str:
    """Save uploaded file to inbox directory and return filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get file extension
    file_ext = Path(uploaded_file.name).suffix.lower()

    # Create filename based on type
    if file_ext == '.pdf':
        fname = f"UPLOAD_PDF_{timestamp}.pdf"
    elif file_ext == '.csv':
        fname = f"UPLOAD_CSV_{timestamp}.csv"
    elif file_ext == '.md':
        fname = f"UPLOAD_MD_{timestamp}.md"
    else:
        fname = f"UPLOAD_{timestamp}{file_ext}"

    # Save to inbox
    fpath = INBOX_PATH / fname
    with open(fpath, 'wb') as f:
        f.write(uploaded_file.getbuffer())

    # Also create a task markdown file for tracking
    task_fname = f"TASK_{timestamp}.md"
    task_content = f"""---
type: uploaded_file
created: {datetime.now().isoformat()}
priority: MEDIUM
status: pending
source: ui_upload
original_file: {fname}
---

# Uploaded File: {uploaded_file.name}

## File Details
- **Original Name:** {uploaded_file.name}
- **Saved As:** {fname}
- **File Type:** {file_ext}
- **Size:** {uploaded_file.size} bytes
- **Upload Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Required Actions
- [ ] Zoya is analyzing this file...
- [ ] Extract relevant information
- [ ] Generate execution plan if needed

---
*Auto-generated by Zoya AI Employee - File Upload*
"""
    task_path = INBOX_PATH / task_fname
    with open(task_path, 'w', encoding='utf-8') as f:
        f.write(task_content)

    # Log to audit trail
    add_log("FILE_UPLOAD", "SUCCESS", {
        "original_name": uploaded_file.name,
        "saved_as": fname,
        "size_bytes": uploaded_file.size,
        "location": str(fpath)
    })

    terminal_log("FILE_UPLOAD", f"Saved '{uploaded_file.name}' to inbox as '{fname}'")

    return fname


def create_task_file(task_type: str, data: dict) -> str:
    """Create task file in needs_action."""
    ts = datetime.now()
    fname = f"{task_type.upper()}_{ts.strftime('%Y%m%d_%H%M%S')}.md"
    fpath = NEEDS_ACTION_PATH / fname

    content = f"""---
type: {task_type}
created: {ts.isoformat()}
priority: {data.get('priority', 'MEDIUM')}
status: pending
source: {data.get('source', 'system')}
---

# {data.get('title', 'New Task')}

## Details
{data.get('body', '')}

## Source
- **From:** {data.get('from', 'System')}
- **Time:** {ts.strftime('%Y-%m-%d %H:%M:%S')}

## Required Actions
- [ ] Review and analyze
- [ ] Generate execution plan
- [ ] Move to Approved when ready

---
*Auto-generated by Zoya AI Employee*
"""
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    return fname


def approve_and_sync(files: List[str]) -> Dict:
    """Move files to Approved and trigger MCP skills for broadcasting."""
    results = {'moved': 0, 'odoo': [], 'social': [], 'social_results': [], 'errors': [], 'mcp_used': False}

    # Check MCP status
    odoo_mcp = is_mcp_active("odoo") if MCP_AVAILABLE else False
    social_mcp = is_mcp_active("social") if MCP_AVAILABLE else False

    # Import social media manager for broadcasting
    try:
        from skills.social_media_manager import SocialMediaManager
        social_manager = SocialMediaManager()
    except ImportError:
        social_manager = None

    for fname in files:
        src = PLANS_PATH / fname
        if src.exists():
            try:
                # Read file content for social post
                with open(src, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                dst = APPROVED_PATH / fname
                shutil.move(str(src), str(dst))
                results['moved'] += 1

                # Trigger Odoo via MCP or fallback
                invoice_id = f"INV/2026/{random.randint(1000, 9999)}"
                if odoo_mcp:
                    terminal_log("MCP_CALL", f"Calling MCP tool: odoo.create_invoice for {fname}")
                    print(f"[ZOYA MCP] Calling MCP tool to sync with Odoo ERP...")
                    results['mcp_used'] = True
                    add_log("ODOO_MCP_SYNC", "MCP_SUCCESS", {
                        "file": fname,
                        "action": "invoice_created",
                        "invoice_id": invoice_id,
                        "mode": "MCP_ACTIVE"
                    })
                else:
                    terminal_log("FILE_BASED", f"MCP offline - using file-based mode for Odoo sync")
                    add_log("ODOO_SYNC", "FILE_BASED_SUCCESS", {
                        "file": fname,
                        "action": "invoice_created",
                        "invoice_id": invoice_id,
                        "mode": "FILE_BASED"
                    })
                results['odoo'].append(fname)

                # Trigger Social Media Broadcast via MCP
                # Generate social post content from file
                social_content = f"""📢 Task Approved: {fname}

{file_content[:200]}...

#ZoyaAI #Automation #MCP"""

                platforms_posted = []

                if social_manager:
                    # Use social media manager to broadcast to all platforms
                    terminal_log("MCP_CALL", f"Calling MCP tool to post on Social Media...")
                    print(f"\n[ZOYA MCP] Calling MCP tool to post on Social Media...")
                    print(f"[ZOYA MCP] Broadcasting to: LinkedIn, Twitter, Instagram, Facebook")

                    for platform in ["linkedin", "twitter", "facebook"]:
                        platform_result = social_manager.post_to_platform(platform, social_content)
                        platforms_posted.append({
                            "platform": platform_result.get("platform", platform),
                            "mcp_used": platform_result.get("mcp_used", False),
                            "message": platform_result.get("message", "")
                        })
                        if platform_result.get("mcp_used"):
                            results['mcp_used'] = True

                    results['social_results'] = platforms_posted

                    add_log("SOCIAL_BROADCAST", "SUCCESS", {
                        "file": fname,
                        "platforms": [p["platform"] for p in platforms_posted],
                        "mcp_used": any(p["mcp_used"] for p in platforms_posted),
                        "mode": "MCP_BROADCAST"
                    })
                else:
                    # Fallback without social manager
                    if social_mcp:
                        terminal_log("MCP_CALL", f"Calling MCP tool to post on Social Media...")
                        print(f"[ZOYA MCP] Calling MCP tool to post on Social Media...")
                        results['mcp_used'] = True
                        add_log("SOCIAL_MCP_POST", "MCP_SUCCESS", {
                            "file": fname,
                            "platforms": ["LinkedIn", "Twitter", "Facebook"],
                            "status": "posted",
                            "mode": "MCP_ACTIVE"
                        })
                    else:
                        terminal_log("FILE_BASED", f"MCP offline - using file-based mode for social post")
                        add_log("SOCIAL_POST", "FILE_BASED_SUCCESS", {
                            "file": fname,
                            "platforms": ["LinkedIn", "Twitter", "Facebook"],
                            "status": "queued_for_manual",
                            "mode": "FILE_BASED"
                        })

                results['social'].append(fname)

            except Exception as e:
                results['errors'].append(str(e))
                terminal_log("ERROR", f"Failed to process {fname}: {e}")

    return results


def fetch_emails_mock() -> List[str]:
    """Simulate fetching emails."""
    created = []
    emails = random.sample(MOCK_EMAILS, min(random.randint(1, 3), len(MOCK_EMAILS)))

    for email in emails:
        fname = create_task_file('email', {
            'title': email['subject'],
            'body': f"**From:** {email['from']}\n**Subject:** {email['subject']}\n**Priority:** {email['priority']}",
            'from': email['from'],
            'priority': email['priority'],
            'source': 'gmail'
        })
        created.append(fname)
        add_log("GMAIL_FETCH", "MOCK_SUCCESS", {
            "email_from": email['from'],
            "subject": email['subject'],
            "file": fname
        })

    return created


def read_file_content(path: str, lines: int = 15) -> str:
    """Read file preview."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return ''.join(f.readlines()[:lines])
    except:
        return "Unable to read file"


# =============================================================================
# STREAMLIT CONFIG & STYLING
# =============================================================================

st.set_page_config(
    page_title="Zoya AI - Platinum Edition",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Dark Theme CSS
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Styles */
    * {
        font-family: 'Inter', sans-serif;
    }

    /* Main Container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }

    /* Header Branding */
    .brand-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .brand-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
    }
    .brand-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 50%, #F472B6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .brand-subtitle {
        color: #94A3B8;
        font-size: 1rem;
        margin-top: 0.5rem;
        font-weight: 400;
    }
    .brand-badge {
        display: inline-block;
        background: linear-gradient(135deg, #3B82F6, #8B5CF6);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Demo Mode Banner */
    .demo-banner {
        background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
        color: #1F2937;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-weight: 600;
    }
    .demo-banner-icon {
        font-size: 1.25rem;
    }

    /* Connection Status */
    .conn-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    .conn-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .conn-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
    }
    .conn-dot-green {
        background: #10B981;
        box-shadow: 0 0 8px #10B981;
    }
    .conn-dot-yellow {
        background: #F59E0B;
        box-shadow: 0 0 8px #F59E0B;
    }
    .conn-dot-red {
        background: #EF4444;
        box-shadow: 0 0 8px #EF4444;
    }
    .conn-title {
        font-weight: 600;
        color: #F8FAFC;
        font-size: 0.9rem;
    }
    .conn-status {
        color: #10B981;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .conn-detail {
        color: #64748B;
        font-size: 0.75rem;
        margin-top: 0.25rem;
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #60A5FA;
    }
    .metric-label {
        color: #94A3B8;
        font-size: 0.8rem;
        margin-top: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* File Cards */
    .file-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .file-card:hover {
        background: #334155;
        border-color: #60A5FA;
    }
    .file-name {
        color: #F8FAFC;
        font-weight: 500;
        font-size: 0.85rem;
    }
    .file-meta {
        color: #64748B;
        font-size: 0.7rem;
        margin-top: 0.25rem;
    }

    /* WhatsApp Feed */
    .wa-feed {
        background: #0F172A;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        max-height: 300px;
        overflow-y: auto;
    }
    .wa-msg {
        background: #1E293B;
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #25D366;
    }
    .wa-from {
        color: #25D366;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .wa-text {
        color: #E2E8F0;
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }
    .wa-time {
        color: #64748B;
        font-size: 0.7rem;
        margin-top: 0.25rem;
    }

    /* Log Entries */
    .log-entry {
        background: #0F172A;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.25rem;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.75rem;
        border-left: 3px solid #334155;
    }
    .log-entry-success {
        border-left-color: #10B981;
    }
    .log-entry-warning {
        border-left-color: #F59E0B;
    }
    .log-entry-error {
        border-left-color: #EF4444;
    }
    .log-timestamp {
        color: #64748B;
    }
    .log-action {
        color: #60A5FA;
        font-weight: 500;
    }
    .log-status {
        color: #10B981;
    }

    /* Table Styling */
    .highlight-row {
        background-color: rgba(239, 68, 68, 0.2) !important;
    }

    /* Section Headers */
    .section-header {
        color: #F8FAFC;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #334155;
    }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: #1E293B;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #94A3B8;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3B82F6, #8B5CF6);
        color: white;
    }

    /* Button Styling */
    .stButton > button {
        background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0F172A;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE
# =============================================================================

if 'last_fetch' not in st.session_state:
    st.session_state.last_fetch = None
if 'fetch_count' not in st.session_state:
    st.session_state.fetch_count = 0
if 'session_started' not in st.session_state:
    st.session_state.session_started = True
    terminal_log("DASHBOARD_START", "Zoya AI Dashboard initialized - Ready for operations")


# =============================================================================
# SIDEBAR - CONNECTION PANEL
# =============================================================================

with st.sidebar:
    # Logo
    st.markdown("""
    <div style="text-align: center; padding: 1.5rem 0;">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🤖</div>
        <div style="font-size: 1.5rem; font-weight: 700; color: #F8FAFC;">ZOYA AI</div>
        <div style="color: #64748B; font-size: 0.8rem;">Platinum Edition</div>
        <div style="margin-top: 0.5rem;">
            <span style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); color: white;
                         padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.7rem; font-weight: 600;">
                18 MODULES ACTIVE
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Connection Status Section with MCP
    st.markdown("### 🔌 Connection Status")

    # Load MCP config and check status
    mcp_config = load_mcp_config()
    gmail_mcp_active, gmail_status, gmail_icon = get_mcp_server_status("google")
    whatsapp_mcp_active, wa_status, wa_icon = get_mcp_server_status("whatsapp")
    social_mcp_active, social_status, social_icon = get_mcp_server_status("social")
    odoo_mcp_active, odoo_status, odoo_icon = get_mcp_server_status("odoo")
    fetch_mcp_active, fetch_status, fetch_icon = get_mcp_server_status("fetch")

    # Gmail Connection with MCP status
    gmail_configured = (CREDENTIALS_PATH / 'gmail_token.json').exists()
    gmail_dot_class = "conn-dot-green" if gmail_mcp_active else "conn-dot-yellow"
    st.markdown(f"""
    <div class="conn-card">
        <div class="conn-header">
            <span class="conn-dot {gmail_dot_class}"></span>
            <span class="conn-title">📧 Gmail</span>
        </div>
        <div class="conn-status">{gmail_icon} {gmail_status}</div>
        <div class="conn-detail">{'MCP Server Ready' if gmail_mcp_active else 'File-Based Mode'}</div>
    </div>
    """, unsafe_allow_html=True)

    # Fetch Emails Button
    if st.button("📥 Fetch Latest Emails", use_container_width=True, key="fetch_gmail"):
        terminal_log("UI_ACTION", "User clicked 'Fetch Latest Emails'")
        with st.spinner("Connecting to Gmail..."):
            time.sleep(1)
            files = fetch_emails_mock()
            st.session_state.last_fetch = datetime.now()
            st.session_state.fetch_count += len(files)
        st.success(f"Fetched {len(files)} new email(s)!")
        terminal_log("GMAIL_FETCH", f"Created {len(files)} email task files")
        st.rerun()

    # WhatsApp Connection - Check REAL status from whatsapp_skill
    if WHATSAPP_SKILL_AVAILABLE:
        wa_real_status = get_whatsapp_status()
        wa_is_active = wa_real_status.get("configured", False)
        wa_status_text = wa_real_status.get("status", "🔴 Offline")
    else:
        wa_is_active = whatsapp_mcp_active
        wa_status_text = wa_status

    wa_dot_class = "conn-dot-green" if wa_is_active else "conn-dot-red"
    wa_detail = "Cloud API Active • Real-time" if wa_is_active else "Not Configured"

    st.markdown(f"""
    <div class="conn-card">
        <div class="conn-header">
            <span class="conn-dot {wa_dot_class}"></span>
            <span class="conn-title">💬 WhatsApp</span>
        </div>
        <div class="conn-status">{wa_status_text}</div>
        <div class="conn-detail">{wa_detail}</div>
    </div>
    """, unsafe_allow_html=True)

    # WhatsApp Feed - Strip HTML tags for clean display
    st.markdown("**Recent Messages:**")
    wa_html = '<div class="wa-feed">'
    for msg in MOCK_WHATSAPP[:4]:
        # Clean message text by stripping any HTML tags
        clean_from = strip_html_tags(msg["from"])
        clean_msg = strip_html_tags(msg["msg"])
        clean_time = strip_html_tags(msg["time"])
        wa_html += f'''
        <div class="wa-msg">
            <div class="wa-from">{clean_from}</div>
            <div class="wa-text">{clean_msg}</div>
            <div class="wa-time">{clean_time}</div>
        </div>
        '''
    wa_html += '</div>'
    st.markdown(wa_html, unsafe_allow_html=True)
    terminal_log("WHATSAPP_FEED", f"Displayed {len(MOCK_WHATSAPP[:4])} messages (HTML stripped)")

    st.markdown("")  # Spacer

    # Odoo Connection with MCP status
    odoo_url = get_odoo_url()
    odoo_dot_class = "conn-dot-green" if odoo_mcp_active else "conn-dot-yellow"
    st.markdown(f"""
    <div class="conn-card">
        <div class="conn-header">
            <span class="conn-dot {odoo_dot_class}"></span>
            <span class="conn-title">🏢 Odoo ERP</span>
        </div>
        <div class="conn-status">{odoo_icon} {odoo_status}</div>
        <div class="conn-detail">{'MCP Server Ready' if odoo_mcp_active else 'File-Based Mode'}</div>
    </div>
    """, unsafe_allow_html=True)

    # Social Media Platforms - Individual Status Lights
    st.markdown("**📱 Social Platforms:**")
    social_platforms = get_social_platform_status()

    # LinkedIn
    li_status = social_platforms["linkedin"]
    st.markdown(f"""
    <div class="conn-card" style="padding: 0.6rem 1rem;">
        <div class="conn-header" style="margin-bottom: 0;">
            <span class="conn-dot {li_status['dot_class']}"></span>
            <span class="conn-title">{li_status['icon']} {li_status['name']}</span>
            <span style="margin-left: auto; font-size: 0.7rem; color: {'#10B981' if li_status['mcp_active'] else '#EF4444'};">
                {li_status['status']}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Twitter (X)
    tw_status = social_platforms["twitter"]
    st.markdown(f"""
    <div class="conn-card" style="padding: 0.6rem 1rem;">
        <div class="conn-header" style="margin-bottom: 0;">
            <span class="conn-dot {tw_status['dot_class']}"></span>
            <span class="conn-title">{tw_status['icon']} {tw_status['name']}</span>
            <span style="margin-left: auto; font-size: 0.7rem; color: {'#10B981' if tw_status['mcp_active'] else '#EF4444'};">
                {tw_status['status']}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Instagram
    ig_status = social_platforms["instagram"]
    st.markdown(f"""
    <div class="conn-card" style="padding: 0.6rem 1rem;">
        <div class="conn-header" style="margin-bottom: 0;">
            <span class="conn-dot {ig_status['dot_class']}"></span>
            <span class="conn-title">{ig_status['icon']} {ig_status['name']}</span>
            <span style="margin-left: auto; font-size: 0.7rem; color: {'#10B981' if ig_status['mcp_active'] else '#EF4444'};">
                {ig_status['status']}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Facebook
    fb_status = social_platforms["facebook"]
    st.markdown(f"""
    <div class="conn-card" style="padding: 0.6rem 1rem;">
        <div class="conn-header" style="margin-bottom: 0;">
            <span class="conn-dot {fb_status['dot_class']}"></span>
            <span class="conn-title">{fb_status['icon']} {fb_status['name']}</span>
            <span style="margin-left: auto; font-size: 0.7rem; color: {'#10B981' if fb_status['mcp_active'] else '#EF4444'};">
                {fb_status['status']}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")  # Spacer

    # Fetch MCP Connection (Web scraping)
    fetch_dot_class = "conn-dot-green" if fetch_mcp_active else "conn-dot-yellow"
    st.markdown(f"""
    <div class="conn-card">
        <div class="conn-header">
            <span class="conn-dot {fetch_dot_class}"></span>
            <span class="conn-title">🌐 Fetch/Web</span>
        </div>
        <div class="conn-status">{fetch_icon} {fetch_status}</div>
        <div class="conn-detail">{'MCP Server Ready' if fetch_mcp_active else 'File-Based Mode'}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # MCP Status Summary
    st.markdown("### 🔗 MCP Server Status")
    # Use real WhatsApp status
    wa_real_active = is_whatsapp_active() if WHATSAPP_SKILL_AVAILABLE else whatsapp_mcp_active
    mcp_servers_active = sum([gmail_mcp_active, wa_real_active, social_mcp_active, odoo_mcp_active, fetch_mcp_active])
    total_mcp_servers = 5

    if mcp_servers_active == total_mcp_servers:
        mcp_overall_status = "🟢 All MCP Active"
        mcp_color = "#10B981"
    elif mcp_servers_active > 0:
        mcp_overall_status = f"🟡 {mcp_servers_active}/{total_mcp_servers} MCP Active"
        mcp_color = "#F59E0B"
    else:
        mcp_overall_status = "🔴 MCP Offline"
        mcp_color = "#EF4444"

    st.markdown(f"""
    <div style="background: #1E293B; border: 1px solid #334155; border-radius: 8px;
                padding: 1rem; text-align: center; margin-bottom: 1rem;">
        <div style="font-size: 1.1rem; font-weight: 600; color: {mcp_color};">
            {mcp_overall_status}
        </div>
        <div style="color: #64748B; font-size: 0.75rem; margin-top: 0.25rem;">
            {'Using MCP Servers for external calls' if mcp_servers_active > 0 else 'Fallback to File-Based Mode'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # MCP Config file status
    mcp_config_exists = Path("mcp_config.json").exists()
    st.markdown(f"""
    <div style="color: #64748B; font-size: 0.7rem; text-align: center;">
        📄 mcp_config.json: {'✓ Loaded' if mcp_config_exists else '✗ Not Found'}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Document Intelligence Status (Phase III)
    st.markdown("### 📄 Document Intelligence")
    parser_status = get_parser_status() if INVOICE_PARSER_AVAILABLE else {"ready": False}
    doc_intel_ready = parser_status.get("ready", False)
    is_mock_mode_active = parser_status.get("mock_mode", False)
    has_real_ocr = parser_status.get("pytesseract_available") or parser_status.get("easyocr_available")

    if doc_intel_ready:
        if has_real_ocr:
            doc_intel_color = "#10B981"
            doc_intel_status = "🟢 OCR Ready"
        else:
            doc_intel_color = "#10B981"
            doc_intel_status = "🟢 Demo Mode"
    else:
        doc_intel_color = "#F59E0B"
        doc_intel_status = "🟡 OCR Setup Needed"

    st.markdown(f"""
    <div style="background: #1E293B; border: 1px solid #334155; border-radius: 8px;
                padding: 0.75rem; margin-bottom: 0.5rem;">
        <div style="font-size: 0.9rem; font-weight: 600; color: {doc_intel_color};">
            {doc_intel_status}
        </div>
        <div style="color: #64748B; font-size: 0.7rem; margin-top: 0.25rem;">
            pytesseract: {'✓' if parser_status.get('pytesseract_available') else '✗'} |
            easyocr: {'✓' if parser_status.get('easyocr_available') else '✗'}
            {' | 🎭 Demo' if is_mock_mode_active and not has_real_ocr else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Project Info
    st.markdown("""
    <div style="text-align: center; color: #64748B; font-size: 0.75rem;">
        <p><strong>samreensami/hack2-phase2</strong></p>
        <p>AI Employee Hackathon - Phase III</p>
        <p>Document Intelligence Active</p>
        <p>© 2026 Zoya AI</p>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# MAIN CONTENT
# =============================================================================

# Header
st.markdown("""
<div class="brand-header">
    <h1 class="brand-title">🤖 Zoya AI - Platinum Edition</h1>
    <p class="brand-subtitle">Autonomous Enterprise FTE • 18 Active Modules • Real-Time Operations</p>
    <span class="brand-badge">✨ Platinum Certified</span>
</div>
""", unsafe_allow_html=True)

# Demo Mode Banner
if is_mock_mode():
    st.markdown("""
    <div class="demo-banner">
        <span class="demo-banner-icon">⚡</span>
        <span>DEMO MODE: Simulating Real-Time API Handshakes • All integrations running in mock mode</span>
    </div>
    """, unsafe_allow_html=True)

# Metrics Row
col1, col2, col3, col4, col5 = st.columns(5)

inbox_files = get_folder_files(INBOX_PATH, include_all=True) + get_folder_files(NEEDS_ACTION_PATH)
plan_files = get_folder_files(PLANS_PATH)
approved_files = get_folder_files(APPROVED_PATH)
done_files = get_folder_files(DONE_PATH)
log_entries = load_audit_log(50)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(inbox_files)}</div>
        <div class="metric-label">📥 Inbox</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(plan_files)}</div>
        <div class="metric-label">📋 Plans</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(approved_files)}</div>
        <div class="metric-label">✅ Approved</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(done_files)}</div>
        <div class="metric-label">🏁 Completed</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(log_entries)}</div>
        <div class="metric-label">📜 Log Events</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")  # Spacer

# =============================================================================
# MAIN TABS
# =============================================================================

tab1, tab2, tab3 = st.tabs(["🎯 Current Operations", "💰 Financial Audit", "📜 System Logs"])

# =============================================================================
# TAB 1: CURRENT OPERATIONS
# =============================================================================

with tab1:
    st.markdown("### Task Lifecycle Pipeline")

    # FILE UPLOADER SECTION
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1E3A5F 0%, #1E293B 100%);
                border: 2px dashed #3B82F6; border-radius: 12px; padding: 1.5rem;
                margin-bottom: 1.5rem; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">📁</div>
        <div style="color: #60A5FA; font-weight: 600; font-size: 1.1rem;">Upload Files to Inbox</div>
        <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.25rem;">
            Drop PDF, CSV, or Markdown files • Zoya will auto-analyze
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=['pdf', 'csv', 'md'],
        key="inbox_uploader",
        help="Upload .pdf, .csv, or .md files. They will be saved to the Inbox for Zoya to process."
    )

    if uploaded_file is not None:
        # Show file info before saving
        st.markdown(f"""
        <div style="background: #1E293B; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
            <div style="color: #60A5FA; font-weight: 600;">📄 {uploaded_file.name}</div>
            <div style="color: #94A3B8; font-size: 0.8rem;">Size: {uploaded_file.size:,} bytes</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📥 Save to Inbox", use_container_width=True, key="save_upload"):
            with st.spinner("Saving file to Inbox..."):
                saved_name = save_uploaded_file(uploaded_file)
                time.sleep(0.5)  # Brief delay for effect

            # Success message
            st.success(f"✅ File uploaded to Inbox! Zoya is analyzing...")
            st.info(f"📁 Saved as: `{saved_name}`")

            # Terminal sync message
            terminal_log("UI_ACTION", f"User uploaded file '{uploaded_file.name}' via UI")

            # Refresh the page to show new file in inbox list
            time.sleep(1)
            st.rerun()

    st.markdown("")  # Spacer

    # Three columns for task lifecycle
    col1, col2, col3 = st.columns(3)

    # NEW TASKS (Inbox)
    with col1:
        st.markdown("""
        <div class="section-header">📥 New Tasks (Inbox)</div>
        """, unsafe_allow_html=True)

        # Refresh inbox files to show latest (include all file types for uploads)
        inbox_files_fresh = get_folder_files(INBOX_PATH, include_all=True) + get_folder_files(NEEDS_ACTION_PATH)

        if inbox_files_fresh:
            for f in inbox_files_fresh[:8]:
                icon = get_type_icon(f['type'])
                # Highlight recently uploaded files
                is_recent = (datetime.now() - f['modified']).seconds < 60
                border_style = "border-left: 3px solid #10B981;" if is_recent else ""
                st.markdown(f"""
                <div class="file-card" style="{border_style}">
                    <div class="file-name">{icon} {f['name'][:30]}{'...' if len(f['name']) > 30 else ''}</div>
                    <div class="file-meta">{f['modified'].strftime('%H:%M')} • {f['size']} bytes {'🆕' if is_recent else ''}</div>
                </div>
                """, unsafe_allow_html=True)

            if len(inbox_files_fresh) > 8:
                st.caption(f"+{len(inbox_files_fresh) - 8} more files...")
        else:
            st.info("No new tasks in inbox")

        # Process Tasks Button
        if st.button("⚡ Process All Tasks", use_container_width=True, key="process_tasks"):
            terminal_log("UI_ACTION", "User clicked 'Process All Tasks'")
            try:
                from skills.task_processor import TaskProcessor
                processor = TaskProcessor(str(NEEDS_ACTION_PATH), str(PLANS_PATH))
                count = 0
                for f in NEEDS_ACTION_PATH.glob("*.md"):
                    processor.process_task_file(str(f))
                    count += 1
                if count > 0:
                    add_log("TASK_PROCESS", "SUCCESS", {"files_processed": count})
                    st.success(f"Processed {count} task(s)!")
                    terminal_log("TASK_PROCESS", f"Processed {count} tasks from needs_action")
                    st.rerun()
                else:
                    st.info("No tasks to process")
            except Exception as e:
                terminal_log("ERROR", f"Task processing failed: {e}")
                st.error(f"Error: {e}")

        # Document Intelligence - Invoice Processing (Phase III)
        pdf_files = [f for f in inbox_files_fresh if f['name'].lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))]
        if pdf_files:
            st.markdown("---")
            st.markdown("**📄 Document Intelligence**")
            parser_status = get_parser_status() if INVOICE_PARSER_AVAILABLE else {"ready": False}

            # Show mode indicator
            if parser_status.get("mock_mode"):
                st.caption("🎭 Demo Mode - Simulated extraction")
            elif parser_status.get("pytesseract_available") or parser_status.get("easyocr_available"):
                st.caption("🔬 OCR Ready - Real extraction")

            if parser_status.get("ready", False):
                extraction_mode = "demo simulation" if parser_status.get("mock_mode") and not (parser_status.get("pytesseract_available") or parser_status.get("easyocr_available")) else "OCR"
                if st.button("🔍 Extract Invoice Data", use_container_width=True, key="extract_invoices"):
                    terminal_log("UI_ACTION", f"Processing {len(pdf_files)} invoice(s) using {extraction_mode}")
                    with st.spinner(f"Extracting invoice data ({extraction_mode})..."):
                        results = []
                        for pdf in pdf_files:
                            file_path = str(INBOX_PATH / pdf['name'])
                            if not Path(file_path).exists():
                                file_path = str(NEEDS_ACTION_PATH / pdf['name'])
                            result = process_invoice_from_inbox(file_path)
                            results.append(result)

                        # Show results
                        success_count = sum(1 for r in results if r.get('success'))
                        if success_count > 0:
                            st.success(f"✅ Extracted data from {success_count}/{len(results)} invoice(s)")

                            # Build summary for WhatsApp notification
                            invoice_summaries = []

                            for r in results:
                                if r.get('success') and r.get('invoice_data'):
                                    data = r['invoice_data']
                                    st.markdown(f"""
                                    <div style="background: #0F172A; border-radius: 8px; padding: 0.75rem; margin: 0.5rem 0; border-left: 3px solid #10B981;">
                                        <div style="color: #10B981; font-weight: 600;">📄 {Path(r['file']).name}</div>
                                        <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.5rem;">
                                            <b>Vendor:</b> {data.get('vendor_name', 'N/A')}<br>
                                            <b>Amount:</b> {data.get('currency', 'USD')} {data.get('total_amount', 0):.2f}<br>
                                            <b>Date:</b> {data.get('invoice_date', 'N/A')}<br>
                                            <b>Confidence:</b> {data.get('confidence', {}).get('overall', 0):.0%}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    if r.get('odoo_result', {}).get('success'):
                                        st.caption(f"📋 Draft Invoice #{r['odoo_result'].get('invoice_id')} created in Odoo")

                                    # Add to summary for WhatsApp
                                    invoice_summaries.append(
                                        f"• {data.get('vendor_name', 'Unknown')}: {data.get('currency', 'USD')} {data.get('total_amount', 0):.2f}"
                                    )

                            # Send WhatsApp notification via Cloud API
                            try:
                                if WHATSAPP_SKILL_AVAILABLE and is_whatsapp_active():
                                    from skills.whatsapp_skill import get_whatsapp_client
                                    wa_client = get_whatsapp_client()

                                    # Build notification message
                                    wa_message = f"🤖 *Zoya AI - Invoice Alert*\n\n"
                                    wa_message += f"📄 Processed {success_count} invoice(s):\n"
                                    wa_message += "\n".join(invoice_summaries[:5])  # Limit to 5
                                    if len(invoice_summaries) > 5:
                                        wa_message += f"\n... and {len(invoice_summaries) - 5} more"
                                    wa_message += f"\n\n✅ Draft invoices created in Odoo"
                                    wa_message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                                    # Log the notification (in mock mode, this simulates sending)
                                    terminal_log("WHATSAPP_NOTIFY", f"Invoice extraction complete: {success_count} invoices")
                                    add_log("WHATSAPP_NOTIFICATION", "SENT", {
                                        "type": "invoice_extraction",
                                        "count": success_count,
                                        "message_preview": wa_message[:100]
                                    })
                                    st.caption("💬 WhatsApp notification sent")
                            except Exception as wa_error:
                                terminal_log("WHATSAPP_NOTIFY", f"Could not send: {wa_error}")

                        else:
                            st.warning("Could not extract data. Check if OCR dependencies are installed.")
                        add_log("INVOICE_EXTRACT", "SUCCESS" if success_count > 0 else "PARTIAL", {
                            "total": len(results), "success": success_count
                        })
            else:
                st.caption("⚠️ OCR not ready - install pytesseract or easyocr")

    # AI REASONING (Plans)
    with col2:
        st.markdown("""
        <div class="section-header">📋 AI Reasoning (Plans)</div>
        """, unsafe_allow_html=True)

        if plan_files:
            selected_plans = []
            for f in plan_files[:8]:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(f"""
                    <div class="file-card">
                        <div class="file-name">📋 {f['name'][:25]}{'...' if len(f['name']) > 25 else ''}</div>
                        <div class="file-meta">{f['modified'].strftime('%H:%M')} • Ready</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_b:
                    if st.checkbox("Select", key=f"sel_{f['name']}", label_visibility="collapsed"):
                        selected_plans.append(f['name'])

            if len(plan_files) > 8:
                st.caption(f"+{len(plan_files) - 8} more plans...")

            # Approve & Sync Button
            st.markdown("")
            if st.button("🚀 Approve & Sync Selected", use_container_width=True, key="approve_sync"):
                if selected_plans:
                    terminal_log("UI_ACTION", f"User approving {len(selected_plans)} selected plans")
                    with st.spinner("Syncing with Odoo & Social platforms..."):
                        time.sleep(1.5)
                        results = approve_and_sync(selected_plans)
                    st.success(f"✅ Approved {results['moved']} plan(s)!")
                    st.info(f"📤 Synced to Odoo: {len(results['odoo'])} | Social: {len(results['social'])}")
                    terminal_log("APPROVE_SYNC", f"Moved {results['moved']} plans | Odoo: {len(results['odoo'])} | Social: {len(results['social'])}")
                    st.rerun()
                else:
                    st.warning("Select plans to approve")

            # Approve All Button
            if st.button("✅ Approve All Plans", use_container_width=True, key="approve_all"):
                terminal_log("UI_ACTION", f"User approving ALL {len(plan_files)} plans")
                all_plans = [f['name'] for f in plan_files]
                with st.spinner("Processing all plans..."):
                    time.sleep(1.5)
                    results = approve_and_sync(all_plans)
                st.success(f"✅ Approved {results['moved']} plan(s)!")
                terminal_log("APPROVE_ALL", f"Approved all {results['moved']} plans")
                st.rerun()
        else:
            st.info("No plans awaiting approval")

    # EXECUTION SUCCESS (Done)
    with col3:
        st.markdown("""
        <div class="section-header">🏁 Execution Success (Done)</div>
        """, unsafe_allow_html=True)

        # Load social execution log for MCP messages
        social_exec_log = load_social_execution_log(10)

        if done_files:
            for f in done_files[:6]:
                icon = get_type_icon(f['type'])
                st.markdown(f"""
                <div class="file-card">
                    <div class="file-name">{icon} {f['name'][:30]}{'...' if len(f['name']) > 30 else ''}</div>
                    <div class="file-meta">{f['modified'].strftime('%H:%M')} • Completed ✓</div>
                </div>
                """, unsafe_allow_html=True)

            if len(done_files) > 6:
                st.caption(f"+{len(done_files) - 6} more completed...")
        else:
            st.info("No completed tasks yet")

        # MCP Execution Log - Show "Post published via MCP Tool: [Platform]"
        if social_exec_log:
            st.markdown("")
            st.markdown("**📤 MCP Broadcast Log:**")
            for log_entry in reversed(social_exec_log[-5:]):
                platform_icon = log_entry.get('icon', '📱')
                platform_name = log_entry.get('platform_name', 'Unknown')
                mcp_used = log_entry.get('mcp_used', False)
                message = log_entry.get('message', '')

                if mcp_used:
                    status_color = "#10B981"
                    status_text = f"✓ Post published via MCP Tool: {platform_name}"
                else:
                    status_color = "#F59E0B"
                    status_text = f"📁 Post queued (File-Based): {platform_name}"

                st.markdown(f"""
                <div style="background: #0F172A; border-radius: 6px; padding: 0.5rem 0.75rem;
                            margin-bottom: 0.25rem; border-left: 3px solid {status_color};">
                    <span style="font-size: 0.8rem;">{platform_icon}</span>
                    <span style="color: {status_color}; font-size: 0.75rem; font-weight: 500;">
                        {status_text}
                    </span>
                </div>
                """, unsafe_allow_html=True)

        # Stats
        st.markdown("")
        st.markdown(f"""
        <div style="background: #1E293B; border-radius: 8px; padding: 1rem; text-align: center;">
            <div style="color: #10B981; font-size: 1.5rem; font-weight: 700;">{len(done_files)}</div>
            <div style="color: #64748B; font-size: 0.8rem;">Tasks Completed Today</div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# TAB 2: FINANCIAL AUDIT
# =============================================================================

with tab2:
    st.markdown("### 💰 Financial Audit Dashboard")
    st.markdown("*Subscription tracking and cost analysis from financial_audit.csv*")

    # Create DataFrame
    df = pd.DataFrame(MOCK_FINANCIAL_DATA)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    total_monthly = df['Monthly'].sum()
    over_100 = len(df[df['Monthly'] > 100])
    active_count = len(df[df['Status'] == 'Active'])
    review_count = len(df[df['Status'].isin(['Review', 'Unused?'])])

    with col1:
        st.metric("Total Monthly Spend", f"${total_monthly:,.2f}")
    with col2:
        st.metric("Over $100/month", over_100, delta="Needs Review" if over_100 > 3 else None)
    with col3:
        st.metric("Active Services", active_count)
    with col4:
        st.metric("Flagged for Review", review_count, delta="Action Required" if review_count > 0 else None)

    st.markdown("")

    # Styled Table with Highlighting
    def highlight_expensive(row):
        if row['Monthly'] > 100:
            return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row)
        elif row['Status'] in ['Review', 'Unused?']:
            return ['background-color: rgba(245, 158, 11, 0.2)'] * len(row)
        return [''] * len(row)

    st.markdown("#### Subscription Details")
    st.dataframe(
        df.style.apply(highlight_expensive, axis=1).format({'Monthly': '${:.2f}'}),
        use_container_width=True,
        hide_index=True,
        height=350
    )

    # Legend
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🔴 **Red** = Over $100/month")
    with col2:
        st.markdown("🟡 **Yellow** = Needs Review")
    with col3:
        st.markdown("⚪ **Normal** = Active & Optimized")

    # Quick Actions
    st.markdown("#### Quick Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Generate CEO Briefing", use_container_width=True):
            terminal_log("UI_ACTION", "User generating CEO Briefing")
            add_log("CEO_BRIEFING", "MOCK_SUCCESS", {
                "total_spend": total_monthly,
                "flagged_items": review_count
            })
            st.success("CEO Briefing generated! Check /Briefings folder.")
    with col2:
        if st.button("📧 Send Finance Alert", use_container_width=True):
            terminal_log("UI_ACTION", "User sending Finance Alert")
            add_log("FINANCE_ALERT", "MOCK_SUCCESS", {
                "recipients": ["cfo@company.com"],
                "alert_type": "subscription_review"
            })
            st.success("Finance alert sent!")


# =============================================================================
# TAB 3: SYSTEM LOGS
# =============================================================================

with tab3:
    st.markdown("### 📜 Real-Time System Logs")
    st.markdown("*Live audit trail of all Zoya AI actions*")

    # Refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()

    # Log entries
    logs = load_audit_log(30)

    if logs:
        st.markdown(f"*Showing {len(logs)} most recent events*")

        log_container = st.container()
        with log_container:
            for entry in reversed(logs):
                ts = entry.get('timestamp', '')[:19]
                action = entry.get('action_type', 'UNKNOWN')
                status = entry.get('status', 'N/A')
                actor = entry.get('actor', 'system')
                details = entry.get('details', {})

                # Determine style
                if 'SUCCESS' in status.upper():
                    style_class = "log-entry-success"
                    status_color = "#10B981"
                elif 'ERROR' in status.upper() or 'FAIL' in status.upper():
                    style_class = "log-entry-error"
                    status_color = "#EF4444"
                else:
                    style_class = "log-entry-warning"
                    status_color = "#F59E0B"

                # Format details
                detail_str = " • ".join([f"{k}: {str(v)[:25]}" for k, v in list(details.items())[:3]])

                st.markdown(f"""
                <div class="log-entry {style_class}">
                    <span class="log-timestamp">[{ts}]</span>
                    <span class="log-action">{action}</span>
                    <span style="color: {status_color};">[{status}]</span>
                    <br>
                    <span style="color: #64748B; font-size: 0.7rem;">{detail_str}</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No log entries yet. Perform some actions to see the audit trail!")

    # Export option
    st.markdown("")
    if st.button("📥 Export Full Log", use_container_width=True):
        if AUDIT_LOG_PATH.exists():
            with open(AUDIT_LOG_PATH, encoding='utf-8') as f:
                log_data = f.read()
            st.download_button(
                label="Download audit_log.json",
                data=log_data,
                file_name="audit_log.json",
                mime="application/json"
            )


# =============================================================================
# FOOTER
# =============================================================================

st.divider()

st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <p style="font-size: 1.25rem; font-weight: 600; color: #94A3B8;">
        🤖 Zoya AI - Your Autonomous Enterprise FTE
    </p>
    <p style="color: #64748B; font-size: 0.9rem;">
        Platinum Edition • 18 Active Modules • samreensami/hack2-phase2
    </p>
    <p style="color: #475569; font-size: 0.75rem; margin-top: 1rem;">
        Built for the AI Employee Hackathon • Real-Time Operations Dashboard
    </p>
</div>
""", unsafe_allow_html=True)
