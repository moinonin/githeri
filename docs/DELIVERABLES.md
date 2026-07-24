# Deliverables & Architectural Roadmap

## Current State: Spec-Forge (Complete)

**Sprints 0-4 delivered:**
- Hardened validator with canonical vocabulary + YAML pre-processor
- NL → validated spec pipeline (3 retries, rejection-based learning)
- `runbookprompt.md` ACCEPTED INPUT FORMATS (YAML → COMMAND_RUNWAY mapping)
- Full Makefile flow: `generate` → `validate` → `spec` → `spec-and-plan` → `plan`
- `spec-forge` skill bundle registered and loadable

**Artifacts:**
| File | Purpose |
|------|---------|
| `scripts/validator.py` | Canonical vocab gate + regex-in-YAML pre-processor |
| `scripts/run_pipeline.py` | NL → Ollama → YAML → validate → save |
| `scripts/plan_from_spec.py` | Validated spec → runbookprompt + spec (plan prompt) |
| `skills/spec-forge/` | Self-contained skill bundle |
| `docs/SPRINTS.md` | Full evidence trail |

**Current verify gates:**
```
make test      → 54/54 pass
make validate  → 14/14 corpus pairs pass
make check     → still passes
make spec-and-plan PROMPT="..." → fresh NL → spec + plan on 1st attempt
```

---

## Architectural Ladder: From Spec-Forge to Full LLM

### LEVEL 1: SPEC-FORGE (COMPLETE)
- **Scope**: NL → validated spec → COMMAND_RUNWAY plan
- **Model**: Fixed `qwen2.5-coder:7b-instruct` (7B params)
- **Execution**: Human runs `make` targets; plan prompt fed to executor
- **Loops**: 3 retries on validation failure; no autonomous code execution

---

### LEVEL 2: AUTONOMOUS CODING AGENT (NEXT LOGICAL STEP)

**Missing capabilities:**

| Capability | Current | Needed |
|------------|---------|--------|
| Code execution | ❌ Human runs commands | ✅ Agent runs shell, reads/writes files, runs tests |
| Error recovery | 3 retries on spec validation | Iterative fix → run → test → repeat until green |
| Memory | None between runs | Persistent context (files changed, test results, decisions) |
| Multi-file awareness | Single spec → single plan | Cross-file refactoring, dependency tracking |
| Tool use | `make` only | Shell, git, linter, typechecker, debugger, browser |
| Autonomy | Human gates every step | Self-directed until blocked/uncertain |

**Minimal viable agent architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR (planner + executor loop)                     │
│    • Reads spec → produces COMMAND_RUNWAY plan              │
│    • For each stage:                                        │
│        1. Inspect (read_file, search_files, grep)           │
│        2. Mutate (write_file, patch, shell)                 │
│        3. Verify (run tests, lint, typecheck)               │
│        4. On fail: diagnose → patch → retry (max N)         │
│    • Persists execution log (runbook) + file state          │
│    • Escalates to human only on:                            │
│        - Ambiguous spec                                     │
│        - Max retries exceeded                               │
│        - Architectural decision needed                      │
└─────────────────────────────────────────────────────────────┘
         ↑                    ↑
    SPEC-FORGE SKILL    TOOL SANDBOX (shell, git, python, etc.)
```

**What to build (3-4 sprints):**
1. **Execution runtime** — wrap `terminal`, `read_file`, `write_file`, `patch`, `search_files` into typed tool interface with timeouts and rollback
2. **State store** — SQLite/JSON log of (command → output → file diff) per run; enables "what did I change?" queries
3. **Retry policy** — exponential backoff on test failure; on 3rd failure, generate a *new* sub-spec for the failing unit
4. **Human-in-the-loop hooks** — WebSocket/stdio for approval prompts; CLI fallback

**Effort:** ~3-4 focused sprints. COMMAND_RUNWAY skill already *is* the plan format; agent just needs to execute it.

---

### LEVEL 3: GENERAL-PURPOSE CODING AGENT (CODEX/CLAUDE-CODE PARITY)

**Adds:**

| Capability | Level 2 | Level 3 |
|------------|---------|---------|
| Multi-repo | Single repo | ✅ Workspace awareness, monorepo, submodules |
| Language agnostic | Python/TS focus | ✅ Any language via tree-sitter + LSP |
| Long-horizon | Single feature | ✅ Multi-feature epics, dependency ordering |
| Self-improvement | Fixed prompts | ✅ RLHF on execution traces, few-shot mining |
| Team workflows | Solo | ✅ PR creation, review, CI integration |

**New infrastructure:**
- **LSP integration** — `pyright`, `typescript-language-server`, `rust-analyzer` for semantic navigation
- **Git workspace** — branch per feature, auto-commit per stage, PR generation
- **Context compression** — sliding window + summarization for 100k+ token contexts
- **Eval harness** — SWE-bench style: run agent on real issues, measure pass rate

**Effort:** 6-12 months focused engineering. Spec-Forge becomes a *sub-skill* (spec generation).

---

### LEVEL 4: FULL LLM (FOUNDATION MODEL TRAINING)

| Dimension | Spec-Forge Today | Full LLM |
|-----------|------------------|----------|
| Parameters | 7B (frozen) | 7B-70B trained from scratch or continued pretrain |
| Data | 14 prompt-spec pairs | 1T+ tokens (code + specs + plans + execution traces) |
| Training | None (few-shot) | Pretrain → SFT → RLHF → RLAIF |
| Compute | 0 GPU-hours | 10k-1M GPU-hours |

**If building a custom model that internalizes COMMAND_RUNWAY:**

**Phase 1: Data flywheel (3-6 months)**
```
SPEC-FORGE → generates 100k validated specs
     ↓
