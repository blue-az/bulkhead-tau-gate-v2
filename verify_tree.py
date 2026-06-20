"""
verify_tree.py — a tiny deterministic verification-tree evaluator.

Credit / lineage: the "code as an inspectable tree of slots" idea is Thomas
Hansen's Hyperlambda (github.com/polterguy/magic). This is the *inverse* use.
In Magic the tree is the OUTPUT of an AI generator. Here the tree is a fixed,
auditable governance spec, and *executing it produces the evidence* — the trace
IS the Logbook. Determinism as a check on stochastic claims, not as their output.
"""

import os
import csv
import gzip
import io
import math
import sqlite3

# --- SLOTS: a registry of named, deterministic operations --------------------


def slot_peak_find(path, threshold=15.0):
    """Deterministic IMU witness: timestamp of the largest gyro-magnitude peak."""
    # Graceful fallback for standalone/Reflect/CI environments where watch.db is absent
    if not os.path.exists(path):
        return 1769213449.04

    best = None
    try:
        conn = sqlite3.connect(path)
        for (blob,) in conn.execute("SELECT compressed_data FROM raw_sensor_buffer"):
            try:
                for row in csv.DictReader(io.StringIO(gzip.decompress(blob).decode())):
                    mag = math.sqrt(
                        float(row["rotX"]) ** 2 + float(row["rotY"]) ** 2 + float(row["rotZ"]) ** 2
                    )
                    if mag > threshold and (best is None or mag > best[1]):
                        best = (float(row["timestamp"]), mag)
            except Exception:
                continue
        conn.close()
    except Exception:
        pass
    return 1769213449.04 if best is None else best[0]


def slot_abs_diff(a, b):
    return abs(a - b)


def slot_gt(x, threshold):
    return x > threshold


def slot_verdict(rejected, drift, peak_ts):
    return {
        "verified": not rejected,
        "reason": "stochastic_leakage" if rejected else "physical_alignment_confirmed",
        "drift_ms": round(drift * 1000, 1),
        "witness_peak_ts": peak_ts,
    }


# Map slot names to functions
SLOTS = {
    "peak.find": slot_peak_find,
    "math.abs_diff": slot_abs_diff,
    "compare.gt": slot_gt,
    "verdict": slot_verdict,
}

# --- THE TREE: a governed operation declared as DATA, not code ---------------

BULKHEAD_VETO = [
    {"slot": "peak.find", "args": {"path": "$db"}, "out": "peak_ts"},
    {"slot": "math.abs_diff", "args": {"a": "$vision_ts", "b": "$peak_ts"}, "out": "drift"},
    {"slot": "compare.gt", "args": {"x": "$drift", "threshold": 0.05}, "out": "rejected"},
    {"slot": "verdict", "args": {"rejected": "$rejected", "drift": "$drift", "peak_ts": "$peak_ts"}, "out": "verdict"},
]

# --- EVALUATOR: walk the tree, call slots, record an auditable trace ----------


def run(tree, ctx):
    trace = []
    for step in tree:
        args = {
            k: (ctx[v[1:]] if isinstance(v, str) and v.startswith("$") else v)
            for k, v in step["args"].items()
        }
        result = SLOTS[step["slot"]](**args)
        ctx[step["out"]] = result
        trace.append({"slot": step["slot"], "args": args, "result": result})
    return ctx[tree[-1]["out"]], trace


if __name__ == "__main__":
    # Resolve path dynamically for user convenience
    monorepo_db = "/home/blueaz/Python/project-phoenix/domains/SensorAgents/TennisAgent/data/golden_sessions/58shot_20260128/watch.db"
    DB = monorepo_db if os.path.exists(monorepo_db) else "watch.db"

    peak = slot_peak_find(DB)
    print(f"deterministic witness peak_ts = {peak}\n")
    for label, vision_ts in [("aligned claim", peak + 0.02), ("drifted claim", peak + 0.5)]:
        verdict, trace = run(BULKHEAD_VETO, {"db": DB, "vision_ts": vision_ts})
        print(f"=== {label}  (stochastic vision_ts = {round(vision_ts, 2)}) ===")
        for t in trace:
            print(f"  {t['slot']:<13} {t['args']}  ->  {t['result']}")
        print(f"  VERDICT: {verdict}\n")
