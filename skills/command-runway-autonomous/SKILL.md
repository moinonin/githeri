---
name: command-runway-autonomous
description: "Fully autonomous execution pipeline: NL prompt → validated spec → PLAN.md + RUNBOOK.md (auto-written to disk) → auto-execution with self-healing. No human approval gates."
version: 1.0.0
author: Nous Research
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [autonomous, spec-forge, command-runway, spec-driven, plan-generation, runbook-execution, self-healing]
    related_skills: [spec-forge-unified, command-runway-planner, command-runway-pattern, spec-forge-scorer]

---

# Command Runway Autonomous

## What This Is

A **fully autonomous execution skill** that takes a natural language prompt and produces a working implementation **without human approval gates**. It combines:

1. **Spec generation** (spec-forge-unified) — NL → validated YAML spec
2. **Plan generation** (command-runway-planner) — Spec → PLAN.md + RUNBOOK.md (auto-written to disk)
3. **Execution** (command-runway-pattern) — RUNBOOK.md → executed implementation
4. **Self-healing** — Auto-retry, diagnosis, corrective action on failure
5. **Escalation** — Only alerts human on critical/blocked states

**No human approval gates.** The pipeline runs end-to-end autonomously.

---

## When To Use This Skill

- **Autonomous feature development** — "Add rate limiting to API", "Implement user profile endpoint"
- **Sprint execution** — Run entire sprint from SPRINTS.md without human gates
- **Bug fixes** — "Fix login timeout bug", "Resolve memory leak in evidence pipeline"
- **Refactoring** — "Extract validation logic to shared module"

**Don't use for:**
- Breaking changes requiring human design decisions
- Security-critical changes requiring audit
- Architecture decisions needing human judgment
- First-time project setup (use spec-forge-unified with approval gates)

---

## The Autonomous Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     COMMAND RUNWAY AUTONOMOUS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────┐ │
│  │  NL Prompt   │───▶│  Spec Gen    │───▶│  Plan Gen    │───▶│ Exec │ │
│  │  (Human)     │    │  (Auto)      │    │  (Auto)      │    │ (Auto)│ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────┘ │
│        │                   │                   │                │       │
│        ▼                   ▼                   ▼                ▼       │
│  validated YAML spec    PLAN.md +          RUNBOOK.md      working     │
│  (validated, saved)     RUNBOOK.md         (auto-executed)  software   │
│       (disk)            (disk, pre-exec)   (disk, pre-exec)            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SELF-HEALING LOOP                            │   │
│  │  1. Execute command → Check verification                        │   │
│  │  2. PASS → Next command                                         │   │
│  │  3. FAIL → Diagnose (root cause) → Corrective action → Retry   │   │
│  │  4. MAX_RETRIES exceeded → Escalate to human                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

```yaml
# ~/.hermes/skills/software-development/command-runway-autonomous/references/autonomous_config.yaml
max_retries_per_command: 3
max_retries_per_stage: 2
escalation_threshold:
  consecutive_failures: 3
  blocked_duration_minutes: 30
  critical_errors: ["security", "data_loss", "schema_migration", "permission_denied", "connection_refused", "timeout"]
auto_approve_plan: true
auto_execute_runbook: true
min_spec_score: 0.75
max_commands_per_feature: 50
max_execution_time_minutes: 60
escalation_channels:
  - "terminal"
  - "log_file"
log_file: ./logs/autonomous_execution.log
allow_destructive: false
environments:
  development:
    allow_destructive: false
    require_approval: false
  staging:
    allow_destructive: false
    require_approval: true
  production:
    allow_destructive: false
    require_approval: true
    human_approval_required: true
```

---

## Usage

### 1. Single Feature (One-off)

```bash
# From project root
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_execute.py \
  --prompt "Add GET /v1/health endpoint that returns {status: 'ok'}" \
  --output-dir ./docs/features/health-endpoint
```

### 2. Full Sprint (from SPRINTS.md)

```bash
# Execute entire sprint autonomously
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_sprint.py \
  --sprint-file SPRINTS.md \
  --sprint 5 \
  --project-root .
```

### 3. Multiple Features (Batch)

```bash
# Execute multiple features from a feature list
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_batch.py \
  --features-file features.yaml \
  --parallel 2
```

---

## Self-Healing Behavior

### On Command Failure (Per-Command)

| Attempt | Action |
|---------|--------|
| 1 | Execute command → Check verification |
| 2 | Re-read spec/PLAN → Re-execute with more context |
| 3 | Diagnose root cause → Corrective action → Retry |
| 4+ | Escalate to human |

### On Stage Failure (Per-Stage)

