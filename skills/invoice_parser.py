"""
Invoice Parser - Document Intelligence for PDF/Image Invoice Processing.

This module extracts key invoice data using OCR (pytesseract/easyocr):
- Total Amount
- Date
- Vendor Name

Features:
- PDF and image (PNG, JPG, JPEG) support
- Multiple OCR engine support (pytesseract primary, easyocr fallback)
- Automatic Odoo draft invoice creation
- Confidence scoring for extracted data
- Audit logging for all operations

Part of Phase III - Document Intelligence
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict

# Configure logging
logger = logging.getLogger(__name__)

# Try to import OCR libraries (graceful handling if missing)
PYTESSERACT_AVAILABLE = False
EASYOCR_AVAILABLE = False
PDF2IMAGE_AVAILABLE = False
PIL_AVAILABLE = False
_OCR_IMPORT_MESSAGES = []

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    _OCR_IMPORT_MESSAGES.append("pytesseract not installed")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    _OCR_IMPORT_MESSAGES.append("easyocr not installed")

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    _OCR_IMPORT_MESSAGES.append("pdf2image not installed")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    _OCR_IMPORT_MESSAGES.append("Pillow not installed")

# Only log once if OCR is missing (not on every import)
if not (PYTESSERACT_AVAILABLE or EASYOCR_AVAILABLE):
    logger.info("OCR libraries not available - Demo mode will be used for invoice extraction")


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


load_env_file()


@dataclass
class InvoiceData:
    """Extracted invoice data with confidence scores."""
    vendor_name: str
    total_amount: float
    currency: str
    invoice_date: str
    raw_text: str
    confidence: Dict[str, float]  # Confidence scores for each field
    source_file: str
    extraction_time: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def is_valid(self) -> bool:
        """Check if minimum required fields are extracted."""
        return bool(self.vendor_name and self.total_amount > 0)


class InvoiceParser:
    """
    OCR-based invoice parser for extracting key data from PDFs and images.

    Supports multiple OCR engines:
    - pytesseract (primary) - requires Tesseract installed
    - easyocr (fallback) - pure Python, no external dependencies
    """

    def __init__(self, ocr_engine: str = 'auto'):
        """
        Initialize the invoice parser.

        Args:
            ocr_engine: 'pytesseract', 'easyocr', or 'auto' (try both)
        """
        self.ocr_engine = ocr_engine
        self.easyocr_reader = None
        self.audit_log_path = "logs/audit_log.json"

        # Ensure logs directory exists
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)

        # Initialize easyocr reader lazily (it's slow to initialize)
        if ocr_engine == 'easyocr' and EASYOCR_AVAILABLE:
            self._init_easyocr()

    def _init_easyocr(self):
        """Initialize easyocr reader (lazy loading)."""
        if self.easyocr_reader is None and EASYOCR_AVAILABLE:
            self.easyocr_reader = easyocr.Reader(['en'])

    def _log_operation(self, operation: str, status: str, details: Dict):
        """Log operation to audit log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": f"INVOICE_PARSER_{operation}",
            "actor": "Zoya_AI_DocIntelligence",
            "status": status,
            "details": details
        }

        # Read existing logs
        existing_logs = []
        if os.path.exists(self.audit_log_path):
            try:
                with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        existing_logs = json.loads(content)
                        if not isinstance(existing_logs, list):
                            existing_logs = [existing_logs]
            except (json.JSONDecodeError, ValueError):
                existing_logs = []

        existing_logs.append(entry)

        with open(self.audit_log_path, 'w', encoding='utf-8') as f:
            json.dump(existing_logs[-100:], f, indent=2)

        # Terminal logging
        print(f"[INVOICE_PARSER] {operation} [{status}]: {details.get('file', 'N/A')}")

        return entry

    def _extract_text_pytesseract(self, image) -> str:
        """Extract text using pytesseract."""
        if not PYTESSERACT_AVAILABLE:
            return ""

        try:
            text = pytesseract.image_to_string(image, config='--psm 6')
            return text
        except Exception as e:
            logger.error(f"pytesseract error: {e}")
            return ""

    def _extract_text_easyocr(self, image_path: str) -> str:
        """Extract text using easyocr."""
        if not EASYOCR_AVAILABLE:
            return ""

        try:
            self._init_easyocr()
            results = self.easyocr_reader.readtext(image_path)
            text = '\n'.join([r[1] for r in results])
            return text
        except Exception as e:
            logger.error(f"easyocr error: {e}")
            return ""

    def _convert_pdf_to_images(self, pdf_path: str) -> List:
        """Convert PDF pages to images."""
        if not PDF2IMAGE_AVAILABLE:
            logger.error("pdf2image not available for PDF conversion")
            return []

        try:
            images = convert_from_path(pdf_path, dpi=300)
            return images
        except Exception as e:
            logger.error(f"PDF conversion error: {e}")
            return []

    def _extract_text_from_file(self, file_path: str) -> Tuple[str, str]:
        """
        Extract text from PDF or image file.

        Returns:
            Tuple of (extracted_text, ocr_engine_used)
        """
        file_path = str(file_path)
        file_ext = Path(file_path).suffix.lower()

        all_text = []
        engine_used = "none"

        # Handle PDF files
        if file_ext == '.pdf':
            images = self._convert_pdf_to_images(file_path)
            if not images:
                return "", "pdf_conversion_failed"

            for i, image in enumerate(images):
                # Try pytesseract first
                if self.ocr_engine in ['auto', 'pytesseract'] and PYTESSERACT_AVAILABLE:
                    text = self._extract_text_pytesseract(image)
                    if text.strip():
                        all_text.append(text)
                        engine_used = "pytesseract"
                        continue

                # Fallback to easyocr
                if self.ocr_engine in ['auto', 'easyocr'] and EASYOCR_AVAILABLE:
                    # Save temp image for easyocr
                    temp_path = f"/tmp/invoice_page_{i}.png"
                    image.save(temp_path)
                    text = self._extract_text_easyocr(temp_path)
                    if text.strip():
                        all_text.append(text)
                        engine_used = "easyocr"
                    # Clean up temp file
                    try:
                        os.remove(temp_path)
                    except:
                        pass

        # Handle image files
        elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            if not PIL_AVAILABLE:
                return "", "pil_not_available"

            image = Image.open(file_path)

            # Try pytesseract first
            if self.ocr_engine in ['auto', 'pytesseract'] and PYTESSERACT_AVAILABLE:
                text = self._extract_text_pytesseract(image)
                if text.strip():
                    all_text.append(text)
                    engine_used = "pytesseract"

            # Fallback to easyocr
            if not all_text and self.ocr_engine in ['auto', 'easyocr'] and EASYOCR_AVAILABLE:
                text = self._extract_text_easyocr(file_path)
                if text.strip():
                    all_text.append(text)
                    engine_used = "easyocr"

        return '\n'.join(all_text), engine_used

    def _extract_amount(self, text: str) -> Tuple[float, str, float]:
        """
        Extract total amount and currency from text.

        Returns:
            Tuple of (amount, currency, confidence)
        """
        text_lower = text.lower()

        # Currency patterns
        currency_symbols = {
            '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₹': 'INR',
            'usd': 'USD', 'eur': 'EUR', 'gbp': 'GBP', 'inr': 'INR'
        }

        # Amount patterns - look for total/grand total/amount due
        total_patterns = [
            r'(?:grand\s*total|total\s*due|amount\s*due|total\s*amount|balance\s*due|total)[:\s]*[$€£¥₹]?\s*([\d,]+\.?\d*)',
            r'[$€£¥₹]\s*([\d,]+\.?\d*)\s*(?:total|due)',
            r'(?:total|sum|amount)[:\s]*[$€£¥₹]?\s*([\d,]+\.?\d*)',
            r'[$€£¥₹]\s*([\d,]+\.?\d*)',
        ]

        best_amount = 0.0
        best_currency = 'USD'
        confidence = 0.0

        for pattern in total_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                for match in matches:
                    try:
                        amount = float(match.replace(',', ''))
                        if amount > best_amount:
                            best_amount = amount
                            # Higher confidence for explicit "total" patterns
                            confidence = 0.9 if 'total' in pattern else 0.6
                    except ValueError:
                        continue

        # Detect currency
        for symbol, curr in currency_symbols.items():
            if symbol in text or symbol in text_lower:
                best_currency = curr
                break

        return best_amount, best_currency, confidence

    def _extract_date(self, text: str) -> Tuple[str, float]:
        """
        Extract invoice date from text.

        Returns:
            Tuple of (date_string in YYYY-MM-DD format, confidence)
        """
        # Date patterns
        date_patterns = [
            # MM/DD/YYYY or MM-DD-YYYY
            (r'(?:invoice\s*date|date|dated)[:\s]*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'mdy', 0.9),
            (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'mdy', 0.7),
            # YYYY-MM-DD
            (r'(?:invoice\s*date|date|dated)[:\s]*(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', 'ymd', 0.9),
            (r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', 'ymd', 0.7),
            # Month DD, YYYY
            (r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', 'text', 0.8),
            # DD Month YYYY
            (r'(\d{1,2})\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', 'dtext', 0.8),
        ]

        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        text_lower = text.lower()

        for pattern, fmt, conf in date_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                match = matches[0]
                try:
                    if fmt == 'mdy':
                        month, day, year = int(match[0]), int(match[1]), int(match[2])
                    elif fmt == 'ymd':
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                    elif fmt == 'text':
                        # Find month from text
                        month_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', text_lower)
                        if month_match:
                            month = month_map[month_match.group(1)]
                            day = int(match[0])
                            year = int(match[1])
                        else:
                            continue
                    elif fmt == 'dtext':
                        month_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', text_lower)
                        if month_match:
                            month = month_map[month_match.group(1)]
                            day = int(match[0])
                            year = int(match[1])
                        else:
                            continue

                    # Validate date
                    if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
                        return f"{year:04d}-{month:02d}-{day:02d}", conf
                except (ValueError, IndexError):
                    continue

        # Default to today if no date found
        return date.today().isoformat(), 0.3

    def _extract_vendor_name(self, text: str) -> Tuple[str, float]:
        """
        Extract vendor/company name from text.

        Returns:
            Tuple of (vendor_name, confidence)
        """
        lines = text.strip().split('\n')

        # Look for common business indicators
        business_patterns = [
            r'(?:from|vendor|supplier|bill\s*from|invoice\s*from)[:\s]*(.+)',
            r'^(.+?(?:inc|llc|ltd|corp|co\.|company|enterprises|services|solutions|consulting)\.?)$',
        ]

        # First, try explicit patterns
        for pattern in business_patterns:
            for line in lines[:10]:  # Check first 10 lines
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    vendor = match.group(1).strip()
                    if len(vendor) > 2 and len(vendor) < 100:
                        return vendor, 0.9

        # Fallback: Use first non-empty line that looks like a company name
        for line in lines[:5]:
            line = line.strip()
            # Skip lines that look like addresses or dates
            if not line:
                continue
            if re.match(r'^\d', line):  # Starts with number
                continue
            if '@' in line:  # Email
                continue
            if len(line) < 3 or len(line) > 100:
                continue
            if any(word in line.lower() for word in ['invoice', 'date', 'total', 'amount', 'bill']):
                continue

            return line, 0.6

        return "Unknown Vendor", 0.2

    def _generate_mock_invoice_data(self, file_path: str) -> InvoiceData:
        """
        Generate realistic mock invoice data for demo mode.
        Used when OCR libraries are not installed.
        """
        import random
        import hashlib

        # Use filename hash for consistent but varied mock data
        file_hash = int(hashlib.md5(file_path.encode()).hexdigest()[:8], 16)
        random.seed(file_hash)

        # Mock vendor names
        vendors = [
            "Acme Corporation", "TechSupply Inc.", "Global Services Ltd.",
            "Prime Vendors Co.", "Summit Solutions", "Nexus Industries",
            "Horizon Supplies", "Apex Trading LLC", "Sterling Partners",
            "Pacific Distributors"
        ]

        # Mock amounts
        amounts = [150.00, 299.99, 450.50, 750.00, 1250.00, 2500.00, 3750.00, 5000.00]

        # Generate consistent mock data based on file
        vendor_name = vendors[file_hash % len(vendors)]
        total_amount = amounts[file_hash % len(amounts)]
        currency = "USD"

        # Generate a realistic date (within last 30 days)
        days_ago = file_hash % 30
        invoice_date = (date.today() - timedelta(days=days_ago)).isoformat()

        mock_raw_text = f"""
INVOICE
{vendor_name}
123 Business Street
New York, NY 10001

Invoice Date: {invoice_date}
Invoice #: INV-{file_hash % 10000:04d}

Description                     Amount
--------------------------------
Professional Services          ${total_amount:.2f}

                    Total:     ${total_amount:.2f}

[DEMO MODE - Simulated OCR Extraction]
"""

        self._log_operation("MOCK_EXTRACT", "DEMO_MODE", {
            "file": file_path,
            "reason": "OCR not available - using demo data",
            "vendor": vendor_name,
            "amount": total_amount
        })

        return InvoiceData(
            vendor_name=vendor_name,
            total_amount=total_amount,
            currency=currency,
            invoice_date=invoice_date,
            raw_text=mock_raw_text,
            confidence={
                "vendor_name": 0.95,
                "total_amount": 0.95,
                "invoice_date": 0.95,
                "overall": 0.95
            },
            source_file=file_path,
            extraction_time=datetime.now().isoformat()
        )

    def parse_invoice(self, file_path: str) -> InvoiceData:
        """
        Parse an invoice file and extract key data.

        Args:
            file_path: Path to PDF or image file

        Returns:
            InvoiceData object with extracted information
        """
        file_path = str(file_path)

        self._log_operation("START", "PROCESSING", {"file": file_path})

        # Check if we're in mock/demo mode
        mock_mode = os.getenv('MOCK_MODE', 'false').lower() == 'true'
        ocr_available = PYTESSERACT_AVAILABLE or EASYOCR_AVAILABLE

        # If OCR not available and we're in demo mode, use mock extraction
        if not ocr_available and mock_mode:
            print(f"[INVOICE_PARSER] Demo mode - generating simulated extraction for {Path(file_path).name}")
            return self._generate_mock_invoice_data(file_path)

        # Extract text from file
        raw_text, engine_used = self._extract_text_from_file(file_path)

        if not raw_text:
            # If OCR failed but we're in mock mode, use mock data
            if mock_mode:
                print(f"[INVOICE_PARSER] OCR failed, using demo data for {Path(file_path).name}")
                return self._generate_mock_invoice_data(file_path)

            self._log_operation("OCR", "FAILED", {
                "file": file_path,
                "reason": "No text extracted",
                "engine": engine_used
            })
            return InvoiceData(
                vendor_name="",
                total_amount=0.0,
                currency="USD",
                invoice_date=date.today().isoformat(),
                raw_text="",
                confidence={"vendor_name": 0.0, "total_amount": 0.0, "invoice_date": 0.0},
                source_file=file_path,
                extraction_time=datetime.now().isoformat()
            )

        # Extract fields
        vendor_name, vendor_conf = self._extract_vendor_name(raw_text)
        total_amount, currency, amount_conf = self._extract_amount(raw_text)
        invoice_date, date_conf = self._extract_date(raw_text)

        invoice_data = InvoiceData(
            vendor_name=vendor_name,
            total_amount=total_amount,
            currency=currency,
            invoice_date=invoice_date,
            raw_text=raw_text[:2000],  # Truncate raw text
            confidence={
                "vendor_name": vendor_conf,
                "total_amount": amount_conf,
                "invoice_date": date_conf,
                "overall": (vendor_conf + amount_conf + date_conf) / 3
            },
            source_file=file_path,
            extraction_time=datetime.now().isoformat()
        )

        self._log_operation("EXTRACT", "SUCCESS", {
            "file": file_path,
            "engine": engine_used,
            "vendor": vendor_name,
            "amount": total_amount,
            "currency": currency,
            "date": invoice_date,
            "confidence": invoice_data.confidence
        })

        return invoice_data

    def create_odoo_draft_invoice(self, invoice_data: InvoiceData) -> Dict[str, Any]:
        """
        Create a draft vendor bill in Odoo from extracted invoice data.

        Args:
            invoice_data: Extracted invoice data

        Returns:
            Dict with operation result including invoice_id
        """
        try:
            from skills.odoo_client import OdooClient
        except ImportError:
            self._log_operation("ODOO_DRAFT", "FAILED", {
                "reason": "OdooClient not available"
            })
            return {"success": False, "error": "OdooClient not available"}

        if not invoice_data.is_valid():
            self._log_operation("ODOO_DRAFT", "SKIPPED", {
                "reason": "Invalid invoice data - missing required fields"
            })
            return {"success": False, "error": "Invalid invoice data"}

        try:
            odoo = OdooClient()

            # First, find or create the vendor partner
            vendor_name = invoice_data.vendor_name
            partners = odoo.search_partners([['name', 'ilike', vendor_name]], limit=1)

            if partners:
                partner_id = partners[0].id
                partner_action = "found_existing"
            else:
                # Create new vendor partner
                partner_id = odoo.create_partner(
                    name=vendor_name,
                    is_company=True,
                    is_customer=False,
                    is_vendor=True
                )
                partner_action = "created_new"

            # Create the draft invoice (vendor bill)
            invoice_lines = [{
                'name': f"Invoice from {vendor_name}",
                'quantity': 1,
                'price_unit': invoice_data.total_amount
            }]

            invoice_id = odoo.create_draft_invoice(
                partner_id=partner_id,
                lines=invoice_lines,
                move_type='in_invoice',  # Vendor bill
                invoice_date=invoice_data.invoice_date
            )

            result = {
                "success": True,
                "invoice_id": invoice_id,
                "partner_id": partner_id,
                "partner_action": partner_action,
                "vendor_name": vendor_name,
                "amount": invoice_data.total_amount,
                "currency": invoice_data.currency,
                "date": invoice_data.invoice_date,
                "move_type": "in_invoice",
                "state": "draft"
            }

            self._log_operation("ODOO_DRAFT", "SUCCESS", result)

            # Also save to pending approval folder
            self._save_draft_to_approval(invoice_data, result)

            return result

        except Exception as e:
            error_msg = str(e)
            self._log_operation("ODOO_DRAFT", "ERROR", {
                "error": error_msg,
                "vendor": invoice_data.vendor_name
            })
            return {"success": False, "error": error_msg}

    def _save_draft_to_approval(self, invoice_data: InvoiceData, odoo_result: Dict):
        """Save draft invoice details to pending approval folder."""
        approval_dir = Path("obsidian_vault/Pending_Approval/odoo")
        approval_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"DRAFT_INVOICE_{timestamp}.md"
        filepath = approval_dir / filename

        content = f"""---
type: draft_invoice
created: {datetime.now().isoformat()}
status: pending_approval
source: document_intelligence
---

# Draft Vendor Bill - {invoice_data.vendor_name}

## Invoice Details
- **Vendor:** {invoice_data.vendor_name}
- **Amount:** {invoice_data.currency} {invoice_data.total_amount:.2f}
- **Invoice Date:** {invoice_data.invoice_date}
- **Source File:** {invoice_data.source_file}

## Odoo Record
- **Invoice ID:** {odoo_result.get('invoice_id', 'N/A')}
- **Partner ID:** {odoo_result.get('partner_id', 'N/A')}
- **Partner Action:** {odoo_result.get('partner_action', 'N/A')}
- **Status:** DRAFT (requires approval to post)

## Extraction Confidence
- Vendor Name: {invoice_data.confidence.get('vendor_name', 0):.0%}
- Total Amount: {invoice_data.confidence.get('total_amount', 0):.0%}
- Invoice Date: {invoice_data.confidence.get('invoice_date', 0):.0%}
- Overall: {invoice_data.confidence.get('overall', 0):.0%}

## Actions Required
- [ ] Review extracted data accuracy
- [ ] Verify vendor details in Odoo
- [ ] Approve or reject draft invoice

---
*Auto-generated by Zoya AI - Document Intelligence (Phase III)*
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"[INVOICE_PARSER] Draft saved to: {filepath}")

    def process_inbox_file(self, file_path: str, auto_create_odoo: bool = True) -> Dict[str, Any]:
        """
        Process an inbox file: extract data and optionally create Odoo draft.

        This is the main entry point for dashboard integration.

        Args:
            file_path: Path to the invoice file
            auto_create_odoo: Whether to automatically create Odoo draft

        Returns:
            Dict with extraction results and Odoo operation status
        """
        result = {
            "file": file_path,
            "success": False,
            "invoice_data": None,
            "odoo_result": None,
            "error": None
        }

        try:
            # Parse the invoice
            invoice_data = self.parse_invoice(file_path)
            result["invoice_data"] = invoice_data.to_dict()

            if invoice_data.is_valid():
                result["success"] = True

                # Create Odoo draft if requested
                if auto_create_odoo:
                    odoo_result = self.create_odoo_draft_invoice(invoice_data)
                    result["odoo_result"] = odoo_result
            else:
                result["error"] = "Could not extract valid invoice data"

        except Exception as e:
            result["error"] = str(e)
            self._log_operation("PROCESS", "ERROR", {"file": file_path, "error": str(e)})

        return result


# =============================================================================
# Dashboard Integration Functions
# =============================================================================

def process_invoice_from_inbox(file_path: str) -> Dict[str, Any]:
    """
    Convenience function for dashboard integration.

    Args:
        file_path: Path to invoice file in inbox

    Returns:
        Processing result dict
    """
    try:
        parser = InvoiceParser(ocr_engine='auto')
        return parser.process_inbox_file(file_path, auto_create_odoo=True)
    except Exception as e:
        # Graceful error handling - never crash the UI
        error_msg = str(e)
        print(f"[INVOICE_PARSER] Error processing {file_path}: {error_msg}")
        return {
            "file": file_path,
            "success": False,
            "invoice_data": None,
            "odoo_result": None,
            "error": f"Processing error: {error_msg}"
        }


def is_invoice_file(file_path: str) -> bool:
    """Check if a file is likely an invoice (PDF or image)."""
    ext = Path(file_path).suffix.lower()
    return ext in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']


def get_parser_status() -> Dict[str, Any]:
    """Get the status of OCR libraries."""
    mock_mode = os.getenv('MOCK_MODE', 'false').lower() == 'true'
    ocr_ready = PYTESSERACT_AVAILABLE or EASYOCR_AVAILABLE

    # In mock mode, parser is always ready (uses simulated extraction)
    is_ready = ocr_ready or mock_mode

    return {
        "pytesseract_available": PYTESSERACT_AVAILABLE,
        "easyocr_available": EASYOCR_AVAILABLE,
        "pdf2image_available": PDF2IMAGE_AVAILABLE,
        "pil_available": PIL_AVAILABLE,
        "mock_mode": mock_mode,
        "recommended_engine": "pytesseract" if PYTESSERACT_AVAILABLE else ("easyocr" if EASYOCR_AVAILABLE else ("demo" if mock_mode else "none")),
        "ready": is_ready
    }


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Invoice Parser - Document Intelligence (Phase III)")
    print("=" * 60)

    # Check dependencies
    status = get_parser_status()
    print(f"\nOCR Status:")
    print(f"  pytesseract: {'Available' if status['pytesseract_available'] else 'Not installed'}")
    print(f"  easyocr: {'Available' if status['easyocr_available'] else 'Not installed'}")
    print(f"  pdf2image: {'Available' if status['pdf2image_available'] else 'Not installed'}")
    print(f"  PIL: {'Available' if status['pil_available'] else 'Not installed'}")
    print(f"  Recommended: {status['recommended_engine']}")
    print(f"  Ready: {status['ready']}")

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"\nProcessing: {file_path}")

        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            sys.exit(1)

        result = process_invoice_from_inbox(file_path)
        print(f"\nResult:")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("\nUsage: python invoice_parser.py <invoice_file>")
        print("\nExample:")
        print("  python skills/invoice_parser.py obsidian_vault/inbox/UPLOAD_PDF_20260219.pdf")
