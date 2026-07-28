#!/usr/bin/env python3
"""
Autonomous execution script: NL prompt -> spec -> PLAN.md -> RUNBOOK.md -> execute
PLAN.md is written to disk BEFORE execution starts.

LLM execution loop: for 'write_file' commands, calls an LLM to generate file content,
writes it to disk, then runs verify commands. On verify failure, feeds the error back
to the LLM for self-healing (up to max_retries).

Usage:
    python3 autonomous_execute.py --prompt "Add health endpoint" --output-dir ./out --output all
    python3 autonomous_execute.py --prompt "..." --output-dir ./out --output all \
        --llm-base-url http://localhost:11434/v1 --llm-model qwen2.5-coder:7b --llm-api-key ollama

Output modes:
    --output spec           : Just validated spec.yaml
    --output plan           : PLAN.md only
    --output plan+runbook   : PLAN.md + RUNBOOK.md (no execution)
    --output all            : Full delivery (spec + plan + runbook + execution)
    --output execute-only   : Just executes a existing RUNBOOK.md

LLM configuration (all optional via env vars or CLI flags):
    --llm-base-url   LLM base URL (default: $LLM_BASE_URL or https://openrouter.ai/api/v1)
    --llm-model       Model name (default: $LLM_MODEL or qwen2.5-coder:7b-instruct)
    --llm-api-key     API key (default: $LLM_API_KEY or empty for local)
    --llm-provider    Provider hint: openrouter|ollama|openai|custom (default: custom)
"""

import sys
import os
import subprocess
import yaml
import json
import re
import urllib.request
import urllib.error
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
# Set skill root to the user's .hermes directory (works both on host and in container)
SKILL_ROOT = Path.home() / ".hermes" / "skills"
SPEC_FORGE_ROOT = SKILL_ROOT / "spec-forge"
PLANNER_ROOT = SKILL_ROOT / "software-development" / "command-runway-planner"

# Add the script directories to the path
sys.path.insert(0, str(SPEC_FORGE_ROOT / "scripts"))
sys.path.insert(0, str(PLANNER_ROOT / "scripts"))

# Import required modules from spec-forge and planner
from validator import validate_spec
from assemble_plan import assemble_plan, assemble_runbook, load_spec

# Import spec-forge pipeline for generation (optional)
try:
    from run_pipeline import generate_one_pair as specforge_generate_one_pair
    SPECFORGE_PIPELINE_AVAILABLE = True
except ImportError:
    SPECFORGE_PIPELINE_AVAILABLE = False
    print("[WARN] spec-forge pipeline not available for generation, falling back to minimal prompt")

# ============================================================
# ============================================================
# LLM CLIENT (OpenAI-compatible HTTP API)
# ============================================================

class LLMClient:
    """Thin HTTP client for OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """Send a chat completion request and return the assistant message."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

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


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Command:
    cmd_num: str
    deps: List[str]
    cmd_type: str  # inspect, create, verify
    command: str
    expected: Dict[str, Any]
    fallback: str
    stage: int

@dataclass
class Stage:
    num: int
    name: str
    commands: List[Command]

@dataclass
class ExecutionResult:
    cmd: Command
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    retries: int
    start_time: datetime
    end_time: datetime


# ============================================================
# CONFIG
# ============================================================

def load_config():
    """Load autonomous execution config."""
    config_path = Path(__file__).resolve().parent.parent / "references" / "autonomous_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f.read())


def detect_project_type(working_dir: Path) -> dict:
    """Detect project type and return appropriate config."""
    project_info = {
        "type": "unknown",
        "root_markers": [],
        "install_cmd": None,
        "context_extensions": [],
        "test_cmd": None,
        "build_cmd": None,
    }
    
    # Python project (pyproject.toml, setup.py, requirements.txt)
    if (working_dir / "pyproject.toml").exists() or (working_dir / "setup.py").exists() or (working_dir / "requirements.txt").exists():
        project_info["type"] = "python"
        project_info["root_markers"] = ["pyproject.toml", "setup.py", "requirements.txt"]
        # Use requirements.txt if it exists, otherwise pip install -e .
        if (working_dir / "requirements.txt").exists():
            project_info["install_cmd"] = "pip install -r requirements.txt"
        else:
            project_info["install_cmd"] = "pip install -e ."
        project_info["context_extensions"] = [".py", ".txt", ".toml", ".yaml", ".yml"]
        project_info["test_cmd"] = "pytest"
        project_info["build_cmd"] = "python -m build"
    
    # Node.js / pnpm monorepo
    elif (working_dir / "pnpm-workspace.yaml").exists() or (working_dir / "package.json").exists():
        project_info["type"] = "node"
        project_info["root_markers"] = ["pnpm-workspace.yaml", "package.json"]
        project_info["install_cmd"] = "pnpm install"
        project_info["context_extensions"] = [".ts", ".js", ".json"]
        project_info["test_cmd"] = "pnpm test"
        project_info["build_cmd"] = "pnpm build"
    
    # Go project
    elif (working_dir / "go.mod").exists():
        project_info["type"] = "go"
        project_info["root_markers"] = ["go.mod"]
        project_info["install_cmd"] = "go mod tidy"
        project_info["context_extensions"] = [".go", ".mod", ".sum"]
        project_info["test_cmd"] = "go test ./..."
        project_info["build_cmd"] = "go build ./..."
    
    # Rust project
    elif (working_dir / "Cargo.toml").exists():
        project_info["type"] = "rust"
        project_info["root_markers"] = ["Cargo.toml"]
        project_info["install_cmd"] = "cargo build"
        project_info["context_extensions"] = [".rs", ".toml"]
        project_info["test_cmd"] = "cargo test"
        project_info["build_cmd"] = "cargo build"
    
    return project_info


def find_project_root(start_dir: Path) -> Path:
    """Find project root by searching for known root markers."""
    search_dir = start_dir
    for _ in range(10):  # Max 10 levels up
        # Check for common root markers
        if (search_dir / "pyproject.toml").exists() or \
           (search_dir / "setup.py").exists() or \
           (search_dir / "requirements.txt").exists() or \
           (search_dir / "pnpm-workspace.yaml").exists() or \
           (search_dir / "package.json").exists() or \
           (search_dir / "go.mod").exists() or \
           (search_dir / "Cargo.toml").exists() or \
           (search_dir / ".git").exists():
            return search_dir
        search_dir = search_dir.parent
        if search_dir == search_dir.parent:
            break
    return start_dir


# ============================================================
# RUNBOOK PARSER
# ============================================================

def parse_runbook(runbook_path: Path) -> List[Stage]:
    """Parse RUNBOOK.md and extract command runway table."""
    with open(runbook_path) as f:
        content = f.read()

    stages = []

    # Find all stage sections
    stage_pattern = r'### Stage (\d+): (.+?)\n'
    stage_matches = list(re.finditer(stage_pattern, content))

    # Filter to only stages that have a command table below them
    real_stages = []
    for match in stage_matches:
        after = content[match.end():]
        if '| Cmd#' in after[:200] and 'Command / Tool' in after[:200]:
            real_stages.append(match)
        elif '| Cmd#' in after[:200] and 'Start | End' in after[:200]:
            # This is the execution log, not a stage — skip
            pass

    for i, match in enumerate(real_stages):
        stage_num = int(match.group(1))
        stage_name = match.group(2).strip()
        start_pos = match.end()
        end_pos = real_stages[i + 1].start() if i + 1 < len(real_stages) else len(content)
        stage_content = content[start_pos:end_pos]

        commands = parse_command_table(stage_content, stage_num)
        stages.append(Stage(num=stage_num, name=stage_name, commands=commands))

    return stages


