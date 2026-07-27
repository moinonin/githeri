#!/usr/bin/env python3
"""
Run CI checks: lint, typecheck, test, build, security.
"""

import argparse
import subprocess
import sys
from typing import List, Tuple


def run_cmd(cmd: str, cwd: str = "") -> Tuple[int, str, str]:
    """Run command and return (code, stdout, stderr)."""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def run_check(name: str, cmd: str, cwd: str = "") -> bool:
    """Run a single check and return success."""
    print(f"\n{'='*60}")
    print(f"🔍 {name}")
    print(f"{'='*60}")
    print(f"Running: {cmd}")

    code, out, err = run_cmd(cmd, cwd)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)

    if code == 0:
        print(f"✅ {name} PASSED")
        return True
    else:
        print(f"❌ {name} FAILED (exit code: {code})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run CI checks")
    parser.add_argument('--checks', default='lint,typecheck,test,build,security',
                        help="Comma-separated list of checks to run")
    parser.add_argument('--skip', default='',
                        help="Comma-separated list of checks to skip")
    parser.add_argument('--strict', action='store_true',
                        help="Exit on first failure")
    args = parser.parse_args()

    checks_to_run = set(args.checks.split(','))
    checks_to_skip = set(args.skip.split(',')) if args.skip else set()

    # Define all available checks
    all_checks = {
        'lint': ("Lint", "ruff check ."),
        'format': ("Format Check", "ruff format --check ."),
        'typecheck': ("Type Check", "mypy ."),
        'test': ("Tests", "pytest -x --tb=short"),
        'build': ("Build", "python -m build"),
        'security': ("Security", "bandit -r . -q"),
    }

    # Filter checks
    selected = []
    for check in checks_to_run:
        if check in checks_to_skip:
            print(f"⏭️  Skipping {check}")
            continue
        if check in all_checks:
            selected.append(all_checks[check])
        else:
            print(f"⚠️  Unknown check: {check}")

    if not selected:
        print("No checks to run")
        return 0

    print(f"Running {len(selected)} check(s): {[c[0] for c in selected]}")

    results = {}
    all_passed = True

    for name, cmd in selected:
        passed = run_check(name, cmd)
        results[name] = passed
        if not passed:
            all_passed = False
            if args.strict:
                break

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    if all_passed:
        print(f"\n🎉 All checks passed!")
        return 0
    else:
        print(f"\n💥 Some checks failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())