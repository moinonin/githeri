# Autonomous Agent Completion Sprints

**Goal:** Transform the current spec→plan→execute pipeline into a production-grade autonomous coding agent ("The Monster").

**Current State:** 65% complete (Brain + Spine + Partial Muscle)
**Target:** 100% (Full autonomy with code review, CI/CD, observability, sprint orchestration, production guardrails)

---

## Sprint 8 — Code Review Agent (The Quality Gate)

**Objective:** Build an LLM-powered code review agent that reads diffs, runs linters/typechecks, enforces patterns, and blocks bad merges.

**Duration:** 1-2 weeks

### Deliverables

1. **Code Review Skill** (`~/.hermes/skills/software-development/code-review-agent/`)
   - `scripts/review_diff.py` — Reads git diff, outputs structured review
   - `scripts/enforce_patterns.py` — Checks against project patterns (naming, structure, imports)
   - `scripts/security_scan.py` — Secret scanning, vulnerability patterns, license checks
   - `SKILL.md` — Documentation for agent integration

2. **Review Pipeline Integration**
   - `make review SPEC=<spec>` — Runs review on changes from a spec
   - `make review-pr PR=<num>` — Reviews GitHub PR diff
   - Configurable severity thresholds (block/warn/info)

3. **Pattern Library** (`.hermes/patterns/`)
   - `naming.yaml` — Function/class/variable naming conventions
   - `structure.yaml` — File/directory organization rules
   - `imports.yaml` — Import ordering, banned imports
   - `testing.yaml` — Test naming, coverage expectations

### Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `make review SPEC=test-feature` | Review JSON output with findings |
| L2 | `make review-pr PR=123` | GitHub PR review posted with findings |
| L3 | `python -m pytest tests/test_code_review.py` | 100% tests pass |
| L4 | `make validate-patterns` | Zero pattern violations in repo |

### Spec for Sprint 8

```yaml
task_id: sprint8-code-review-agent
summary: "Build LLM-powered code review agent with pattern enforcement, security scanning, and CI/CD integration"
depends_on: []
local_goals:
  - id: L1
    description: "CREATE: Code review skill with diff analysis and pattern enforcement"
    verification:
      type: file_exists
      path: skills/software-development/code-review-agent/SKILL.md
      expect:
        content_contains: "code-review-agent"
  - id: L2
    description: "CREATE: Review diff script with structured output (findings: block/warn/info)"
    verification:
      type: file_exists
      path: skills/software-development/code-review-agent/scripts/review_diff.py
      expect:
        content_contains: "block\|warn\|info"
  - id: L3
    description: "CREATE: Pattern library with naming, structure, imports, testing rules"
    verification:
      type: file_exists
      path: .hermes/patterns/naming.yaml
      expect:
        exists: true
  - id: L4
    description: "CREATE: Security scanner for secrets, vulnerabilities, license issues"
    verification:
      type: file_exists
      path: skills/software-development/code-review-agent/scripts/security_scan.py
      expect:
        content_contains: "secret\|vulnerab"
  - id: L5
    description: "VERIFY: Review agent catches injected bugs in test diffs"
    verification:
      type: cli
      command: "python skills/software-development/code-review-agent/scripts/review_diff.py --diff tests/fixtures/buggy.diff --format json"
      expect:
        exit_code: 0
        stdout_contains: "block"
  - id: L6
    description: "VERIFY: Pattern enforcement passes on clean code, fails on violations"
    verification:
      type: cli
      command: "python skills/software-development/code-review-agent/scripts/enforce_patterns.py --path . --strict"
      expect:
        exit_code: 0
context:
  language: Python
  framework: Hermes
  test_framework: pytest
```

---

## Sprint 9 — CI/CD Integration (The Automation Gate)

**Objective:** Auto-create PRs, run checks, merge on green, rollback on failure.

**Duration:** 1-2 weeks

### Deliverables

1. **CI/CD Skill** (`~/.hermes/skills/software-development/ci-cd-integration/`)
   - `scripts/create_pr.py` — Creates GitHub PR from spec changes
   - `scripts/run_checks.py` — Runs lint, typecheck, test, build
   - `scripts/merge_on_green.py` — Merges when all checks pass
   - `scripts/rollback.py` — Reverts merge on failure

