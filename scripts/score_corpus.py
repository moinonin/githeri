#!/usr/bin/env python3
"""
Score all specs in a corpus file (training_data.jsonl or failed_specs.jsonl).

Usage:
    python scripts/score_corpus.py [--file data/training_data.jsonl] [--threshold 0.75]
"""
import json
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from runbook_scorer import runbook_score


def score_corpus(input_file, output_file=None, threshold=0.75):
    """Score all specs in the input file and write results."""
    if not Path(input_file).exists():
        print(f"File not found: {input_file}")
        return

    results = []
    with open(input_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Skipping invalid JSON line: {e}")
                continue

            spec_yaml = record.get("spec_yaml", "")
            if not spec_yaml:
                continue

            try:
                spec_dict = yaml.safe_load(spec_yaml)
                spec_dict["_prompt"] = record.get("prompt", "")
                score, issues = runbook_score(spec_dict)
                record["runbook_score"] = score
                record["score_details"] = issues
                record["above_threshold"] = score >= threshold
            except Exception as e:
                record["runbook_score"] = 0.0
                record["score_details"] = [f"Scoring error: {e}"]
                record["above_threshold"] = False

            results.append(record)

    # Write back
    if output_file is None:
        output_file = input_file

    with open(output_file, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Summary
    total = len(results)
    above = sum(1 for r in results if r.get("above_threshold", False))
    avg_score = sum(r.get("runbook_score", 0) for r in results) / total if total > 0 else 0

    print(f"Scored {total} specs from {input_file}")
    print(f"  Average score: {avg_score:.3f}")
    print(f"  Above threshold ({threshold}): {above}/{total} ({100*above/total:.1f}%)")
    print(f"  Written to: {output_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Score specs in corpus")
    parser.add_argument("--file", default="data/training_data.jsonl", help="Input JSONL file")
    parser.add_argument("--output", default=None, help="Output file (default: overwrite input)")
    parser.add_argument("--threshold", type=float, default=0.75, help="Score threshold")
    args = parser.parse_args()

    score_corpus(args.file, args.output, args.threshold)