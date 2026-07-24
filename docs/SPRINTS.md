# Githeri — Spec-Forge Skill Packaging Sprints

**Goal:** Tighten the current pipeline so the artifacts (validated YAML specs) are natively accepted by the COMMAND_RUNWAY skill, then package the result as a self-contained coding-agent skill.

**Format:** Each sprint has a binary verify gate. No sprint starts until the prior sprint's gate is green. Backend-first; no UI work.

---

## Sprint 0 — Validator Hardening (the gate everything depends on)

The validator must enforce the canonical assertion vocabulary and minimum quality, not just structure.

**Deliverables:**
- Rewrite `scripts/validator.py` to enforce the full canonical vocab: exit_code, stdout_regex, stdout_contains, stdout_lines_min (cli); status, body_regex, body_contains, json_schema (http); content, content_contains, content_not_contains, exists (file_exists); manual type accepted.
- Add semantic gates: min 2 local_goals, per-type required fields, no unknown expect keys, no near-duplicate verifications, non-empty task_id, trivial-command rejection, file_exists must have at least one content/exists check.
- Add `tests/test_validator.py` with full coverage of every rule.
- Add `make validate` and `make test` targets; fix bare `python` → `.venv/bin/python`.

**Verify gate:**
- `make test` → all tests pass (exit 0).
- `make validate` → reports the pass/fail split honestly. Run against existing data to measure the failure rate (evidence the old gate was loose).

**Status:** ✅ Complete. 36 tests pass. Hardened validator caught 7/10 previously-"valid" pairs as defective. Stale corpus archived to `data/legacy/`.

---

## Sprint 1 — Assert-Fidelity: prompt + validator agree on the canonical vocabulary

The few-shot example in `run_pipeline.py` uses non-canonical expect keys (e.g., `content_type`, `headers` in expect, `exit_code` on file_exists). The model learns from the few-shot, so it reproduces those errors. Fix the example so new generation produces gate-clean specs naturally.

**Deliverables:**
- Audit every expect key in the `FEW_SHOT_EXAMPLE` (run_pipeline.py) against the canonical vocab from Sprint 0.
- Rewrite the few-shot example so every verification block uses only canonical expect keys and satisfies every semantic gate (min goals, no near-dupes, required fields present).
- Audit the `SYSTEM_PROMPT` instructions for any vocab drift — the "verification must follow these rules" block lists only http/cli/file_exists; add `manual` and enumerate the canonical expect keys explicitly so the model can't invent keys.
- Update `make generate` so the regeneration against the new gate is reproducible and idempotent.
- Regenerate the corpus: `make clean && make generate N=10`. Run `make validate` — the new pairs should all pass the hardened gate.

**Verify gate:**
- `make validate` → all newly-generated pairs pass (exit 0).
- `make test` → still all pass (exit 0).
- Compare the new corpus against the archived stale corpus: new corpus has zero unknown-expect-key errors and zero near-duplicate errors.

**Status:** ✅ Complete. SYSTEM_PROMPT rules block rewritten to enumerate all 4 verification types (added `manual`) and the full canonical expect-key vocabulary per type, plus anti-padding guidance (min 2 goals, no near-duplicate goals with same type+target). FEW_SHOT_EXAMPLE second task expanded from 1 goal to 2 goals (added the 401 unauthenticated case) to satisfy the min-2 gate. Near-duplicate detection in validator.py refined: same method+URL+identical headers+identical expect-keys is a dup; auth-vs-noauth (different headers) or different expect keys are distinct aspects, not padding. 39/39 validator tests pass; both few-shot tasks pass the hardened gate. Corpus regenerated: 10/10 new pairs pass (vs 3/10 in the stale corpus). Error-class comparison: stale corpus had 16 errors (5 unknown-expect-key, 9 near-dup, 1 too-few-goals, 1 no-file-exists-check); new corpus has 0. The pipeline's retry loop now teaches the model the canonical vocab via rejection — observed `content_type`, `exit_code on file_exists`, and `"a" * 101` YAML alias-explosions all caught and retried on generation.

---

## Sprint 2 — Bridge the format: COMMAND_RUNWAY accepts structured YAML specs

The `runbookprompt.md` says "Convert the supplied software specification" but never defines what a specification looks like. The isolation test used free-form markdown; our pipeline produces structured YAML. Add an explicit "Accepted Input Format" section so a planning agent knows how to consume the single-feature spec format.

