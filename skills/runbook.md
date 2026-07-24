# COMMAND_RUNWAY: <Feature Name>

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** `<path/to/spec.md>` (<Feature # or Task #>)
**Generated With:** `.runbookprompt.md` (plan generation prompt)
**Agent/Responsible:** AI Execution Agent + Human Reviewer
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

---

## 0. Taxonomy

This runbook uses three layers of granularity:

| Layer | Unit | Purpose | Typical Size |
|-------|------|---------|---------------|
| Feature | The whole runbook | One deliverable built from a spec | 1–5 stages |
| Stage | Verification gate | Independently verifiable increment of work | < 1 hour, 5–15 commands |
| Command | Atomic action | One tool invocation (shell, file edit, test run) | One tool call |

**Daily flow:** Feature → Stages → Commands. **No stage proceeds until its local checks pass. Global checks run only at stage completion, not after every command.**

---

## 1. Intent & Goals

### Global Project Goals (reminder)
Pre-existing project goals this feature must not break.
- G1: <global capability — e.g. "all API endpoints return consistent error shapes">
- G2: <global capability>

### Task-Local Goals
_Once this feature is done, I should be able to…_
- L1: <observable outcome — e.g. "POST /register returns 201 with user ID">
- L2: <observable outcome — e.g. "duplicate email returns 409 with EMAIL_EXISTS">
- L3: <observable outcome>

---

## 2. Preconditions

_Everything that must already exist before command C1 runs. If any precondition is false, do not start — resolve the dependency first and log it in Section 5._

| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | `<tool/dep>` installed (e.g. Node ≥ 20, pnpm ≥ 9) | `<tool> --version` |
| P2 | `<file/dir>` exists (e.g. `schema.prisma`, `packages/core/`) | `test -f <path>` |
| P3 | Prior stage `<Stage N>` verified complete | Section 4 of that runbook shows ✅ |
| P4 | `<env var / config>` set | `echo $<VAR>` non-empty |

---

## 3. Command Runway

_Each command is a discrete, auditable action.**No implicit steps — if a step isn't listed here, don't do it.** Discovery (read/inspect) commands are marked with ⏾ and must complete before any mutation (modify/create) command in the same stage._

### Stage A: <Stage Name>

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat <existing-file>` or `read_file <path>` | file contents understood | file may not exist — search for it, log finding |
| C2 | — | ⏾ inspect | `<tool> --version` | version string | dependency missing — install or halt |
| C3 | C1,C2 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C3 content, re-read spec, retry |
| C4 | C3 | ✎ modify | `patch <path>` <old> → <new> | file patched | re-read file fresh, retry with exact snippet |
| C5 | C3 | ✎ create | `<db migration command>` | migration SQL + schema updated | inspect migration diff, fix schema, re-run |
| C6 | C5 | ✎ create | `write_file <handler>` business logic | handler uses client lib | compare with C3 scaffold, fix references |
| C7 | C6 | ✓ verify | `<build cmd> && <test cmd>` | tests pass, exit 0 | revert C6, re-prompt with error context |
| C8 | C7 | ✓ verify | `curl <endpoint>` | expected HTTP status + body | check server logs, diagnose, revisit C6 |

**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality — failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | 10:23:01 | 10:23:02 | 0 | 0 | read 248 lines |
| C2 | — | 10:23:03 | 10:23:03 | 0 | 0 | pnpm 9.0.0 |
| C3 | C1,C2 | 10:23:10 | 10:23:15 | 0 | 0 | wrote 42 lines, sha:3f2a |
| C4 | C3 | 10:23:20 | 10:23:25 | 0 | 0 | patched +12/-4 lines |
| C5 | C3 | 10:23:30 | 10:23:45 | 1 | 0 | FAIL: prisma schema missing model — halted |
| C5 | C3 | 10:24:00 | 10:24:12 | 0 | 1 | migration 001_add_user.sql, sha:9a1c |
| C6 | C5 | 10:24:20 | 10:24:50 | 0 | 0 | 120-line handler, sha:b7e1 |
| C7 | C6 | 10:25:00 | 10:25:12 | 1 | 0 | FAIL: 2 tests failed (missing email normalization) |
| C6 | C5 | 10:25:15 | 10:25:40 | 0 | 1 | added email .toLowerCase(), sha:d4f3 |
| C7 | C6 | 10:25:45 | 10:26:00 | 0 | 1 | 5 tests passing |
| C8 | C7 | 10:26:05 | 10:26:08 | 0 | 0 | 201 + {"id":"uuid"} |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion — never after every command (too slow)._

### Local Goal Checks

- **L1:** `curl -X POST /register -d '{"email":"a@b.com","pass":"123"}'` → **201 + {id: "uuid"}** ✅
- **L2:** `npx prisma studio` → user row visible ✅
- **L3:** repeat L1 with same email → `409 {error: "EMAIL_EXISTS"}` ✅

### Global Regression Quick-Checks (at stage completion)
- **G2:** error shape matches `{error: string, details?: any}` across new + existing endpoints — `pnpm test:integration` ✅

---

## 6. Iteration & Notes

- **Deviations from runway:** C4 expanded beyond planned scope — documented inline.
- **Blockers:** none.
- **Commands that needed rework:** C5 (schema incomplete), C6 (email normalization missing). Both logged with Retry# in Section 4.
- **Lessons learned:** <method-level insight — e.g. "always inspect prisma schema before running migrate dev">
- **Next runways:** COMMAND_RUNWAY: <linked feature>

---

## 7. Machine-Readable Extension (JSON)

_Automation bridge. Each runbook can be serialized to JSON for programmatic execution and validation. `commands[].depends_on` defines the DAG; `expected` is a structured assertion, not free text._

```json
{
  "task_id": "auth-register",
  "status": "Verified",
  "generated_with": ".runbookprompt.md",
  "goals": {
    "local": [
      {
        "id": "L1",
        "description": "POST /register returns 201 with user ID",
        "assert": {
          "cmd": "curl -s -o /dev/null -w '%{http_code}' -X POST /register -H 'Content-Type: application/json' -d '{\"email\":\"a@b.com\",\"pass\":\"123\"}'",
          "equals": "201"
        }
      },
      {
        "id": "L3",
        "description": "Duplicate email returns 409",
        "assert": {
          "cmd": "curl -s -X POST /register ...",
          "status_code": 409,
          "body_regex": "EMAIL_EXISTS"
        }
      }
    ],
    "global": ["G2"]
  },
  "preconditions": [
    {"id": "P1", "check": "node --version", "expect_regex": "v(2[0-9]|3[0-9])"},
    {"id": "P2", "check": "test -f server/prisma/schema.prisma", "expect_exit": 0}
  ],
  "stages": [
    {
      "id": "StageA",
      "name": "Register endpoint",
      "commands": [
        {
          "id": "C1",
          "type": "inspect",
          "tool": "read_file",
          "args": {"path": "server/src/routes/auth.ts"},
          "depends_on": []
        },
        {
          "id": "C3",
          "type": "create",
          "tool": "write_file",
          "args": {"path": "server/src/routes/auth.ts", "content_ref": "file://./scaffolds/auth-handler.ts"},
          "depends_on": ["C1", "C2"]
        },
        {
          "id": "C7",
          "type": "verify",
          "tool": "shell",
          "args": {"cmd": "npm run build && npm test -- auth"},
          "expected": {"exit_code": 0},
          "fallback": "revert C6 content and re-prompt with error context",
          "depends_on": ["C6"]
        }
      ]
    }
  ]
}
```

**`content_ref` resolution** — one of:
- `file://<relative/path>` — load content from local file
- `hash://<sha256>` — content integrity-verified by hash (for reproducible builds)
- `inline:` — content embedded directly in the JSON (escape newlines)

**`expected` assertion shapes** — one or more of:
- `exit_code: N`
- `stdout_regex: "pattern"`
- `stdout_contains: "substring"`
- `status_code: N` (HTTP)
- `body_regex: "pattern"` (HTTP)
- `file_exists: "path"` (after command)

**`depends_on`** — command IDs that must complete (exit 0) before this command starts. Defines the execution DAG.

---

## Execution Rules (Mandatory)

1. **Never skip inspection** — ⏾ commands (C1, C2…) must complete before ✎ commands in the same stage.
2. **Never skip verification** — stage is incomplete until its ✓ commands pass.
3. **Never continue after a failed verify** — diagnose in Section 4 (Retry#), produce a corrective note, then retry.
4. **Every command is atomic** — one tool invocation. If a command does two things, split it into two commands.
5. **No implicit steps** — if it's not in the command table, it doesn't happen.
6. **Failures are logged, not hidden** — Section 4 records retries with `Retry#` increment.
7. **Local checks per command, global checks per stage** — running global regressions after every command is wasteful.
8. **Update Last Updated timestamp** — every time the runbook is edited or a command is logged.
```
