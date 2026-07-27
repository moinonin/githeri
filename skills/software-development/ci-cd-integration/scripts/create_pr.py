#!/usr/bin/env python3
"""
Create PR from spec changes.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, cwd=None, input_data=None):
    """Run command and return result."""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, input=input_data)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def main():
    parser = argparse.ArgumentParser(description="Create GitHub PR from spec changes")
    parser.add_argument('--spec', required=True, help="Path to spec.yaml")
    parser.add_argument('--base', default='main', help="Base branch")
    parser.add_argument('--title', required=True, help="PR title")
    parser.add_argument('--body-file', help="Path to PR body file (PLAN.md)")
    parser.add_argument('--draft', action='store_true', help="Create as draft PR")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"Error: Spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    # Load spec to get task_id
    import yaml
    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    task_id = spec.get('task_id', 'unknown-task')
    branch_name = f"auto/{task_id}"

    # Create branch
    print(f"Creating branch: {branch_name}")
    code, out, err = run_cmd(f"git checkout -b {branch_name} {args.base}")
    if code != 0:
        print(f"Error creating branch: {err}", file=sys.stderr)
        sys.exit(1)

    # Commit spec and plan files
    run_cmd("git add -A")
    code, out, err = run_cmd(f'git commit -m "feat: {task_id}\n\nAuto-generated from spec: {spec_path}"')
    if code != 0:
        print(f"Error committing: {err}", file=sys.stderr)
        sys.exit(1)

    # Push branch
    code, out, err = run_cmd(f"git push origin {branch_name}")
    if code != 0:
        print(f"Error pushing: {err}", file=sys.stderr)
        sys.exit(1)

    # Create PR
    body = ""
    if args.body_file:
        body = Path(args.body_file).read_text()

    gh_cmd = f'gh pr create --base {args.base} --head {branch_name} --title "{args.title}"'
    if body:
        gh_cmd += f' --body-file -'
        code, out, err = run_cmd(gh_cmd, input_data=body)
    else:
        gh_cmd += f' --body "Auto-generated PR for {task_id}"'
        code, out, err = run_cmd(gh_cmd)

    if args.draft:
        run_cmd(f'gh pr ready {out.strip()} --undo')

    if code != 0:
        print(f"Error creating PR: {err}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ PR created: {out.strip()}")
    print(out.strip())


if __name__ == '__main__':
    main()