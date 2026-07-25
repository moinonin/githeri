# githeri

Spec-Forge: a pipeline that trains an AI to bridge the gap between a human's
natural-language feature request and a machine-executable specification that
feeds the COMMAND_RUNWAY skill.

The central thesis: most time in AI-assisted development is lost before the AI
and the human agree on what to build. Githeri attacks that by producing
validated, structured YAML specs — which then feed into COMMAND_RUNWAY runbooks
that an executor agent follows verbatim.

## Pipeline

```
Human natural-language request
        │
        ▼
Spec-Forge (LLM + validator)
Generates:
    data/training_data.jsonl  (valid prompt + spec_yaml pairs)
    data/failed_specs.jsonl   (invalid specs, saved for analysis)
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

## Runbook Scoring System

Every generated spec is scored against runbook-readiness criteria (see
`docs/scoring_spec.md`). Scoring is decoupled from generation — specs are saved
first, then scored in a separate pass via `make score`.

The scorer (`scripts/runbook_scorer.py`) evaluates five weighted categories:

| Category | Weight | Key Checks |
|----------|--------|------------|
| **Intent & Goals** | 20% | Summary present, goals have descriptions, endpoint tasks have HTTP verification |
| **Preconditions** | 15% | `depends_on` references valid globals/stages, Express+Prisma → stage-1-core-models, CLI tools declared in context |
| **Command Runway Structure** | 30% | **Hard gate**: must have Inspect (file_exists/read CLI), Create/Modify (build CLI), Verify (HTTP/test CLI). Stage order: Inspect → Create → Verify |
| **Verification Testability** | 25% | Concrete commands, explicit assertions (status/exit_code/content), reproducible URLs |
| **Completion Coverage** | 10% | Prompt-mentioned status codes, tests, OpenAPI updates reflected in spec |

**Hard gate**: If any of the three runway stages (Inspect, Create/Modify,
Verify) is missing, the spec scores **0.0** and is not runbook-ready.

## Quick Start

### 1. Setup

```bash
git clone <repo-url> && cd githeri
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt

# For generation: install Ollama + pull the model
ollama pull qwen2.5-coder:7b-instruct

# For training: install on a GPU machine
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

### 2. Generate specs

```bash
# Generate a validated spec from a fresh NL prompt
make spec PROMPT="Add a POST /register endpoint that accepts email and password"

# Generate N pairs from seed prompts (475 prompts across 21 categories)
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
make train                     # outputs models/qwen2.5-coder-7b-specforge/

# Merge adapter + export GGUF for Ollama
make merge                     # outputs models/qwen2.5-coder-7b-specforge-gguf/

# Evaluate fine-tuned vs base model on held-out prompts
make eval-model                # saves data/eval_results.json

# Register in Ollama
ollama create specforge -f models/qwen2.5-coder-7b-specforge-gguf/Modelfile
```

### 4. Upload to HuggingFace Hub

Model weights are stored in git (not LFS). The upload sends the standard
model files (adapter config, tokenizer, MODEL_CARD.md) to HF Hub.

```bash
# Set up auth
echo "HF_TOKEN=hf_your_token_here" > .env

# Upload
make upload-hf REPO=githeri/qwen2.5-coder-7b-specforge
make upload-hf REPO=githeri/qwen2.5-coder-7b-specforge PRIVATE=1  # private repo
```

### 5. Install skill for agent use

```bash
make install-skill             # copies skills/spec-forge/ to ~/.hermes/skills/spec-forge/
```

## Training Pipeline (Fine-tuning qwen2.5-coder:7b)

```bash
# 1. Generate validated specs with runbook scoring (requires Ollama + qwen2.5-coder:7b-instruct)
make generate N=100

# 2. Score all specs against runbook criteria (hard gate at 0.75)
make score

# 3. Export chat format for fine-tuning (filters specs below MIN_SCORE)
make convert-chat              # default MIN_SCORE=0.75
make convert-chat MIN_SCORE=0.9  # only high-quality specs

# 4. LoRA fine-tuning (requires Unsloth + GPU)
make train                     # LoRA on qwen2.5-coder-7b, outputs models/qwen2.5-coder-7b-specforge/

# 5. Merge adapter + export GGUF for Ollama
make merge                     # merged 16-bit + q4_k_m/q8_0 GGUF in models/qwen2.5-coder-7b-specforge-gguf/

# 6. Evaluate fine-tuned model on held-out prompts
make eval-model                # compares base vs fine-tuned pass rates

# 7. Upload model to HuggingFace Hub (requires HF_TOKEN in .env)
make upload-hf REPO=githeri/qwen2.5-coder-7b-specforge

# 8. Install spec-forge skill for agent use
make install-skill             # copies to ~/.hermes/skills/spec-forge/
```

After fine-tuning, register the model in Ollama:
```bash
ollama create specforge -f models/qwen2.5-coder-7b-specforge-gguf/Modelfile
```

Then use it in the pipeline by setting `MODEL=specforge` in `scripts/run_pipeline.py`.

