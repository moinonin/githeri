"""Tests for scripts/validator.py — the spec conformance gate.

Run:  .venv/bin/python -m pytest tests/test_validator.py -v
  or:  .venv/bin/python -m pytest tests/ -v
"""
import sys
import re
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from validator import validate_spec  # noqa: E402
from validator import (  # noqa: E402
    VALID_VERIFICATION_TYPES,
    VALID_EXPECT_KEYS,
    REQUIRED_TOP_LEVEL,
    MIN_LOCAL_GOALS,
    MIN_BLUEPRINT_LENGTH,
    OPTIONAL_TOP_LEVEL,
)

# ---------- helpers ----------

VALID_CLI = """
task_id: foo
summary: "Foo bar"
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
        stdout_contains: "passing"
context:
  language: TypeScript
"""


def _spec(local_goals_yaml, toplevel_extras=""):
    """Build a minimal valid spec with custom local_goals."""
    return f"""
task_id: test-feature
summary: "A test feature"
{toplevel_extras}
local_goals:
{local_goals_yaml}
context:
  language: TypeScript
"""


def _goal(gid, gtype, **kwargs):
    """Build a single goal YAML snippet."""
    ver_type = kwargs.pop("verification_type", gtype if gtype in {"cli", "http", "file_exists", "manual"} else "file_exists")
    ver = {"type": ver_type}
    for k, v in kwargs.items():
        if k in {"command", "path", "method", "url", "body", "headers", "expect", "description"}:
            ver[k] = v
    # Remove empty expect
    if "expect" in ver and ver["expect"] == "":
        del ver["expect"]
    # Default expect for cli
    if ver_type == "cli" and "expect" not in ver:
        ver["expect"] = {"exit_code": 0}
    # Default expect for file_exists
    if ver_type == "file_exists" and "expect" not in ver:
        ver["expect"] = {"exists": True}
    # Default expect for http
    if ver_type == "http" and "expect" not in ver:
        ver["expect"] = {"status": 200}
    # Build YAML
    lines = [f"  - id: {gid}"]
    # Add goal-level type if it's create
    if gtype == "create":
        lines.append(f"    type: create")
    if "description" in kwargs:
        lines.append(f"    description: {kwargs['description']}")
    else:
        lines.append(f"    description: \"Goal {gid}\"")
    # Add blueprint if present
    if "blueprint" in kwargs:
        lines.append(f"    blueprint: |\n      " + "\n      ".join(kwargs["blueprint"].split("\n")))
    # Add acceptance_criteria if present
    if "acceptance_criteria" in kwargs:
        lines.append(f"    acceptance_criteria: {kwargs['acceptance_criteria']}")
    lines.append("    verification:")
    for vk, vv in ver.items():
        if isinstance(vv, dict):
            lines.append(f"      {vk}:")
            for ek, ev in vv.items():
                lines.append(f"        {ek}: {ev}")
        elif isinstance(vv, list):
            lines.append(f"      {vk}:")
            for item in vv:
                lines.append(f"        - {item}")
        else:
            lines.append(f"      {vk}: {vv}")
    return "\n".join(lines)


def errs(yaml_str):
    """Shorthand: return the error list as a list."""
    return validate_spec(yaml_str)


def _has_error(error_list, substring):
    return any(substring in e for e in error_list)


# ---------- canonical vocabulary ----------

def test_canonical_verification_types():
    assert VALID_VERIFICATION_TYPES == {"http", "cli", "file_exists", "manual"}


def test_canonical_expect_keys():
    assert VALID_EXPECT_KEYS["http"] == {"status", "body_regex", "body_contains", "json_schema", "headers_contain"}
    assert VALID_EXPECT_KEYS["cli"] == {"exit_code", "stdout_regex", "stdout_contains", "stdout_lines_min"}
    assert VALID_EXPECT_KEYS["file_exists"] == {"content", "content_contains", "content_not_contains", "exists"}
    assert VALID_EXPECT_KEYS["manual"] == set()


def test_required_top_level():
    assert REQUIRED_TOP_LEVEL == ["task_id", "summary", "local_goals", "context"]


def test_min_local_goals():
    assert MIN_LOCAL_GOALS == 2


# ---------- YAML pre-processor (regex-in-double-quotes fix) ----------

from validator import preprocess_yaml, _has_invalid_backslash_escape


