"""
Odoo Client - JSON-RPC client for Odoo Community Edition integration.

This module provides a Python client for interacting with Odoo's External API
using JSON-RPC 2.0 protocol. It supports Odoo 19+ and handles authentication,
CRUD operations, and business logic for accounting integration.

Reference: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html

Features:
    - JSON-RPC 2.0 authentication
    - Partner (contact) management
    - Invoice management (draft creation)
    - Payment management (draft creation)
    - Product/service lookup
    - Account balance queries
    - Transaction history
    - MOCK MODE for demos without real Odoo instance
"""

import os
import json
import logging
import random
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


# Load .env file on module import
load_env_file()

# Configure logging
logger = logging.getLogger(__name__)


class OdooMockLogger:
    """Logs mock Odoo API calls to audit_log.json for demo purposes."""

    def __init__(self, log_path="logs/audit_log.json"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log_mock_call(self, operation: str, model: str, payload: dict, result: Any = None):
        """Log a mock Odoo API call with MOCK_SUCCESS status."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": "MOCK_ODOO_API",
            "actor": "AI_Employee_Zoya",
            "status": "MOCK_SUCCESS",
            "details": {
                "service": "Odoo",
                "operation": operation,
                "model": model,
                "payload": payload,
                "mock_result": result,
                "note": "Mock mode - no real Odoo connection"
            }
        }

        # Read existing logs
        existing_logs = []
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        existing_logs = json.loads(content)
                        if not isinstance(existing_logs, list):
                            existing_logs = [existing_logs]
            except (json.JSONDecodeError, ValueError):
                existing_logs = []

        existing_logs.append(log_entry)

        with open(self.log_path, 'w', encoding='utf-8') as f:
            json.dump(existing_logs, f, indent=2)

        return log_entry


class OdooError(Exception):
    """Base exception for Odoo API errors."""
    pass


class OdooAuthError(OdooError):
    """Authentication error."""
    pass


class OdooAPIError(OdooError):
    """API call error."""
    pass


class InvoiceState(Enum):
    """Invoice states in Odoo."""
    DRAFT = 'draft'
    POSTED = 'posted'
    CANCEL = 'cancel'


class PaymentState(Enum):
    """Payment states in Odoo."""
    DRAFT = 'draft'
    POSTED = 'posted'
    CANCEL = 'cancel'


@dataclass
class OdooPartner:
    """Represents an Odoo partner (contact/customer/vendor)."""
    id: int
    name: str
    email: str
    phone: str
    is_company: bool
    customer_rank: int
    supplier_rank: int
    street: str = ''
    city: str = ''
    country: str = ''
    vat: str = ''


@dataclass
class OdooInvoice:
    """Represents an Odoo invoice."""
    id: int
    name: str
    partner_id: int
    partner_name: str
    move_type: str  # 'out_invoice', 'in_invoice', 'out_refund', 'in_refund'
    state: str
    amount_total: float
    amount_residual: float
    invoice_date: str
    invoice_date_due: str
    currency: str
    lines: List[Dict] = None


@dataclass
class OdooPayment:
    """Represents an Odoo payment."""
    id: int
    name: str
    partner_id: int
    partner_name: str
    payment_type: str  # 'inbound' or 'outbound'
    amount: float
    state: str
    date: str
    currency: str
    memo: str = ''


class OdooClient:
    """
    JSON-RPC client for Odoo External API.

    Provides methods for:
    - Authentication
    - Partner (contact) CRUD
    - Invoice management
    - Payment management
    - Accounting queries
    """

    def __init__(
        self,
        url: str = None,
        database: str = None,
        username: str = None,
        password: str = None,
        timeout: int = 30
    ):
        """
        Initialize Odoo client.

        Args:
            url: Odoo server URL (e.g., 'http://localhost:8069')
            database: Odoo database name
            username: Odoo username (email)
            password: Odoo password or API key
            timeout: Request timeout in seconds

        If credentials are missing, the client operates in MOCK MODE,
        printing JSON payloads and logging MOCK_SUCCESS to audit trail.
        """
        # Load from environment if not provided
        self.url = (url or os.getenv('ODOO_URL', '')).rstrip('/')
        self.database = database or os.getenv('ODOO_DB') or os.getenv('ODOO_DATABASE', '')
        self.username = username or os.getenv('ODOO_USER') or os.getenv('ODOO_USERNAME', '')
        self.password = password or os.getenv('ODOO_PASSWORD', '')
        self.timeout = timeout
        self.uid: Optional[int] = None
        self._request_id = 0
        self._mock_id_counter = 1000  # For generating mock IDs

        # Initialize mock logger
        self.mock_logger = OdooMockLogger()

        # Determine if mock mode should be enabled
        self.mock_mode = self._should_enable_mock_mode()

        if self.mock_mode:
            logger.info("OdooClient initialized in MOCK MODE - no real Odoo connection")
            print("\n" + "=" * 60)
            print("[MOCK MODE] Odoo Client")
            print("=" * 60)
            print("Odoo credentials not configured or MOCK_MODE=true")
            print("All Odoo operations will be simulated and logged")
            print("=" * 60 + "\n")
        else:
            logger.info(f"OdooClient initialized for {self.url}, database: {self.database}")

    def _should_enable_mock_mode(self) -> bool:
        """Determine if mock mode should be enabled based on credentials."""
        # Explicit mock mode from environment
        if os.getenv('MOCK_MODE', 'false').lower() == 'true':
            return True

        # Missing or placeholder credentials
        if not self.url or self.url == 'http://localhost:8069':
            # Check if Odoo is actually running (quick test)
            try:
                from urllib.request import urlopen
                urlopen(f"{self.url}/web/database/selector", timeout=2)
                return False  # Odoo is running
            except:
                return True  # Can't connect, use mock mode

        if not self.password or self.password == 'your_odoo_password_here':
            return True

        if not self.database or self.database == 'odoo':
            return True

        return False

    def _get_next_mock_id(self) -> int:
        """Generate a mock ID for simulated records."""
        self._mock_id_counter += 1
        return self._mock_id_counter

    def _json_rpc(self, endpoint: str, method: str, params: Dict) -> Any:
        """
        Make a JSON-RPC 2.0 call.

        In MOCK MODE: Prints payload and returns simulated result.

        Args:
            endpoint: API endpoint (e.g., '/jsonrpc')
            method: RPC method name
            params: Method parameters

        Returns:
            Result from the API call (or mock result)

        Raises:
            OdooAPIError: If the API returns an error (not in mock mode)
        """
        self._request_id += 1

        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': self._request_id
        }

        # MOCK MODE: Print payload and return simulated result
        if self.mock_mode:
            return self._handle_mock_request(endpoint, method, params, payload)

        data = json.dumps(payload).encode('utf-8')
        url = f"{self.url}{endpoint}"

        try:
            request = Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))

            if 'error' in result:
                error = result['error']
                error_msg = error.get('data', {}).get('message', str(error))
                raise OdooAPIError(f"Odoo API error: {error_msg}")

            return result.get('result')

        except HTTPError as e:
            raise OdooAPIError(f"HTTP error {e.code}: {e.reason}")
        except URLError as e:
            raise OdooAPIError(f"Connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise OdooAPIError(f"Invalid JSON response: {e}")

    def _handle_mock_request(self, endpoint: str, method: str, params: Dict, payload: Dict) -> Any:
        """Handle a mock Odoo API request."""
        print("\n" + "-" * 60)
        print(f"[MOCK] Odoo JSON-RPC Call")
        print("-" * 60)
        print(f"Endpoint: {self.url}{endpoint}")
        print(f"Method: {method}")
        print("\nJSON Payload:")
        print(json.dumps(payload, indent=2, default=str))

        # Generate mock result based on the operation
        mock_result = self._generate_mock_result(params)

        print(f"\nMock Result: {mock_result}")
        print("-" * 60)
        print("[MOCK_SUCCESS] Operation simulated successfully")
        print("-" * 60 + "\n")

        # Log to audit trail
        service = params.get('service', 'object')
        model = 'unknown'
        if service == 'object' and 'args' in params and len(params['args']) >= 4:
            model = params['args'][3]  # Model name is typically the 4th arg

        self.mock_logger.log_mock_call(
            operation=method,
            model=model,
            payload=payload,
            result=mock_result
        )

        return mock_result

    def _generate_mock_result(self, params: Dict) -> Any:
        """Generate a mock result based on the operation type."""
        service = params.get('service', '')
        method_name = params.get('method', '')
        args = params.get('args', [])

        # Authentication
        if service == 'common' and method_name == 'authenticate':
            return 1  # Mock user ID

        # Version info
        if service == 'common' and method_name == 'version':
            return {
                'server_version': '19.0 (MOCK)',
                'server_serie': '19.0',
                'protocol_version': 1
            }

        # Object methods
        if service == 'object' and method_name == 'execute_kw':
            if len(args) >= 5:
                model = args[3]
                operation = args[4]

                # Create operations return new ID
                if operation == 'create':
                    return self._get_next_mock_id()

                # Search/read operations return mock data
                if operation in ['search', 'search_read']:
                    return self._generate_mock_records(model, args)

                # Action methods return True
                if operation.startswith('action_') or operation.startswith('button_'):
                    return True

        return True  # Default mock result

    def _generate_mock_records(self, model: str, args: List) -> List[Dict]:
        """Generate mock records for search operations."""
        if model == 'res.partner':
            return [{
                'id': 1,
                'name': 'Mock Partner',
                'email': 'mock@example.com',
                'phone': '+1-555-0100',
                'is_company': True,
                'customer_rank': 1,
                'supplier_rank': 0,
                'street': '123 Mock Street',
                'city': 'Mock City',
                'country_id': [1, 'United States'],
                'vat': 'US123456789'
            }]

        if model == 'account.move':
            return [{
                'id': 100,
                'name': 'INV/2026/0001 (MOCK)',
                'partner_id': [1, 'Mock Partner'],
                'move_type': 'out_invoice',
                'state': 'draft',
                'amount_total': 1000.00,
                'amount_residual': 1000.00,
                'invoice_date': date.today().isoformat(),
                'invoice_date_due': date.today().isoformat(),
                'currency_id': [1, 'USD'],
                'invoice_line_ids': [1, 2]
            }]

        if model == 'account.payment':
            return [{
                'id': 200,
                'name': 'PAY/2026/0001 (MOCK)',
                'partner_id': [1, 'Mock Partner'],
                'payment_type': 'inbound',
                'amount': 500.00,
                'state': 'draft',
                'date': date.today().isoformat(),
                'currency_id': [1, 'USD'],
                'ref': 'Mock payment'
            }]

        if model == 'res.users':
            return [{
                'id': 1,
                'name': 'Mock Admin User',
                'email': 'admin@mock-odoo.com',
                'company_id': [1, 'Mock Company']
            }]

        return []

    def authenticate(self) -> int:
        """
        Authenticate with Odoo and get user ID.

        Returns:
            User ID (uid) on success

        Raises:
            OdooAuthError: If authentication fails
        """
        try:
            result = self._json_rpc(
                '/jsonrpc',
                'call',
                {
                    'service': 'common',
                    'method': 'authenticate',
                    'args': [self.database, self.username, self.password, {}]
                }
            )

            if not result:
                raise OdooAuthError("Authentication failed - invalid credentials")

            self.uid = result
            logger.info(f"Authenticated as user ID: {self.uid}")
            return self.uid

        except OdooAPIError as e:
            raise OdooAuthError(f"Authentication error: {e}")

    def _execute_kw(
        self,
        model: str,
        method: str,
        args: List = None,
        kwargs: Dict = None
    ) -> Any:
        """
        Execute a method on an Odoo model.

        Args:
            model: Odoo model name (e.g., 'res.partner')
            method: Method name (e.g., 'search_read')
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Method result
        """
        if self.uid is None:
            self.authenticate()

        args = args or []
        kwargs = kwargs or {}

        return self._json_rpc(
            '/jsonrpc',
            'call',
            {
                'service': 'object',
                'method': 'execute_kw',
                'args': [
                    self.database,
                    self.uid,
                    self.password,
                    model,
                    method,
                    args,
                    kwargs
                ]
            }
        )

    # ==================== Partner Management ====================

    def search_partners(
        self,
        domain: List = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OdooPartner]:
        """
        Search for partners (customers/vendors).

        Args:
            domain: Odoo domain filter (e.g., [['is_company', '=', True]])
            limit: Maximum records to return
            offset: Pagination offset

        Returns:
            List of OdooPartner objects
        """
        domain = domain or []
        fields = [
            'name', 'email', 'phone', 'is_company',
            'customer_rank', 'supplier_rank', 'street',
            'city', 'country_id', 'vat'
        ]

        results = self._execute_kw(
            'res.partner',
            'search_read',
            [domain],
            {'fields': fields, 'limit': limit, 'offset': offset}
        )

        partners = []
        for r in results:
            partners.append(OdooPartner(
                id=r['id'],
                name=r.get('name', ''),
                email=r.get('email') or '',
                phone=r.get('phone') or '',
                is_company=r.get('is_company', False),
                customer_rank=r.get('customer_rank', 0),
                supplier_rank=r.get('supplier_rank', 0),
                street=r.get('street') or '',
                city=r.get('city') or '',
                country=r['country_id'][1] if r.get('country_id') else '',
                vat=r.get('vat') or ''
            ))

        return partners

    def get_partner(self, partner_id: int) -> Optional[OdooPartner]:
        """Get a specific partner by ID."""
        partners = self.search_partners([['id', '=', partner_id]], limit=1)
        return partners[0] if partners else None

    def create_partner(
        self,
        name: str,
        email: str = '',
        phone: str = '',
        is_company: bool = False,
        is_customer: bool = True,
        is_vendor: bool = False,
        **kwargs
    ) -> int:
        """
        Create a new partner.

        Args:
            name: Partner name
            email: Email address
            phone: Phone number
            is_company: True if company, False if individual
            is_customer: True to mark as customer
            is_vendor: True to mark as vendor
            **kwargs: Additional fields

        Returns:
            New partner ID
        """
        vals = {
            'name': name,
            'email': email,
            'phone': phone,
            'is_company': is_company,
            'customer_rank': 1 if is_customer else 0,
            'supplier_rank': 1 if is_vendor else 0,
            **kwargs
        }

        partner_id = self._execute_kw('res.partner', 'create', [vals])
        logger.info(f"Created partner: {name} (ID: {partner_id})")
        return partner_id

    # ==================== Invoice Management ====================

    def search_invoices(
        self,
        domain: List = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OdooInvoice]:
        """
        Search for invoices.

        Args:
            domain: Odoo domain filter
            limit: Maximum records to return
            offset: Pagination offset

        Returns:
            List of OdooInvoice objects
        """
        domain = domain or []
        fields = [
            'name', 'partner_id', 'move_type', 'state',
            'amount_total', 'amount_residual', 'invoice_date',
            'invoice_date_due', 'currency_id', 'invoice_line_ids'
        ]

        results = self._execute_kw(
            'account.move',
            'search_read',
            [domain],
            {'fields': fields, 'limit': limit, 'offset': offset}
        )

        invoices = []
        for r in results:
            invoices.append(OdooInvoice(
                id=r['id'],
                name=r.get('name', ''),
                partner_id=r['partner_id'][0] if r.get('partner_id') else 0,
                partner_name=r['partner_id'][1] if r.get('partner_id') else '',
                move_type=r.get('move_type', ''),
                state=r.get('state', ''),
                amount_total=r.get('amount_total', 0.0),
                amount_residual=r.get('amount_residual', 0.0),
                invoice_date=r.get('invoice_date') or '',
                invoice_date_due=r.get('invoice_date_due') or '',
                currency=r['currency_id'][1] if r.get('currency_id') else 'USD',
                lines=[]
            ))

        return invoices

    def get_invoice(self, invoice_id: int) -> Optional[OdooInvoice]:
        """Get a specific invoice by ID."""
        invoices = self.search_invoices([['id', '=', invoice_id]], limit=1)
        return invoices[0] if invoices else None

    def create_draft_invoice(
        self,
        partner_id: int,
        lines: List[Dict],
        move_type: str = 'out_invoice',
        invoice_date: str = None,
        invoice_date_due: str = None,
        **kwargs
    ) -> int:
        """
        Create a DRAFT invoice (requires approval to post).

        Args:
            partner_id: Customer/vendor partner ID
            lines: List of invoice line dicts with:
                - name: Description
                - quantity: Quantity
                - price_unit: Unit price
                - (optional) product_id: Product ID
                - (optional) tax_ids: List of tax IDs
            move_type: Invoice type:
                - 'out_invoice': Customer invoice
                - 'in_invoice': Vendor bill
                - 'out_refund': Customer credit note
                - 'in_refund': Vendor credit note
            invoice_date: Invoice date (YYYY-MM-DD)
            invoice_date_due: Due date (YYYY-MM-DD)
            **kwargs: Additional fields

        Returns:
            New invoice ID (in draft state)
        """
        invoice_date = invoice_date or date.today().isoformat()

        # Prepare invoice lines
        invoice_lines = []
        for line in lines:
            line_vals = {
                'name': line.get('name', 'Product/Service'),
                'quantity': line.get('quantity', 1),
                'price_unit': line.get('price_unit', 0),
            }
            if 'product_id' in line:
                line_vals['product_id'] = line['product_id']
            if 'tax_ids' in line:
                line_vals['tax_ids'] = [(6, 0, line['tax_ids'])]

            invoice_lines.append((0, 0, line_vals))

        vals = {
            'partner_id': partner_id,
            'move_type': move_type,
            'invoice_date': invoice_date,
            'invoice_line_ids': invoice_lines,
            **kwargs
        }

        if invoice_date_due:
            vals['invoice_date_due'] = invoice_date_due

        invoice_id = self._execute_kw('account.move', 'create', [vals])
        logger.info(f"Created draft invoice ID: {invoice_id} for partner: {partner_id}")
        return invoice_id

    def post_invoice(self, invoice_id: int) -> bool:
        """
        Post (confirm) an invoice. Requires HITL approval.

        Args:
            invoice_id: Invoice ID to post

        Returns:
            True if successful
        """
        self._execute_kw('account.move', 'action_post', [[invoice_id]])
        logger.info(f"Posted invoice ID: {invoice_id}")
        return True

    def cancel_invoice(self, invoice_id: int) -> bool:
        """Cancel an invoice."""
        self._execute_kw('account.move', 'button_cancel', [[invoice_id]])
        logger.info(f"Cancelled invoice ID: {invoice_id}")
        return True

    # ==================== Payment Management ====================

    def search_payments(
        self,
        domain: List = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OdooPayment]:
        """
        Search for payments.

        Args:
            domain: Odoo domain filter
            limit: Maximum records to return
            offset: Pagination offset

        Returns:
            List of OdooPayment objects
        """
        domain = domain or []
        fields = [
            'name', 'partner_id', 'payment_type', 'amount',
            'state', 'date', 'currency_id', 'ref'
        ]

        results = self._execute_kw(
            'account.payment',
            'search_read',
            [domain],
            {'fields': fields, 'limit': limit, 'offset': offset}
        )

        payments = []
        for r in results:
            payments.append(OdooPayment(
                id=r['id'],
                name=r.get('name', ''),
                partner_id=r['partner_id'][0] if r.get('partner_id') else 0,
                partner_name=r['partner_id'][1] if r.get('partner_id') else '',
                payment_type=r.get('payment_type', ''),
                amount=r.get('amount', 0.0),
                state=r.get('state', ''),
                date=r.get('date') or '',
                currency=r['currency_id'][1] if r.get('currency_id') else 'USD',
                memo=r.get('ref') or ''
            ))

        return payments

    def create_draft_payment(
        self,
        partner_id: int,
        amount: float,
        payment_type: str = 'inbound',
        journal_id: int = None,
        payment_date: str = None,
        memo: str = '',
        **kwargs
    ) -> int:
        """
        Create a DRAFT payment (requires approval to post).

        Args:
            partner_id: Customer/vendor partner ID
            amount: Payment amount
            payment_type: 'inbound' (receive) or 'outbound' (send)
            journal_id: Journal ID (optional, uses default bank journal)
            payment_date: Payment date (YYYY-MM-DD)
            memo: Payment reference/memo
            **kwargs: Additional fields

        Returns:
            New payment ID (in draft state)
        """
        payment_date = payment_date or date.today().isoformat()

        vals = {
            'partner_id': partner_id,
            'amount': amount,
            'payment_type': payment_type,
            'date': payment_date,
            'ref': memo,
            **kwargs
        }

        if journal_id:
            vals['journal_id'] = journal_id

        payment_id = self._execute_kw('account.payment', 'create', [vals])
        logger.info(f"Created draft payment ID: {payment_id}, amount: {amount}")
        return payment_id

    def post_payment(self, payment_id: int) -> bool:
        """
        Post (confirm) a payment. Requires HITL approval.

        Args:
            payment_id: Payment ID to post

        Returns:
            True if successful
        """
        self._execute_kw('account.payment', 'action_post', [[payment_id]])
        logger.info(f"Posted payment ID: {payment_id}")
        return True

    # ==================== Accounting Queries ====================

    def get_account_balance(self, account_code: str = None) -> Dict[str, float]:
        """
        Get account balances.

        Args:
            account_code: Specific account code or None for all

        Returns:
            Dictionary with account codes and balances
        """
        domain = []
        if account_code:
            domain.append(['code', '=', account_code])

        accounts = self._execute_kw(
            'account.account',
            'search_read',
            [domain],
            {'fields': ['code', 'name', 'current_balance']}
        )

        return {
            acc['code']: {
                'name': acc['name'],
                'balance': acc.get('current_balance', 0.0)
            }
            for acc in accounts
        }

    def get_unpaid_invoices(self, partner_id: int = None) -> List[OdooInvoice]:
        """Get all unpaid (open) invoices."""
        domain = [
            ['state', '=', 'posted'],
            ['amount_residual', '>', 0]
        ]
        if partner_id:
            domain.append(['partner_id', '=', partner_id])

        return self.search_invoices(domain)

    def get_overdue_invoices(self) -> List[OdooInvoice]:
        """Get all overdue invoices."""
        today = date.today().isoformat()
        domain = [
            ['state', '=', 'posted'],
            ['amount_residual', '>', 0],
            ['invoice_date_due', '<', today]
        ]
        return self.search_invoices(domain)

    def get_revenue_summary(
        self,
        date_from: str = None,
        date_to: str = None
    ) -> Dict[str, float]:
        """
        Get revenue summary for a period.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dictionary with revenue metrics
        """
        domain = [
            ['move_type', 'in', ['out_invoice', 'out_refund']],
            ['state', '=', 'posted']
        ]

        if date_from:
            domain.append(['invoice_date', '>=', date_from])
        if date_to:
            domain.append(['invoice_date', '<=', date_to])

        invoices = self.search_invoices(domain, limit=1000)

        total_invoiced = sum(
            inv.amount_total for inv in invoices
            if inv.move_type == 'out_invoice'
        )
        total_refunds = sum(
            inv.amount_total for inv in invoices
            if inv.move_type == 'out_refund'
        )
        total_outstanding = sum(inv.amount_residual for inv in invoices)

        return {
            'total_invoiced': total_invoiced,
            'total_refunds': total_refunds,
            'net_revenue': total_invoiced - total_refunds,
            'total_outstanding': total_outstanding,
            'invoice_count': len([i for i in invoices if i.move_type == 'out_invoice']),
            'refund_count': len([i for i in invoices if i.move_type == 'out_refund'])
        }

    def get_expense_summary(
        self,
        date_from: str = None,
        date_to: str = None
    ) -> Dict[str, float]:
        """
        Get expense summary for a period.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dictionary with expense metrics
        """
        domain = [
            ['move_type', 'in', ['in_invoice', 'in_refund']],
            ['state', '=', 'posted']
        ]

        if date_from:
            domain.append(['invoice_date', '>=', date_from])
        if date_to:
            domain.append(['invoice_date', '<=', date_to])

        bills = self.search_invoices(domain, limit=1000)

        total_billed = sum(
            inv.amount_total for inv in bills
            if inv.move_type == 'in_invoice'
        )
        total_credits = sum(
            inv.amount_total for inv in bills
            if inv.move_type == 'in_refund'
        )
        total_outstanding = sum(inv.amount_residual for inv in bills)

        return {
            'total_billed': total_billed,
            'total_credits': total_credits,
            'net_expenses': total_billed - total_credits,
            'total_outstanding': total_outstanding,
            'bill_count': len([b for b in bills if b.move_type == 'in_invoice']),
            'credit_count': len([b for b in bills if b.move_type == 'in_refund'])
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Odoo server.

        Returns:
            Dictionary with connection info
        """
        try:
            # Get server version
            version = self._json_rpc(
                '/jsonrpc',
                'call',
                {
                    'service': 'common',
                    'method': 'version',
                    'args': []
                }
            )

            # Authenticate
            uid = self.authenticate()

            # Get user info
            user_info = self._execute_kw(
                'res.users',
                'search_read',
                [[['id', '=', uid]]],
                {'fields': ['name', 'email', 'company_id']}
            )

            result = {
                'connected': True,
                'mock_mode': self.mock_mode,
                'server_version': version.get('server_version', 'unknown'),
                'user_id': uid,
                'user_name': user_info[0]['name'] if user_info else 'Unknown',
                'user_email': user_info[0].get('email', '') if user_info else '',
                'company': user_info[0]['company_id'][1] if user_info and user_info[0].get('company_id') else 'Unknown'
            }

            if self.mock_mode:
                result['note'] = 'Running in MOCK MODE - no real Odoo connection'

            return result

        except Exception as e:
            return {
                'connected': False,
                'mock_mode': self.mock_mode,
                'error': str(e)
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current OdooClient status."""
        return {
            'mock_mode': self.mock_mode,
            'url': self.url,
            'database': self.database,
            'username': self.username,
            'authenticated': self.uid is not None,
            'user_id': self.uid
        }


def main():
    """Test the Odoo client with mock mode demo."""
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("Odoo Client - AI Employee Zoya")
    print("=" * 60)

    # Initialize client (will auto-detect mock mode from environment)
    client = OdooClient()

    # Show status
    status = client.get_status()
    print(f"\nMock Mode: {'ENABLED' if status['mock_mode'] else 'DISABLED'}")
    print(f"URL: {status['url']}")
    print(f"Database: {status['database']}")

    print("\n" + "-" * 40)
    print("Testing connection...")
    print("-" * 40)
    result = client.test_connection()
    print(json.dumps(result, indent=2, default=str))

    if status['mock_mode']:
        print("\n" + "-" * 40)
        print("Demo: Creating mock invoice...")
        print("-" * 40)

        invoice_id = client.create_draft_invoice(
            partner_id=1,
            lines=[
                {'name': 'Consulting Services', 'quantity': 10, 'price_unit': 150.00},
                {'name': 'Project Setup Fee', 'quantity': 1, 'price_unit': 500.00}
            ],
            move_type='out_invoice'
        )
        print(f"Created draft invoice ID: {invoice_id}")

        print("\n" + "-" * 40)
        print("Demo: Creating mock payment...")
        print("-" * 40)

        payment_id = client.create_draft_payment(
            partner_id=1,
            amount=1000.00,
            payment_type='inbound',
            memo='Payment for invoice'
        )
        print(f"Created draft payment ID: {payment_id}")

    print("\n" + "=" * 60)
    print("Odoo client test completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
