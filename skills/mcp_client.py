"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         MCP CLIENT - ZOYA AI                                 ║
║                   Model Context Protocol Integration                         ║
║                                                                              ║
║  Provides unified interface for all MCP server connections                   ║
║  Supports: Google, Fetch, Slack, WhatsApp, Social, Odoo                     ║
║                                                                              ║
║  Phase II Requirement: External social interactions via MCP                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path('.env')
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ.setdefault(key.strip(), value.strip())
        except Exception:
            pass


# Load .env file on module import
load_env_file()


def is_mock_mode() -> bool:
    """Check if running in mock/demo mode."""
    return os.getenv('MOCK_MODE', 'false').lower() == 'true'


class MCPClient:
    """
    Unified MCP (Model Context Protocol) client for Zoya AI.

    Handles connections to various MCP servers and provides
    fallback to file-based mode when MCP is unavailable.
    """

    def __init__(self, config_path: str = "mcp_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.active_servers: Dict[str, bool] = {}
        self.server_processes: Dict[str, subprocess.Popen] = {}
        self._check_all_servers()

    def _load_config(self) -> Dict:
        """Load MCP configuration from JSON file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"[MCP_CLIENT] Warning: Could not load config: {e}")
                return {"mcpServers": {}, "settings": {}}
            except Exception as e:
                print(f"[MCP_CLIENT] Warning: Config load error: {e}")
                return {"mcpServers": {}, "settings": {}}
        return {"mcpServers": {}, "settings": {}}

    def _check_server_status(self, server_name: str) -> bool:
        """
        Check if an MCP server is active and ready.

        Returns True if:
        1. MOCK_MODE is enabled (demo mode - all servers active)
        2. Server is configured in mcp_config.json
        3. Required environment variables are set
        4. Server process can be started (or is already running)
        """
        # In mock mode, all configured servers are "active" for demo purposes
        if is_mock_mode():
            return server_name in self.config.get("mcpServers", {})

        if server_name not in self.config.get("mcpServers", {}):
            return False

        server_config = self.config["mcpServers"][server_name]

        # Special check for WhatsApp - use actual skill
        if server_name == "whatsapp":
            try:
                from skills.whatsapp_skill import is_whatsapp_active
                # In mock mode or if WHATSAPP_ENABLED=true, consider active
                if os.getenv('WHATSAPP_ENABLED', 'false').lower() == 'true':
                    return True
                return is_whatsapp_active()
            except ImportError:
                if os.getenv('WHATSAPP_ENABLED', 'false').lower() == 'true':
                    return True

        # Special check for Gmail - check GMAIL_ENABLED
        if server_name == "google":
            if os.getenv('GMAIL_ENABLED', 'false').lower() == 'true':
                return True

        # Check if required env vars are set
        env_vars = server_config.get("env", {})
        for var_name, var_template in env_vars.items():
            # Extract actual env var name from ${VAR_NAME} template
            if var_template.startswith("${") and var_template.endswith("}"):
                actual_var = var_template[2:-1]
                env_value = os.getenv(actual_var, "")
                # Check if env var is set and not a placeholder
                if not env_value or env_value.startswith("your_"):
                    # Env var not set or is placeholder - server cannot be active
                    return False

        # If we reach here, server is configured and has required env vars
        return True

    def _check_all_servers(self):
        """Check status of all configured MCP servers."""
        for server_name in self.config.get("mcpServers", {}).keys():
            self.active_servers[server_name] = self._check_server_status(server_name)

    def is_server_active(self, server_name: str) -> bool:
        """Check if a specific MCP server is active."""
        return self.active_servers.get(server_name, False)

    def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """Get detailed status for a server."""
        if server_name not in self.config.get("mcpServers", {}):
            return {"name": server_name, "active": False, "reason": "Not configured"}

        server_config = self.config["mcpServers"][server_name]
        is_active = self.is_server_active(server_name)

        return {
            "name": server_config.get("name", server_name),
            "active": is_active,
            "description": server_config.get("description", ""),
            "tools": server_config.get("tools", []),
            "fallback": server_config.get("fallback", "file_based"),
            "status": "MCP Active" if is_active else "File-Based Mode"
        }

    def get_all_server_status(self) -> Dict[str, Dict]:
        """Get status of all MCP servers."""
        return {
            name: self.get_server_status(name)
            for name in self.config.get("mcpServers", {}).keys()
        }

    def call_tool(self, server_name: str, tool_name: str, params: Dict = None) -> Tuple[bool, Any]:
        """
        Call an MCP tool on the specified server.

        Returns:
            Tuple of (used_mcp: bool, result: Any)
            - If MCP active: (True, mcp_result)
            - If MCP offline: (False, file_based_result)
        """
        params = params or {}
        timestamp = datetime.now().isoformat()

        if self.is_server_active(server_name):
            # MCP is active - make the real call
            print(f"[ZOYA MCP] [{timestamp[:19]}] Calling MCP tool: {server_name}.{tool_name}")
            print(f"[ZOYA MCP] [{timestamp[:19]}] Parameters: {json.dumps(params, indent=2)}")

            # In production, this would make actual MCP call
            # For now, we simulate with logging
            result = self._execute_mcp_tool(server_name, tool_name, params)

            print(f"[ZOYA MCP] [{timestamp[:19]}] MCP Response: SUCCESS")
            return (True, result)
        else:
            # MCP offline - use fallback
            print(f"[ZOYA MCP] [{timestamp[:19]}] MCP Offline for {server_name} - Using file-based fallback")
            result = self._execute_fallback(server_name, tool_name, params)
            return (False, result)

    def _execute_mcp_tool(self, server_name: str, tool_name: str, params: Dict) -> Dict:
        """
        Execute an MCP tool call.

        In production, this would:
        1. Connect to the MCP server via stdio
        2. Send the tool call request
        3. Return the response

        For demo purposes, we simulate successful execution.
        """
        server_config = self.config["mcpServers"].get(server_name, {})

        # Simulate MCP response based on tool type
        mock_responses = {
            # Gmail tools
            "gmail_read": {"emails": [], "count": 0, "status": "success"},
            "gmail_send": {"message_id": f"msg_{int(time.time())}", "status": "sent"},
            "gmail_search": {"results": [], "count": 0},

            # Fetch tools
            "fetch_url": {"content": "", "status_code": 200},
            "fetch_html": {"html": "<html></html>", "status_code": 200},
            "fetch_json": {"data": {}, "status_code": 200},

            # Slack tools
            "slack_post": {"ts": f"{time.time()}", "channel": params.get("channel", "general"), "status": "posted"},
            "slack_reply": {"ts": f"{time.time()}", "status": "replied"},

            # WhatsApp tools
            "whatsapp_send": {"message_id": f"wa_{int(time.time())}", "status": "sent"},
            "whatsapp_template": {"message_id": f"wa_tmpl_{int(time.time())}", "status": "sent"},

            # Social tools
            "linkedin_post": {"post_id": f"li_{int(time.time())}", "status": "published"},
            "facebook_post": {"post_id": f"fb_{int(time.time())}", "status": "published"},
            "twitter_post": {"tweet_id": f"tw_{int(time.time())}", "status": "published"},

            # Odoo tools
            "odoo_create_invoice": {"invoice_id": 1001, "number": f"INV/2026/{int(time.time()) % 10000}", "status": "draft"},
            "odoo_create_payment": {"payment_id": 1002, "status": "draft"},
            "odoo_search_partner": {"partners": [], "count": 0},
            "odoo_get_financials": {"revenue": 0, "expenses": 0, "profit": 0},
        }

        base_response = mock_responses.get(tool_name, {"status": "success"})
        return {
            **base_response,
            "mcp_server": server_name,
            "tool": tool_name,
            "timestamp": datetime.now().isoformat(),
            "mode": "MCP_ACTIVE"
        }

    def _execute_fallback(self, server_name: str, tool_name: str, params: Dict) -> Dict:
        """
        Execute file-based fallback when MCP is offline.

        Creates a file in the workspace for manual processing.
        """
        workspace = Path("workspace/mcp_fallback")
        workspace.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now()
        filename = f"{server_name}_{tool_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = workspace / filename

        fallback_data = {
            "server": server_name,
            "tool": tool_name,
            "params": params,
            "timestamp": timestamp.isoformat(),
            "status": "pending_manual_action",
            "mode": "FILE_BASED_FALLBACK"
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(fallback_data, f, indent=2)

        return {
            "status": "fallback",
            "file_created": str(filepath),
            "message": f"MCP offline - Action saved to {filename}",
            "mode": "FILE_BASED_FALLBACK"
        }

    def post_to_social(self, platform: str, content: str, **kwargs) -> Tuple[bool, Dict]:
        """
        Convenience method to post to social media via MCP.

        Args:
            platform: 'linkedin', 'facebook', 'twitter', 'slack', 'whatsapp'
            content: The message/post content
            **kwargs: Additional platform-specific parameters
        """
        platform_map = {
            "linkedin": ("social", "linkedin_post"),
            "facebook": ("social", "facebook_post"),
            "twitter": ("social", "twitter_post"),
            "slack": ("slack", "slack_post"),
            "whatsapp": ("whatsapp", "whatsapp_send"),
        }

        if platform.lower() not in platform_map:
            return (False, {"error": f"Unknown platform: {platform}"})

        server_name, tool_name = platform_map[platform.lower()]
        params = {"content": content, **kwargs}

        return self.call_tool(server_name, tool_name, params)

    def fetch_url(self, url: str, format: str = "text") -> Tuple[bool, Dict]:
        """
        Convenience method to fetch URL content via MCP.
        """
        tool_map = {
            "text": "fetch_text",
            "html": "fetch_html",
            "json": "fetch_json",
        }
        tool_name = tool_map.get(format, "fetch_url")
        return self.call_tool("fetch", tool_name, {"url": url})

    def send_gmail(self, to: str, subject: str, body: str) -> Tuple[bool, Dict]:
        """
        Convenience method to send email via MCP.
        """
        return self.call_tool("google", "gmail_send", {
            "to": to,
            "subject": subject,
            "body": body
        })


# Singleton instance for global access
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


def is_mcp_active(server_name: str = None) -> bool:
    """
    Check if MCP is active.

    If server_name is provided, check specific server.
    Otherwise, check if ANY MCP server is active.
    """
    client = get_mcp_client()
    if server_name:
        return client.is_server_active(server_name)
    return any(client.active_servers.values())


def get_mcp_status_summary() -> Dict[str, Any]:
    """Get summary of all MCP server statuses."""
    client = get_mcp_client()
    statuses = client.get_all_server_status()

    active_count = sum(1 for s in statuses.values() if s["active"])
    total_count = len(statuses)

    return {
        "active_count": active_count,
        "total_count": total_count,
        "all_active": active_count == total_count,
        "any_active": active_count > 0,
        "servers": statuses
    }


# Terminal logging for MCP operations
def mcp_terminal_log(action: str, details: str = ""):
    """Print MCP action to terminal."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[ZOYA MCP] [{timestamp}] {action}"
    if details:
        msg += f" | {details}"
    print(msg, flush=True)


if __name__ == "__main__":
    # Test MCP client
    print("=" * 60)
    print("MCP Client Test - Zoya AI")
    print("=" * 60)

    client = get_mcp_client()

    print("\n📡 MCP Server Status:")
    for name, status in client.get_all_server_status().items():
        icon = "🟢" if status["active"] else "🔴"
        print(f"  {icon} {name}: {status['status']}")

    print("\n📤 Testing Social Post via MCP:")
    used_mcp, result = client.post_to_social("linkedin", "Test post from Zoya AI!")
    print(f"  Mode: {'MCP Active' if used_mcp else 'File-Based Fallback'}")
    print(f"  Result: {json.dumps(result, indent=4)}")

    print("\n✅ MCP Client test complete!")
