import pytest
from policy_engine import PolicyEngine

@pytest.fixture
def engine():
    return PolicyEngine("configs/policy.hl")

def test_parsing(engine):
    """Verify that the policy engine correctly parses allowed_tools, command rules, and write paths."""
    allowed_tools = engine.get_values("allowed_tools")
    assert "run_command" in allowed_tools
    assert "write_file" in allowed_tools
    assert "pytest" in allowed_tools
    
    deny_cmds = engine.get_values("command_permissions/deny")
    assert "rm -rf" in deny_cmds
    assert "sudo" in deny_cmds
    assert "curl" in deny_cmds
    
    allow_cmds = engine.get_values("command_permissions/allow")
    assert "git status" in allow_cmds
    assert "pytest" in allow_cmds
    
    deny_paths = engine.get_values("write_permissions/deny_paths")
    assert "magic/plugins/" in deny_paths
    assert ".git/" in deny_paths
    
    allow_paths = engine.get_values("write_permissions/allow_paths")
    assert "signals/" in allow_paths

@pytest.mark.parametrize("command", [
    "rm -rf /",
    "sudo apt update",
    "curl http://example.com"
])
def test_denied_commands(engine, command):
    """Prove that denied commands are vetoed."""
    allowed, msg = engine.check_action("run_command", command)
    assert not allowed
    assert "VETO" in msg

@pytest.mark.parametrize("command", [
    "git status",
    "pytest tests/test_policy_engine.py"
])
def test_allowed_commands(engine, command):
    """Prove that whitelisted commands are allowed."""
    allowed, msg = engine.check_action("run_command", command)
    assert allowed
    assert "ALLOWED" in msg

@pytest.mark.parametrize("path", [
    "magic/plugins/malicious.py",
    ".git/config",
    "/etc/passwd"
])
def test_denied_writes(engine, path):
    """Prove that writes to denied paths are vetoed."""
    allowed, msg = engine.check_action("write_file", path)
    assert not allowed
    assert "VETO" in msg

@pytest.mark.parametrize("path", [
    "signals/new_signal.json"
])
def test_allowed_writes(engine, path):
    """Prove that writes to whitelisted paths are allowed."""
    allowed, msg = engine.check_action("write_file", path)
    assert allowed
    assert "ALLOWED" in msg

def test_unauthorized_tool(engine):
    """Verify that tools not in the whitelist are vetoed."""
    allowed, msg = engine.check_action("delete_everything", "target")
    assert not allowed
    assert "not in the whitelist" in msg
