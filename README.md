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
    data/training_data.jsonl  (prompt + spec_yaml pairs)
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

Every generated spec is scored against runbook-readiness criteria (see `docs/scoring_spec.md`). The scorer (`scripts/runbook_scorer.py`) evaluates five weighted categories:

| Category | Weight | Key Checks |
|----------|--------|------------|
| **Intent & Goals** | 20% | Summary present, goals have descriptions, endpoint tasks have HTTP verification |
| **Preconditions** | 15% | `depends_on` references valid globals/stages, Express+Prisma → stage-1-core-models, CLI tools declared in context |
| **Command Runway Structure** | 30% | **Hard gate**: must have Inspect (file_exists/read CLI), Create/Modify (build CLI), Verify (HTTP/test CLI). Stage order: Inspect → Create → Verify |
| **Verification Testability** | 25% | Concrete commands, explicit assertions (status/exit_code/content), reproducible URLs |
| **Completion Coverage** | 10% | Prompt-mentioned status codes, tests, OpenAPI updates reflected in spec |

**Hard gate**: If any of the three runway stages (Inspect, Create/Modify, Verify) is missing, the spec scores **0.0** and is rejected during generation.

## Repository layout

```
scripts/
  prompt_generator.py   — seed bank of realistic feature requests (475 prompts)
  run_pipeline.py       — orchestrator: seed prompt → Ollama → YAML → validate → score → save
  validator.py          — the spec conformance gate (canonical vocabulary + quality)
  runbook_scorer.py     — runbook readiness scorer (5 categories, hard gate)
  score_corpus.py       — scores all specs in training_data.jsonl
  plan_from_spec.py     — extracts a validated spec and emits the COMMAND_RUNWAY plan prompt
skills/
  runbookprompt.md      — the COMMAND_RUNWAY plan-generation prompt (accepts YAML + markdown)
  runbook.md            — the runbook template (execution log layout)
  command-runway-pattern/  — the full vendored skill
docs/
  spec-forge.yml        — gold project-level example (VAE, 22 stages, G1..G19)
  spec-blueprint.md     — pipeline diagram
  SPRINTS.md            — sprint breakdown + status
  scoring_spec.md       — runbook scoring specification
tests/
  test_validator.py         — 39 tests covering the canonical vocabulary + gates
  test_plan_from_spec.py    — 6 tests covering spec extraction + prompt assembly
  test_runbook_scorer.py    — 24 tests covering the runbook scorer
```

## Usage

### Full pipeline

```bash
# 1. Generate validated spec pairs (requires Ollama with qwen2.5-coder:7b-instruct)
make generate N=10

# 2. Validate the corpus against the hardened spec gate
make validate

# 3. Score all specs against runbook criteria (hard gate at 0.75)
make score

# 4. Inspect a generated pair
make check

# 5. Emit the COMMAND_RUNWAY plan prompt for a validated spec
make plan SPEC=data/training_data.jsonl#0

# 6. Run the test suite (validator + plan assembly + scorer)
make test
```

### End-to-end from a fresh natural-language prompt

```bash
# Generate a validated spec from a fresh NL feature request
make spec PROMPT="Add a POST /register endpoint that accepts email and password, hashes the password, and returns 201 with the user ID"

# End-to-end: fresh prompt → validated spec → COMMAND_RUNWAY plan prompt
make spec-and-plan PROMPT="Add a PATCH endpoint to update user displayName and bio. Only the owner or an admin can update. Return 200 with updated user, 401 if unauthenticated, 403 if forbidden, 404 if not found, 422 for validation errors."
```

The `make spec-and-plan` output is a self-contained plan prompt: the
runbookprompt.md content (with the ACCEPTED INPUT FORMATS section) followed by
the validated spec YAML. An agent consuming this produces a COMMAND_RUNWAY plan
that translates each `local_goals` entry into a concrete Local Verification row.

### Validate a single spec

```bash
# Validate a standalone .yaml spec file
make validate-one SPEC=path/to/spec.yaml
```

### Emit a plan from a spec file (not the jsonl corpus)

```bash
# A standalone .yaml spec → plan prompt on stdout
make plan SPEC=path/to/spec.yaml
```

The `make plan` output is a self-contained prompt for a planning agent: the
runbookprompt.md content (with the ACCEPTED INPUT FORMATS section) followed by
the validated spec YAML. An agent consuming this produces a COMMAND_RUNWAY plan
that translates each `local_goals` entry into a concrete Local Verification row.

## Prerequisites

- Python 3.11 (the repo ships a `.venv`; activate or use `.venv/bin/python`)
- Ollama running locally with `qwen2.5-coder:7b-instruct` (for `make generate`)
- `requirements.txt` deps (PyYAML, requests) — install via `pip install -r requirements.txt`

## Make Targets Quick Reference

| Target | Description |
|--------|-------------|
| `make generate N=10` | Generate N prompt-spec pairs from seed bank |
| `make spec PROMPT="..."` | Generate validated spec from fresh NL prompt |
| `make spec-and-plan PROMPT="..."` | End-to-end: NL → validated spec → plan prompt |
| `make validate` | Validate all specs in corpus |
| `make validate-one SPEC=x` | Validate single spec file |
| `make score` | Score all specs against runbook criteria (hard gate) |
| `make check` | Pretty-print first corpus entry |
| `make plan SPEC=x` | Emit COMMAND_RUNWAY plan prompt for spec |
| `make test` | Run full test suite (78 tests) |
| `make clean` | Delete training_data.jsonl |