2. **GitHub Actions Workflow** (`.github/workflows/autonomous.yml`)
   - Trigger: PR opened/updated by autonomous agent
   - Jobs: lint → typecheck → test → build → security
   - Merge: Auto-merge when all green + approved

3. **PR Template** (`.github/PULL_REQUEST_TEMPLATE/autonomous.md`)
   - Links to spec, plan, runbook
   - Checklist: verification gates passed
   - Rollback instructions

### Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `make create-pr SPEC=sprint8-code-review-agent` | PR created with spec changes |
| L2 | `make run-checks PR=123` | All CI jobs pass (lint, typecheck, test, build) |
| L3 | `make merge-on-green PR=123` | PR merged when all green |
| L4 | `make rollback PR=123` | Merge reverted, main branch restored |

### Spec for Sprint 9

```yaml
task_id: sprint9-ci-cd-integration
summary: "Build CI/CD integration for autonomous agent: auto-PR, checks, merge-on-green, rollback"
depends_on: ["sprint8-code-review-agent"]
local_goals:
  - id: L1
    description: "CREATE: CI/CD skill with PR creation, check execution, merge, rollback"
    verification:
      type: file_exists
      path: skills/software-development/ci-cd-integration/SKILL.md
      expect:
        content_contains: "ci-cd-integration"
  - id: L2
    description: "CREATE: GitHub Actions workflow for autonomous PRs"
    verification:
      type: file_exists
      path: .github/workflows/autonomous.yml
      expect:
        content_contains: "autonomous"
  - id: L3
    description: "CREATE: PR creation script from spec changes"
    verification:
      type: file_exists
      path: skills/software-development/ci-cd-integration/scripts/create_pr.py
      expect:
        content_contains: "create_pr"
  - id: L4
    description: "CREATE: Check runner (lint, typecheck, test, build, security)"
    verification:
      type: file_exists
      path: skills/software-development/ci-cd-integration/scripts/run_checks.py
      expect:
        content_contains: "lint\|typecheck\|test\|build"
  - id: L5
    description: "CREATE: Auto-merge on green, rollback on failure"
    verification:
      type: file_exists
      path: skills/software-development/ci-cd-integration/scripts/merge_on_green.py
      expect:
        content_contains: "merge\|rollback"
  - id: L5
    description: "VERIFY: Full cycle - spec → PR → checks → merge"
    verification:
      type: cli
      command: "make autonomous-cycle SPEC=test-endpoint"
      expect:
        exit_code: 0
        stdout_contains: "merged"
context:
  language: Python
  framework: GitHub Actions
  test_framework: pytest
```

---

## Sprint 10 — Cost/Performance Observatory (The Dashboard)

**Objective:** Token usage, latency, success rate per feature type; alerting on anomalies.

**Duration:** 1 week

### Deliverables

1. **Observability Skill** (`~/.hermes/skills/software-development/observability/`)
   - `scripts/collect_metrics.py` — Collects tokens, latency, success/fail per feature
   - `scripts/dashboard.py` — Generates HTML/JSON dashboard
   - `scripts/alerting.py` — Alerts on anomalies (cost spike, failure rate, latency)

2. **Metrics Database** (`metrics/autonomous.db`)
   - SQLite schema: runs, features, tokens, latency, status, cost
   - Retention: 90 days

3. **Dashboard** (`dashboard/autonomous.html`)
   - Real-time: tokens/sec, latency p50/p99, success rate
   - Historical: trends, feature-type breakdown
   - Anomalies: highlighted with severity

### Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `make collect-metrics` | Metrics written to SQLite |
| L2 | `make dashboard` | HTML dashboard generated |
| L3 | `make alert-check` | Anomalies detected and logged |
| L4 | `make metrics-report` | Summary report generated |

### Spec for Sprint 10

