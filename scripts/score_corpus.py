"""Score all specs in the training corpus."""
import json
import sys
import pathlib
import yaml

# Add scripts to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from runbook_scorer import runbook_score

OUTPUT_FILE = "data/training_data.jsonl"

def main():
    try:
        with open(OUTPUT_FILE) as f:
            pairs = [json.loads(line) for line in f.read().strip().splitlines() if line.strip()]
    except FileNotFoundError:
        print(f"Error: {OUTPUT_FILE} not found")
        sys.exit(1)

    for i, p in enumerate(pairs):
        spec_dict = yaml.safe_load(p['spec_yaml'])
        spec_dict['_prompt'] = p.get('prompt', '')
        score, issues = runbook_score(spec_dict)
        status = '✅' if score >= 0.7 else '⚠️'
        print(f"  {status} [{i}] {spec_dict.get('task_id', 'unknown')}: {score:.2f}")
        if issues:
            for issue in issues[:3]:
                print(f"     - {issue}")
            if len(issues) > 3:
                print(f"     ... and {len(issues) - 3} more")

if __name__ == "__main__":
    main()