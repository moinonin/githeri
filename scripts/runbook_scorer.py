"""Runbook Scorer — scores how well a spec maps to a runbook-ready spec.

Scoring categories (weights from docs/scoring_spec.md):
  1. Intent & Goals (20%)
  2. Preconditions (15%)
  3. Command Runway Structure (30%)
  4. Verification Testability (25%)
  5. Completion Coverage (10%)
"""
import yaml
import re

VALID_GLOBAL_GOALS = {f"G{i}" for i in range(1, 20)}

# Required expect keys per verification type (matching validator)
REQUIRED_EXPECT_KEYS = {
    "http": {"status"},
    "cli": {"exit_code"},
    "file_exists": {"content", "content_contains", "content_not_contains", "exists"},
    "manual": set(),
}

# CLI command patterns for stage classification.
# Inspect: read-only checks (file existence, show file, list directory)
INSPECT_PATTERNS = ["test -f", "head", "cat", "ls", "stat"]
# Create/Modify: build, install, migrate, generate — actually changes the codebase
CREATE_MODIFY_PATTERNS = ["build", "install", "migrate", "generate", "scaffold", "pnpm build", "npm run build", "gradle build"]
# Verify: test, lint, check — asserts the code works
VERIFY_PATTERNS_CLI = ["test", "lint", "check"]


def _check_inspect(goals):
    """Check if there's at least one inspect goal.

    Inspect = read-only: file_exists verification, or CLI commands that read
    (test -f, head, cat, ls, stat). A file_exists goal IS an inspect, NOT a
    create — it checks that something exists, it doesn't create it.

    Explicitly-typed goals also count: type: 'inspect' or type: 'verify'.
    """
    for g in goals:
        gtype = g.get("type", "").lower()
        # Explicit goal type takes precedence
        if gtype == "inspect":
            return True
        ver = g.get("verification", {})
        if ver.get("type") == "file_exists":
            return True
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if any(p in cmd for p in INSPECT_PATTERNS):
                return True
    return False


def _check_create_modify(goals):
    """Check if there's at least one create/modify goal.

    Create/Modify = a CLI build/install/migrate command, OR an explicitly-typed
    create goal (type: 'create'), OR a file_exists check on a NEW file path
    that isn't already in the codebase (best heuristic available without git
    diff access). Goals with type: 'create' count as create even if they use
    file_exists verification — the executor will generate the file.
    """
    for g in goals:
        gtype = g.get("type", "").lower()
        # Explicit create type ALWAYS counts
        if gtype == "create":
            return True
        ver = g.get("verification", {})
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if any(p in cmd for p in CREATE_MODIFY_PATTERNS):
                return True
    return False


def _check_verify(goals):
    """Check if there's at least one verify goal.

    Verify = HTTP endpoint check, CLI test/lint/check command, OR an
    explicitly-typed verify goal (type: 'verify'), OR a file_exists goal
    with content_contains/content checks (asserts content shape, not just
    existence).
    """
    for g in goals:
        gtype = g.get("type", "").lower()
        # Explicit verify type ALWAYS counts
        if gtype == "verify":
            return True
        ver = g.get("verification", {})
        if ver.get("type") == "http":
            return True
        if ver.get("type") == "cli":
            cmd = ver.get("command", "")
            if any(p in cmd for p in VERIFY_PATTERNS_CLI):
                return True
        # file_exists with content assertion counts as verify (checks shape)
        if ver.get("type") == "file_exists":
            expect = ver.get("expect", {})
            if any(k in expect for k in ["content_contains", "content_not_contains", "content"]):
                return True
    return False