```yaml
task_id: sprint10-observability-dashboard
summary: "Build cost/performance observability: token tracking, latency, success rates, anomaly alerting"
depends_on: ["sprint9-ci-cd-integration"]
local_goals:
  - id: L1
    description: "CREATE: Observability skill with metrics collection and dashboard"
    verification:
      type: file_exists
      path: skills/software-development/observability/SKILL.md
      expect:
        content_contains: "observability"
  - id: L2
    description: "CREATE: Metrics collector (tokens, latency, success, cost per feature)"
    verification:
      type: file_exists
      path: skills/software-development/observability/scripts/collect_metrics.py
      expect:
        content_contains: "tokens\|latency\|success"
  - id: L3
    description: "CREATE: SQLite metrics database with 90-day retention"
    verification:
      type: file_exists
      path: metrics/autonomous.db
      expect:
        exists: true
  - id: L4
    description: "CREATE: HTML dashboard with real-time and historical views"
    verification:
      type: file_exists
      path: dashboard/autonomous.html
      expect:
        exists: true
  - id: L5
    description: "CREATE: Anomaly alerting (cost spike, failure rate, latency)"
    verification:
      type: file_exists
      path: skills/software-development/observability/scripts/alerting.py
      expect:
        content_contains: "alert\|anomaly"
  - id: L6
    description: "VERIFY: Dashboard shows real data after autonomous run"
    verification:
      type: cli
      command: "make autonomous-cycle SPEC=test-feature && make dashboard"
      expect:
        exit_code: 0
        stdout_contains: "dashboard"
context:
  language: Python
  framework: SQLite/HTML
  test_framework: pytest
```

---

## Sprint 11 — Sprint Orchestrator (The Conductor)

**Objective:** Parallel execution of multiple features with dependency resolution.

**Duration:** 2-3 weeks

### Deliverables

1. **Orchestrator Skill** (`~/.hermes/skills/software-development/sprint-orchestrator/`)
   - `scripts/orchestrator.py` — Reads SPRINTS.md, resolves deps, runs parallel
   - `scripts/dependency_graph.py` — Builds DAG from sprint dependencies
   - `scripts/resource_manager.py` — Manages parallel workers, GPU/CPU allocation

2. **SPRINTS.md Enhancement**
   - Dependency syntax: `depends_on: ["sprint8", "sprint9"]`
   - Parallel groups: `parallel_group: "group-a"`
   - Resource hints: `requires_gpu: true`, `memory_gb: 8`

3. **Worker Pool** (`scripts/worker_pool.py`)
   - Manages N parallel autonomous agents
   - Tracks progress, failures, retries
   - Reports aggregate status

### Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `make orchestrate SPRINTS=SPRINTS.md` | All sprints executed in correct order |
| L2 | `make parallel SPRINTS=SPRINTS.md --workers 3` | 3 features run in parallel |
| L3 | `make dependency-check SPRINTS=SPRINTS.md` | No circular deps, valid DAG |
| L4 | `make resource-report` | GPU/CPU/memory usage reported |

### Spec for Sprint 11

```yaml
task_id: sprint11-sprint-orchestrator
summary: "Build sprint orchestrator for parallel feature execution with dependency resolution"
depends_on: ["sprint10-observability-dashboard"]
local_goals:
  - id: L1
    description: "CREATE: Orchestrator skill with DAG resolution and parallel execution"
    verification:
      type: file_exists
      path: skills/software-development/sprint-orchestrator/SKILL.md
      expect:
        content_contains: "sprint-orchestrator"
  - id: L2
    description: "CREATE: Dependency graph builder from SPRINTS.md"
    verification:
      type: file_exists
      path: skills/software-development/sprint-orchestrator/scripts/dependency_graph.py
      expect:
        content_contains: "depends_on\|DAG"
  - id: L3
    description: "CREATE: Parallel worker pool with resource management"
    verification:
      type: file_exists
      path: skills/software-development/sprint-orchestrator/scripts/worker_pool.py
      expect:
        content_contains: "parallel\|worker\|gpu"
  - id: L4
    description: "CREATE: SPRINTS.md dependency syntax and parallel groups"
    verification:
      type: file_exists
      path: docs/SPRINTS.md
      expect:
        content_contains: "depends_on\|parallel_group"
  - id: L5
    description: "VERIFY: Orchestrator runs 3 sprints in parallel with correct deps"
    verification:
      type: cli
      command: "make orchestrate SPRINTS=test_sprints.md --workers 3 --dry-run"
      expect:
        exit_code: 0
        stdout_contains: "parallel"
  - id: L6
    description: "VERIFY: Dependency graph is valid (no cycles, valid DAG)"
    verification:
      type: cli
      command: "make dependency-check SPRINTS=SPRINTS.md"
      expect:
        exit_code: 0
        stdout_contains: "valid"
context:
  language: Python
  framework: Hermes
  test_framework: pytest
```

