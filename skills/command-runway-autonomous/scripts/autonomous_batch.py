#!/usr/bin/env python3
"""
Batch autonomous execution: Generate N validated specs from seed prompts.

This replaces `make generate N=X` by using the autonomous skill to:
1. Load seed prompts from prompt_generator.py
2. Generate validated specs for each
3. Save to data/training_data.jsonl (valid) and data/failed_specs.jsonl (invalid)
4. Score all specs with runbook_scorer.py

Usage:
    python3 autonomous_batch.py --count 10 --output-dir ./data --min-score 0.75
"""

import sys
import os
import json
import yaml
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import argparse

# Add githeri repo scripts path
GITHERI_ROOT = Path("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri")
sys.path.insert(0, str(GITHERI_ROOT / "scripts"))
sys.path.insert(0, str(GITHERI_ROOT / "skills" / "spec-forge" / "scripts"))
sys.path.insert(0, str(Path.home() / ".hermes" / "skills" / "spec-forge" / "scripts"))

from prompt_generator import generate_prompt
from validator import validate_spec
from runbook_scorer import runbook_score


class BatchExecutor:
    def __init__(self, llm_base_url: str, llm_model: str, llm_api_key: str = ""):
        self.llm_base_url = llm_base_url
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.llm_process = None  # We'll use the existing LLMClient
        
    def load_llm_client(self):
        """Load the LLM client from autonomous_execute.py"""
        import urllib.request
        import json
        
        class LLMClient:
            def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 300):
                self.base_url = base_url.rstrip("/")
                self.model = model
                self.api_key = api_key
                self.timeout = timeout

            def chat(self, messages: list, temperature: float = 0.3) -> str:
                url = f"{self.base_url}/chat/completions"
                payload = {"model": self.model, "messages": messages, "temperature": temperature}
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                if self.api_key:
                    req.add_header("Authorization", f"Bearer {self.api_key}")
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        return body["choices"][0]["message"]["content"]
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"LLM HTTP {e.code}: {err_body[:500]}")
                except urllib.error.URLError as e:
                    raise RuntimeError(f"LLM connection error: {e}")
        
        self.llm_client = LLMClient(self.llm_base_url, self.llm_model, self.llm_api_key)

    def generate_spec(self, prompt: str) -> Dict[str, Any]:
        """Generate a spec from a prompt using LLM with validation retries."""
        
        # Load system prompt from run_pipeline.py
        pipeline_path = Path(__file__).parent.parent.parent / "spec-forge" / "scripts" / "run_pipeline.py"
        if not pipeline_path.exists():
            pipeline_path = Path.home() / ".hermes" / "skills" / "spec-forge" / "scripts" / "run_pipeline.py"
        
        # Build the same system prompt as run_pipeline.py
        cmd_runway_dir = Path.home() / ".hermes" / "skills" / "command-runway-pattern"
        skill_files = [
            cmd_runway_dir / "SKILL.md",
            cmd_runway_dir / "references" / "command-runway-pattern.md",
            cmd_runway_dir / "templates" / "runbook-template.md",
            cmd_runway_dir / "templates" / "stage-template.md",
        ]
        skill_context = ""
        for f in skill_files:
            if f.exists():
                skill_context += f"--- {f.name} ---\n{f.read_text()}\n\n"
        
        # Few-shot example from run_pipeline.py
        few_shot = """---
FEW-SHOT EXAMPLE ---
Request: "Implement the Session lifecycle API: create, get, update, close, and expire sessions. Enforce the session state machine. Add auth middleware (JWT). Generate the OpenAPI spec. Integrate with the evidence pipeline when evidence is submitted."
---
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
        Authorization: "Bearer {{test_token}}"
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
        Authorization: "Bearer {{test_token}}"
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

Now produce ONLY the YAML specification for the following feature request.

"""
        
        system_prompt = f"""You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.
Output ONLY a YAML document. No code, no commentary.

--- PROJECT SKILL (Command Runway Pattern) ---
{skill_context}

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

Canonical `expect` keys (use ONLY these -- unknown keys are rejected):
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
            Authorization: "Bearer {{test_token}}"
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
    Use literal strings or placeholders like {{101_a_string}}.
  - json_schema must be inline; do NOT use $ref or definitions blocks.
  - Placeholders for dynamic values like {{test_user_id}}, {{admin_token}}, {{user_token}} are allowed.
  - Regex patterns inside string values MUST use single quotes (e.g. '\\d+') --
    YAML double quotes reject backslash escapes like \\d, \\w, \\s.

For cli:
  - Provide a real command (at least 3 chars). An empty or near-empty command is rejected.
  - Provide expect.exit_code.  Optionally use stdout_contains / stdout_regex / stdout_lines_min.

For file_exists:
  - Provide path.  Provide at least one of the content/exists checks under expect.
  - Do NOT use exit_code on a file_exists goal -- use content_contains instead.

For manual:
  - Provide description (the description IS the verification; no expect block).

Context: TypeScript, Express, Prisma, Vitest. Auth middleware handles JWT.
Context may also include language, framework, orm, test_framework keys.
Global goals available: G1..G19 (refer to project charter).
{few_shot}
Now produce ONLY the YAML specification for the following feature request."""

        prompt_template = f"""Generate a spec for this feature:

{{prompt}}

Follow the exact YAML structure from the system prompt. Use "verification:" with nested "expect:" blocks. Output only YAML."""

        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.llm_client.chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_template.format(prompt=prompt)},
                ], temperature=0.2 if attempt == 1 else 0.1)
            except Exception as e:
                return {"prompt": prompt, "spec_yaml": None, "validated": False, "error": str(e), "attempt": attempt}

            # Extract YAML
            content = response.strip()
            if content.startswith("```yaml"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse YAML
            try:
                spec = yaml.safe_load(content)
            except yaml.YAMLError as e:
                return {"prompt": prompt, "spec_yaml": content, "validated": False, "error": f"YAML parse error: {e}", "attempt": attempt}

            if not isinstance(spec, dict):
                return {"prompt": prompt, "spec_yaml": content, "validated": False, "error": "Spec is not a dict", "attempt": attempt}

            # Validate
            errors = validate_spec(yaml.dump(spec))
            if not errors:
                return {
                    "prompt": prompt,
                    "spec_yaml": yaml.dump(spec),
                    "validated": True,
                    "attempt": attempt,
                }
            
            if attempt < max_retries:
                # Retry with error feedback
                prompt = f"""The spec had these validation errors:
{chr(10).join(errors)}

Fix these issues and output a corrected YAML spec. Output only YAML."""
                continue
            else:
                return {"prompt": prompt, "spec_yaml": yaml.dump(spec), "validated": False, "errors": errors, "attempt": attempt}

        return {"prompt": prompt, "spec_yaml": None, "validated": False, "error": "Max retries exceeded", "attempt": max_retries}


def main():
    parser = argparse.ArgumentParser(description="Batch generate validated specs for training data")
    parser.add_argument("--count", type=int, default=10, help="Number of specs to generate")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory")
    parser.add_argument("--llm-base-url", type=str, default="http://localhost:11434/v1", help="LLM base URL")
    parser.add_argument("--llm-model", type=str, default="qwen2.5-coder:7b-instruct", help="LLM model")
    parser.add_argument("--llm-api-key", type=str, default="", help="LLM API key")
    parser.add_argument("--min-score", type=float, default=0.75, help="Minimum runbook score for valid")
    parser.add_argument("--skip-scoring", action="store_true", help="Skip runbook scoring")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    training_file = output_dir / "training_data.jsonl"
    failed_file = output_dir / "failed_specs.jsonl"

    executor = BatchExecutor(args.llm_base_url, args.llm_model, args.llm_api_key)
    executor.load_llm_client()

    print(f"🚀 Generating {args.count} prompt-spec pairs...")
    print(f"   Model: {args.llm_model}")
    print(f"   Output: {training_file}")
    print(f"   Min score: {args.min_score}")

    valid_count = 0
    failed_count = 0
    
    for i in range(args.count):
        print(f"\n[{i+1}/{args.count}] Generating...")
        
        # Get seed prompt
        prompt = generate_prompt()
        print(f"  Prompt: {prompt[:80]}...")
        
        # Generate spec
        result = executor.generate_spec(prompt)
        
        # Score if validated
        score = 0.0
        above_threshold = False
        
        if result.get("validated"):
            spec_yaml = result["spec_yaml"]
            try:
                spec_dict = yaml.safe_load(spec_yaml)
                spec_dict["_prompt"] = result["prompt"]
                score, _ = runbook_score(spec_dict)
                above_threshold = score >= args.min_score
            except:
                score = 0.0
                above_threshold = False
            
            record = {
                "prompt": result["prompt"],
                "spec_yaml": result["spec_yaml"],
                "attempt": result.get("attempt", 1),
                "validation_errors": [],
                "validated": True,
                "runbook_score": score,
                "above_threshold": above_threshold,
            }
            
            with open(training_file, "a") as f:
                f.write(json.dumps(record) + "\n")
            valid_count += 1
            print(f"  ✅ Valid (score: {score:.2f}, threshold: {above_threshold})")
        else:
            record = {
                "prompt": result["prompt"],
                "spec_yaml": result.get("spec_yaml"),
                "attempt": result.get("attempt", 1),
                "validation_errors": result.get("errors", [result.get("error", "Unknown")]),
                "validated": False,
            }
            with open(failed_file, "a") as f:
                f.write(json.dumps(record) + "\n")
            failed_count += 1
            print(f"  ❌ Failed: {result.get('error', result.get('errors', 'Unknown'))}")

    # Summary
    print(f"\n🏁 Done. {valid_count} valid, {failed_count} failed saved.")
    print(f"   Training data: {training_file}")
    print(f"   Failed specs: {failed_file}")

    # Score all specs
    if not args.skip_scoring:
        print("\n📊 Scoring all specs...")
        subprocess.run([
            sys.executable, 
            str(Path(__file__).parent / "score_corpus.py"),
            "--file", str(training_file),
            "--threshold", str(args.min_score)
        ])
        subprocess.run([
            sys.executable,
            str(Path(__file__).parent / "score_corpus.py"),
            "--file", str(failed_file),
            "--threshold", "0.0"
        ])


if __name__ == "__main__":
    main()