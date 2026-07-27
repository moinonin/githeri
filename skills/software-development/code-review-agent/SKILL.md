---
name: code-review-agent
description: "LLM-powered code review agent with pattern enforcement, security scanning, and CI/CD integration. Reviews diffs, checks patterns, scans for secrets/vulnerabilities, and provides structured findings (block/warn/info)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-review, pattern-enforcement, security-scan, ci-cd]
    related_skills: [command-runway-pattern, ci-cd-integration, spec-forge]
---

# Code Review Agent

## What This Is

An AI-powered code review system that:
1. **Analyzes diffs** - Reads git diffs and provides structured feedback
2. **Enforces patterns** - Checks against project conventions (naming, structure, imports, testing)
3. **Scans for security** - Detects secrets, vulnerabilities, license issues
3. **Integrates with CI/CD** - Posts reviews to GitHub PRs, blocks on critical findings

## When To Use

- After implementing a feature (before merge)
- In CI/CD pipeline on every PR
- For automated code quality gates
- To enforce team conventions consistently

## Installation

```bash
# Copy skill to Hermes skills directory
cp -r skills/software-development/code-review-agent ~/.hermes/skills/code-review-agent
```

## Usage

### Review a Diff

```bash
python skills/software-development/code-review-agent/scripts/review_diff.py \
  --diff path/to/diff.patch \
  --format json \
  --severity block,warn,info
```

### Enforce Patterns

```bash
python skills/software-development/code-review-agent/scripts/enforce_patterns.py \
  --path . \
  --strict \
  --config .hermes/patterns/
```

### Security Scan

```bash
python skills/software-development/code-review-agent/scripts/security_scan.py \
  --path . \
  --rules secrets,vulnerabilities,licenses
```

### GitHub PR Review (in CI)

```yaml
# .github/workflows/code-review.yml
- name: Code Review
  run: |
    python skills/software-development/code-review-agent/scripts/review_diff.py \
      --diff ${{ github.event.pull_request.diff_url }} \
      --format github \
      --post-review
```

## Pattern Library

The skill uses YAML pattern files in `.hermes/patterns/`:

- `naming.yaml` - Function/class/variable naming conventions
- `structure.yaml` - File/directory organization rules
- `imports.yaml` - Import ordering, banned imports
- `testing.yaml` - Test naming, coverage expectations

## Findings Severity

| Level | Meaning | Blocks Merge |
|-------|---------|--------------|
| `block` | Critical issue (security, breaking change, bug) | YES |
| `warn` | Should fix (style, pattern violation, minor bug risk) | Configurable |
| `info` | Nice to have (suggestion, improvement) | NO |

## Output Format

```json
{
  "findings": [
    {
      "file": "src/auth.py",
      "line": 42,
      "severity": "block",
      "category": "security",
      "rule": "hardcoded-secret",
      "message": "Hardcoded API key detected",
      "suggestion": "Use environment variable"
    }
  ],
  "summary": {
    "block": 1,
    "warn": 3,
    "info": 5
  }
}
```

## Extending

Add custom rules in `scripts/rules/`:
- Each rule is a Python class with `check(diff, context)` method
- Register in `scripts/rules/__init__.py`
- Patterns in `.hermes/patterns/` are auto-loaded