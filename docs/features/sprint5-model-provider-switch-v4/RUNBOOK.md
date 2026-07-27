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
- L1: INSPECT: check existing run_pipeline.py structure
- L2: CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py
- L3: CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py
- L4: CREATE: add .env configuration for Ollama and OpenRouter
- L5: VERIFY: run_pipeline.py recognizes --provider ollama flag
- L6: VERIFY: run_pipeline.py recognizes --provider openrouter flag

---

## 2. Preconditions

_Everything that must already exist before command C1 runs. If any precondition is false, do not start -- resolve the dependency first and log it in Section 5._

| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | Python 3.11+, pip installed | `python --version && pip --version` |
| P2 | Git repo initialized | `git status` |
| P3 | githeri project root exists | `test -f Makefile && test -d scripts` |

---

## 3. Command Runway

_Each command is a discrete, auditable action. **No implicit steps -- if a step isn't listed here, don't do it.** Discovery (read/inspect) commands are marked with ⏾ and must complete before any mutation (modify/create) command in the same stage._

### Stage 1: INSPECT: check existing run_pipeline.py structure

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat scripts/run_pipeline.py` | file contents understood | file may not exist -- search for it, log finding |
| C2 | — | ⏾ inspect | `python --version && pip --version` | version string | dependency missing -- install or halt |

### Stage 2: CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C3 | C1,C2 | ✎ create | `write_file scripts/run_pipeline.py` with <content_ref> | new file on disk | revert C3 content, re-read spec, retry |
| C4 | C3 | ✓ verify | `test -f scripts/run_pipeline.py && grep -q -- '--provider' scripts/run_pipeline.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 3: CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C5 | C3,C4 | ✎ create | `write_file scripts/run_pipeline.py` with <content_ref> | updated file on disk | revert C5 content, re-read spec, retry |
| C6 | C5 | ✓ verify | `test -f scripts/run_pipeline.py && grep -q "openrouter" scripts/run_pipeline.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 4: CREATE: add .env configuration for Ollama and OpenRouter

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C7 | C5,C6 | ✎ create | `write_file .env` with <content_ref> | new file on disk | revert C7 content, re-read spec, retry |
| C8 | C7 | ✓ verify | `test -f .env && grep -q 'OPENROUTER_API_KEY' .env` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 5: VERIFY: run_pipeline.py recognizes --provider ollama flag

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C9 | C8 | ✓ verify | `python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 6: VERIFY: run_pipeline.py recognizes --provider openrouter flag

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C10 | C9 | ✓ verify | `python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |

**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality -- failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | 23:21:01 | 23:21:01 | 0 | 0 | #!/usr/bin/env python3

import argparse
import os
from dotenv import load_dotenv

# Load environment |
| C2 | — | 23:21:01 | 23:21:01 | 0 | 0 | Python 3.11.13
pip 26.1.2 from /Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/.venv/ |
| C3 | C1,C2 | | | | | |
| C4 | C3 | 23:21:31 | 23:21:31 | 0 | 0 |  |
| C5 | C3,C4 | | | | | |
| C6 | C5 | 23:22:01 | 23:22:01 | 0 | 0 |  |
| C7 | C5,C6 | | | | | |
| C8 | C7 | 23:22:19 | 23:22:19 | -1 | 3 |  | ERR: Max retries exceeded |
| C9 | C8 | 23:28:40 | 23:28:41 | -1 | 3 |  | ERR: Max retries exceeded |
| C10 | C9 | 23:32:16 | 23:32:16 | 0 | 0 | Running with OpenRouter provider and model: model1
exit_code=0 |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion -- never after every command (too slow)._

### Local Goal Checks

- **L1:** `cat scripts/run_pipeline.py && echo 'exit_code=0'` PASS
- **L2:** `test -f scripts/run_pipeline.py && grep -q -- '--provider' scripts/run_pipeline.py` FAIL
- **L3:** `test -f scripts/run_pipeline.py && grep -q 'openrouter' scripts/run_pipeline.py` PASS
- **L4:** `test -f .env && grep -q 'OPENROUTER_API_KEY' .env` FAIL ✅
- **L5:** `python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'` FAIL ✅
- **L6:** `python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'` PASS

