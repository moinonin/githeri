# Quick Reference: Output Modes

## Command

```bash
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_execute.py \
  --prompt "Add GET /health endpoint" \
  --output-dir ./features/health \
  --output <mode>
```

## Output Modes

| Mode | Flag | Files Created | Stops At |
|------|------|---------------|----------|
| **Spec only** | `--output spec` | `spec.yaml` | After validation |
| **Plan only** | `--output plan` | `PLAN.md` | After plan generation |
| **Plan + Runbook** | `--output plan+runbook` | `PLAN.md` + `RUNBOOK.md` | After runbook generation |
| **Full delivery** | `--output all` (default) | `spec.yaml` + `PLAN.md` + `RUNBOOK.md` + execution log | After execution |

## Examples

```bash
# Just get a validated spec
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_execute.py \
  --prompt "Add PATCH /users/:id" --output-dir ./user-patch --output spec

# Get plan for review (no execution)
python3 ... --prompt "Add rate limiting" --output-dir ./rate-limit --output plan

# Get plan + runbook for manual execution
python3 ... --prompt "Add audit logging" --output-dir ./audit --output plan+runbook

# Full autonomous delivery
python3 ... --prompt "Add health endpoint" --output-dir ./health --output all
```

## What Happens at Each Step

| Step | What Happens | File Created |
|------|--------------|--------------|
| 1. Spec Gen | Agent writes YAML spec → validates → retries up to 3x | `spec.yaml` |
| 2. Plan Gen | Assembles `PLAN.md` + `RUNBOOK.md` from spec + templates | `PLAN.md`, `RUNBOOK.md` |
| 3. Auto-approve | Checks spec score ≥ 0.75 → auto-approves | — |
| 3. Execute | Parses RUNBOOK command table → runs commands with retry/heal | `RUNBOOK.md` (execution log) |

## Files Created (by mode)

| Mode | Files |
|------|-------|
| `spec` | `spec.yaml` |
| `plan` | `PLAN.md`, `RUNBOOK.md` |
| `plan+runbook` | `PLAN.md`, `RUNBOOK.md` |
| `all` | `spec.yaml`, `PLAN.md`, `RUNBOOK.md` (with execution log) |

## Files Location

```
<output-dir>/
├── spec.yaml          # Always
├── PLAN.md            # --output plan|plan+runbook|all
├── RUNBOOK.md         # --output plan|plan+runbook|all (with exec log)
└── logs/
    └── autonomous_execution.log
```