def test_invalid_backslash_escape_detection():
    """Regex character-class escapes are invalid in YAML double-quoted scalars."""
    for esc in ["\\d", "\\w", "\\s", "\\D", "\\W", "\\S", "\\.", "\\[", "\\]", "\\*", "\\?"]:
        assert _has_invalid_backslash_escape(esc), f"{esc!r} should be detected as invalid"


def test_valid_yaml_escapes_not_flagged():
    """Valid YAML double-quoted escapes are NOT flagged."""
    for esc in ["\\n", "\\t", "\\\\", '\\"', "\\x41", "\\u0041"]:
        assert not _has_invalid_backslash_escape(esc), f"{esc!r} should NOT be flagged"


def test_preprocessor_fixes_regex_in_headers():
    """The exact rate-limiter failure: Retry-After: "\\d+" → single-quoted."""
    bad_yaml = (
        'task_id: rate-limiter\n'
        'summary: "Rate limiter"\n'
        'local_goals:\n'
        '  - id: L1\n'
        '    description: "first goal"\n'
        '    verification:\n'
        '      type: http\n'
        '      method: GET\n'
        '      url: http://localhost:3000/test\n'
        '      headers:\n'
        '        Retry-After: "\\d+"\n'
        '      expect:\n'
        '        status: 429\n'
        '  - id: L2\n'
        '    description: "second goal"\n'
        '    verification:\n'
        '      type: cli\n'
        '      command: "pnpm test"\n'
        '      expect:\n'
        '        exit_code: 0\n'
        'context:\n'
        '  language: TypeScript\n'
    )
    fixed, fixes = preprocess_yaml(bad_yaml)
    assert fixes == 1, f"expected 1 fix, got {fixes}"
    # The fixed line should use single quotes
    fixed_lines = fixed.splitlines()
    retry_line = [l for l in fixed_lines if "Retry-After" in l][0]
    assert "Retry-After: '\\d+'" in retry_line, f"not single-quoted: {retry_line!r}"
    # Full validation should now pass
    assert validate_spec(bad_yaml) == [], "pre-processed spec should validate cleanly"


def test_preprocessor_preserves_valid_yaml():
    """Valid YAML with no invalid escapes is returned unchanged."""
    valid = VALID_CLI
    fixed, fixes = preprocess_yaml(valid)
    assert fixes == 0
    assert fixed == valid


def test_preprocessor_preserves_valid_quoted_strings():
    """Strings with valid escapes (\\n, \\t) are NOT touched."""
    yaml_block = 'description: "line1\\nline2"\n'
    fixed, fixes = preprocess_yaml(yaml_block)
    assert fixes == 0
    assert fixed == yaml_block


def test_preprocessor_handles_multiple_offending_lines():
    """Multiple lines with invalid escapes are all fixed."""
    yaml_block = (
        'header1: "\\d+"\n'
        'header2: "\\w+"\n'
        'header3: "normal text"\n'
    )
    fixed, fixes = preprocess_yaml(yaml_block)
    assert fixes == 2, f"expected 2 fixes, got {fixes}"


def test_preprocessor_single_quote_inside_value():
    """If an offending value contains a single quote, it is escaped (doubled)."""
    yaml_block = "key: \"it\\'s a \\d regex\"\n"
    fixed, fixes = preprocess_yaml(yaml_block)
    assert fixes == 1
    # The single quote inside should be doubled
    assert "''" in fixed


# ---------- valid specs ----------

def test_minimal_valid_spec():
    assert errs(VALID_CLI) == []


def test_valid_http_spec():
    g = _goal("L1", "http",
              method="POST",
              url='http://localhost:3000/v1/sessions',
              expect='{"status": 201}')
    g2 = _goal("L2", "http",
               method="GET",
               url='http://localhost:3000/v1/sessions/{id}',
               expect='{"status": 200}')
    assert errs(_spec(g + "\n" + g2)) == []


def test_valid_file_exists_spec():
    g = _goal("L1", "file_exists",
              path="src/models/User.ts",
              expect='{"exists": true}')
    g2 = _goal("L2", "file_exists",
               path="docs/api.md",
               expect='{"content_contains": "## Endpoints"}')
    assert errs(_spec(g + "\n" + g2)) == []


def test_valid_manual_spec():
    g = _goal("L1", "manual", description='"Manual check"')
    g2 = _goal("L2", "manual", description='"Another manual check"')
    spec = f"""
task_id: manual-feature
summary: "Manual checks only"
local_goals:
{g}
{g2}
context:
  language: TypeScript
"""
    assert errs(spec) == []


