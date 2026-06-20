# Bulkhead &tau; Gate (`bulkhead-tau-gate`)

The runtime policy-enforcement gate (the **enforce** layer) of the Bulkhead &tau; ecosystem.

This repository completes the manual trilogy of Bulkhead &tau;:
1. **Contract** (`pbc-spec`): Defines the charter and acceptable operational bounds.
2. **Ledger** (`operator-control-plane`): The audit log of state changes.
3. **Enforce** (`bulkhead-tau-gate`): Intercepts agent tool actions at runtime, vetoing unsafe inputs before execution and validating workspace consistency after writes.

> [!NOTE]
> **Honest Positioning:** This project is a working, prototype-grade runtime policy-enforcement gate targeting LLM agent integrations (such as the Claude Code PreToolUse hooks). It is *not* a Hyperlambda or Magic web deployment; it uses a Hyperlambda-inspired syntax statically for declarative policy definition (`configs/policy.hl`).

---

## Architecture: The Pre-Execution Firewall

The gate operates as an interception sandwich:

1. **Pre-Execution Hook:** The LLM's proposed action (e.g. command execution, file read/write) is sent to `claude_hook.py` or `pre_tool_hook.py` via stdin.
2. **Policy Evaluation:** The hook invokes `policy_engine.py` to evaluate the action against `configs/policy.hl`.
3. **Predictive Simulation & Post-Write Validation:** If a file write or edit is proposed, the hook simulates the write in memory and runs `validate_payload.py` to verify schema compliance *before* allowing the write to touch the actual workspace.
4. **Execution / Veto:** The hook outputs a JSON decision (`{"decision": "allow"}` or `{"decision": "deny", "reason": "..."}`) to the agent's harness.

---

## File Layout

```
bulkhead-tau-gate/
├── README.md                  # Project overview and honest framing
├── harness_specification.md   # Conceptual architecture and detailed specs
├── pyproject.toml             # Pytest and module path configurations
├── requirements.txt           # Minimal standard-library-first dependencies
├── policy_engine.py           # Core policy evaluator parsing .hl config files
├── harness.py                 # Legacy Gemini CLI harness [Legacy fallback]
├── claude_hook.py             # Active PreToolUse hook for Claude Code
├── pre_tool_hook.py           # Active PreToolUse hook for general agentic tools
├── validate_payload.py        # Post-write structured validator (JSON/status schema)
├── verify_tree.py             # Inverse Magic tree evaluator (determinstic sensor peaks)
├── configs/
│   ├── policy.hl              # Declarative whitelists & blacklist rules
│   ├── bulkhead_audit.hl      # Example veto policy for sensor drift
│   └── governed_operation.hl  # Example charter-to-logbook sandwich flow
└── tests/
    ├── test_policy_engine.py  # Tests parsing, whitelists, and veto rules
    └── test_harness.py        # Tests shadow/live execution and validation rollback
```

---

## Verification & Execution

### 1. Running the Test Suite
Ensure you have `pytest` installed, and run it from the root of the repository:

```bash
pip install -r requirements.txt
pytest
```

All tests should pass successfully.

### 2. Manual Hook Demonstration (Veto vs Allow)
To verify the policy gate manually, you can simulate hook execution by piping JSON payloads into `claude_hook.py`.

#### Case A: Vetoing a Dangerous Command
When an agent attempts to run a forbidden command (e.g., `rm -rf /`):

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}' | python3 claude_hook.py
```

Expected output (denied by policy):
```json
{"decision": "deny", "reason": "VETO: Command 'rm -rf /' matches deny rule 'rm -rf'."}
```

#### Case B: Allowing a Whitelisted Command
When an agent attempts to run a whitelisted command (e.g., `git status`):

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "git status"}}' | python3 claude_hook.py
```

Expected output (allowed by policy):
```json
{"decision": "allow"}
```

#### Case C: Vetoing a Restricted Path Write
When an agent attempts to modify restricted files (e.g., `.git/config`):

```bash
echo '{"tool_name": "Write", "tool_input": {"file_path": ".git/config", "content": "evil"}}' | python3 claude_hook.py
```

Expected output (denied by write permissions):
```json
{"decision": "deny", "reason": "VETO: Path '.git/config' matches deny rule '.git/'."}
```
