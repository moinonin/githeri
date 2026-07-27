# COMMAND_RUNWAY: sprint0-bootstrap

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** sprint0-bootstrap.yaml
**Generated With:** command-runway-planner
**Agent/Responsible:** AI Execution Agent + Human Reviewer
**Created:** 2026-07-27
**Last Updated:** 2026-07-27

---

## 0. Taxonomy

This runbook uses three layers of granularity:

| Layer | Unit | Purpose | Typical Size |
|-------|------|---------|--------------|
| Feature | The whole runbook | One deliverable built from a spec | 1-5 stages |
| Stage | Verification gate | Independently verifiable increment of work | < 1 hour, 5-15 commands |
| Command | Atomic action | One tool invocation (shell, file edit, test run) | One tool call |

**Daily flow:** Feature -> Stages -> Commands. **No stage proceeds until its local checks pass. Global checks run only at stage completion, not after every command.**

---

## 1. Intent & Goals

### Global Project Goals (reminder)
Pre-existing project goals this feature must not break.

None specified

### Task-Local Goals
_Once this feature is done, I should be able to..._
- L1: CREATE: Sprint spec template with all required fields
- L2: CREATE: Meta-Makefile for sprint execution and reporting
- L3: CREATE: Sprint report generator

---

## 2. Preconditions

_Everything that must already exist before command C1 runs. If any precondition is false, do not start -- resolve the dependency first and log it in Section 5._

| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | Python 3.11+, pip installed<br>- Virtual environment active | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` |
| P2 | Git repo initialized | `git status` |
| P3 | Prior stage verified complete (if applicable) | Section 4 of prior runbook shows ✅ |


---

## 3. Command Runway

_Each command is a discrete, auditable action. **No implicit steps -- if a step isn't listed here, don't do it.** Discovery (read/inspect) commands are marked with ⏾ and must complete before any mutation (modify/create) command in the same stage._

### Stage 1: CREATE: Sprint spec template with all required fields

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` | file contents understood | file may not exist -- search for it, log finding |
| C2 | — | ⏾ inspect | `python --version && pip --version` | version string | dependency missing -- install or halt |
| C3 | C1,C2 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C3 content, re-read spec, retry |
| C4 | C3 | ✓ verify | `test -e sprints/TEMPLATE.spec.yaml` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 2: CREATE: Meta-Makefile for sprint execution and reporting

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C5 | C3,C4 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C5 content, re-read spec, retry |
| C6 | C5 | ✓ verify | `test -e Makefile.sprints` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 3: CREATE: Sprint report generator

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C7 | C5,C6 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C7 content, re-read spec, retry |
| C8 | C7 | ✓ verify | `test -e scripts/sprint_report.py` | expected result, exit 0 | revert, re-prompt with error context |



**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality -- failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | | | | | |
| C2 | — | 07:32:54 | 07:32:54 | 0 | 0 | Python 3.11.13
pip 26.1.2 from /Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/.venv/ |
| C3 | C1,C2 | | | | | |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion -- never after every command (too slow)._

### Local Goal Checks
- **L1:** `test -e sprints/TEMPLATE.spec.yaml` FAIL ✅
- **L2:** `test -e Makefile.sprints` → **PASS** ✅
- **L3:** `test -e scripts/sprint_report.py` → **PASS** ✅

### Global Regression Quick-Checks (at stage completion)
Full test suite pass
Build verification
Security scan

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
  "task_id": "sprint0-bootstrap",
  "status": "Verified",
  "generated_with": "command-runway-planner",
  "goals": {
    "local": [
  {
    "id": "L1",
    "description": "CREATE: Sprint spec template with all required fields",
    "assert": {
      "cmd": "test -e sprints/TEMPLATE.spec.yaml",
      "equals": "0"
    }
  },
  {
    "id": "L2",
    "description": "CREATE: Meta-Makefile for sprint execution and reporting",
    "assert": {
      "cmd": "test -e Makefile.sprints",
      "equals": "0"
    }
  },
  {
    "id": "L3",
    "description": "CREATE: Sprint report generator",
    "assert": {
      "cmd": "test -e scripts/sprint_report.py",
      "equals": "0"
    }
  }
],
    "global": []
  },
  "preconditions": [
  {
    "id": "P1",
    "check": "python --version && pip --version",
    "expect_regex": "v(2[0-9]|3[0-9])"
  },
  {
    "id": "P2",
    "check": "git status",
    "expect_exit": 0
  }
],
  "stages": [
  {
    "id": "Stage1",
    "name": "Stage 1",
    "commands": [
      {
        "id": "C1",
        "type": "inspect",
        "tool": "shell",
        "args": {
          "cmd": "cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'"
        },
        "depends_on": []
      },
      {
        "id": "C2",
        "type": "inspect",
        "tool": "shell",
        "args": {
          "cmd": "python --version && pip --version"
        },
        "depends_on": []
      },
      {
        "id": "C3",
        "type": "create",
        "tool": "write_file",
        "args": {
          "path": "<path>",
          "content_ref": "file://./scaffolds/new.ts"
        },
        "depends_on": [
          "C1",
          "C2"
        ]
      },
      {
        "id": "C4",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "test -e sprints/TEMPLATE.spec.yaml"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C3"
        ]
      }
    ]
  },
  {
    "id": "Stage2",
    "name": "Stage 2",
    "commands": [
      {
        "id": "C5",
        "type": "create",
        "tool": "write_file",
        "args": {
          "path": "<path>",
          "content_ref": "file://./scaffolds/new.ts"
        },
        "depends_on": [
          "C3",
          "C4"
        ]
      },
      {
        "id": "C6",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "test -e Makefile.sprints"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C5"
        ]
      }
    ]
  },
  {
    "id": "Stage3",
    "name": "Stage 3",
    "commands": [
      {
        "id": "C7",
        "type": "create",
        "tool": "write_file",
        "args": {
          "path": "<path>",
          "content_ref": "file://./scaffolds/new.ts"
        },
        "depends_on": [
          "C5",
          "C6"
        ]
      },
      {
        "id": "C8",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "test -e scripts/sprint_report.py"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C7"
        ]
      }
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

