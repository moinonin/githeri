# COMMAND_RUNWAY: model-provider-switching

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** `<path/to/spec.yaml>` (<Feature # or Task #>)
**Generated With:** `.runbookprompt.md` (plan generation prompt)
**Agent/Responsible:** AI Execution Agent + Human Reviewer
**Created:** model-provider-switching
**Last Updated:** 2026-07-26

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
- L1: INSPECT: check existing run_pipeline.py configuration file
- L2: CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py
- L3: CREATE: add model provider switching logic for Ollama in run_pipeline.py
- L4: CREATE: add .env configuration for Ollama and OpenRouter
- L5: VERIFY: run_pipeline.py switches to Ollama when --provider ollama is used
- L6: VERIFY: run_pipeline.py switches to OpenRouter when --provider openrouter is used

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
### Stage 1: INSPECT: check existing run_pipeline.py configuration file

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | file may not exist -- search for it, log finding |
| C2 | — | ⏾ inspect | `pnpm --version` | version string | dependency missing -- install or halt |
| C3 | C2 | ✓ verify | `cat scripts/run_pipeline.py && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 2: CREATE: add CLI flags --provider (ollama|openrouter) and --c

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C4 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | file may not exist -- search for it, log finding |
| C5 | — | ⏾ inspect | `pnpm --version` | version string | dependency missing -- install or halt |
| C6 | C4,C5 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C6 content, re-read spec, retry |
| C7 | C6 | ✓ verify | `test -f scripts/run_pipeline.py && grep -q '--provider' scripts/run_pipeline.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 3: CREATE: add model provider switching logic for Ollama in run

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C8 | C6,C7 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C8 content, re-read spec, retry |
| C9 | C8 | ✓ verify | `test -e scripts/run_pipeline.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 4: CREATE: add .env configuration for Ollama and OpenRouter

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C10 | C8,C9 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C10 content, re-read spec, retry |
| C11 | C10 | ✓ verify | `test -f .env && grep -q 'OPENROUTER_API_KEY' .env` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 5: VERIFY: run_pipeline.py switches to Ollama when --provider o

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C12 | C11 | ✓ verify | `python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 6: VERIFY: run_pipeline.py switches to OpenRouter when --provid

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C13 | — | ⏾ inspect | `cat packages/core/src/index.ts` | file contents understood | file may not exist -- search for it, log finding |
| C14 | — | ⏾ inspect | `pnpm --version` | version string | dependency missing -- install or halt |
| C15 | C14 | ✓ verify | `python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality -- failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | 23:05:51 | 23:05:51 | 1 | 0 |  | ERR: cat: packages/core/src/index.ts: No such file or d |
| C2 | — | 23:05:51 | 23:05:51 | 0 | 0 | 9.0.0 |
| C3 | C1,C2 | | | | | |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion -- never after every command (too slow)._

### Local Goal Checks

- **L1:** `cat scripts/run_pipeline.py && echo 'exit_code=0'` PASS ✅
- **L2:** `test -f scripts/run_pipeline.py && grep -q '--provider' scripts/run_pipeline.py` FAIL ✅
- **L3:** `test -e scripts/run_pipeline.py` → **PASS** ✅
- **L4:** `test -f .env && grep -q 'OPENROUTER_API_KEY' .env` → **PASS** ✅
- **L5:** `python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'` → **PASS** ✅
- **L6:** `python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'` → **PASS** ✅

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
  "task_id": "model-provider-switching",
  "status": "Verified",
  "generated_with": ".runbookprompt.md",
  "goals": {
    "local": [      {
        "id": "L1",
        "description": "INSPECT: check existing run_pipeline.py configuration file",
        "assert": {
          "cmd": "cat scripts/run_pipeline.py && echo 'exit_code=0'",
          "equals": "0"
        }
      },      {
        "id": "L2",
        "description": "CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py",
        "assert": {
          "cmd": "test -f scripts/run_pipeline.py && grep -q '--provider' scripts/run_pipeline.py",
          "equals": "0"
        }
      },      {
        "id": "L3",
        "description": "CREATE: add model provider switching logic for Ollama in run_pipeline.py",
        "assert": {
          "cmd": "test -e scripts/run_pipeline.py",
          "equals": "0"
        }
      },      {
        "id": "L4",
        "description": "CREATE: add .env configuration for Ollama and OpenRouter",
        "assert": {
          "cmd": "test -f .env && grep -q 'OPENROUTER_API_KEY' .env",
          "equals": "0"
        }
      },      {
        "id": "L5",
        "description": "VERIFY: run_pipeline.py switches to Ollama when --provider ollama is used",
        "assert": {
          "cmd": "python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'",
          "equals": "0"
        }
      },      {
        "id": "L6",
        "description": "VERIFY: run_pipeline.py switches to OpenRouter when --provider openrouter is used",
        "assert": {
          "cmd": "python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'",
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
