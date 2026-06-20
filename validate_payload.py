#!/usr/bin/env python3
import sys
import json
import os

def validate_json_payload(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        return False

    # Check if the file is empty
    if os.path.getsize(file_path) == 0:
        print("Validation failed: Payload file is empty.", file=sys.stderr)
        return False

    # Check if the file name ends with .json
    if not file_path.endswith('.json'):
        print(f"Validation warning: File '{file_path}' is not a JSON file. Performing basic non-empty check.", file=sys.stderr)
        return True

    # Structured JSON validation
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Validation failed: Malformed JSON. {e}", file=sys.stderr)
        return False

    # Schema & Content validation rules:
    # 1. Root must be a dictionary (JSON object)
    if not isinstance(data, dict):
        print("Validation failed: Root of JSON payload must be a JSON object (dict).", file=sys.stderr)
        return False

    # 2. Check for "status" field validations if present
    if "status" in data:
        val = data["status"]
        if not isinstance(val, str):
            print(f"Validation failed: 'status' must be a string, got {type(val).__name__}.", file=sys.stderr)
            return False
        
        allowed_statuses = ["ok", "pending", "success", "active"]
        if val.lower() not in allowed_statuses:
            print(f"Validation failed: Status '{val}' is not in the allowed list {allowed_statuses}.", file=sys.stderr)
            return False

    # 3. Check for specific restricted keywords or fields that might break the schema
    for k, v in data.items():
        if k == "input_tokens" or k == "ollama_interceptor":
            print(f"Validation failed: Hallucinated/forbidden configuration key '{k}' found.", file=sys.stderr)
            return False

    print(f"Validation passed: {file_path} is structurally sound.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_payload.py <file_path>", file=sys.stderr)
        sys.exit(2)
        
    target_file = sys.argv[1]
    if validate_json_payload(target_file):
        sys.exit(0)
    else:
        sys.exit(1)
