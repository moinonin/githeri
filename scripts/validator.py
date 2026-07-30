import yaml
import json
import re

# -------------------- YAML OUTPUT SANITIZER --------------------
# Raw LLM output (especially from `ollama run`) often contains ANSI escape
# sequences and terminal control characters (e.g. \x1b[1D, \x1b[K, \x1b[3D)
# that break yaml.safe_load().  This sanitizer strips them BEFORE parsing.
#
# Verified against the real Ollama output in testyaml.yml which contained
# sequences like \x1b[1D\x1b[K (cursor left + erase line) mid-YAML.

# Match ANSI escape sequences: \x1b[ ... letter (CSI sequences)
_ANSI_CSI_PATTERN = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')

# Match other common control sequences that Ollama/Curses emit
# \x1b[K  = erase line (already covered by CSI above, but be explicit)
# \r      = carriage return (not a newline; strip)
# \x08    = backspace
# \x00-\x08, \x0b, \x0c, \x0e-\x1f = other C0 control chars (keep \t \n)
_OTHER_CONTROL_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\r]')


def clean_yaml_output(raw: str) -> str:
    """Strip ANSI escape sequences and terminal control characters from raw LLM output.

    Called before yaml.safe_load() in both validate_spec() and
    run_pipeline.py's extract_yaml().  Handles:
      - CSI sequences: \x1b[1D, \x1b[K, \x1b[3D, \x1b[12D, etc.
      - Carriage returns, backspaces, other C0 control chars
      - Preserves tabs (\x09) and newlines (\x0a)
      - Joins orphaned newlines left by CSI removal (e.g. "p\npush" -> "ppush"
        when the original was "p\x1b[1D\x1b[K\npush" meaning the cursor went
        back and the word continued on the same logical line)

    Returns the cleaned string.  Does NOT alter YAML semantics — only
    removes non-printable injection from terminal rendering.
    """
    if not raw:
        return raw

    # Phase 1: Remove the ANSI CSI sequences (e.g. \x1b[1D\x1b[K).
    # These are "cursor left + erase line" — the model was typing, backspacing,
    # and retyping.  After removing them, the text fragments that were on the
    # same logical line are now separated only by a newline, so we join them.
    parts = _ANSI_CSI_PATTERN.split(raw)
    if len(parts) > 1:
        # The fragments separated by CSI removal should be joined (no newline)
        # because the cursor moved back on the same line, not to a new line.
        # But if the raw text had real newlines BEFORE a CSI sequence, those
        # are preserved in the split fragments themselves.
        # Strategy: join fragments that were CSI-separated, then clean newlines.
        joined = ''.join(parts)
    else:
        joined = raw

    # Phase 2: Remove remaining C0 control chars (keep \t and \n)
    cleaned = _OTHER_CONTROL_PATTERN.sub('', joined)

    return cleaned

# -------------------- CANONICAL VOCABULARY --------------------
# The single source of truth for assertion keys, shared by the validator,
# the generation prompt, and the COMMAND_RUNWAY runbook template.
#
# Verified against:
#   - docs/spec-forge.yml  (the gold project-level example)
#   - skills/runbook.md    (the Layer 3 template's "assertion shapes" section)
#
# Keep these three in sync. If you add a key here, also add it to the
# runbook template's assertion-shapes list and the few-shot example.
VALID_VERIFICATION_TYPES = {"http", "cli", "file_exists", "manual"}

VALID_GLOBAL_GOALS = {f"G{i}" for i in range(1, 20)}  # G1..G19

REQUIRED_TOP_LEVEL = ["task_id", "summary", "local_goals", "context"]
OPTIONAL_TOP_LEVEL = {"depends_on", "global_goals_refs",
                      "business_rules", "test_fixtures",
                      "environment", "global_verification"}

# Per-type required verification fields (besides `type` itself)
REQUIRED_VERIFICATION_FIELDS = {
    "http": ["method", "url"],
    "cli": ["command"],
    "file_exists": ["path"],
    "manual": [],  # only needs `description` (checked separately)
}

# Per-type valid `expect` keys.  Unknown keys are rejected.
#   cli:           exit_code, stdout_regex, stdout_contains, stdout_lines_min
#   http:          status, body_regex, body_contains, json_schema, headers_contain
#   file_exists:   content, content_contains, content_not_contains, exists
#   manual:        (no expect block — the description IS the check)
VALID_EXPECT_KEYS = {
    "http": {"status", "body_regex", "body_contains", "json_schema", "headers_contain"},
    "cli": {"exit_code", "stdout_regex", "stdout_contains", "stdout_lines_min"},
    "file_exists": {"content", "content_contains", "content_not_contains", "exists"},
    "manual": set(),
}

