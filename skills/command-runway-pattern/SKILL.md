---
name: command-runway-pattern
description: "COMMAND_RUNWAY: a generic, agent-agnostic method for transforming specs into verified implementations. Three layers — prompt (generate plan), plan (static stages), runbook (log execution). Any coding agent can use it."
version: 2.0.0
author: Nous Research
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, execution, verification, spec-driven, runbook, agent-agnostic]
    related_skills: [writing-plans, subagent-driven-development, test-driven-development]
---

# COMMAND_RUNWAY Method

## What This Is

COMMAND_RUNWAY is a **spec-to-verified-implementation method** for any coding agent. It binds programming work to structured inspection, atomic commands, and objective verification — so an executing agent never invents an unstated step and never claims success without a test passing.

It is not a fixture for one project. It is a three-layer system that any agent (Claude Code, Cursor, Hermes, OpenCode, human) can adopt.

---

## The Three Layers

| Layer | Document | When | Purpose |
|-------|----------|------|---------|
| 1. Prompt | `.runbookprompt.md` (project-local) or this skill | Before work starts | Generate a stage-by-stage plan from the spec |
| 2. Plan | `COMMAND_RUNWAY.md` or embedded in issue/PR | Once per feature | Static artifacts: stages, commands, expected outputs, success gates |
| 3. Runbook | `.runbook.md` or equivalent execution log | During execution | Record what actually happened: runtimes, retries, failures, verifications |

**Flow:** read spec → (Layer 1 prompt) → produce Layer 2 plan → (begin Layer 3 runbook at first command) → execute each command, log it, verify, only advance on pass.

---

## Taxonomy (Use the Same Vocabulary Everywhere)

Work is decomposed into three units of escalating granularity:

| Unit | Definition | Typical Size |
|------|-----------|--------------|
| **Feature** | One deliverable described by a spec — the whole runbook | Variable; often 1–5 stages |
| **Stage** | A verification gate — an independently verifiable increment | < 1 hour; 5–15 commands |
| **Command** | One atomic tool invocation (read_file, shell, patch, test run) | One tool call |

**Hard rule:** a stage is incomplete until every command with a ✓ verify role passes. The feature is incomplete until all stages and the global verification gate pass.

---

## Stage Structure (Every Stage Has These)

Each stage in a COMMAND_RUNWAY plan/r refers to one of three roles. Inspection commands must complete before mutation commands in the same stage.

