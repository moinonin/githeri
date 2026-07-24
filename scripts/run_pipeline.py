import json
import sys
import re
import requests
import yaml
import pathlib
from prompt_generator import generate_prompt
from validator import validate_spec
from runbook_scorer import runbook_score

# -------------------- CONFIG --------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b-instruct"
MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILS = 10
OUTPUT_FILE = "data/training_data.jsonl"

SKILL_DIR = pathlib.Path("skills/command-runway-pattern")

def load_skill_context():
    """Read key skill files and return a combined context string."""
    files = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "references" / "command-runway-pattern.md",
        SKILL_DIR / "templates" / "runbook-template.md",
        SKILL_DIR / "templates" / "stage-template.md",
    ]
    parts = []
    for f in files:
        if f.exists():
            parts.append(f"--- {f.name} ---\n{f.read_text()}\n")
    return "\n".join(parts)

SKILL_CONTEXT = load_skill_context()

FEW_SHOT_EXAMPLE = """---
FEW-SHOT EXAMPLE ---
Request: "Implement the Session lifecycle API: create, get, update, close, and expire sessions. Enforce the session state machine. Add auth middleware (JWT). Generate the OpenAPI spec. Integrate with the evidence pipeline when evidence is submitted."

Spec YAML:
```yaml
task_id: session-lifecycle-api
summary: "REST API for session lifecycle with state machine enforcement and evidence integration"
depends_on: ["stage-1-core-models", "stage-2-pipeline"]
local_goals:
  - id: L1
    description: "INSPECT: check existing session model and routes before adding endpoints"
    verification:
      type: file_exists
      path: "src/models/Session.ts"
      expect:
        exists: true
  - id: L2
    description: "INSPECT: check existing API routes structure"
    verification:
      type: cli
      command: "cat apps/api/src/routes/sessions.ts"
      expect:
        exit_code: 0
  - id: L3
    description: "CREATE: add POST /v1/sessions endpoint and session model extensions"
    verification:
      type: cli
      command: "pnpm build --filter=@verified-attention/api"
      expect:
        exit_code: 0
  - id: L4
    description: "CREATE: add GET/PATCH/POST endpoints for session lifecycle"
    verification:
      type: cli
      command: "pnpm build --filter=@verified-attention/api"
      expect:
        exit_code: 0
  - id: L5
    description: "VERIFY: POST /v1/sessions creates a session and returns sessionId"
    verification:
      type: http
      method: POST
      url: http://localhost:3000/v1/sessions
      headers:
        Authorization: "Bearer {test_token}"
      body:
        contentId: "test-content"
      expect:
        status: 201
        json_schema:
          type: object
          properties:
            sessionId: { type: string }
          required: [sessionId]
  - id: L6
    description: "VERIFY: GET /v1/sessions/:id returns the session with evidence and claims"
    verification:
      type: http
      method: GET
      url: http://localhost:3000/v1/sessions/{session_id}
      headers:
        Authorization: "Bearer {test_token}"
      expect:
        status: 200
        json_schema:
          type: object
          properties:
            sessionId: { type: string }
            state: { type: string }
            evidence: { type: array }
            claims: { type: array }
          required: [sessionId, state]
  - id: L7
    description: "VERIFY: Session state machine rejects invalid transitions"
    verification:
      type: cli
      command: "pnpm test --filter=@verified-attention/api -- --testPathPattern=session-state-machine"
      expect:
        exit_code: 0
  - id: L8
    description: "VERIFY: OpenAPI spec is valid and contains session endpoints"
    verification:
      type: cli
      command: "npx @redocly/cli lint apps/api/openapi.yaml && grep '/v1/sessions' apps/api/openapi.yaml"
      expect:
        exit_code: 0
global_goals_refs: ["G5", "G13"]
context:
  language: TypeScript
  framework: Express
  orm: Prisma
  test_framework: Vitest
```
"""
SYSTEM_PROMPT = f"""
You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.
Output ONLY a YAML document. No code, no commentary.

--- PROJECT SKILL (Command Runway Pattern) ---
{SKILL_CONTEXT}

--- YAML SPEC FORMAT ---
The YAML must contain these exact top-level fields, in this order:
task_id: string
summary: string
depends_on: list of strings (optional)
local_goals: list of objects with id, description, verification
global_goals_refs: list of strings (optional, must reference existing global goals G1-G19)
context: object with keys: language, framework, orm, test_framework

For each local_goal, verification must follow these rules:
- type: http | cli | file_exists | manual
- MINIMUM 2 local_goals per spec (more is fine; 1 is never enough).
- Every goal must verify a DISTINCT aspect.  Do NOT pad with near-duplicate
  goals that hit the same endpoint or same file path twice.  If two goals
  share the same (type, method, url) or (type, path) or (type, command),
  they are near-duplicates and the spec will be rejected.

Canonical `expect` keys (use ONLY these — unknown keys are rejected):
  http:        status (required), body_regex, body_contains, json_schema, headers_contain
  cli:         exit_code (required), stdout_regex, stdout_contains, stdout_lines_min
  file_exists: path is required; expect must contain at least one of content,
               content_contains, content_not_contains, exists
  manual:      description (required); never include an `expect` block

For http:
  - Provide method (GET/POST/PATCH/PUT/DELETE), url, and expect.status.
  - REQUEST headers (optional) live BESIDE expect, under verification, not inside expect.
    e.g.:
        verification:
          type: http
          method: GET
          url: http://localhost:3000/api
          headers:                       # <- request headers, SIBLING of expect
            Authorization: "Bearer {{{{test_token}}}}"
          expect:
            status: 200
  - RESPONSE header assertions go INSIDE expect as `headers_contain`, a map of
    header-name to required-substring.  This is the ONLY correct place to assert
    response headers; never put `headers` inside expect.
    e.g.:
        expect:
          status: 429
          headers_contain:               # <- response-header checks, INSIDE expect
            Retry-After: "\\d+"          # <- single-quoted YAML so backslash is literal
  - body (optional) lives beside expect under verification, not inside expect.
  - All body values must be valid JSON (quoted strings, no expressions like "a"*101).
    Use literal strings or placeholders like {{{{101_a_string}}}}.
  - json_schema must be inline; do NOT use $ref or definitions blocks.
  - Placeholders for dynamic values like {{{{test_user_id}}}}, {{{{admin_token}}}}, {{{{user_token}}}} are allowed.
  - Regex patterns inside string values MUST use single quotes (e.g. '\\d+') —
    YAML double quotes reject backslash escapes like \d, \w, \s.

For cli:
  - Provide a real command (at least 3 chars). An empty or near-empty command is rejected.
  - Provide expect.exit_code.  Optionally use stdout_contains / stdout_regex / stdout_lines_min.

For file_exists:
  - Provide path.  Provide at least one of the content/exists checks under expect.
  - Do NOT use exit_code on a file_exists goal — use content_contains instead.

For manual:
  - Provide description (the description IS the verification; no expect block).

Context: TypeScript, Express, Prisma, Vitest. Auth middleware handles JWT.
Context may also include language, framework, orm, test_framework keys.
Global goals available: G1..G19 (refer to project charter).

--- COMMAND_RUNWAY STRUCTURE (MANDATORY) ---
Every spec MUST include at least one goal of each type in this order:
1. INSPECT: file_exists verification OR CLI read-only command (cat, head, ls, test -f)
2. CREATE/MODIFY: CLI build/install/migrate/generate command (pnpm build, npm run build, prisma migrate, etc.)
3. VERIFY: HTTP endpoint check OR CLI test/lint/check command

Goals should follow this progression: Inspect → Create/Modify → Verify
{FEW_SHOT_EXAMPLE}
Now produce ONLY the YAML specification for the following feature request.
"""

