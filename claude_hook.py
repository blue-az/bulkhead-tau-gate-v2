#!/usr/bin/env python3
import sys
import json
import os
import subprocess

def main():
    try:
        # Resolve project directory dynamically
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("GEMINI_CWD") or "."
        project_dir = os.path.abspath(project_dir)
        
        # Add project_dir to sys.path to resolve modules correctly
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
            
        from policy_engine import PolicyEngine
        
        # 1. Read Payload from stdin
        payload_str = sys.stdin.read()
        if not payload_str:
            print(json.dumps({"decision": "allow"}))
            return
            
        payload = json.loads(payload_str)
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input", {})
        
        # 2. Policy Setup
        policy_path = os.path.join(project_dir, "configs/policy.hl")
        engine = PolicyEngine(policy_path)
        
        # 3. Tool Mapping & Veto Logic
        decision = {"decision": "allow"}
        
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            allowed, msg = engine.check_action("run_command", command)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}
        
        elif tool_name == "Write":
            path = tool_input.get("file_path", "")
            content = tool_input.get("content", "")
            allowed, msg = engine.check_action("write_file", path)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}
            else:
                # Post-write validation (in-memory simulation)
                # Ensure .json extension for structured validation
                temp_file = os.path.join(project_dir, f".claude_write_temp_{os.path.basename(path)}.json")
                try:
                    with open(temp_file, "w") as f:
                        f.write(content)
                    valid, val_msg = run_validators(engine, temp_file, project_dir)
                    if not valid:
                        decision = {"decision": "deny", "reason": f"Validator Failure: {val_msg}"}
                finally:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

        elif tool_name == "Edit":
            path = tool_input.get("file_path", "")
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
            
            allowed, msg = engine.check_action("replace", path)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}
            else:
                # Predictive validation for Edit
                full_path = os.path.join(project_dir, path)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r") as f:
                            original_content = f.read()
                        
                        if old_string in original_content:
                            simulated_content = original_content.replace(old_string, new_string, 1)
                        else:
                            simulated_content = original_content
                        
                        temp_file = os.path.join(project_dir, f".claude_edit_temp_{os.path.basename(path)}.json")
                        try:
                            with open(temp_file, "w") as f:
                                f.write(simulated_content)
                            valid, val_msg = run_validators(engine, temp_file, project_dir)
                            if not valid:
                                decision = {"decision": "deny", "reason": f"Validator Failure on Edit: {val_msg}"}
                        finally:
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                    except Exception as edit_err:
                        # Fail-closed on simulation error
                        sys.stderr.write(f"Edit simulation error: {str(edit_err)}\n")
                        sys.exit(2)
        
        elif tool_name == "MultiEdit":
            path = tool_input.get("file_path", "")
            allowed, msg = engine.check_action("replace", path)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}

        elif tool_name == "NotebookEdit":
            path = tool_input.get("notebook_path", "")
            allowed, msg = engine.check_action("write_file", path)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}

        elif tool_name == "Read":
            path = tool_input.get("file_path", "")
            allowed, msg = engine.check_action("read_file", path)
            if not allowed:
                decision = {"decision": "deny", "reason": msg}

        print(json.dumps(decision))

    except Exception as e:
        sys.stderr.write(f"FATAL HOOK ERROR: {str(e)}\n")
        sys.exit(2) # Fail closed

def run_validators(engine, target_path, project_dir):
    validators = engine.get_values("post_write_validators")
    for validator in validators:
        # Resolve validator path relative to project_dir
        val_path = os.path.join(project_dir, validator)
        if not os.path.exists(val_path):
            sys.stderr.write(f"WARNING: configured validator not found, not run: {validator}\n")
            continue
        try:
            # Explicitly use sys.executable for .py files
            cmd = [sys.executable, val_path, target_path] if val_path.endswith(".py") else [val_path, target_path]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            return False, f"{e.stderr or e.stdout}".strip()
    return True, "OK"

if __name__ == "__main__":
    main()
