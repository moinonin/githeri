# COMMAND_RUNWAY — Method Reference

This reference captures the COMMAND_RUNWAY method in depth. For the concise form, see the skill's `SKILL.md`. For blank templates, see `templates/`.

This document is agent-agnostic. It does not assume Hermes, Claude Code, Cursor, Codex, or any specific tool — only that the agent can run shell commands, read/write files, and assert expected outputs.

---

## 1. The Three Layers

```
        ┌────────────────────┐
        │  Layer 1: Prompt   │  .runbookprompt.md (project-local)
        │  (generate plan)   │  OR command-runway-pattern skill
        └─────────┬──────────┘
                  │ feeds spec + sprint plan
                  ▼
        ┌────────────────────┐
        │  Layer 2: Plan     │  COMMAND_RUNWAY.md
        │  (static stages)   │
        └─────────┬──────────┘
                  │ agent begins execution
                  ▼
        ┌────────────────────┐
        │  Layer 3: Runbook  │  .runbook.md (execution log)
        │  (live execution)  │
        └────────────────────┘
```

**Layer 1** transforms intent into a plan. **Layer 2** is the plan itself. **Layer 3** is the execution log that records what actually happened — including deviations, retries, and verifications.

A spec without Layer 3 is a wish. Layer 3 without Layer 2 is undirected typing.

---

## 2. Feature → Stage → Command

| Unit | What It Is | Size | Verified By |
|------|------------|------|-------------|
| Feature | The whole runbook — one deliverable from a spec | 1–5 stages | Global verification (Section 5 of runbook) |
| Stage | Verification gate — independent increment | < 1 hour, 5–15 commands | Stage's ✓ commands + Local Goal Checks |
| Command | One atomic tool invocation | One tool call | Its `expected` assertion |

A stage is atomic for retry purposes. A command that fails is retried in place; a stage whose completion condition can't be met is re-run, not partially salvaged.

---

## 3. Command Roles and the ⏾→✎→✓ Discipline

| Marker | Role | Can mutate? | Allowed after |
|--------|------|-------------|---------------|
| ⏾ inspect | read, search, version-check | No | stage start |
| ✎ modify | write_file, patch, run migration | Yes | all ⏾ in stage exit 0 |
| ✓ verify | build, test, lint, curl, assert | No (assertion only) | mutated ✎ commands it depends on |

**Invariant:** Each ✎ command must have at least one ⏾ command in its `depends_on` chain that reads the target before modification. All ⏾ commands that are prerequisites must exit 0 before their dependent ✎ commands start. ✓ commands run after their ✎ dependencies — in the same stage or at stage end.

---

## 4. The Execution DAG

Within a stage, the `Deps` column of each command lists command IDs that must have exited 0 before it starts. This forms a DAG. An agent harness (or human) enforces it:

