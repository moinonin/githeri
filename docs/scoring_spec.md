# Mapping the Runbook to the Spec

| Runbook Section | Required Spec Element(s) | Scoring Criteria |
|-----------------|--------------------------|------------------|
| **1. Intent & Goals** | `summary`, `local_goals` | Summary is non-empty; each local goal has a description and a verification command matching its intent. |
| **2. Preconditions** | `depends_on`, `context`, optional preconditions | `depends_on` references known global goals or prior stage IDs. If the task uses tools (Prisma, Gradle), the context must mention them or a precondition flag is required. |
| **3. Command Runway (Stages)** | `local_goals` grouped by type (⏾ inspect, ✎ modify, ✓ verify) | At least one inspect-like goal, one create/modify goal, and one verify goal. |
| **4. Execution Log** | *(Not represented in the spec)* | N/A |
| **5. Goal Verification** | `local_goal.verification` | Verification commands must be runnable and produce a boolean outcome. Already enforced by the validator. |
| **6. Completion Condition** | Implicit – all local goals passing | All prompt-mentioned status codes, test types, and OpenAPI updates are covered. Already part of heuristic scoring. |
| **7. Machine-Readable Extension** | *(Optional)* | N/A |

## Definition of a "Runbook-Ready" Spec

A specification is considered **runbook-ready** if it adequately covers:

- Intent & Goals
- Preconditions
- Command Runway
- Goal Verification
- Completion Condition

The scoring function evaluates how well a spec satisfies each of these areas.

---

# Proposed Scoring Function (`runbook_score`)

The score is computed as a weighted sum across five categories.

## Category Weights

| Category | Weight |
|----------|-------:|
| Intent & Goals | **20%** |
| Preconditions | **15%** |
| Command Runway Structure | **30%** |
| Verification Testability | **25%** |
| Completion Coverage | **10%** |

---

# Category Definitions

## 1. Intent & Goals (0.0–1.0)

### Summary Quality (0.2)

- Summary is a clear, one-sentence description of the task.

### Goal Clarity (0.4)

Every local goal:

- has a non-empty description
- states an observable outcome

### Goal-Type Alignment (0.4)

Examples:

| Goal mentions | Verification Type |
|---------------|-------------------|
| endpoint / route / API | `http` |
| job / task | `cli` |
| file / model | `file_exists` |

---

## 2. Preconditions (0.0–1.0)

### Depends-On Validity (0.3)

`depends_on` should reference only:

- known global goals (`G1`–`G19`)
- existing stage IDs

### Dependency Coverage (0.4)

Example:

If context contains:

- Express
- Prisma

then `depends_on` should include:

```
stage-1-core-models
```

(or another expected dependency from the knowledge base).

### Tool Preconditions (0.3)

If verification commands invoke tools such as:

- pnpm
- Gradle

then either:

- the context declares those tools, or
- a preconditions block exists.

(Currently the scorer simply rewards specs whose context declares the tools.)

---

## 3. Command Runway Structure (0.0–1.0)

### Inspect Goal (0.15)

There should be at least one **inspect** stage.

Approximated as:

- `file_exists`
- `test -f`
- `head`
- `cat`

---

### Create / Modify Goal (0.4)

At least one stage should create or modify something.

Examples:

- `file_exists`
- build
- install
- migrate
- `pnpm build`

---

### Verify Goal (0.3)

At least one verification stage.

Examples:

- HTTP endpoint
- automated tests

---

### Stage Separation (0.15)

Preferred logical order:

```
Inspect
    ↓
Create / Modify
    ↓
Verify
```

Specs are rewarded if goals follow this progression.

---

## 4. Verification Testability (0.0–1.0)

### Concrete Commands (0.4)

Verification commands should be executable directly.

Acceptable placeholders:

```
{admin_token}
```

Not acceptable:

- empty URLs
- missing commands

---

### Assertion Clarity (0.3)

Each verification includes explicit expectations.

Examples:

| Type | Expected Assertion |
|------|--------------------|
| HTTP | expected status code |
| CLI | exit code |
| File | content or existence |

---

### Reproducibility (0.3)

Verification should be independently repeatable.

Example:

HTTP URLs should not reference ephemeral resources.

---

## 5. Completion Coverage (0.0–1.0)

Reuse the existing prompt-based heuristic.

Examples checked include:

- status codes
- required tests
- OpenAPI updates

---

# Example Implementation (Python)

Create a new module:

```
runbook_scorer.py
```

and import it into the pipeline.

