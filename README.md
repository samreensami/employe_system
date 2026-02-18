# AI Employee - Zoya

An autonomous AI employee designed to manage digital operations and assist with business tasks.

## Overview

Zoya is a Digital Operations Manager that monitors tasks, executes skills, and maintains organized workflows using the Obsidian vault system. It implements the **Platinum Tier** requirements from the AI Employee Hackathon specification.

## Tier Status: PLATINUM

| Component | Status |
|-----------|--------|
| Obsidian Vault | Implemented |
| Filesystem Watcher | Implemented |
| Gmail Watcher | Implemented |
| WhatsApp Watcher | Implemented |
| Odoo Integration | Implemented |
| Task Processor | Implemented |
| Execution Engine | Implemented |
| Human-in-the-Loop | Implemented |
| Financial Auditor | Implemented |
| CEO Briefing | Implemented |
| Audit Logging | Implemented |
| Ralph Wiggum Loop | Implemented |
| Error Handler | Implemented |

## Structure

```
AI_Employee/
├── obsidian_vault/           # Obsidian knowledge base
│   ├── inbox/                # New tasks drop here
│   ├── needs_action/         # Tasks requiring processing
│   ├── Plans/                # Generated execution plans
│   ├── Approved/             # Human-approved plans
│   │   └── odoo/             # Odoo-specific approvals
│   ├── Pending_Approval/     # Awaiting human approval
│   │   └── odoo/             # Odoo draft documents
│   ├── Done/                 # Completed tasks
│   └── Briefings/            # CEO briefings
├── skills/                   # Python skill modules (17 modules)
│   ├── gmail_watcher.py      # Gmail monitoring
│   ├── whatsapp_watcher.py   # WhatsApp monitoring
│   ├── odoo_client.py        # Odoo JSON-RPC client
│   ├── odoo_mcp_server.py    # Odoo MCP server
│   ├── odoo_watcher.py       # Odoo approval watcher
│   ├── filesystem_watcher.py # File monitoring
│   ├── task_processor.py     # Plan generation
│   ├── execution_engine.py   # Plan execution
│   ├── financial_auditor.py  # Financial analysis
│   ├── audit_logger.py       # Action logging
│   ├── persistence_loop.py   # Ralph Wiggum Loop
│   └── ...                   # Other skills
├── credentials/              # OAuth/session credentials (gitignored)
├── logs/                     # System logs
└── workspace/                # Working files
```

## Features

- **Gmail Monitoring**: Automatically detects and processes important emails
- **WhatsApp Monitoring**: Monitors WhatsApp Web for business messages
- **Odoo Integration**: Full ERP integration for accounting operations
- **Filesystem Monitoring**: Watches for new task files in inbox
- **Automatic Plan Generation**: Creates execution plans from tasks
- **Human-in-the-Loop**: Sensitive actions require approval
- **Financial Auditing**: Analyzes transactions and generates CEO briefings
- **Comprehensive Logging**: All actions are audited

## Quick Start

### 1. Install Dependencies

```bash
# Core dependencies
pip install watchdog psutil pandas

# Web UI Dashboard
pip install streamlit

# Gmail integration
pip install google-auth google-auth-oauthlib google-api-python-client

# WhatsApp integration
pip install playwright
playwright install chromium

# Odoo integration (no additional packages needed - uses stdlib)
```

### 2. Setup Integrations

**Gmail (optional):**
```bash
python setup_gmail.py
```

**WhatsApp (optional):**
```bash
python setup_whatsapp.py
```

**Odoo (optional but recommended for Platinum):**
```bash
python setup_odoo.py
```

### 3. Start the AI Employee

**Windows:**
```batch
deploy_local.bat
```

**Mac/Linux:**
```bash
python start_agent.py
```

### 4. Launch the Web UI Dashboard

```bash
streamlit run ui_dashboard.py
```

The Command Center dashboard provides:
- Real-time system status and watcher monitoring
- Task workflow visualization (Inbox → Plans → Approved → Done)
- Approval gate with one-click approvals
- Live audit log streaming
- Odoo insights and subscription alerts
- Manual scan trigger button

## Web UI Dashboard

The Command Center (`ui_dashboard.py`) provides a professional Streamlit-based interface.

### Features

| Component | Description |
|-----------|-------------|
| **Sidebar Status** | Shows Tier (Platinum), Mock Mode, Active Watchers |
| **Task Monitor** | Three columns: Pending, Planning, Completed |
| **Approval Gate** | View and approve files with one click |
| **Live Logs** | Streams last 10 entries from audit_log.json |
| **Odoo Insights** | Draft invoices and subscription alerts |
| **Action Button** | Trigger manual scan |

### Running the Dashboard

```bash
# Install Streamlit
pip install streamlit pandas

# Launch dashboard
streamlit run ui_dashboard.py

# Access at http://localhost:8501
```

### Screenshots

The dashboard features:
- Dark theme with gradient accents
- Real-time folder monitoring
- File preview and approval buttons
- Auto-refresh capability

---

## Odoo Integration

The Odoo integration provides full ERP capabilities for accounting operations.

### Features

- **Partner Management**: Create and search customers/vendors
- **Invoice Management**: Create draft invoices (HITL approval to post)
- **Payment Management**: Create draft payments (HITL approval to post)
- **Financial Reporting**: Revenue, expenses, and cash flow summaries
- **CEO Briefing Data**: Automated financial data for briefings

