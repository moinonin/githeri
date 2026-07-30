# githeri

**Spec-Forge**: a pipeline that trains an AI to bridge the gap between a human's natural-language feature request and a machine-executable specification that feeds the COMMAND_RUNWAY skill.

The central thesis: most time in AI-assisted development is lost before the AI and the human agree on what to build. Githeri attacks that by producing validated, structured YAML specs — which then feed into COMMAND_RUNWAY runbooks that an executor agent follows verbatim.

## Pipeline

```
Human natural-language request
        │
        ▼
Spec-Forge (LLM + validator)
Generates:
    data/training_data.jsonl   (valid prompt + spec_yaml pairs)
    data/failed_specs.jsonl    (invalid specs, saved for analysis)
        │
        ▼
Runbook Scorer (standalone, post-generation)
Scores:
    5 categories — Intent, Preconditions, Structure, Testability, Coverage
    Hard gate: missing Inspect/Create/Verify = 0.0
        │
        ▼
Human Review
"L1-L4 look good. Approve."
        │
        ▼
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
        ▼
Executor (any coding agent)
Reads:
    COMMAND_RUNWAY.md
For each command:
    ✓ modify code
    ✓ create/update tests
    ✓ execute verification commands
    ✓ record results
    ✓ continue automatically
    ✓ request human assistance only when blocked
        │
        ▼
Completed Feature
Outputs:
    ✓ implementation complete
    ✓ all tests passing
    ✓ OpenAPI updated
    ✓ documentation synchronized
    ✓ human notified
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

---

## Quick Start

### 1. Setup

```bash
git clone <repo-url> && cd githeri
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt

# For local generation (Ollama):
ollama pull qwen3.5-4b-128k

# For cloud generation (Together AI - hosts Nemotron 3 Ultra):
export NVIDIA_API_KEY=your_together_ai_key

# For training: install on a GPU machine
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

### 2. Generate specs

```bash
# Generate a validated spec from a fresh NL prompt (Ollama default)
make spec PROMPT="Add a POST /register endpoint that accepts email and password"

# Use NVIDIA Nemotron 3 Ultra via Together AI
make spec PROMPT="Add a PATCH /users/{id}/settings endpoint" PROVIDER=nvidia API_KEY=$NVIDIA_API_KEY

# Use any OpenAI-compatible endpoint
make spec PROMPT="..." PROVIDER=openai-compat BASE_URL=https://api.fireworks.ai/inference/v1 API_KEY=... MODEL=accounts/nvidia/models/nemotron-3-ultra

# Generate N pairs from seed bank (475 prompts across 21 categories)
make generate N=100

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

---

## Generation + Scoring Architecture

Generation and scoring are decoupled:

- **Generation** (`run_pipeline.py`): prompts LLM → extracts YAML → validates → saves. Valid specs go to `data/training_data.jsonl`. Invalid specs (after 3 retry attempts) go to `data/failed_specs.jsonl` with their validation errors recorded. Every final attempt is saved, regardless of pass/fail.

- **Scoring** (`score_corpus.py`): reads a JSONL file, scores each spec against runbook criteria, writes back with `runbook_score` and `above_threshold` fields. Run independently via `make score` or `make score-failed`.

- **Hard gate** (`runbook_scorer.py`): specs missing any of Inspect/Create/Verify stages score 0.0. The scorer uses harsh penalties for missing dependencies, context mismatches, and missing stage types.

---

## Repository Layout

```
scripts/
  prompt_generator.py      — seed bank of realistic feature requests (475 prompts)
  run_pipeline.py          — orchestrator: seed prompt → LLM → YAML → validate → save
  validator.py             — the spec conformance gate (canonical vocabulary + quality)
  runbook_scorer.py        — runbook readiness scorer (5 categories, hard gate)
  score_corpus.py          — scores all specs in a JSONL file (standalone)
  plan_from_spec.py        — extracts a validated spec and emits the COMMAND_RUNWAY plan prompt
  convert_to_chat.py       — converts training_data.jsonl → chat format for fine-tuning
  train.py                 — LoRA fine-tuning script (Unsloth + qwen3.5-4b-128k)
  merge_and_export.py      — merges adapter + exports GGUF (q4_k_m, q8_0) for Ollama
  eval_model.py            — evaluates fine-tuned model on held-out prompts
  upload_to_hf.py          — uploads model files to HuggingFace Hub (uses HF_TOKEN from .env)