---

## Sprint 12 — Production Guardrails (The Shield)

**Objective:** Canary deploy, health checks, auto-rollback, secret scanning.

**Duration:** 1 week

### Deliverables

1. **Guardrails Skill** (`~/.hermes/skills/software-development/production-guardrails/`)
   - `scripts/canary_deploy.py` — Deploys to canary, monitors health
   - `scripts/health_checks.py` — Runs liveness/readiness/startup probes
   - `scripts/auto_rollback.py` — Rolls back on health degradation
   - `scripts/secret_scanner.py` — Scans code/secrets/configs before deploy

2. **Deployment Config** (`deploy/guardrails.yaml`)
   - Canary: 5% traffic, 10 min monitoring
   - Health: latency p99 < 500ms, error rate < 0.1%
   - Rollback: auto on 3 consecutive failures

3. **Pre-Deploy Gates** (`scripts/pre_deploy_gates.py`)
   - Secret scan (truffleHog, git-secrets)
   - License check (FOSSA, licensee)
   - Dependency audit (npm audit, pip-audit, cargo audit)

### Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `make secret-scan` | Zero secrets found |
| L2 | `make license-check` | All deps compatible |
| L3 | `make canary-deploy FEATURE=my-feature` | Canary deployed, monitored |
| L4 | `make health-check SERVICE=my-service` | All probes pass |
| L5 | `make auto-rollback SERVICE=my-service` | Rollback on degradation |

### Spec for Sprint 12

```yaml
task_id: sprint12-production-guardrails
summary: "Build production guardrails: canary deploy, health checks, auto-rollback, secret scanning"
depends_on: ["sprint11-sprint-orchestrator"]
local_goals:
  - id: L1
    description: "CREATE: Guardrails skill with canary, health, rollback, secrets"
    verification:
      type: file_exists
      path: skills/software-development/production-guardrails/SKILL.md
      expect:
        content_contains: "production-guardrails"
  - id: L2
    description: "CREATE: Canary deployment with traffic splitting and monitoring"
    verification:
      type: file_exists
      path: skills/software-development/production-guardrails/scripts/canary_deploy.py
      expect:
        content_contains: "canary\|traffic"
  - id: L3
    description: "CREATE: Health checks (liveness, readiness, startup) with auto-rollback"
    verification:
      type: file_exists
      path: skills/software-development/production-guardrails/scripts/health_checks.py
      expect:
        content_contains: "liveness\|readiness\|rollback"
  - id: L4
    description: "CREATE: Secret scanner for code, configs, env files"
    verification:
      type: file_exists
      path: skills/software-development/production-guardrails/scripts/secret_scanner.py
      expect:
        content_contains: "secret\|truffleHog"
  - id: L4
    description: "CREATE: License and dependency audit gates"
    verification:
      type: file_exists
      path: skills/software-development/production-guardrails/scripts/license_check.py
      expect:
        content_contains: "license\|audit"
  - id: L5
    description: "VERIFY: Full guardrails pipeline - scan → canary → health → rollback"
    verification:
      type: cli
      command: "make guardrails-pipeline FEATURE=test-feature"
      expect:
        exit_code: 0
        stdout_contains: "guardrails complete"
context:
  language: Python
  framework: Kubernetes/Docker
  test_framework: pytest
```

---

## Execution Order

```
Sprint 8  → Sprint 9  → Sprint 10  → Sprint 11  → Sprint 12
(Code Review) (CI/CD) (Observability) (Orchestrator) (Guardrails)
   │           │            │              │              │
   ▼           ▼            ▼              ▼              ▼
Quality    Automation   Visibility    Parallel      Production
Gate       Pipeline     Dashboard     Execution     Ready
```

---

