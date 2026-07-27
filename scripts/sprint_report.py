#!/usr/bin/env python3
"""
Sprint Report Generator

Generates a markdown report from a sprint's RUNBOOK.md and SPEC.yaml.
"""

import json
import yaml
import sys
import re
from pathlib import Path
from datetime import datetime


def parse_runbook(runbook_path):
    """Parse RUNBOOK.md and extract execution results."""
    with open(runbook_path) as f:
        content = f.read()

    results = {
        "stages": [],
        "goals": {},
        "commands": [],
        "failures": [],
        "retries": 0,
    }

    # Parse execution log table
    in_log = False
    for line in content.split('\n'):
        if '| Cmd#' in line and 'Start' in line and 'End' in line:
            in_log = True
            continue
        if in_log and line.startswith('|'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 7:
                cmd_num = parts[0]
                start = parts[2]
                end = parts[3]
                exit_code = parts[4]
                retry = parts[5]
                output = parts[6]
                if exit_code.isdigit() or (exit_code.startswith('-') and exit_code[1:].isdigit()):
                    results["commands"].append({
                        "cmd": cmd_num,
                        "start": start,
                        "end": end,
                        "exit": int(exit_code),
                        "retry": int(retry) if retry.isdigit() else 0,
                        "output": output[:100],
                    })
                    if int(exit_code) != 0:
                        results["failures"].append(cmd_num)
                    if retry.isdigit() and int(retry) > 0:
                        results["retries"] += int(retry)
        elif in_log and not line.startswith('|'):
            in_log = False

    # Parse goal verification
    in_goals = False
    for line in content.split('\n'):
        if '### Local Goal Checks' in line:
            in_goals = True
            continue
        if in_goals and line.startswith('- **L'):
            # Parse goal line: - **L1:** `command` FAIL ✅  OR  - **L1:** `command` → **PASS** ✅
            # Try format 1: `command` FAIL/PASS (with optional emoji)
            match = re.search(r'\*\*(L\d+)\*\*:\s+`([^`]+)`\s+(PASS|FAIL)\s*✅', line)
            if not match:
                # Try format 2: `command` → **PASS/FAIL** (with optional emoji)
                match = re.search(r'\*\*(L\d+)\*\*:\s+`([^`]+)`\s*→\s*\*\*(PASS|FAIL)\*\*\s*✅', line)
            if match:
                goal_id, cmd, status = match.groups()
                results["goals"][goal_id] = {"command": cmd, "status": status}

    return results


def parse_spec(spec_path):
    """Parse SPEC.yaml for goals and metadata."""
    with open(spec_path) as f:
        spec = yaml.safe_load(f.read())
    return spec


def generate_report(spec_path, runbook_path, output_path):
    """Generate sprint report markdown."""
    spec = parse_spec(spec_path)
    results = parse_runbook(runbook_path)

    task_id = spec.get("task_id", "unknown")
    summary = spec.get("summary", "")
    goals = spec.get("local_goals", [])

    # Calculate stats
    total_commands = len(results["commands"])
    passed_commands = sum(1 for c in results["commands"] if c["exit"] == 0)
    failed_commands = total_commands - passed_commands
    total_retries = results["retries"]
    failed_goals = sum(1 for g in results["goals"].values() if g["status"] == "FAIL")
    total_goals = len(results["goals"])

    md = f"""# Sprint Report: {task_id}

**Generated:** {datetime.now().isoformat()}
**Spec:** {spec_path}
**Runbook:** {runbook_path}

---

## Summary

{summary}

---

## Execution Summary

| Metric | Value |
|--------|-------|
| Total Commands | {total_commands} |
| Passed | {passed_commands} |
| Failed | {failed_commands} |
| Retries | {total_retries} |
| Goals Passed | {total_goals - failed_goals}/{total_goals} |

---

## Goal Verification

| Goal | Description | Command | Status |
|------|-------------|---------|--------|
"""
    for goal in spec.get("local_goals", []):
        goal_id = goal.get("id", "")
        desc = goal.get("description", "")
        goal_result = results["goals"].get(goal_id, {})
        status = goal_result.get("status", "UNKNOWN")
        cmd = goal_result.get("command", "")
        md += f"| {goal_id} | {desc} | `{cmd[:50]}...` | **{status}** |\n"

    md += f"""

---

## Command Execution Log

| Cmd | Start | End | Exit | Retry | Output |
|-----|-------|-----|------|-------|--------|
"""
    for cmd in results["commands"]:
        status_emoji = "✅" if cmd["exit"] == 0 else "❌"
        md += f"| {cmd['cmd']} | {cmd['start']} | {cmd['end']} | {cmd['exit']} {status_emoji} | {cmd['retry']} | {cmd['output']} |\n"

    if results["failures"]:
        md += f"""

---

## Failures Analysis

**Failed Commands:** {', '.join(results['failures'])}

**Total Retries:** {total_retries}

### Recommendations

- Review failed commands and their output
- Check for missing dependencies or environment issues
- Consider increasing retry count for flaky commands
"""

    md += f"""

---

## Spec Compliance

**Task ID:** {task_id}
**Goals Defined:** {len(spec.get("local_goals", []))}
**Goals Verified:** {len(results["goals"])}
**Goals Passed:** {len(results["goals"]) - sum(1 for g in results["goals"].values() if g["status"] == "FAIL")}

---

*Report generated by sprint_report.py on {datetime.now().isoformat()}*
"""

    with open(output_path, 'w') as f:
        f.write(md)

    print(f"✅ Report generated: {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate sprint report")
    parser.add_argument("--runbook", required=True, help="Path to RUNBOOK.md")
    parser.add_argument("--spec", required=True, help="Path to SPEC.yaml")
    parser.add_argument("--output", required=True, help="Output report path")
    args = parser.parse_args()

    generate_report(args.spec, args.runbook, args.output)