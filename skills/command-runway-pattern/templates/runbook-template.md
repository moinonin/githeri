# COMMAND_RUNWAY: <Feature Name>

**Status:** [ Draft Plan | In-Flight | Verified | Blocked ]
**Derived From Spec:** `<path/to/spec.md>` (<Feature # or Task #>)
**Generated With:** `.runbookprompt.md` (plan generation prompt)
**Agent/Responsible:** <agent identity> + Human Reviewer
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

---

## 0. Taxonomy

Three layers of granularity:

| Layer | Unit | Purpose | Typical Size |
|-------|------|---------|---------------|
| Feature | The whole runbook | One deliverable from a spec | 1–5 stages |
| Stage | Verification gate | Independently verifiable increment | < 1 hour; 5–15 commands |
| Command | Atomic action | One tool invocation | One tool call |

**No stage proceeds until its local checks pass. Global checks run only at stage completion.**

---

## 1. Intent & Goals

### Global Project Goals (must not break)
- G1: <global capability>
- G2: <global capability>

### Task-Local Goals
_Once this feature is done, I should be able to…_
- L1: <observable outcome>
- L2: <observable outcome>
- L3: <observable outcome>

---

## 2. Preconditions

_Must be true before command C1 runs. If any is false, resolve the dependency first and log it in Section 6._

| # | Precondition | Verified How |
|---|--------------|--------------|
| P1 | <tool/dep> installed | `<tool> --version` |
| P2 | <file/dir> exists | `test -f <path>` |
| P3 | Prior stage `<id>` verified | that runbook's Section 5 shows ✅ |
| P4 | <env var> set | `echo $<VAR>` non-empty |

### Python Virtual Environment (CRITICAL — when Python is used)

**All Python backend commands MUST use `.venv` — NEVER bare `python`, `python3`, or `pip`.**

| # | Precondition | Verified How |
|---|--------------|--------------|
| P5 | `.venv` exists and is functional | `test -d .venv && .venv/bin/python --version` |

**If P5 is false**, the FIRST command in Stage A MUST create it:
```
python3 -m venv .venv   # or: python3.11 -m venv .venv if a specific version is required
```

All subsequent Python commands MUST use `.venv/bin/python` or `.venv/bin/pip`.
Activation (`. .venv/bin/activate`) MUST happen in the same shell invocation that runs Python — do NOT assume activation persists across commands.

---

## 3. Command Runway

_Each command is a discrete, auditable action. ⏾ commands (inspect) must complete before ✎ commands (mutate) in the same stage. ✓ commands (verify) run after ✎ — in the same stage or at stage end._

### Stage A: <Stage Name>

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C1 | — | ⏾ | `read_file <path>` | file contents understood | search for file, log finding |
| C2 | — | ⏾ | `<tool> --version` | version string | dep missing — install or halt |
| C3 | C1,C2 | ✎ | `write_file <path>` with <content_ref> | new file on disk | revert, re-read spec, retry |
| C4 | C3 | ✎ | `patch <path>` <old> → <new> | file patched | re-read file fresh, retry |
| C5 | C4 | ✓ | `<build cmd> && <test cmd>` | exit 0, tests pass | see Failure Procedure |
| C6 | C5 | ✓ | `curl <endpoint>` | expected HTTP status + body | check logs, revisit C4 |

**Legend:** ⏾ = inspect (read-only), ✎ = modify/create, ✓ = verify

### Stage B: <Stage Name>

| Cmd# | Deps | Type | Command / Tool Invocation | Expected Artifact / Δ | Fallback if Fail |
|------|------|------|---------------------------|------------------------|------------------|
| C7 | C5 | ⏾ | … | … | … |
| … | … | … | … | … | … |

---

## 4. Execution Log

_Filled in during execution. Capture reality — failures and retries are logged, not hidden._

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary / Artifact Hash |
|------|------|-------|-----|------|--------|-------------------------------|
| C1 | — | 10:23:01 | 10:23:02 | 0 | 0 | read 248 lines |
| C2 | — | 10:23:03 | 10:23:03 | 0 | 0 | <tool> 9.0.0 |
| C3 | C1,C2 | 10:23:10 | 10:23:15 | 0 | 0 | wrote 42 lines, sha:3f2a |
| C4 | C3 | 10:23:20 | 10:23:25 | 1 | 0 | FAIL: patch target not found — halted |
| C4 | C3 | 10:23:30 | 10:23:32 | 0 | 1 | patched +12/-4, sha:b7e1 |
| C5 | C4 | 10:23:35 | 10:23:48 | 0 | 0 | 5 tests passing |
| C6 | C5 | 10:23:50 | 10:23:52 | 0 | 0 | 201 + {"id":"uuid"} |

---

## 5. Goal Verification

_Local checks run after stage commands complete. Global checks run at stage completion only._

### Local Goal Checks
- **L1:** `curl -X POST <endpoint> -d '<body>'` → **201 + {id: "uuid"}** ✅
- **L2:** repeat L1 with duplicate email → **409 {error: "EMAIL_EXISTS"}** ✅
- **L3:** <other observable outcome> ✅

### Global Regression Quick-Checks (at stage completion)
- **G2:** <global capability> — `<verify cmd>` ✅

---

## 6. Iteration & Notes

- **Deviations from runway:** <none / description>
- **Blockers:** <none / description>
- **Commands that needed rework:** C4 (patch target stale; re-read file before retry)
- **Lessons learned:** <method-level insight for the next runbook>
- **Next runways:** COMMAND_RUNWAY: <linked feature>

---

## 7. Machine-Readable Extension (JSON)

_Optional. For orchestration harnesses. `depends_on` defines the DAG; `expected` is a structured assertion._

```json
{
  "task_id": "<feature-id>",
  "status": "Verified",
  "generated_with": ".runbookprompt.md",
  "goals": {
    "local": [
      {
        "id": "L1",
        "description": "<outcome>",
        "assert": {
          "cmd": "<verify command>",
          "exit_code": 0,
          "stdout_regex": "<pattern>"
        }
      }
    ],
    "global": ["G2"]
  },
  "preconditions": [
    {"id": "P1", "check": "<tool> --version", "expect_regex": "<pattern>"},
    {"id": "P2", "check": "test -f <path>", "expect_exit": 0}
  ],
  "stages": [
    {
      "id": "StageA",
      "name": "<stage name>",
      "commands": [
        {
          "id": "C1",
          "type": "inspect",
          "tool": "read_file",
          "args": {"path": "<file>"},
          "depends_on": []
        },
        {
          "id": "C3",
          "type": "create",
          "tool": "write_file",
          "args": {"path": "<file>", "content_ref": "file://./scaffolds/<file>"},
          "depends_on": ["C1", "C2"]
        },
        {
          "id": "C5",
          "type": "modify",
          "tool": "patch",
          "args": {"path": "<file>", "old": "...", "new": "..."},
          "depends_on": ["C3", "C4"]
        },
        {
          "id": "C6",
          "type": "verify",
          "tool": "shell",
          "args": {"cmd": "<build> && <test>"},
          "expected": {"exit_code": 0},
          "fallback": "<corrective action>",
          "depends_on": ["C5"]
        }
      ],
      "completion_condition": "C6 exits 0 AND L1 assertion passes"
    }
  ]
}
```

**`expected` assertion shapes** (use one or more):
- `exit_code: N`
- `stdout_regex: "pattern"`
- `stdout_contains: "substring"`
- `http_status: N`
- `body_regex: "pattern"`
- `file_exists: "path"`

**`content_ref` resolution:**
- `file://<relative/path>` — load from local file
- `hash://<sha256>` — content integrity-verified (reproducible builds)
- `inline:` — content embedded (escape newlines)

---

## Execution Rules (Mandatory)

1. ⏾ commands complete before ✎ in the same stage
2. No stage closes until its ✓ commands pass
3. On ✓ failure: stop, diagnose (Section 6), retry — don't advance
4. Every command is atomic: one tool invocation
5. No implicit steps — if it's not in the table, it doesn't happen
6. Failures are logged with Retry# — never hidden
7. Local checks per command; global checks per stage (not per command)
8. Never weaken an assertion to pass — fix the implementation or the test, not the gate
9. Update Last Updated timestamp on every edit or log entry