- C1 (⏾ read spec) → C2 (⏾ read existing code) → C3 (✎ write file) → C5 (✎ patch) → C6 (✓ build) → C7 (✓ test)
- C3 cannot start before C1 and C2 exit 0
- C6 cannot start before C5 exits 0
- If C6 fails, C7 does not start; C5 is retried (Retry# += 1), then C6

Cycles are errors. Commands without `Deps` can run in parallel if the harness supports it.

---

## 5. Verification Gate Structure

```
Stage:
  ⏾ ⏾ ✎ ✎ ✎ → [stage-local ✓] → [Local Goal Checks]
                              ↓ pass
                        (advance to next stage)
                              ↓ fail
                        diagnose → retry ✎ → retry ✓
                              ↓
                        [retry cannot satisfy completion condition]
                              ↓
                        stage fails; human review
```

Global checks run only at stage completion, not after every command — running the full test suite after every file edit is prohibitively slow.

---

## 6. Failure Procedure (Detailed)

On any ✓ failure or precondition failure:

1. **Stop** — dependent commands do not run
2. **Diagnose** — classify the root cause:
   - Incorrect assumption (spec misunderstood, API shape wrong)
   - Missing dependency (tool not installed, package missing)
   - Incorrect implementation (bug in the code just written)
   - Environment problem (Node version, missing service, filesystem perms)
   - Test failure (flaky, assertion too strict, or test itself is wrong)
   - Unexpected architecture (discovered during ⏾ phase, invalidates plan)
3. **Record** — write the diagnosis and the corrective action in the runbook's Iteration section. Include the failed command's output summary (last ~50 lines, not the full log).
4. **Retry** — re-run the failed command with `Retry#` incremented. Do not advance to dependent commands unless the retry exits 0.
5. **Never weaken silently** — if the assertion itself was wrong (test bug, not impl bug), fix the assertion and document the change. Do not relax the gate to make a failing implementation pass.

---

## 7. Machine-Readable Extension

The runbook serializes to JSON for orchestration harnesses. See `templates/runbook-template.md` Section 7 for the full schema. Key fields an agent harness needs:

- `preconditions[]` — checked before any command runs
- `stages[].commands[]` — the DAG; each has `id`, `type`, `tool`, `args`, `depends_on`, `expected`, `fallback`
- `expected` assertion — one or more of: `exit_code`, `stdout_regex`, `stdout_contains`, `http_status`, `body_regex`, `file_exists`
- `content_ref` — for write commands: `file://`, `hash://`, or `inline:` (escape newlines for `inline:`)
- `goals.local[].assert` — per-feature goal assertions (run at stage end, not per command)
- `goals.global[]` — global regression check IDs (run only at stage completion)

A harness that implements this JSON can drive any agent that supports `shell`, `read_file`, `write_file`, and `patch` tools.

---

## 8. Compatibility Across Agents

The method prescribes the structure, not the tool names. Adapters:

| Agent | ⏾ inspect | ✎ modify | ✓ verify |
|-------|-----------|-----------|----------|
| Hermes | `read_file`, `search_files` | `write_file`, `patch` | `terminal`, inline assertions |
| Claude Code | `read_file`, `grep` | `apply_patch`, `write_file` | `bash` |
| Cursor | file reads via MCP | edit operations | shell tool |
| Codex CLI | `cat`, `rg` | inline edits | `npm test` / bash |
| Human | open file | text editor | shell |

As long as the agent can read, write, and run commands with assertions, COMMAND_RUNWAY applies. The JSON schema's `tool` field is a string — agents map it to their native tool names.

---

## 9. When Not To Use COMMAND_RUNWAY

- **Single-file edit driven by a one-line request.** Overhead exceeds value. Just do it.
- **Exploratory throwaway prototypes.** Use a "spike" pattern instead; a spike's output may later become a precondition for a runbook.
- **Pure CI tasks.** Those have their own harnesses (e.g. GitHub Actions) and don't benefit from the stage/verification-gate structure.

---

## 10. Key Learning: Generate → Read → Patch for Test Creation

When creating tests for existing implementations, the **Generate → Read → Patch** pattern prevents type mismatches:

1. **Generate** the test mentally (or draft it)
2. **Read** the ACTUAL implementation and normative spec
3. **Patch** the test to match the actual schema/structure

**Anti-pattern (causes TypeScript errors):**
```
✎ write_file test_file.ts   # Assume nested payload.payload structure
→ Type errors: "Property 'payload' does not exist on type..."
```

**Correct pattern:**
```
⏾ read_file packages/core/src/evidence.ts    # Read ACTUAL implementation
⏾ read_file docs/specs/0001-vap.md           # Read normative spec (VAP §5)
✎ write_file packages/core/src/evidence.test.ts  # Tests matching ACTUAL schema
```

**Specific Example (Sprint 2 Evidence Model):**
- The VAP spec shows `payload: { evidenceType, payload: {...} }` (nested)
- The actual implementation uses a **discriminated union** with flat structure
- Tests written against the spec without reading implementation had:
  - `payload: { evidenceType: 'E-INTERACTION', payload: { clickCount: 5 } }` → TypeError
  - Correct: `payload: { evidenceType: 'E-INTERACTION', payload: { clickCount: 5 } }` (already flat)

**Rule for AI agents:** When creating tests for existing code, ALWAYS read the implementation first. The normative spec is authoritative for behavior, but the implementation is authoritative for structure.
