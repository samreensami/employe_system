"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      WHATSAPP CLOUD API SKILL - ZOYA AI                      ║
║                    Meta Graph API v21.0 Integration                          ║
║                                                                              ║
║  Project: samreensami/hack2-phase2                                           ║
║  Status: ACTIVE with real credentials                                        ║
║                                                                              ║
║  Features:                                                                   ║
║  - Send text messages via WhatsApp Business API                              ║
║  - Send template messages                                                    ║
║  - MCP integration for unified messaging                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file."""
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

# Load environment on import
load_env()


class WhatsAppCloudAPI:
    """
    WhatsApp Cloud API client using Meta Graph API.

    Uses the official Meta Cloud API for WhatsApp Business.
    API Version: v21.0
    """

    BASE_URL = "https://graph.facebook.com"

    def __init__(self):
        self.access_token = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
        self.business_account_id = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID', '')
        self.api_version = os.getenv('WHATSAPP_API_VERSION', 'v21.0')
        self.enabled = os.getenv('WHATSAPP_ENABLED', 'false').lower() == 'true'

        # Audit logging
        self.audit_log_path = Path("logs/whatsapp_audit.json")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

        self._log_init()

    def _log_init(self):
        """Log initialization status."""
        if self.is_configured():
            print(f"\n[ZOYA WHATSAPP] ✅ WhatsApp Cloud API initialized")
            print(f"[ZOYA WHATSAPP] API Version: {self.api_version}")
            print(f"[ZOYA WHATSAPP] Phone ID: {self.phone_number_id[:10]}...")
            print(f"[ZOYA WHATSAPP] Status: ACTIVE")
            logger.info("WhatsApp Cloud API initialized successfully")
        else:
            print(f"\n[ZOYA WHATSAPP] ⚠️ WhatsApp not configured")
            print(f"[ZOYA WHATSAPP] Status: OFFLINE")
            logger.warning("WhatsApp Cloud API not configured")

    def is_configured(self) -> bool:
        """Check if WhatsApp API is properly configured."""
        # In demo/mock mode, consider configured if WHATSAPP_ENABLED=true
        mock_mode = os.getenv('MOCK_MODE', 'false').lower() == 'true'
        if mock_mode and self.enabled:
            return True

        return bool(
            self.enabled and
            self.access_token and
            self.access_token != 'your_whatsapp_access_token_here' and
            self.phone_number_id and
            self.phone_number_id != 'your_phone_number_id_here'
        )

    def get_status(self) -> Dict[str, Any]:
        """Get WhatsApp API status."""
        return {
            "enabled": self.enabled,
            "configured": self.is_configured(),
            "api_version": self.api_version,
            "phone_number_id": self.phone_number_id[:10] + "..." if self.phone_number_id else None,
            "business_account_id": self.business_account_id[:10] + "..." if self.business_account_id else None,
            "status": "🟢 Active" if self.is_configured() else "🔴 Offline",
            "mcp_ready": self.is_configured()
        }

    def _get_api_url(self, endpoint: str = "messages") -> str:
        """Build the API URL."""
        return f"{self.BASE_URL}/{self.api_version}/{self.phone_number_id}/{endpoint}"

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _log_to_audit(self, action: str, status: str, details: Dict):
        """Log action to audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": f"WHATSAPP_{action}",
            "actor": "Zoya_AI_WhatsApp",
            "status": status,
            "details": details
        }

        # Load existing logs
        logs = []
        if self.audit_log_path.exists():
            try:
                with open(self.audit_log_path, encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                logs = []

        logs.append(entry)

        with open(self.audit_log_path, 'w', encoding='utf-8') as f:
            json.dump(logs[-100:], f, indent=2)

        return entry

    def send_text_message(self, to: str, message: str) -> Tuple[bool, Dict]:
        """
        Send a text message via WhatsApp Cloud API.

        Args:
            to: Recipient phone number (with country code, e.g., "923001234567")
            message: Text message to send

        Returns:
            Tuple of (success: bool, response: dict)
        """
        if not self.is_configured():
            error_msg = "WhatsApp API not configured"
            print(f"[ZOYA WHATSAPP] ❌ {error_msg}")
            return (False, {"error": error_msg, "status": "not_configured"})

        # Clean phone number (remove + and spaces)
        to_clean = to.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }

        print(f"\n[ZOYA WHATSAPP] 📤 Sending message to {to_clean[:6]}***")
        print(f"[ZOYA WHATSAPP] Message: {message[:50]}...")

        try:
            response = requests.post(
                self._get_api_url("messages"),
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200:
                message_id = response_data.get("messages", [{}])[0].get("id", "unknown")
                print(f"[ZOYA WHATSAPP] ✅ Message sent successfully!")
                print(f"[ZOYA WHATSAPP] Message ID: {message_id}")

                self._log_to_audit("SEND_TEXT", "SUCCESS", {
                    "to": to_clean[:6] + "***",
                    "message_preview": message[:50],
                    "message_id": message_id
                })

                return (True, {
                    "success": True,
                    "message_id": message_id,
                    "status": "sent",
                    "to": to_clean
                })
            else:
                error = response_data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                print(f"[ZOYA WHATSAPP] ❌ Failed: {error_msg}")

                self._log_to_audit("SEND_TEXT", "FAILED", {
                    "to": to_clean[:6] + "***",
                    "error": error_msg,
                    "status_code": response.status_code
                })

                return (False, {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                })

        except requests.exceptions.Timeout:
            print(f"[ZOYA WHATSAPP] ❌ Request timeout")
            return (False, {"error": "Request timeout", "status": "timeout"})
        except requests.exceptions.RequestException as e:
            print(f"[ZOYA WHATSAPP] ❌ Request error: {e}")
            return (False, {"error": str(e), "status": "request_error"})

    def send_template_message(self, to: str, template_name: str, language_code: str = "en_US", components: list = None) -> Tuple[bool, Dict]:
        """
        Send a template message via WhatsApp Cloud API.

        Args:
            to: Recipient phone number
            template_name: Name of the approved template
            language_code: Template language code
            components: Template components (header, body, buttons)

        Returns:
            Tuple of (success: bool, response: dict)
        """
        if not self.is_configured():
            return (False, {"error": "WhatsApp API not configured"})

        to_clean = to.replace("+", "").replace(" ", "").replace("-", "")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

        if components:
            payload["template"]["components"] = components

        print(f"\n[ZOYA WHATSAPP] 📤 Sending template '{template_name}' to {to_clean[:6]}***")

        try:
            response = requests.post(
                self._get_api_url("messages"),
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            response_data = response.json()

            if response.status_code == 200:
                message_id = response_data.get("messages", [{}])[0].get("id", "unknown")
                print(f"[ZOYA WHATSAPP] ✅ Template message sent!")
                print(f"[ZOYA WHATSAPP] Message ID: {message_id}")

                self._log_to_audit("SEND_TEMPLATE", "SUCCESS", {
                    "to": to_clean[:6] + "***",
                    "template": template_name,
                    "message_id": message_id
                })

                return (True, {
                    "success": True,
                    "message_id": message_id,
                    "template": template_name,
                    "status": "sent"
                })
            else:
                error = response_data.get("error", {}).get("message", "Unknown error")
                print(f"[ZOYA WHATSAPP] ❌ Failed: {error}")
                return (False, {"error": error})

        except Exception as e:
            print(f"[ZOYA WHATSAPP] ❌ Error: {e}")
            return (False, {"error": str(e)})

    def get_phone_number_info(self) -> Tuple[bool, Dict]:
        """Get information about the registered phone number."""
        if not self.is_configured():
            return (False, {"error": "WhatsApp API not configured"})

        try:
            url = f"{self.BASE_URL}/{self.api_version}/{self.phone_number_id}"
            response = requests.get(url, headers=self._get_headers(), timeout=30)

            if response.status_code == 200:
                return (True, response.json())
            else:
                return (False, response.json())

        except Exception as e:
            return (False, {"error": str(e)})


# Singleton instance
_whatsapp_client: Optional[WhatsAppCloudAPI] = None


def get_whatsapp_client() -> WhatsAppCloudAPI:
    """Get the WhatsApp client singleton."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppCloudAPI()
    return _whatsapp_client


def is_whatsapp_active() -> bool:
    """Check if WhatsApp is active and configured."""
    client = get_whatsapp_client()
    return client.is_configured()


def get_whatsapp_status() -> Dict[str, Any]:
    """Get WhatsApp status for UI display."""
    client = get_whatsapp_client()
    return client.get_status()


def send_whatsapp_message(to: str, message: str) -> Tuple[bool, Dict]:
    """Quick function to send a WhatsApp message."""
    client = get_whatsapp_client()
    return client.send_text_message(to, message)


# MCP Tool wrapper for unified interface
def mcp_whatsapp_send(params: Dict) -> Dict:
    """MCP tool wrapper for WhatsApp send."""
    to = params.get("to", "")
    message = params.get("message", "")

    if not to or not message:
        return {"success": False, "error": "Missing 'to' or 'message' parameter"}

    success, result = send_whatsapp_message(to, message)
    return {"success": success, **result}


if __name__ == "__main__":
    print("\n" + "="*60)
    print("WhatsApp Cloud API - Connection Test")
    print("="*60)

    client = get_whatsapp_client()

    print("\n📊 Status:")
    status = client.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    if client.is_configured():
        print("\n✅ WhatsApp Cloud API is ACTIVE and ready!")
        print("   You can send messages via Zoya AI.")
    else:
        print("\n⚠️ WhatsApp not configured.")
        print("   Please check .env file for credentials.")

    print("\n" + "="*60)
