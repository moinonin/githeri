import yaml
import json
import re

VALID_GLOBAL_GOALS = {f"G{i}" for i in range(1, 20)}  # G1..G19
REQUIRED_TOP_LEVEL = ["task_id", "summary", "local_goals", "context"]
EXPRESSION_PATTERN = re.compile(r'[*+/%]\s*\d+|\d+\s*[*+/%]|def\s+|import\s+|\.\.\.')

def _contains_ref(schema):
    """Recursively check if schema contains a '$ref' key anywhere."""
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
    """Check if schema has a top-level 'definitions' key."""
    return isinstance(schema, dict) and "definitions" in schema

def validate_spec(yaml_str):
    errors = []
    try:
        spec = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        msg = str(e)
        if "alias" in msg:
            return [f"Invalid YAML: {msg}. Avoid expressions like \"A\" * 101. Use a literal string like 'AAAAAAAA... (101 times)' or a placeholder like {{101_a_string}}."]
        return [f"Invalid YAML: {e}"]

    if not isinstance(spec, dict):
        return ["Top level must be a dictionary"]

    # Required top-level fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in spec:
            errors.append(f"Missing required top-level field: {field}")

    # global_goals_refs
    if "global_goals_refs" in spec and spec["global_goals_refs"]:
        for ref in spec["global_goals_refs"]:
            if ref not in VALID_GLOBAL_GOALS:
                errors.append(f"Invalid global_goals_refs: '{ref}'. Must be one of {sorted(VALID_GLOBAL_GOALS)}")

    # local_goals
    goals = spec.get("local_goals", [])
    seen_ids = set()
    for i, goal in enumerate(goals):
        gid = goal.get("id")
        if not gid:
            errors.append(f"Goal {i} missing 'id'")
            continue
        # Accept any identifier that starts with L and contains at least one alphanumeric
        if not re.match(r'^L[A-Za-z0-9]+', gid):
            errors.append(f"Goal ID '{gid}' must start with 'L' followed by letters or digits (e.g., L1, LG1)")
        if gid in seen_ids:
            errors.append(f"Duplicate goal ID: {gid}")
        seen_ids.add(gid)

        # verification
        ver = goal.get("verification")
        if not ver:
            errors.append(f"Goal {gid}: missing verification")
            continue
        vtype = ver.get("type")
        if vtype == "http":
            body = ver.get("body", {})
            try:
                body_str = json.dumps(body)
                if EXPRESSION_PATTERN.search(body_str):
                    errors.append(f"Goal {gid}: body contains code-like expression, use literal strings")
            except Exception as e:
                errors.append(f"Goal {gid}: body is not valid JSON: {e}")

            schema = ver.get("expect", {}).get("json_schema")
            if schema:
                if _contains_ref(schema):
                    errors.append(
                        f"Goal {gid}: json_schema must be inline, no $ref. "
                        "Replace $ref with the full properties, e.g.: "
                        '{"type": "object", "properties": {"id": {"type": "string"}, ...}}'
                    )
                if _has_definitions(schema):
                    errors.append(f"Goal {gid}: json_schema must be inline, no 'definitions' block")

        elif vtype == "cli":
            if "command" not in ver:
                errors.append(f"Goal {gid}: CLI verification missing 'command'")
        elif vtype == "file_exists":
            if "path" not in ver:
                errors.append(f"Goal {gid}: file_exists verification missing 'path'")
        else:
            errors.append(f"Goal {gid}: unknown verification type '{vtype}'")

    return errors