| Attempt | Action |
|---------|--------|
| 1 | Execute all stage commands |
| 2 | Re-read PLAN.md → Re-execute failed commands with more context |
| 3 | Full stage re-plan (agent re-generates stage commands) |

### Escalation Triggers (Human Required)

- `max_retries_per_stage` exceeded
- `consecutive_failures` > threshold
- `blocked_duration_minutes` exceeded
- Error contains: `security`, `data_loss`, `schema_migration`, `permission_denied`
- Critical infrastructure down (DB, message queue, external API)

---

## Human Escalation Interface

When escalated, the system provides:

```markdown
## 🚨 AUTONOMOUS ESCALATION

**Feature:** add-user-profile
**Stage:** 3 (Verify: POST /users returns 201)
**Command:** `pnpm test --filter=@verified-attention/api -- testPathPattern=users`
**Failures:** 3 consecutive
**Duration:** 45 minutes blocked

### Last Error
```
FAIL tests/api/users.test.ts
  ✕ POST /users returns 201
    Expected: 201
    Received: 500
    Error: duplicate key value violates unique constraint "users_email_key"
```

### Diagnosed Root Cause
- [x] Incorrect assumption: email uniqueness not checked before insert
- [ ] Missing dependency
- [ ] Incorrect implementation
- [ ] Environment problem
- [ ] Test failure
- [ ] Unexpected architecture

### Suggested Corrective Actions
1. Add email uniqueness check before INSERT (ON CONFLICT DO NOTHING)
2. Return 409 CONFLICT with error code EMAIL_EXISTS
3. Add test for duplicate email case

### Context Files
- PLAN.md: ./docs/features/add-user-profile/PLAN.md
- RUNBOOK.md: ./docs/features/add-user-profile/RUNBOOK.md
- Execution Log: ./docs/features/add-user-profile/RUNBOOK.md (Section 4)

### Options
- [ ] Apply suggested fix and resume
- [ ] Re-plan stage and resume
- [ ] Abort feature
- [ ] Human takes over
```

---

## Files

```
command-runway-autonomous/
├── references/
│   └── autonomous_config.yaml          # Configuration
├── scripts/
│   ├── autonomous_execute.py           # Single feature execution
│   ├── autonomous_sprint.py            # Sprint execution from SPRINTS.md
│   ├── autonomous_batch.py             # Batch feature execution
│   ├── diagnose.py                     # Failure diagnosis
│   ├── corrective.py                   # Corrective action generator
│   └── escalate.py                     # Human escalation
├── templates/
│   ├── escalation_template.md          # Escalation report template
│   └── diagnosis_template.md           # Root cause diagnosis template
└── SKILL.md
```

---

## Integration with Existing Skills

| Skill | Role in Autonomous Pipeline |
|-------|----------------------------|
| `spec-forge-unified` | Spec generation + validation |
| `command-runway-planner` | PLAN.md + RUNBOOK.md generation |
| `command-runway-pattern` | Execution methodology (⏾/✎/✓ commands) |
| `spec-forge-scorer` | Spec quality gate (must score ≥0.75) |
| `command-runway-pattern` | Execution semantics (⏾/✎/✓ commands) |

---

## Safety Guards

1. **No destructive commands without explicit config** — `rm -rf`, `DROP TABLE`, `git push --force` blocked unless `allow_destructive: true`
2. **No production writes without `environment: production` guard**
3. **No secret exposure** — secrets masked in logs
4. **Rollback on migration failure** — `down` migration auto-run on failure
5. **Budget limits** — max commands, max time, max tokens per feature

---

## Example: Autonomous Feature Execution

```bash
$ python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_execute.py \
  --prompt "Add PATCH /v1/users/:id endpoint for updating user profile" \
  --output-dir ./features/user-profile-patch

[2026-07-26 10:00:00] 🚀 Starting autonomous execution: add-user-profile-patch
[2026-07-26 10:00:01] 📝 Generating validated spec...
[2026-07-26 10:00:03] ✅ Spec validated (score: 0.87)
[2026-07-26 10:00:04] 📐 Generating PLAN.md + RUNBOOK.md...
[2026-07-26 10:00:04] ✅ Plan generated: 4 stages, 12 commands
[2026-07-26 10:00:04] 🔒 Auto-approving plan (score: 0.87 ≥ 0.75)
[2026-07-26 10:00:04] 📝 PLAN.md written to ./docs/features/user-profile-patch/PLAN.md
[2026-07-26 10:00:04] 📝 RUNBOOK.md written to ./docs/features/user-profile-patch/RUNBOOK.md
[2026-07-26 10:00:04] ⚡ Executing RUNBOOK...
[2026-07-26 10:00:05]   Stage 1: CREATE PATCH endpoint - PASS
[2026-07-26 10:00:07]   Stage 2: VERIFY 200 response - PASS
[2026-07-26 10:00:08]   Stage 3: VERIFY 404 for invalid ID - PASS
[2026-07-26 10:00:09]   Stage 4: VERIFY 400 for invalid body - PASS
[2026-07-26 10:00:10] ✅ Feature complete: add-user-profile-patch
[2026-07-26 10:00:10] 📊 Execution log: ./docs/features/user-profile-patch/RUNBOOK.md
```

