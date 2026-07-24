---
name: spec-forge
description: "Spec-Forge: bridge the gap between a human's natural-language feature request and a machine-executable spec. Produces validated single-feature YAML specs that feed the command-runway-pattern skill. Uses a local Ollama model + a hardened validator with canonical-vocabulary enforcement + a regex-in-YAML pre-processor."
version: 1.0.0
author: Nous Research
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [spec, spec-driven, validation, plan-generation, command-runway, ollama]
    related_skills: [command-runway-pattern, writing-plans, test-driven-development]
---

# Spec-Forge

## What This Is

Spec-Forge is a **natural-language-to-spec bridge** for AI-assisted software
development. The central problem it solves: most time in AI-assisted dev is
lost *before* the AI and the human agree on what to build. Spec-Forge attacks
that by producing validated, structured YAML specs — which then feed the
COMMAND_RUNWAY skill's runbook generation.

This is NOT a fine-tuned model. It is a thin pipeline: a local Ollama model
(qwen2.5-coder:7b-instruct) generates a candidate YAML spec, a hardened
validator enforces a canonical assertion vocabulary + minimum quality gates,
and the validator's error feedback is fed back into the model's retry loop so
the model learns the vocabulary by rejection. The output is a spec the
COMMAND_RUNWAY prompt natively accepts and translates into a plan.

## When To Use This Skill

Use Spec-Forge when ALL of these are true:
- The user gives a natural-language feature description (not a finished spec)
- You have a local Ollama server running with `qwen2.5-coder:7b-instruct` OR
  you are invoking from a context that has access to the repo's `make` targets
- The output should feed the **command-runway-pattern** skill (the spec is
  the input to COMMAND_RUNWAY plan generation)

Do NOT use Spec-Forge when:
- The spec already exists (skip to `command-runway-pattern` directly)
- You only need a one-line edit (the overhead exceeds the value)
- The work is exploratory/throwaway (use the `spike` skill instead)

## The Three-Layer Flow

```
Human NL → Spec-Forge → validated YAML spec → Human Review → command-runway-pattern → COMMAND_RUNWAY.md plan
```

### Layer 1: Natural Language → Validated Spec

The user types a feature request. Spec-Forge sends it to a local Ollama model
with a system prompt that:
1. Loads the project's `command-runway-pattern` skill as context (so the model
   knows what the downstream plan will look like)
2. Specifies the canonical top-level fields (`task_id`, `summary`,
   `local_goals`, `context`) and the canonical verification vocabulary
3. Shows a 3-task few-shot example (session lifecycle, paginated list,
   rate-limited endpoint with response-header assertion)
4. On every attempt: extracts the YAML, runs the hardened validator, and on
   failure feeds the errors back into the next attempt (up to 3 retries)

### Layer 2: Validated Spec → Plan Prompt

Once a spec passes the hardened gate, Spec-Forge emits a self-contained plan
prompt: the `runbookprompt.md` content (with its ACCEPTED INPUT FORMATS
section) followed by the spec YAML wrapped in a ```yaml fence. An agent
consuming this produces a COMMAND_RUNWAY plan that maps each `local_goals`
entry to a concrete Local Verification row.

### Layer 3: Plan → Execution

The plan is handed to the `command-runway-pattern` skill for stage-by-stage
execution. This is out of Scope-Forge's scope — it's where the spec-forge
handoff ends and the runway execution begins.

## The Canonical Spec Vocabulary (enforced by the validator)

This is the contract between Spec-Forge and the COMMAND_RUNWAY skill. The
validator (`scripts/validator.py`) rejects any spec that violates it.

### Top-Level Shape

A single-feature spec has these required top-level fields: `task_id`,
`summary`, `local_goals`, `context`. Optional: `depends_on`,
`global_goals_refs` (refs must be in `G1..G19`).

### Verification Types

Each `local_goals[].verification.type` must be one of:

| Type | Required Fields | Required `expect` Keys | Valid `expect` Keys |
|------|-----------------|------------------------|---------------------|
| `http` | `method`, `url` | `status` | `status`, `body_regex`, `body_contains`, `json_schema`, `headers_contain` |
| `cli` | `command` (≥3 chars) | `exit_code` | `exit_code`, `stdout_regex`, `stdout_contains`, `stdout_lines_min` |
| `file_exists` | `path` | (at least one content/exists check) | `content`, `content_contains`, `content_not_contains`, `exists` |
| `manual` | `description` | (none — the description IS the check) | (none) |

### Critical Placement Rules

- **REQUEST headers** (`Authorization`, etc.) are a SIBLING of `expect`, under
  `verification`. Never inside `expect`.
- **RESPONSE header assertions** go INSIDE `expect` as `headers_contain`, a map
  of header-name → required-substring.
- **`body`** lives beside `expect` under `verification`, not inside `expect`.
- **Regex patterns inside string values MUST use single quotes** (e.g.
  `Retry-After: '\d+'`). YAML double quotes reject backslash escapes like
  `\d`, `\w`, `\s`. The validator's pre-processor (`preprocess_yaml`) will
  auto-fix double-quoted regex values to single-quoted form, but emitting
  them correctly the first time avoids the retry.

### Quality Gates

- Minimum 2 `local_goals` per spec (1 is never enough)
- No near-duplicate verifications (same type+method+url+headers+expect-keys is
  padding — auth-vs-noauth on the same endpoint IS distinct, not a dup)
- No unknown top-level fields
- Non-empty `task_id`
- No `$ref` or `definitions` in `json_schema`
- No code-like expressions in `body`

## How To Use This Skill

### Prerequisites

- Python 3.11+ with a `.venv` containing PyYAML and requests
- Ollama running locally with `qwen2.5-coder:7b-instruct` loaded
  (`OLLAMA_HOST=http://localhost:11434` by default)

