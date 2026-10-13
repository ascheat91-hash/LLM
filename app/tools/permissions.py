import uuid
import time
import re
from enum import Enum
from typing import Dict, Any, Optional, Tuple

from app.core.logger import logger

class PermissionLevel(str, Enum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    BLOCKED = "BLOCKED"


# Malicious or dangerous patterns blocked permanently
BLOCKED_PATTERNS = [
    re.compile(r"(mimikatz|invoke-mimikatz)", re.IGNORECASE),
    re.compile(r"(samdump|pwdump|secretsdump)", re.IGNORECASE),
    re.compile(r"reg(\.exe)?\s+(delete|add)\s+.*\\(sam|system|security)", re.IGNORECASE),
    re.compile(r"(format\s+[a-z]:)", re.IGNORECASE),
    re.compile(r"rmdir\s+.*(/s|/q)\s+c:\\windows", re.IGNORECASE),
    re.compile(r"remove-item\s+.*c:\\windows", re.IGNORECASE),
    re.compile(r"vssadmin\s+delete\s+shadows", re.IGNORECASE),
    re.compile(r"(powershell|cmd).*(downloadstring|invoke-webrequest).*\.exe", re.IGNORECASE),
    re.compile(r"net\s+user\s+.*\/add", re.IGNORECASE),
]


class PermissionManager:
    """Enforces safety rules and tracks user confirmation requests."""

    def __init__(self):
        # Pending confirmations: {confirmation_id: {tool_name, arguments, status, created_at, prompt}}
        self._pending: Dict[str, Dict[str, Any]] = {}

    def is_blocked(self, command_or_arg: str) -> Tuple[bool, Optional[str]]:
        """Check if any argument or command contains blocked patterns."""
        for pattern in BLOCKED_PATTERNS:
            if pattern.search(command_or_arg):
                reason = f"Security Violation: Pattern '{pattern.pattern}' is strictly blocked."
                logger.warning(f"BLOCKED ACTION DETECTED: {command_or_arg} -> {reason}")
                return True, reason
        return False, None

    def create_confirmation_request(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        description: str,
    ) -> str:
        confirmation_id = str(uuid.uuid4())[:8]
        self._pending[confirmation_id] = {
            "id": confirmation_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "description": description,
            "status": "pending",
            "created_at": time.time(),
        }
        logger.info(f"Created confirmation request [{confirmation_id}] for tool '{tool_name}': {description}")
        return confirmation_id

    def get_pending_requests(self) -> Dict[str, Dict[str, Any]]:
        # Clean expired (older than 10 mins)
        now = time.time()
        expired = [cid for cid, v in self._pending.items() if now - v["created_at"] > 600]
        for cid in expired:
            del self._pending[cid]
        return {k: v for k, v in self._pending.items() if v["status"] == "pending"}

    def resolve_request(self, confirmation_id: str, approved: bool) -> Optional[Dict[str, Any]]:
        if confirmation_id not in self._pending:
            return None
        req = self._pending[confirmation_id]
        req["status"] = "approved" if approved else "rejected"
        req["resolved_at"] = time.time()
        logger.info(f"Confirmation request [{confirmation_id}] was {'APPROVED' if approved else 'REJECTED'}")
        return req


_permission_manager_instance: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    global _permission_manager_instance
    if _permission_manager_instance is None:
        _permission_manager_instance = PermissionManager()
    return _permission_manager_instance
