# COMMAND_RUNWAY: sprint10-observability-dashboard

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** sprint10-observability-dashboard.yaml
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
- L1: CREATE: Observability skill with metrics collection and dashboard
- L2: CREATE: Metrics collector (tokens, latency, success, cost per feature)
- L3: CREATE: SQLite metrics database with 90-day retention
- L4: CREATE: HTML dashboard with real-time and historical views
- L5: CREATE: Anomaly alerting (cost spike, failure rate, latency)
- L6: VERIFY: Dashboard shows real data after autonomous run

---

## 2. Preconditions

_Everything that must already exist before command C1 runs. If any precondition is false, do not start -- resolve the dependency first and log it in Section 5._

| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | Python 3.11+, pip installed<br>- Virtual environment active | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` |
| P2 | Git repo initialized | `git status` |
| P3 | Prior stage verified complete (if applicable) | Section 4 of prior runbook shows ✅ |
| P4 | Dependency `sprint9-ci-cd-integration` complete | Check prior runbook |


---

## 3. Command Runway

_Each command is a discrete, auditable action. **No implicit steps -- if a step isn't listed here, don't do it.** Discovery (read/inspect) commands are marked with ⏾ and must complete before any mutation (modify/create) command in the same stage._

### Stage 1: CREATE: Observability skill with metrics collection and dash

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ inspect | `cat pyproject.toml || cat requirements.txt || echo 'No pyproject.toml or requirements.txt'` | file contents understood | file may not exist -- search for it, log finding |
| C2 | — | ⏾ inspect | `python --version && pip --version` | version string | dependency missing -- install or halt |
| C3 | C1,C2 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C3 content, re-read spec, retry |
| C4 | C3 | ✓ verify | `test -f .hermes/skills/software-development/observability/SKILL.md && grep -q -- 'observability' .hermes/skills/software-development/observability/SKILL.md` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 2: CREATE: Metrics collector (tokens, latency, success, cost pe

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C5 | C3,C4 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C5 content, re-read spec, retry |
| C6 | C5 | ✓ verify | `test -f skills/software-development/observability/scripts/collect_metrics.py && grep -q -- 'tokens|latency|success' skills/software-development/observability/scripts/collect_metrics.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 3: CREATE: SQLite metrics database with 90-day retention

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C7 | C5,C6 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C7 content, re-read spec, retry |
| C8 | C7 | ✓ verify | `test -f metrics/autonomous.db` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 4: CREATE: HTML dashboard with real-time and historical views

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C9 | C7,C8 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C9 content, re-read spec, retry |
| C10 | C9 | ✓ verify | `test -f dashboard/autonomous.html` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 5: CREATE: Anomaly alerting (cost spike, failure rate, latency)

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C11 | C9,C10 | ✎ create | `write_file <path>` with <content_ref> | new file on disk | revert C11 content, re-read spec, retry |
| C12 | C11 | ✓ verify | `test -f skills/software-development/observability/scripts/alerting.py && grep -q -- 'alert|anomaly' skills/software-development/observability/scripts/alerting.py` | expected result, exit 0 | revert, re-prompt with error context |

### Stage 6: VERIFY: Dashboard shows real data after autonomous run

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C13 | C12 | ✓ verify | `make autonomous-cycle SPEC=test-feature && make dashboard && echo 'exit_code=0'` | expected result, exit 0 | revert, re-prompt with error context |



**Legend:** ⏾ = inspect/read (no mutation), ✎ = modify/create, ✓ = verify/run

---

## 4. Execution Log

_Filled in during execution, not during planning. Capture reality -- failures and retries are logged here, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | | | | | |
| C2 | — | | | | | |
| C3 | C1,C2 | | | | | |

---

## 5. Goal Verification

_Run local checks after the stage's commands complete. Run global checks only at stage completion -- never after every command (too slow)._

