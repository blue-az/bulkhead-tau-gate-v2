import sys
import json
import os
from policy_engine import PolicyEngine

def main():
    try:
        # Read the payload from stdin
        payload_str = sys.stdin.read()
        if not payload_str:
            print(json.dumps({"decision": "allow"}))
            return
            
        payload = json.loads(payload_str)
        
        # Extract tool info
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input", {})
        
        # PolicyEngine expects (tool, target)
        # We need to map tool_name + tool_input to our policy
        # Supported tools in policy_engine.py: run_command, write_file, replace, write_to_file
        
        target = ""
        if tool_name == "run_shell_command":
            # For run_shell_command, target is the command string
            target = tool_input.get("command", "")
            mapped_tool = "run_command"
        elif tool_name in ["write_file", "replace", "write_to_file"]:
            # For file tools, target is the file_path
            target = tool_input.get("file_path", "")
            mapped_tool = tool_name
        else:
            # Default to allow for unknown tools
            print(json.dumps({"decision": "allow"}))
            return

        # Initialize PolicyEngine
        policy_path = os.path.join(os.environ.get("GEMINI_CWD", "."), "configs/policy.hl")
        if not os.path.exists(policy_path):
             # Fallback if env var not set correctly
             policy_path = "configs/policy.hl"

        engine = PolicyEngine(policy_path)
        allowed, msg = engine.check_action(mapped_tool, target)
        
        if not allowed:
            print(json.dumps({
                "decision": "deny",
                "reason": msg
            }))
        else:
            print(json.dumps({
                "decision": "allow"
            }))

    except Exception as e:
        # On error, we fail safe by continuing but logging the error to stderr
        sys.stderr.write(f"Hook Error: {str(e)}\n")
        print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