## Meta-Execution: Using the Pipeline to Build Itself

Each sprint spec above can be executed via:

```bash
# For each sprint:
make spec-and-plan PROMPT_FILE=sprints/sprint8-code-review-agent.spec.yaml
make autonomous-execute SPEC=sprints/sprint8-code-review-agent.spec.yaml --output-dir docs/features/sprint8
```

**Reporting:** After each sprint, run:
```bash
make sprint-report SPRINT=sprint8
```

Outputs: `docs/sprints/sprint8-report.md` with:
- Spec compliance (which L goals passed/failed)
- Execution log (from RUNBOOK.md)
- Metrics (tokens, time, cost)
- Blocker analysis
- Next sprint adjustments

---

## Sprint 0 — Bootstrap (Run First)

**Objective:** Set up the sprint execution infrastructure.

```yaml
task_id: sprint0-bootstrap
summary: "Bootstrap sprint execution infrastructure: spec templates, report generator, meta-Makefile"
local_goals:
  - id: L1
    description: "CREATE: Sprint spec template with all required fields"
    verification:
      type: file_exists
      path: sprints/TEMPLATE.spec.yaml
  - id: L2
    description: "CREATE: Meta-Makefile for sprint execution and reporting"
    verification:
      type: file_exists
      path: Makefile.sprints
  - id: L3
    description: "CREATE: Sprint report generator"
    verification:
      type: file_exists
      path: scripts/sprint_report.py
```

---

## Start Command

```bash
# Begin autonomous agent completion
cd /Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri
make spec-and-plan PROMPT_FILE=sprints/sprint0-bootstrap.spec.yaml
make autonomous-execute SPEC=sprints/sprint0-bootstrap.spec.yaml --output-dir docs/sprints/sprint0
```
---
## Current Autonomous System Status (As of Implementation)

The autonomous execution pipeline has reached approximately 65% completion toward a fully autonomous coding agent ("The Monster"). Here's what has been implemented:

### Core Pipeline Components
1. **NL Prompt -> Spec Generation**
   - Uses project-context-aware LLM prompting (detects Python/Node/Go/Rust)
   - Generates validated YAML specs with canonical vocabulary
   - Includes validation against expectation formats and goal uniqueness

2. **Spec -> PLAN.md + RUNBOOK.md Generation**
   - Uses deterministic plan generation from spec-forge and command-runway-planner skills
   - **Critical requirement met**: PLAN.md is written to disk BEFORE any execution begins
   - RUNBOOK.md contains executable command runway with verification criteria
   - Uses ⏾ (inspect), ✎ (create), ✓ (verify) notation for command types

3. **Execution Engine with Self-Healing**
   - Parses RUNBOOK.md to extract stages and commands with dependencies
   - Detects project type for appropriate tooling (pip/pnpm/go/cargo)
   - Installs dependencies based on project type
   - Executes commands in dependency order:
     - Create commands: Uses LLM to generate file content
     - Verify commands: Executes shell commands and checks expectations
   - Self-healing mechanism: On verification failure, identifies failed create command and regenerates with error context
   - Updates execution log in RUNBOOK.md with timestamps, exit codes, retry counts, and output snippets
   - Stops execution if any verification fails after max retries exhausted

4. **Docker Integration (Addresses Gap 3 & 4)**
   - Optional --docker flag for isolated execution
   - Generates appropriate Dockerfile based on detected project type
   - Builds image with output directory as build context (small, fast)
   - Mounts project directory and skill directory at runtime
   - Runs execution phase inside container with --output execute-only
   - Automatically cleans up container after execution (--rm)
   - Includes intelligent .dockerignore to exclude large directories (.venv, models, etc.)

5. **Supporting Components & Skills**
   - command-runway-planner: Generates PLAN.md/RUNBOOK.md from spec
   - command-runway-pattern: Defines execution methodology
   - spec-forge-unified: Generates validated specs from NL prompts
   - spec-forge-scorer: Evaluates spec quality (≥0.75 threshold)
   - observability: Collects metrics and generates dashboards
   - sprint-orchestrator: Enables parallel execution of multiple features
   - production-guardrails: Provides canary deployment, health checks, auto-rollback