# -------------------- HELPERS --------------------
def extract_yaml(text: str) -> str:
    """Pull YAML content from markdown fences or plain text."""
    # Try ```yaml ... ``` fences
    match = re.search(r"```yaml\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no fences, look for first line starting with a YAML key
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r'^\w+:', line):
            return "\n".join(lines[i:]).strip()
    # Fallback
    return text.strip()

def call_ollama(system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2048,
        },
    }
    resp = requests.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    return resp.json()["response"]


# -------------------- CORE GENERATION --------------------


def generate_one_pair(prompt: str | None = None):
    """Generate one validated spec from a single prompt.

    If `prompt` is None, picks a random seed prompt (the batch/training path).
    If `prompt` is provided, uses it verbatim (the end-to-end NL path).
    """
    original_prompt = prompt if prompt is not None else generate_prompt()
    prompt = original_prompt  # will be extended on retries

    spec_yaml = None
    for attempt in range(1, MAX_RETRIES + 1):
        # 1) Get raw response
        try:
            raw_yaml = call_ollama(SYSTEM_PROMPT, prompt)
        except Exception as e:
            print(f"  ❌ Ollama error: {e}")
            return None

        # 2) Extract pure YAML
        cleaned_yaml = extract_yaml(raw_yaml)
        print(f"  🔍 Attempt {attempt} - first 120 chars: {cleaned_yaml[:120]}...")

        # 3) Validate
        errors = validate_spec(cleaned_yaml)
        if not errors:
            spec_yaml = cleaned_yaml
            break

        # 4) Show failures
        print(f"  ❌ Validation failed ({len(errors)} errors):")
        for err in errors[:3]:   # show first 3
            print(f"    - {err}")

        # 5) Prepare retry prompt (keep original, add error feedback)
        prompt = (
            original_prompt
            + f"\n\nYour previous response had these validation errors:\n"
            + "\n".join(errors)
            + "\nPlease correct and output ONLY the YAML, without markdown fences."
        )

    if spec_yaml is None:
        print(f"  ❌ Failed after {MAX_RETRIES} retries. Skipping.\n")
        return None

    # Score the spec
    spec_dict = yaml.safe_load(spec_yaml)
    spec_dict["_prompt"] = original_prompt
    score, issues = runbook_score(spec_dict)

    print(f"  📊 Runbook score: {score:.2f}")
    if issues:
        for issue in issues[:5]:
            print(f"    - {issue}")
        if len(issues) > 5:
            print(f"    ... and {len(issues) - 5} more")

    # Only save if score >= 0.75 — specs missing entire runway stages
    # (inspect/create/verify) should be rejected, not just penalized.
    SCORE_THRESHOLD = 0.75
    if score >= SCORE_THRESHOLD:
        pair = {
            "prompt": original_prompt,
            "spec_yaml": spec_yaml,
            "runbook_score": score,
            "score_details": issues,
        }
        with open(OUTPUT_FILE, "a") as f:
            f.write(json.dumps(pair) + "\n")
        print(f"  ✅ Saved valid pair (task_id: {spec_dict.get('task_id', 'unknown')}, score: {score:.2f})\n")
        return pair
    else:
        print(f"  ⚠️  Score {score:.2f} below threshold ({SCORE_THRESHOLD}). Not saved.\n")
        return None

def generate_batch(count: int):
    print(f"🚀 Generating {count} prompt-spec pairs...\n")
    created = 0
    consecutive_fails = 0

    while created < count:
        res = generate_one_pair()
        if res:
            created += 1
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                print(f"❌ Aborting after {consecutive_fails} consecutive failures.")
                break

    print(f"🏁 Done. {created} pairs saved to {OUTPUT_FILE}")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    # Two modes:
    #   python run_pipeline.py [N]          batch mode: generate N pairs from seed prompts
    #   python run_pipeline.py --prompt "…"  single mode: generate one spec from a fresh NL prompt
    if len(sys.argv) >= 2 and sys.argv[1] == "--prompt":
        if len(sys.argv) < 3:
            print('Usage: python run_pipeline.py --prompt "<your feature request>"', file=sys.stderr)
            sys.exit(2)
        user_prompt = sys.argv[2]
        print(f"🚀 Processing fresh prompt: {user_prompt[:80]}...\n")
        result = generate_one_pair(prompt=user_prompt)
        if result:
            print(f"🏁 Done. Spec saved to {OUTPUT_FILE}")
            sys.exit(0)
        else:
            print("❌ Failed to produce a valid spec.")
            sys.exit(1)
    else:
        n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        generate_batch(n)