import os
import sys
import subprocess
import shutil
import logging
from policy_engine import PolicyEngine

class GeminiHarness:
    """
    [LEGACY] Interception and execution harness for Gemini CLI.
    This class is preserved for legacy test execution and backward compatibility.
    New integrations should target the Claude PreToolUse hook implementation.
    """
    def __init__(self, policy_file="configs/policy.hl", mode="shadow"):
        self.engine = PolicyEngine(policy_file)
        self.mode = mode # 'shadow' (dry-run) or 'live'
        self.logger = logging.getLogger("GeminiHarness")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            file_handler = logging.FileHandler("harness.log")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)
        
        # Binary check (Gemini CLI is sunset, so this is non-blocking/legacy)
        self.gemini_path = shutil.which("gemini")
        if not self.gemini_path:
            self.logger.info("Legacy gemini binary not found in PATH (normal for successor environments)")
        else:
            self.logger.info(f"Legacy Gemini binary found at: {self.gemini_path}")

    def run_action(self, tool, target, content=None):
        """
        Intercepts and executes an action after policy verification.
        """
        self.logger.info(f"[PROPOSAL] Tool: {tool} | Target: {target}")
        
        # 1. Pre-execution Policy Check
        allowed, msg = self.engine.check_action(tool, target)
        if not allowed:
            self.logger.error(f"[VETO] {msg}")
            return False, msg

        self.logger.info(f"[POLICY] {msg}")

        # 2. Execution
        if self.mode == "shadow":
            self.logger.info(f"[SHADOW] Would execute {tool} on {target}")
            return True, "Shadow mode: No action taken"
        
        if tool == "run_command":
            return self._execute_command(target)
        elif tool in ["write_file", "write_to_file", "replace"]:
            return self._execute_write(target, content)
        
        return True, "Action allowed but no execution logic defined"

    def _execute_command(self, command):
        self.logger.info(f"[LIVE] Executing command: {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"[FAILURE] Command failed: {e.stderr}")
            return False, e.stderr

    def _execute_write(self, path, content):
        self.logger.info(f"[LIVE] Writing to file: {path}")
        
        # Backup for rollback
        backup_path = path + ".bak"
        existed = os.path.exists(path)
        if existed:
            shutil.copy2(path, backup_path)
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content or "")
            
            # Post-write validation
            valid, val_msg = self._run_validators(path)
            if not valid:
                self.logger.error(f"[ROLLBACK] Validation failed: {val_msg}")
                if existed:
                    shutil.move(backup_path, path)
                else:
                    os.remove(path)
                return False, f"Validation failed: {val_msg}"
            
            if existed and os.path.exists(backup_path):
                os.remove(backup_path)
            return True, "File written and validated"
            
        except Exception as e:
            self.logger.error(f"[FAILURE] Write failed: {str(e)}")
            if existed and os.path.exists(backup_path):
                shutil.move(backup_path, path)
            return False, str(e)

    def _run_validators(self, target_path):
        validators = self.engine.get_values("post_write_validators")
        for validator in validators:
            if not os.path.exists(validator):
                self.logger.warning(f"Validator script {validator} not found, skipping.")
                continue
                
            self.logger.info(f"[VALIDATOR] Running {validator} on {target_path}")
            try:
                if validator.endswith(".py"):
                    cmd = [sys.executable, validator, target_path]
                else:
                    cmd = [validator, target_path]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                return False, f"Validator {validator} failed: {e.stderr or e.stdout}"
        return True, "All validators passed"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Legacy Gemini Interception Policy Harness")
    parser.add_argument("--mode", choices=["shadow", "live"], default="shadow", help="Harness mode")
    parser.add_argument("--tool", required=True, help="Tool name (e.g., run_command, write_file)")
    parser.add_argument("--target", required=True, help="Target command or file path")
    parser.add_argument("--content", help="Content to write (for write tools)")
    
    args = parser.parse_args()
    harness = GeminiHarness(mode=args.mode)
    success, result = harness.run_action(args.tool, args.target, content=args.content)
    if not success:
        sys.exit(1)
    sys.exit(0)