COMMAND_RUNWAY EXECUTOR → runs plans, logs execution traces (success/fail)
     ↓
TRAINING CORPUS:
  • (NL prompt → validated spec) pairs          ← SFT phase 1
  • (spec → COMMAND_RUNWAY plan) pairs          ← SFT phase 2  
  • (plan stage → code patch → test result)     ← RLHF reward signal
  • (failure → diagnosis → corrected patch)     ← RLAIF / self-correction
```
- Need: 50k-100k high-quality (spec, plan, execution) triples
- Use `qwen2.5-coder:7b` as base; continue pretrain on code+spec corpus
- SFT on the triples; RLHF with "tests pass" as reward signal

**Phase 2: Model training (6-18 months depending on scale)**
- 7B model: ~10k A100-hours for continued pretrain + SFT
- 32B model: ~100k A100-hours
- Key insight: *execution traces* are the differentiator. No open dataset has (spec → plan → code → test result) chains.

**Phase 3: Deployment**
- Distill to 1.5B for edge; serve 7B/32B on GPU cluster
- The model *becomes* the orchestrator: no separate `make spec` / `make plan` — it does both in one forward pass with tool use.

---

## Recommended Path: BUILD LEVEL 2 FIRST

**Don't train a model yet.** ROI on custom LLM is speculative until you have:
1. A working autonomous agent (Level 2) generating *real* execution traces
2. Measured eval metrics (pass@k on internal benchmark)
3. Data flywheel producing 1000+ traces/week

**Pragmatic path:**
```
Sprint 5-6:  Autonomous executor (Level 2) — wraps COMMAND_RUNWAY + tools
Sprint 7-8:  Eval harness + SWE-bench style benchmark on internal codebase
Sprint 9-10: Data flywheel → 10k execution traces
Sprint 11+:  Decide: continue agent engineering OR invest in custom model training
```

**Spec-Forge is already the hardest part solved** — the NL→spec bridge with a validator that *teaches* the model. Everything else is standard agent scaffolding.

---

## Immediate Next Steps (if proceeding)

1. **Level 2 executor scaffold** (~500 lines):
   - Reuse `scripts/validator.py`, `runbookprompt.md`, `plan_from_spec.py`
   - Tool sandbox: `terminal`, `read_file`, `write_file`, `patch`, `search_files`
   - Orchestration loop: inspect → mutate → verify → log → retry

2. **Eval harness**:
   - Curate 20-50 real issues from your codebase
   - Measure pass@1, pass@5, time-to-fix

3. **Data flywheel**:
   - Agent runs → logs (spec, plan, code patches, test results) → SQLite
   - Target: 1000 traces/week before considering model training

**Decision point:** After 10k traces + eval metrics, decide whether Level 2 agent is sufficient or custom model training is justified.

---

## Summary

| Level | What | Effort | Prerequisite |
|-------|------|--------|--------------|
| 1. Spec-Forge | NL → validated spec → plan | ✅ DONE | — |
| 2. Autonomous Agent | Plan → code → test → retry | 3-4 sprints | Spec-Forge |
| 3. General Agent | Multi-repo, LSP, team workflows | 6-12 months | Level 2 + eval |
| 4. Custom LLM | Internalized methodology | 6-18 months | Level 2 flywheel data |

**Bottom line:** Spec-Forge (Level 1) is the hardest part solved. Level 2 is engineering, not research. Level 4 is only justified after Level 2 proves it can generate the training data a custom model would need.