## Generation + Scoring Architecture

Generation and scoring are decoupled:

- **Generation** (`run_pipeline.py`): prompts Ollama → extracts YAML → validates
  → saves. Valid specs go to `data/training_data.jsonl`. Invalid specs (after
  3 retry attempts) go to `data/failed_specs.jsonl` with their validation errors
  recorded. Every final attempt is saved, regardless of pass/fail.

- **Scoring** (`score_corpus.py`): reads a JSONL file, scores each spec against
  the runbook criteria, writes back with `runbook_score` and `above_threshold`
  fields. Run independently via `make score` or `make score-failed`.

- **Hard gate** (`runbook_scorer.py`): specs missing any of Inspect/Create/Verify
  stages score 0.0. The scorer uses harsh penalties for missing dependencies,
  context mismatches, and missing stage types.

## Repository layout

```
scripts/
  prompt_generator.py     — seed bank of realistic feature requests (475 prompts)
  run_pipeline.py         — orchestrator: seed prompt → Ollama → YAML → validate → save
  validator.py            — the spec conformance gate (canonical vocabulary + quality)
  runbook_scorer.py       — runbook readiness scorer (5 categories, hard gate)
  score_corpus.py         — scores all specs in a JSONL file (standalone)
  plan_from_spec.py       — extracts a validated spec and emits the COMMAND_RUNWAY plan prompt
  convert_to_chat.py      — converts training_data.jsonl → chat format for fine-tuning
  train.py                — LoRA fine-tuning script (Unsloth + qwen2.5-coder-7b)
  merge_and_export.py     — merges adapter + exports GGUF (q4_k_m, q8_0) for Ollama
  eval_model.py           — evaluates fine-tuned model on held-out prompts
  upload_to_hf.py         — uploads model files to HuggingFace Hub (uses HF_TOKEN from .env)
skills/
  spec-forge/             — the Spec-Forge skill (scripts + SKILL.md + references)
  command-runway-pattern/ — the Command Runway Pattern skill (references + templates)
  runbookprompt.md        — the COMMAND_RUNWAY plan-generation prompt
  runbook.md              — the runbook template (execution log layout)
docs/
  spec-forge.yml          — gold project-level example (VAE, 22 stages, G1..G19)
  spec-blueprint.md       — pipeline diagram
  SPRINTS.md              — sprint breakdown + status
  scoring_spec.md         — runbook scoring specification
  training_data_spec.md   — guide for chat format conversion
MODEL_CARD.md             — standard HF model card (uploaded as README.md to Hub)
data/
  training_data.jsonl     — valid prompt+spec pairs (generation output)
  training_data_chat.jsonl — chat-format training data (for fine-tuning)
  failed_specs.jsonl      — invalid specs with validation errors (for analysis)
  eval_results.json       — eval results from make eval-model
tests/
  test_validator.py       — 39 tests covering the canonical vocabulary + gates
  test_plan_from_spec.py  — 6 tests covering spec extraction + prompt assembly
  test_runbook_scorer.py  — 24 tests covering the runbook scorer
```

## Prerequisites

- Python 3.11+ (the repo ships a `.venv`; activate or use `.venv/bin/python`)
- Ollama running locally with `qwen2.5-coder:7b-instruct` (for `make generate`)
- `requirements.txt` deps — install via `pip install -r requirements.txt`
- For training: CUDA GPU with 8GB+ VRAM, Unsloth, trl, peft, bitsandbytes
- For HF upload: `HF_TOKEN` set in `.env` file

## Make Targets Quick Reference

| Target | Description |
|--------|-------------|
| `make spec PROMPT="..."` | Generate a validated spec from a fresh NL prompt |
| `make spec-and-plan PROMPT="..."` | End-to-end: NL → validated spec → plan prompt |
| `make generate N=10` | Generate N pairs from seed bank |
| `make check` | Pretty-print first corpus entry |
| `make validate` | Validate all specs in corpus |
| `make validate-one SPEC=x` | Validate single spec file |
| `make score` | Score all specs against runbook criteria (standalone) |
| `make score-failed` | Score failed specs in data/failed_specs.jsonl |
| `make plan SPEC=x` | Emit COMMAND_RUNWAY plan prompt for spec |
| `make convert-chat [MIN_SCORE=0.75]` | Convert training_data.jsonl → chat format (filters by score) |
| `make train` | Run LoRA fine-tuning (qwen2.5-coder-7b) |
| `make merge` | Merge adapter + export GGUF for Ollama |
| `make eval-model` | Evaluate fine-tuned model on held-out prompts |
| `make upload-hf REPO=<repo>` | Upload model to HuggingFace Hub (requires HF_TOKEN in .env) |
| `make install-skill` | Install spec-forge skill to ~/.hermes/skills/ |
| `make uninstall-skill` | Remove spec-forge skill |
| `make test` | Run full test suite (78 tests) |
| `make clean` | Delete training_data.jsonl |