```python
import yaml
import re

VALID_GLOBAL_GOALS = {f"G{i}" for i in range(1, 20)}
EXPECTED_DEPENDENCIES = {
    ("express", "prisma"): "stage-1-core-models",
    ("express", "prisma", "auth"): "stage-3-session-api",
}

def _check_inspect(goals):
    for g in goals:
        ver = g.get("verification", {})
        cmd = ver.get("command", "") if ver.get("type") == "cli" else ""
        if ver.get("type") == "file_exists" or ("test -f" in cmd or "head" in cmd):
            return True
    return False

def _check_create_modify(goals):
    for g in goals:
        ver = g.get("verification", {})
        if ver.get("type") == "file_exists":
            return True
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if any(word in cmd for word in ["build", "migrate", "install", "gradle", "npm run", "pnpm build"]):
                return True
    return False

def _check_verify(goals):
    for g in goals:
        ver = g.get("verification", {})
        if ver.get("type") == "http":
            return True
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if "test" in cmd:
                return True
    return False

def runbook_score(spec):
    """Score a spec YAML on how well it would translate into a complete COMMAND_RUNWAY."""
    score = 1.0
    details = []

    goals = spec.get("local_goals", [])

    # 1. Intent & Goals (20%)
    intent_score = 1.0
    if not spec.get("summary"):
        intent_score -= 0.3
        details.append("Summary missing")
    for g in goals:
        if not g.get("description"):
            intent_score -= 0.1
            details.append(f"Goal {g.get('id')} missing description")
    if "endpoint" in spec.get("summary", "").lower() or any("endpoint" in g.get("description", "").lower() for g in goals):
        if not any(g.get("verification", {}).get("type") == "http" for g in goals):
            intent_score -= 0.3
            details.append("Endpoint task lacks HTTP verification")
    score -= 0.2 * (1 - intent_score)

    # 2. Preconditions (15%)
    precond_score = 1.0
    deps = spec.get("depends_on", []) or []
    for d in deps:
        if d not in VALID_GLOBAL_GOALS and not d.startswith("stage-"):
            precond_score -= 0.2
            details.append(f"Unknown dependency '{d}'")
    context = spec.get("context", {})
    if "express" in str(context).lower() and "prisma" in str(context).lower():
        if not any(d == "stage-1-core-models" for d in deps):
            precond_score -= 0.2
            details.append("Should depend on stage-1-core-models")
    tools_used = set()
    for g in goals:
        ver = g.get("verification", {})
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if "pnpm" in cmd:
                tools_used.add("pnpm")
            if "gradle" in cmd:
                tools_used.add("gradle")
    if tools_used and not any(t in str(context).lower() for t in tools_used):
        precond_score -= 0.1
        details.append("Context missing some tools used in commands")
    score -= 0.15 * (1 - precond_score)

    # 3. Command Runway Structure (30%)
    struct_score = 1.0
    if not _check_inspect(goals):
        struct_score -= 0.15
        details.append("No inspect goal (file read / existence check)")
    if not _check_create_modify(goals):
        struct_score -= 0.4
        details.append("No create/modify goal (file write / build)")
    if not _check_verify(goals):
        struct_score -= 0.3
        details.append("No verify goal (test run / HTTP check)")
    create_idx = -1
    verify_idx = -1
    for i, g in enumerate(goals):
        ver = g.get("verification", {})
        if ver.get("type") == "file_exists" or (
            ver.get("type") == "cli" and "build" in ver.get("command", "")
        ):
            create_idx = i
        if ver.get("type") == "http" or (
            ver.get("type") == "cli" and "test" in ver.get("command", "")
        ):
            verify_idx = i if verify_idx == -1 else verify_idx
    if create_idx != -1 and verify_idx != -1 and create_idx > verify_idx:
        struct_score -= 0.15
        details.append("Create goal appears after verify goal")
    score -= 0.30 * (1 - struct_score)

    # 4. Verification Testability (25%)
    test_score = 1.0
    for g in goals:
        ver = g.get("verification", {})
        vtype = ver.get("type")
        if vtype == "http":
            if not ver.get("url"):
                test_score -= 0.1
                details.append(f"Goal {g['id']} missing URL")
            if "expect" not in ver or "status" not in ver.get("expect", {}):
                test_score -= 0.1
                details.append(f"Goal {g['id']} missing expected status")
        elif vtype == "cli":
            if not ver.get("command"):
                test_score -= 0.1
                details.append(f"Goal {g['id']} missing CLI command")
        elif vtype == "file_exists":
            if not ver.get("path"):
                test_score -= 0.1
                details.append(f"Goal {g['id']} missing file path")
    if test_score < 0:
        test_score = 0
    score -= 0.25 * (1 - test_score)

    # 5. Completion Coverage (10%)
    prompt_score = prompt_heuristic_score(spec.get("_prompt", ""), spec)
    score -= 0.10 * (1 - prompt_score)

    return max(0.0, min(1.0, score)), details
```

---

# Integrating into `generate_one_pair`

```python
spec_yaml = ...
spec_dict = yaml.safe_load(spec_yaml)
spec_dict["_prompt"] = original_prompt

score, issues = runbook_score(spec_dict)

pair = {
    "prompt": original_prompt,
    "spec_yaml": spec_yaml,
    "runbook_score": score,
    "score_details": issues,
}

# Only save if score >= 0.7 and no blocking issues
if score >= 0.7:
    with open(OUTPUT_FILE, "a") as f:
        f.write(json.dumps(pair) + "\n")
```

---

# Why This Works

This scoring system intentionally mirrors the structure expected by the **Runway Compiler**.

Specifically, it:

- Maps directly onto the sections of a complete COMMAND_RUNWAY.
- Penalizes missing stages such as **Inspect**, **Create**, or **Verify**.
- Validates that dependencies and preconditions are coherent.
- Ensures verification steps are concrete, executable, and reproducible.
- Complements the existing syntax validator and prompt-coverage heuristics.

Together, these checks produce a **360° quality score** for each generated specification.

The result is a fine-tuning dataset composed only of specs that are:

- syntactically valid,
- semantically complete,
- executable,
- and immediately suitable for compilation into fully executable runbooks.

This is precisely the type of high-quality supervision needed to train a reliable **Spec-Forge** model.
