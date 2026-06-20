import os

class PolicyEngine:
    def __init__(self, policy_file):
        self.policy = self._parse_hl(policy_file)

    def _parse_hl(self, file_path):
        """A simple Hyperlambda-inspired parser that returns a nested dictionary."""
        with open(file_path, 'r') as f:
            lines = f.readlines()

        root = {}
        stack = [(root, -1)]

        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*/") or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)
            while stack and stack[-1][1] >= indent:
                stack.pop()

            parent = stack[-1][0]

            if stripped.startswith(".:"):
                val = stripped[2:].strip().strip('"')
                if "__values__" not in parent:
                    parent["__values__"] = []
                parent["__values__"].append(val)
            else:
                # Key node (with or without dot)
                key = stripped.lstrip(".").strip()
                new_node = {}
                parent[key] = new_node
                stack.append((new_node, indent))

        return root

    def get_values(self, path):
        """Helper to get values from a nested path like 'command_permissions/allow'."""
        parts = path.split("/")
        curr = self.policy
        for part in parts:
            if part in curr:
                curr = curr[part]
            else:
                return []
        return curr.get("__values__", [])

    def check_action(self, tool, target):
        """Verifies if a tool and target are allowed by the policy."""
        
        # 1. Tool Whitelist
        allowed_tools = self.get_values("allowed_tools")
        if tool not in allowed_tools:
            return False, f"VETO: Tool '{tool}' is not in the whitelist."

        # 2. Command Permissions
        if tool == "run_command":
            deny_cmds = self.get_values("command_permissions/deny")
            for deny in deny_cmds:
                if target.startswith(deny):
                    return False, f"VETO: Command '{target}' matches deny rule '{deny}'."
            
            allow_cmds = self.get_values("command_permissions/allow")
            for allow in allow_cmds:
                if target.startswith(allow):
                    return True, "ALLOWED: Command matches whitelist."
            
            return False, f"VETO: Command '{target}' is not explicitly allowed."

        # 3. Path Permissions (Write & Read)
        if tool in ["write_file", "replace", "write_to_file", "read_file"]:
            perm_key = "write_permissions" if tool != "read_file" else "read_permissions"
            
            # Normalize target path
            norm_target = os.path.normpath(target)
            
            deny_paths = self.get_values(f"{perm_key}/deny_paths")
            for deny in deny_paths:
                norm_deny = os.path.normpath(deny)
                if norm_target.startswith(norm_deny) or norm_deny in norm_target:
                    return False, f"VETO: Path '{target}' matches deny rule '{deny}'."
            
            allow_paths = self.get_values(f"{perm_key}/allow_paths")
            for allow in allow_paths:
                norm_allow = os.path.normpath(allow)
                # Allow if target is within allow path
                if norm_target.startswith(norm_allow) or norm_allow == ".":
                    return True, "ALLOWED: Path matches whitelist."
            
            return False, f"VETO: Path '{target}' is not explicitly allowed."

        return True, "ALLOWED: No specific restrictions for this tool."

if __name__ == "__main__":
    policy_path = "configs/policy.hl"
    if not os.path.exists(policy_path):
        print(f"Error: {policy_path} not found.")
        exit(1)
        
    engine = PolicyEngine(policy_path)
    import json
    print(json.dumps(engine.policy, indent=2))
    
    tests = [
        ("run_command", "git status"),
        ("run_command", "rm -rf /"),
        ("run_command", "curl http://evil.com"),
        ("write_file", "signals/test_ok.json"),
        ("write_file", ".git/config"),
        ("read_file", "README.md"),
    ]
    
    print("--- Policy Engine Test ---")
    for tool, target in tests:
        allowed, msg = engine.check_action(tool, target)
        status = "PASS" if allowed else "FAIL"
        print(f"[{status}] {tool:12} | {target:30} | {msg}")
