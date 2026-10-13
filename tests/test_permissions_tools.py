import pytest
from app.tools.permissions import get_permission_manager, PermissionLevel
from app.tools.router import get_tool_router

def test_permissions_blocked_patterns():
    pm = get_permission_manager()
    is_blocked, reason = pm.is_blocked("invoke-mimikatz")
    assert is_blocked is True
    assert "Security Violation" in reason

    is_blocked, _ = pm.is_blocked("calc.exe")
    assert is_blocked is False

def test_tool_router_safe_execution():
    router = get_tool_router()
    # Test time tool
    res = router.execute_tool("get_time", {})
    assert res["status"] == "success"
    assert "current_time" in res["result"]

    # Test system info
    res = router.execute_tool("get_system_info", {})
    assert res["status"] == "success"
    assert "cpu_cores" in res["result"]

def test_tool_router_confirm_execution():
    router = get_tool_router()
    # Close program requires confirmation
    res = router.execute_tool("close_program", {"process_name_or_pid": "calc.exe"})
    assert res["status"] == "pending_confirmation"
    assert "confirmation_id" in res
    cid = res["confirmation_id"]

    # Test resolving request
    pm = get_permission_manager()
    resolved = pm.resolve_request(cid, approved=False)
    assert resolved["status"] == "rejected"