def prompt_heuristic_score(prompt: str, spec: dict) -> float:
    """Heuristic score for completion coverage based on prompt and spec."""
    if not prompt:
        return 0.0

    score = 1.0
    prompt_lower = prompt.lower()
    goals = spec.get("local_goals", [])

    # Check for status codes mentioned in prompt
    if any(code in prompt_lower for code in ["200", "201", "202", "204", "400", "401", "403", "404", "409", "422", "429", "500", "503"]):
        has_http_status = any(
            g.get("verification", {}).get("type") == "http" and
            "status" in g.get("verification", {}).get("expect", {})
            for g in goals
        )
        if not has_http_status:
            score -= 0.8  # Very strong penalty

    # Check for test mentions
    if "test" in prompt_lower:
        has_test_verify = any(
            g.get("verification", {}).get("type") == "cli" and
            "test" in g.get("verification", {}).get("command", "")
            for g in goals
        )
        if not has_test_verify:
            score -= 0.8  # Very strong penalty

    # Check for OpenAPI/spec mentions
    if any(term in prompt_lower for term in ["openapi", "swagger"]):
        has_openapi_check = any(
            g.get("verification", {}).get("type") == "cli" and
            any(t in g.get("verification", {}).get("command", "") for t in ["openapi", "swagger", "redocly"])
            for g in goals
        )
        if not has_openapi_check:
            score -= 0.7  # Strong penalty

    # Check for scheduled/cron mentions
    if any(term in prompt_lower for term in ["scheduled", "cron", "background", "worker"]):
        has_scheduled = any(
            "cron" in g.get("verification", {}).get("command", "") or
            "schedule" in g.get("verification", {}).get("command", "") or
            g.get("verification", {}).get("type") == "manual"
            for g in goals
        )
        if not has_scheduled:
            score -= 0.6

    return max(0.0, min(1.0, score))


