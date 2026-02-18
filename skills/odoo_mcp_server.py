"""
Odoo MCP Server - Model Context Protocol server for Odoo integration.

This module implements an MCP-style server that provides accounting capabilities
to the AI Employee through Odoo Community Edition. It follows the HITL pattern
where draft documents are created and require human approval before posting.

Features:
    - Partner (contact) management
    - Draft invoice creation (requires approval to post)
    - Draft payment creation (requires approval to post)
    - Accounting queries and summaries
    - CEO briefing data generation
    - Integration with Obsidian vault workflow
"""

import os
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

from skills.odoo_client import (
    OdooClient, OdooError, OdooAuthError,
    OdooPartner, OdooInvoice, OdooPayment
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class OdooConfig:
    """Odoo connection configuration."""
    url: str
    database: str
    username: str
    password: str
    timeout: int = 30

    @classmethod
    def from_env(cls) -> 'OdooConfig':
        """Load configuration from environment variables."""
        return cls(
            url=os.getenv('ODOO_URL', 'http://localhost:8069'),
            database=os.getenv('ODOO_DATABASE', 'odoo'),
            username=os.getenv('ODOO_USERNAME', 'admin'),
            password=os.getenv('ODOO_PASSWORD', 'admin'),
            timeout=int(os.getenv('ODOO_TIMEOUT', '30'))
        )

    @classmethod
    def from_file(cls, filepath: str) -> 'OdooConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)


class OdooMCPServer:
    """
    MCP-style server for Odoo accounting operations.

    All write operations create drafts that require HITL approval.
    Approval workflow uses the Obsidian vault folder structure:
    - Draft created -> Action file in /Pending_Approval
    - Human moves to /Approved
    - Orchestrator detects and posts the document
    """

    def __init__(
        self,
        config: OdooConfig = None,
        vault_path: str = "obsidian_vault",
        approval_threshold: float = 100.0
    ):
        """
        Initialize Odoo MCP Server.

        Args:
            config: Odoo connection configuration
            vault_path: Path to Obsidian vault
            approval_threshold: Amount threshold requiring approval (default: $100)
        """
        self.config = config or OdooConfig.from_env()
        self.vault_path = Path(vault_path)
        self.approval_threshold = approval_threshold
        self.client: Optional[OdooClient] = None
        self.connected = False

        # Ensure directories exist
        self.pending_approval_path = self.vault_path / "Pending_Approval" / "odoo"
        self.approved_path = self.vault_path / "Approved" / "odoo"
        self.done_path = self.vault_path / "Done"

        for path in [self.pending_approval_path, self.approved_path, self.done_path]:
            path.mkdir(parents=True, exist_ok=True)

        logger.info(f"OdooMCPServer initialized. Vault: {self.vault_path}")

    def connect(self) -> bool:
        """
        Connect to Odoo server.

        Returns:
            True if connection successful
        """
        try:
            self.client = OdooClient(
                url=self.config.url,
                database=self.config.database,
                username=self.config.username,
                password=self.config.password,
                timeout=self.config.timeout
            )

            result = self.client.test_connection()

            if result.get('connected'):
                self.connected = True
                logger.info(f"Connected to Odoo: {result.get('company')} as {result.get('user_name')}")
                return True
            else:
                logger.error(f"Connection failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {e}")
            return False

    def disconnect(self):
        """Disconnect from Odoo."""
        self.client = None
        self.connected = False
        logger.info("Disconnected from Odoo")

    def _ensure_connected(self):
        """Ensure connection is established."""
        if not self.connected:
            if not self.connect():
                raise OdooError("Not connected to Odoo")

    def _create_approval_file(
        self,
        action_type: str,
        odoo_id: int,
        details: Dict,
        amount: float = 0
    ) -> Path:
        """
        Create an approval request file in Pending_Approval folder.

        Args:
            action_type: Type of action (invoice_post, payment_post, etc.)
            odoo_id: Odoo document ID
            details: Document details dictionary
            amount: Amount for threshold checking

        Returns:
            Path to created approval file
        """
        timestamp = datetime.now()
        filename = f"ODOO_{action_type}_{odoo_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.pending_approval_path / filename

        requires_approval = amount >= self.approval_threshold

        content = f"""---
type: odoo_approval
action: {action_type}
odoo_id: {odoo_id}
amount: {amount}
requires_approval: {requires_approval}
created_at: {timestamp.isoformat()}
status: pending
---

# Odoo Action: {action_type.replace('_', ' ').title()}

## Document Details
- **Odoo ID:** {odoo_id}
- **Amount:** ${amount:,.2f}
- **Requires Approval:** {'Yes' if requires_approval else 'No (auto-approved)'}
- **Created:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Details
```json
{json.dumps(details, indent=2, default=str)}
```

## Action Required
{'Move this file to `/Approved/odoo/` to post the document in Odoo.' if requires_approval else 'This action is below the approval threshold and can be auto-approved.'}

## To Approve
Move this file to `/Approved/odoo/` folder.

## To Reject
Move this file to `/Rejected/` folder or delete it.

---
*Generated by Odoo MCP Server*
*AI Employee Zoya - Accounting Integration*
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Created approval file: {filename}")
        return filepath

    # ==================== Partner Operations ====================

    def search_customers(self, query: str = None, limit: int = 50) -> List[Dict]:
        """
        Search for customers.

        Args:
            query: Search query (name/email)
            limit: Maximum results

        Returns:
            List of customer dictionaries
        """
        self._ensure_connected()

        domain = [['customer_rank', '>', 0]]
        if query:
            domain.append('|')
            domain.append(['name', 'ilike', query])
            domain.append(['email', 'ilike', query])

        partners = self.client.search_partners(domain, limit=limit)
        return [asdict(p) for p in partners]

    def search_vendors(self, query: str = None, limit: int = 50) -> List[Dict]:
        """Search for vendors."""
        self._ensure_connected()

        domain = [['supplier_rank', '>', 0]]
        if query:
            domain.append('|')
            domain.append(['name', 'ilike', query])
            domain.append(['email', 'ilike', query])

        partners = self.client.search_partners(domain, limit=limit)
        return [asdict(p) for p in partners]

    def create_customer(
        self,
        name: str,
        email: str = '',
        phone: str = '',
        **kwargs
    ) -> Dict:
        """
        Create a new customer.

        Args:
            name: Customer name
            email: Email address
            phone: Phone number

        Returns:
            Created customer info
        """
        self._ensure_connected()

        partner_id = self.client.create_partner(
            name=name,
            email=email,
            phone=phone,
            is_customer=True,
            **kwargs
        )

        return {
            'success': True,
            'partner_id': partner_id,
            'message': f"Created customer: {name}"
        }

    # ==================== Invoice Operations ====================

    def create_draft_invoice(
        self,
        customer_id: int,
        lines: List[Dict],
        due_date: str = None,
        notes: str = ''
    ) -> Dict:
        """
        Create a draft customer invoice.

        The invoice is created in DRAFT state and requires approval to post.

        Args:
            customer_id: Customer partner ID
            lines: Invoice lines [{name, quantity, price_unit}]
            due_date: Payment due date (YYYY-MM-DD)
            notes: Internal notes

        Returns:
            Result with invoice ID and approval file path
        """
        self._ensure_connected()

        # Calculate total
        total_amount = sum(
            line.get('quantity', 1) * line.get('price_unit', 0)
            for line in lines
        )

        # Create draft invoice
        invoice_id = self.client.create_draft_invoice(
            partner_id=customer_id,
            lines=lines,
            move_type='out_invoice',
            invoice_date_due=due_date
        )

        # Get invoice details
        invoice = self.client.get_invoice(invoice_id)
        customer = self.client.get_partner(customer_id)

        # Create approval file
        details = {
            'invoice_id': invoice_id,
            'customer_name': customer.name if customer else 'Unknown',
            'customer_email': customer.email if customer else '',
            'lines': lines,
            'total_amount': total_amount,
            'due_date': due_date,
            'notes': notes
        }

        approval_file = self._create_approval_file(
            action_type='invoice_post',
            odoo_id=invoice_id,
            details=details,
            amount=total_amount
        )

        return {
            'success': True,
            'invoice_id': invoice_id,
            'state': 'draft',
            'amount_total': total_amount,
            'approval_file': str(approval_file),
            'message': f"Draft invoice created. Move approval file to /Approved/odoo/ to post."
        }

    def create_draft_vendor_bill(
        self,
        vendor_id: int,
        lines: List[Dict],
        due_date: str = None,
        notes: str = ''
    ) -> Dict:
        """
        Create a draft vendor bill.

        Args:
            vendor_id: Vendor partner ID
            lines: Bill lines [{name, quantity, price_unit}]
            due_date: Payment due date
            notes: Internal notes

        Returns:
            Result with bill ID and approval file path
        """
        self._ensure_connected()

        total_amount = sum(
            line.get('quantity', 1) * line.get('price_unit', 0)
            for line in lines
        )

        bill_id = self.client.create_draft_invoice(
            partner_id=vendor_id,
            lines=lines,
            move_type='in_invoice',
            invoice_date_due=due_date
        )

        vendor = self.client.get_partner(vendor_id)

        details = {
            'bill_id': bill_id,
            'vendor_name': vendor.name if vendor else 'Unknown',
            'lines': lines,
            'total_amount': total_amount,
            'due_date': due_date,
            'notes': notes
        }

        approval_file = self._create_approval_file(
            action_type='bill_post',
            odoo_id=bill_id,
            details=details,
            amount=total_amount
        )

        return {
            'success': True,
            'bill_id': bill_id,
            'state': 'draft',
            'amount_total': total_amount,
            'approval_file': str(approval_file),
            'message': f"Draft vendor bill created. Requires approval to post."
        }

    def post_invoice(self, invoice_id: int) -> Dict:
        """
        Post an invoice (called after approval).

        Args:
            invoice_id: Invoice ID to post

        Returns:
            Result dictionary
        """
        self._ensure_connected()

        try:
            self.client.post_invoice(invoice_id)
            invoice = self.client.get_invoice(invoice_id)

            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_name': invoice.name if invoice else '',
                'state': 'posted',
                'message': f"Invoice {invoice.name if invoice else invoice_id} posted successfully"
            }
        except Exception as e:
            return {
                'success': False,
                'invoice_id': invoice_id,
                'error': str(e)
            }

    # ==================== Payment Operations ====================

    def create_draft_payment(
        self,
        partner_id: int,
        amount: float,
        payment_type: str = 'inbound',
        memo: str = ''
    ) -> Dict:
        """
        Create a draft payment.

        Args:
            partner_id: Partner ID
            amount: Payment amount
            payment_type: 'inbound' (receive) or 'outbound' (pay)
            memo: Payment reference/memo

        Returns:
            Result with payment ID and approval file path
        """
        self._ensure_connected()

        payment_id = self.client.create_draft_payment(
            partner_id=partner_id,
            amount=amount,
            payment_type=payment_type,
            memo=memo
        )

        partner = self.client.get_partner(partner_id)

        details = {
            'payment_id': payment_id,
            'partner_name': partner.name if partner else 'Unknown',
            'amount': amount,
            'payment_type': payment_type,
            'direction': 'Receive' if payment_type == 'inbound' else 'Pay',
            'memo': memo
        }

        approval_file = self._create_approval_file(
            action_type='payment_post',
            odoo_id=payment_id,
            details=details,
            amount=amount
        )

        return {
            'success': True,
            'payment_id': payment_id,
            'state': 'draft',
            'amount': amount,
            'approval_file': str(approval_file),
            'message': f"Draft payment created. Requires approval to post."
        }

    def post_payment(self, payment_id: int) -> Dict:
        """
        Post a payment (called after approval).

        Args:
            payment_id: Payment ID to post

        Returns:
            Result dictionary
        """
        self._ensure_connected()

        try:
            self.client.post_payment(payment_id)

            return {
                'success': True,
                'payment_id': payment_id,
                'state': 'posted',
                'message': f"Payment {payment_id} posted successfully"
            }
        except Exception as e:
            return {
                'success': False,
                'payment_id': payment_id,
                'error': str(e)
            }

    # ==================== Reporting ====================

    def get_financial_summary(
        self,
        date_from: str = None,
        date_to: str = None
    ) -> Dict:
        """
        Get comprehensive financial summary.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Financial summary dictionary
        """
        self._ensure_connected()

        revenue = self.client.get_revenue_summary(date_from, date_to)
        expenses = self.client.get_expense_summary(date_from, date_to)
        overdue = self.client.get_overdue_invoices()

        return {
            'period': {
                'from': date_from or 'All time',
                'to': date_to or 'Present'
            },
            'revenue': revenue,
            'expenses': expenses,
            'net_income': revenue['net_revenue'] - expenses['net_expenses'],
            'overdue_invoices': {
                'count': len(overdue),
                'total_amount': sum(inv.amount_residual for inv in overdue)
            },
            'generated_at': datetime.now().isoformat()
        }

    def get_unpaid_invoices(self, customer_id: int = None) -> List[Dict]:
        """Get all unpaid invoices."""
        self._ensure_connected()
        invoices = self.client.get_unpaid_invoices(customer_id)
        return [asdict(inv) for inv in invoices]

    def get_overdue_invoices(self) -> List[Dict]:
        """Get all overdue invoices."""
        self._ensure_connected()
        invoices = self.client.get_overdue_invoices()
        return [asdict(inv) for inv in invoices]

    def generate_ceo_briefing_data(self) -> Dict:
        """
        Generate data for CEO briefing from Odoo.

        Returns:
            Dictionary with all data needed for CEO briefing
        """
        self._ensure_connected()

        # Get current month data
        today = date.today()
        first_of_month = today.replace(day=1).isoformat()
        today_str = today.isoformat()

        # Get summaries
        mtd_summary = self.get_financial_summary(first_of_month, today_str)
        overdue = self.get_overdue_invoices()

        # Get draft documents awaiting approval
        draft_invoices = self.client.search_invoices(
            [['state', '=', 'draft'], ['move_type', '=', 'out_invoice']]
        )
        draft_payments = self.client.search_payments(
            [['state', '=', 'draft']]
        )

        return {
            'generated_at': datetime.now().isoformat(),
            'mtd_summary': mtd_summary,
            'overdue_invoices': {
                'count': len(overdue),
                'items': overdue[:10],  # Top 10
                'total_amount': sum(inv['amount_residual'] for inv in overdue)
            },
            'pending_approval': {
                'draft_invoices': len(draft_invoices),
                'draft_invoices_amount': sum(inv.amount_total for inv in draft_invoices),
                'draft_payments': len(draft_payments)
            },
            'key_metrics': {
                'revenue_mtd': mtd_summary['revenue']['net_revenue'],
                'expenses_mtd': mtd_summary['expenses']['net_expenses'],
                'net_income_mtd': mtd_summary['net_income'],
                'outstanding_ar': mtd_summary['revenue']['total_outstanding'],
                'outstanding_ap': mtd_summary['expenses']['total_outstanding']
            }
        }

    # ==================== Approval Processing ====================

    def process_approved_actions(self) -> List[Dict]:
        """
        Process all approved Odoo actions.

        Scans the /Approved/odoo/ folder and posts approved documents.

        Returns:
            List of processing results
        """
        results = []

        for filepath in self.approved_path.glob("ODOO_*.md"):
            try:
                content = filepath.read_text()

                # Parse action type and ID from filename
                # Format: ODOO_<action>_<id>_<timestamp>.md
                parts = filepath.stem.split('_')
                if len(parts) >= 3:
                    action = parts[1]
                    odoo_id = int(parts[2])

                    if action == 'invoice' and 'post' in filepath.stem:
                        result = self.post_invoice(odoo_id)
                    elif action == 'bill' and 'post' in filepath.stem:
                        result = self.post_invoice(odoo_id)  # Same method for bills
                    elif action == 'payment' and 'post' in filepath.stem:
                        result = self.post_payment(odoo_id)
                    else:
                        result = {'success': False, 'error': f'Unknown action: {action}'}

                    results.append({
                        'file': filepath.name,
                        'action': action,
                        'odoo_id': odoo_id,
                        'result': result
                    })

                    # Move to Done folder
                    if result.get('success'):
                        done_file = self.done_path / filepath.name
                        filepath.rename(done_file)
                        logger.info(f"Processed and moved to Done: {filepath.name}")

            except Exception as e:
                logger.error(f"Error processing {filepath.name}: {e}")
                results.append({
                    'file': filepath.name,
                    'error': str(e)
                })

        return results

    def get_status(self) -> Dict:
        """Get MCP server status."""
        pending_count = len(list(self.pending_approval_path.glob("ODOO_*.md")))
        approved_count = len(list(self.approved_path.glob("ODOO_*.md")))

        return {
            'connected': self.connected,
            'odoo_url': self.config.url,
            'database': self.config.database,
            'approval_threshold': self.approval_threshold,
            'pending_approval_count': pending_count,
            'approved_awaiting_processing': approved_count
        }


def main():
    """Test the Odoo MCP Server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    server = OdooMCPServer()

    print("Odoo MCP Server - Test Mode")
    print("=" * 40)

    if server.connect():
        print("\nConnection successful!")
        print(f"Status: {json.dumps(server.get_status(), indent=2)}")

        print("\nGenerating financial summary...")
        summary = server.get_financial_summary()
        print(json.dumps(summary, indent=2))
    else:
        print("Connection failed. Check your Odoo configuration.")


if __name__ == "__main__":
    main()