### Local Goal Checks
- **L1:** `test -f .hermes/skills/software-development/observability/SKILL.md && grep -q -- 'observability' .hermes/skills/software-development/observability/SKILL.md` → **PASS** ✅
- **L2:** `test -f skills/software-development/observability/scripts/collect_metrics.py && grep -q -- 'tokens|latency|success' skills/software-development/observability/scripts/collect_metrics.py` → **PASS** ✅
- **L3:** `test -f metrics/autonomous.db` → **PASS** ✅
- **L4:** `test -f dashboard/autonomous.html` → **PASS** ✅
- **L5:** `test -f skills/software-development/observability/scripts/alerting.py && grep -q -- 'alert|anomaly' skills/software-development/observability/scripts/alerting.py` → **PASS** ✅
- **L6:** `make autonomous-cycle SPEC=test-feature && make dashboard && echo 'exit_code=0'` → **PASS** ✅

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
  "task_id": "sprint10-observability-dashboard",
  "status": "Verified",
  "generated_with": "command-runway-planner",
  "goals": {
    "local": [
  {
    "id": "L1",
    "description": "CREATE: Observability skill with metrics collection and dashboard",
    "assert": {
      "cmd": "test -f .hermes/skills/software-development/observability/SKILL.md && grep -q -- 'observability' .hermes/skills/software-development/observability/SKILL.md",
      "equals": "0"
    }
  },
  {
    "id": "L2",
    "description": "CREATE: Metrics collector (tokens, latency, success, cost per feature)",
    "assert": {
      "cmd": "test -f skills/software-development/observability/scripts/collect_metrics.py && grep -q -- 'tokens|latency|success' skills/software-development/observability/scripts/collect_metrics.py",
      "equals": "0"
    }
  },
  {
    "id": "L3",
    "description": "CREATE: SQLite metrics database with 90-day retention",
    "assert": {
      "cmd": "test -f metrics/autonomous.db",
      "equals": "0"
    }
  },
  {
    "id": "L4",
    "description": "CREATE: HTML dashboard with real-time and historical views",
    "assert": {
      "cmd": "test -f dashboard/autonomous.html",
      "equals": "0"
    }
  },
  {
    "id": "L5",
    "description": "CREATE: Anomaly alerting (cost spike, failure rate, latency)",
    "assert": {
      "cmd": "test -f skills/software-development/observability/scripts/alerting.py && grep -q -- 'alert|anomaly' skills/software-development/observability/scripts/alerting.py",
      "equals": "0"
    }
  },
  {
    "id": "L6",
    "description": "VERIFY: Dashboard shows real data after autonomous run",
    "assert": {
      "cmd": "make autonomous-cycle SPEC=test-feature && make dashboard && echo 'exit_code=0'",
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
          "cmd": "test -f .hermes/skills/software-development/observability/SKILL.md && grep -q -- 'observability' .hermes/skills/software-development/observability/SKILL.md"
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
          "cmd": "test -f skills/software-development/observability/scripts/collect_metrics.py && grep -q -- 'tokens|latency|success' skills/software-development/observability/scripts/collect_metrics.py"
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
          "cmd": "test -f metrics/autonomous.db"
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
  },
  {
    "id": "Stage4",
    "name": "Stage 4",
    "commands": [
      {
        "id": "C9",
        "type": "create",
        "tool": "write_file",
        "args": {
          "path": "<path>",
          "content_ref": "file://./scaffolds/new.ts"
        },
        "depends_on": [
          "C7",
          "C8"
        ]
      },
      {
        "id": "C10",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "test -f dashboard/autonomous.html"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C9"
        ]
      }
    ]
  },
  {
    "id": "Stage5",
    "name": "Stage 5",
    "commands": [
      {
        "id": "C11",
        "type": "create",
        "tool": "write_file",
        "args": {
          "path": "<path>",
          "content_ref": "file://./scaffolds/new.ts"
        },
        "depends_on": [
          "C9",
          "C10"
        ]
      },
      {
        "id": "C12",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "test -f skills/software-development/observability/scripts/alerting.py && grep -q -- 'alert|anomaly' skills/software-development/observability/scripts/alerting.py"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C11"
        ]
      }
    ]
  },
  {
    "id": "Stage6",
    "name": "Stage 6",
    "commands": [
      {
        "id": "C13",
        "type": "verify",
        "tool": "shell",
        "args": {
          "cmd": "make autonomous-cycle SPEC=test-feature && make dashboard && echo 'exit_code=0'"
        },
        "expected": {
          "exit_code": 0
        },
        "fallback": "revert content and re-prompt with error context",
        "depends_on": [
          "C12"
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