---

## PLAN.md Before Execution

**PLAN.md is ALWAYS written to disk BEFORE execution starts.** The autonomous script:

```python
# In autonomous_execute.py
def main():
    # 1. Generate spec
    spec = generate_spec(prompt, output_dir)
    
    # 2. Generate PLAN.md (WRITTEN TO DISK BEFORE EXECUTION)
    plan_path = generate_plan(spec, output_dir)
    print(f"\n📋 PLAN.md available for review at: {plan_path}")
    print("   (Auto-approval enabled - proceeding to execution)")
    print()
    
    # 3. Execute RUNBOOK.md
    success = execute_runbook(runbook_path, config)
```

**PLAN.md is available on disk before any execution command runs.** This satisfies the requirement.

---

## Safety Guards

1. **No destructive commands without explicit config** — `rm -rf`, `DROP TABLE`, `git push --force` blocked unless `allow_destructive: true`
2. **No production writes without `environment: production` guard**
3. **No secret exposure** — secrets masked in logs
4. **Rollback on migration failure** — `down` migration auto-run on failure
5. **Budget limits** — max commands, max time, max tokens per feature

---

## Agent-Agnostic Execution (Any AI Agent)

The autonomous pipeline is designed to work with **any AI agent** that can:
1. Read files from disk (spec.yaml, PLAN.md, RUNBOOK.md)
2. Execute shell commands
3. Write files to disk

### Supported Execution Backends

| Backend | Flag | How It Works |
|---------|------|--------------|
| **Python (built-in)** | `--executor python` | Internal Python LLM client (OpenAI-compatible HTTP API) |
| **Hermes** | `--executor hermes` | `hermes chat -q "Execute RUNBOOK at <path>" --yolo` |
| **OpenCode** | `--executor opencode` | `opencode run "Execute RUNBOOK at <path>"` |
| **Claude Code** | `--executor claude` | `claude -p "Execute RUNBOOK at <path>"` |
| **Codex** | `--executor codex` | `codex exec "Execute RUNBOOK at <path>"` |
| **Custom** | `--executor custom --executor-cmd "..."` | Any CLI agent that accepts a prompt |

### Adding a New Backend

```python
# In autonomous_execute.py, add to execute_runbook():
elif executor == "your-agent":
    success = execute_with_your_agent(runbook_path, args)

def execute_with_your_agent(runbook_path: Path, args) -> bool:
    # Your agent's CLI invocation here
    cmd = ["your-agent", "run", f"Execute RUNBOOK at {runbook_path}"]
    return subprocess.run(cmd).returncode == 0
```

### Requirements for Any Agent

The agent must be able to:
1. **Read** `spec.yaml`, `PLAN.md`, `RUNBOOK.md` from the output directory
2. **Parse** the RUNBOOK command table (C1, C2, C3... with types ⏾/✎/✓)
3. **Execute** each command in order, respecting dependencies
4. **Verify** each command's expected result (exit code, file existence, grep match, HTTP status)
5. **Write** updated execution log back to RUNBOOK.md (Section 4)
6. **On failure**: Diagnose, correct, retry (up to `max_retries`)

### Universal RUNBOOK Format

The RUNBOOK.md uses a standard markdown table that any agent can parse:

```markdown
### Stage 1: CREATE Health Endpoint

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | search for it |
| C2 | — | ⏾ inspect | `pnpm --version` | version string | install or halt |
| C3 | C1,C2 | ✎ create | `write_file packages/api/src/health.ts` | new file on disk | revert, re-read spec |
| C4 | C3 | ✓ verify | `test -f packages/api/src/health.ts && grep -q 'export' packages/api/src/health.ts` | expected result, exit 0 | revert, re-prompt |

**Legend:** ⏾ = inspect/read, ✎ = create/modify, ✓ = verify/run
```

---

## Agent-Agnostic Execution (Any AI Agent)

The autonomous pipeline is designed to work with **any AI agent** that can:
1. Read files from disk (spec.yaml, PLAN.md, RUNBOOK.md)
2. Execute shell commands
3. Write files to disk

### Supported Execution Backends

