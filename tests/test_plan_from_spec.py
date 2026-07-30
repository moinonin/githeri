"""Tests for scripts/plan_from_spec.py — the spec extraction + prompt assembly.

Run:  .venv/bin/python -m pytest tests/test_plan_from_spec.py -v
"""
import subprocess
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
PY = str(REPO / ".venv" / "bin" / "python")
PLAN_SCRIPT = str(REPO / "scripts" / "plan_from_spec.py")
DATA_FILE = str(REPO / "data" / "training_data.jsonl")
VALID_SPEC_PATH = str(REPO / "tests" / "fixtures" / "valid_spec.yaml")
INVALID_SPEC_PATH = str(REPO / "tests" / "fixtures" / "invalid_spec.yaml")


def _run(args):
    """Run plan_from_spec.py with args; return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [PY, PLAN_SCRIPT] + args,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    return result.returncode, result.stdout, result.stderr


# ---------- fixtures: create valid + invalid spec test files once ----------

VALID_YAML = """\
task_id: test-feature
summary: "A test feature"
business_rules: []
test_fixtures: []
environment:
  packages: []
  env_vars: {}
  services: []
global_verification: []
local_goals:
  - id: L1
    description: "Build runs"
    verification:
      type: cli
      command: "pnpm build"
      expect:
        exit_code: 0
  - id: L2
    description: "Tests pass"
    verification:
      type: cli
      command: "pnpm test"
      expect:
        exit_code: 0
context:
  language: TypeScript
"""

INVALID_YAML = """\
task_id: ""
summary: "A bad spec"
business_rules: []
test_fixtures: []
environment:
  packages: []
  env_vars: {}
  services: []
global_verification: []
local_goals:
  - id: L1
    description: "only one goal"
    verification:
      type: cli
      command: "pnpm build"
      expect:
        exit_code: 0
context:
  language: TypeScript
"""


# ---------- tests ----------

def test_valid_yaml_file_emits_prompt_and_spec():
    """A valid .yaml file → exit 0, stdout contains runbookprompt + spec."""
    fixture = pathlib.Path(VALID_SPEC_PATH)
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(VALID_YAML)
    try:
        code, out, err = _run([VALID_SPEC_PATH])
        assert code == 0, f"expected exit 0, got {code}: {err}"
        assert "ACCEPTED INPUT FORMATS" in out   # runbookprompt loaded
        assert "test-feature" in out              # spec_yaml included
        assert "SUPPLIED SPECIFICATION" in out    # the spec block marker
        assert "```yaml" in out                   # spec wrapped in yaml fence
    finally:
        fixture.unlink(missing_ok=True)


def test_invalid_yaml_file_exits_nonzero():
    """An invalid .yaml file (empty task_id, only 1 goal) → exit 1, no prompt."""
    fixture = pathlib.Path(INVALID_SPEC_PATH)
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(INVALID_YAML)
    try:
        code, out, err = _run([INVALID_SPEC_PATH])
        assert code == 1, f"expected exit 1, got {code}: stdout={out[:100]}"
        assert "failed validation" in err
        assert "ACCEPTED INPUT FORMATS" not in out  # no prompt emitted
    finally:
        fixture.unlink(missing_ok=True)


def test_jsonl_index_extraction():
    """`data/training_data.jsonl#0` → extracts first pair's spec_yaml."""
    if not pathlib.Path(DATA_FILE).exists():
        import pytest
        pytest.skip("training_data.jsonl not present")
    code, out, err = _run([f"{DATA_FILE}#0"])
    assert code == 0, f"expected exit 0, got {code}: {err}"
    assert "SUPPLIED SPECIFICATION" in out
    # The first pair's spec_yaml should appear
    import json
    pairs = [
        json.loads(line)
        for line in pathlib.Path(DATA_FILE).read_text().strip().splitlines()
    ]
    first_task_id = pairs[0]["spec_yaml"].splitlines()[0].strip()
    assert first_task_id in out


def test_jsonl_out_of_range_index_exits_nonzero():
    """An out-of-range index → exit 2 (file/parse error), not 1 (validation)."""
    if not pathlib.Path(DATA_FILE).exists():
        import pytest
        pytest.skip("training_data.jsonl not present")
    code, out, err = _run([f"{DATA_FILE}#99999"])
    assert code == 2
    assert "out of range" in err


def test_nonexistent_file_exits_nonzero():
    """A path that doesn't exist → exit 2, clear error."""
    code, out, err = _run(["/tmp/nonexistent_spec.yaml"])
    assert code == 2
    assert "not found" in err


def test_no_args_prints_usage():
    """No args → exit 2, usage printed to stderr."""
    code, out, err = _run([])
    assert code == 2
    assert "USAGE" in err or "usage" in err
