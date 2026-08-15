# githeri

**Spec-Forge**: a pipeline that trains an AI to bridge the gap between a human's natural-language feature request and a machine-executable specification that feeds the COMMAND_RUNWAY skill.

The central thesis: most time in AI-assisted development is lost before the AI and the human agree on what to build. Githeri attacks that by producing validated, structured YAML specs — which then feed into COMMAND_RUNWAY runbooks that an executor agent follows verbatim.

## Pipeline

```text
Human natural-language request
        │
        � ▼
Spec-Forge (LLM + validator)
Generates:
    data/training_data.jsonl   (valid prompt + spec_yaml pairs)
    data/failed_specs.jsonl    (invalid specs, saved for analysis)
        │
        � ▼
Runbook Scorer (standalone, post-generation)
Scores:
    5 categories — Intent, Preconditions, Structure, Testability, Coverage
    Hard gate: missing Inspect/Create/Verify = 0.0
        │
        � ▼
Human Review
"L1-L4 look good. Approve."
        │
        � ▼
COMMAND_RUNWAY Skill
Consumes:
    a validated spec (single-feature YAML)
Produces:
    COMMAND_RUNWAY.md
        • ordered implementation plan
        • exact file paths
        • code modifications
        • test skeletons
        • verification commands (translated from spec local_goals)
        • rollback guidance
        • completion criteria
        │
        � ▼
GRG Executor (with COMMAND_RUNWAY pattern integration)
Consumes:
    a validated spec OR COMMAND_RUNWAY plan JSON
Produces (all under foreign/ directory):
    • implementation source files
    • test files
    • RUNBOOK.md (human-readable execution log with GRG scores)
    • RUNBOOK.json (machine-readable execution data)
    • automatic ruff check --fix on generated code
        │
        � ▼
Completed Feature
Outputs:
    • implementation complete
    • all tests passing
    • OpenAPI updated
    • documentation synchronized
    • human notified
```

## Spec Enrichment (IMPROVE_SPEC)

Every generated spec now includes optional **enrichment fields** that make specs machine-executable:

| Field | Location | Purpose |
|-------|----------|---------|
| `business_rules` | top-level | Invariants & formulas (e.g., "JWT Secret: 256-bit random, rotated quarterly") |
| `test_fixtures` | top-level | Seed data & setup commands (e.g., `python scripts/seed_admin.py`) |
| `environment` | top-level | Required packages + env vars (e.g., `pyyaml>=6.0`, `JWT_SECRET`) |
| `global_verification` | top-level | Post-execution gate commands (e.g., `pytest tests/`, `bandit -r src/`) |
| `blueprint` | per-goal | **Required for `type: create`** (≥100 chars). Code-level outline: class signatures, route decorators, SQLAlchemy models, business logic steps |
| `acceptance_criteria` | per-goal | List of `{test, steps}` — executable test cases in pseudo-code |
| `type` | per-goal | `create` \| `update` \| `delete` \| `inspect` \| `verify` — drives runbook stage classification |

These fields are validated by `scripts/validator.py` and consumed by downstream generators (plan, runbook, scorer).

## Runbook Scoring System

Every generated spec is scored against runbook-readiness criteria (see `docs/scoring_spec.md`). Scoring is decoupled from generation — specs are saved first, then scored in a separate pass via `make score`.

The scorer (`scripts/runbook_scorer.py`) evaluates five weighted categories:

| Category | Weight | Key Checks |
|----------|--------|------------|
| **Intent & Goals** | 20% | Summary present, goals have descriptions, endpoint tasks have HTTP verification |
| **Preconditions** | 15% | `depends_on` references valid globals/stages, CLI tools declared in context |
| **Command Runway Structure** | 30% | **Hard gate**: must have Inspect (file_exists/read CLI), Create/Modify (build CLI), Verify (HTTP/test CLI). Stage order: Inspect → Create → Verify |
| **Verification Testability** | 25% | Concrete commands, explicit assertions (status/exit_code/content), reproducible URLs |
| **Completion Coverage** | 10% | Prompt-mentioned status codes, tests, OpenAPI updates reflected in spec |

**Hard gate**: If any of the three runway stages (Inspect, Create/Modify, Verify) is missing, the spec scores **0.0** and is not runbook-ready.