skills/
  spec-forge/              — the Spec-Forge skill (scripts + SKILL.md + references)
  command-runway-pattern/  — the Command Runway Pattern skill (references + templates)
  runbookprompt.md         — the COMMAND_RUNWAY plan-generation prompt
  runbook.md               — the runbook template (execution log layout)
docs/
  spec-forge.yml           — gold project-level example (VAE, 22 stages, G1..G19)
  spec-blueprint.md        — pipeline diagram
  SPRINTS.md               — sprint breakdown + status
  scoring_spec.md          — runbook scoring specification
  training_data_spec.md    — guide for chat format conversion
  IMPROVE_SPEC.md          — spec enrichment field specification
MODEL_CARD.md              — standard HF model card (uploaded as README.md to Hub)
data/
  training_data.jsonl      — valid prompt+spec pairs (generation output)
  training_data_chat.jsonl — chat-format training data (for fine-tuning)
  failed_specs.jsonl       — invalid specs with validation errors (for analysis)
  eval_results.json        — eval results from make eval-model
tests/
  test_validator.py        — 42 tests covering canonical vocabulary + gates + enrichment
  test_plan_from_spec.py   — 6 tests covering spec extraction + prompt assembly
  test_runbook_scorer.py   — 42 tests covering runbook scorer (spec/execution/pipeline health)
```

---

## Prerequisites

- Python 3.11+ (the repo ships a `.venv`; activate or use `.venv/bin/python`)
- **For local generation**: Ollama running locally with `qwen3.5-4b-128k` (recommended) or `qwen2.5-coder:7b-instruct`
- **For cloud generation**: API key for Together AI (`NVIDIA_API_KEY`), Fireworks, or any OpenAI-compatible endpoint
- `requirements.txt` deps — install via `pip install -r requirements.txt`
- **For training**: CUDA GPU with 8GB+ VRAM, Unsloth, trl, peft, bitsandbytes
- **For HF upload**: `HF_TOKEN` set in `.env` file

---

## Make Targets Quick Reference

| Target | Description |
|--------|-------------|
| `make spec PROMPT="..."` | Generate a validated spec from a fresh NL prompt |
| `make spec-and-plan PROMPT="..."` | End-to-end: NL → validated spec → plan prompt |
| `make generate N=10` | Generate N pairs from seed bank |
| `make check` | Pretty-print first corpus entry |
| `make validate` | Validate all specs in corpus |
| `make validate-one SPEC=path.yaml` | Validate single spec file |
| `make score` | Score all specs against runbook criteria (standalone) |
| `make score-failed` | Score failed specs in data/failed_specs.jsonl |
| `make plan SPEC=x` | Emit COMMAND_RUNWAY plan prompt for spec |
| `make convert-chat [MIN_SCORE=0.75]` | Convert training_data.jsonl → chat format (filters by score) |
| `make train` | Run LoRA fine-tuning (qwen3.5-4b-128k) |
| `make merge` | Merge adapter + export GGUF for Ollama |
| `make eval-model` | Evaluate fine-tuned model on held-out prompts |
| `make upload-hf REPO=<repo>` | Upload model to HuggingFace Hub (requires HF_TOKEN in .env) |
| `make install-skill` | Install spec-forge skill to ~/.hermes/skills/ |
| `make uninstall-skill` | Remove spec-forge skill |
| `make test` | Run full test suite (90 tests) |
| `make clean` | Delete training_data.jsonl |

### Provider Configuration

All generation targets accept provider overrides:

```bash
# NVIDIA Nemotron 3 Ultra via Together AI
make spec PROMPT="..." PROVIDER=nvidia API_KEY=$NVIDIA_API_KEY

# OpenAI GPT-4o
make spec PROMPT="..." PROVIDER=openai API_KEY=$OPENAI_API_KEY MODEL=gpt-4o

