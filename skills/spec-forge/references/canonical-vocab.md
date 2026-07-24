# Canonical Spec Vocabulary

The single source of truth for the spec format Spec-Forge produces and the
COMMAND_RUNWAY skill consumes. Kept in sync with `scripts/validator.py` —
if you change one, change the other.

## Top-Level Shape (single-feature spec)

Required top-level fields, in this order:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `task_id` | string | yes | non-empty |
| `summary` | string | yes | |
| `depends_on` | list of strings | no | each entry is one dependency |
| `local_goals` | list | yes | minimum 2 goals |
| `global_goals_refs` | list of strings | no | each must be in `G1..G19` |
| `context` | object | yes | must include `language`, `framework`, `orm`, `test_framework` |

Unknown top-level fields are rejected.

## Verification Types

Each `local_goals[].verification.type` must be one of exactly four values.

### `http`

Required fields (besides `type`): `method`, `url`.
Required `expect` key: `status`.
Valid `expect` keys: `status`, `body_regex`, `body_contains`, `json_schema`, `headers_contain`.

Placement:
- `headers` (REQUEST headers) is a SIBLING of `expect`, under `verification`.
  Never inside `expect`.
- `headers_contain` (RESPONSE header assertions) lives INSIDE `expect` as a
  map of header-name to required-substring.
- `body` (request body) is a SIBLING of `expect`, under `verification`.
- `json_schema` is inline — no `$ref`, no `definitions`.
- Body values must be valid JSON; no expressions like `"a" * 101`. Use literal
  strings or placeholders like `{{101_a_string}}`.
- Regex patterns inside string values MUST use single quotes (YAML double
  quotes reject `\d`, `\w`, `\s`). The validator's pre-processor will
  auto-fix double-quoted regex values to single-quoted form, but emitting
  them correctly the first time avoids the retry.

### `cli`

Required fields: `command` (must be ≥3 chars — trivial commands rejected).
Required `expect` key: `exit_code`.
Valid `expect` keys: `exit_code`, `stdout_regex`, `stdout_contains`, `stdout_lines_min`.

### `file_exists`

Required fields: `path`.
Required `expect` keys: at least one of `content`, `content_contains`,
`content_not_contains`, `exists`.
Valid `expect` keys: `content`, `content_contains`, `content_not_contains`, `exists`.

Do NOT use `exit_code` on a `file_exists` goal — use `content_contains` instead.

### `manual`

Required fields: `description`.
Never include an `expect` block — the description IS the verification.

## Quality Gates

- Minimum 2 `local_goals` per spec. 1 is never enough.
- No duplicate goal IDs. Each ID must match `^L[A-Za-z0-9]+` (e.g. `L1`,
  `L2A`).
- No near-duplicate verifications:
  - `http`: same `method` + same `url` (after normalizing `{placeholder}` →
    `{}`) + same `headers` + same `expect` keys → near-duplicate. Auth-vs-
    noauth (different headers) or different expect keys ARE distinct.
  - `file_exists`: same `path` + same `expect` keys → near-duplicate.
    Different expect keys on the same path ARE distinct.
  - `cli`: same `command` → near-duplicate.
- No unknown top-level fields.
- No `$ref` or `definitions` in `json_schema`.
- No code-like expressions in `body`.

## YAML Pre-Processor

`validator.preprocess_yaml()` runs before `yaml.safe_load()`. It detects
double-quoted YAML scalars containing backslash escapes that are not valid
YAML escapes (regex character classes like `\d`, `\w`, `\s`, `\.`, `\[`,
`]`, `(`, `)`, `*`, `?`, `|`), and converts the offending value to
single-quoted form (single-quoted YAML treats backslash literally). Valid
YAML escapes (`\n`, `\t`, `\\`, `\"`, `\xNN`, `\uNNNN`) are left untouched.

This allows specs to carry regex patterns (e.g. `Retry-After: '\d+'`) without
YAML parse failures.

## Project-Level Charter Format (different, not validated here)

A separate project-level charter format exists (`docs/spec-forge.yml`) with
top-level keys `spec_version`, `project`, `based_on`, `global_goals`,
`context` (project-wide), `tasks` (array). Each task uses `id` (not
`task_id`), has no per-task `context`, and may use `GV1..GV14` for
global-verification goals and range strings like `"G1–G19"` in
`global_goals_refs`. This format is the gold PROJECT-level reference, not the
SINGLE-FEATURE training target. The validator enforces the single-feature
format only; do not push project charters through it.