### Current Capabilities Assessment

Based on the skill documentation's "Monster Assessment":

| Component | Status | Notes |
|-----------|--------|-------|
| **Brain** (NL → Spec) | ✅ 95% | LLM spec generation works; validator catches errors |
| **Spine** (Spec → PLAN+RUNBOOK) | ✅ 100% | Deterministic plan generation |
| **Muscle** (RUNBOOK → Files) | ✅ 80% | Python executor works; Hermes/Codex need more testing |
| **Self-Healing** | ✅ 70% | Retry+diagnose+correct works; needs better root-cause analysis |
| **Code Review Gate** | ❌ 0% | No automated quality review before merge |
| **Production Deploy** | ❌ 0% | No CI/CD integration, no rollback |
| **Observability** | ❌ 20% | Basic logs only; no metrics dashboard |
| **Multi-Feature Orchestration** | ❌ 10% | Batch/sprint scripts exist but untested |

**Overall: ~65% complete** toward a fully autonomous agent ("The Monster")

### Verified Ways to Run the Autonomous System

#### 1. Local Execution (Host Environment)
```bash
# Basic usage with default model (qwen2.5-coder:7b-instruct via Ollama)
python3 run_autonomous.py --prompt "Add a POST /notifications endpoint that sends email and push notifications"

# Specify custom model and provider
python3 run_autonomous.py --prompt "Add user authentication" --model anthropic/claude-sonnet-4 --provider openrouter --api-key $OPENROUTER_API_KEY

# Use Hermes as the execution backend
python3 run_autonomous.py --prompt "Implement rate limiting" --executor hermes

# Use OpenCode as the execution backend
python3 run_autonomous.py --prompt "Add data validation middleware" --executor opencode

# Enable verbose output for debugging
python3 run_autonomous.py --prompt "Create REST API for blog posts" --verbose

# Custom output directory
python3 run_autonomous.py --prompt "Implement file upload endpoint" --output-dir ./features/file-upload

# Increase retries and timeout for complex features
python3 run_autonomous.py --prompt "Implement real-time chat with WebSockets" --max-retries 5 --timeout 300
```

#### 2. Docker-Isolated Execution (Clean Environment)
```bash
# Basic Docker execution (auto-generates Dockerfile based on project type)
python3 run_autonomous.py --prompt "Add payment processing endpoint" --docker

# Docker execution with custom model
python3 run_autonomous.py --prompt "Implement machine learning pipeline" --model specforge-128k:latest --docker

# Docker execution with Hermes executor
python3 run_autonomous.py --prompt "Add real-time notifications" --executor hermes --docker

# Use pre-built Docker image (skips build step)
python3 run_autonomous.py --prompt "Process data streams" --docker --docker-image my-custom-image:latest

# Specify custom Dockerfile directory
python3 run_autonomous.py --prompt "Build microservice" --docker --dockerfile-dir ./custom-dockerfiles
```

#### 3. Makefile Commands (Project-Level Operations)
```bash
# Generate validated spec from natural language prompt
make spec PROMPT="Add user profile management endpoint"

# End-to-end: prompt -> validated spec -> plan prompt
make spec-and-plan PROMPT="Implement file upload with virus scanning"

# Generate N prompt-spec pairs for training data
make generate N=20

# Validate all specs in training corpus
make validate

# Validate a single spec file
make validate-one SPEC=specs/user-management.yaml

# Emit COMMAND_RUNWAY plan prompt for a validated spec
make plan SPEC=specs/user-management.yaml

# Score all specs against runbook criteria
make score

# Convert training data to chat format for fine-tuning
make convert-chat MIN_SCORE=0.75

# Run LoRA fine-tuning on qwen2.5-coder-7b
make train

# Merge adapter and export GGUF for Ollama
make merge

# Evaluate fine-tuned model on held-out prompts
make eval-model

# Upload model to HuggingFace Hub
make upload-hf REPO=myorg/my-finetuned-model

# Run observability dashboard generation
make dashboard

# Collect metrics from autonomous run
make metrics-collect SPRINT=sprint5

# Check for anomalies in metrics
make alerts

# Run sprint orchestrator (parallel execution)
make orchestrate SPRINTS=SPRINTS.md --workers 3

# Run autonomous cycle: spec -> plan -> runbook -> execute -> report
make autonomous-cycle SPEC=specs/test-endpoint.yaml

# Full pipeline with Docker isolation
make autonomous-cycle SPEC=specs/test-endpoint.yaml && make dashboard

# Install/uninstall spec-forge skill
make install-skill
make uninstall-skill

# Run test suite
make test

# Clean output files
make clean
```