def test_valid_global_goals_refs():
    spec = VALID_CLI.rstrip() + '\nglobal_goals_refs: ["G1", "G2"]\n'
    assert errs(spec) == []


# ---------- top-level errors ----------

def test_missing_top_level_field():
    bad = VALID_CLI.replace("summary:", "# summary:")
    e = errs(bad)
    assert _has_error(e, "Missing required top-level field: summary")


def test_unknown_top_level_field():
    bad = VALID_CLI.rstrip() + "\nfoobar: 123\n"
    e = errs(bad)
    assert _has_error(e, "Unknown top-level fields")


def test_task_id_must_be_nonempty():
    bad = VALID_CLI.replace("task_id: foo", 'task_id: ""')
    e = errs(bad)
    assert _has_error(e, "task_id must be a non-empty string")


def test_invalid_global_goal_ref():
    bad = VALID_CLI.rstrip() + '\nglobal_goals_refs: ["G1", "G99"]\n'
    e = errs(bad)
    assert _has_error(e, "Invalid global_goals_refs")


# ---------- local_goals errors ----------

def test_too_few_goals():
    g = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    e = errs(_spec(g))
    assert _has_error(e, "at least 2 goals")


def test_duplicate_goal_id():
    g = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g))
    assert _has_error(e, "Duplicate goal ID")


def test_bad_goal_id():
    g = _goal("X1", "cli", command='"pnpm build"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "id must start with 'L'")


# ---------- verification errors ----------

def test_unknown_verification_type():
    # Create a spec with an invalid verification type
    spec = """
task_id: test-feature
summary: "A test feature"
local_goals:
  - id: L1
    description: "Goal L1"
    verification:
      type: websocket
      path: src/x.ts
      expect:
        exists: true
  - id: L2
    description: "Goal L2"
    verification:
      type: cli
      command: "pnpm test"
      expect:
        exit_code: 0
context:
  language: TypeScript
"""
    e = errs(spec)
    assert _has_error(e, "unknown verification type 'websocket'")


def test_http_missing_method():
    g = _goal("L1", "http", url='"http://x"', expect='{"status": 200}')
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "http verification missing 'method'")


def test_http_missing_url():
    g = _goal("L1", "http", method="GET", expect='{"status": 200}')
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "http verification missing 'url'")


def test_http_missing_status_in_expect():
    g = _goal("L1", "http", method="GET", url='"http://x"', expect='{"body_contains": "ok"}')
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "http verification requires expect.status")


def test_cli_missing_command():
    g = _goal("L1", "cli", expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "cli verification missing 'command'")


