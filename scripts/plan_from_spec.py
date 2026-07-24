"""Extract a single validated spec and emit it + the runbookprompt to stdout.

USAGE
    .venv/bin/python scripts/plan_from_spec.py <spec-path>
    .venv/bin/python scripts/plan_from_spec.py data/training_data.jsonl#0

The output is a self-contained prompt for a planning agent: the
runbookprompt.md content (with the ACCEPTED INPUT FORMATS section) followed
by the validated spec YAML.  An agent consuming this produces a
COMMAND_RUNWAY plan.

Exit codes:
    0  — spec valid, prompt emitted to stdout
    1  — spec failed validation (errors printed to stderr)
    2  — file not found or parse error
"""
import json
import pathlib
import re
import sys

# Make the validator importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validator import validate_spec  # noqa: E402


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "skills" / "runbookprompt.md"


def extract_spec(spec_ref: str) -> str:
    """Return the YAML spec string from either a .yaml file or a .jsonl#index.

    `spec_ref` may be:
      - A path to a .yaml file (relative or absolute)
      - A `path/to/file.jsonl#N` reference, extracting the Nth pair's spec_yaml
    """
    if "#" in spec_ref:
        path_part, _, idx_part = spec_ref.rpartition("#")
        try:
            idx = int(idx_part)
        except ValueError:
            print(f"ERROR: invalid index '{idx_part}' in {spec_ref}", file=sys.stderr)
            sys.exit(2)
        path = pathlib.Path(path_part)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(2)
        try:
            pairs = [
                json.loads(line)
                for line in path.read_text().strip().splitlines()
                if line.strip()
            ]
        except Exception as e:
            print(f"ERROR: could not parse JSONL: {e}", file=sys.stderr)
            sys.exit(2)
        if idx < 0 or idx >= len(pairs):
            print(
                f"ERROR: index {idx} out of range (file has {len(pairs)} pairs)",
                file=sys.stderr,
            )
            sys.exit(2)
        return pairs[idx].get("spec_yaml", "")

    path = pathlib.Path(spec_ref)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    return path.read_text()


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    spec_ref = sys.argv[1]
    spec_yaml = extract_spec(spec_ref)

    # 1) Validate before emitting — no plan without a valid spec
    errors = validate_spec(spec_yaml)
    if errors:
        print(f"❌ Spec failed validation ({len(errors)} errors):", file=sys.stderr)
        for err in errors[:8]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 8:
            print(f"  ... and {len(errors) - 8} more", file=sys.stderr)
        sys.exit(1)

    # 2) Load the runbookprompt
    if not PROMPT_PATH.exists():
        print(f"ERROR: runbookprompt not found at {PROMPT_PATH}", file=sys.stderr)
        sys.exit(2)
    prompt_text = PROMPT_PATH.read_text()

    # 3) Emit the combined prompt + spec to stdout
    print(prompt_text)
    print()
    print("---")
    print()
    print("## SUPPLIED SPECIFICATION (Format B — Structured YAML)")
    print()
    print("```yaml")
    print(spec_yaml.strip())
    print("```")
    print()
    print(
        "Now produce the COMMAND_RUNWAY plan for the spec above, "
        "following the Field to Plan-Section Mapping in the ACCEPTED INPUT "
        "FORMATS section."
    )


if __name__ == "__main__":
    main()
