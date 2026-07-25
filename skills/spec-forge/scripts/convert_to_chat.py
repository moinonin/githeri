#!/usr/bin/env python3
"""Convert training_data.jsonl to chat format (system/user/assistant) for fine-tuning.

Input:  data/training_data.jsonl  (prompt + spec_yaml + runbook_score + score_details)
Output: data/training_data_chat.jsonl (messages: system, user, assistant)

Each output line:
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

Usage: python convert_to_chat.py [--min-score THRESHOLD]
Default threshold: 0.75 (hard gate from scorer)
"""
import json
import sys
import argparse
from pathlib import Path

INPUT_FILE = Path("data/training_data.jsonl")
OUTPUT_FILE = Path("data/training_data_chat.jsonl")

SYSTEM_PROMPT = (
    "You are a precise specification generator. Output ONLY a YAML document. "
    "No code, no commentary. Convert the given feature request into a valid "
    "executable specification with task_id, summary, local_goals (with "
    "verification steps), global_goals_refs, and context."
)

def main():
    parser = argparse.ArgumentParser(description="Convert training data to chat format for fine-tuning")
    parser.add_argument("--min-score", type=float, default=0.75,
                        help="Minimum runbook_score to include (default: 0.75)")
    parser.add_argument("--input", type=Path, default=INPUT_FILE,
                        help=f"Input JSONL file (default: {INPUT_FILE})")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE,
                        help=f"Output JSONL file (default: {OUTPUT_FILE})")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    count = 0
    filtered = 0
    with args.input.open() as fin, args.output.open("w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                pair = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: skipping invalid JSON line: {e}", file=sys.stderr)
                continue

            prompt = pair.get("prompt", "").strip()
            spec_yaml = pair.get("spec_yaml", "").strip()
            score = pair.get("runbook_score", 0.0)

            if not prompt or not spec_yaml:
                print("Warning: skipping entry with empty prompt or spec_yaml", file=sys.stderr)
                continue

            if score < args.min_score:
                filtered += 1
                continue

            chat = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": spec_yaml},
                ]
            }
            fout.write(json.dumps(chat, ensure_ascii=False) + "\n")
            count += 1

    print(f"✅ Converted {count} entries → {args.output}")
    if filtered:
        print(f"   Filtered out {filtered} entries with score < {args.min_score}")

if __name__ == "__main__":
    main()