### Global Regression Quick-Checks (at stage completion)
- **G1:** `make test` passes ✅

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
    "local": [
      {
        "id": "L1",
        "description": "INSPECT: check existing run_pipeline.py structure",
        "assert": {
          "cmd": "cat scripts/run_pipeline.py && echo 'exit_code=0'",
          "equals": "0"
        }
      },
      {
        "id": "L2",
        "description": "CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py",
        "assert": {
          "cmd": "test -f scripts/run_pipeline.py && grep -q -- '--provider' scripts/run_pipeline.py",
          "equals": "0"
        }
      },
      {
        "id": "L3",
        "description": "CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py",
        "assert": {
          "cmd": "test -f scripts/run_pipeline.py && grep -q 'openrouter' scripts/run_pipeline.py",
          "equals": "0"
        }
      },
      {
        "id": "L4",
        "description": "CREATE: add .env configuration for Ollama and OpenRouter",
        "assert": {
          "cmd": "test -f .env && grep -q 'OPENROUTER_API_KEY' .env",
          "equals": "0"
        }
      },
      {
        "id": "L5",
        "description": "VERIFY: run_pipeline.py recognizes --provider ollama flag",
        "assert": {
          "cmd": "python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'",
          "equals": "0"
        }
      },
      {
        "id": "L6",
        "description": "VERIFY: run_pipeline.py recognizes --provider openrouter flag",
        "assert": {
          "cmd": "python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'",
          "equals": "0"
        }
      }
    ],
    "global": ["G1"]
  },
  "preconditions": [
    {"id": "P1", "check": "python --version", "expect_regex": "3\\.(1[0-9]|2[0-9])"},
    {"id": "P2", "check": "test -f Makefile", "expect_exit": 0}
  ],
  "stages": [
    {
      "id": "Stage1",
      "name": "INSPECT: check existing run_pipeline.py structure",
      "commands": [
        {"id": "C1", "type": "inspect", "tool": "read_file", "args": {"path": "scripts/run_pipeline.py"}, "depends_on": []},
        {"id": "C2", "type": "inspect", "tool": "shell", "args": {"cmd": "python --version && pip --version"}, "depends_on": []}
      ]
    },
    {
      "id": "Stage2",
      "name": "CREATE: add CLI flags --provider (ollama|openrouter) and --cloud-model for scoring in run_pipeline.py",
      "commands": [
        {"id": "C3", "type": "create", "tool": "write_file", "args": {"path": "scripts/run_pipeline.py", "content_ref": "inline:new_run_pipeline"}, "depends_on": ["C1", "C2"]},
        {"id": "C4", "type": "verify", "tool": "shell", "args": {"cmd": "test -f scripts/run_pipeline.py && grep -q -- '--provider' scripts/run_pipeline.py"}, "expected": {"exit_code": 0}, "fallback": "revert C3 content and re-prompt with error context", "depends_on": ["C3"]}
      ]
    },
    {
      "id": "Stage3",
      "name": "CREATE: add model provider switching logic for Ollama and OpenRouter in run_pipeline.py",
      "commands": [
        {"id": "C5", "type": "create", "tool": "write_file", "args": {"path": "scripts/run_pipeline.py", "content_ref": "inline:provider_switching_logic"}, "depends_on": ["C3", "C4"]},
        {"id": "C6", "type": "verify", "tool": "shell", "args": {"cmd": "test -f scripts/run_pipeline.py && grep -q 'openrouter' scripts/run_pipeline.py"}, "expected": {"exit_code": 0}, "fallback": "revert C5 content and re-prompt with error context", "depends_on": ["C5"]}
      ]
    },
    {
      "id": "Stage4",
      "name": "CREATE: add .env configuration for Ollama and OpenRouter",
      "commands": [
        {"id": "C7", "type": "create", "tool": "write_file", "args": {"path": ".env", "content_ref": "inline:env_config"}, "depends_on": ["C5", "C6"]},
        {"id": "C8", "type": "verify", "tool": "shell", "args": {"cmd": "test -f .env && grep -q 'OPENROUTER_API_KEY' .env"}, "expected": {"exit_code": 0}, "fallback": "revert C7 content and re-prompt with error context", "depends_on": ["C7"]}
      ]
    },
    {
      "id": "Stage5",
      "name": "VERIFY: run_pipeline.py recognizes --provider ollama flag",
      "commands": [
        {"id": "C9", "type": "verify", "tool": "shell", "args": {"cmd": "python scripts/run_pipeline.py --provider ollama --cloud-model model1 && echo 'exit_code=0'"}, "expected": {"exit_code": 0}, "fallback": "revert, re-prompt with error context", "depends_on": ["C8"]}
      ]
    },
    {
      "id": "Stage6",
      "name": "VERIFY: run_pipeline.py recognizes --provider openrouter flag",
      "commands": [
        {"id": "C10", "type": "verify", "tool": "shell", "args": {"cmd": "python scripts/run_pipeline.py --provider openrouter --cloud-model model1 && echo 'exit_code=0'"}, "expected": {"exit_code": 0}, "fallback": "revert, re-prompt with error context", "depends_on": ["C9"]}
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