def parse_command_table(content: str, stage_num: int) -> List[Command]:
    """Parse markdown command table into Command objects.

    Stops at the first blank line or non-table line after the header row.
    Ignores rows that look like execution log entries (7 columns: Start, End, Exit, Retry#, Output).
    """
    commands = []

    lines = content.strip().split('\n')
    in_table = False

    for line in lines:
        if '| Cmd#' in line and '| Deps' in line:
            in_table = True
            # Only treat as command table if it has the right column headers
            if 'Command / Tool' not in line and 'Expected Artifact' not in line:
                in_table = False
            continue
        if in_table and line.startswith('|'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            # Skip separator rows (|------|------|...)
            if all(set(c) <= set('-: ') for c in parts):
                continue
            if len(parts) >= 6:
                cmd_num = parts[0]
                # Skip log entries (7 columns: Cmd#, Deps, Start, End, Exit, Retry#, Output)
                if len(parts) >= 7:
                    continue
                deps_str = parts[1].strip()
                deps = [d.strip() for d in deps_str.split(',') if d.strip() and d.strip() != '—'] if deps_str and deps_str != '—' else []
                cmd_type = parts[2]
                command = parts[3].replace('`', '')  # Strip backticks from markdown
                expected = parse_expected(parts[4])
                fallback = parts[5]

                commands.append(Command(
                    cmd_num=cmd_num, deps=deps, cmd_type=extract_type(cmd_type),
                    command=command, expected=expected, fallback=fallback, stage=stage_num
                ))
        elif in_table and not line.startswith('|'):
            in_table = False

    return commands


def extract_type(type_str: str) -> str:
    """Extract clean command type from icon-prefixed string."""
    type_str = type_str.strip()
    for t in ["inspect", "create", "verify"]:
        if t in type_str.lower():
            return t
    return "inspect"


def parse_expected(text: str) -> Dict[str, Any]:
    """Parse expected artifact/verification string into structured dict."""
    expected = {}
    text = text.strip()

    if 'exit 0' in text:
        expected['exit_code'] = 0
    if 'exit' in text and 'exit 0' not in text:
        match = re.search(r'exit\s+(\d+)', text)
        if match:
            expected['exit_code'] = int(match.group(1))

    match = re.search(r"grep -q ['\"]([^'\"]+)['\"]", text)
    if match:
        expected['stdout_contains'] = match.group(1)

    if 'status' in text.lower() and ('200' in text or '^200' in text):
        expected['http_status'] = 200

    if 'file exists' in text.lower() or 'test -f' in text:
        expected['file_exists'] = True

    if not expected:
        expected['raw'] = text

    return expected


# ============================================================
# WRITE_FILE COMMAND PARSER
# ============================================================

def parse_write_file_command(command_str: str, stage: Optional[Stage] = None) -> Optional[Dict[str, str]]:
    """
    Parse 'write_file <path> with <content_ref>' commands.

    Handles backtick-wrapped commands from markdown tables.
    If the path is a placeholder like <path>, extract the real path
    from the stage's verify command (which contains 'test -f <real_path>').
    """
    command_str = command_str.strip().replace('`', '')  # Strip backticks from markdown

    # Pattern: write_file <path> with <content_ref>
    match = re.match(r'write_file\s+(\S+)(?:\s+with\s+(.+))?', command_str)
    if match:
        path = match.group(1)
        content_ref = (match.group(2) or '').strip()

        # If path is a placeholder, extract from verify commands in the same stage
        if path.startswith('<') and path.endswith('>') and stage:
            for vcmd in stage.commands:
                if vcmd.cmd_type == 'verify':
                    # Look for 'test -f <path>' or 'test -e <path>' in verify command
                    testf_match = re.search(r'test -[fe]\s+(\S+)', vcmd.command)
                    if testf_match:
                        path = testf_match.group(1)
                        # Also extract content_contains from the verify command
                        grep_match = re.search(r"grep -q ['\"]([^'\"]+)['\"]", vcmd.command)
                        if grep_match and not content_ref:
                            content_ref = f"must contain: {grep_match.group(1)}"
                        break

        return {
            'path': path,
            'content_ref': content_ref,
        }

    # Pattern: write_file(path, content) — function call style
    match = re.match(r"write_file\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*(.+)\s*\)", command_str)
    if match:
        return {
            'path': match.group(1),
            'content_ref': match.group(2).strip(),
        }

    return None


def parse_mkdir_command(command_str: str) -> Optional[str]:
    """Parse 'mkdir -p <path>' commands, return the path."""
    match = re.match(r'mkdir\s+(?:-p\s+)?(\S+)', command_str.strip())
    if match:
        return match.group(1)
    return None


# ============================================================
# LLM-BACKED FILE GENERATION
# ============================================================

def build_file_gen_prompt(
    file_path: str,
    spec: dict,
    stage: Stage,
    cmd: Command,
    existing_files: Dict[str, str],
    error_context: str = "",
    project_type: str = "unknown",
) -> List[Dict[str, str]]:
    """
    Build chat messages for the LLM to generate file content.
    
    The LLM is asked to generate files appropriate for the project type.
    
    Returns as a JSON dict of {filepath: content} so the executor can
    write each file to disk.
    """
    spec_yaml = yaml.dump(spec, default_flow_style=False, sort_keys=False)

    # Gather existing file context (limit to 3 most relevant)
    context_lines = []
    for fpath, fcontent in list(existing_files.items())[:3]:
        context_lines.append(f"--- {fpath} ---\n{fcontent[:2000]}")
    existing_context = "\n\n".join(context_lines) if context_lines else "(no existing files yet)"

    # Project-specific conventions
    project_conventions = {
        "python": {
            "description": "Python project with standard packaging",
            "conventions": """- Python 3.11+ with type hints
- Use pydantic for schema validation  
- Use pytest for tests
- Use pyproject.toml for packaging (or setup.py)
- Keep code focused and minimal
- Tests should verify the main functionality""",
            "package_files": {
                "pyproject.toml": "[project]\nname = \"{pkg_name}\"\nversion = \"0.1.0\"\ndescription = \"{summary}\"\nrequires-python = \">=3.11\"\ndependencies = []\n\n[build-system]\nrequires = [\"setuptools>=61.0\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\npython_files = [\"test_*.py\"]\npython_functions = [\"test_*\"]",
                "src/{pkg_name}/__init__.py": "\"\"\"{summary}\"\"\"\n\n__version__ = \"0.1.0\"",
                "tests/test_{pkg_name}.py": "import pytest\nfrom {pkg_name} import main\n\ndef test_main():\n    # TODO: implement test\n    assert True",
            },
            "main_entry": "src/{pkg_name}/main.py",
        },
        "node": {
            "description": "TypeScript/Node.js project with pnpm",
            "conventions": """- TypeScript packages with strict mode, target ES2022, module ESNext, moduleResolution bundler
- Use zod for schema validation
- Use vitest for tests (describe, it, expect)
- Use tsdown for builds (entry: src/index.ts, format: esm, dts: true)
- Package naming: @verified-attention/<name>
- Each package has: package.json, tsconfig.json, tsdown.config.ts, src/index.ts
- Test files use src/index.test.ts
- Keep code focused and minimal — no unnecessary abstractions
- Tests should verify the main functionality, not edge cases""",
            "package_files": {
                "package.json": "{{\n  \"name\": \"@verified-attention/{pkg_name}\",\n  \"version\": \"0.1.0\",\n  \"type\": \"module\",\n  \"scripts\": {{\n    \"build\": \"tsdown\",\n    \"test\": \"vitest run\",\n    \"dev\": \"vitest\"\n  }},\n  \"devDependencies\": {{\n    \"typescript\": \"^5.3.0\",\n    \"vitest\": \"^1.6.1\",\n    \"tsdown\": \"^0.22.0\",\n    \"zod\": \"^3.22.0\"\n  }}\n}}",
                "tsconfig.json": "{{\n  \"compilerOptions\": {{\n    \"target\": \"ES2022\",\n    \"module\": \"ESNext\",\n    \"moduleResolution\": \"bundler\",\n    \"strict\": true,\n    \"esModuleInterop\": true,\n    \"skipLibCheck\": true,\n    \"forceConsistentCasingInFileNames\": true\n  }},\n  \"include\": [\"src/**/*\"],\n  \"exclude\": [\"node_modules\"]\n}}",
                "tsdown.config.ts": "import {{defineConfig}} from 'tsdown'\nexport default defineConfig({{\n  entry: 'src/index.ts',\n  format: 'esm',\n  dts: true\n}})",
                "src/index.ts": "// Main entry point\n",
                "src/index.test.ts": "import {{describe, it, expect}} from 'vitest'\n\ndescribe('{pkg_name}', () => {{\n  it('should work', () => {{\n    expect(true).toBe(true)\n  }})\n}})",
            },
            "main_entry": "src/index.ts",
        },
        "go": {
            "description": "Go project with modules",
            "conventions": """- Go 1.21+ with modules
- Standard library preferred, minimal dependencies
- Use testify for tests
- Follow Go conventions (go.mod, go.sum)""",
            "package_files": {
                "go.mod": "module {pkg_name}\n\ngo 1.21\n",
                "main.go": "package main\n\nimport \"fmt\"\n\nfunc main() {{\n    fmt.Println(\"{summary}\")\n}}\n",
                "main_test.go": "package main\n\nimport \"testing\"\n\nfunc TestMain(t *testing.T) {{\n    // TODO: implement test\n}}\n",
            },
            "main_entry": "main.go",
        },
        "rust": {
            "description": "Rust project with Cargo",
            "conventions": """- Rust 1.70+ with Cargo
- Standard Cargo project structure
- Use serde for serialization
- Tests in same file or tests/ directory""",
            "package_files": {
                "Cargo.toml": "[package]\nname = \"{pkg_name}\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nserde = {{ version = \"1.0\", features = [\"derive\"] }}\n",
                "src/main.rs": "fn main() {{\n    println!(\"{summary}\");\n}}\n",
                "src/lib.rs": "// Library code\n",
                "tests/integration_test.rs": "// Integration tests\n",
            },
            "main_entry": "src/main.rs",
        },
    }

    proj = project_conventions.get(project_type, project_conventions["python"])
    
    # Extract package name from task_id
    task_id = spec.get('task_id', 'unknown')
    pkg_name = task_id.replace('-', '_').replace('/', '_')
    
    # Check if spec mentions tests
    goals_with_test = [g for g in spec.get('local_goals', [])
                       if 'test' in g.get('description', '').lower()
                       or g.get('verification', {}).get('type') == 'cli'
                       and 'test' in g.get('verification', {}).get('command', '').lower()]
    needs_test = len(goals_with_test) > 0

    system_prompt = f"""You are a senior software engineer writing code for a {proj['description']}.

CONVENTIONS:
{proj['conventions']}

OUTPUT FORMAT:
- Output a JSON object mapping file paths to file contents
- Example: {{\"src/main.py\": \"...\", \"tests/test_main.py\": \"...\"}}
- Do NOT wrap in markdown fences
- Output ONLY the JSON object

TASK SPEC:
{spec_yaml}

STAGE {stage.num}: {stage.name}
The main file to create is: {file_path}
""" + (f"\nThis project ALSO needs a test file.\n" if needs_test else "")

    user_prompt = f"""Create the project files for the feature. The main entry point is `{file_path}`.

Generate ALL required files as a JSON object:
"""

    # Add package file templates
    for fname, fcontent in proj['package_files'].items():
        # Replace placeholders
        fcontent = fcontent.replace('{pkg_name}', pkg_name)
        fcontent = fcontent.replace('{summary}', spec.get('summary', ''))
        user_prompt += f"{fname}:\n{fcontent}\n\n"

    user_prompt += f"{proj['main_entry']} (the main source file)\n"
    
    if needs_test:
        test_file = file_path.replace('main.py', 'test_main.py').replace('index.ts', 'index.test.ts').replace('.py', '_test.py')
        user_prompt += f"{test_file} (test file)\n"

    user_prompt += f"""

EXISTING FILE CONTEXT (for style matching):
{existing_context}

"""

    if error_context:
        user_prompt += f"""PREVIOUS ATTEMPT FAILED with this error:
{error_context}

Fix the issue and regenerate the files. Output ONLY the JSON object, no markdown fences.
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def generate_spec_with_llm(
    prompt: str,
    llm: LLMClient,
    project_context: dict = None,
) -> dict:
    """Generate a validated spec.yaml from a natural language prompt using the LLM.

    Args:
        prompt: Natural language feature description
        llm: LLM client
        project_context: Dict with keys: language, framework, orm, test_framework
                        (from detect_project_type or user input)
    """

    # Use the proper canonical vocabulary system prompt
    # This mirrors the spec-forge skill's SYSTEM_PROMPT but is self-contained
    # and adapts to the detected project context.

    project_context = project_context or {}
    language = project_context.get("language", "TypeScript")
    framework = project_context.get("framework", "Express")
    orm = project_context.get("orm", "Prisma")
    test_framework = project_context.get("test_framework", "Vitest")

    # Language-specific conventions for the few-shot example
    if language == "Python":
        example_paths = {
            "file_exists": "src/models/User.py",
            "cli_create": "pip install -e .",
            "cli_test": "pytest tests/",
            "http": "http://localhost:8000",
        }
        example_conventions = """- Python 3.11+ with type hints
- Use pydantic for schema validation
- Use pytest for tests
- Use pyproject.toml for packaging"""
    elif language == "Go":
        example_paths = {
            "file_exists": "internal/models/user.go",
            "cli_create": "go build ./...",
            "cli_test": "go test ./...",
            "http": "http://localhost:8080",
        }
        example_conventions = """- Go 1.21+ with modules
- Standard library preferred, minimal dependencies
- Use testify for tests
- Follow Go conventions"""
    elif language == "Rust":
        example_paths = {
            "file_exists": "src/models/user.rs",
            "cli_create": "cargo build",
            "cli_test": "cargo test",
            "http": "http://localhost:3000",
        }
        example_conventions = """- Rust 1.70+ with Cargo
- Standard Cargo project structure
- Use serde for serialization
- Tests in same file or tests/ directory"""
    else:  # TypeScript (default)
        example_paths = {
            "file_exists": "packages/api/src/routes/users.ts",
            "cli_create": "pnpm build --filter=@verified-attention/api",
            "cli_test": "pnpm test --filter=@verified-attention/api",
            "http": "http://localhost:3000",
        }
        example_conventions = """- TypeScript packages with strict mode, target ES2022, module ESNext, moduleResolution bundler
- Use zod for schema validation
- Use vitest for tests (describe, it, expect)
- Use tsdown for builds (entry: src/index.ts, format: esm, dts: true)
- Package naming: @verified-attention/<name>
- Each package has: package.json, tsconfig.json, tsdown.config.ts, src/index.ts
- Test files use src/index.test.ts"""

    # Build the system prompt with canonical vocabulary
    system_prompt = f"""You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.
Output ONLY a YAML document. No code, no commentary.

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
            Retry-After: '\\d+'          # <- single-quoted YAML so backslash is literal
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

--- PROJECT CONTEXT ---
Language: {language}
Framework: {framework}
ORM: {orm}
Test Framework: {test_framework}

Conventions:
{example_conventions}

--- FEW-SHOT EXAMPLE ---
task_id: example-feature
summary: "Example feature showing the canonical format"
depends_on: ["stage-1-core-models"]
local_goals:
  - id: L1
    description: "INSPECT: check existing model before adding endpoint"
    verification:
      type: file_exists
      path: "{example_paths['file_exists']}"
      expect:
        exists: true
  - id: L2
    description: "CREATE: add the feature endpoint"
    verification:
      type: cli
      command: "{example_paths['cli_create']}"
      expect:
        exit_code: 0
  - id: L3
    description: "VERIFY: endpoint returns correct response"
    verification:
      type: http
      method: POST
      url: "{example_paths['http']}/example"
      headers:
        Authorization: "Bearer {{test_token}}"
      expect:
        status: 200
        json_schema:
          type: object
          properties:
            id: {{ type: string }}
          required: [id]
  - id: L4
    description: "VERIFY: tests pass"
    verification:
      type: cli
      command: "{example_paths['cli_test']}"
      expect:
        exit_code: 0
global_goals_refs: ["G5", "G13"]
context:
  language: "{language}"
  framework: "{framework}"
  orm: "{orm}"
  test_framework: "{test_framework}"

Now produce ONLY the YAML specification for the following feature request.
"""

    user_prompt = f"""Generate a spec for this feature:

{prompt}

Follow the exact YAML format from the system prompt. Use "verification:" with nested "expect:" blocks. Output only YAML."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print(f"[LLM] Generating spec from prompt (context: {language}/{framework}/{orm}/{test_framework})...")
    response = llm.chat(messages, temperature=0.2)

    # Strip markdown fences if present
    response = re.sub(r'^```ya?ml\n', '', response, flags=re.MULTILINE)
    response = re.sub(r'\n```$', '', response, flags=re.MULTILINE)

    # Parse and validate
    try:
        spec = yaml.safe_load(response)
    except yaml.YAMLError as e:
        raise ValueError(f"LLM returned invalid YAML: {e}\n\nRaw response:\n{response[:1000]}")

    if not isinstance(spec, dict):
        raise ValueError(f"LLM returned non-dict spec: {type(spec)}\n\nRaw:\n{response[:500]}")

    # Validate
    errors = validate_spec(yaml.dump(spec))
    if errors:
        print(f"[LLM] ⚠️  Spec validation errors: {errors}")
        print(f"[LLM] Retrying with error context...")
        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user",
            "content": f"The spec has validation errors: {errors}\n\nFix these issues and output a corrected YAML spec."
        })
        response = llm.chat(messages, temperature=0.1)
        response = re.sub(r'^```ya?ml\n', '', response, flags=re.MULTILINE)
        response = re.sub(r'\n```$', '', response, flags=re.MULTILINE)
        spec = yaml.safe_load(response)
        errors = validate_spec(yaml.dump(spec))
        if errors:
            raise ValueError(f"Spec still invalid after retry: {errors}")

    return spec


