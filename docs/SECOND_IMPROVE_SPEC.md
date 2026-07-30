# Enriched Spec Pipeline – Generic Gap Analysis & Improvements

After examining 8 fully generated specs (all validated with the existing validator), clear patterns emerge. The enriched fields (`blueprint`, `business_rules`, etc.) are a huge step forward, but they are not yet applied **consistently** across all prompts. The following analysis identifies the truly generic gaps and provides ready-to-use code modifications that will make **every** future spec fully autonomous-ready.

---

## 1. Spec-by-Spec Comparison

| # | Spec ID | Blueprint (CREATE) | Acceptance Criteria | Business Rules | Test Fixtures | Teardown Commands | Environment | Global Verification | Placeholder Secrets | Missing Imports | External Script Deps (not created) | Verification Runs Actual Tests |
|---|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | `list-sessions-endpoint` | ✅ | ✅ (L2) | ❌ | ❌ | ❌ | ❌ | ❌ | — | ✅ (all present) | — | ❌ (only file_exists) |
| 2 | `submit-evidence-endpoint` | ✅ | ✅ (L2,L3,L4) | ✅ | ✅ | ❌ | ✅ | ✅ | — | ❌ (L2 missing Field, datetime) | `seed_evidence_types.py` | ❌ (file_exists for test file, global runs tests) |
| 3 | `revoke-proof-endpoint` | ✅ | ✅ (L2) | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ (no imports in blueprint) | — | ❌ (only file_exists) |
| 4 | `cleanup-expired-sessions` | ✅ | ✅ (L2,L3) | ✅ | ✅ | ❌ | ✅ | ✅ | — | ✅ (L2 has imports) | `seed_sessions.py` | ✅ (L4 runs unit test) |
| 5 | `get-proof-of-attention` | ✅ | ✅ (L2,L3,L4) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ (`{{JWT_SECRET}}`, `***`) | ❌ (L2 missing datetime import) | `seed_proof_of_attention.py`, `generate_openapi.py` | ❌ (L3 external script, L4 test file must exist) |
| 6 | `update-verification-policy` | ✅ | ✅ (L2,L3,L4,L5) | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ (no imports in L2 blueprint) | — | ✅ (http + openapi-generator) |
| 7 | `batch-observation-upload` | ✅ | ❌ (none) | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ (L3 missing imports) | — | ❌ (only file_exists) |
| 8 | `scheduled-confidence-recalc` | ✅ | ❌ (none) | ❌ | ❌ | ❌ | ❌ | ❌ | — | ✅ (L2 has import) | — | ✅ (L4,L5 run pytest) |

**Key observations:**
- ✅ **Every spec now contains blueprints** – the prompt update worked.
- ❌ **Acceptance criteria are missing in 2/8 specs** – and even when present, they aren't always used for verification.
- ❌ **Business rules, test fixtures, environment, and global verification appear in only 3-4 specs** – the model adds them only when the prompt explicitly mentions those aspects.
- ❌ **No spec includes teardown commands** – a universal cleanup gap.
- ❌ **Placeholder secrets (`{{JWT_SECRET}}`) appear in one spec** – the model still uses template syntax.
- ❌ **Blueprints often lack imports** (5/8 specs) – code can't run as-is.
- ❌ **Verification is largely superficial** – most goals only check file existence and string content, not runtime correctness.

---

## 2. Truly Generic Gaps (Will Affect Every Future Spec)

| # | Generic Gap | Why It Happens | Impact |
|---|-------------|----------------|--------|
| 1 | **Missing teardown** | LLM thinks only about setup, never cleanup. | Repeated test runs pollute the DB; agent can't reset state. |
| 2 | **Missing acceptance criteria** | LLM considers `verification` enough. | Executor cannot generate concrete test commands. |
| 3 | **Missing `business_rules`, `test_fixtures`, `environment`, `global_verification`** | Sections are optional in the prompt; model omits them. | Executor has no shared logic, no test data, no environment setup, no final quality gates. |
| 4 | **Placeholder secrets** | LLM uses `{{...}}` from template habits. | Agent tries to use literal `{{JWT_SECRET}}` as key – auth fails. |
| 5 | **Missing imports in blueprints** | LLM writes the meat of the code, but skips the header. | Generated files fail on import. |
| 6 | **External scripts referenced but not created** | Model assumes `scripts/...` exist. | Verification commands fail with "file not found". |
| 7 | **Superficial verification** | `file_exists` + `content_contains` are easiest to generate. | Code may pass checks even if logic is completely broken. |

