#!/usr/bin/env python3
"""
Merge on Green - Waits for CI checks to pass, then merges PR.
Rolls back on failure if requested.
"""

import argparse
import subprocess
import sys
import time


def run_cmd(cmd: str) -> tuple[bool, str, str]:
    """Run command and return (success, stdout, stderr)."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()


def get_check_status(pr_number: str) -> dict:
    """Get GitHub check status for a PR."""
    code, out, err = run_cmd(f'gh pr checks {pr_number} --json name,state,conclusion')
    if code != 0:
        print(f"Error getting checks: {err}")
        return {}
    try:
        import json
        checks = json.loads(out)
        return {check['name']: check for check in checks}
    except Exception as e:
        print(f"Error parsing checks: {e}")
        return {}


def all_checks_passed(checks: dict) -> tuple[bool, str]:
    """Check if all required checks have passed."""
    if not checks:
        return False, "No checks found"

    required = ['lint', 'typecheck', 'test', 'build', 'security']
    pending = []
    failed = []

    for check in required:
        found = False
        for name, info in checks.items():
            if check.lower() in name.lower():
                found = True
                state = info.get('state', '').lower()
                conclusion = info.get('conclusion', '').lower()
                if state != 'completed':
                    pending.append(name)
                elif conclusion != 'success':
                    failed.append(name)
                break
        if not found:
            pending.append(check)

    if failed:
        return False, f"Failed: {', '.join(failed)}"
    if pending:
        return False, f"Pending: {', '.join(pending)}"
    return True, "All checks passed"


def wait_for_checks(pr_number: str, timeout: int = 600, poll: int = 30) -> tuple[bool, str]:
    """Wait for all checks to complete."""
    start = time.time()
    while time.time() - start < timeout:
        checks = get_check_status(pr_number)
        passed, msg = all_checks_passed(checks)
        print(f"  Status: {msg}")
        if passed:
            return True, msg
        if "Failed" in msg:
            return False, msg
        time.sleep(poll)
    return False, f"Timeout after {timeout}s"


def merge_pr(pr_number: str, method: str = "squash") -> tuple[bool, str, str]:
    """Merge a PR."""
    return run_cmd(f'gh pr merge {pr_number} --{method} --delete-branch --auto')


def rollback_pr(pr_number: str) -> tuple[bool, str, str]:
    """Close PR and delete branch."""
    run_cmd(f'gh pr close {pr_number} --delete-branch')
    return run_cmd(f'gh pr close {pr_number}')


def approve_pr(pr_number: str) -> tuple[bool, str, str]:
    """Approve PR."""
    return run_cmd(f'gh pr review {pr_number} --approve')


def main():
    parser = argparse.ArgumentParser(description="Merge PR on green checks")
    parser.add_argument('pr', help="PR number")
    parser.add_argument('--method', choices=['squash', 'merge', 'rebase'], default='squash')
    parser.add_argument('--timeout', type=int, default=600, help="Timeout in seconds")
    parser.add_argument('--poll', type=int, default=30, help="Poll interval in seconds")
    parser.add_argument('--rollback-on-failure', action='store_true', help="Rollback on failure")
    parser.add_argument('--auto-approve', action='store_true', help="Auto-approve PR")
    args = parser.parse_args()

    pr_number = args.pr

    if args.auto_approve:
        print(f"Approving PR #{pr_number}...")
        code, out, err = approve_pr(pr_number)
        if code != 0:
            print(f"Warning: Could not approve: {err}")

    print(f"Waiting for checks on PR #{pr_number}...")
    passed, msg = wait_for_checks(pr_number, args.timeout, args.poll)
    print(f"Checks: {msg}")

    if passed:
        print(f"Merging PR #{pr_number} with {args.method}...")
        code, out, err = merge_pr(pr_number, args.method)
        if code == 0:
            print(f"✅ PR merged successfully")
            sys.exit(0)
        else:
            print(f"❌ Merge failed: {err}")
            sys.exit(1)
    else:
        print(f"❌ Checks failed: {msg}")
        if args.rollback_on_failure:
            print(f"Rolling back PR #{pr_number}...")
            rollback_pr(pr_number)
        sys.exit(1)


if __name__ == '__main__':
    import time
    main()