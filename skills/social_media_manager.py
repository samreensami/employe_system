"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SOCIAL MEDIA MANAGER - ZOYA AI                            ║
║                     MCP-Powered Multi-Platform Publishing                    ║
║                                                                              ║
║  Phase II Requirement: All social interactions via MCP Servers               ║
║  Platforms: LinkedIn, Twitter (X), Instagram, Facebook                       ║
║                                                                              ║
║  Project: samreensami/hack2-phase2                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logger = logging.getLogger(__name__)

# Import MCP client
try:
    from skills.mcp_client import get_mcp_client, is_mcp_active, mcp_terminal_log
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    def is_mcp_active(server=None): return False
    def mcp_terminal_log(action, details=""): pass
    def get_mcp_client(): return None


def load_env():
    """Load environment variables from .env file."""
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()


class SocialMediaManager:
    """
    MCP-Powered Social Media Manager for Zoya AI.

    Handles publishing to multiple platforms:
    - LinkedIn (Professional updates)
    - Twitter/X (Short updates)
    - Instagram (Visual content)
    - Facebook (General posts)

    Uses MCP Servers when available, falls back to file-based mode.
    """

    # Platform configurations
    PLATFORMS = {
        "linkedin": {
            "name": "LinkedIn",
            "mcp_server": "social",
            "mcp_tool": "linkedin_post",
            "max_chars": 3000,
            "icon": "💼",
            "api_endpoint": "https://api.linkedin.com/v2/ugcPosts"
        },
        "twitter": {
            "name": "Twitter (X)",
            "mcp_server": "social",
            "mcp_tool": "twitter_post",
            "max_chars": 280,
            "icon": "🐦",
            "api_endpoint": "https://api.twitter.com/2/tweets"
        },
        "instagram": {
            "name": "Instagram",
            "mcp_server": "social",
            "mcp_tool": "instagram_post",
            "max_chars": 2200,
            "icon": "📸",
            "api_endpoint": "https://graph.instagram.com/me/media"
        },
        "facebook": {
            "name": "Facebook",
            "mcp_server": "social",
            "mcp_tool": "facebook_post",
            "max_chars": 63206,
            "icon": "👥",
            "api_endpoint": "https://graph.facebook.com/v18.0/me/feed"
        }
    }

    def __init__(self):
        self.mcp_client = get_mcp_client() if MCP_AVAILABLE else None
        self.audit_log_path = Path("logs/audit_log.json")
        self.execution_log_path = Path("logs/social_execution.json")

        # Check MCP status for social server
        self.mcp_active = is_mcp_active("social") if MCP_AVAILABLE else False

        # Initialize execution log
        self.execution_log_path.parent.mkdir(parents=True, exist_ok=True)

        self._log_init()

    def _log_init(self):
        """Log initialization status."""
        mode = "MCP Active" if self.mcp_active else "File-Based Mode"
        print(f"\n[ZOYA SOCIAL] Social Media Manager initialized")
        print(f"[ZOYA SOCIAL] Mode: {mode}")
        print(f"[ZOYA SOCIAL] Platforms: LinkedIn, Twitter(X), Instagram, Facebook")
        mcp_terminal_log("SOCIAL_INIT", f"Mode={mode} | Platforms=4")

    def get_platform_status(self, platform: str) -> Dict[str, Any]:
        """Get MCP status for a specific platform."""
        if platform not in self.PLATFORMS:
            return {"active": False, "error": "Unknown platform"}

        config = self.PLATFORMS[platform]
        mcp_active = is_mcp_active(config["mcp_server"]) if MCP_AVAILABLE else False

        return {
            "platform": platform,
            "name": config["name"],
            "icon": config["icon"],
            "mcp_active": mcp_active,
            "mcp_server": config["mcp_server"],
            "mcp_tool": config["mcp_tool"],
            "status": "🟢 MCP Active" if mcp_active else "🔴 MCP Offline"
        }

    def get_all_platform_status(self) -> Dict[str, Dict]:
        """Get MCP status for all platforms."""
        return {p: self.get_platform_status(p) for p in self.PLATFORMS}

    def _truncate_content(self, content: str, platform: str) -> str:
        """Truncate content to platform's max character limit."""
        max_chars = self.PLATFORMS[platform]["max_chars"]
        if len(content) <= max_chars:
            return content
        return content[:max_chars-3] + "..."

    def _build_payload(self, platform: str, content: str, **kwargs) -> Dict:
        """Build API payload for a platform."""
        config = self.PLATFORMS[platform]
        timestamp = datetime.now().isoformat()

        base_payload = {
            "platform": platform,
            "platform_name": config["name"],
            "content": self._truncate_content(content, platform),
            "timestamp": timestamp,
            "source": "Zoya_AI_Employee",
            "mcp_tool": config["mcp_tool"],
            "api_endpoint": config["api_endpoint"]
        }

        # Platform-specific fields
        if platform == "linkedin":
            base_payload["visibility"] = kwargs.get("visibility", "PUBLIC")
            base_payload["author"] = "urn:li:person:USER_ID"
        elif platform == "twitter":
            base_payload["reply_settings"] = kwargs.get("reply_settings", "everyone")
        elif platform == "instagram":
            base_payload["media_type"] = kwargs.get("media_type", "TEXT")
            base_payload["caption"] = base_payload["content"]
        elif platform == "facebook":
            base_payload["privacy"] = kwargs.get("privacy", "EVERYONE")

        return base_payload

    def _log_to_audit(self, action: str, status: str, details: Dict):
        """Log action to audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action,
            "actor": "Zoya_AI_Social",
            "status": status,
            "details": details
        }

        # Load existing logs
        logs = []
        if self.audit_log_path.exists():
            try:
                with open(self.audit_log_path) as f:
                    logs = json.load(f)
            except:
                logs = []

        logs.append(entry)

        with open(self.audit_log_path, 'w') as f:
            json.dump(logs[-100:], f, indent=2)

    def _log_execution(self, platform: str, status: str, result: Dict):
        """Log execution result for UI display."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "platform_name": self.PLATFORMS[platform]["name"],
            "icon": self.PLATFORMS[platform]["icon"],
            "status": status,
            "mcp_used": result.get("mcp_used", False),
            "post_id": result.get("post_id", "N/A"),
            "message": f"Post published via MCP Tool: {self.PLATFORMS[platform]['name']}" if result.get("mcp_used") else f"Post queued (File-Based): {self.PLATFORMS[platform]['name']}"
        }

        # Load existing execution log
        logs = []
        if self.execution_log_path.exists():
            try:
                with open(self.execution_log_path) as f:
                    logs = json.load(f)
            except:
                logs = []

        logs.append(entry)

        with open(self.execution_log_path, 'w') as f:
            json.dump(logs[-50:], f, indent=2)

        return entry

    def post_to_platform(self, platform: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Post content to a specific platform via MCP.

        Args:
            platform: Platform name (linkedin, twitter, instagram, facebook)
            content: Post content
            **kwargs: Platform-specific options

        Returns:
            Dict with status, mcp_used, and result details
        """
        if platform not in self.PLATFORMS:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        config = self.PLATFORMS[platform]
        payload = self._build_payload(platform, content, **kwargs)

        print(f"\n{'='*60}")
        print(f"[ZOYA SOCIAL] Publishing to {config['name']} {config['icon']}")
        print(f"{'='*60}")

        # Try MCP first
        if self.mcp_active and self.mcp_client:
            print(f"[ZOYA MCP] Calling MCP tool: {config['mcp_server']}.{config['mcp_tool']}")
            mcp_terminal_log("MCP_CALL", f"Calling MCP tool to post on {config['name']}...")

            try:
                used_mcp, mcp_result = self.mcp_client.call_tool(
                    config["mcp_server"],
                    config["mcp_tool"],
                    {"content": content, **kwargs}
                )

                if used_mcp:
                    post_id = mcp_result.get("post_id", f"{platform}_{int(datetime.now().timestamp())}")

                    print(f"[ZOYA MCP] ✓ MCP Response: SUCCESS")
                    print(f"[ZOYA MCP] Post ID: {post_id}")
                    print(f"[ZOYA MCP] Post published via MCP Tool: {config['name']}")
                    print(f"{'='*60}\n")

                    mcp_terminal_log("MCP_SUCCESS", f"Post published via MCP Tool: {config['name']} | post_id={post_id}")

                    # Log to audit
                    self._log_to_audit(
                        f"SOCIAL_MCP_{platform.upper()}",
                        "MCP_SUCCESS",
                        {**payload, "post_id": post_id, "mcp_result": mcp_result}
                    )

                    # Log execution for UI
                    exec_log = self._log_execution(platform, "MCP_SUCCESS", {
                        "mcp_used": True,
                        "post_id": post_id
                    })

                    return {
                        "success": True,
                        "mcp_used": True,
                        "platform": config["name"],
                        "post_id": post_id,
                        "message": f"Post published via MCP Tool: {config['name']}",
                        "execution_log": exec_log
                    }
            except Exception as e:
                logger.error(f"MCP call failed: {e}")
                print(f"[ZOYA MCP] MCP call failed, falling back to file-based mode")

        # Fallback to file-based mode
        print(f"[ZOYA SOCIAL] MCP Offline - Using file-based mode")
        print(f"[ZOYA SOCIAL] Saving post to fallback file...")
        mcp_terminal_log("FILE_BASED", f"MCP offline - saving {config['name']} post to file")

        # Save to fallback file
        fallback_dir = Path("workspace/mcp_fallback/social")
        fallback_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_file = fallback_dir / f"{platform}_{timestamp}.json"

        with open(fallback_file, 'w') as f:
            json.dump(payload, f, indent=2)

        print(f"[ZOYA SOCIAL] ✓ Saved to: {fallback_file}")
        print(f"[ZOYA SOCIAL] Post queued (File-Based): {config['name']}")
        print(f"{'='*60}\n")

        # Log to audit
        self._log_to_audit(
            f"SOCIAL_FILE_{platform.upper()}",
            "FILE_BASED_SUCCESS",
            {**payload, "fallback_file": str(fallback_file)}
        )

        # Log execution for UI
        exec_log = self._log_execution(platform, "FILE_BASED_SUCCESS", {
            "mcp_used": False,
            "fallback_file": str(fallback_file)
        })

        return {
            "success": True,
            "mcp_used": False,
            "platform": config["name"],
            "fallback_file": str(fallback_file),
            "message": f"Post queued (File-Based): {config['name']}",
            "execution_log": exec_log
        }

    def broadcast_to_all(self, content: str, platforms: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Broadcast content to multiple platforms via MCP.

        Args:
            content: Post content
            platforms: List of platforms (default: all)
            **kwargs: Platform-specific options

        Returns:
            Dict with results for each platform
        """
        if platforms is None:
            platforms = list(self.PLATFORMS.keys())

        print(f"\n{'='*60}")
        print(f"[ZOYA SOCIAL] 📡 BROADCASTING TO {len(platforms)} PLATFORMS")
        print(f"{'='*60}")
        mcp_terminal_log("BROADCAST_START", f"Broadcasting to {len(platforms)} platforms")

        results = {}
        success_count = 0
        mcp_count = 0

        for platform in platforms:
            if platform in self.PLATFORMS:
                result = self.post_to_platform(platform, content, **kwargs)
                results[platform] = result

                if result.get("success"):
                    success_count += 1
                if result.get("mcp_used"):
                    mcp_count += 1

        print(f"\n{'='*60}")
        print(f"[ZOYA SOCIAL] 📊 BROADCAST COMPLETE")
        print(f"[ZOYA SOCIAL] Success: {success_count}/{len(platforms)}")
        print(f"[ZOYA SOCIAL] MCP Used: {mcp_count}/{len(platforms)}")
        print(f"{'='*60}\n")

        mcp_terminal_log("BROADCAST_COMPLETE", f"Success={success_count}/{len(platforms)} | MCP={mcp_count}/{len(platforms)}")

        return {
            "success": success_count == len(platforms),
            "total": len(platforms),
            "success_count": success_count,
            "mcp_count": mcp_count,
            "platforms": results
        }

    def get_execution_log(self, limit: int = 10) -> List[Dict]:
        """Get recent execution log entries for UI display."""
        if not self.execution_log_path.exists():
            return []

        try:
            with open(self.execution_log_path) as f:
                logs = json.load(f)
            return logs[-limit:]
        except:
            return []


# Convenience functions for direct platform posting
def post_to_linkedin(content: str, **kwargs) -> Dict:
    """Quick post to LinkedIn via MCP."""
    manager = SocialMediaManager()
    return manager.post_to_platform("linkedin", content, **kwargs)


def post_to_twitter(content: str, **kwargs) -> Dict:
    """Quick post to Twitter/X via MCP."""
    manager = SocialMediaManager()
    return manager.post_to_platform("twitter", content, **kwargs)


def post_to_instagram(content: str, **kwargs) -> Dict:
    """Quick post to Instagram via MCP."""
    manager = SocialMediaManager()
    return manager.post_to_platform("instagram", content, **kwargs)


def post_to_facebook(content: str, **kwargs) -> Dict:
    """Quick post to Facebook via MCP."""
    manager = SocialMediaManager()
    return manager.post_to_platform("facebook", content, **kwargs)


def broadcast_post(content: str, platforms: List[str] = None) -> Dict:
    """Broadcast to multiple platforms via MCP."""
    manager = SocialMediaManager()
    return manager.broadcast_to_all(content, platforms)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Social Media Manager - MCP Test")
    print("="*60)

    manager = SocialMediaManager()

    # Show platform status
    print("\n📊 Platform Status:")
    for platform, status in manager.get_all_platform_status().items():
        print(f"  {status['icon']} {status['name']}: {status['status']}")

    # Test broadcast
    print("\n📡 Testing Broadcast...")
    test_content = """🚀 Exciting Update from Zoya AI!

We're leveraging MCP (Model Context Protocol) for seamless social media integration.

#AI #Automation #MCP #ZoyaAI"""

    result = manager.broadcast_to_all(test_content)

    print(f"\n✅ Broadcast Test Complete!")
    print(f"   Platforms: {result['total']}")
    print(f"   Success: {result['success_count']}")
    print(f"   MCP Used: {result['mcp_count']}")