All these gaps can be eliminated by **two changes**:
1. Adding explicit rules to the `SYSTEM_PROMPT_TEMPLATE`.
2. Adding corresponding validation checks in `validate_spec()`.

Because the fixes are structural, they will apply **uniformly to any future prompt**, regardless of feature or language.

---

## 3. Classification: Doable vs Design Decisions vs Skip

### ✅ DOABLE — High Value, Low Risk (Low-Hanging Fruit)

These are structural validations + prompt rules — zero architectural changes. **Target: implement these.**

| # | Item | Why Doable | Effort |
|---|------|------------|--------|
| 1 | **Require 4 top-level fields** | Already optional in validator; just flip to required (allow empty lists) | ~30 min |
| 2 | **Require `teardown_commands` in test_fixtures** | Simple validation rule | ~15 min |
| 3 | **Require `acceptance_criteria` on CREATE goals** | Validator already checks this; just make mandatory | ~15 min |
| 4 | **Ban placeholder secrets (`{{...}}`, `***`)** | Simple recursive scan in validator | ~20 min |
| 5 | **Require imports in blueprints** | Heuristic check (`import ` / `from `) | ~20 min |
| 6 | **Update system prompt** | Add the 10 rules from Section 4 | ~15 min |
| 7 | **Update few-shot example** | Show all 4 fields + teardown + acceptance_criteria | ~15 min |

---

### ⚠️ NEEDS DESIGN DECISIONS — Doable But Requires Choices

| # | Item | Concern |
|---|------|---------|
| 8 | **Prevent dangling script references** | Validator would need to track `output_file` vs `depends_on` vs `command` — regex on shell commands is fragile |
| 9 | **Make `services` required in `environment`** | Current schema: `services: []` optional. Adding requirement is fine but what if spec genuinely needs no services? |

---

### 🚫 SKIP — Low ROI / High Complexity

| # | Item | Why Skip |
|---|------|----------|
| 10 | **Force real test execution in verification** | Can't validate statically. The prompt says "add pytest step for test files" — but we can't verify the model actually did it without running the test. |
| 11 | **Make all 4 fields required (no empty lists)** | Some specs genuinely don't need `business_rules` (e.g., pure infrastructure). Keep optional but *warn* if missing. |
| 12 | **Blueprint "completeness" check** | "No ellipsis, no missing variables" — this requires code analysis, not string matching. |
| 13 | **Services list in environment as mandatory** | Often empty. Keep optional. |

---

## 4. System Prompt Additions

Insert these rules **after** the existing format description in `SYSTEM_PROMPT_TEMPLATE`. They must be part of the prompt that the LLM sees on every generation call.

```
RULES FOR ALL SPECS (must be followed exactly):

The following sections are REQUIRED in every spec, even if they are empty:

business_rules: [] # list of {name, formula}

test_fixtures: [] # list of {name, setup_commands, teardown_commands}

environment: # must contain: packages (list), env_vars (dict), services (list)
  packages: []
  env_vars: {}
  services: []

global_verification: [] # list of shell commands

Every test_fixtures entry MUST include both setup_commands AND teardown_commands.
If no teardown is needed, write: teardown_commands: []

Every CREATE goal MUST include:
  A blueprint field with ALL necessary import statements.
  A non-empty acceptance_criteria list. Each criterion must have test (description) and steps (pseudo-code).

NEVER use placeholder strings like {{JWT_SECRET}} or *** in any value.
Use concrete test values (e.g., JWT_SECRET: "test-secret-32chars").

If a verification command references a script file (e.g., python scripts/seed_foo.py), that script must either be:
  Listed in depends_on (meaning it already exists), OR
  Created by another goal in the same spec (it must have an output_file that matches).
Otherwise, do not reference it.

For every CREATE goal that creates a test file (path starting with tests/),
add a verification step that runs that test (e.g., pytest <file>).
Do not rely only on file_exists or content_contains.

All blueprints must be complete, runnable code – no ellipsis, no missing variables.
```

