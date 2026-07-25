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
FAILED_FILE = "data/failed_specs.jsonl"

CMD_RUNWAY_DIR = pathlib.Path.home() / ".hermes" / "skills" / "command-runway-pattern"

def load_skill_context():
    """Read key skill files and return a combined context string."""
    files = [
        CMD_RUNWAY_DIR / "SKILL.md",
        CMD_RUNWAY_DIR / "references" / "command-runway-pattern.md",
        CMD_RUNWAY_DIR / "templates" / "runbook-template.md",
        CMD_RUNWAY_DIR / "templates" / "stage-template.md",
    ]
    parts = []
    for f in files:
        if f.exists():
            parts.append("--- {0} ---\n{1}\n".format(f.name, f.read_text()))
    return "\n".join(parts)

SKILL_CONTEXT = load_skill_context()

FEW_SHOT_EXAMPLE = (
    "---\n"
    "FEW-SHOT EXAMPLE ---\n"
    "Request: \"Implement the Session lifecycle API: create, get, update, close, and expire sessions. Enforce the session state machine. Add auth middleware (JWT). Generate the OpenAPI spec. Integrate with the evidence pipeline when evidence is submitted.\"\n"
    "\n"
    "Spec YAML:\n"
    "```yaml\n"
    "task_id: session-lifecycle-api\n"
    "summary: \"REST API for session lifecycle with state machine enforcement and evidence integration\"\n"
    "depends_on: [\"stage-1-core-models\", \"stage-2-pipeline\"]\n"
    "local_goals:\n"
    "  - id: L1\n"
    "    description: \"INSPECT: check existing session model and routes before adding endpoints\"\n"
    "    verification:\n"
    "      type: file_exists\n"
    "      path: \"src/models/Session.ts\"\n"
    "      expect:\n"
    "        exists: true\n"
    "  - id: L2\n"
    "    description: \"INSPECT: check existing API routes structure\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"cat apps/api/src/routes/sessions.ts\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L3\n"
    "    description: \"CREATE: add POST /v1/sessions endpoint and session model extensions\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"pnpm build --filter=@verified-attention/api\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L4\n"
    "    description: \"CREATE: add GET/PATCH/POST endpoints for session lifecycle\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"pnpm build --filter=@verified-attention/api\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L5\n"
    "    description: \"VERIFY: POST /v1/sessions creates a session and returns sessionId\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: http://localhost:3000/v1/sessions\n"
    "      headers:\n"
    "        Authorization: \"Bearer {{test_token}}\"\n"
    "      body:\n"
    "        contentId: \"test-content\"\n"
    "      expect:\n"
    "        status: 201\n"
    "        json_schema:\n"
    "          type: object\n"
    "          properties:\n"
    "            sessionId: { type: string }\n"
    "          required: [sessionId]\n"
    "  - id: L6\n"
    "    description: \"VERIFY: GET /v1/sessions/:id returns the session with evidence and claims\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: GET\n"
    "      url: http://localhost:3000/v1/sessions/{session_id}\n"
    "      headers:\n"
    "        Authorization: \"Bearer {{test_token}}\"\n"
    "      expect:\n"
    "        status: 200\n"
    "        json_schema:\n"
    "          type: object\n"
    "          properties:\n"
    "            sessionId: { type: string }\n"
    "            state: { type: string }\n"
    "            evidence: { type: array }\n"
    "            claims: { type: array }\n"
    "          required: [sessionId, state]\n"
    "  - id: L7\n"
    "    description: \"VERIFY: Session state machine rejects invalid transitions\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"pnpm test --filter=@verified-attention/api -- --testPathPattern=session-state-machine\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L8\n"
    "    description: \"VERIFY: OpenAPI spec is valid and contains session endpoints\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"npx @redocly/cli lint apps/api/openapi.yaml && grep '/v1/sessions' apps/api/openapi.yaml\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "global_goals_refs: [\"G5\", \"G13\"]\n"
    "context:\n"
    "  language: TypeScript\n"
    "  framework: Express\n"
    "  orm: Prisma\n"
    "  test_framework: Vitest\n"
)