def runbook_score(spec):
    """Score a spec on how well it would translate into a complete COMMAND_RUNWAY.

    Returns:
        tuple: (score: float 0.0-1.0, details: list[str])
    """
    score = 1.0
    details = []

    goals = spec.get("local_goals", [])

    # 1. Intent & Goals (20%)
    intent_score = 1.0
    if not spec.get("summary"):
        intent_score -= 0.8
        details.append("Summary missing")
    for g in goals:
        if not g.get("description"):
            intent_score -= 0.4
            details.append(f"Goal {g.get('id')} missing description")

    # Endpoint task should have HTTP verification
    summary_lower = spec.get("summary", "").lower()
    if ("endpoint" in summary_lower or
        any("endpoint" in g.get("description", "").lower() for g in goals)):
        if not any(g.get("verification", {}).get("type") == "http" for g in goals):
            intent_score -= 0.8
            details.append("Endpoint task lacks HTTP verification")

    # Database/model task should have file_exists or cli create
    if any(kw in summary_lower for kw in ["model", "schema", "database", "table", "entity"]):
        if not any(
            g.get("verification", {}).get("type") == "file_exists" or
            (g.get("verification", {}).get("type") == "cli" and any(p in g.get("verification", {}).get("command", "") for p in CREATE_MODIFY_PATTERNS))
            for g in goals
        ):
            intent_score -= 0.7
            details.append("Database/model task lacks file_exists or create verification")

    intent_score = max(0.0, intent_score)
    score -= 0.20 * (1 - intent_score)

    # 2. Preconditions (15%)
    precond_score = 1.0
    deps = spec.get("depends_on", []) or []
    for d in deps:
        if d not in VALID_GLOBAL_GOALS and not d.startswith("stage-"):
            precond_score -= 0.8
            details.append(f"Unknown dependency '{d}'")

    context = spec.get("context", {})
    context_str = str(context).lower()
    if "express" in context_str and "prisma" in context_str:
        if not any(d == "stage-1-core-models" for d in deps):
            precond_score -= 0.8
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
    if tools_used and not any(t in context_str for t in tools_used):
        precond_score -= 0.8  # Harsh penalty - context mismatch is serious
        details.append("Context missing tools used in commands")

    score -= 0.15 * (1 - max(0.0, precond_score))

    # 3. Command Runway Structure (30%) — the heaviest weight
    # Missing entire stage types is a serious structural deficiency.
    # HARD GATE: a runbook-ready spec MUST have at least one of each:
    #   inspect (file_exists or read-only CLI), create/modify (build CLI), verify (HTTP or test CLI)
    # If any is missing, the spec is not runbook-ready → return 0.0 score.
    struct_score = 1.0
    has_inspect = _check_inspect(goals)
    has_create = _check_create_modify(goals)
    has_verify = _check_verify(goals)

    if not has_inspect:
        struct_score -= 0.8
        details.append("No inspect goal (file_exists or read-only CLI)")
    if not has_create:
        struct_score -= 0.9  # Very harsh - create is essential
        details.append("No create/modify goal (build/install/migrate CLI)")
    if not has_verify:
        struct_score -= 0.9  # Very harsh - verify is essential
        details.append("No verify goal (HTTP endpoint or test/lint CLI)")

    # Check stage order: inspect -> create -> verify (only if all three stages present)
    if has_inspect and has_create and has_verify:
        inspect_idx = -1
        create_idx = -1
        verify_idx = -1
        for i, g in enumerate(goals):
            ver = g.get("verification", {})
            # Inspect stage
            if ver.get("type") == "file_exists" or (
                ver.get("type") == "cli" and any(p in ver.get("command", "") for p in INSPECT_PATTERNS)
            ):
                if inspect_idx == -1:
                    inspect_idx = i
            # Create/Modify stage (CLI build only — file_exists is inspect, not create)
            if ver.get("type") == "cli" and any(
                p in ver.get("command", "") for p in CREATE_MODIFY_PATTERNS
            ):
                if create_idx == -1:
                    create_idx = i
            # Verify stage
            if ver.get("type") == "http" or (
                ver.get("type") == "cli" and any(p in ver.get("command", "") for p in VERIFY_PATTERNS_CLI)
            ):
                if verify_idx == -1:
                    verify_idx = i

        if inspect_idx != -1 and create_idx != -1 and inspect_idx > create_idx:
            struct_score -= 0.4
            details.append("Inspect goal appears after create goal")
        if create_idx != -1 and verify_idx != -1 and create_idx > verify_idx:
            struct_score -= 0.4
            details.append("Create goal appears after verify goal")
        if inspect_idx != -1 and verify_idx != -1 and inspect_idx > verify_idx:
            struct_score -= 0.3
            details.append("Inspect goal appears after verify goal")

    # Hard gate: if any of the three required stages is missing, spec is not runbook-ready
    if not (has_inspect and has_create and has_verify):
        return 0.0, details + ["HARD GATE: spec missing required runway stage(s) - not runbook-ready"]

    struct_score = max(0.0, struct_score)
    score -= 0.30 * (1 - struct_score)

    # 4. Verification Testability (25%)
    test_score = 1.0
    for g in goals:
        ver = g.get("verification", {})
        vtype = ver.get("type")
        if vtype == "http":
            if not ver.get("url"):
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing URL")
            if "expect" not in ver or "status" not in ver.get("expect", {}):
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing expected status")
        elif vtype == "cli":
            if not ver.get("command"):
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing CLI command")
            expect = ver.get("expect", {})
            if "exit_code" not in expect:
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing required expect.exit_code")
        elif vtype == "file_exists":
            if not ver.get("path"):
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing file path")
            expect = ver.get("expect", {})
            if not any(k in expect for k in REQUIRED_EXPECT_KEYS["file_exists"]):
                test_score -= 0.4
                details.append(f"Goal {g['id']} missing required expect check (content/exists)")

    if test_score < 0:
        test_score = 0
    score -= 0.25 * (1 - test_score)

    # 5. Completion Coverage (10%)
    prompt_score = prompt_heuristic_score(spec.get("_prompt", ""), spec)
    score -= 0.10 * (1 - prompt_score)

    return max(0.0, min(1.0, score)), details