---

## 5. Validator Enhancements

Add the following code to `validate_spec()`. Place it **after** the existing checks (but still within the function).

```python
    # =====================================================================
    # NEW ENRICHED-SPEC VALIDATION (add after the existing checks)
    # =====================================================================

    # 1. Require new top-level sections (allow empty lists/dicts)
    for section in ['business_rules', 'test_fixtures', 'environment', 'global_verification']:
        if section not in spec:
            errors.append(f"Missing required top-level key: {section}")
        else:
            if section == 'business_rules' and not isinstance(spec[section], list):
                errors.append("business_rules must be a list")
            if section == 'test_fixtures':
                for fix in spec['test_fixtures']:
                    if not isinstance(fix, dict):
                        errors.append(f"test_fixtures entry is not a dict: {fix}")
                        continue
                    if 'teardown_commands' not in fix:
                        errors.append(f"Test fixture '{fix.get('name', '?')}' missing 'teardown_commands'. Add an empty list if not needed.")
                    elif not isinstance(fix['teardown_commands'], list):
                        errors.append(f"Test fixture '{fix.get('name', '?')}': teardown_commands must be a list")
            if section == 'environment':
                env = spec['environment']
                if not isinstance(env, dict):
                    errors.append("environment must be a dict")
                else:
                    if 'packages' not in env or not isinstance(env['packages'], list):
                        errors.append("environment.packages must be a list")
                    if 'env_vars' not in env or not isinstance(env['env_vars'], dict):
                        errors.append("environment.env_vars must be a dict")
                    # services is optional but must be a list if present
                    if 'services' in env and not isinstance(env['services'], list):
                        errors.append("environment.services must be a list")

    # 2. Enforce acceptance_criteria on all CREATE goals
    for goal in spec.get('local_goals', []):
        if not isinstance(goal, dict):
            continue
        gid = goal.get('id', '?')
        if goal.get('type') == 'create':
            if 'acceptance_criteria' not in goal or not isinstance(goal['acceptance_criteria'], list) or len(goal['acceptance_criteria']) == 0:
                errors.append(f"Goal {gid}: CREATE goals require a non-empty 'acceptance_criteria' list")
            # 3. Check for missing imports in blueprint
            blueprint = goal.get('blueprint', '')
            if blueprint and ('def ' in blueprint or 'class ' in blueprint) and 'import ' not in blueprint and 'from ' not in blueprint:
                errors.append(f"Goal {gid}: blueprint appears to be missing import statements. Add all necessary imports.")

    # 4. No placeholder secrets anywhere in the spec
    def _has_placeholders(obj, path="spec"):
        if isinstance(obj, str):
            if '{{' in obj or '***' in obj:
                errors.append(f"{path}: contains placeholder ({{...}} or ***) – use concrete test values")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _has_placeholders(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _has_placeholders(v, f"{path}[{i}]")
    _has_placeholders(spec)

    # 5. Prevent references to external scripts that are not created or depended on
    # (This is a soft check – warns but doesn't block, since regex on shell is fragile)
    created_files = set()
    for goal in spec.get('local_goals', []):
        out = goal.get('output_file')
        if out:
            created_files.add(out)
    for goal in spec.get('local_goals', []):
        if not isinstance(goal, dict):
            continue
        gid = goal.get('id', '?')
        ver = goal.get('verification', {})
        if not isinstance(ver, dict):
            continue
        cmd = ver.get('command', '')
        # Find all paths that look like scripts/...
        import re
        script_refs = re.findall(r'\bscripts/\S+', cmd)
        for ref in script_refs:
            # ref may include trailing punctuation; strip it
            clean_ref = ref.rstrip('"\' ,;')
            if clean_ref not in created_files and clean_ref not in spec.get('depends_on', []):
                # Warning only – don't hard-fail because regex can catch false positives
                errors.append(
                    f"Goal {gid}: [WARN] verification references script '{clean_ref}' which is not created in this spec "
                    "and not listed in depends_on. Consider adding a goal to create it or remove the reference."
                )
```

