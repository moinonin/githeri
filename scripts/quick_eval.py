#!/usr/bin/env python3
"""Quick A/B eval: base (qwen2.5-coder:7b-instruct) vs fine-tuned (specforge-128k).

Uses the SAME system prompt as the training pipeline so the fine-tuned model
is evaluated in the context it was trained for.

Usage:
    .venv/bin/python scripts/quick_eval.py [--prompts N] [--timeout 60]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_pipeline import SYSTEM_PROMPT, extract_yaml
from validator import validate_spec
from runbook_scorer import runbook_score
import yaml

OLLAMA_URL = "http://localhost:11434/api/generate"

# Reuse session for connection pooling
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})


def call_model(model: str, system: str, user: str, timeout: int = 120) -> dict:
    """Call Ollama generate with a system prompt. Returns {success, response, elapsed}."""
    start = time.time()
    try:
        resp = SESSION.post(
            OLLAMA_URL,
            json={
                "model": model,
                "system": system,
                "prompt": user,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 2048},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        elapsed = time.time() - start
        return {"success": True, "response": resp.json()["response"], "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"success": False, "error": str(e), "elapsed": elapsed}


HELD_OUT_PROMPTS = [
    "Add a POST /notifications endpoint that sends email and push notifications. Accept recipient, subject, body, and priority. Return 202 with notification ID. Add integration tests.",
    "Create a scheduled job that archives completed verification sessions older than 90 days. Move to cold storage, update indexes. Run daily at 2 AM. Log stats.",
    "Implement a POST /admin/impersonate endpoint that allows super-admins to act as another user. Audit log all impersonation. Return impersonation token.",
    "Add a GET /analytics/funnel endpoint that returns conversion funnel data (sessions -> evidence -> verification -> proof). Filterable by date range, policy.",
    "Create a POST /webhooks/retry endpoint to manually retry failed webhook deliveries. Accept webhook ID. Return 200 with retry status.",
    "Implement a GET /health/dependencies endpoint that checks DB, Redis, S3, message queue connectivity. Return 200 if all healthy, 503 otherwise.",
    "Add support for bulk user import from CSV with validation. Return summary of imported/skipped/failed. Async processing for large files.",
    "Create a POST /proofs/verify endpoint that verifies a Proof of Attention by proofId. Public endpoint (no auth). Return verification result.",
    "Implement a scheduled task that recalculates user reputation scores weekly based on verification activity. Update rankings.",
    "Add a DELETE /sessions/:id/evidence/:evidenceId endpoint to remove specific evidence from a session. Only creator or admin. Return 204.",
    "Add a PATCH /users/{id}/settings endpoint that updates notification preferences, privacy flags, and theme. Return 200 with updated settings.",
    "Create a GET /exports/sessions endpoint that returns a CSV download of verification sessions. Filter by date range and status. Return 200 with file stream.",
]


def evaluate_model(model: str, prompts: list, timeout: int) -> dict:
    """Eval one model on all prompts. Returns structured results."""
    results = {
        "model": model,
        "total": len(prompts),
        "generated": 0,
        "validated": 0,
        "passed_score": 0,
        "avg_score": 0.0,
        "avg_latency": 0.0,
        "details": [],
    }
    scores = []
    latencies = []

    for i, prompt in enumerate(prompts):
        short = prompt[:60] + "..."
        print(f"  [{i+1}/{len(prompts)}] {short}", end="", flush=True)

        r = call_model(model, SYSTEM_PROMPT, prompt, timeout=timeout)

        if not r["success"]:
            print(f" ERROR: {r['error'][:40]}")
            results["details"].append({"prompt": prompt, "error": r["error"]})
            continue

        results["generated"] += 1
        latencies.append(r["elapsed"])

        spec_yaml = extract_yaml(r["response"])
        errors = validate_spec(spec_yaml)
        is_valid = len(errors) == 0

        if not is_valid:
            print(f" generated but INVALID ({len(errors)} errors)")
            results["details"].append({
                "prompt": prompt,
                "generated": True,
                "valid": False,
                "errors": errors[:3],
            })
            continue

        results["validated"] += 1
        spec_dict = yaml.safe_load(spec_yaml)
        spec_dict["_prompt"] = prompt
        score, score_details = runbook_score(spec_dict)
        scores.append(score)

        passed = score >= 0.75
        if passed:
            results["passed_score"] += 1

        status = f"score={score:.2f} {'PASS' if passed else 'FAIL'}"
        print(f" valid, {status}")

        results["details"].append({
            "prompt": prompt,
            "generated": True,
            "valid": True,
            "score": round(score, 3),
            "passed_score": passed,
            "latency": round(r["elapsed"], 1),
        })

    results["avg_score"] = round(sum(scores) / len(scores), 3) if scores else 0.0
    results["avg_latency"] = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    results["validation_rate"] = round(results["validated"] / results["total"], 3)
    results["score_pass_rate"] = round(results["passed_score"] / results["total"], 3)
    return results


def main():
    parser = argparse.ArgumentParser(description="Quick A/B eval: base vs fine-tuned")
    parser.add_argument("--prompts", type=int, default=5, help="Number of held-out prompts to test")
    parser.add_argument("--timeout", type=int, default=120, help="Per-prompt timeout in seconds")
    parser.add_argument("--models", type=str, default="qwen2.5-coder:7b-instruct,specforge-128k:latest",
                        help="Comma-separated model names")
    args = parser.parse_args()

    prompts = HELD_OUT_PROMPTS[:args.prompts]
    models = args.models.split(",")

    print(f"=== Quick A/B Eval ===")
    print(f"  Prompts: {len(prompts)}")
    print(f"  Models:  {models}")
    print(f"  Timeout: {args.timeout}s per prompt")
    print()

    all_results = {}
    for model in models:
        print(f"--- Model: {model} ---")
        all_results[model] = evaluate_model(model, prompts, args.timeout)
        print()

    # Summary comparison
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Metric':<25} {' | '.join(m[:18] for m in models)}")
    print("-" * 60)

    for metric in ["validation_rate", "score_pass_rate", "avg_score", "avg_latency"]:
        row = f"{metric:<25}"
        for model in models:
            val = all_results[model].get(metric, 0)
            if isinstance(val, float):
                row += f" {val:>18.3f}"
            else:
                row += f" {val:>18}"
        print(row)

    # Improvement deltas if 2 models
    if len(models) == 2:
        a, b = models[0], models[1]
        ra, rb = all_results[a], all_results[b]
        print()
        print(f"Delta ({b} vs {a}):")
        for metric in ["validation_rate", "score_pass_rate", "avg_score"]:
            delta = rb.get(metric, 0) - ra.get(metric, 0)
            pct = delta * 100 if metric != "avg_score" else delta
            sign = "+" if delta >= 0 else ""
            print(f"  {metric}: {sign}{pct:.1f}%")

    # Save
    out_path = PROJECT_ROOT / "data" / "eval_results.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()