### End-to-End From a Fresh Natural-Language Prompt

From the repo root (where the Makefile lives):

```bash
# Generate a validated spec from a fresh NL feature request
make spec PROMPT="Add a POST /register endpoint that accepts email and password"

# End-to-end: fresh prompt → validated spec → COMMAND_RUNWAY plan prompt on stdout
make spec-and-plan PROMPT="Add a PATCH endpoint to update user displayName and bio. Only the owner or admin can update."
```

The `make spec-and-plan` output is a self-contained prompt for a planning
agent: the runbookprompt.md content followed by the validated spec YAML.

### From an Existing Validated Spec

If a spec already exists (e.g. in `data/training_data.jsonl` or as a
standalone `.yaml` file):

```bash
# Validate it
make validate-one SPEC=path/to/spec.yaml

# Emit the COMMAND_RUNWAY plan prompt for it
make plan SPEC=path/to/spec.yaml
# OR by index from the corpus:
make plan SPEC=data/training_data.jsonl#0
```

## Repository Layout (what this skill bundles)

```
skills/spec-forge/
  SKILL.md                       (this file)
  scripts/validator.py            the hardened spec gate (canonical vocab + gates + regex pre-processor)
  scripts/plan_from_spec.py       extracts a validated spec and emits the plan prompt
  scripts/run_pipeline.py         the orchestrator (NL → Ollama → YAML → validate → save)
  scripts/prompt_generator.py     seed bank (used only for batch training)
  runbookprompt.md                the COMMAND_RUNWAY plan-generation prompt (with ACCEPTED INPUT FORMATS)
  runbook.md                      the runbook template (execution log layout)
  references/
    canonical-vocab.md            the canonical assertion vocabulary (kept in sync with validator.py)
```

The bundled `runbookprompt.md` and `runbook.md` are designed to feed into
the `command-runway-pattern` skill.

## Using This Skill Inside a Coding Agent

When the agent receives a natural-language feature request, the flow is:

1. Check Ollama is up: `curl -s http://localhost:11434/api/tags | jq '.models[].name'`
2. Run `make spec PROMPT="<the user's request>"` from the repo root; if it
   exits 0 the validated spec is appended to `data/training_data.jsonl`
3. Read the spec back, present it to the user, ask for approval
4. On approval, run `make plan SPEC=data/training_data.jsonl#<last-index>`
   and feed the stdout to the `command-runway-pattern` skill, which produces
   the COMMAND_RUNWAY plan and executes it stage-by-stage

The skill is self-contained: it only depends on the repo's bundled
`scripts/validator.py` and `scripts/plan_from_spec.py`. The seed bank is
optional (only needed for batch training data generation).

## Known Limitations

- The model occasionally still fails 3 retries on prompts where the spec
  structure is genuinely ambiguous (e.g. near-duplicate HTTP goals where the
  user's prompt doesn't clearly differentiate what each goal verifies).
- The validator's pre-processor only handles the regex-in-double-quote case.
  Other YAML-emit quirks (e.g. unquoted strings starting with special chars)
  will still produce a parse failure.
- The pipeline uses a fixed `qwen2.5-coder:7b-instruct` model. To use a
  different model, change `MODEL` in `scripts/run_pipeline.py`.

## Tests

The validator and plan-assembly have full test coverage. From the repo root:

```bash
make test   # runs 54 tests: 46 validator (canonical vocab + pre-processor) + 6 plan assembly
```

All sprints (0 through 4) reaching green before this skill was packaged are
documented in `docs/SPRINTS.md`.

## Origin

Spec-Forge was built in the githeri repo across sprints 0-4, hardening the
validator first (catching 7/10 stale pairs as defective), then fixing the
generation prompt's vocabulary drift, then bridging the format to the
COMMAND_RUNWAY skill, then wiring the full NL → spec → plan flow, then adding
the regex-in-YAML pre-processor and the `headers_contain` canonical key.
See `docs/SPRINTS.md` for the full evidence trail.