# ============================================================
# COMMAND EXECUTOR (shell commands)
# ============================================================

def run_command(cmd: Command, config: dict, working_dir: Path) -> ExecutionResult:
    """Execute a single verify/inspect command with retries."""
    max_retries = config.get('max_retries_per_command', 3)
    timeout = config.get('command_timeout', 120)
    start_time = datetime.now()

    for attempt in range(max_retries + 1):
        print(f"  [EXEC] C{cmd.cmd_num} (attempt {attempt + 1}/{max_retries + 1}): {cmd.command[:80]}...")

        try:
            result = subprocess.run(
                cmd.command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            end_time = datetime.now()
            passed = verify_result(result, cmd.expected)

            exec_result = ExecutionResult(
                cmd=cmd, exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr,
                passed=passed, retries=attempt,
                start_time=start_time, end_time=end_time
            )

            if passed:
                print(f"    PASS")
                return exec_result
            else:
                print(f"    FAIL (exit={result.returncode}, expected={cmd.expected})")
                if result.stderr:
                    print(f"    stderr: {result.stderr.strip()[:200]}")
                if attempt < max_retries:
                    print(f"    Retrying...")
                continue

        except subprocess.TimeoutExpired:
            end_time = datetime.now()
            print(f"    TIMEOUT")
            if attempt < max_retries:
                continue
            return ExecutionResult(
                cmd=cmd, exit_code=-1, stdout="", stderr="TIMEOUT",
                passed=False, retries=attempt, start_time=start_time, end_time=end_time
            )
        except Exception as e:
            end_time = datetime.now()
            print(f"    ERROR: {e}")
            if attempt < max_retries:
                continue
            return ExecutionResult(
                cmd=cmd, exit_code=-1, stdout="", stderr=str(e),
                passed=False, retries=attempt, start_time=start_time, end_time=end_time
            )

    end_time = datetime.now()
    return ExecutionResult(
        cmd=cmd, exit_code=-1, stdout="", stderr="Max retries exceeded",
        passed=False, retries=max_retries, start_time=start_time, end_time=end_time
    )


def verify_result(result: subprocess.CompletedProcess, expected: Dict[str, Any]) -> bool:
    """Verify command result against expected assertions."""
    if not expected:
        # No expected = pass on exit 0
        return result.returncode == 0

    if 'exit_code' in expected:
        if result.returncode != expected['exit_code']:
            return False

    if 'stdout_contains' in expected:
        if expected['stdout_contains'] not in result.stdout:
            return False

    if expected.get('file_exists'):
        if result.returncode != 0:
            return False

    return True


# ============================================================
# LLM EXECUTION LOOP (create commands)
# ============================================================

def execute_create_command(
    cmd: Command,
    stage: Stage,
    spec: dict,
    llm: LLMClient,
    config: dict,
    working_dir: Path,
    existing_files: Dict[str, str],
    error_context: str = "",
    project_type: str = "unknown",
) -> ExecutionResult:
    """Execute a 'create' command by calling the LLM to generate file content."""

    write_info = parse_write_file_command(cmd.command, stage)
    mkdir_path = parse_mkdir_command(cmd.command)

    # Handle mkdir
    if mkdir_path and not write_info:
        full_path = working_dir / mkdir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  [CREATE] C{cmd.cmd_num}: mkdir -p {mkdir_path}")
        return ExecutionResult(
            cmd=cmd, exit_code=0, stdout=f"Created directory: {mkdir_path}",
            stderr="", passed=True, retries=0,
            start_time=datetime.now(), end_time=datetime.now()
        )

    # Handle write_file
    if not write_info:
        # Not a write_file command — run as shell command
        return run_command(cmd, config, working_dir)

    file_path = write_info['path']
    max_retries = config.get('max_retries_per_command', 3)

    print(f"  [CREATE] C{cmd.cmd_num}: write_file {file_path}")

    error_ctx = error_context  # Start with healing context if provided
    for attempt in range(max_retries + 1):
        print(f"    [LLM] Generating {file_path} (attempt {attempt + 1}/{max_retries + 1})...")

        try:
            messages = build_file_gen_prompt(
                file_path, spec, stage, cmd, existing_files, error_ctx,
                project_type
            )
            content = llm.chat(messages, temperature=0.2 if attempt == 0 else 0.1)

            # Strip markdown code fences if present
            content = re.sub(r'^```(?:json|ts|typescript|yaml|python|bash)?\n', '', content, flags=re.MULTILINE)
            content = re.sub(r'\n```$', '', content, flags=re.MULTILINE)

            # Try to parse as JSON object {filepath: content}
            files_written = []
            try:
                # Handle both valid JSON and Python dict-like strings (single quotes)
                # First try JSON
                try:
                    files_dict = json.loads(content)
                except json.JSONDecodeError:
                    # Try parsing as Python literal (handles single quotes)
                    import ast
                    files_dict = ast.literal_eval(content)
                
                if isinstance(files_dict, dict):
                    for fpath, fcontent in files_dict.items():
                        target = working_dir / fpath
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with open(target, 'w') as f:
                            # Write package.json as valid JSON
                            if fpath.endswith('package.json') and isinstance(fcontent, dict):
                                f.write(json.dumps(fcontent, indent=2))
                            # Write tsconfig.json as valid JSON
                            elif fpath.endswith('tsconfig.json') and isinstance(fcontent, dict):
                                f.write(json.dumps(fcontent, indent=2))
                            else:
                                f.write(fcontent if isinstance(fcontent, str) else str(fcontent))
                        files_written.append(fpath)
                        existing_files[fpath] = fcontent if isinstance(fcontent, str) else str(fcontent)
                        print(f"    [LLM] Wrote {len(fcontent if isinstance(fcontent, str) else str(fcontent))} chars to {fpath}")
                else:
                    raise ValueError("LLM returned non-dict JSON")
            except (json.JSONDecodeError, ValueError, SyntaxError):
                # Fallback: treat as single file content
                full_path = working_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
                files_written.append(file_path)
                existing_files[file_path] = content
                print(f"    [LLM] Wrote {len(content)} chars to {file_path} (raw)")

            return ExecutionResult(
                cmd=cmd, exit_code=0,
                stdout=f"Created {len(files_written)} files: {', '.join(files_written)}",
                stderr="", passed=True, retries=attempt,
                start_time=datetime.now(), end_time=datetime.now()
            )

        except json.JSONDecodeError as e:
            # Not JSON — treat as raw file content
            full_path = working_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            existing_files[file_path] = content
            print(f"    [LLM] Wrote {len(content)} chars to {file_path} (raw)")
            return ExecutionResult(
                cmd=cmd, exit_code=0,
                stdout=f"Created {file_path} ({len(content)} chars)",
                stderr="", passed=True, retries=attempt,
                start_time=datetime.now(), end_time=datetime.now()
            )

        except Exception as e:
            error_ctx = f"Error writing {file_path}: {e}"
            print(f"    [LLM] ERROR: {e}")
            if attempt < max_retries:
                print(f"    [LLM] Retrying with error context...")
                continue

            return ExecutionResult(
                cmd=cmd, exit_code=-1, stdout="", stderr=str(e),
                passed=False, retries=attempt,
                start_time=datetime.now(), end_time=datetime.now()
            )

    return ExecutionResult(
        cmd=cmd, exit_code=-1, stdout="", stderr="LLM generation failed",
        passed=False, retries=max_retries,
        start_time=datetime.now(), end_time=datetime.now()
    )


def execute_verify_command(
    cmd: Command,
    config: dict,
    working_dir: Path,
    llm: LLMClient,
    stage: Stage,
    spec: dict,
    existing_files: Dict[str, str],
    create_results: List[ExecutionResult],
    all_results: List[ExecutionResult],
) -> ExecutionResult:
    """Execute a verify command. On failure, provide LLM self-healing."""

    max_retries = config.get('max_retries_per_command', 3)

    for attempt in range(max_retries + 1):
        result = run_command(cmd, config, working_dir)

        if result.passed:
            return result

        # Self-healing: if a create command failed verification,
        # try to regenerate the file with error context
        if attempt < max_retries:
            # Find the create command this verify depends on
            # by walking the dependency chain: verify -> verify -> create
            failed_create = None
            visited = set()
            to_check = list(cmd.deps)
            while to_check:
                dep_num = to_check.pop(0)
                if dep_num in visited:
                    continue
                visited.add(dep_num)

                # Look in all_results
                dep_result = None
                for r in all_results:
                    if r.cmd.cmd_num == dep_num:
                        dep_result = r
                        break

                if not dep_result:
                    continue

                if dep_result.cmd.cmd_type == "create":
                    failed_create = dep_result
                    break
                # If it's a verify, check its deps too
                to_check.extend(dep_result.cmd.deps)

            if failed_create:
                print(f"    [HEAL] Attempting self-healing for {failed_create.cmd.cmd_num}...")
                # Build error context from the verify failure
                error_ctx = (
                    f"Verify command failed:\n"
                    f"  Command: {cmd.command}\n"
                    f"  Exit code: {result.exit_code}\n"
                    f"  stderr: {result.stderr[:500]}\n"
                    f"  stdout: {result.stdout[:500]}\n"
                    f"  Expected: {cmd.expected}\n"
                )

                # Regenerate the file with error context
                heal_result = execute_create_command(
                    failed_create.cmd, stage, spec, llm, config,
                    working_dir, existing_files, error_ctx
                )

                if heal_result.passed:
                    print(f"    [HEAL] File regenerated, re-running verify...")
                    # Update the create result in all_results
                    for i, r in enumerate(all_results):
                        if r.cmd.cmd_num == failed_create.cmd.cmd_num:
                            all_results[i] = heal_result
                            break
                    continue
            else:
                print(f"    [HEAL] No create dependency found for self-healing, retrying verify...")

    return result


# ============================================================
# EXECUTION LOG UPDATER
# ============================================================

def update_execution_log(runbook_path: Path, results: List[ExecutionResult]):
    """Update RUNBOOK.md execution log table with results."""
    with open(runbook_path) as f:
        content = f.read()

    for result in results:
        cmd_num = result.cmd.cmd_num
        start_str = result.start_time.strftime("%H:%M:%S")
        end_str = result.end_time.strftime("%H:%M:%S")
        status = "PASS" if result.passed else "FAIL"
        output = result.stdout.strip()[:100] if result.stdout else ""
        if result.stderr:
            output += f" | ERR: {result.stderr.strip()[:50]}"

        old_row = f"| {cmd_num} | {'|'.join(result.cmd.deps) if result.cmd.deps else '—'} | | | | | |"
        new_row = f"| {cmd_num} | {'|'.join(result.cmd.deps) if result.cmd.deps else '—'} | {start_str} | {end_str} | {result.exit_code} | {result.retries} | {output} |"

        content = content.replace(old_row, new_row, 1)

    # Update goal verification section
    content = update_goal_verification(content, results)

    with open(runbook_path, 'w') as f:
        f.write(content)


def update_goal_verification(content: str, results: List[ExecutionResult]) -> str:
    """Update Local Goal Checks section with PASS/FAIL."""
    # Map stages to goals
    stage_results = {}
    for r in results:
        stage_num = r.cmd.stage
        if stage_num not in stage_results:
            stage_results[stage_num] = []
        stage_results[stage_num].append(r)

    # Replace pending goal lines with actual results
    for stage_num, stage_res in stage_results.items():
        # A goal passes if all its verify commands pass
        verifies = [r for r in stage_res if r.cmd.cmd_type == 'verify']
        goal_passed = all(r.passed for r in verifies) if verifies else all(r.passed for r in stage_res)
        status = "PASS" if goal_passed else "FAIL"

        # Replace placeholder patterns
        patterns = [
            rf'(L{stage_num}:.*?)(?:PASS ✅|FAIL ❌|→ \*\*PASS\*\*|→ \*\*FAIL\*\*)',
        ]

        for pattern in patterns:
            content = re.sub(pattern, rf'\1{status}', content)

    return content


# ============================================================
# MAIN EXECUTOR
# ============================================================

def execute_runbook(
    runbook_path: Path,
    config: dict,
    spec: dict,
    llm: Optional[LLMClient],
) -> bool:
    """Execute RUNBOOK.md commands autonomously with LLM-backed self-healing."""
    print(f"[EXEC] Starting autonomous execution...")
    print(f"[EXEC] Parsing RUNBOOK: {runbook_path}")
    print(f"[EXEC] LLM: {'enabled' if llm else 'disabled (shell-only)'}")

    stages = parse_runbook(runbook_path)
    print(f"[EXEC] Found {len(stages)} with {sum(len(s.commands) for s in stages)} commands")

    # Find the project root using generic detection
    working_dir = find_project_root(Path.cwd())
    print(f"[EXEC] Working dir: {working_dir}")

    # Detect project type and get appropriate config
    project_info = detect_project_type(working_dir)
    print(f"[EXEC] Project type: {project_info['type']}")

    # Run project-specific install command if available
    if project_info["install_cmd"]:
        print(f"[EXEC] Running install: {project_info['install_cmd']}...")
        install_result = subprocess.run(
            project_info["install_cmd"],
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        if install_result.returncode != 0:
            print(f"[EXEC] WARNING: install failed: {install_result.stderr[:200]}")
        else:
            print(f"[EXEC] install completed")

    all_results = []
    existing_files: Dict[str, str] = {}

    # Pre-load existing files from working_dir for context (use project-appropriate extensions)
    for ext in project_info["context_extensions"]:
        for src_file in working_dir.rglob(f"*{ext}"):
            rel = src_file.relative_to(working_dir)
            try:
                existing_files[str(rel)] = src_file.read_text()[:3000]
            except:
                pass
            if len(existing_files) >= 15:
                break
        if len(existing_files) >= 15:
            break

    for stage in stages:
        print(f"\n[EXEC] === STAGE {stage.num}: {stage.name} ===")

        stage_results = []
        create_results: List[ExecutionResult] = []

        for cmd in stage.commands:
            # Check dependencies
            deps_passed = True
            for dep in cmd.deps:
                dep_result = next((r for r in all_results if r.cmd.cmd_num == dep), None)
                if not dep_result or not dep_result.passed:
                    print(f"  [EXEC] Dependency {dep} not satisfied, skipping {cmd.cmd_num}")
                    deps_passed = False
                    break

            if not deps_passed:
                result = ExecutionResult(
                    cmd=cmd, exit_code=-1, stdout="", stderr="Dependency failed",
                    passed=False, retries=0, start_time=datetime.now(), end_time=datetime.now()
                )
            elif cmd.cmd_type == "create" and llm:
                # LLM-backed file creation
                result = execute_create_command(
                    cmd, stage, spec, llm, config, working_dir, existing_files,
                    error_context="", project_type=project_info["type"]
                )
                if result.passed:
                    # Run project-specific install after creating new package files
                    if project_info["install_cmd"]:
                        print(f"[EXEC] Running install after package creation...")
                        install_result = subprocess.run(
                            project_info["install_cmd"],
                            shell=True,
                            cwd=working_dir,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        if install_result.returncode != 0:
                            print(f"[EXEC] WARNING: install failed: {install_result.stderr[:200]}")
                        else:
                            print(f"[EXEC] install completed")
            else:
                # Shell-only execution
                result = run_command(cmd, config, working_dir)

            stage_results.append(result)
            all_results.append(result)

            # Stop stage on verify failure
            if not result.passed and cmd.cmd_type == 'verify':
                print(f"  [EXEC] Verification failed, stage {stage.num} FAILED")
                break

        # Update log after each stage
        update_execution_log(runbook_path, stage_results)

        # Check if all stage verifications passed
        stage_verifies = [r for r in stage_results if r.cmd.cmd_type == 'verify']
        if stage_verifies and not all(r.passed for r in stage_verifies):
            print(f"[EXEC] Stage {stage.num} FAILED - stopping execution")
            return False

        print(f"[EXEC] Stage {stage.num} PASSED")

    # Final log update
    update_execution_log(runbook_path, all_results)
    print(f"\n[EXEC] All stages completed successfully!")
    return True


# ============================================================
# SPEC GENERATION
# ============================================================

def generate_spec(prompt: str, output_dir: Path, llm: Optional[LLMClient], project_context: dict = None) -> dict:
    """Generate validated spec from prompt."""
    print(f"[GEN] Generating spec from prompt...")

    spec_file = output_dir / "spec.yaml"

    if spec_file.exists():
        spec = load_spec(str(spec_file))
        print(f"[GEN] Using existing spec at {spec_file}")
    elif llm:
        # Detect project context if not provided
        if project_context is None:
            working_dir = find_project_root(Path.cwd())
            project_info = detect_project_type(working_dir)
            project_context = {
                "language": "Python" if project_info["type"] == "python" else "TypeScript",
                "framework": project_info.get("framework", "Express"),
                "orm": project_info.get("orm", "Prisma"),
                "test_framework": project_info.get("test_framework", "Vitest"),
            }
            print(f"[GEN] Detected project context: {project_context}")
        # Use built-in project-aware prompt (not spec-forge which hardcodes TypeScript)
        spec = generate_spec_with_llm(prompt, llm, project_context)
    else:
        raise ValueError(
            "No spec.yaml found and no LLM configured. "
            "Either provide a spec.yaml or configure LLM with --llm-base-url and --llm-model."
        )

    # Validate
    errors = validate_spec(yaml.dump(spec))
    if errors:
        raise ValueError(f"Spec validation failed: {errors}")

    with open(spec_file, 'w') as f:
        yaml.dump(spec, f)

    print(f"[GEN] Spec validated and saved to {spec_file}")
    return spec


def generate_plan(spec: dict, output_dir: Path) -> Path:
    """Generate PLAN.md and RUNBOOK.md."""
    print(f"[PLAN] Generating PLAN.md + RUNBOOK.md...")

    plan_path = output_dir / "PLAN.md"
    runbook_path = output_dir / "RUNBOOK.md"

    assemble_plan(spec, str(output_dir))
    assemble_runbook(spec, str(output_dir))

    print(f"[PLAN] PLAN.md written to {plan_path}")
    print(f"[PLAN] RUNBOOK.md written to {runbook_path}")

    return plan_path


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():
    """Parse command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Autonomous execution: NL prompt -> spec -> PLAN -> RUNBOOK -> LLM execution"
    )
    parser.add_argument("--prompt", type=str, help="Natural language feature description")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")

    parser.add_argument("--output", type=str, default="all",
                        choices=["spec", "plan", "plan+runbook", "all", "execute-only"],
                        help="Output mode (default: all)")
    parser.add_argument("--executor", type=str, default="python",
                        choices=["python", "hermes", "opencode"],
                        help="Execution backend (default: python)")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per command")
    parser.add_argument("--timeout", type=int, default=120, help="Command timeout (seconds)")

    # LLM configuration
    parser.add_argument("--llm-base-url", type=str, default=None,
                        help=f"LLM base URL (default: $LLM_BASE_URL or https://openrouter.ai/api/v1)")
    parser.add_argument("--llm-model", type=str, default=None,
                        help=f"LLM model name (default: $LLM_MODEL or qwen2.5-coder:7b-instruct)")
    parser.add_argument("--llm-api-key", type=str, default=None,
                        help="LLM API key (default: $LLM_API_KEY or empty for local)")
    parser.add_argument("--llm-provider", type=str, default="custom",
                        choices=["openrouter", "ollama", "openai", "custom"],
                        help="LLM provider hint (auto-sets base URL if not given)")

    # Legacy support
    parser.add_argument("--model", type=str, default=None, help="Alias for --llm-model")
    parser.add_argument("--provider", type=str, default=None, help="Alias for --llm-provider")
    parser.add_argument("--yolo", action="store_true", help="Auto-approve (passed to Hermes)")

    # Docker isolation
    parser.add_argument("--docker", action="store_true", default=False,
                        help="Run execution inside an isolated Docker container (clean environment, destroyed after)")
    parser.add_argument("--docker-image", type=str, default=None,
                        help="Use a pre-built Docker image instead of generating one (requires --docker)")
    parser.add_argument("--dockerfile-dir", type=str, default=None,
                        help="Directory containing a custom Dockerfile (requires --docker, overrides auto-generation)")

    return parser.parse_args()


def resolve_llm_config(args) -> Optional[LLMClient]:
    """Build LLMClient from args + env vars. Returns None if LLM disabled."""
    # Resolve base URL
    base_url = args.llm_base_url or os.environ.get("LLM_BASE_URL")
    provider = args.llm_provider or args.provider or "custom"

    if not base_url:
        if provider == "ollama":
            base_url = "http://localhost:11434/v1"
        elif provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "openai":
            base_url = "https://api.openai.com/v1"
        else:
            base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    # Resolve model
    model = args.llm_model or args.model or os.environ.get("LLM_MODEL", "qwen2.5-coder:7b-instruct")

    # Resolve API key
    api_key = args.llm_api_key or os.environ.get("LLM_API_KEY", "")

    # For Ollama, API key is typically empty but some clients need non-empty
    if provider == "ollama" and not api_key:
        api_key = "ollama"  # Ollama ignores this but some clients require non-empty

    print(f"[LLM] Provider: {provider}")
    print(f"[LLM] Base URL: {base_url}")
    print(f"[LLM] Model: {model}")
    print(f"[LLM] API key: {'set' if api_key else 'empty'}")

    return LLMClient(base_url=base_url, model=model, api_key=api_key)


# ============================================================
# DOCKER INTEGRATION (Gap 3 + Gap 4)
# ============================================================

# Generic Dockerfile templates per project type.
# These are generated dynamically and written to a temp dir before building.
# Each template sets up the runtime, installs deps, and mounts the project.
# The container runs autonomous_execute.py with --output execute-only,
# so spec/plan/runbook are generated on the HOST and only execution happens
# inside the container (clean environment, no host pollution).
# IMPORTANT: The build context is the OUTPUT DIRECTORY (small, only spec/plan/runbook/scripts).
# The project is MOUNTED at runtime, not copied at build time.
_DOCKERFILE_TEMPLATES = {
    "python": '''FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl git python3-yaml && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pyyaml
# Copy requirements if they exist in build context (output dir)
COPY requirements.txt ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi
# Project is mounted at /app/project at runtime
ENTRYPOINT ["python3"]
''',
    "node": '''FROM node:20-alpine
WORKDIR /app
RUN apk add --no-cache curl git
COPY package*.json ./
RUN npm install 2>/dev/null || npm ci 2>/dev/null || true
# Project is mounted at /app/project at runtime
ENTRYPOINT ["node"]
''',
    "go": '''FROM golang:1.21-alpine
WORKDIR /app
RUN apk add --no-cache curl git
COPY go.mod go.sum ./
RUN go mod download 2>/dev/null || true
# Project is mounted at /app/project at runtime
ENTRYPOINT ["go"]
''',
    "rust": '''FROM rust:1.70-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build 2>/dev/null || true
# Project is mounted at /app/project at runtime
ENTRYPOINT ["cargo"]
''',
    "unknown": '''FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*
# Project is mounted at /app/project at runtime
ENTRYPOINT ["python3"]
''',
}


def generate_dockerfile(project_type: str, output_dir: Path) -> Path:
    """Generate a Dockerfile for the detected project type.

    Writes to <output_dir>/Dockerfile.<project_type> and returns the path.
    """
    template = _DOCKERFILE_TEMPLATES.get(project_type, _DOCKERFILE_TEMPLATES["unknown"])
    dockerfile_path = output_dir / f"Dockerfile.{project_type}"
    with open(dockerfile_path, 'w') as f:
        f.write(template)
    print(f"[DOCKER] Generated Dockerfile for {project_type}: {dockerfile_path}")
    return dockerfile_path


def docker_run_pipeline(args, config: dict) -> bool:
    """Run the full autonomous pipeline inside an isolated Docker container.

    Steps:
      1. Detect project type from cwd
      2. Generate (or use provided) Dockerfile
      3. Build Docker image
      4. Run container with:
         - Output dir mounted (so spec/plan/runbook land on host)
         - LLM env vars passed through
         - --output execute-only (spec/plan generated on host first)
      5. Container auto-removed after execution (--rm)

    The host generates spec.yaml + PLAN.md + RUNBOOK.md, then only the
    EXECUTION phase runs inside Docker — keeping the host clean while
    ensuring the spec/plan are available on disk.
    """
    import shutil

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate spec + plan + runbook on the HOST (no Docker needed for this)
    print("[DOCKER] Phase 1: Generating spec + plan + runbook on host...")
    host_args = argparse.Namespace(**vars(args))
    host_args.docker = False  # Avoid recursion
    host_args.output = "plan+runbook"  # Stop before execution

    # We need an LLM client for spec generation
    llm = resolve_llm_config(args)

    # Detect project root and context for spec generation
    working_dir = find_project_root(Path.cwd())
    project_info = detect_project_type(working_dir)
    project_context = {
        "language": "Python" if project_info["type"] == "python" else "TypeScript",
        "framework": project_info.get("framework", "Express"),
        "orm": project_info.get("orm", "Prisma"),
        "test_framework": project_info.get("test_framework", "Vitest"),
    }
    print(f"[DOCKER] Project context for spec generation: {project_context}")

    try:
        spec = generate_spec(args.prompt, output_path, llm, project_context)
        with open(output_path / "spec.yaml", 'w') as f:
            yaml.dump(spec, f)
        print(f"[DOCKER] Spec saved: {output_path}/spec.yaml")

        generate_plan(spec, output_path)
        print(f"[DOCKER] Plan + Runbook generated: {output_path}/PLAN.md, {output_path}/RUNBOOK.md")
    except Exception as e:
        print(f"[DOCKER] ERROR during host-side generation: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Detect project type and generate Dockerfile
    project_info = detect_project_type(working_dir)
    project_type = project_info["type"]
    print(f"[DOCKER] Detected project type: {project_type}")

    if args.docker_image:
        image_name = args.docker_image
        print(f"[DOCKER] Using pre-built image: {image_name}")
    else:
        # Generate Dockerfile
        dockerfile_path = generate_dockerfile(project_type, output_path)

        # Also generate a .dockerignore if none exists
        dockerignore_path = working_dir / ".dockerignore"
        if not dockerignore_path.exists():
            print("[DOCKER] No .dockerignore found — generating one...")
            with open(dockerignore_path, 'w') as f:
                f.write(
                    ".venv\nnode_modules\n__pycache__\n*.pyc\n*.egg-info\n"
                    "models\n*.gguf\n*.bin\n*.safetensors\n*.pt\n*.pth\n"
                    ".git\n*.md\ndocs\ndashboard\nDockerfile*\n"
                    "docker-compose*\n.dockerignore\n*.log\n.env\n"
                )

        # Step 3: Build the Docker image
        image_name = f"autonomous-{spec.get('task_id', 'task').replace('_', '-')}-{project_type}"
        print(f"[DOCKER] Building image: {image_name}")
        
        # Build context is the output dir (small, only has spec, plan, runbook, scripts)
        # Create a minimal .dockerignore for the build context
        build_dockerignore = output_path / ".dockerignore"
        if not build_dockerignore.exists():
            with open(build_dockerignore, 'w') as f:
                f.write("*\n!Dockerfile*\n!requirements.txt\n!package.json\n!go.mod\n!Cargo.toml\n")
        
        # Ensure dependency files exist in build context to avoid COPY errors
        if project_type == "python":
            req_file = output_path / "requirements.txt"
            if not req_file.exists():
                req_file.touch()
                print(f"[DOCKER] Created empty {req_file} for build context")
        elif project_type == "node":
            pkg_file = output_path / "package.json"
            if not pkg_file.exists():
                # Create a minimal package.json
                pkg_file.write_text('{"name": "app", "private": true}\n')
                print(f"[DOCKER] Created minimal {pkg_file} for build context")
        elif project_type == "go":
            go_mod_file = output_path / "go.mod"
            if not go_mod_file.exists():
                go_mod_file.write_text("module example.com/app\ngo 1.21\n")
                print(f"[DOCKER] Created minimal {go_mod_file} for build context")
        elif project_type == "rust":
            cargo_file = output_path / "Cargo.toml"
            if not cargo_file.exists():
                cargo_file.write_text('[package]\nname = "app"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n')
                print(f"[DOCKER] Created minimal {cargo_file} for build context")

        build_cmd = [
            "docker", "build",
            "-t", image_name,
            "-f", str(dockerfile_path),
            str(output_path)  # Build context is output dir (small)
        ]
        print(f"[DOCKER] Running: {' '.join(build_cmd)}")
        build_result = subprocess.run(
            build_cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 min max for build
        )
        if build_result.returncode != 0:
            print(f"[DOCKER] BUILD FAILED (exit {build_result.returncode})")
            print(build_result.stderr[:2000])
            return False
        print(f"[DOCKER] Image built successfully")

    # Step 4: Run execution inside the container
    # Mount the output dir so results land on the host
    # Also mount the project so the executor can read source files
    abs_output = output_path.resolve()
    abs_project = working_dir.resolve()

    # Build the command to run inside the container
    # We run the same script with --output execute-only
    inner_cmd = [
        "/app/scripts/autonomous_execute.py",
        "--output-dir", "/app/output",
        "--output", "execute-only",
        "--executor", "python",
        "--max-retries", str(args.max_retries),
        "--timeout", str(args.timeout),
    ]

    # Pass through LLM config
    llm_base_url = os.environ.get("LLM_BASE_URL", "")
    llm_model = os.environ.get("LLM_MODEL", "qwen2.5-coder:7b-instruct")
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    if args.llm_base_url:
        llm_base_url = args.llm_base_url
    if args.llm_model or args.model:
        llm_model = args.llm_model or args.model
    if args.llm_api_key:
        llm_api_key = args.llm_api_key

    # For Ollama running on host, the container needs host.docker.internal
    # Build the command to run inside the container
        # We run the same script with --output execute-only
        inner_cmd = [
            "/app/skill/scripts/autonomous_execute.py",
            "--output-dir", "/app/output",
            "--output", "execute-only",
            "--executor", "python",
            "--max-retries", str(args.max_retries),
            "--timeout", str(args.timeout),
        ]

        # Docker run command
                # Docker run command
        docker_run_cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_output}:/app/output",
            "-v", f"{abs_project}:/app/project",
            "-v", f"{SKILL_ROOT}:/app/skill",
            "-e", f"LLM_BASE_URL={llm_base_url}",
            "-e", f"LLM_MODEL={llm_model}",
            "-e", f"LLM_API_KEY={llm_api_key}",
            "-e", f"PYTHONPATH=/app/skill/spec-forge/scripts:/app/skill/software-development/command-runway-planner/scripts:/app/skill/software-development/command-runway-autonomous/scripts:$PYTHONPATH",
            "--workdir", "/app/project",
            image_name,
        ] + inner_cmd

    print(f"[DOCKER] Running execution inside container...")
    print(f"[DOCKER] Image: {image_name}")
    print(f"[DOCKER] Mount: {abs_output} -> /app/output")
    print(f"[DOCKER] Mount: {abs_project} -> /app/project")
    print()

    try:
        run_result = subprocess.run(
            docker_run_cmd,
            timeout=args.timeout * 10,  # Allow more time inside container
        )
        if run_result.returncode == 0:
            print(f"\n[DOCKER] Execution completed successfully")
            print(f"[DOCKER] Container auto-removed (--rm)")
            print(f"\nFULL DELIVERY COMPLETE")
            print(f"   Spec: {args.output_dir}/spec.yaml")
            print(f"   Plan: {args.output_dir}/PLAN.md")
            print(f"   Runbook: {args.output_dir}/RUNBOOK.md (with execution log)")
            return True
        else:
            print(f"\n[DOCKER] Execution FAILED (exit {run_result.returncode})")
            print(f"[DOCKER] Container auto-removed (--rm)")
            return False
    except subprocess.TimeoutExpired:
        print(f"\n[DOCKER] Execution TIMED OUT")
        return False
    except Exception as e:
        print(f"\n[DOCKER] Error: {e}")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    if args.output != "execute-only" and not args.prompt:
        print("Error: --prompt required (except for --output execute-only)")
        sys.exit(2)

    output_dir = args.output_dir
    output_mode = args.output
    executor = args.executor

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Update config with CLI args
    config = load_config()
    config['max_retries_per_command'] = args.max_retries
    config['command_timeout'] = args.timeout

    # Build LLM client
    llm = resolve_llm_config(args)

    print(f"PIPELINE STARTED")
    print(f"   Prompt: {args.prompt or 'N/A (execute-only)'}")
    print(f"   Output: {output_dir}")
    print(f"   Mode: {output_mode}")
    print(f"   Executor: {executor}")
    print(f"   LLM: {'enabled' if llm else 'disabled'}")
    if args.docker:
        print(f"   Docker: ISOLATED (clean container, auto-destroyed)")
    print()

    # --- DOCKER PATH ---
    # If --docker is set, dispatch to the Docker integration which:
    #   1. Generates spec + plan + runbook on the host
    #   2. Builds a Docker image based on detected project type
    #   3. Runs execution inside the container
    #   4. Auto-removes the container (--rm)
    if args.docker:
        success = docker_run_pipeline(args, config)
        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    try:
        # Step 1: Generate spec (skip for execute-only)
        if output_mode != "execute-only":
            # Detect project context for spec generation
            working_dir = find_project_root(Path.cwd())
            project_info = detect_project_type(working_dir)
            project_context = {
                "language": "Python" if project_info["type"] == "python" else "TypeScript",
                "framework": project_info.get("framework", "Express"),
                "orm": project_info.get("orm", "Prisma"),
                "test_framework": project_info.get("test_framework", "Vitest"),
            }
            print(f"[GEN] Project context: {project_context}")

            spec = generate_spec(args.prompt, output_path, llm, project_context)

            spec_file = output_path / "spec.yaml"
            with open(spec_file, 'w') as f:
                yaml.dump(spec, f)
            print(f"[GEN] Spec saved to {spec_file}")

            if output_mode == "spec":
                print(f"\nSPEC MODE COMPLETE")
                print(f"   Spec: {output_dir}/spec.yaml")
                return

            # Step 2: Generate PLAN.md + RUNBOOK.md
            generate_plan(spec, output_path)
            print(f"\nPLAN.md available at: {output_dir}/PLAN.md")

            if output_mode == "plan":
                print(f"\nPLAN MODE COMPLETE")
                return

            print(f"[PLAN] RUNBOOK.md written to {output_dir}/RUNBOOK.md")

            if output_mode == "plan+runbook":
                print(f"\nPLAN+RUNBOOK MODE COMPLETE")
                print(f"   Plan: {output_dir}/PLAN.md")
                print(f"   Runbook: {output_dir}/RUNBOOK.md")
                return
        else:
            # execute-only: load existing spec
            spec_file = output_path / "spec.yaml"
            if spec_file.exists():
                spec = load_spec(str(spec_file))
            else:
                print(f"[WARN] No spec.yaml found, using empty spec for execute-only")
                spec = {"task_id": "execute-only", "summary": "", "local_goals": []}

        # Step 3: Execute RUNBOOK.md
        runbook_path = output_path / "RUNBOOK.md"
        if not runbook_path.exists():
            print(f"Error: RUNBOOK.md not found at {runbook_path}")
            sys.exit(1)

        # Select executor
        if executor == "hermes":
            success = execute_with_hermes(runbook_path, args)
        elif executor == "opencode":
            success = execute_with_opencode(runbook_path, args)
        else:
            success = execute_runbook(runbook_path, config, spec, llm)

        if success:
            print(f"\nFULL DELIVERY COMPLETE")
            print(f"   Spec: {output_dir}/spec.yaml")
            print(f"   Plan: {output_dir}/PLAN.md")
            print(f"   Runbook: {output_dir}/RUNBOOK.md (with execution log)")
        else:
            print(f"\nEXECUTION FAILED")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================
# EXECUTOR BACKENDS
# ============================================================

def execute_with_hermes(runbook_path: Path, args) -> bool:
    """Execute RUNBOOK using Hermes agent."""
    import shlex

    print(f"[EXEC] Running with Hermes agent...")

    with open(runbook_path) as f:
        runbook_content = f.read()

    prompt = f"""Execute the COMMAND_RUNWAY runbook at {runbook_path}.

Read the runbook and execute each command in the command runway table in order.
Verify each command's expected result. On failure, diagnose and retry up to 3 times.
Update the execution log in the runbook as you go.

Runbook content:
{runbook_content[:8000]}
"""

    model = args.llm_model or args.model or "qwen2.5-coder:7b-instruct"
    provider = args.llm_provider or args.provider or "openrouter"

    cmd = [
        "hermes", "chat",
        "-q", prompt,
        "-m", model,
        "--provider", provider
    ]

    if args.yolo:
        cmd.append("--yolo")

    print(f"[EXEC] Running: hermes chat -q '...' -m {model}")

    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("[EXEC] Hermes timed out")
        return False
    except Exception as e:
        print(f"[EXEC] Hermes failed: {e}")
        return False


def execute_with_opencode(runbook_path: Path, args) -> bool:
    """Execute RUNBOOK using OpenCode agent."""
    print(f"[EXEC] Running with OpenCode agent...")

    with open(runbook_path) as f:
        runbook_content = f.read()

    prompt = f"""Execute this COMMAND_RUNWAY runbook:
{runbook_path}

Runbook content:
{runbook_content[:8000]}

Execute each command. Verify results. Retry on failure (max 3x). Update execution log.
"""

    cmd = ["opencode", "run", prompt]

    try:
        result = subprocess.run(cmd, timeout=600, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("[EXEC] OpenCode timed out")
        return False
    except Exception as e:
        print(f"[EXEC] OpenCode failed: {e}")
        return False


if __name__ == "__main__":
    import yaml
    main()