---

## 6. Recommended Implementation Plan

```bash
# 1. Validator: Make 4 fields required (but allow empty lists/dicts)
# 2. Validator: Require teardown_commands in test_fixtures
# 3. Validator: Require acceptance_criteria on type:create
# 4. Validator: Ban {{...}} and *** anywhere (recursive scan)
# 5. Validator: Heuristic import check in blueprints
# 6. Validator: Soft warning for dangling script references
# 7. System prompt: Add the 10 rules from Section 4
# 8. Few-shot example: Update to show all 4 fields + teardown + acceptance_criteria
```

**Estimated effort: 2-3 hours total.**

---

## 7. Next Steps

1. **Start with items 1-5 + prompt/few-shot updates** (low-hanging fruit)
2. **Test with 5-10 batch generations** to verify consistency
3. **Evaluate items 8-9** (design decisions) if needed
4. **Skip items 10-13** permanently

---

*Document last updated: 2026-07-30*  
*Based on analysis of 8 generated specs using the enriched pipeline*

---

## 8. Prompt Engineering Fixes (deepseek-r1 Test Results)

**Test date**: 2026-07-30  
**Model**: deepseek-r1:7b via Ollama  
**Prompt**: "Create a scheduled task that generates a daily operational report summarizing API usage, verification outcomes, failed jobs, and system health. Store the report and make it available through an authenticated download endpoint. Add unit tests and integration tests."

### Failure Analysis (3 attempts, all YAML syntax errors)

| Attempt | Error | Root Cause |
|---------|-------|------------|
| 1 | `expected <block end>, but found '<scalar>'` on `value: "0 8 * * *" (cron expression)` | Inline comment after quoted value — YAML parser sees `(cron expression)` as a new scalar |
| 2 | `found character '@' that cannot start any token` on `@dag schedule="0 8 * * *"` | Decorator syntax (`@dag`) in a plain YAML value — `@` is a reserved indicator |
| 3 | `expected <block end>, but found '?'` on `- type: cli` / `command: "pytest...` | Indentation mismatch — sequence item keys at different indentation levels |

### Key Insight

deepseek-r1 understands the spec structure correctly (task_id, local_goals, verification, etc.) but fails on YAML syntax. This is a **prompt engineering** problem, not a capability problem.

### Prompt Fixes Applied

Added 10 explicit YAML formatting rules to `SYSTEM_PROMPT` in `run_pipeline.py`:

1. **Quoting**: Any string with `:`, `@`, `#`, `*`, `&`, `!`, `%`, `|`, `>` must be double-quoted
2. **No inline comments** after quoted values on the same line
3. **Blueprint code** must be in `blueprint: |` block scalars (never plain values with `@` or `*`)
4. **Never start a value** with `@`, `*`, `&`, `!`, `%`, `#`, `|`, `>`, or backtick
5. **Indentation**: consistent 6-space alignment for keys under list items, +2 for nesting
6. **Cron expressions** must be double-quoted: `schedule: "0 8 * * *"`
7. **No top-level `description`** field — use `summary` instead
8. **No `---` prefix** — start with `task_id:` as first line
9. **No `name:` at top level** — the identifier is `task_id`
10. All YAML must parse with `yaml.safe_load()`

### Retry Prompt Enhancement

The retry prompt (sent when validation fails) now includes explicit reminders:
- `task_id` first (no `---` prefix)
- `id` fields start with `L` (L1, L2...)
- Quote all strings with colons or special chars
- Put code in `blueprint: |` blocks
- Never put inline comments after a quoted value

### Status

- **Validator**: Items 1-5 from Section 6 implemented (4 required fields, teardown_commands, acceptance_criteria, placeholder ban, import check)
- **Prompt**: 10 YAML formatting rules added + retry prompt enhanced
- **Few-shot example**: Fully enriched with all fields, teardown, acceptance_criteria, imports in blueprints
- **Default model**: Reverted to `qwen2.5-coder:7b-instruct` (was regressed to `qwen3.5-4b-128k:latest`)