import pytest
import os
import shutil
from harness import GeminiHarness

@pytest.fixture
def shadow_harness():
    return GeminiHarness(mode="shadow")

@pytest.fixture
def live_harness():
    return GeminiHarness(mode="live")

def test_binary_path_exists(shadow_harness):
    """Verify the harness finds the gemini binary if present."""
    if shadow_harness.gemini_path is not None:
        assert os.path.exists(shadow_harness.gemini_path)

def test_shadow_mode_no_execution(shadow_harness):
    """Prove that shadow mode intercepts but does not execute."""
    success, msg = shadow_harness.run_action("run_command", "git status")
    assert success
    assert "Shadow mode" in msg

def test_live_command_execution(live_harness):
    """Verify live command execution for whitelisted commands."""
    success, output = live_harness.run_action("run_command", "git status")
    assert success
    assert "On branch" in output or "Not a git repository" in output

def test_live_command_veto(live_harness):
    """Verify live command veto for denied commands."""
    success, msg = live_harness.run_action("run_command", "rm -rf /")
    assert not success
    assert "VETO" in msg

def test_live_write_success(live_harness):
    """Verify successful write and validation."""
    test_path = "signals/test_ok.json"
    content = '{"status": "ok"}'
    
    success, msg = live_harness.run_action("write_file", test_path, content=content)
    assert success
    assert os.path.exists(test_path)
    with open(test_path, 'r') as f:
        assert f.read() == content
    
    # Cleanup
    os.remove(test_path)

def test_live_write_rollback(live_harness):
    """Verify write rollback on validation failure."""
    test_path = "signals/test_fail.json"
    content = '{"status": "FAIL"}' # This triggers the validator failure
    
    # Ensure file doesn't exist initially
    if os.path.exists(test_path):
        os.remove(test_path)
    
    success, msg = live_harness.run_action("write_file", test_path, content=content)
    assert not success
    assert "Validation failed" in msg
    assert not os.path.exists(test_path)

def test_live_write_rollback_existing(live_harness):
    """Verify rollback restores previous version of existing file."""
    test_path = "signals/test_existing.json"
    original_content = "original"
    
    # Setup existing file
    os.makedirs(os.path.dirname(test_path), exist_ok=True)
    with open(test_path, 'w') as f:
        f.write(original_content)
    
    fail_content = "FAIL CONTENT"
    success, msg = live_harness.run_action("write_file", test_path, content=fail_content)
    
    assert not success
    assert "Validation failed" in msg
    
    # Check that original content is restored
    with open(test_path, 'r') as f:
        assert f.read() == original_content
    
    # Cleanup
    os.remove(test_path)

def test_structured_validation_malformed_json(live_harness):
    """Verify malformed JSON payload is rejected structurally."""
    test_path = "signals/test_malformed.json"
    bad_content = "{invalid json"
    success, msg = live_harness.run_action("write_file", test_path, content=bad_content)
    assert not success
    assert "Validation failed" in msg
    assert "Malformed JSON" in msg
    assert not os.path.exists(test_path)

def test_structured_validation_invalid_status_type(live_harness):
    """Verify that a status key with a non-string value is rejected."""
    test_path = "signals/test_type.json"
    bad_content = '{"status": 123}'
    success, msg = live_harness.run_action("write_file", test_path, content=bad_content)
    assert not success
    assert "Validation failed" in msg
    assert "status' must be a string" in msg
    assert not os.path.exists(test_path)

def test_structured_validation_forbidden_key(live_harness):
    """Verify that hallucinated/forbidden configuration keys are rejected."""
    test_path = "signals/test_forbidden.json"
    bad_content = '{"status": "ok", "input_tokens": 500}'
    success, msg = live_harness.run_action("write_file", test_path, content=bad_content)
    assert not success
    assert "Validation failed" in msg
    assert "forbidden configuration key" in msg
    assert not os.path.exists(test_path)

def test_structured_validation_non_dict_root(live_harness):
    """Verify that root JSON element must be an object/dictionary."""
    test_path = "signals/test_array.json"
    bad_content = '["status", "ok"]'
    success, msg = live_harness.run_action("write_file", test_path, content=bad_content)
    assert not success
    assert "Validation failed" in msg
    assert "must be a JSON object" in msg
    assert not os.path.exists(test_path)
