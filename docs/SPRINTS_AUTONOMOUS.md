# SPRINTS — Autonomous Pipeline Execution

Tracking model/executor experiments and decisions for the command-runway-autonomous pipeline.

---

## Summary (2026-07-30)

**THIRD_IMPROVE_SPEC**: Pipeline analysis from a 10-spec batch run revealed 7 recurring failure patterns. Implemented all 7 fixes:

1. **Minimal structural skeleton** in SYSTEM_PROMPT — eliminated top-level field confusion
2. **task_id validator check** — rejects L11/G18-style IDs, requires descriptive slug
3. **Verification types & expect keys table** — explicit vocabulary reduces hallucinated keys
4. **Placeholder ban strengthened** — concrete examples in prompt + validator hint
5. **Helpful error hints** — "These fields belong inside a goal under `local_goals`"
6. **depends_on validator hints** — rejects L/G refs, redirects to task_ids/stage names
7. **Structural acceptance criteria template** — local goal field, not top-level

All 90 tests passing. Complex prompts (scheduled tasks, multi-endpoint features) now consistently produce valid specs with all enrichment fields after 2-3 retries.

**Prompt-few-shot model matrix** (final, after multiple iterations):

| Model | Default? | Spec Gen Quality | Notes |
|-------|----------|------------------|-------|
| **qwen2.5-coder:7b-instruct** | ✅ Yes | Best structure compliance | Default; sometimes misses structure on 1st attempt, retries fix it |
| qwen3.5-4b-128k | No (was regressed) | Good | Larger context; was default until model regression discovered |
| qwen3.5-9b-code:128k | No | Excellent | Times out at 600s on M1 — too slow for batch runs |
| deepseek-r1:7b | No | Excellent structure understanding | YAML syntax errors (inline comments after quotes, @ in plain values, indentation) |
| **Nemotron 3 Ultra** | Cloud | Excellent | Via Together AI (`--provider nvidia`), best quality when API key available |

**Generation mode matrix** (Makefile):

| Target | Behavior | Use case |
|--------|----------|----------|
| `make generate N=10` | 10 random specs from 475-prompt seed bank | Standard batch runs |
| `make generate N=random` | Same as N=10, explicit mode | Scripting clarity |
| `make generate N=all` | All 475 seed prompts in sequential order | Full corpus generation |
| `make generate-random` | Alias: 10 random specs | Quick test runs |
| `make generate-all` | Alias: ALL seed prompts in order | Full coverage |

---

## Summary (2026-07-29)

Tested the full autonomous pipeline (NL prompt → spec → plan → runbook → execute) across multiple model and executor configurations. Spec generation is stable. Hermes executor requires further prompt engineering to drive actual file creation. Scoring expanded to cover spec quality, execution outcomes, and pipeline health.

---

## Known Issues & Fixes

### 1. YAML Truncation / Colon-in-Description (FIXED)

**Problem:** `qwen2.5-coder:7b-instruct` generates specs with unquoted colons in `description:` fields (e.g. `description: CREATE: add file`), breaking `yaml.safe_load` at parse time. Also truncates YAML mid-document when hitting token limits.

**Fix:** Added retry loop in `generate_spec_with_llm()` in `autonomous_execute.py`. On `yaml.YAMLError`, re-prompts the LLM with explicit instruction to quote values containing colons. 3 retries max.

**Files:** `autonomous_execute.py` lines 895-924 (parse retry loop), spec-forge-scorer `spec_quality_score()` detection.

---

### 2. Hermes Executor — Context Window Gate (RESOLVED)

**Problem:** `qwen2.5-coder:7b-instruct` has 32K context. Hermes Agent requires minimum 64K. Agent refuses to start.

**Resolved by:** Using models with 128K context (specforge-128k, qwen3.5-4b-128k). Created custom Ollama modelfiles with `PARAMETER num_ctx 131072`.

---

### 3. Hermes Executor — Model Tools Support (PARTIALLY RESOLVED)

**Problem:** `specforge-128k:latest` lacks tool-calling capability in its Ollama modelfile template. Hermes needs tools for `hermes chat -q` execution. Returns HTTP 400 "does not support tools".

