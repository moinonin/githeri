# CI/CD Integration Skill

---
name: ci-cd-integration
description: "CI/CD integration for autonomous agent: auto-PR creation, check execution, merge-on-green, rollback"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ci-cd, github-actions, auto-merge, automation]
    related_skills: [code-review-agent, spec-forge, command-runway-pattern]
---

# CI/CD Integration

## What This Is

End-to-end CI/CD automation for the autonomous coding agent:
1. **Auto-PR Creation** - Creates PR from spec changes
2. **Check Execution** - Runs lint, typecheck, test, build, security
3. **Merge on Green** - Auto-merges when all checks pass
4. **Rollback on Failure** - Closes PR and deletes branch on failure

## Installation

```bash
# Copy skill to Hermes skills directory
cp -r skills/software-development/ci-cd-integration ~/.hermes/skills/ci-cd-integration
```

## Usage

### Create PR from Spec

```bash
python skills/software-development/ci-cd-integration/scripts/create_pr.py \
  --spec path/to/spec.yaml \
  --title "feat: Add new endpoint" \
  --body-file docs/features/my-feature/PLAN.md
```

### Run Checks

```bash
python skills/software-development/ci-cd-integration/scripts/run_checks.py \
  --skip security  # Optional: skip certain checks
```

### Auto-Merge on Green

```bash
python skills/software-development/ci-cd-integration/scripts/merge_on_green.py 123 \
  --method squash \
  --timeout 600 \
  --rollback-on-failure \
  --auto-approve
```

## GitHub Actions Workflow

The skill includes a workflow at `.github/workflows/autonomous.yml` that:

1. Triggers on PR opened/updated by the autonomous agent
2. Runs all checks (lint, typecheck, test, build, security)
3. Auto-merges on green with squash strategy
4. Rolls back on failure

```yaml
# .github/workflows/autonomous.yml
name: Autonomous Agent CI/CD
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: pip install -r requirements.txt
      - name: Run checks
        run: python skills/software-development/ci-cd-integration/scripts/run_checks.py

  merge:
    needs: ci
    if: github.actor == 'github-actions[bot]'  # Only for autonomous PRs
    runs-on: ubuntu-latest
    steps:
      - name: Merge on green
        run: |
          python skills/software-development/ci-cd-integration/scripts/merge_on_green.py \
            ${{ github.event.pull_request.number }} \
            --method squash \
            --rollback-on-failure \
            --auto-approve
```

## Scripts

| Script | Purpose |
|--------|---------|
| `create_pr.py` | Creates PR from spec changes |
| `run_checks.py` | Runs lint, typecheck, test, build, security |
| `merge_on_green.py` | Waits for checks, merges or rolls back |

## Configuration

Environment variables:
- `GH_TOKEN` - GitHub token for `gh` CLI (auto-provided in Actions)
- `BASE_BRANCH` - Base branch for PRs (default: `main`)

## Requirements

- `gh` CLI installed and authenticated
- Python 3.11+
- Project with `requirements.txt` or `pyproject.toml`
- GitHub repository with Actions enabled