# Per-type required `expect` keys — a verification with no assertion is vacuous.
REQUIRED_EXPECT_KEYS = {
    "http": {"status"},
    "cli": {"exit_code"},
    "file_exists": set(),  # any one of the content/exists keys suffices (checked below)
    "manual": set(),
}

# file_exists requires at least one of these to be meaningful
FILE_EXISTS_MIN_ONE = {"content", "content_contains", "content_not_contains", "exists"}

# Minimum quality thresholds
MIN_LOCAL_GOALS = 2
MIN_NONTRIVIAL_CMD_LEN = 3  # reject " ", "a", or empty strings

# Blueprint minimum length for CREATE goals
MIN_BLUEPRINT_LENGTH = 100

# New optional top-level fields (IMPROVE_SPEC enrichment)
OPTIONAL_TOP_LEVEL = {"depends_on", "global_goals_refs",
                      "business_rules", "test_fixtures",
                      "environment", "global_verification"}

EXPRESSION_PATTERN = re.compile(r'[*+/%]\s*\d+|\d+\s*[*+/%]|def\s+|import\s+|\.\.\.')


# -------------------- HELPERS --------------------
def _contains_ref(schema):
    """Recursively check if a json_schema contains a '$ref' key anywhere."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            return True
        for v in schema.values():
            if _contains_ref(v):
                return True
    elif isinstance(schema, list):
        for item in schema:
            if _contains_ref(item):
                return True
    return False


def _has_definitions(schema):
    """Check if a json_schema has a top-level 'definitions' key."""
    return isinstance(schema, dict) and "definitions" in schema


def _near_duplicate(a, b):
    """Return True if two verification blocks are near-identical.

    Same type, same target (path/url/command), and same expect keys → duplicate.
    Differing headers, body, or expect values are NOT enough to differentiate
    if the expect keys are identical (that's just asserting the same check
    twice with minor variation).  However, different expect keys (e.g.,
    exit_code vs stdout_contains) or different headers (auth vs no-auth)
    indicate genuinely distinct checks, so those are not duplicates.

    Exception: for http, two goals that differ ONLY by headers (e.g. auth vs
    no-auth on the same endpoint) are distinct aspects, not duplicates.
    """
    if a.get("type") != b.get("type"):
        return False
    t = a.get("type")
    if t == "file_exists":
        # Same path → check if the expectations are also identical
        if a.get("path", "") != b.get("path", ""):
            return False
        ea = a.get("expect") or {}
        eb = b.get("expect") or {}
        if not isinstance(ea, dict) or not isinstance(eb, dict):
            return False
        return set(ea.keys()) == set(eb.keys())
    if t == "http":
        # Normalize path-param placeholders for URL comparison
        ua = re.sub(r"\{[^}]+\}", "{}", a.get("url", ""))
        ub = re.sub(r"\{[^}]+\}", "{}", b.get("url", ""))
        if ua != ub or a.get("method", "") != b.get("method", ""):
            return False
        # Same endpoint — only a near-duplicate if the headers and expect
        # keys are also identical.  Auth vs no-auth (different headers) is a
        # legitimate distinct check, not padding.
        if a.get("headers", {}) != b.get("headers", {}):
            return False
        ea = a.get("expect") or {}
        eb = b.get("expect") or {}
        if not isinstance(ea, dict) or not isinstance(eb, dict):
            return False
        return set(ea.keys()) == set(eb.keys())
    if t == "cli":
        return a.get("command", "") == b.get("command", "")
    return False


# -------------------- YAML PRE-PROCESSOR --------------------
# The model often emits regex patterns inside double-quoted YAML scalars
# (e.g.  Retry-After: "\d+").  YAML double-quoted scalars reject backslash
# escapes that are not in the YAML spec's valid set (\n, \t, \", \\, etc.),
# so a regex like \d+ causes a parse error before the validator can even
# run.  This pre-processor detects such offending double-quoted scalars and
# converts them to single-quoted form (single-quoted YAML treats backslash
# literally — no escaping).  Run BEFORE yaml.safe_load.

# Characters valid after a backslash inside a YAML double-quoted scalar.
# Source: YAML 1.2 spec, section 7.4.2 (Double-Quoted Style).
_YAML_DOUBLE_QUOTED_ESCAPES = set("0abtnvfreNLP\"\\/ xueU ")


def _has_invalid_backslash_escape(s):
    """Return True if the string s contains a backslash followed by a char
    that is NOT a valid YAML double-quoted escape."""
    i = 0
    while i < len(s) - 1:
        if s[i] == "\\":
            nxt = s[i + 1]
            # Hex/unicode escapes: \xNN, \uNNNN, \UNNNNNNNN
            if nxt in ("x", "u", "U"):
                return False  # the rest of the escape is valid (digits/letters)
            if nxt not in _YAML_DOUBLE_QUOTED_ESCAPES:
                return True
            i += 2
        else:
            i += 1
    return False


def preprocess_yaml(yaml_str):
    """Convert double-quoted YAML scalars containing invalid backslash escapes
    (e.g. regex patterns) to single-quoted form so they parse cleanly.

    Operates line-by-line; only modifies the specific offending string value,
    never rewrites all quotes.  Returns the (possibly modified) YAML string.
    """
    import re as _re

    fixed_lines = []
    fixes_applied = 0

    # Pattern: a double-quoted string value on a YAML line.
    #   key: "value with \d+ inside"
    # Captures everything between the FIRST pair of double quotes that contains
    # a backslash escape.  Conservative — only matches simple inline scalars.
    dq_pattern = _re.compile(r':\s*"([^"\\]*(?:\\.[^"\\]*)*)"')

    for line in yaml_str.splitlines():
        m = dq_pattern.search(line)
        if m:
            quoted_value = m.group(1)
            if _has_invalid_backslash_escape(quoted_value):
                # Convert this value to single-quoted form.
                # In single-quoted YAML, the only special char is the single
                # quote itself — escape it by doubling ('' → ').
                single_quoted_value = quoted_value.replace("'", "''")
                new_line = line[: m.start()] + ": '" + single_quoted_value + "'" + line[m.end():]
                fixed_lines.append(new_line)
                fixes_applied += 1
                continue
        fixed_lines.append(line)

    result = "\n".join(fixed_lines)
    # Preserve a trailing newline if the original had one (splitlines() strips it).
    if yaml_str.endswith("\n"):
        result += "\n"
    return result, fixes_applied


# -------------------- MAIN VALIDATOR --------------------
def validate_spec(yaml_str):
    """Validate a single-feature YAML spec string.

    Returns a list of error strings.  Empty list == valid.
    """
    # Sanitize: strip ANSI escape sequences and terminal control chars
    # that raw LLM output (especially `ollama run`) injects into the YAML.
    yaml_str = clean_yaml_output(yaml_str)

    # Pre-process: fix double-quoted scalars with invalid regex escapes
    # before attempting to parse.
    yaml_str, _fixes = preprocess_yaml(yaml_str)

    errors = []
    try:
        spec = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        msg = str(e)
        if "alias" in msg:
            return [
                f"Invalid YAML: {msg}. Avoid expressions like \"A\" * 101. "
                "Use a literal string like 'AAAA... (101 times)' or a placeholder "
                "like {{101_a_string}}."
            ]
        return [f"Invalid YAML: {e}"]

    if not isinstance(spec, dict):
        return ["Top level must be a dictionary"]

    # ---- Required + optional top-level fields ----
    for field in REQUIRED_TOP_LEVEL:
        if field not in spec:
            errors.append(f"Missing required top-level field: {field}")
    unknown_toplevel = set(spec.keys()) - set(REQUIRED_TOP_LEVEL) - OPTIONAL_TOP_LEVEL
    if unknown_toplevel:
        errors.append(
            f"Unknown top-level fields: {sorted(unknown_toplevel)}. "
            f"Allowed: {sorted(set(REQUIRED_TOP_LEVEL) | OPTIONAL_TOP_LEVEL)}"
        )

    # ---- task_id must be a non-empty string ----
    tid = spec.get("task_id")
    if tid is not None and not (isinstance(tid, str) and tid.strip()):
        errors.append("task_id must be a non-empty string")

    # ---- global_goals_refs ----
    if "global_goals_refs" in spec and spec["global_goals_refs"]:
        for ref in spec["global_goals_refs"]:
            # Handle both string refs ("G5") and dict refs ({"goal": "G5", ...})
            ref_str = ref if isinstance(ref, str) else ref.get("goal") if isinstance(ref, dict) else None
            if not ref_str or ref_str not in VALID_GLOBAL_GOALS:
                errors.append(
                    f"Invalid global_goals_refs: '{ref}'. "
                    f"Must be one of {sorted(VALID_GLOBAL_GOALS)} or a dict with 'goal' field"
                )

    # ---- local_goals ----
    goals = spec.get("local_goals", [])
    if not isinstance(goals, list):
        errors.append("local_goals must be a list")
        return errors  # can't continue — iteration below assumes list

    if len(goals) < MIN_LOCAL_GOALS:
        errors.append(
            f"local_goals must have at least {MIN_LOCAL_GOALS} goals "
            f"(found {len(goals)})"
        )

    seen_ids = set()
    verifications = []  # collect for dedup pass
    for i, goal in enumerate(goals):
        gid = goal.get("id") if isinstance(goal, dict) else None
        if not gid:
            errors.append(f"Goal {i}: missing 'id'")
            continue
        if not re.match(r"^L[A-Za-z0-9]+", gid):
            errors.append(
                f"Goal '{gid}': id must start with 'L' followed by letters/digits "
                f"(e.g., L1, L2A)"
            )
        if gid in seen_ids:
            errors.append(f"Duplicate goal ID: {gid}")
        seen_ids.add(gid)

        # ---- verification block ----
        ver = goal.get("verification")
        if not isinstance(ver, dict):
            errors.append(f"Goal {gid}: missing or non-dict 'verification'")
            continue

        vtype = ver.get("type")
        if vtype not in VALID_VERIFICATION_TYPES:
            errors.append(
                f"Goal {gid}: unknown verification type '{vtype}'. "
                f"Must be one of {sorted(VALID_VERIFICATION_TYPES)}"
            )
            continue  # can't do type-specific checks

        # ---- required fields per type ----
        req_fields = REQUIRED_VERIFICATION_FIELDS.get(vtype, [])
        for rf in req_fields:
            val = ver.get(rf)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"Goal {gid}: {vtype} verification missing '{rf}'")

        # ---- manual type: needs a description (not under expect) ----
        if vtype == "manual":
            if not ver.get("description", "").strip():
                errors.append(
                    f"Goal {gid}: manual verification requires a 'description'"
                )
            continue  # manual verification is done — no expect block to check

        # ---- cli command non-triviality ----
        if vtype == "cli":
            cmd = ver.get("command", "")
            if cmd and len(cmd.strip()) < MIN_NONTRIVIAL_CMD_LEN:
                errors.append(
                    f"Goal {gid}: cli command is trivial ({len(cmd.strip())} chars) "
                    f"— must be a real command"
                )

        # ---- http body validation ----
        if vtype == "http":
            body = ver.get("body", {})
            try:
                body_str = json.dumps(body)
                if EXPRESSION_PATTERN.search(body_str):
                    errors.append(
                        f"Goal {gid}: body contains code-like expression, "
                        "use literal strings"
                    )
            except Exception as e:
                errors.append(f"Goal {gid}: body is not valid JSON: {e}")

            schema = None
            expect_for_schema = ver.get("expect", {})
            if isinstance(expect_for_schema, dict):
                schema = expect_for_schema.get("json_schema")
            if schema:
                if _contains_ref(schema):
                    errors.append(
                        f"Goal {gid}: json_schema must be inline, no $ref. "
                        "Replace $ref with the full properties, e.g.: "
                        '{"type": "object", "properties": {"id": {"type": "string"}}}'
                    )
                if _has_definitions(schema):
                    errors.append(
                        f"Goal {gid}: json_schema must be inline, no 'definitions'"
                    )

        # ---- expect block: key vocabulary ----
        expect = ver.get("expect", {})
        if expect is None:
            expect = {}
        if not isinstance(expect, dict):
            errors.append(f"Goal {gid}: 'expect' must be a dict, got {type(expect).__name__}")
            continue
        valid_keys = VALID_EXPECT_KEYS.get(vtype, set())
        unknown_expect = set(expect.keys()) - valid_keys
        if unknown_expect:
            errors.append(
                f"Goal {gid}: unknown expect keys {sorted(unknown_expect)} "
                f"for type '{vtype}'. Valid: {sorted(valid_keys) or '(none)'}"
            )

        # ---- required expect keys ----
        req_expect = REQUIRED_EXPECT_KEYS.get(vtype, set())
        for rk in req_expect:
            if rk not in expect:
                errors.append(
                    f"Goal {gid}: {vtype} verification requires expect.{rk}"
                )

        # ---- file_exists needs at least one meaningful check ----
        if vtype == "file_exists":
            present = set(expect.keys()) & FILE_EXISTS_MIN_ONE
            if not present:
                errors.append(
                    f"Goal {gid}: file_exists verification needs at least one of "
                    f"expect.{sorted(FILE_EXISTS_MIN_ONE)} (found none)"
                )

        # stash for dedup
        verifications.append((gid, ver))

    # ---- dedup pass: flag near-identical verifications ----
    for i in range(len(verifications)):
        for j in range(i + 1, len(verifications)):
            id_i, v_i = verifications[i]
            id_j, v_j = verifications[j]
            if _near_duplicate(v_i, v_j):
                errors.append(
                    f"Goals {id_i} and {id_j}: near-duplicate verification "
                    f"(type={v_i.get('type')}, same target). "
                    "Each goal should verify a distinct aspect."
                )

    # ---- New IMPROVE_SPEC enrichment fields validation ----
    # business_rules: list of dicts with 'name' and 'formula' (non-empty strings)
    if "business_rules" in spec:
        rules = spec["business_rules"]
        if not isinstance(rules, list):
            errors.append("business_rules must be a list")
        else:
            for idx, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    errors.append(f"business_rules[{idx}]: must be a dict")
                    continue
                if not rule.get("name") or not isinstance(rule.get("name"), str) or not rule["name"].strip():
                    errors.append(f"business_rules[{idx}]: missing or empty 'name'")
                if not rule.get("formula") or not isinstance(rule.get("formula"), str) or not rule["formula"].strip():
                    errors.append(f"business_rules[{idx}]: missing or empty 'formula'")

    # test_fixtures: list of dicts with 'name' and 'setup_commands' (list of strings)
    if "test_fixtures" in spec:
        fixtures = spec["test_fixtures"]
        if not isinstance(fixtures, list):
            errors.append("test_fixtures must be a list")
        else:
            for idx, fix in enumerate(fixtures):
                if not isinstance(fix, dict):
                    errors.append(f"test_fixtures[{idx}]: must be a dict")
                    continue
                if not fix.get("name") or not isinstance(fix.get("name"), str) or not fix["name"].strip():
                    errors.append(f"test_fixtures[{idx}]: missing or empty 'name'")
                setup_cmds = fix.get("setup_commands")
                if not isinstance(setup_cmds, list):
                    errors.append(f"test_fixtures[{idx}]: 'setup_commands' must be a list")
                else:
                    for cmd_idx, cmd in enumerate(setup_cmds):
                        if not isinstance(cmd, str) or not cmd.strip():
                            errors.append(f"test_fixtures[{idx}].setup_commands[{cmd_idx}]: must be a non-empty string")

    # environment: dict with 'packages' (list of strings) and 'env_vars' (dict)
    if "environment" in spec:
        env = spec["environment"]
        if not isinstance(env, dict):
            errors.append("environment must be a dict")
        else:
            packages = env.get("packages")
            if packages is not None and not isinstance(packages, list):
                errors.append("environment.packages must be a list of strings")
            elif packages:
                for idx, pkg in enumerate(packages):
                    if not isinstance(pkg, str) or not pkg.strip():
                        errors.append(f"environment.packages[{idx}]: must be a non-empty string")
            env_vars = env.get("env_vars")
            if env_vars is not None and not isinstance(env_vars, dict):
                errors.append("environment.env_vars must be a dict")

    # global_verification: non-empty list of strings (commands)
    if "global_verification" in spec:
        gv = spec["global_verification"]
        if not isinstance(gv, list) or len(gv) == 0:
            errors.append("global_verification must be a non-empty list of command strings")
        else:
            for idx, cmd in enumerate(gv):
                if not isinstance(cmd, str) or not cmd.strip():
                    errors.append(f"global_verification[{idx}]: must be a non-empty string")

    # Blueprint validation for CREATE goals
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        if goal.get("type") == "create":
            blueprint = goal.get("blueprint", "")
            if not blueprint or not isinstance(blueprint, str) or len(blueprint.strip()) < MIN_BLUEPRINT_LENGTH:
                errors.append(
                    f"Goal {goal.get('id', '?')}: CREATE goals require a 'blueprint' "
                    f"with at least {MIN_BLUEPRINT_LENGTH} characters of code outline"
                )
        # Acceptance criteria validation (optional but if present must be well-formed)
        if "acceptance_criteria" in goal:
            ac = goal["acceptance_criteria"]
            if not isinstance(ac, list):
                errors.append(f"Goal {goal.get('id')}: acceptance_criteria must be a list")
            else:
                for idx, criterion in enumerate(ac):
                    if not isinstance(criterion, dict):
                        errors.append(f"Goal {goal.get('id')}.acceptance_criteria[{idx}]: must be a dict")
                        continue
                    if not criterion.get("test") or not isinstance(criterion.get("test"), str) or not criterion["test"].strip():
                        errors.append(f"Goal {goal.get('id')}.acceptance_criteria[{idx}]: missing or empty 'test'")
                    if not criterion.get("steps") or not isinstance(criterion.get("steps"), str) or not criterion["steps"].strip():
                        errors.append(f"Goal {goal.get('id')}.acceptance_criteria[{idx}]: missing or empty 'steps'")

    return errors