#### 4. Direct Skill Usage (Advanced)
```bash
# Spec generation only (using spec-forge-unified skill)
python3 ~/.hermes/skills/spec-forge/scripts/run_pipeline.py --prompt "Add REST API for task management"

# Plan generation only (using command-runway-planner skill)
python3 ~/.hermes/skills/software-development/command-runway-planner/scripts/assemble_plan.py spec.yaml ./output/

# Autonomous execution only (using command-runway-autonomous skill)
python3 ~/.hermes/skills/software-development/command-runway-autonomous/scripts/autonomous_execute.py   --prompt "Add GraphQL endpoint for user data"   --output-dir ./output/   --output all
```

#### 5. Sprint-Based Execution
```bash
# Execute a specific sprint from SPRINTS.md
make autonomous-execute SPEC=sprints/sprint5.spec.yaml --output-dir docs/sprints/sprint5

# Execute sprint with Docker isolation
make autonomous-execute SPEC=sprints/sprint5.spec.yaml --output-dir docs/sprints/sprint5 --docker

# Generate sprint report after execution
make sprint-report SPRINT=sprint5

# Run meta-execution: use the pipeline to build the pipeline itself
# (Execute sprint specs to implement sprint functionality)
make spec-and-plan PROMPT_FILE=sprints/sprint8-code-review-agent.spec.yaml
make autonomous-execute SPEC=sprints/sprint8-code-review-agent.spec.yaml --output-dir docs/features/sprint8
```

### Expected Outputs

After successful execution, the system produces:

1. **spec.yaml** - Validated feature specification
2. **PLAN.md** - Implementation plan with stages and goals
3. **RUNBOOK.md** - Executable command runway with verification criteria (updated with execution log)
4. **Generated source code** - Files created according to the plan
5. **Modified source code** - Existing files updated as needed
6. **Execution log** - Embedded in RUNBOOK.md showing command results, timing, and retries
7. **Metrics** - Stored in metrics/autonomous.db (when observability enabled)
8. **Dashboard** - HTML visualization at dashboard/autonomous.html (when observability enabled)

### Troubleshooting

Common issues and solutions:

1. **"LLM connection error"**
   - Ensure Ollama is running: `ollama serve`
   - Verify model is available: `ollama list`
   - Check API key for cloud providers

2. **"Docker build failed"**
   - Increase Docker resources (memory, CPU)
   - Check .dockerexclude for necessary files
   - Verify Dockerfile syntax for detected project type

3. **"Verification failed after max retries"**
   - Check RUNBOOK.md execution log for specific error
   - Consider simplifying the prompt or breaking into smaller features
   - Manual intervention may be needed for complex logic issues

4. **"Permission denied"**
   - Ensure script files are executable: `chmod +x ~/.hermes/skills/*/scripts/*.py`
   - Check file ownership in mounted directories

5. **"Module not found"**
   - Ensure Python virtual environment is activated if using venv
   - Install required packages: `pip install pyyaml`
   - Verify skill installation: `ls ~/.hermes/skills/`

### Next Planned Improvements

Based on the sprint roadmap, upcoming enhancements include:

1. **Sprint 8**: Code Review Agent (quality gate with linters, typechecks, pattern enforcement)
2. **Sprint 9**: CI/CD Integration (auto-PR, checks, merge-on-green, rollback)
3. **Sprint 10**: Cost/Performance Observatory (token tracking, latency monitoring, alerting)
4. **Sprint 11**: Sprint Orchestrator (parallel execution with dependency resolution)
5. **Sprint 12**: Production Guardrails (canary deployment, health checks, auto-rollback, secret scanning)

Each sprint builds upon the previous ones to progressively achieve full autonomy ("The Monster").
