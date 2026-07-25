#!/usr/bin/env python3
"""Evaluate fine-tuned model on held-out prompts.

Compares base vs fine-tuned model pass rates through validator + scorer.
"""
import json
import sys
import subprocess
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINING_DATA = PROJECT_ROOT / "data" / "training_data.jsonl"
VALIDATOR_SCRIPT = PROJECT_ROOT / "scripts" / "validator.py"
SCORER_SCRIPT = PROJECT_ROOT / "scripts" / "runbook_scorer.py"

# Test prompts not in training data
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
]


def run_cmd(cmd: str) -> tuple[int, str, str]:
    """Run command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_model(model_name: str, prompt: str) -> Dict:
    """Test a model with a single prompt via Ollama."""
    # Use ollama generate
    import requests
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 2048},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return {"success": True, "response": resp.json()["response"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def validate_spec(spec_yaml: str) -> tuple[bool, List[str]]:
    """Validate spec using the hardened validator."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from validator import validate_spec
    errors = validate_spec(spec_yaml)
    return len(errors) == 0, errors


def score_spec(spec_yaml: str, prompt: str) -> tuple[float, List[str]]:
    """Score spec using runbook scorer."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import yaml
    from runbook_scorer import runbook_score
    spec_dict = yaml.safe_load(spec_yaml)
    spec_dict["_prompt"] = prompt
    score, details = runbook_score(spec_dict)
    return score, details


def extract_yaml(response: str) -> str:
    """Extract YAML from model response (handles markdown fences)."""
    import re
    # Try ```yaml ... ``` fences
    match = re.search(r"```yaml\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try ``` ... ``` fences
    match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: find first line starting with key:
    lines = response.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\w+:", line):
            return "\n".join(lines[i:]).strip()
    return response.strip()


def evaluate_model(model_name: str, prompts: List[str]) -> Dict:
    """Evaluate a model on a set of prompts."""
    results = {
        "model": model_name,
        "total": len(prompts),
        "validated": 0,
        "passed_score": 0,
        "details": [],
    }

    for i, prompt in enumerate(prompts):
        print(f"  [{i+1}/{len(prompts)}] Testing: {prompt[:60]}...")

        gen_result = test_model(model_name, prompt)
        if not gen_result["success"]:
            results["details"].append({
                "prompt": prompt,
                "generated": False,
                "error": gen_result.get("error", "unknown"),
            })
            continue

        spec_yaml = extract_yaml(gen_result["response"])

        # Validate
        is_valid, errors = validate_spec(spec_yaml)
        if not is_valid:
            results["details"].append({
                "prompt": prompt,
                "generated": True,
                "valid": False,
                "errors": errors,
            })
            continue

        results["validated"] += 1

        # Score
        score, score_details = score_spec(spec_yaml, prompt)
        passed_score = score >= 0.75

        if passed_score:
            results["passed_score"] += 1

        results["details"].append({
            "prompt": prompt,
            "generated": True,
            "valid": True,
            "score": score,
            "score_details": score_details,
            "passed_score": passed_score,
        })

    # Summary
    results["validation_rate"] = results["validated"] / results["total"] if results["total"] > 0 else 0
    results["score_pass_rate"] = results["passed_score"] / results["total"] if results["total"] > 0 else 0

    return results


def main():
    print("📊 Evaluating models on held-out prompts...")
    print(f"   Test prompts: {len(HELD_OUT_PROMPTS)}")

    # Test base model
    print("\n🤖 Testing base model (qwen2.5-coder:7b-instruct)...")
    base_results = evaluate_model("qwen2.5-coder:7b-instruct", HELD_OUT_PROMPTS)

    # Test fine-tuned model if available
    ft_results = None
    ft_model = "specforge"  # Created by 'make merge' + 'ollama create specforge -f ...'
    print(f"\n🤖 Testing fine-tuned model ({ft_model})...")
    try:
        ft_results = evaluate_model(ft_model, HELD_OUT_PROMPTS)
    except Exception as e:
        print(f"   ⚠️  Fine-tuned model not available: {e}")

    # Print comparison
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Base model (qwen2.5-coder:7b-instruct):")
    print(f"  Validation rate: {base_results['validation_rate']*100:.1f}% ({base_results['validated']}/{base_results['total']})")
    print(f"  Score pass rate: {base_results['score_pass_rate']*100:.1f}% ({base_results['passed_score']}/{base_results['total']})")

    if ft_results:
        print(f"\nFine-tuned model (specforge):")
        print(f"  Validation rate: {ft_results['validation_rate']*100:.1f}% ({ft_results['validated']}/{ft_results['total']})")
        print(f"  Score pass rate: {ft_results['score_pass_rate']*100:.1f}% ({ft_results['passed_score']}/{ft_results['total']})")

        # Improvement
        val_improvement = ft_results['validation_rate'] - base_results['validation_rate']
        score_improvement = ft_results['score_pass_rate'] - base_results['score_pass_rate']
        print(f"\nImprovement:")
        print(f"  Validation rate: {val_improvement*100:+.1f}%")
        print(f"  Score pass rate: {score_improvement*100:+.1f}%")

        # Check target
        target_met = ft_results['score_pass_rate'] >= 0.80
        print(f"\nTarget (>80% score pass rate): {'✅ MET' if target_met else '❌ NOT MET'}")

    # Save detailed results
    output = {
        "base_model": base_results,
        "fine_tuned_model": ft_results,
    }
    out_path = PROJECT_ROOT / "data" / "eval_results.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n💾 Detailed results saved to {out_path}")


if __name__ == "__main__":
    main()