import json
import re
from typing import Dict, Any, Optional, List, Tuple

from app.core.logger import logger
from app.tools.permissions import PermissionLevel, get_permission_manager
from app.tools.system_tools import ALL_TOOLS

JSON_BLOCK_REGEX = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class ToolRouter:
    """Dispatches tool calls, checks permissions, and manages confirmation requests."""

    def __init__(self):
        self._permission_mgr = get_permission_manager()
        self._tools = ALL_TOOLS

    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("parameters", {}),
                "permission": t["permission"].value,
            }
            for t in self._tools.values()
        ]

    def extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts tool JSON call from LLM response text if present."""
        # 1. Match code blocks
        match = JSON_BLOCK_REGEX.search(text)
        if match:
            candidate = match.group(1)
            try:
                data = json.loads(candidate)
                if "tool" in data:
                    return data
            except Exception:
                pass

        # 2. Try raw JSON string
        try:
            trimmed = text.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                data = json.loads(trimmed)
                if "tool" in data:
                    return data
        except Exception:
            pass

        return None

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        bypass_confirmation: bool = False,
    ) -> Dict[str, Any]:
        """Validates tool, checks security, checks confirmation, and executes handler."""
        if tool_name not in self._tools:
            logger.warning(f"Unknown tool requested: {tool_name}")
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' is not recognized or permitted.",
            }

        tool_spec = self._tools[tool_name]
        permission = tool_spec["permission"]

        # Check for blocked patterns in arguments
        args_str = json.dumps(arguments)
        is_blocked, reason = self._permission_mgr.is_blocked(args_str)
        if is_blocked:
            return {
                "status": "blocked",
                "message": f"Execution halted: {reason}",
            }

        # Check for confirmation requirement
        if permission == PermissionLevel.CONFIRM and not bypass_confirmation:
            desc = f"Request to execute '{tool_name}' with parameters {arguments}"
            conf_id = self._permission_mgr.create_confirmation_request(tool_name, arguments, desc)
            return {
                "status": "pending_confirmation",
                "confirmation_id": conf_id,
                "tool": tool_name,
                "arguments": arguments,
                "message": f"Action '{tool_name}' requires explicit user confirmation. Request ID: {conf_id}",
            }

        # Execute safe or approved tool
        try:
            logger.info(f"Executing tool '{tool_name}' with args {arguments}")
            handler = tool_spec["handler"]
            result = handler(**arguments)
            logger.info(f"Tool '{tool_name}' execution completed: {result.get('status', 'ok')}")
            return {
                "status": "success",
                "tool": tool_name,
                "result": result,
            }
        except Exception as e:
            logger.exception(f"Error executing tool '{tool_name}': {e}")
            return {
                "status": "error",
                "tool": tool_name,
                "message": f"Tool execution failed: {str(e)}",
            }

    def execute_confirmed_request(self, confirmation_id: str) -> Dict[str, Any]:
        """Executes a previously pending confirmation request that was approved."""
        pending = self._permission_mgr.get_pending_requests()
        req = pending.get(confirmation_id)
        if not req:
            return {"status": "error", "message": "Confirmation request not found or expired."}

        self._permission_mgr.resolve_request(confirmation_id, approved=True)
        return self.execute_tool(req["tool_name"], req["arguments"], bypass_confirmation=True)


_router_instance: Optional[ToolRouter] = None


def get_tool_router() -> ToolRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ToolRouter()
    return _router_instance
