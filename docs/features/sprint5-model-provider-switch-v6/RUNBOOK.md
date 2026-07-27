# COMMAND_RUNWAY: sprint-5-model-provider-switching

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** `<path/to/spec.yaml>` (<Feature # or Task #>)
**Generated With:** `.runbookprompt.md` (plan generation prompt)
**Agent/Responsible:** AI Execution Agent + Human Reviewer
**Created:** sprint-5-model-provider-switching
**Last Updated:** 2026-07-27

---

## 0. Taxonomy

This runbook uses three layers of granularity:

| Layer | Unit | Purpose | Typical Size |
|-------|------|---------|---------------|
| Feature | The whole runbook | One deliverable built from a spec | 1-5 stages |
| Stage | Verification gate | Independently verifiable increment of work | < 1 hour, 5-15 commands |
| Command | Atomic action | One tool invocation (shell, file edit, test run) | One tool call |

**Daily flow:** Feature -> Stages -> Commands. **No stage proceeds until its local checks pass. Global checks run only at stage completion, not after every command.**

---

## 1. Intent & Goals

### Global Project Goals (reminder)
Pre-existing project goals this feature must not break.

### Task-Local Goals
_Once this feature is done, I should be able to..._
- L1: CREATE: ModelProviderSwitcher class in run_pipeline.py
- L2: VERIFY: Model provider switching tests pass

---

## 2. Preconditions

_Everything that must already exist before command C1 runs. If any precondition is false, do not start -- resolve the dependency first and log it in Section 5._
| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | Node.js >= 20, pnpm >= 9 installed | `node --version && pnpm --version` |
| P2 | Git repo initialized | `git status` |
| P3 | Prior stage verified complete (if applicable) | Section 4 of prior runbook shows ✅ |

---

## 3. Command Runway

_Each command is a discrete, auditable action. **No implicit steps -- if a step isn't listed here, don't do it.** Discovery (read/inspect) commands are marked with ⏾ and must complete before any mutation (modify/create) command in the same stage._
### Stage 1: CREATE: ModelProviderSwitcher class in run_pipeline.py

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | file may not exist -- search for it, log finding |
| C2 | — | ⏾ inspect | `pnpm --version` | version string | dependency missing -- install or halt |
| C3 | C1,C2 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C3 content, re-read spec, retry |
| C4 | C3 | ✓ verify | `test -f packages/pipeline/src/run_pipeline.py && grep -q 'ModelProviderSwitcher' packages/pipeline/src/run_pipeline.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 2: VERIFY: Model provider switching tests pass

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C5 | C4 | ✓ verify | `pnpm test --filter=@verified-attention/pipeline-model-provider-switching && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality -- failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | 04:02:00 | 04:02:00 | 1 | 0 |  | ERR: cat: packages/core/src/index.ts: No such file or d |
| C2 | — | 04:02:00 | 04:02:01 | 0 | 0 | 9.0.0 |
| C3 | C1,C2 | | | | | |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion -- never after every command (too slow)._

### Local Goal Checks

- **L1:** `test -f packages/pipeline/src/run_pipeline.py && grep -q 'ModelProviderSwitcher' packages/pipeline/src/run_pipeline.py` FAIL ✅
- **L2:** `pnpm test --filter=@verified-attention/pipeline-model-provider-switching && echo 'exit_code=0'` → **PASS** ✅

### Global Regression Quick-Checks (at stage completion)
- **G2:** error shape matches `{error: string, details?: any}` across new + existing endpoints -- `pnpm test:integration` ✅

---

## 6. Iteration & Notes

- **Deviations from runway:** 
- **Blockers:** 
- **Commands that needed rework:** 
- **Lessons learned:** 
- **Next runways:** COMMAND_RUNWAY: <linked feature>

---

## 7. Machine-Readable Extension (JSON)

```json
{
  "task_id": "sprint-5-model-provider-switching",
  "status": "Verified",
  "generated_with": ".runbookprompt.md",
  "goals": {
    "local": [      {
        "id": "L1",
        "description": "CREATE: ModelProviderSwitcher class in run_pipeline.py",
        "assert": {
          "cmd": "test -f packages/pipeline/src/run_pipeline.py && grep -q 'ModelProviderSwitcher' packages/pipeline/src/run_pipeline.py",
          "equals": "0"
        }
      },      {
        "id": "L2",
        "description": "VERIFY: Model provider switching tests pass",
        "assert": {
          "cmd": "pnpm test --filter=@verified-attention/pipeline-model-provider-switching && echo 'exit_code=0'",
          "equals": "0"
        }
      },
    ],
    "global": ["G2"]
  },
  "preconditions": [
    {"id": "P1", "check": "node --version", "expect_regex": "v(2[0-9]|3[0-9])"},
    {"id": "P2", "check": "test -f package.json", "expect_exit": 0}
  ],
  "stages": [
    {
      "id": "Stage1",
      "name": "Stage 1",
      "commands": [
        {"id": "C1", "type": "inspect", "tool": "read_file", "args": {"path": "packages/core/src/index.ts"}, "depends_on": []},
        {"id": "C2", "type": "inspect", "tool": "shell", "args": {"cmd": "pnpm --version"}, "depends_on": []},
        {"id": "C3", "type": "create", "tool": "write_file", "args": {"path": "packages/core/src/new.ts", "content_ref": "file://./scaffolds/new.ts"}, "depends_on": ["C1", "C2"]},
        {"id": "C4", "type": "verify", "tool": "shell", "args": {"cmd": "pnpm build --filter=@verified-attention/core && pnpm test --filter=@verified-attention/core"}, "expected": {"exit_code": 0}, "fallback": "revert C3 content and re-prompt with error context", "depends_on": ["C3"]}
      ]
    }
  ]
}
```

**`content_ref` resolution** -- one of:
- `file://<relative/path>` -- load content from local file
- `hash://<sha256>` -- content integrity-verified by hash (for reproducible builds)
- `inline:` -- content embedded directly in the JSON (escape newlines for `inline:`)

**`expected` assertion shapes** -- one or more of:
- `exit_code: N`
- `stdout_regex: "pattern"`
- `stdout_contains: "substring"`
- `status_code: N` (HTTP)
- `body_regex: "pattern"` (HTTP)
- `file_exists: "path"` (after command)

**`depends_on`** -- command IDs that must complete (exit 0) before this command starts. Defines the execution DAG.
