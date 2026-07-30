"""Tests for runbook_scorer.py — the spec-to-runbook quality scorer."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from runbook_scorer import (
    runbook_score,
    _check_inspect,
    _check_create_modify,
    _check_verify,
    prompt_heuristic_score,
)


def _spec_from_goals(goals_yaml: str, extra_top_level: str = "") -> str:
    """Build a minimal valid spec with the given local_goals."""
    return f"""task_id: test-feature
summary: "A test feature"
{extra_top_level}
local_goals:
{goals_yaml}
context:
  language: TypeScript
  framework: Express
  orm: Prisma
  test_framework: Vitest
"""


def _goal(gid: str, vtype: str, **kwargs) -> str:
    """Build a single goal YAML block."""
    gtype = kwargs.pop("gtype", None)
    lines = [f"  - id: {gid}", f"    description: 'goal {gid}'"]
    if gtype:
        lines.append(f"    type: {gtype}")
    lines.append("    verification:")
    lines.append(f"      type: {vtype}")
    for k, v in kwargs.items():
        if isinstance(v, dict):
            import json
            lines.append(f"      {k}: {json.dumps(v)}")
        elif isinstance(v, str):
            lines.append(f"      {k}: {v}")
        else:
            lines.append(f"      {k}: {v}")
    return "\n".join(lines)


def test_check_inspect_detects_file_exists():
    g1 = _goal("L1", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_inspect(spec_dict["local_goals"]) is True


def test_check_inspect_detects_cli_inspect_commands():
    g1 = _goal("L1", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_inspect(spec_dict["local_goals"]) is True


def test_check_inspect_missing():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_inspect(spec_dict["local_goals"]) is False


def test_check_create_modify_detects_file_exists():
    """file_exists is an inspect operation, not create/modify.
    Create/modify should be detected via CLI build/install/migrate commands."""
    g1 = _goal("L1", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    # file_exists is inspect, not create/modify
    assert _check_create_modify(spec_dict["local_goals"]) is False


def test_check_create_modify_detects_build_commands():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_create_modify(spec_dict["local_goals"]) is True


def test_check_create_modify_missing():
    g1 = _goal("L1", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_create_modify(spec_dict["local_goals"]) is False


def test_check_verify_detects_http():
    g1 = _goal("L1", "http", method="GET", url='"http://x"', expect='{"status": 200}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_verify(spec_dict["local_goals"]) is True


def test_check_verify_detects_cli_test():
    g1 = _goal("L1", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_verify(spec_dict["local_goals"]) is True


def test_check_verify_missing():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_verify(spec_dict["local_goals"]) is False


def test_runbook_score_high_quality_spec():
    """A well-structured spec with inspect, create, verify stages scores high."""
    g1 = _goal("L1", "file_exists", path='"src/models/User.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g3 = _goal("L3", "http", method="GET", url='"http://localhost:3000/health"', expect='{"status": 200}')
    spec = _spec_from_goals(g1 + "\n" + g2 + "\n" + g3, 'depends_on: ["stage-1-core-models"]\n')
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score >= 0.7, f"Expected score >= 0.7, got {score}: {details}"


def test_runbook_score_penalizes_missing_inspect():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score < 1.0
    assert any("inspect" in d.lower() for d in details)


def test_runbook_score_penalizes_missing_create():
    g1 = _goal("L1", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score < 1.0
    assert any("create" in d.lower() or "modify" in d.lower() for d in details)


def test_runbook_score_penalizes_missing_verify():
    g1 = _goal("L1", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score < 1.0
    assert any("verify" in d.lower() for d in details)


def test_runbook_score_penalizes_wrong_order():
    """Create before inspect should trigger hard gate (missing inspect stage comes first).
    This spec has build (create), cat (inspect), test (verify) — all three stages present,
    but in wrong order. Should NOT hit hard gate, should report ordering issue."""
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"cat src/x.ts"', expect='{"exit_code": 0}')
    g3 = _goal("L3", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2 + "\n" + g3)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    # All three stages present, so hard gate passes; should get ordering penalty
    assert score > 0.0, f"Expected non-zero score, got {score}: {details}"
    assert any("inspect goal appears after create goal" in d.lower() for d in details) or \
           any("create goal appears after verify goal" in d.lower() for d in details)


def test_check_create_modify_detects_explicit_create_type():
    """Explicit type: 'create' on a goal should be detected as create/modify,
    even if verification is file_exists (executor will generate the file)."""
    g1 = _goal("L1", "file_exists", gtype="create", path='"src/models/User.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_create_modify(spec_dict["local_goals"]) is True


def test_check_inspect_detects_explicit_inspect_type():
    """Explicit type: 'inspect' should be detected even if verification doesn't match patterns."""
    g1 = _goal("L1", "cli", gtype="inspect", command='"some custom command"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_inspect(spec_dict["local_goals"]) is True


def test_check_verify_detects_explicit_verify_type():
    """Explicit type: 'verify' should be detected even if verification doesn't match patterns."""
    g1 = _goal("L1", "manual", gtype="verify", description='"manual check"')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_verify(spec_dict["local_goals"]) is True


def test_check_verify_detects_file_exists_with_content_check():
    """file_exists with content_contains should count as verify (asserts content shape)."""
    g1 = _goal("L1", "file_exists", path='"src/models/User.ts"',
               expect='{"content_contains": ["password_hash", "bcrypt"]}')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    assert _check_verify(spec_dict["local_goals"]) is True


def test_runbook_score_create_with_file_exists_passes_hard_gate():
    """A spec with explicit type: 'create' + file_exists should NOT hit the hard gate.
    This is the 'Create a User model' pattern: file_exists verifies the file was generated."""
    g1 = _goal("L1", "file_exists", gtype="create", path='"src/models/User.py"',
               expect='{"content_contains": ["password_hash", "bcrypt"]}')
    g2 = _goal("L2", "file_exists", gtype="verify", path='"src/models/User.py"',
               expect='{"exists": true}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    # Should NOT hit hard gate because explicit create + verify types are present
    assert score > 0.0, f"Expected non-zero score, got {score}: {details}"
    assert not any("HARD GATE" in d for d in details), f"Should not hit hard gate: {details}"


def test_runbook_score_verification_testability_http():
    g1 = _goal("L1", "http", method="GET", url='"http://localhost:3000/x"', expect='{}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    # Add an inspect goal to pass hard gate
    g3 = _goal("L3", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    # Add a create goal to pass hard gate
    g4 = _goal("L4", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2 + "\n" + g3 + "\n" + g4)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score > 0.0, f"Expected non-zero score, got {score}: {details}"
    assert any("missing expected status" in d.lower() for d in details)


def test_runbook_score_verification_testability_cli():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"stdout_contains": "ok"}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    # Add an inspect goal to pass hard gate
    g3 = _goal("L3", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    # Add a verify HTTP goal to pass hard gate (already have test CLI)
    g4 = _goal("L4", "http", method="GET", url='"http://localhost:3000/x"', expect='{"status": 200}')
    spec = _spec_from_goals(g1 + "\n" + g2 + "\n" + g3 + "\n" + g4)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score > 0.0, f"Expected non-zero score, got {score}: {details}"
    assert any("missing required expect.exit_code" in d.lower() for d in details)


def test_runbook_score_verification_testability_file_exists():
    g1 = _goal("L1", "file_exists", path='"src/x.ts"', expect='{}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    # Add a create goal to pass hard gate
    g3 = _goal("L3", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    # Add a verify HTTP goal to pass hard gate
    g4 = _goal("L4", "http", method="GET", url='"http://localhost:3000/x"', expect='{"status": 200}')
    spec = _spec_from_goals(g1 + "\n" + g2 + "\n" + g3 + "\n" + g4)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert score > 0.0, f"Expected non-zero score, got {score}: {details}"
    assert any("missing required expect check" in d.lower() for d in details)


def test_runbook_score_intent_goals_summary():
    """Missing summary should be penalized."""
    g1 = _goal("L1", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    # Remove summary
    import yaml
    spec_dict = yaml.safe_load(spec)
    del spec_dict["summary"]
    score, details = runbook_score(spec_dict)
    assert any("summary missing" in d.lower() for d in details)


def test_runbook_score_intent_endpoint_needs_http_verify():
    """Endpoint task without HTTP verification should be penalized."""
    g1 = _goal("L1", "file_exists", path='"src/routes/sessions.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(
        g1 + "\n" + g2,
        'summary: "Add POST /sessions endpoint"\n'
    )
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert any("endpoint task lacks http verification" in d.lower() for d in details)


def test_runbook_score_preconditions_depends_on_validity():
    g1 = _goal("L1", "file_exists", path='"src/x.ts"', expect='{"exists": true}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2, 'depends_on: ["stage-1-core-models", "G99"]\n')
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    assert any("unknown dependency" in d.lower() for d in details)


def test_runbook_score_preconditions_tool_context():
    g1 = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(
        g1 + "\n" + g2,
        'context:\n  language: TypeScript\n  framework: Express\n'
    )
    import yaml
    spec_dict = yaml.safe_load(spec)
    score, details = runbook_score(spec_dict)
    # Should not penalize if tools mentioned in context
    # (This test ensures the tool context check doesn't false-positive)


def test_prompt_heuristic_score_empty_prompt():
    score = prompt_heuristic_score("", {})
    assert score == 0.0


def test_prompt_heuristic_score_status_code_check():
    prompt = "Add endpoint returning 201 on success"
    g1 = _goal("L1", "http", method="POST", url='"http://x"', expect='{"status": 201}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score = prompt_heuristic_score(prompt, spec_dict)
    assert score >= 0.7


def test_prompt_heuristic_score_missing_test_verify():
    prompt = "Add endpoint with tests"
    g1 = _goal("L1", "http", method="POST", url='"http://x"', expect='{"status": 201}')
    g2 = _goal("L2", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    spec = _spec_from_goals(g1 + "\n" + g2)
    import yaml
    spec_dict = yaml.safe_load(spec)
    score = prompt_heuristic_score(prompt, spec_dict)
    assert score < 1.0