def test_cli_trivial_command():
    g = _goal("L1", "cli", command='"a"', expect='{"exit_code": 0}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "cli command is trivial")


def test_cli_missing_exit_code():
    g = _goal("L1", "cli", command='"pnpm build"', expect='{"stdout_contains": "ok"}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "cli verification requires expect.exit_code")


def test_file_exists_missing_path():
    g = _goal("L1", "file_exists", expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path="src/x.ts", expect='{"exists": true}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "file_exists verification missing 'path'")


def test_file_exists_no_meaningful_check():
    g = _goal("L1", "file_exists", path="src/x.ts", expect="{}")
    g2 = _goal("L2", "file_exists", path="src/y.ts", expect='{"exists": true}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "file_exists verification needs at least one of")


def test_manual_missing_description():
    g = _goal("L1", "manual")
    g2 = _goal("L2", "manual", description='"ok"')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "manual verification requires a 'description'")


# ---------- unknown expect keys ----------

def test_unknown_expect_key_cli():
    g = _goal("L1", "cli", command='"pnpm build"', expect='{"exit_code": 0, "bogus_key": 1}')
    g2 = _goal("L2", "cli", command='"pnpm test"', expect='{"exit_code": 0}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "unknown expect keys")


def test_unknown_expect_key_http():
    g = _goal("L1", "http", method="GET", url='"http://x"', expect='{"status": 200, "bogus_key": 1}')
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "unknown expect keys")


def test_headers_inside_expect_is_rejected():
    """The model's common mistake — putting `headers` (a request-header field)
    INSIDE `expect` — must be rejected.  `headers` is a sibling of `expect`,
    not a child.  Only `headers_contain` (response-header assertions) is a
    valid expect key."""
    g = _goal(
        "L1", "http", method="GET", url='"http://x"',
        expect='{"status": 200, "headers": {"Authorization": "Bearer x"}}',
    )
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "unknown expect keys")


def test_headers_contain_is_accepted():
    """`headers_contain` (response-header assertions) IS a valid http expect key."""
    g = _goal(
        "L1", "http", method="GET", url='"http://x"',
        expect='{"status": 429, "headers_contain": {"Retry-After": "\\d+"}}',
    )
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert not _has_error(e, "unknown expect keys"), f"headers_contain was rejected: {e}"


# ---------- json_schema $ref / definitions ----------

def test_json_schema_ref_rejected():
    import json
    schema = {"$ref": "#/definitions/User"}
    g = _goal("L1", "http", method="GET", url='"http://x"',
              expect=json.dumps({"status": 200, "json_schema": schema}))
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "json_schema must be inline, no $ref")


def test_json_schema_definitions_rejected():
    import json
    schema = {"definitions": {"User": {"type": "object"}}}
    g = _goal("L1", "http", method="GET", url='"http://x"',
              expect=json.dumps({"status": 200, "json_schema": schema}))
    g2 = _goal("L2", "http", method="GET", url='"http://y"', expect='{"status": 200}')
    e = errs(_spec(g + "\n" + g2))
    assert _has_error(e, "json_schema must be inline, no 'definitions'")


# ---------- dedup ----------

def test_near_duplicate_file_exists_is_dup():
    """Same path AND same expect keys → duplicate (padding)."""
    g1 = _goal("L1", "file_exists", path='src/models/User.ts', expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path='src/models/User.ts', expect='{"exists": true}')
    e = errs(_spec(g1 + "\n" + g2))
    assert _has_error(e, "near-duplicate verification")


def test_near_duplicate_file_exists_different_check_not_dup():
    """Same path but different expect keys (content vs existence) → not a duplicate."""
    g1 = _goal("L1", "file_exists", path='src/models/User.ts', expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path='src/models/User.ts',
               expect='{"content_contains": "class"}')
    e = errs(_spec(g1 + "\n" + g2))
    assert not _has_error(e, "near-duplicate verification")


def test_near_duplicate_http_identical_is_dup():
    """Same method+url+headers+expect-keys → duplicate."""
    g1 = _goal("L1", "http", method="GET", url='http://x/v1/users', expect='{"status": 200}')
    g2 = _goal("L2", "http", method="GET", url='http://x/v1/users', expect='{"status": 200}')
    e = errs(_spec(g1 + "\n" + g2))
    assert _has_error(e, "near-duplicate verification")


def test_http_different_expect_keys_not_dup():
    """Same endpoint, same headers, but different expect keys → not a duplicate."""
    g1 = _goal("L1", "http", method="GET", url='http://x/v1/users', expect='{"status": 200}')
    g2 = _goal("L2", "http", method="GET", url='http://x/v1/users', expect='{"status": 200, "body_contains": "ok"}')
    e = errs(_spec(g1 + "\n" + g2))
    assert not _has_error(e, "near-duplicate verification")


def test_http_auth_vs_noauth_not_dup():
    """Same endpoint, same expect keys, but different headers (auth vs no-auth)
    → NOT a duplicate — these verify distinct authorization behaviour."""
    g1 = _goal(
        "L1", "http", method="GET", url='http://x/v1/sessions',
        headers='{"Authorization": "Bearer {test_token"}',
        expect='{"status": 200}',
    )
    g2 = _goal(
        "L2", "http", method="GET", url='http://x/v1/sessions',
        expect='{"status": 401}',
    )
    e = errs(_spec(g1 + "\n" + g2))
    assert not _has_error(e, "near-duplicate verification")


def test_http_url_placeholder_normalized_dup():
    """Two HTTP goals that share method+normalized-URL+headers+expect-keys
    ARE duplicates — `/users/{id}` and `/users/{otherId}` normalize to the
    same endpoint, so with identical headers and expect they are padding."""
    g1 = _goal("L1", "http", method="GET", url='http://x/v1/users/{id}', expect='{"status": 200}')
    g2 = _goal("L2", "http", method="GET", url='http://x/v1/users/{otherId}', expect='{"status": 200}')
    e = errs(_spec(g1 + "\n" + g2))
    assert _has_error(e, "near-duplicate verification")


# ---------- YAML parse errors ----------

def test_invalid_yaml():
    e = errs("this is not: : : yaml at all")
    assert len(e) >= 1  # at least one error


def test_non_dict_top_level():
    e = errs("- just\n- a\n- list")
    assert _has_error(e, "Top level must be a dictionary")


# ---------- existing data regression ----------

def test_gold_spec_forge_task_goals_are_well_formed():
    """The gold project-level example uses a project-level format that differs
    from the single-feature spec our pipeline produces.  This test documents
    the known divergences so they are not silently ignored:

    - `id` (not `task_id`) for tasks
    - `context` lives at the project level, not per-task
    - goal IDs are `L<n>-<n>` or `GV<n>` (global-verification uses GV prefix)
    - `global_goals_refs` can be a range string "G1–G19" (not a list of refs)

    Here we only validate the *goals* of each gold task — the structural
    per-task fields (task_id, summary, context) are skipped because the gold
    format puts them at the project level, which is correct for a project
    charter and not a defect.
    """
    import yaml
    gold = yaml.safe_load(
        open(pathlib.Path(__file__).resolve().parent.parent / "docs" / "spec-forge.yml").read()
    )
    goal_failures = []
    for task in gold.get("tasks", []):
        for g in task.get("local_goals", []):
            gid = g.get("id", "")
            # Accept L-prefixed or GV-prefixed IDs (project-level convention)
            if not re.match(r"^(L|GV)[A-Za-z0-9]+", gid):
                goal_failures.append(f"{task.get('id')}/{gid}: bad id format")
            ver = g.get("verification", {})
            vtype = ver.get("type")
            if vtype not in VALID_VERIFICATION_TYPES:
                goal_failures.append(f"{task.get('id')}/{gid}: bad type {vtype}")
            continue
    assert goal_failures == [], f"Gold goal format errors: {goal_failures}"


# ---------- NEW: enrichment fields validation ----------

def test_business_rules_validation():
    """business_rules must be list of dicts with name and formula."""
    # Valid
    spec = VALID_CLI.replace("context:", """business_rules:
  - name: "JWT Secret"
    formula: "256-bit random"
context:""")
    assert errs(spec) == []

    # Invalid: not a list
    spec_bad = VALID_CLI.replace("context:", """business_rules: "not a list"
context:""")
    e = errs(spec_bad)
    assert _has_error(e, "business_rules must be a list")

    # Invalid: missing name
    spec_bad2 = VALID_CLI.replace("context:", """business_rules:
  - formula: "test"
context:""")
    e2 = errs(spec_bad2)
    assert _has_error(e2, "missing or empty 'name'")

    # Invalid: missing formula
    spec_bad3 = VALID_CLI.replace("context:", """business_rules:
  - name: "test"
context:""")
    e3 = errs(spec_bad3)
    assert _has_error(e3, "missing or empty 'formula'")


def test_test_fixtures_validation():
    """test_fixtures must be list of dicts with name and setup_commands."""
    # Valid
    spec = VALID_CLI.replace("context:", """test_fixtures:
  - name: "seed-admin"
    setup_commands: ["python seed.py"]
context:""")
    assert errs(spec) == []

    # Invalid: missing setup_commands
    spec_bad = VALID_CLI.replace("context:", """test_fixtures:
  - name: "seed-admin"
context:""")
    e = errs(spec_bad)
    assert _has_error(e, "'setup_commands' must be a list")

    # Invalid: empty command
    spec_bad2 = VALID_CLI.replace("context:", """test_fixtures:
  - name: "seed-admin"
    setup_commands: [""]
context:""")
    e2 = errs(spec_bad2)
    assert _has_error(e2, "must be a non-empty string")


def test_environment_validation():
    """environment must have packages (list) and env_vars (dict)."""
    # Valid
    spec = VALID_CLI.replace("context:", """environment:
  packages: ["pyyaml>=6.0", "jsonschema>=4.0"]
  env_vars:
    JWT_SECRET: "secret"
context:""")
    assert errs(spec) == []

    # Invalid: packages not a list
    spec_bad = VALID_CLI.replace("context:", """environment:
  packages: "not a list"
  env_vars: {}
context:""")
    e = errs(spec_bad)
    assert _has_error(e, "environment.packages must be a list of strings")

    # Invalid: env_vars not a dict
    spec_bad2 = VALID_CLI.replace("context:", """environment:
  packages: []
  env_vars: "not a dict"
context:""")
    e2 = errs(spec_bad2)
    assert _has_error(e2, "environment.env_vars must be a dict")


def test_global_verification_validation():
    """global_verification must be non-empty list of strings."""
    # Valid
    valid_spec = VALID_CLI.replace("context:", """global_verification:
  - "pytest tests/"
  - "bandit -r src/"
context:""")
    assert errs(valid_spec) == []

    # Empty list
    invalid_spec = VALID_CLI.replace("context:", """global_verification: []
context:""")
    e = errs(invalid_spec)
    assert _has_error(e, "global_verification must be a non-empty list")

    # Not a list
    invalid_spec2 = VALID_CLI.replace("context:", """global_verification: "not a list"
context:""")
    e2 = errs(invalid_spec2)
    assert _has_error(e2, "global_verification must be a non-empty list")

    # Empty string in list
    invalid_spec3 = VALID_CLI.replace("context:", """global_verification:
  - "pytest tests/"
  - ""
context:""")
    e3 = errs(invalid_spec3)
    assert _has_error(e3, "global_verification[1]: must be a non-empty string")


def test_blueprint_required_for_create_goals():
    """CREATE goals must have blueprint >= 100 chars."""
    # Valid: CREATE goal with blueprint
    blueprint = "class User(Base):\n    id = Column(Integer, primary_key=True)\n    email = Column(String(255))\n    password_hash = Column(String(255))\n    def set_password(self, p):\n        self.password_hash = bcrypt.hashpw(p.encode(), bcrypt.gensalt(12))"
    g1 = _goal("L1", "create", blueprint=blueprint, verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path="src/models/User2.py", expect='{"exists": true}')
    assert errs(_spec(g1 + "\n" + g2)) == []

    # Invalid: CREATE goal without blueprint
    g1_bad = _goal("L1", "create", blueprint="", verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    e = errs(_spec(g1_bad + "\n" + g2))
    assert _has_error(e, "CREATE goals require a 'blueprint' with at least 100 characters")

    # Invalid: CREATE goal with short blueprint
    g1_short = _goal("L1", "create", blueprint="class User:\n    pass", verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    e2 = errs(_spec(g1_short + "\n" + g2))
    assert _has_error(e2, "CREATE goals require a 'blueprint' with at least 100 characters")

    # Valid: non-CREATE goal without blueprint
    g1_inspect = _goal("L1", "inspect", verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    assert errs(_spec(g1_inspect + "\n" + g2)) == []


def test_acceptance_criteria_validation():
    """acceptance_criteria if present must be list of dicts with test and steps."""
    # Valid acceptance_criteria
    blueprint = "x" * 150
    g1 = _goal("L1", "create", blueprint=blueprint, acceptance_criteria='[{"test": "User created", "steps": "POST /users -> 201"}]', verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    g2 = _goal("L2", "file_exists", path="src/models/User2.py", expect='{"exists": true}')
    assert errs(_spec(g1 + "\n" + g2)) == []

    # Invalid: not a list
    g1_bad = _goal("L1", "create", blueprint=blueprint, acceptance_criteria='{"test": "foo"}', verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    e = errs(_spec(g1_bad + "\n" + g2))
    assert _has_error(e, "acceptance_criteria must be a list")

    # Invalid: missing test
    g1_bad2 = _goal("L1", "create", blueprint=blueprint, acceptance_criteria='[{"steps": "foo"}]', verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    e2 = errs(_spec(g1_bad2 + "\n" + g2))
    assert _has_error(e2, "missing or empty 'test'")

    # Invalid: missing steps
    g1_bad3 = _goal("L1", "create", blueprint=blueprint, acceptance_criteria='[{"test": "foo"}]', verification_type="file_exists", path="src/models/User.py", expect='{"exists": true}')
    e3 = errs(_spec(g1_bad3 + "\n" + g2))
    assert _has_error(e3, "missing or empty 'steps'")


def test_new_optional_top_level_fields_accepted():
    """All new optional top-level fields should be accepted (not flagged as unknown)."""
    spec = VALID_CLI.replace("context:", """business_rules:
  - name: "test"
    formula: "test"
test_fixtures:
  - name: "test"
    setup_commands: ["cmd"]
environment:
  packages: ["pkg"]
  env_vars: {}
global_verification:
  - "cmd"
context:""")
    errors = errs(spec)
    # Should NOT have unknown top-level fields error
    unknown_errors = [e for e in errors if "Unknown top-level fields" in e]
    assert unknown_errors == [], f"New fields rejected: {unknown_errors}"