**Deliverables:**
- Patch `skills/runbookprompt.md` to add an "Accepted Input Formats" section declaring both (a) free-form markdown specs (original isolation-test style) and (b) structured single-feature YAML specs (the pipeline format).
- For the YAML format, document how each field maps to a COMMAND_RUNWAY plan section: `task_id` → Feature Name, `summary` → Purpose, `local_goals[].description` → Local Verification per stage, `local_goals[].verification` → concrete verify commands (✓), `context` → Target Environment, `depends_on` / `global_goals_refs` → Dependencies.
- Add a worked mini-example showing a 2-goal spec YAML and the resulting COMMAND_RUNWAY stage it maps to.

**Status:** ✅ Complete. Added an "ACCEPTED INPUT FORMATS" section to `skills/runbookprompt.md` between EXECUTION PHILOSOPHY and TARGET ENVIRONMENT (the right injection point — input expectations belong before the document-structure section). Declares Format A (free-form markdown, original isolation-test style) and Format B (structured single-feature YAML, the pipeline format). Includes a Field→Plan-Section mapping table (task_id→Feature/Name, summary→Purpose, context→Target Environment, local_goals→Execution Stages+Local Verification, verification.type→concrete command translation), and a worked mini-example showing a 2-goal spec YAML and the resulting COMMAND_RUNWAY excerpt. Verified the mapping rules against a real spec from the new corpus (`cleanup-expired-sessions-job`): task_id correctly maps to Feature/Name, both L1 (file_exists → `grep -q '<content>' <path>`) and L2 (cli → exact `pnpm test` command + exit 0) translate to concrete Local Verification rows. `make test` and `make check` still pass.

---

## Sprint 3 — Pipeline integration: generate → validate → plan in one flow

Wire `make` so the full NL → validated spec → plan runbook flow is one command set. This is the "one coding agent skill" backbone.

**Deliverables:**
- Add `make plan SPEC=<path>` that extracts a validated spec and emits it + the `runbookprompt.md` prompt to stdout (or saves a `COMMAND_RUNWAY.md` draft), ready for an agent to consume.
- Add `make validate` support for a single `.yaml` spec file (not just the training_data.jsonl batch).
- Update `Makefile` so the full flow is documented: `make generate` → `make validate` → `make plan SPEC=...`.
- Update `README.md` with the pipeline diagram and usage for each target.

**Status:** ✅ Complete. Added `scripts/plan_from_spec.py` — a thin helper that extracts a validated spec from either a `.yaml` file or a `data/training_data.jsonl#<index>` reference, validates it against the hardened gate, and emits the runbookprompt.md + spec to stdout as a self-contained plan prompt for an agent. Added 6 tests in `tests/test_plan_from_spec.py` covering both extraction shapes, validate-before-emit (invalid spec → exit 1, no prompt emitted), out-of-range index, missing file, and no-args usage. Added `make validate-one SPEC=<path>` for single-spec validation. Added `make plan SPEC=<path>` for plan-prompt emission. Rewrote `Makefile` with the full flow documented (generate → validate → plan) and `make help` listing every target. Rewrote `README.md` with the pipeline diagram, repo layout, and usage for every target.

Verify: `make test` → 45/45 pass (39 validator + 6 plan). `make validate` → 10/10 corpus pass. `make validate-one SPEC=<valid>` → PASS. `make validate-one SPEC=<invalid>` → exit 1 with both errors. `make plan SPEC=<valid>` → emits prompt + spec. `make plan SPEC=<invalid>` → exit 1, no prompt emitted. `make check` → still passes.

---

## Interlude — End-to-End from a Fresh NL Prompt (pre-Sprint-4 wiring)

Before the skill can be packaged, the pipeline must accept a fresh
natural-language prompt end-to-end — not just pick from the seed corpus.
The seed bank (`prompt_generator.py`) was the only entry point; there was
no path from a user-typed prompt to a validated spec.

**Deliverables:**
- Refactor `generate_one_pair()` in `run_pipeline.py` to accept an optional
  `prompt` argument (default `None` → random seed prompt for the batch path;
  explicit string → the end-to-end NL path).
- Add CLI mode: `python run_pipeline.py --prompt "<NL>"` generates one spec
  from a fresh prompt, validates it, and appends to `data/training_data.jsonl`.
- Add `make spec PROMPT="..."` Makefile target: the fresh-prompt → validated
  spec entry point.
- Add `make spec-and-plan PROMPT="..."` Makefile target: end-to-end — fresh
  prompt → validated spec → COMMAND_RUNWAY plan prompt on stdout.

**Verify gate:**
- `make spec PROMPT="<a brand-new feature request>"` → a validated spec saved
  to the corpus (exit 0 on first or retry attempt).
- `make spec-and-plan PROMPT="<a brand-new feature request>"` → both a saved
  spec AND the runbookprompt + spec emitted to stdout.
- `make test` → still all pass (exit 0).
- `make validate` → all corpus pairs (now including the fresh-prompt ones)
  pass the hardened gate.

