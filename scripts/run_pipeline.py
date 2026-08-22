import json
import sys
import re
import requests
import yaml
import pathlib
import os
from prompt_generator import generate_prompt
from validator import validate_spec
from runbook_scorer import runbook_score

# -------------------- CONFIG --------------------
# Provider: "ollama" | "openai" | "nvidia" | "anthropic" | "openai-compat" | "hermes" | "lmstudio"
PROVIDER = "ollama"

# Ollama
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "specforge-128k-tools2:latest"

# OpenAI / OpenAI-compatible (NVIDIA NIM, Together, Fireworks, etc.)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

# NVIDIA NIM (uses OpenAI-compatible API)
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "minimaxai/minimax-m3")

# LM Studio (OpenAI-compatible with API key)
LMSTUDIO_API_KEY = os.environ.get("LMSTUDIO_API_KEY", "")
LMSTUDIO_BASE_URL = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:34149/v1")
LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "Bonsai-27B-Q1_0")

MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILS = 10
OUTPUT_FILE = "data/training_data.jsonl"
FAILED_FILE = "data/failed_specs.jsonl"

# LLM sampling parameters (can be overridden via CLI)
TEMPERATURE = 0.2
MAX_TOKENS = 2048
OLLAMA_TIMEOUT = 300  # seconds (5 minutes) - allows for cold start

CMD_RUNWAY_DIR = pathlib.Path.home() / ".hermes" / "skills" / "command-runway-pattern"


# -------------------- SKILL CONTEXT --------------------
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
# Escape any curly braces in skill context to avoid format() conflicts
SKILL_CONTEXT = SKILL_CONTEXT.replace("{", "{{").replace("}", "}}")


# -------------------- FEW-SHOT EXAMPLE (ENRICHED) --------------------
FEW_SHOT_EXAMPLE = (
    "---\n"
    "EXAMPLE 1: HTTP Endpoint\n"
    "---\n"
    "Request: \"Add a POST /register endpoint that accepts email and password\"\n"
    "\n"
    "<thought>\n"
    "I need to create a new HTTP endpoint. First I will inspect if the file exists. Then I will create the endpoint with a blueprint. Finally I will verify it with an HTTP request.\n"
    "</thought>\n"
    "```yaml\n"
    "task_id: register-endpoint\n"
    "summary: \"POST /register endpoint\"\n"
    "business_rules:\n"
    "  - name: \"Password\"\n"
    "    formula: \"hashed\"\n"
    "test_fixtures: []\n"
    "environment:\n"
    "  packages: []\n"
    "  env_vars: {}\n"
    "  services: []\n"
    "global_verification:\n"
    "  - \"pytest tests/\"\n"
    "local_goals:\n"
    "  - id: L1\n"
    "    description: \"INSPECT: check routes\"\n"
    "    type: inspect\n"
    "    verification:\n"
    "      type: file_exists\n"
    "      path: \"src/routes.py\"\n"
    "      expect:\n"
    "        exists: true\n"
    "  - id: L2\n"
    "    description: \"CREATE: add /register\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      from fastapi import APIRouter\n"
    "      router = APIRouter()\n"
    "      @router.post('/register')\n"
    "      async def register(email: str, password: str):\n"
    "          return {'status': 'ok'}\n"
    "    acceptance_criteria:\n"
    "      - test: \"Returns 200\"\n"
    "        steps: \"POST /register\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/register\"\n"
    "      expect:\n"
    "        status: 200\n"
    "context:\n"
    "  language: Python\n"
    "  framework: FastAPI\n"
    "  orm: SQLAlchemy\n"
    "  test_framework: pytest\n"
    "```\n"
    "\n"
    "---\n"
    "EXAMPLE 2: CLI Command\n"
    "---\n"
    "Request: \"Create a script to seed the database\"\n"
    "\n"
    "<thought>\n"
    "I need to create a python script. I'll inspect the db directory, create the script, and run it with a CLI verification.\n"
    "</thought>\n"
    "```yaml\n"
    "task_id: seed-db-script\n"
    "summary: \"Database seed script\"\n"
    "business_rules: []\n"
    "test_fixtures: []\n"
    "environment:\n"
    "  packages: []\n"
    "  env_vars: {}\n"
    "  services: []\n"
    "global_verification: []\n"
    "local_goals:\n"
    "  - id: L1\n"
    "    description: \"INSPECT: check db module\"\n"
    "    type: inspect\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"ls src/db\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L2\n"
    "    description: \"CREATE: seed script\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      import sqlite3\n"
    "      def seed():\n"
    "          conn = sqlite3.connect('db.sqlite')\n"
    "          conn.execute('CREATE TABLE IF NOT EXISTS users (id INT)')\n"
    "      if __name__ == '__main__':\n"
    "          seed()\n"
    "    acceptance_criteria:\n"
    "      - test: \"Script runs\"\n"
    "        steps: \"Run script\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"python src/db/seed.py\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "context:\n"
    "  language: Python\n"
    "  framework: None\n"
    "  orm: None\n"
    "  test_framework: pytest\n"
    "```\n"
)