| Backend | Flag | How It Works |
|---------|------|--------------|
| **Python (built-in)** | `--executor python` | Internal Python LLM client (OpenAI-compatible HTTP API) |
| **Hermes** | `--executor hermes` | `hermes chat -q "Execute RUNBOOK at <path>" --yolo` |
| **OpenCode** | `--executor opencode` | `opencode run "Execute RUNBOOK at <path>"` |
| **Claude Code** | `--executor claude` | `claude -p "Execute RUNBOOK at <path>"` |
| **Codex** | `--executor codex` | `codex exec "Execute RUNBOOK at <path>"` |
| **Custom** | `--executor custom --executor-cmd "..."` | Any CLI agent that accepts a prompt |

### Adding a New Backend

```python
# In autonomous_execute.py, add to execute_runbook():
elif executor == "your-agent":
    success = execute_with_your_agent(runbook_path, args)

def execute_with_your_agent(runbook_path: Path, args) -> bool:
    # Your agent's CLI invocation here
    cmd = ["your-agent", "run", f"Execute RUNBOOK at {runbook_path}"]
    return subprocess.run(cmd).returncode == 0
```

### Requirements for Any Agent

The agent must be able to:
1. **Read** `spec.yaml`, `PLAN.md`, `RUNBOOK.md` from the output directory
2. **Parse** the RUNBOOK command table (C1, C2, C3... with types ⏾/✎/✓)
3. **Execute** each command in order, respecting dependencies
4. **Verify** each command's expected result (exit code, file existence, grep match, HTTP status)
5. **Write** updated execution log back to RUNBOOK.md (Section 4)
6. **On failure**: Diagnose, correct, retry (up to `max_retries`)

### Universal RUNBOOK Format

The RUNBOOK.md uses a standard markdown table that any agent can parse:

```markdown
### Stage 1: CREATE Health Endpoint

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | search for it |
| C2 | — | ⏾ inspect | `pnpm --version` | version string | install or halt |
| C3 | C1,C2 | ✎ create | `write_file packages/api/src/health.ts` | new file on disk | revert, re-read spec |
| C4 | C3 | ✓ verify | `test -f packages/api/src/health.ts && grep -q 'export' packages/api/src/health.ts` | expected result, exit 0 | revert, re-prompt |

**Legend:** ⏾ = inspect/read, ✎ = create/modify, ✓ = verify/run
```

---

## The Monster Assessment (Honest)

### What "The Monster" Means

A fully autonomous coding agent that takes a natural language prompt and produces working, tested, production-ready code — **no human in the loop**.

### Current State

| Component | Status | Notes |
|-----------|--------|-------|
| **Brain** (NL → Spec) | ✅ 95% | LLM spec generation works; validator catches errors |
| **Spine** (Spec → PLAN + RUNBOOK) | ✅ 100% | `assemble_plan.py` + `assemble_runbook.py` — deterministic |
| **Muscle** (RUNBOOK → Files) | ✅ 80% | Python executor works; Hermes/Codex need more testing |
| **Self-Healing** | ✅ 70% | Retry + diagnose + correct works; needs better root-cause analysis |
| **Code Review Gate** | ❌ 0% | No automated quality review before merge |
| **Production Deploy** | ❌ 0% | No CI/CD integration, no rollback |
| **Observability** | ❌ 20% | Basic logs only; no metrics dashboard |
| **Multi-Feature Orchestration** | ❌ 10% | Batch/sprint scripts exist but untested |

### Honest Distance to "The Monster"

```
████████████░░░░░░░░░░  65%
```

**We have the brain, spine, and partial muscle. The monster is not fully alive.**

### What's Missing for True Autonomy

1. **Code Review Agent** — LLM that reads diff, runs linter/typecheck, enforces patterns, blocks bad merges
2. **CI/CD Integration** — Auto-create PR, run checks, merge on green, rollback on failure
3. **Cost/Performance Observatory** — Token usage, latency, success rate per feature type
4. **Sprint Orchestrator** — Parallel execution of multiple features with dependency resolution
5. **Production Guardrails** — Canary deploy, health checks, auto-rollback on anomaly

### Time to Monster (Estimated)

| Effort | Component |
|--------|-----------|
| 1-2 weeks | Code review agent + CI/CD integration |
| 1 week | Cost observability dashboard |
| 2-3 weeks | Sprint orchestrator + parallel execution |
| 1 week | Production guardrails |

**Total: ~5-7 weeks of focused engineering** to reach a production-grade autonomous agent.

---

## Origin

Built on the Spec-Forge + Command-Runway two-skill workflow (VAE Sprint 6), extended with autonomous execution, self-healing, and escalation for fully hands-off feature development.