**Resolution:** `qwen3.5-4b-128k` supports tools and passes the 64K context gate. It connects successfully through the proxy at `localhost:20128` (custom provider). However, the model doesn't execute runbook commands — it calls `clarify` or `skill_view` instead of writing files. This is a prompt engineering issue in `execute_with_hermes()`, not a model capability issue.

**Model compatibility matrix:**

| Model | Context | Tools | Speed (M1 16GB) | Spec Gen | Executor | Status |
|-------|---------|-------|-----------------|----------|----------|--------|
| qwen2.5-coder:7b-instruct | 32K | Yes | Fast | Works (with YAML retry) | Fails 64K gate | Deprecated |
| specforge-128k:latest | 128K | No | Fast | Works (clean YAML) | Fails tools (HTTP 400) | Spec-only |
| qwen3.5-9b-code:128k | 128K | Yes | Slow | Works | Times out at 600s | Too slow |
| qwen3.5-4b-128k | 128K | Yes | Fast | Works (clean YAML) | Connects but doesn't execute | Needs prompt fix |
| qwen3.5:0.8b | 2048 | TBD | Very fast | Untested | Context too small | N/A |

---

### 4. Scoring Expansion (DONE)

Added three new scoring dimensions to `spec-forge-scorer/scripts/runbook_scorer.py`:

- **`spec_quality_score()`** — truncated YAML detection, colon-in-description detection, goal count checks, verification-type checks, sequential ID checks
- **`execution_score()`** — parses RUNBOOK Section 4 (execution log) and Section 5 (goal checks), penalizes FAIL/PENDING, detects crash signatures (uvicorn, click/core.py, "Stage 4 FAILED", "EXECUTION FAILED")
- **`pipeline_health_score()`** — LLM call count, YAML parse retry count, spec validation retry count, timeouts, connection errors, stage failures, pipeline FAILED status

Tests: `tests/test_runbook_scorer.py` — 38 tests, all passing.

---

### 5. Pipeline UX Improvements (DONE)

Added three new flags to `run_autonomous.py` and `autonomous_execute.py`:

- `--fresh` — removes the output directory before each run (cleans stale files from prior experiments)
- `--exec-model` — use a different model for the executor stage than for spec generation
- `--exec-provider` — use a different provider for the executor stage

Also fixed: executor timeout now scales with `--timeout` (at least 600s for Hermes agent tool-calling).

---

## Decision Log

### 2026-07-29: Split-model vs single-model

Implemented `--exec-model` / `--exec-provider` flags to allow split-model operation. Tested both approaches:

- **Split:** specforge-128k (Ollama, spec gen) + qwen3.5-4b-128k (proxy, executor) — spec gen works, executor connects but doesn't execute commands
- **Single:** qwen3.5-4b-128k (proxy, both stages) — spec gen works, executor connects but doesn't execute commands

Both approaches have the same executor bottleneck: the Hermes executor prompt doesn't give the model enough direction to actually write files. The split approach adds complexity without benefit until the executor prompt is fixed.

**Current recommendation:** Use single-model (qwen3.5-4b-128k via proxy) for simplicity. The split flags remain available for when a larger tools-capable model is needed for execution.

### 2026-07-29: Python executor (fallback option)

If the Hermes executor prompt fix proves difficult, fix the `--executor python` path instead. Known bug: the Python executor tries to start uvicorn for HTTP verification, causing recursion when run from within `autonomous_execute.py`. Fix: detect and prevent the recursive invocation.

---

## Next Steps

1. **Fix Hermes executor prompt** — make `execute_with_hermes()` prompt explicit: "For each `write_file` command, generate the file content yourself using the spec and write it to disk." The 4B model currently calls `clarify` or `skill_view` instead of acting.
2. **Fix `--executor python` path** — prevent the uvicorn recursion crash (original Stage 4 failure). This bypasses Hermes entirely and runs runbook commands directly via the LLM-backed file generator.
3. **Proxy dependency** — the executor requires the proxy at `localhost:20128` to be running. Document the startup procedure or add a health-check before execution.
4. **Score a real run** — once the executor actually creates files and runs tests, use the new `execution_score()` and `pipeline_health_score()` functions to evaluate the full pipeline end-to-end.