### Workflow

```
AI creates draft → /Pending_Approval/odoo/ → Human moves to /Approved/odoo/ → Odoo Watcher posts → /Done/
```

### Approval Thresholds

| Amount | Approval Required |
|--------|-------------------|
| < $100 | Auto-approved (logged) |
| >= $100 | Manual approval required |

### Supported Operations

| Operation | Creates Draft | Requires Approval |
|-----------|---------------|-------------------|
| Customer Invoice | Yes | Yes (to post) |
| Vendor Bill | Yes | Yes (to post) |
| Inbound Payment | Yes | Yes (to post) |
| Outbound Payment | Yes | Yes (to post) |
| Partner Creation | No (immediate) | No |
| Queries/Reports | No | No |

## Communication Watchers

### Gmail Watcher

Monitors your inbox for new emails and creates action files.

### WhatsApp Watcher

Monitors WhatsApp Web for new business messages.

### Priority Detection

| Priority | Criteria |
|----------|----------|
| HIGH | Multiple urgent keywords, VIP sender/contact |
| MEDIUM | Single urgent keyword or business keyword |
| LOW | Regular messages |

## Human-in-the-Loop Workflow

```
Email/WhatsApp/Task → needs_action/ → Plans/ → [HUMAN APPROVAL] → Approved/ → Done/
Odoo Draft → Pending_Approval/odoo/ → [HUMAN APPROVAL] → Approved/odoo/ → Posted → Done/
```

Sensitive actions are **never** executed automatically.

### Approval Required For:

- Payments > $100
- New contact interactions
- Email/WhatsApp responses
- Posting Odoo invoices/bills
- Posting Odoo payments
- Any external API calls

## Security Disclosure

This system implements several security measures:

- **Payment Approval Threshold**: Any payment > $100 requires human approval
- **Draft-Only Odoo Operations**: Cannot post documents directly
- **Contact Interaction Control**: New contact interactions require approval
- **Audit Logging**: All actions logged with timestamps and actors
- **Error Handling**: Transient errors handled with exponential backoff
- **Read-Only Email/WhatsApp**: Watchers cannot send/modify messages
- **Credential Security**: All credentials stored locally, never transmitted

## Deployment

Optimized for 'Local-Always-On' operation:

- **Background Mode**: Runs continuously without terminal access
- **Auto-Restart**: Automatically recovers from crashes (max 10 attempts)
- **Health Monitoring**: Checks all services every 5 minutes
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM

## Logs

| Log File | Purpose |
|----------|---------|
| `logs/start_agent.log` | Main orchestrator logs |
| `logs/audit_log.json` | Action audit trail |
| `logs/health_monitor.log` | System health checks |
| `logs/gmail_processed_ids.json` | Processed email tracking |
| `logs/whatsapp_processed_ids.json` | Processed WhatsApp tracking |
| `logs/odoo_audit.json` | Odoo operation audit trail |

## Troubleshooting

### Gmail Not Starting
1. Verify credentials: `ls credentials/gmail_*`
2. Re-run setup: `python setup_gmail.py`

### WhatsApp Not Starting
1. Verify session: `ls credentials/whatsapp_session/`
2. Re-run setup: `python setup_whatsapp.py`

### Odoo Not Connecting
1. Verify Odoo is running: `curl http://localhost:8069`
2. Check credentials in `.env`
3. Re-run setup: `python setup_odoo.py`

### Health Check Shows Degraded
```bash
python -c "from skills.health_monitor import HealthMonitor; import json; print(json.dumps(HealthMonitor().run_once(), indent=2))"
```

## Platinum Tier Features

This implementation includes all Platinum Tier requirements:

1. **Multiple Watchers**: Filesystem, Gmail, WhatsApp, Odoo
2. **Cross-Domain Integration**: Personal (email/WhatsApp) + Business (Odoo ERP)
3. **Odoo Community Integration**: Full accounting via JSON-RPC API
4. **Draft-Only Operations**: HITL approval for posting documents
5. **Financial Audit from Odoo**: Real-time revenue/expense data
6. **Ralph Wiggum Loop**: Persistence loop for multi-step tasks
7. **Comprehensive Audit Logging**: JSON-based action tracking
8. **Error Recovery**: Exponential backoff with graceful degradation

## Skills Inventory (17 modules)

```
skills/
├── gmail_watcher.py      # Email monitoring
├── whatsapp_watcher.py   # WhatsApp monitoring
├── odoo_client.py        # Odoo JSON-RPC client
├── odoo_mcp_server.py    # Odoo MCP server
├── odoo_watcher.py       # Odoo approval watcher
├── filesystem_watcher.py # File monitoring
├── task_processor.py     # Plan generation
├── execution_engine.py   # Plan execution
├── financial_auditor.py  # Financial analysis
├── audit_logger.py       # Action logging
├── persistence_loop.py   # Ralph Wiggum Loop
├── health_monitor.py     # System health
├── error_handler.py      # Retry logic
├── social_manager.py     # LinkedIn posts
├── skill_manager.py      # Skill coordination
├── base_watcher.py       # Watcher interface
└── watcher.py            # Legacy watcher
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details