# Build SYSTEM_PROMPT with .format() to avoid f-string issues
SYSTEM_PROMPT_TEMPLATE = (
    "You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.\n"
    "Output ONLY a YAML document. No code, no commentary.\n"
    "\n"
    "--- PROJECT SKILL (Command Runway Pattern) ---\n"
    "{skill_context}\n"
    "\n"
    "--- YAML SPEC FORMAT ---\n"
    "The YAML must contain these exact top-level fields, in this order:\n"
    "task_id: string\n"
    "summary: string\n"
    "depends_on: list of strings (optional)\n"
    "local_goals: list of objects with id, description, verification\n"
    "global_goals_refs: list of strings (optional, must reference existing global goals G1-G19)\n"
    "context: object with keys: language, framework, orm, test_framework\n"
    "\n"
    "For each local_goal, verification must follow these rules:\n"
    "- type: http | cli | file_exists | manual\n"
    "- MINIMUM 2 local_goals per spec (more is fine; 1 is never enough).\n"
    "- Every goal must verify a DISTINCT aspect.  Do NOT pad with near-duplicate\n"
    "  goals that hit the same endpoint or same file path twice.  If two goals\n"
    "  share the same (type, method, url) or (type, path) or (type, command),\n"
    "  they are near-duplicates and the spec will be rejected.\n"
    "\n"
    "Canonical `expect` keys (use ONLY these -- unknown keys are rejected):\n"
    "  http:        status (required), body_regex, body_contains, json_schema, headers_contain\n"
    "  cli:         exit_code (required), stdout_regex, stdout_contains, stdout_lines_min\n"
    "  file_exists: path is required; expect must contain at least one of content,\n"
    "               content_contains, content_not_contains, exists\n"
    "  manual:      description (required); never include an `expect` block\n"
    "\n"
    "For http:\n"
    "  - Provide method (GET/POST/PATCH/PUT/DELETE), url, and expect.status.\n"
    "  - REQUEST headers (optional) live BESIDE expect, under verification, not inside expect.\n"
    "    e.g.:\n"
    "        verification:\n"
    "          type: http\n"
    "          method: GET\n"
    "          url: http://localhost:3000/api\n"
    "          headers:                       # <- request headers, SIBLING of expect\n"
    "            Authorization: \"Bearer {{test_token}}\"\n"
    "          expect:\n"
    "            status: 200\n"
    "  - RESPONSE header assertions go INSIDE expect as `headers_contain`, a map of\n"
    "    header-name to required-substring.  This is the ONLY correct place to assert\n"
    "    response headers; never put `headers` inside expect.\n"
    "    e.g.:\n"
    "        expect:\n"
    "          status: 429\n"
    "          headers_contain:               # <- response-header checks, INSIDE expect\n"
    "            Retry-After: \"\\d+\"          # <- single-quoted YAML so backslash is literal\n"
    "  - body (optional) lives beside expect under verification, not inside expect.\n"
    "  - All body values must be valid JSON (quoted strings, no expressions like \"a\"*101).\n"
    "    Use literal strings or placeholders like {{101_a_string}}.\n"
    "  - json_schema must be inline; do NOT use $ref or definitions blocks.\n"
    "  - Placeholders for dynamic values like {{test_user_id}}, {{admin_token}}, {{user_token}} are allowed.\n"
    "  - Regex patterns inside string values MUST use single quotes (e.g. '\\d+') --\n"
    "    YAML double quotes reject backslash escapes like \d, \w, \s.\n"
    "\n"
    "For cli:\n"
    "  - Provide a real command (at least 3 chars). An empty or near-empty command is rejected.\n"
    "  - Provide expect.exit_code.  Optionally use stdout_contains / stdout_regex / stdout_lines_min.\n"
    "\n"
    "For file_exists:\n"
    "  - Provide path.  Provide at least one of the content/exists checks under expect.\n"
    "  - Do NOT use exit_code on a file_exists goal -- use content_contains instead.\n"
    "\n"
    "For manual:\n"
    "  - Provide description (the description IS the verification; no expect block).\n"
    "\n"
    "Context: TypeScript, Express, Prisma, Vitest. Auth middleware handles JWT.\n"
    "Context may also include language, framework, orm, test_framework keys.\n"
    "Global goals available: G1..G19 (refer to project charter).\n"
    "{few_shot_example}\n"
    "Now produce ONLY the YAML specification for the following feature request.\n"
)

SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(
    skill_context=SKILL_CONTEXT,
    few_shot_example=FEW_SHOT_EXAMPLE
)

# -------------------- HELPERS --------------------
def extract_yaml(text):
    """Pull YAML content from markdown fences or plain text."""
    match = re.search(r"```yaml\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r'^\w+:', line):
            return "\n".join(lines[i:]).strip()
    return text.strip()

def call_ollama(system_prompt, user_prompt):
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


def generate_one_pair(prompt=None):
    """Generate one spec from a single prompt.

    If `prompt` is None, picks a random seed prompt (the batch/training path).
    If `prompt` is provided, uses it verbatim (the end-to-end NL path).

    Returns a dict with: prompt, spec_yaml, validation_errors, attempt_count
    The spec is ALWAYS saved (to training_data.jsonl if valid, failed_specs.jsonl if not).
    """
    original_prompt = prompt if prompt is not None else generate_prompt()
    prompt = original_prompt

    spec_yaml = None
    validation_errors = []
    attempt = 1
    cleaned_yaml = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_yaml = call_ollama(SYSTEM_PROMPT, prompt)
        except Exception as e:
            print("  \u274c Ollama error: {0}".format(e))
            validation_errors = ["Ollama error: {0}".format(e)]
            break

        cleaned_yaml = extract_yaml(raw_yaml)
        print("  \u2753 Attempt {0} - first 120 chars: {1}...".format(attempt, cleaned_yaml[:120]))

        errors = validate_spec(cleaned_yaml)
        if not errors:
            spec_yaml = cleaned_yaml
            validation_errors = []
            break

        validation_errors = errors
        print("  \u274c Validation failed ({0} errors):".format(len(errors)))
        for err in errors[:3]:
            print("    - {0}".format(err))

        prompt = (
            original_prompt
            + "\n\nYour previous response had these validation errors:\n"
            + "\n".join(errors)
            + "\nPlease correct and output ONLY the YAML, without markdown fences."
        )

    # ALWAYS save the final attempt (valid or not)
    record = {
        "prompt": original_prompt,
        "spec_yaml": spec_yaml if spec_yaml else cleaned_yaml,
        "attempt": attempt,
        "validation_errors": validation_errors,
        "validated": spec_yaml is not None,
    }

    if spec_yaml is not None:
        with open(OUTPUT_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
        print("  \u2705 Saved valid spec (attempt {0}) to {1}\n".format(attempt, OUTPUT_FILE))
    else:
        with open(FAILED_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
        print("  \u274c Saved invalid spec (after {0} attempts) to {1}\n".format(attempt, FAILED_FILE))

    return record


def generate_batch(count):
    from tqdm import tqdm

    print("\U0001f680 Generating {0} prompt-spec pairs...\n".format(count))
    created = 0
    failed = 0
    consecutive_fails = 0

    pbar = tqdm(total=count, desc="Generating", unit="spec",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]  ✓{postfix}")
    pbar.set_postfix_str("valid=0 fail=0")

    while created + failed < count:
        res = generate_one_pair()
        pbar.update(1)
        if res.get("validated"):
            created += 1
            consecutive_fails = 0
        else:
            failed += 1
            consecutive_fails += 1
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                pbar.close()
                print("\u274c Aborting after {0} consecutive failures.".format(consecutive_fails))
                break
        pbar.set_postfix_str("valid={0} fail={1}".format(created, failed))

    pbar.close()
    print("\U0001f3c1 Done. {0} valid saved to {1}, {2} failed saved to {3}".format(
        created, OUTPUT_FILE, failed, FAILED_FILE))


# -------------------- MAIN --------------------
if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--prompt":
        if len(sys.argv) < 3:
            print('Usage: python run_pipeline.py --prompt "<your feature request>"', file=sys.stderr)
            sys.exit(2)
        user_prompt = sys.argv[2]
        print("\U0001f680 Processing fresh prompt: {0}...\n".format(user_prompt[:80]))
        result = generate_one_pair(prompt=user_prompt)
        if result.get("validated"):
            print("\U0001f3c1 Done. Spec saved to {0}".format(OUTPUT_FILE))
            sys.exit(0)
        else:
            print("\u274c Spec had validation errors, saved to {0}".format(FAILED_FILE))
            sys.exit(1)
    else:
        n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        generate_batch(n)