The scorer now **honors explicit `type` on goals** — a goal with `type: create` counts as Create/Modify even if its verification is `file_exists` (executor will generate the file). Similarly `type: inspect` and `type: verify` map directly to stages.

## Quick Start

### 1. Setup

```bash
git clone <repo-url> && cd githeri
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt

# For local generation (Ollama):
ollama pull qwen2.5-coder:7b-instruct

# For cloud generation (NVIDIA NIM - host any model like minimaxai/minimax-m3):
export NVIDIA_API_KEY=your_nvidia_api_key

# For training: install on a GPU machine
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

### 2. Generate specs

```bash
# Generate a validated spec from a fresh NL prompt (Ollama default)
make spec PROMPT="Add a POST /register endpoint that accepts email and password"

# Use NVIDIA NIM (default model: minimaxai/minimax-m3, base URL: https://integrate.api.nvidia.com/v1)
make spec PROMPT="Add a PATCH /users/{id}/settings endpoint" PROVIDER=nvidia API_KEY=$NVIDIA_API_KEY

# Use any OpenAI-compatible endpoint
make spec PROMPT="..." PROVIDER=openai-compat BASE_URL=https://api.fireworks.ai/inference/v1 API_KEY=... MODEL=accounts/nvidia/models/nemotron-3-ultra

# Generate N specs from random seed prompts (475 prompts across 21 categories)
make generate N=10
make generate N=100

# Generate ALL seed prompts in sequential order (full corpus generation)
make generate N=all
make generate-all

# Generate 10 random specs (explicit alias, good for short test runs)
make generate N=random
make generate-random

# Validate all specs in the corpus
make validate

# Score all specs against runbook criteria (standalone, post-generation)
make score
make score-failed          # score invalid specs in data/failed_specs.jsonl
```

### 3. Convert + fine-tune + export

```bash
# Convert training data to chat format (filters by runbook score)
make convert-chat              # default MIN_SCORE=0.75
make convert-chat MIN_SCORE=0.9  # only high-quality specs

# LoRA fine-tuning (requires Unsloth + GPU with 8GB VRAM)
make train                     # outputs models/qwen3.5-4b-128k-specforge/

# Merge adapter + export GGUF for Ollama
make merge                     # outputs models/qwen3.5-4b-128k-specforge-gguf/

# Evaluate fine-tuned vs base model on held-out prompts
make eval-model                # saves data/eval_results.json

# Register in Ollama
ollama create specforge -f models/qwen3.5-4b-128k-specforge-gguf/Modelfile
```

### 4. Upload to HuggingFace Hub

Model weights are stored in git (not LFS). The upload sends standard model files to HF Hub.

```bash
# Set up auth
echo "HF_TOKEN=hf_your_token_here" > .env

# Upload
make upload-hf REPO=githeri/qwen3.5-4b-128k-specforge
make upload-hf REPO=githeri/qwen3.5-4b-128k-specforge PRIVATE=1  # private repo
```

### 5. Install skill for agent use

```bash
make install-skill             # copies skills/spec-forge/ to ~/.hermes/skills/spec-forge/
```

### 6. Autonomous Execution with Isolation (NEW)

The GRG executor isolates all generated artifacts in a `foreign/` directory to prevent mixing with native project files.

```bash
# Full pipeline from a validated spec
make grg-plan SPEC=/tmp/your_spec.yaml
make grg-run PLAN=/tmp/test_plan.json PROVIDER=ollama

# Or run the entire flow with a fresh prompt (requires stronger model for spec generation)
make grg-full PROMPT="Your prompt here" PROVIDER=ollama

# Use Hermes proxy for cloud models (NVIDIA Nemotron, Nous Portal, xAI Grok)
# First: hermes proxy start --port 8465
make grg-full PROMPT="Your prompt here" PROVIDER=hermes

# Verify runbook completeness
make grg-verify RUNBOOK=foreign/RUNBOOK.json

# Clean generated artifacts
make grg-clean   # removes foreign/ entirely
```

### Provider Configuration

All generation targets accept provider overrides:

```bash
# NVIDIA NIM (default: minimaxai/minimax-m3 at integrate.api.nvidia.com/v1)
make spec PROMPT="..." PROVIDER=nvidia API_KEY=$NVIDIA_API_KEY

# OpenAI GPT-4o
make spec PROMPT="..." PROVIDER=openai API_KEY=$OPENAI_API_KEY MODEL=gpt-4o

