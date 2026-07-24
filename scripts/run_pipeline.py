import json
import sys
import re
import requests
import yaml
import pathlib
from prompt_generator import generate_prompt
from validator import validate_spec

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

FEW_SHOT_EXAMPLE = """
--- FEW-SHOT EXAMPLE ---
Request: "Implement the Session lifecycle API: create, get, update, close, and expire sessions. Enforce the session state machine. Add auth middleware (JWT). Generate the OpenAPI spec. Integrate with the evidence pipeline when evidence is submitted."

Spec YAML:
```yaml
task_id: session-lifecycle-api
summary: "REST API for session lifecycle with state machine enforcement and evidence integration"
depends_on: ["stage-1-core-models", "stage-2-pipeline"]
local_goals:
  - id: L1
    description: "POST /v1/sessions creates a session and returns sessionId"
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
  - id: L2
    description: "GET /v1/sessions/:id returns the session with evidence and claims"
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
  - id: L3
    description: "PATCH /v1/sessions/:id updates session config and heartbeat"
    verification:
      type: http
      method: PATCH
      url: http://localhost:3000/v1/sessions/{session_id}
      headers:
        Authorization: "Bearer {test_token}"
      body:
        config: { timeout: 3600 }
      expect:
        status: 200
  - id: L4
    description: "POST /v1/sessions/:id/evidence submits evidence to pipeline"
    verification:
      type: http
      method: POST
      url: http://localhost:3000/v1/sessions/{session_id}/evidence
      headers:
        Authorization: "Bearer {test_token}"
      body:
        type: "E-VISIBLE"
        payload: { timestamp: 1620000000000, duration: 5000 }
      expect:
        status: 202
  - id: L5
    description: "POST /v1/sessions/:id/close transitions session to CLOSED"
    verification:
      type: http
      method: POST
      url: http://localhost:3000/v1/sessions/{session_id}/close
      headers:
        Authorization: "Bearer {test_token}"
      expect:
        status: 200
        json_schema:
          type: object
          properties:
            state: { const: CLOSED }
  - id: L6
    description: "Session state machine rejects invalid transitions"
    verification:
      type: cli
      command: "pnpm test --filter=@verified-attention/api -- --testPathPattern=session-state-machine"
      expect:
        exit_code: 0
  - id: L7
    description: "OpenAPI spec is valid and contains session endpoints"
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

task_id: list-sessions-endpoint
summary: "GET /v1/sessions returns paginated list of sessions"
local_goals:
  - id: L1
    description: "GET /v1/sessions with page/limit returns 200 and session array"
    verification:
      type: http
      method: GET
      url: http://localhost:3000/v1/sessions?page=1&limit=10
      headers:
        Authorization: "Bearer {test_token}"
      expect:
        status: 200
        json_schema:
          type: object
          properties:
            data:
              type: array
              items:
                type: object
                properties:
                  id: { type: string }
                  state: { type: string }
                  contentId: { type: string }
                  createdAt: { type: string }
                required: [id, state, contentId]
            total: { type: integer }
            page: { type: integer }
            limit: { type: integer }
          required: [data, total]
context:
  language: TypeScript
  framework: Express
  orm: Prisma
  test_framework: Vitest
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
- type: http | cli | file_exists
- For http: method, url, headers (optional), body (optional), expect with status and optional json_schema
- All body values must be valid JSON (quoted strings, no expressions like "a"*101).
  Use literal strings or placeholders like "{{{{101_a_string}}}}".
- json_schema must be inline; do NOT use $ref or definitions blocks.
- Placeholders for dynamic values like {{{{test_user_id}}}}, {{{{admin_token}}}}, {{{{user_token}}}} are allowed.

Context: TypeScript, Express, Prisma, Vitest. Auth middleware handles JWT.
Global goals available: G1..G19 (refer to project charter).
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
def generate_one_pair():
    original_prompt = generate_prompt()
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

    # Save valid pair
    pair = {
        "prompt": original_prompt,
        "spec_yaml": spec_yaml,
    }
    with open(OUTPUT_FILE, "a") as f:
        f.write(json.dumps(pair) + "\n")
    print(f"  ✅ Saved valid pair (task_id: {yaml.safe_load(spec_yaml).get('task_id', 'unknown')})\n")
    return pair

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
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    generate_batch(n)