# Now build SYSTEM_PROMPT using concatenation instead of .format() to avoid brace conflicts
SYSTEM_PROMPT = (
    "<system_role>\n"
    "You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.\n"
    "First, write a <thought> block where you briefly plan the local goals and identify which verifications they need. "
    "Then, output the final YAML wrapped in a ```yaml code block.\n"
    "</system_role>\n"
    "\n"
    "<project_context>\n"
    + SKILL_CONTEXT + "\n"
    "</project_context>\n"
    "\n"
    "<yaml_template>\n"
    "# FILL IN THIS TEMPLATE EXACTLY\n"
    "task_id: \"descriptive-slug-here\"\n"
    "summary: \"Short summary\"\n"
    "depends_on: []\n"
    "business_rules:\n"
    "  - name: \"Rule Name\"\n"
    "    formula: \"Rule description\"\n"
    "test_fixtures:\n"
    "  - name: \"fixture-name\"\n"
    "    setup_commands: [\"python setup.py\"]\n"
    "    teardown_commands: []\n"
    "environment:\n"
    "  packages: [\"package>=1.0\"]\n"
    "  env_vars:\n"
    "    ENV_VAR: \"test_value\"\n"
    "  services: []\n"
    "global_verification: [\"pytest tests/\"]\n"
    "local_goals:\n"
    "  - id: L1\n"
    "    description: \"INSPECT: check X\"\n"
    "    type: inspect\n"
    "    verification:\n"
    "      type: file_exists  # MUST BE: file_exists, cli, http, or manual\n"
    "      path: \"path/to/file\"\n"
    "      expect:\n"
    "        exists: true\n"
    "  - id: L2\n"
    "    description: \"CREATE: build Y\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      # Write python code here (at least 100 chars, with imports)\n"
    "    acceptance_criteria:\n"
    "      - test: \"description\"\n"
    "        steps: \"steps\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/api\"\n"
    "      headers: # REQUEST HEADERS GO HERE (sibling to expect)\n"
    "        Authorization: \"Bearer token\"\n"
    "      expect:\n"
    "        status: 201\n"
    "        headers_contain: # RESPONSE HEADERS GO HERE (inside expect)\n"
    "          Content-Type: \"application/json\"\n"
    "context:\n"
    "  language: Python\n"
    "  framework: FastAPI\n"
    "  orm: SQLAlchemy\n"
    "  test_framework: pytest\n"
    "</yaml_template>\n"
    "\n"
    "<anti_patterns>\n"
    "CRITICAL AVOID THESE MISTAKES:\n"
    "1. DO NOT put request headers inside expect:\n"
    "   expect:\n"
    "     status: 200\n"
    "     headers:  <-- WRONG! Request headers go under verification, not expect.\n"
    "2. DO NOT forget 'id' or 'description' in local_goals:\n"
    "   local_goals:\n"
    "     - verification:  <-- WRONG! Must include 'id' and 'description'.\n"
    "3. DO NOT use unknown verification types. MUST BE: http, cli, file_exists, or manual.\n"
    "4. DO NOT use unknown expect keys. \n"
    "   http allows: status, body_regex, body_contains, json_schema, headers_contain, content_type.\n"
    "   cli allows: exit_code, stdout_regex, stdout_contains, stdout_lines_min.\n"
    "5. NEVER start a YAML value with @, *, &, !, %, #, |, >, or backtick without quotes.\n"
    "6. DO NOT generate arbitrary bash commands to create or edit code (like echo \"import pytest\" >> tests/...) in any field. Let the execution engine handle writing code via the blueprint.\n"
    "</anti_patterns>\n"
    "\n"
    "<examples>\n"
    + FEW_SHOT_EXAMPLE + "\n"
    "</examples>\n"
    "\n"
    "Write your reasoning in <thought>...</thought> then output the YAML in a ```yaml block.\n"
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

def call_llm(system_prompt, user_prompt):
    """Call the configured LLM provider and return the response text."""
    if PROVIDER == "ollama":
        return _call_ollama(system_prompt, user_prompt)
    elif PROVIDER in ("openai", "openai-compat", "nvidia", "hermes", "lmstudio"):
        return _call_openai_compat(system_prompt, user_prompt)
    elif PROVIDER == "anthropic":
        return _call_anthropic(system_prompt, user_prompt)
    else:
        raise ValueError(f"Unknown PROVIDER: {PROVIDER}")

def _call_ollama(system_prompt, user_prompt):
    """Ollama OpenAI-compatible API (requires Ollama 0.1.26+ with /v1 endpoints)."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    resp = requests.post(OLLAMA_URL, headers=headers, json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def _call_openai_compat(system_prompt, user_prompt):
    """OpenAI-compatible API (OpenAI, NVIDIA NIM, Together, Fireworks, Hermes Proxy, LM Studio, etc.)"""
    if PROVIDER == "nvidia":
        api_key = NVIDIA_API_KEY
        base_url = NVIDIA_BASE_URL
        model = NVIDIA_MODEL
    elif PROVIDER == "hermes":
        api_key = "hermes-proxy"  # placeholder, proxy ignores it
        base_url = args.base_url if args.base_url else os.environ.get("HERMES_PROXY_URL", "http://localhost:8465/v1")
        model = args.model if args.model else os.environ.get("HERMES_PROXY_MODEL", "poolside/laguna-s-2.1:free")
    elif PROVIDER == "lmstudio":
        api_key = LMSTUDIO_API_KEY
        base_url = LMSTUDIO_BASE_URL
        model = LMSTUDIO_MODEL
    else:
        api_key = OPENAI_API_KEY
        base_url = OPENAI_BASE_URL
        model = OPENAI_MODEL

    if not api_key and PROVIDER not in ("hermes", "lmstudio"):
        raise RuntimeError(f"{PROVIDER.upper()}_API_KEY not set")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def _call_anthropic(system_prompt, user_prompt):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return msg.content[0].text


# -------------------- CORE GENERATION --------------------


def generate_one_pair(prompt=None, max_retries=None):
    """Generate one spec from a single prompt.

    If `prompt` is None, picks a random seed prompt (the batch/training path).
    If `prompt` is provided, uses it verbatim (the end-to-end NL path).

    Returns a dict with: prompt, spec_yaml, validation_errors, attempt_count
    The spec is ALWAYS saved (to training_data.jsonl if valid, failed_specs.jsonl if not).
    """
    if max_retries is None:
        max_retries = MAX_RETRIES
    original_prompt = prompt if prompt is not None else generate_prompt()
    prompt = original_prompt

    spec_yaml = None
    validation_errors = []
    attempt = 1
    cleaned_yaml = None

    for attempt in range(1, max_retries + 1):
        try:
            raw_yaml = call_llm(SYSTEM_PROMPT, prompt)
        except Exception as e:
            print("  \u274c LLM error: {0}".format(e))
            validation_errors = ["LLM error: {0}".format(e)]
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
                    + "\n\nFix EVERY error above. Output ONLY the corrected YAML (no prose, no markdown fences, no ```yaml wrapper).\n"
                    "Remember: task_id first (no '---' prefix), 'id' fields start with L (L1, L2...),\n"
                    "quote all strings with colons or special chars, put code in 'blueprint: |' blocks,\n"
                    "and never put inline comments after a quoted value on the same line.\n"
                    "REPLACE ALL PLACEHOLDERS: {{...}} and *** must become concrete test values.\n"
                    "  - Wrong: Authorization: ***\"Bearer {{admin_access_token}}\" or \"Bearer ***\"\n"
                    "  - Correct: Authorization: ***\"Bearer test-token-abc123\"\n"
                    "  - Wrong: DATABASE_URL: \"postgresql://user:***@localhost:5432/app\"\n"
                    "  - Correct: DATABASE_URL: \"postgresql://user:***@localhost:5432/app\"\n"
                    "  - Wrong: JWT_SECRET: \"{{JWT_SECRET}}\"\n"
                    "  - Correct: JWT_SECRET: \"test-secret-1234567890abcdef\"\n"
                    "NEVER use *** in any string - not in DATABASE_URL, not in headers, not in env_vars.\n"
                    "Every password, secret, token must be a concrete test value like 'testpass', 'test-token-abc123', 'test-secret-...'.\n"
                    "Every CREATE goal MUST have 'verification' and non-empty 'acceptance_criteria'.\n"
                    "No two goals may verify the same target with the same method (near-duplicate check).\n"
                    "CRITICAL: For CREATE goals, blueprint MUST include all necessary import statements at the top.\n"
                    "CRITICAL: Each goal must verify a DISTINCT target. Different (type, url) for http, different (type, path) for file_exists, different (type, command) for cli."
                )

    # ALWAYS save the final attempt (valid or not)
    record = {
        "prompt": original_prompt,
        "spec_yaml": spec_yaml if spec_yaml else cleaned_yaml,
        "attempt": attempt,
        "validation_errors": validation_errors,
        "validated": spec_yaml is not None,
    }

    # Compute runbook_score for fine-tuning pipeline compatibility
    if spec_yaml is not None:
        import yaml
        try:
            score, _ = runbook_score(yaml.safe_load(spec_yaml))
            record["runbook_score"] = round(float(score), 4)
        except Exception:
            record["runbook_score"] = 0.0
    else:
        record["runbook_score"] = 0.0

    if spec_yaml is not None:
        with open(OUTPUT_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
        print("  \u2705 Saved valid spec (attempt {0}) to {1}\n".format(attempt, OUTPUT_FILE))
    else:
        with open(FAILED_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
        print("  \u274c Saved invalid spec (after {0} attempts) to {1}\n".format(attempt, FAILED_FILE))

    return record


def generate_batch(count, max_retries=None):
    from tqdm import tqdm

    print("\U0001f680 Generating {0} prompt-spec pairs... [provider={1}]\n".format(count, PROVIDER))
    created = 0
    failed = 0
    consecutive_fails = 0

    pbar = tqdm(total=count, desc="Generating", unit="spec",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]  \u2713{postfix}")
    pbar.set_postfix_str("valid=0 fail=0")

    while created + failed < count:
        res = generate_one_pair(max_retries=max_retries)
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
    import argparse

    parser = argparse.ArgumentParser(description="Generate COMMAND_RUNWAY specs from natural language")
    parser.add_argument("--prompt", type=str, help="Feature request prompt (single spec mode)")
    parser.add_argument("--batch", type=int, help="Number of specs to generate (batch mode, default 10)")
    parser.add_argument("--provider", type=str, choices=["ollama", "openai", "nvidia", "anthropic", "openai-compat", "hermes", "lmstudio"],
                        help="LLM provider (overrides PROVIDER config)")
    parser.add_argument("--model", type=str, help="Model name (overrides provider's default model)")
    parser.add_argument("--api-key", type=str, help="API key for provider (or set via env var)")
    parser.add_argument("--base-url", type=str, help="Base URL for OpenAI-compatible APIs")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens in response")
    parser.add_argument("--timeout", type=int, default=300, help="LLM request timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=None, help="Max retry attempts for validation (default: from config)")
    args = parser.parse_args()

    # Override config from CLI args
    if args.provider:
        PROVIDER = args.provider
    if args.model:
        if PROVIDER == "nvidia":
            NVIDIA_MODEL = args.model
        elif PROVIDER in ("openai", "openai-compat"):
            OPENAI_MODEL = args.model
        elif PROVIDER == "ollama":
            OLLAMA_MODEL = args.model
        elif PROVIDER == "anthropic":
            ANTHROPIC_MODEL = args.model
        elif PROVIDER == "hermes":
            HERMES_PROXY_MODEL = args.model
        elif PROVIDER == "lmstudio":
            LMSTUDIO_MODEL = args.model
    if args.api_key:
        if PROVIDER == "nvidia":
            NVIDIA_API_KEY = args.api_key
        elif PROVIDER in ("openai", "openai-compat"):
            OPENAI_API_KEY = args.api_key
        elif PROVIDER == "anthropic":
            ANTHROPIC_API_KEY = args.api_key
        elif PROVIDER == "hermes":
            # Hermes proxy ignores api_key
            pass
        elif PROVIDER == "lmstudio":
            LMSTUDIO_API_KEY = args.api_key
    if args.base_url:
        if PROVIDER == "nvidia":
            NVIDIA_BASE_URL = args.base_url
        elif PROVIDER in ("openai", "openai-compat"):
            OPENAI_BASE_URL = args.base_url
        elif PROVIDER == "hermes":
            HERMES_PROXY_URL = args.base_url
        elif PROVIDER == "lmstudio":
            LMSTUDIO_BASE_URL = args.base_url

    if args.temperature:
        TEMPERATURE = args.temperature
    if args.max_tokens:
        MAX_TOKENS = args.max_tokens
    if args.max_retries is not None:
        MAX_RETRIES = args.max_retries

    if args.prompt:
        print("\U0001f680 Processing fresh prompt: {0}...\n".format(args.prompt[:80]))
        result = generate_one_pair(prompt=args.prompt, max_retries=args.max_retries)
        if result.get("validated"):
            print("\U0001f3c1 Done. Spec saved to {0}".format(OUTPUT_FILE))
            sys.exit(0)
        else:
            print("\u274c Spec had validation errors, saved to {0}".format(FAILED_FILE))
            sys.exit(1)
    else:
        n = args.batch if args.batch else (int(sys.argv[1]) if len(sys.argv) > 1 else 10)
        generate_batch(n, max_retries=args.max_retries)