1. **Preconditions** — what must already exist (prior stage verified, tools installed, files present)
2. **Commands** — atomic actions, each tagged with role and dependency
3. **Local Verification** — per-stage ✓ commands; run *after* the stage's mutate commands
4. **Failure Procedure** — on any ✓ failure: stop, diagnose, record corrective note, retry (don't advance)
5. **Completion Condition** — binary gate; either met or not

### Command Roles

| Marker | Role | Allowed To Mutate? |
|--------|------|---------------------|
| ⏾ inspect | Read existing file, check tool version, search code | No |
| ✎ modify | Create/edit a file, run a migration, apply a patch | Yes |
| ✓ verify | Run build/test/lint/curl and assert expected output | No (read-only assertion) |

**Invariant:** Each ✎ command must have at least one ⏾ command in its `depends_on` chain that reads the target before modification. All ⏾ commands that are prerequisites must exit 0 before their dependent ✎ commands start. ✓ commands run after their ✎ dependencies — in the same stage or at stage end.

### Generate → Read → Patch Pattern (Critical for Existing Code)

When working with **existing codebases**, the inspect phase must go beyond "file exists" — you must read and understand the actual implementation before writing tests or modifications. The pattern:

```
⏾ read_file <target>           # Read actual implementation
⏾ read_file <spec>             # Read normative spec
⏾ search_files <pattern>       # Find related files
→ understand actual structure
✎ write_file <test>            # Write tests matching ACTUAL implementation
✎ patch <target>               # Modify if needed
✓ verify                       # Run tests
```

**Anti-pattern (what NOT to do):**
```
✎ write_file <test>            # Write tests assuming structure
⏾ read_file <target>           # Read after - TOO LATE
→ TypeScript errors, schema mismatches, wasted retries
```

**Worked example from Sprint 2 (Evidence Model):**
- The `evidence.ts` implementation already had complete VAP Section 5 schemas with a flat `payload` structure (discriminated union on `evidenceType`)
- My first test attempt assumed a nested `payload: { evidenceType, payload: {...} }` structure
- This caused TypeScript errors because the actual `InteractionEvidencePayloadSchema` defines the inner payload directly, not wrapped
- The fix: read `evidence.ts` first, understand the discriminated union structure, then write tests matching the ACTUAL schema

**Rule:** For any ✎ command that creates tests or modifies existing code, the `depends_on` chain MUST include a ⏾ `read_file` of the target file that was read and understood, not just checked for existence.

See `references/relaxed-inspect-before-mutate-rule.md` for the full rationale and worked example (Generate → Read → Patch pattern).

---

## Command Table Format

Each stage expresses work as an ordered table. The `Deps` column enforces the execution DAG within a stage; `Fallback` records the corrective hook for failures.

```
| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1   | —    | ⏾    | read_file <path>          | file contents known    | search for file, log |
| C2   | —    | ⏾    | <tool> --version          | version string         | install dep or halt   |
| C3   | C1,C2| ✎    | write_file <path>         | file on disk           | revert, re-read spec  |
| C4   | C3   | ✓    | <build-cmd> && <test-cmd> | exit 0                 | see Failure Procedure |
```

- `Deps` lists command IDs that must have exited 0 before this one starts
- `Type` is one of ⏾ / ✎ / ✓ (see Command Roles)
- `Command` is copy-paste runnable — no placeholders where possible; if unavoidable, mark `[PLACEHOLDER: <meaning>]`
- `Expected Artifact / Δ` states exactly what the command produces or changes
- `Fallback if Fail` states the corrective action — not "fix it" but a specific next step

---

## Verification Discipline

**Guiding rule:** No stage proceeds without local verification passing. Global checks run only at stage completion, never after every command (too slow).

- **Local checks:** per-command assertion of exit code, stdout pattern, HTTP status, or file existence
- **Stage gate:** every ✓ command in the stage passes
- **Feature gate:** all stages pass + a global verification block (full test suite, typecheck, lint, integration) runs at the end
- **No soft pass:** "I think it works" is not pressedDo. The token ✓ in the execution log requires the command to have actually run and met its assertion

---

## The Execution Log (Runbook Layer)

This is what separates COMMAND_RUNWAY from a plan-only approach. Every command actually run is recorded — including failures and retries.

```
| Cmd# | Start | End | Exit | Retry# | Output Summary |
|------|-------|-----|------|--------|----------------|
| C3   | 10:23 | :25 | 0    | 0      | 42 lines, sha:3f2a |
| C4   | 10:25 | :30 | 1    | 0      | FAIL: 2 tests failed |
| C4   | 10:30 | :35 | 0    | 1      | 5 tests passing    |
```

- `Retry#` increments on each re-attempt of the same command after a failure
- Failures are never elided — they become learning data (Iteration section) and feed the next plan
- Human reviewer's audit trail: reviewer can scan one table and see what happened

---

## Failure Procedure

When any ✓ command fails or a precondition check fails:

1. **Stop** — do not run further commands
2. **Diagnose** — classify the failure: incorrect assumption | missing dependency | bad implementation | environment problem | test failure | unexpected architecture
3. **Corrective note** — record the diagnosis and the fix in the Iteration section
4. **Retry** — re-run the failed command (increment Retry#); do not advance to dependent commands unless the retry exits 0
5. **Never mute** — do not weaken the assertion to make the command pass. Fix the implementation or fix the test, but never relax the gate silently.

**User-confirmed rule (Sprint 2 VAE):** "We need those failing tests fixed first. Let's do them systematically following the routine we developed." Do not carry known test failures into the next stage — even partially-passing test files must reach green before the stage's completion condition is met. Diagnose root causes in dependency order (schema validity → timestamp/precision → cross-package resolution → assertion correctness), fix at the source, and re-run the full suite for that package before declaring the stage done.

---

## Machine-Readable Extension (Automation Bridge)

A runbook serializes to JSON for orchestration harnesses. Keys a minimal agent harness needs:

```json
{
  "task_id": "<feature-id>",
  "status": "Draft|In-Flight|Verified|Blocked",
  "preconditions": [
    {"id": "P1", "check": "<shell cmd>", "expect_exit": 0}
  ],
  "stages": [
    {
      "id": "StageA",
      "commands": [
        {
          "id": "C1",
          "type": "inspect|modify|verify",
          "tool": "read_file|write_file|patch|shell",
          "args": {...},
          "depends_on": [],
          "expected": {"exit_code": 0, "stdout_contains": "..."},
          "fallback": "<action on failure>"
        }
      ],
      "completion_condition": "<binary rule>"
    }
  ],
  "goals": {
    "local": [{"id": "L1", "assert": {...}}],
    "global": ["G2"]
  }
}
```

**`expected` assertion shapes** (agent picks one or more):
- `exit_code: N`
- `stdout_regex: "pattern"`
- `stdout_contains: "substring"`
- `http_status: N`
- `body_regex: "pattern"`
- `file_exists: "path"`

**`content_ref` resolution** for write_file commands:
- `file://<relative/path>` — load from local file
- `hash://<sha256>` — content integrity-verified (reproducible builds)
- `inline:` — content embedded in the JSON (escape newlines for `inline:`)

**`depends_on`** — command IDs that must have exited 0 before this one starts. Defines the execution DAG. An agent harness enforces this; cycles are errors.

---

## When To Use This Pattern

Use COMMAND_RUNWAY when **any** of these are true:
- The work traces to a formal or semi-formal specification (protocol, architecture doc, RFC, user story)
- Multiple stages depend on each other (mistakes in stage N surface in stage N+3)
- Verification/conformance is a first-class requirement (tests are not optional)
- You want an audit trail of what was tried (retries, fallbacks, deviations)
- The executing agent may differ from the planning agent (portability across tools)

Don't use it for:
- Single-file edits driven by a one-line request (overhead exceeds value)
- Exploratory/throwaway prototypes (the "spike" pattern is a better fit)
- Pure CI tasks (those have their own harnesses already)

---

## Anti-Patterns To Avoid

| Anti-Pattern | Why It Fails | Fix |
|--------------|--------------|-----|
| Stage with no ✓ commands | No gate — agent declares done on vibes | Every stage ends with at least one verifiable check |
| Mutate before inspect | Modifications blind to existing form | Add ⏾ commands before ✎; enforce via `depends_on` |
| Vague "run tests" | Agent can't self-verify; reviewer can't audit | Exact command + `expected` assertion (exit code, stdout pattern, etc.) |
| Skip Execution Log | Plan diverges silently from reality | Always run Layer 3 (runbook) when executing Layer 2 (plan) |
| Relax assertion silently | Premature "done"; regression hiding | Never weaken `expected` to pass — fix the implementation, not the gate |
| Mega-stage (> 1 hr, > 15 commands) | Retry granularity too coarse | Split into multiple stages, each independently verifiable |
| No fallback column | Failures produce dead air | Each ✎/✓ command states the corrective hook |
| Backend mixed with UI in same stage | Blocking coupling; UI churn destabilizes backend | Order stages backend-first; UI stages come last |

---

## Backend-First Ordering (Default Stage Sequencing)

By default, order stages so backend/infrastructure precedes UI/UX. Rationale: backend contracts (APIs, schemas, pipeline outputs) are more stable and easier to verify objectively than UI. UI that calls a stable contract changes less than UI built against a moving backend.

This is a default, not a rule. If the feature is UI-only, ignore it. If backend and UI are tightly coupled in a way that benefits from co-development (rare), merge cautiously.

## Python Virtual Environment Rule (CRITICAL)

When the project uses Python for any backend work:

1. **All Python commands MUST use `.venv`** — NEVER bare `python`, `python3`, or `pip`. Use `.venv/bin/python` and `.venv/bin/pip` explicitly.
2. **Venv precondition**: Every runbook MUST include a precondition `test -d .venv && .venv/bin/python --version`. If false, the FIRST command in Stage A creates it: `python3 -m venv .venv` (or `python3.11 -m venv .venv` if a specific version is required).
3. **No cross-command activation**: If a script sources `. .venv/bin/activate`, the activation MUST happen in the same shell invocation that runs Python. Do NOT assume activation persists across commands.
4. **Venv relocation hazard**: If a `.venv` was created at a different path and moved/copied, its `pyvenv.cfg` and bin shebangs will point to the old location — pip will break. Recreate the venv fresh at the current project path.
5. **Preferred Python version**: When available, prefer `python3.11` (or project-specified version) for venv creation over system `python3` to ensure consistent minor version across team members.

## Make Targets For Backend Entrypoints

All backend entrypoints (scripts, servers, CLIs) MUST have Make targets with:
- **Verbosity**: Each target prints what it's about to do, the command it runs, and the result
- **Documentation**: Each target is documented in README.md (purpose, prerequisites, usage, expected output)
- **Idempotency**: Running twice should not fail or corrupt state
- **Venv usage**: Make targets that invoke Python MUST reference `.venv/bin/python` — never bare `python`

---

## Relationship To Existing Skills

| Skill | Relationship |
|-------|--------------|
| `writing-plans` | COMMAND_RUNWAY Layer 2 (plan) is a specialized form of writing-plans with a runbook and machine-readable extension. Use writing-plans for less structured planning; use COMMAND_RUNWAY when spec-to-verified-implementation with audit trail is required |
| `subagent-driven-development` | Subagent entry points map to COMMAND_RUNWAY stages. Each subagent receives a stage definition (preconditions, commands, verification) and produces an Execution Log row |
| `test-driven-development` | ✓ commands are TDD assertions. The COMMAND_RUNWAY does not prescribe TDD internally, but it is compatible: stage commands may be `test_write_then_implement` pairs |
| `spike` | For throwaway validation. The output of a spike MAY become a precondition for a COMMAND_RUNWAY plan |

---

## Adoption For A New Project

To use COMMAND_RUNWAY on a new repo:

1. **Copy the prompt** — Place `.runbookprompt.md` (or use this skill) at the repo root. It defines the role (Senior AI Execution Architect) and the stage structure.
2. **Generate the plan** — Feed the spec + sprint plan to an agent with the prompt. Produce `COMMAND_RUNWAY.md` (Layer 2). Review with the human before executing.
3. **Create the runbook** — Copy `.runbook.md` template to the repo. The agent fills in the Execution Log during work.
4. **Execute** — Agent works stage-by-stage: preconditions → inspect → mutate → verify → log. Human reviews the runbook audit trail.
5. **Machine-readable (optional)** — If using an orchestration harness, serialize the runbook to JSON (Section 7 of `.runbook.md` template).

No coupling to a specific language, framework, or agent. The skill provides the method; your agent provides the tools.

---

## Linked Templates

- `references/command-runway-pattern.md` — deeper reference and examples (portable across agents)
- `references/relaxed-inspect-before-mutate-rule.md` — clarification on the Generate→Read→Patch pattern
- `references/sprint-02-evidence-model-test-pattern.md` — worked example: Sprint 2 Evidence Model test writing (Generate→Read→Patch pattern + schema details)
- `references/vae-sprint-runbooks-worked-example.md` — 20-sprint worked example from the Verified Attention Engine project
- `references/typescript-monorepo-zod-test-pitfalls.md` — durable test- and lint-plumbing traps (Zod datetime precision, tsdown `.mjs`/`.js` exports, pnpm workspace cross-package resolution, `write_file` pagination guard, minimal reproducer debug pattern, discriminated union `.strict()` enforcement, ESLint v9+ flat config setup, `require()`-to-ES-`import` migration for `no-require-imports`, `prefer-const` fixes, unused vitest import cleanup). Surfaces during ✎ mutate / ✓ verify on TS+Zod+pnpm+ESLint stacks.
- `references/zod-discriminated-union-test-pattern.md` — when testing Zod discriminated unions (e.g., VAP EvidencePayloadSchema), the discriminator field must match exactly; mismatched payload fields are correctly rejected. Test both valid combinations for each discriminator value AND mismatched combinations to verify the union correctly rejects them.
- `references/tsdown-config-pattern.md` — for single-entry packages, tsdown.config.ts should specify `entry: ['src/index.ts']` (not an array of all source files). Multiple entries produce duplicate module outputs; tsdown handles re-exports from the single index.
- `templates/stage-template.md` — blank stage template to copy when authoring a new plan
- `templates/runbook-template.md` — blank runbook template (Layer 3, execution log)

---

## Origin

This method was distilled from the Verified Attention Engine (VAE) project — see `/docs/COMMAND_RUNWAY.md` in that repo for a worked example (22 stages). The VAE instance is not normative; this skill is. This is the generic, agent-agnostic form usable by any coding agent or human engineer.