# Anthropic Claude
make spec PROMPT="..." PROVIDER=anthropic API_KEY=$ANTHROPIC_API_KEY MODEL=claude-3-5-sonnet-20241022

# Any OpenAI-compatible endpoint (Fireworks, Together, vLLM, self-hosted NIM)
make spec PROMPT="..." PROVIDER=openai-compat BASE_URL=https://api.fireworks.ai/inference/v1 API_KEY=... MODEL=accounts/nvidia/models/nemotron-3-ultra

# Override sampling
make generate N=5 PROVIDER=nvidia TEMPERATURE=0.3 MAX_TOKENS=4096
```

Environment variable fallbacks:
- `PROVIDER` → `ollama` (default)
- `MODEL` → provider-specific default
- `API_KEY` → `OPENAI_API_KEY`, `NVIDIA_API_KEY`, `ANTHROPIC_API_KEY`
- `BASE_URL` → `OPENAI_BASE_URL`, `NVIDIA_BASE_URL`
- `TEMPERATURE` → `0.2`
- `MAX_TOKENS` → `2048`

---

## Autonomous Execution System

The autonomous execution system takes a natural language prompt and produces a working implementation without human intervention in the loop. It uses the Spec-Forge pipeline to generate a validated spec, then uses the Command Runway skills to generate a plan and runbook, and finally executes the runbook using an LLM agent (with self-healing capabilities).

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
```

---

## Recent Enhancements (2026-07-30)

### Spec Enrichment (IMPROVE_SPEC)
Added five top-level enrichment fields (`business_rules`, `test_fixtures`, `environment`, `global_verification`) and three goal-level fields (`blueprint`, `acceptance_criteria`, `type`). All validated and scored.

### Multi-Provider LLM Support
`run_pipeline.py` now supports Ollama, OpenAI, Anthropic, NVIDIA (via Together AI), and any OpenAI-compatible endpoint. Configured via `--provider` CLI arg or Makefile variables.

### Runbook Scorer Stage Detection
Scorer now honors explicit `type: create|inspect|verify` on goals, fixing false "missing stage" penalties for `file_exists` verification on CREATE goals.

### Validator Hardening
- Guarded against `expect` being a string instead of dict (prevents `AttributeError: 'str' object has no attribute 'get'`)
- Near-duplicate detection now handles malformed `expect` blocks defensively
- All 90 tests pass

---

## Model Compatibility Matrix

| Model | Context | Tools | Speed (M1 16GB) | Spec Gen | Recommended Use |
|-------|---------|-------|-----------------|----------|-----------------|
| **qwen3.5-4b-128k** | 128K | Yes | Fast | Works | **Default local (Ollama)** |
| qwen3.5-9b-code:128k | 128K | Yes | Slow | Works | Higher quality if time allows |
| qwen2.5-coder:7b-instruct | 32K | Yes | Fast | Works (YAML retry needed) | Legacy |
| specforge-128k:latest | 128K | No | Fast | Works | Spec-only (no tools) |
| **Nemotron 3 Ultra** | 128K | Yes | Fast | Excellent | **Cloud via Together AI (--provider nvidia)** |

**Current recommendation**: Local → `qwen3.5-4b-128k` on Ollama. Cloud → `nvidia/nemotron-3-ultra` via Together AI (`--provider nvidia`).

---

## For More Information

- [docs/SPRINTS_AUTONOMOUS.md](docs/SPRINTS_AUTONOMOUS.md) — sprint breakdown, model experiments, decisions, next steps
- [docs/scoring_spec.md](docs/scoring_spec.md) — runbook scoring specification
- [docs/IMPROVE_SPEC.md](docs/IMPROVE_SPEC.md) — spec enrichment field specification
- [MODEL_CARD.md](MODEL_CARD.md) — model card (uploaded to HF Hub)
- [skills/spec-forge/SKILL.md](skills/spec-forge/SKILL.md) — Spec-Forge skill reference
- [skills/command-runway-pattern/SKILL.md](skills/command-runway-pattern/SKILL.md) — Command Runway pattern skill