**Status:** ✅ Complete. Tested with two fresh prompts not in the seed bank:
1. "Add a webhook endpoint that accepts incoming Stripe event payloads,
   verifies the Stripe signature, and enqueues the event for async
   processing..." → valid spec saved on first Ollama attempt
   (`task_id: add-stripe-webhook-endpoint`).
2. "Add an endpoint that lists all active verification sessions for the
   authenticated publisher..." → valid spec saved AND the full
   runbookprompt + spec emitted as a plan prompt (`task_id:
   list-active-sessions-endpoint`).

Corpus now 12 pairs (10 from Sprint 1 regeneration + 2 fresh end-to-end NL
prompts); 12/12 pass the hardened validator. `make test` → 45/45 pass.

**Known limitation discovered:** prompts that explicitly ask for a regex
header value (e.g. "Retry-After: \d+") cause the model to embed a regex
inside a YAML double-quoted scalar, which YAML rejects (`\d` is not a valid
YAML escape). The model cannot recover within 3 retries. Fix belongs in a
future sprint: either teach the prompt to single-quote regex patterns, or
add a validator pre-processor that single-quotes suspicious regex-like
string values.

**Resolved (added before Sprint 4):** Added a YAML pre-processor to
`scripts/validator.py` — `preprocess_yaml()` runs before `yaml.safe_load`,
detects double-quoted scalars containing backslash escapes that are not
valid YAML escapes (regex character classes like `\d`, `\w`, `\s`, `\.`,
`\[`, `]`, `(`, `)`, `*`, `?`, `|`), and converts the offending value to
single-quoted form (single-quoted YAML treats backslash literally). Valid
YAML escapes (`\n`, `\t`, `\\`, `\"`, `\xNN`, `\uNNNN`) are left untouched.
7 dedicated tests added (`test_preprocessor_*`); the exact rate-limiter
YAML block now validates cleanly. Total tests: 52/52 pass.

**Remaining separate issue surfaced:** the same rate-limiter prompt now
trips a different gate — the model keeps placing `headers` inside
`verification.expect` (incorrect) instead of beside `expect` under
`verification` (correct, per the SYSTEM_PROMPT rules block). The retry
feedback tells it the right key set but the model cannot restructure in 3
retries. This is a model-vocabulary issue, not a parser issue, and would
benefit from either more explicit scaffolding in the few-shot example or a
validator-side auto-repair suggestion in the error feedback. Not blocking
Sprint 4.

**Resolved (added before Sprint 4):** Root cause was a missing canonical
home for RESPONSE-header assertions. The existing few-shot demonstrates
REQUEST `headers` (sibling of `expect`) but the model had no template for
asserting a response header like `Retry-After`, so it conflated the two and
stuffed `headers` inside `expect`. Fix: (1) added `headers_contain` as a
new canonical http expect key (a map of header-name → required-substring,
lives inside `expect`); (2) added a third few-shot task
(`rate-limited-endpoint`) with two goals — L1 (200 under limit) and L2
(429 over limit with `headers_contain: { Retry-After: '\d+' }`) — that
explicitly contrasts request-headers placement (sibling of `expect`) vs
response-headers placement (inside `expect` as `headers_contain`); (3)
rewrote the http rules block in SYSTEM_PROMPT with two side-by-side
inline YAML examples making the placement distinction unambiguous, plus
an explicit "Regex patterns MUST use single quotes" rule. Tests added:
`test_headers_inside_expect_is_rejected` (the old mistake now caught),
`test_headers_contain_is_accepted` (the new key works). Total: 54/54 tests
pass. End-to-end: the rate-limiter prompt that previously failed 3 retries
now produces a valid spec on the FIRST Ollama attempt, with the model
correctly emitting `headers_contain: { Retry-After: '\d+' }` inside
`expect` and `Authorization` as a sibling of `expect`. Corpus 13/13 pass.

---

## Sprint 4 — Skill packaging: self-contained skill that consumes validated YAML specs

The previous sprints made artifacts compatible. This sprint bundles the result as a self-contained skill an agent can load without cloning the whole repo.

**Deliverables:**
- Author the skill `SKILL.md` that documents the full flow: human NL → spec YAML (via the prompt + validator) → human review → COMMAND_RUNWAY plan.
- Bundle the validator as a runnable script the skill can invoke.
- Bundle the updated `runbookprompt.md` (from Sprint 2) and the runbook template.
- Add a "Usage" section: how a human invokes the skill, what it produces, where the artifacts go.

**Verify gate:**
- Load the skill via `skill_view` — confirm it loads cleanly, produces a validated spec for a novel prompt, and then a plan draft.
- `make check` → still passes (exit 0).
- `make test` → still all pass (exit 0).
- The skill is self-contained: no dependency on the repo's other scripts except the bundled validator.
