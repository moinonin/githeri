#!/usr/bin/env python3
"""Quick evaluation with a subset of prompts."""
import json
import sys
import subprocess
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Just 2 prompts for quick test
HELD_OUT_PROMPTS = [
    "Add a POST /notifications endpoint that sends email and push notifications. Accept recipient, subject, body, and priority. Return 202 with notification ID. Add integration tests.",
    "Create a scheduled job that archives completed verification sessions older than 90 days. Move to cold storage, update indexes. Run daily at 2 AM. Log stats.",
]

def run_cmd(cmd: str) -> tuple[int, str, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def test_model(model_name: str, prompt: str) -> Dict:
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
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from validator import validate_spec as validate
    errors = validate(spec_yaml)
    return len(errors) == 0, errors

def score_spec(spec_yaml: str, prompt: str) -> tuple[float, List[str]]:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import yaml
    from runbook_scorer import runbook_score
    spec_dict = yaml.safe_load(spec_yaml)
    spec_dict["_prompt"] = prompt
    score, details = runbook_score(spec_dict)
    return score, details

def extract_yaml(response: str) -> str:
    import re
    match = re.search(r"```yaml\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = response.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\w+:", line):
            return "\n".join(lines[i:]).strip()
    return response.strip()

def evaluate_model(model_name: str, prompts: List[str]) -> Dict:
    results = {"model": model_name, "total": len(prompts), "validated": 0, "passed_score": 0, "details": []}
    for i, prompt in enumerate(prompts):
        print(f"  [{i+1}/{len(prompts)}] Testing: {prompt[:60]}...")
        gen_result = test_model(model_name, prompt)
        if not gen_result["success"]:
            results["details"].append({"prompt": prompt, "generated": False, "error": gen_result.get("error", "unknown")})
            continue
        spec_yaml = extract_yaml(gen_result["response"])
        is_valid, errors = validate_spec(spec_yaml)
        if not is_valid:
            results["details"].append({"prompt": prompt, "generated": True, "valid": False, "errors": errors})
            continue
        results["validated"] += 1
        score, score_details = score_spec(spec_yaml, prompt)
        passed_score = score >= 0.75
        if passed_score:
            results["passed_score"] += 1
        results["details"].append({"prompt": prompt, "generated": True, "valid": True, "score": score, "score_details": score_details, "passed_score": passed_score})
    results["validation_rate"] = results["validated"] / results["total"] if results["total"] > 0 else 0
    results["score_pass_rate"] = results["passed_score"] / results["total"] if results["total"] > 0 else 0
    return results

def main():
    print("📊 Quick evaluation on 2 held-out prompts...")
    print("\n🤖 Testing base model (qwen2.5-coder:7b-instruct)...")
    base_results = evaluate_model("qwen2.5-coder:7b-instruct", HELD_OUT_PROMPTS)
    print("\n🤖 Testing fine-tuned model (specforge)...")
    ft_results = evaluate_model("specforge", HELD_OUT_PROMPTS)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS (2 prompts)")
    print("=" * 60)
    print(f"Base model:  Validation {base_results['validation_rate']*100:.0f}% | Score pass {base_results['score_pass_rate']*100:.0f}%")
    print(f"Fine-tuned:  Validation {ft_results['validation_rate']*100:.0f}% | Score pass {ft_results['score_pass_rate']*100:.0f}%")
    
    val_imp = (ft_results['validation_rate'] - base_results['validation_rate'])*100
    score_imp = (ft_results['score_pass_rate'] - base_results['score_pass_rate'])*100
    print(f"\nImprovement: Validation {val_imp:+.0f}% | Score pass {score_imp:+.0f}%")
    
    for d in ft_results["details"]:
        print(f"\n  Prompt: {d['prompt'][:50]}...")
        if d.get("valid"):
            print(f"  Score: {d['score']:.2f} | Passed: {d['passed_score']}")

if __name__ == "__main__":
    main()