# Anthropic Claude
make spec PROMPT="..." PROVIDER=anthropic API_KEY=$ANTHROPIC_API_KEY MODEL=claude-3-5-sonnet-20241022

# Any OpenAI-compatible endpoint (Fireworks, Together, vLLM, self-hosted NIM)
make spec PROMPT="..." PROVIDER=openai-compat BASE_URL=https://api.fireworks.ai/inference/v1 API_KEY=... MODEL=accounts/nvidia/models/nemotron-3-ultra

# Override sampling
make generate N=5 PROVIDER=nvidia TEMPERATURE=0.3 MAX_TOKENS=4096

# NVIDIA NIM models with longer cold start: use bigger TIMEOUT
make generate N=1 PROVIDER=nvidia TIMEOUT=600
```

Environment variable fallbacks:
- `PROVIDER` → `ollama` (default)
- `MODEL` → provider-specific default
- `API_KEY` → `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `ANTHROPIC_API_KEY`
- `BASE_URL` → `OPENAI_BASE_URL`, `NVIDIA_BASE_URL` (default `https://integrate.api.nvidia.com/v1`)
- `TEMPERATURE` → `0.2`
- `MAX_TOKENS` → `2048`

## Autonomous Execution System

The autonomous execution system takes a natural language prompt and produces a working implementation without human intervention in the loop. It uses the Spec-Forge pipeline to generate a validated spec, then uses the Command Runway skills to generate a plan and runbook, and finally executes the runbook using the GRG executor (with self-healing capabilities via GRG quality gates).

For detailed instructions, see [docs/SPRINTS_AUTONOMOUS.md](docs/SPRINTS_AUTONOMOUS.md).

### Quick Reference

```bash
# Basic local execution
python3 run_autonomous.py --prompt "Add a POST /notifications endpoint"

# Docker-isolated execution
python3 run_autonomous.py --prompt "Add user authentication" --docker

# Using Hermes as the execution backend
python3 run_autonomous.py --prompt "Implement rate limiting" --executor hermes

# Makefile: generate spec and plan
make spec-and-plan PROMPT="Add file upload endpoint"

# Makefile: full autonomous cycle (spec -> plan -> runbook -> execute -> report)
make autonomous-cycle SPEC=specs/test-endpoint.yaml

# GRG isolated execution (recommended for clean workspace)
make grg-full PROMPT="Add a POST /webhook endpoint that validates signature" PROVIDER=ollama
# Outputs: foreign/src/, foreign/tests/, foreign/RUNBOOK.md, foreign/RUNBOOK.json
```

## Recent Enhancements

### 2026-08-15 (This Session)

#### GRG Agent Skill — Hermes Native Integration
The GRG agent skill is now installed as a native Hermes skill (`~/.hermes/skills/autonomous-ai-agents/grg_agent/`) with full multi-provider support:

1. **Skill Installation** — Copied from `skills/grg_agent/` and installed via editable pip install
2. **Lightweight GRG Dependency** — Uses local `grg-0.1.0-py3-none-any.whl` wheel (no karakana dependency) providing `AlphaMomentumTracker` and `compute_structural_alpha`
3. **Hermes Proxy Support** — Skill accepts `provider` argument: `ollama` | `hermes` | `auto` — uses Hermes's configured providers (NVIDIA Nemotron, Nous Portal, xAI Grok, etc.) instead of local models
4. **Direct GRG Agent Execution** — `grg:execute` command now calls `self.agent.solve()` directly instead of legacy `run_pipeline.py` subprocess
5. **Make Target Integration** — `scripts/grg_make_spec.py` updated to use the skill with provider argument: `make grg-spec PROMPT="..." PROVIDER=ollama|hermes|auto`
6. **Project Virtual Environment** — Runs in project's own `.venv/` (not external karakana venv)

**Key Benefit**: You can now use cloud models via Hermes proxy (`hermes proxy start`) instead of relying on locally installed Ollama models. The skill routes through Hermes's provider config which supports NVIDIA Nemotron, Nous Portal, xAI Grok, and any OpenAI-compatible endpoint.

### 2026-07-30 (Latest)

#### THIRD_IMPROVE_SPEC — 7 Pipeline Fixes
After analyzing a 10-spec batch run, identified 7 recurring failure patterns and fixed all of them:

1. **Minimal structural skeleton in SYSTEM_PROMPT** — eliminated top-level field confusion
2. **task_id validator check** — rejects L11/G18-style IDs, requires descriptive slug like `jwt-auth-login`
3. **Verification types & expect keys table** — explicit vocabulary reduces hallucinated keys
4. **Placeholder ban strengthened** — concrete examples in prompt (`JWT_SECRET: "test-secret-..."`, `DATABASE_URL: "postgresql://user:***@..."`) + validator hint
5. **Helpful error hints** — "These fields belong inside a goal under `local_goals`, not at the spec root"
6. **depends_on validator hints** — rejects L/G refs, redirects to task_ids/stage names
7. **Structural acceptance_criteria template** — local goal field, not top-level

All 90 tests passing.

#### Generation Mode Aliases
Added `make generate N=random` and `make generate N=all` flags plus `generate-random` / `generate-all` aliases for short tests and full corpus runs. 475 seed prompts across 21 categories available.

#### Model Default Reverted
`OLLAMA_MODEL` reverted to `qwen2.5-coder:7b-instruct` (was regressed to `qwen3.5-4b-128k:latest`). Better structure compliance after prompt fixes.

### 2026-07-30 (Earlier)

#### Spec Enrichment (IMPROVE_SPEC)
Added five top-level enrichment fields (`business_rules`, `test_fixtures`, `environment`, `global_verification`) and three goal-level fields (`blueprint`, `acceptance_criteria`, `type`). All validated and scored.

#### Multi-Provider LLM Support
`run_pipeline.py` now supports Ollama, OpenAI, Anthropic, NVIDIA (via Together AI), and any OpenAI-compatible endpoint. Configured via `--provider` CLI arg or Makefile variables.

#### Runbook Scorer Stage Detection
Scorer now honors explicit `type: create|inspect|verify` on goals, fixing false "missing stage" penalties for `file_exists` verification on CREATE goals.

#### Validator Hardening
- Guarded against `expect` being a string instead of dict (prevents `AttributeError: 'str' object has no attribute 'get'`)
- Near-duplicate detection now handles malformed `expect` blocks defensively
- All 90 tests pass

## Model Compatibility Matrix

| Model | Context | Tools | Speed (M1 16GB) | Spec Gen | Recommended Use |
|-------|---------|-------|-----------------|----------|-----------------|
| **qwen2.5-coder:7b-instruct** | 32K | Yes | Fast | Works (best structure compliance) | **Default local (Ollama)** |
| qwen3.5-4b-128k | 128K | Yes | Fast | Works | Larger context fallback |
| qwen3.5-9b-code:128k | 128K | Yes | Slow | Excellent | Higher quality if time allows |
| deepseek-r1:7b | 128K | TBD | Fast | YAML syntax errors | Not recommended for spec gen |
| **Nemotron 3 Ultra** | 128K | Yes | Fast | Excellent | **Cloud via NVIDIA NIM (`--provider nvidia`)** |

**Current recommendation**: Local → `qwen2.5-coder:7b-instruct` on Ollama. Cloud → `minimaxai/minimax-m3` via NVIDIA NIM (`--provider nvidia`, base URL `https://integrate.api.nvidia.com/v1`).

## For More Information

- [docs/SPRINTS_AUTONOMOUS.md](docs/SPRINTS_AUTONOMOUS.md) — sprint breakdown, model experiments, decisions, next steps
- [docs/scoring_spec.md](docs/scoring_spec.md) — runbook scoring specification
- [docs/IMPROVE_SPEC.md](docs/IMPROVE_SPEC.md) — spec enrichment field specification (v1)
- [docs/SECOND_IMPROVE_SPEC.md](docs/SECOND_IMPROVE_SPEC.md) — enrichment field enforcement (v2)
- [docs/THIRD_IMPROVE_SPEC.txt](docs/THIRD_IMPROVE_SPEC.txt) — 7 pipeline failure patterns + fixes (v3)
- [MODEL_CARD.md](MODEL_CARD.md) — model card (uploaded to HF Hub)
- [skills/spec-forge/SKILL.md](skills/spec-forge/SKILL.md) — Spec-Forge skill reference
- [skills/command-runway-pattern/SKILL.md](skills/command-runway-pattern/SKILL.md) — Command Runway pattern skill
- [skills/grg_agent/SKILL.md](skills/grg_agent/SKILL.md) — GRG Agent skill reference