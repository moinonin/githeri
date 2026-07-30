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
# Provider: "ollama" | "openai" | "nvidia" | "anthropic" | "openai-compat"
PROVIDER = "ollama"

# Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b-nr-instruct"

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
    "FEW-SHOT EXAMPLE (ENRICHED) ---\n"
    "Request: \"Implement JWT authentication with login endpoint, User model, and token refresh. Enforce password hashing with bcrypt (cost 12). JWT tokens expire in 15 min, refresh tokens in 7 days. Store refresh token hashes in DB.\"\n"
    "\n"
    "Spec YAML:\n"
    "```yaml\n"
    "task_id: jwt-auth-login\n"
    "summary: \"JWT authentication with login, refresh, and secure password handling\"\n"
    "depends_on: [\"stage-1-core-models\", \"stage-2-pipeline\"]\n"
    "business_rules:\n"
    "  - name: \"JWT Secret\"\n"
    "    formula: \"256-bit random, rotated quarterly, stored in vault\"\n"
    "  - name: \"Access Token Expiry\"\n"
    "    formula: \"15 minutes sliding window\"\n"
    "  - name: \"Refresh Token Expiry\"\n"
    "    formula: \"7 days, single-use, rotated on each refresh\"\n"
    "  - name: \"Password Hashing\"\n"
    "    formula: \"bcrypt with cost factor 12, constant-time comparison\"\n"
    "test_fixtures:\n"
    "  - name: \"seed-admin-user\"\n"
    "    setup_commands:\n"
    "      - \"python scripts/seed_admin.py --email admin@example.com --password 'SecurePass123!'\"\n"
    "      - \"python scripts/create_refresh_token.py --user admin@example.com --days 7\"\n"
    "    teardown_commands:\n"
    "      - \"python scripts/cleanup_admin.py --email admin@example.com\"\n"
    "environment:\n"
    "  packages:\n"
    "    - \"pyyaml>=6.0\"\n"
    "    - \"jsonschema>=4.0\"\n"
    "    - \"bcrypt>=4.0\"\n"
    "    - \"pyjwt>=2.8\"\n"
    "  env_vars:\n"
    "    JWT_SECRET: \"test-secret-1234567890abcdef\"\n"
    "    DATABASE_URL: \"postgresql://user:testpass@localhost:5432/app\"\n"
    "    BCRYPT_COST: \"12\"\n"
    "  services: []\n"
    "global_verification:\n"
    "  - \"pytest tests/auth/ -v --tb=short\"\n"
    "  - \"bandit -r src/auth/ -f json -o bandit-report.json\"\n"
    "  - \"pytest tests/ -k 'not integration' --maxfail=5\"\n"
    "local_goals:\n"
    "  - id: L1\n"
    "    description: \"INSPECT: check existing user model and auth routes before adding JWT\"\n"
    "    verification:\n"
    "      type: file_exists\n"
    "      path: \"src/models/User.py\"\n"
    "      expect:\n"
    "        exists: true\n"
    "  - id: L2\n"
    "    description: \"INSPECT: check existing auth middleware structure\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"cat src/middleware/auth.py\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L3\n"
    "    description: \"CREATE: add User model extensions (password_hash, refresh_token_hash, last_login)\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      class User(Base):\n"
    "          __tablename__ = 'users'\n"
    "          id = Column(Integer, primary_key=True)\n"
    "          email = Column(String(255), unique=True, nullable=False, index=True)\n"
    "          password_hash = Column(String(255), nullable=False)  # bcrypt hash\n"
    "          refresh_token_hash = Column(String(255), nullable=True, index=True)  # hashed refresh token\n"
    "          last_login = Column(DateTime, nullable=True)\n"
    "          is_active = Column(Boolean, default=True)\n"
    "          created_at = Column(DateTime, default=datetime.utcnow)\n"
    "          \n      def set_password(self, password: str):\n"
    "          self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))\n"
    "      \n      def check_password(self, password: str) -> bool:\n"
    "          return bcrypt.checkpw(password.encode(), self.password_hash.encode())\n"
    "      \n      def set_refresh_token(self, token: str):\n"
    "          self.refresh_token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt(rounds=12))\n"
    "      \n      def verify_refresh_token(self, token: str) -> bool:\n"
    "          return bcrypt.checkpw(token.encode(), self.refresh_token_hash.encode())\n"
    "    verification:\n"
    "      type: file_exists\n"
    "      path: \"src/models/User.py\"\n"
    "      expect:\n"
    "        content_contains: [\"password_hash\", \"refresh_token_hash\", \"bcrypt\", \"set_password\", \"check_password\"]\n"
    "    acceptance_criteria:\n"
    "      - test: \"User model has required fields\"\n"
    "        steps: \"Check User class has password_hash, refresh_token_hash, last_login, is_active\"\n"
    "      - test: \"Password hashing uses bcrypt cost 12\"\n"
    "        steps: \"Verify set_password uses bcrypt.gensalt(rounds=12)\"\n"
    "  - id: L4\n"
    "    description: \"CREATE: implement JWT token service (issue, verify, refresh)\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      import jwt\n"
    "      from datetime import datetime, timedelta\n"
    "      from typing import Optional\n"
    "      \n"
    "      class JWTService:\n"
    "          def __init__(self, secret: str, access_expiry_min: int = 15, refresh_expiry_days: int = 7):\n"
    "              self.secret = secret\n"
    "              self.access_expiry = timedelta(minutes=access_expiry_min)\n"
    "              self.refresh_expiry = timedelta(days=refresh_expiry_days)\n"
    "          \n"
    "          def create_access_token(self, user_id: int, email: str) -> str:\n"
    "              payload = {\n"
    "                  'sub': user_id,\n"
    "                  'email': email,\n"
    "                  'type': 'access',\n"
    "                  'iat': datetime.utcnow(),\n"
    "                  'exp': datetime.utcnow() + self.access_expiry\n"
    "              }\n"
    "              return jwt.encode(payload, self.secret, algorithm='HS256')\n"
    "          \n"
    "          def create_refresh_token(self, user_id: int) -> str:\n"
    "              payload = {\n"
    "                  'sub': user_id,\n"
    "                  'type': 'refresh',\n"
    "                  'iat': datetime.utcnow(),\n"
    "                  'exp': datetime.utcnow() + self.refresh_expiry\n"
    "              }\n"
    "              return jwt.encode(payload, self.secret, algorithm='HS256')\n"
    "          \n"
    "          def verify_token(self, token: str, expected_type: str = 'access') -> Optional[dict]:\n"
    "              try:\n"
    "                  payload = jwt.decode(token, self.secret, algorithms=['HS256'])\n"
    "                  if payload.get('type') != expected_type:\n"
    "                      return None\n"
    "                  return payload\n"
    "              except jwt.PyJWTError:\n"
    "                  return None\n"
    "    verification:\n"
    "      type: file_exists\n"
    "      path: \"src/services/jwt_service.py\"\n"
    "      expect:\n"
    "        content_contains: [\"create_access_token\", \"create_refresh_token\", \"verify_token\", \"HS256\", \"exp\"]\n"
    "    acceptance_criteria:\n"
    "      - test: \"Access token expires in 15 minutes\"\n"
    "        steps: \"Create token -> decode -> assert exp - iat == 15 min\"\n"
    "      - test: \"Refresh token expires in 7 days\"\n"
    "        steps: \"Create refresh token -> decode -> assert exp - iat == 7 days\"\n"
    "      - test: \"Token type validation works\"\n"
    "        steps: \"Try verify access token as refresh type -> expect None\"\n"
    "  - id: L5\n"
    "    description: \"CREATE: add POST /auth/login endpoint with JWT response\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      @app.post('/auth/login')\n"
    "      async def login(credentials: LoginRequest, db: Session = Depends(get_db)):\n"
    "          user = db.query(User).filter(User.email == credentials.email).first()\n"
    "          if not user or not user.check_password(credentials.password):\n"
    "              raise HTTPException(401, 'Invalid credentials')\n"
    "          if not user.is_active:\n"
    "              raise HTTPException(403, 'Account disabled')\n"
    "          \n"
    "          jwt_service = JWTService(settings.JWT_SECRET)\n"
    "          access_token = jwt_service.create_access_token(user.id, user.email)\n"
    "          refresh_token = jwt_service.create_refresh_token(user.id)\n"
    "          \n"
    "          user.set_refresh_token(refresh_token)\n"
    "          user.last_login = datetime.utcnow()\n"
    "          db.commit()\n"
    "          \n"
    "          return {\n"
    "              'access_token': access_token,\n"
    "              'refresh_token': refresh_token,\n"
    "              'token_type': 'bearer',\n"
    "              'expires_in': 900\n"
    "          }\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/auth/login\"\n"
    "      body:\n"
    "        email: \"admin@example.com\"\n"
    "        password: \"SecurePass123!\"\n"
    "      expect:\n"
    "        status: 200\n"
    "        json_schema:\n"
    "          type: object\n"
    "          properties:\n"
    "            access_token: {type: string}\n"
    "            refresh_token: {type: string}\n"
    "            token_type: {type: string, enum: ['bearer']}\n"
    "            expires_in: {type: integer}\n"
    "          required: [access_token, refresh_token, token_type, expires_in]\n"
    "    acceptance_criteria:\n"
    "      - test: \"Valid credentials return access + refresh tokens\"\n"
    "        steps: \"POST /auth/login with valid creds -> 200 + both tokens present\"\n"
    "      - test: \"Invalid password returns 401\"\n"
    "        steps: \"POST /auth/login with wrong password -> 401\"\n"
    "      - test: \"Inactive user returns 403\"\n"
    "        steps: \"POST /auth/login with is_active=False user -> 403\"\n"
    "  - id: L6\n"
    "    description: \"CREATE: add POST /auth/refresh endpoint for token rotation\"\n"
    "    type: create\n"
    "    blueprint: |\n"
    "      @app.post('/auth/refresh')\n"
    "      async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):\n"
    "          jwt_service = JWTService(settings.JWT_SECRET)\n"
    "          payload = jwt_service.verify_token(request.refresh_token, 'refresh')\n"
    "          if not payload:\n"
    "              raise HTTPException(401, 'Invalid or expired refresh token')\n"
    "          \n"
    "          user = db.query(User).filter(User.id == payload['sub']).first()\n"
    "          if not user or not user.verify_refresh_token(request.refresh_token):\n"
    "              raise HTTPException(401, 'Refresh token revoked or invalid')\n"
    "          \n"
    "          # Rotate: issue new access + refresh, invalidate old refresh\n"
    "          new_access = jwt_service.create_access_token(user.id, user.email)\n"
    "          new_refresh = jwt_service.create_refresh_token(user.id)\n"
    "          user.set_refresh_token(new_refresh)\n"
    "          db.commit()\n"
    "          \n"
    "          return {\n"
    "              'access_token': new_access,\n"
    "              'refresh_token': new_refresh,\n"
    "              'token_type': 'bearer',\n"
    "              'expires_in': 900\n"
    "          }\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/auth/refresh\"\n"
    "      body:\n"
    "        refresh_token: \"{{valid_refresh_token}}\"\n"
    "      expect:\n"
    "        status: 200\n"
    "        json_schema:\n"
    "          type: object\n"
    "          properties:\n"
    "            access_token: {type: string}\n"
    "            refresh_token: {type: string}\n"
    "            token_type: {type: string, enum: ['bearer']}\n"
    "            expires_in: {type: integer}\n"
    "          required: [access_token, refresh_token, token_type, expires_in]\n"
    "    acceptance_criteria:\n"
    "      - test: \"Valid refresh token returns new token pair\"\n"
    "        steps: \"POST /auth/refresh with valid token -> 200 + new access + new refresh\"\n"
    "      - test: \"Old refresh token cannot be reused (rotation)\"\n"
    "        steps: \"POST /auth/refresh with same token twice -> second call returns 401\"\n"
    "      - test: \"Expired refresh token returns 401\"\n"
    "        steps: \"Wait for expiry -> POST /auth/refresh -> 401\"\n"
    "  - id: L7\n"
    "    description: \"VERIFY: login endpoint rejects invalid credentials with 401\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/auth/login\"\n"
    "      body:\n"
    "        email: \"admin@example.com\"\n"
    "        password: \"WrongPassword\"\n"
    "      expect:\n"
    "        status: 401\n"
    "  - id: L8\n"
    "    description: \"VERIFY: refresh endpoint enforces token rotation\"\n"
    "    verification:\n"
    "      type: http\n"
    "      method: POST\n"
    "      url: \"http://localhost:8000/auth/refresh\"\n"
    "      body:\n"
    "        refresh_token: \"{{used_refresh_token}}\"\n"
    "      expect:\n"
    "        status: 401\n"
    "  - id: L9\n"
    "    description: \"VERIFY: auth test suite passes\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"pytest tests/auth/ -v --tb=short\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "  - id: L10\n"
    "    description: \"VERIFY: security scan passes (no high-severity issues)\"\n"
    "    verification:\n"
    "      type: cli\n"
    "      command: \"bandit -r src/auth/ -ll -f json -o bandit-report.json && jq '.results | map(select(.severity==\"HIGH\")) | length' bandit-report.json\"\n"
    "      expect:\n"
    "        exit_code: 0\n"
    "        stdout_contains: \"0\"\n"
    "business_rules:\n"
    "  - name: \"JWT Secret\"\n"
    "    formula: \"256-bit random, rotated quarterly, stored in vault\"\n"
    "  - name: \"Access Token Expiry\"\n"
    "    formula: \"15 minutes sliding window\"\n"
    "  - name: \"Refresh Token Expiry\"\n"
    "    formula: \"7 days, single-use, rotated on each refresh\"\n"
    "  - name: \"Password Hashing\"\n"
    "    formula: \"bcrypt with cost factor 12, constant-time comparison\"\n"
    "test_fixtures:\n"
    "  - name: \"seed-admin-user\"\n"
    "    setup_commands:\n"
    "      - \"python scripts/seed_admin.py --email admin@example.com --password 'SecurePass123!'\"\n"
    "      - \"python scripts/create_refresh_token.py --user admin@example.com --days 7\"\n"
    "    teardown_commands:\n"
    "      - \"python scripts/cleanup_admin.py --email admin@example.com\"\n"
    "environment:\n"
    "  packages:\n"
    "    - \"pyyaml>=6.0\"\n"
    "    - \"jsonschema>=4.0\"\n"
    "    - \"bcrypt>=4.0\"\n"
    "    - \"pyjwt>=2.8\"\n"
    "  env_vars:\n"
    "    JWT_SECRET: \"test-secret-1234567890abcdef\"\n"
    "    DATABASE_URL: \"postgresql://user:testpass@localhost:5432/app\"\n"
    "    BCRYPT_COST: \"12\"\n"
    "  services: []\n"
    "global_verification:\n"
    "  - \"pytest tests/auth/ -v --tb=short\"\n"
    "  - \"bandit -r src/auth/ -f json -o bandit-report.json\"\n"
    "  - \"pytest tests/ -k 'not integration' --maxfail=5\"\n"
    "global_goals_refs: [\"G5\", \"G13\", \"G17\"]\n"
    "context:\n"
    "  language: Python\n"
    "  framework: FastAPI\n"
    "  orm: SQLAlchemy\n"
    "  test_framework: pytest\n"
    "```\n"
)

# Now build SYSTEM_PROMPT using concatenation instead of .format() to avoid brace conflicts
SYSTEM_PROMPT = (
    "You are a precise specification generator for a project that uses the COMMAND_RUNWAY methodology.\n"
    "Output ONLY a YAML document. No code, no commentary.\n"
    "\n"
    "--- PROJECT SKILL (Command Runway Pattern) ---\n"
    + SKILL_CONTEXT + "\n"
    "\n"
    "--- YAML SPEC FORMAT ---\n"
    "The YAML must contain these exact top-level fields, in this order:\n"
    "task_id: string\n"
    "summary: string\n"
    "depends_on: list of strings (optional)\n"
    "business_rules: list of objects (REQUIRED, even if empty list [])\n"
    "test_fixtures: list of objects (REQUIRED, even if empty list [])\n"
    "environment: object with packages, env_vars, services (REQUIRED)\n"
    "global_verification: list of strings (REQUIRED, even if empty list [])\n"
    "local_goals: list of objects with id, description, verification\n"
    "global_goals_refs: list of strings (optional, must reference existing global goals G1-G19)\n"
    "context: object with keys: language, framework, orm, test_framework\n"
    "\n"
    "--- REQUIRED ENRICHMENT FIELDS (IMPROVE_SPEC) ---\n"
    "The following top-level fields are REQUIRED in every spec (must be present, can be empty lists/dicts):\n"
    "  business_rules: list of objects, each with 'name' (string) and 'formula' (string)\n"
    "    Example: [{name: 'JWT Secret', formula: '256-bit random, rotated quarterly, stored in vault'}]\n"
    "  test_fixtures: list of objects, each with 'name' (string), 'setup_commands' (list of strings), and 'teardown_commands' (list of strings)\n"
    "    Example: [{name: 'seed-admin', setup_commands: ['python scripts/seed_admin.py'], teardown_commands: []}]\n"
    "  environment: object with 'packages' (list of strings), 'env_vars' (dict), 'services' (list)\n"
    "    Example: {packages: ['pyyaml>=6.0', 'jsonschema>=4.0'], env_vars: {OLLAMA_URL: 'http://localhost:11434'}, services: []}\n"
    "  global_verification: list of command strings (run after all local goals pass)\n"
    "    Example: ['pytest tests/', 'bandit -r src/']\n"
    "\n"
    "For each local_goal, verification must follow these rules:\n"
    "- type: http | cli | file_exists | manual\n"
    "- MINIMUM 2 local_goals per spec (more is fine; 1 is never enough).\n"
    "- Every goal MUST have an 'id' field (e.g., L1, L2, L3...) and a 'description' field.\n"
    "- Every goal must verify a DISTINCT aspect.  Do NOT pad with near-duplicate\n"
    "  goals that hit the same endpoint or same file path twice.  If two goals\n"
    "  share the same (type, method, url) or (type, path) or (type, command),\n"
    "  they are near-duplicates and the spec will be rejected.\n"
    "\n"
    "Canonical `expect` keys (use ONLY these -- unknown keys are rejected):\n"
    "  http:        status (required), body_regex, body_contains, json_schema, headers_contain, content_type\n"
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
    "    YAML double quotes reject backslash escapes like \\d, \\w, \\s.\n"
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
    "--- LOCAL GOAL ENHANCEMENTS (IMPROVE_SPEC) ---\n"
    "Each local_goal MAY include these additional fields:\n"
    "  blueprint: string (REQUIRED for goals with type: 'create' - min 100 chars)\n"
    "    A code-level outline: class/function signatures, SQLAlchemy models, route decorators,\n"
    "    business logic steps. This is what the executor translates into working code.\n"
    "    Example for CREATE goal: 'class User(Base): ... @app.post(\"/users\") async def create_user(...): ...'\n"
    "  acceptance_criteria: list of objects with 'test' (description) and 'steps' (pseudo-code/test instructions)\n"
    "    Example: [{test: 'User created returns 201', steps: 'POST /users with valid data -> assert 201 + user in response'}]\n"
    "    CRITICAL: acceptance_criteria is a LOCAL GOAL FIELD (inside each goal under local_goals),\n"
    "    NOT a top-level field. Put it at the same level as 'id', 'description', 'verification'.\n"
    "  type: 'create' | 'update' | 'delete' | 'inspect' | 'verify' (optional, but recommended for CREATE)\n"
    "    If type == 'create', blueprint is MANDATORY and must be >= 100 characters.\n"
    "\n"
    "VALID VERIFICATION TYPES (only these four are allowed):\n"
    "  - cli: command-line execution with exit_code and stdout checks\n"
    "  - file_exists: check file existence and content\n"
    "  - http: HTTP request with status, headers, body checks\n"
    "  - manual: human verification (description only, no expect block)\n"
    "DO NOT use 'db', 'api', 'custom', or any other type - they will be rejected.\n"
    "\n"
    "CRITICAL: local_goals MUST be a list of OBJECTS (dicts), NOT plain strings.\n"
    "Each goal MUST have 'id' (e.g. L1, L2, L3...) and 'description' and 'verification' keys.\n"
    "WRONG (will be rejected):\n"
    "  local_goals:\n"
    "    - Do something\n"
    "    - Do another thing\n"
    "CORRECT:\n"
    "  local_goals:\n"
    "    - id: L1\n"
    "      description: \"INSPECT: check existing files\"\n"
    "      verification:\n"
    "        type: cli\n"
    "        command: \"ls src/\"\n"
    "        expect:\n"
    "          exit_code: 0\n"
    "    - id: L2\n"
    "      description: \"CREATE: add User model\"\n"
    "      type: create\n"
    "      blueprint: |\n"
    "        class User(Base):\n"
    "            id = Column(Integer, primary_key=True)\n"
    "            email = Column(String(255))\n"
    "            ...(more fields and methods, must be >= 100 chars total)\n"
    "      verification:\n"
    "        type: file_exists\n"
    "        path: \"src/models/User.py\"\n"
    "        expect:\n"
    "          exists: true\n"
    "    - id: L3\n"
    "      description: \"VERIFY: test endpoint returns expected response\"\n"
    "      verification:\n"
    "        type: http\n"
    "        method: GET\n"
    "        url: \"http://localhost:8000/health\"\n"
    "        expect:\n"
    "          status: 200\n"
    "No goal may be a bare string. Every goal must be a map (dict) with at least id, description, and verification.\n"
    "\n"
    "--- FEW-SHOT EXAMPLE (ENRICHED) ---\n"
    + FEW_SHOT_EXAMPLE + "\n"
    "IMPORTANT: The output MUST be a complete YAML document with ALL required top-level fields:\n"
    "  task_id, summary, depends_on (optional), local_goals, global_goals_refs (optional), context,\n"
    "  business_rules (REQUIRED, can be []), test_fixtures (REQUIRED, can be []),\n"
    "  environment (REQUIRED, can be {packages: [], env_vars: {}, services: []}), global_verification (REQUIRED, can be [])\n"
    "Do NOT output just a list of goals.\n"
    "\n"
    "CRITICAL YAML FORMATTING RULES (violations cause immediate rejection):\n"
    "1. QUOTING: Any string containing colons (:), @, #, *, &, !, %, |, >, or starting with a\n"
    "   reserved character MUST be double-quoted. When in doubt, double-quote ALL string values.\n"
    "   - summary: \"CREATE: add User model\" (NOT: summary: CREATE: add User model)\n"
    "   - description: \"INSPECT: check existing model\" (NOT: description: INSPECT: check existing model)\n"
    "2. NO INLINE COMMENTS after quoted values on the same line.\n"
    "   - value: \"0 8 * * *\" (CORRECT -- the value is the whole string)\n"
    "   - value: \"0 8 * * *\" (cron expression) (WRONG -- the trailing text breaks the parser)\n"
    "   If you need a comment, put it on its OWN line with # at the start.\n"
    "3. BLUEPRINT CODE must be inside a YAML block scalar (use the | indicator and indent 2+ spaces).\n"
    "   Never put code with @, *, or special chars as a plain YAML value.\n"
    "   blueprint: |                       # <- block scalar indicator\n"
    "     @app.route('/api/report')         # <- indented under the block, safe\n"
    "     def get_report(): ...\n"
    "   Never do:  blueprint: @app.route('/api/report')  (WRONG -- @ breaks YAML)\n"
    "4. NEVER start a YAML value with @, *, &, !, %, #, |, >, or backtick. Quote it or use a block scalar.\n"
    "5. INDENTATION: All keys under a list item (- key) must be indented consistently (usually 6 spaces\n"
    "   for the first key after the dash+space, then 6 for siblings, 8 for nested).\n"
    "   - id: L1                          # <- 'id' aligned after '- '\n"
    "     description: \"some desc\"        # <- same column as 'id'\n"
    "     verification:                    # <- same column as 'id'\n"
    "       type: cli                      # <- +2 spaces under verification\n"
    "       command: \"pytest\"             # <- +2 spaces under verification\n"
    "       expect:                       # <- +2 spaces under verification\n"
    "         exit_code: 0                # <- +2 spaces under expect\n"
    "   Do NOT dedent a sibling key to a different column.\n"
    "6. CRON EXPRESSIONS must be double-quoted: schedule: \"0 8 * * *\" (never bare -- * breaks YAML).\n"
    "7. NO TOP-LEVEL 'description' FIELD. Use summary for the high-level description.\n"
    "   The word 'description' only appears inside individual local_goals.\n"
    "8. NO '---' at the start. Begin directly with task_id: as the first line.\n"
    "9. NO 'name:' at the top level. The top-level identifier is 'task_id', not 'name'.\n"
    "10. NO PLACEHOLDERS in env_vars: DATABASE_URL must be a concrete test value.\n"
    "    WRONG: DATABASE_URL: \"postgresql://user:***@localhost:5432/app\"\n"
    "    CORRECT: DATABASE_URL: \"postgresql://user:testpass@localhost:5432/app\"\n"
    "11. The YAML must be valid and parseable by yaml.safe_load().\n"
    "\n"
    "Now produce ONLY the YAML specification for the following feature request.\n"
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
    elif PROVIDER in ("openai", "openai-compat", "nvidia"):
        return _call_openai_compat(system_prompt, user_prompt)
    elif PROVIDER == "anthropic":
        return _call_anthropic(system_prompt, user_prompt)
    else:
        raise ValueError(f"Unknown PROVIDER: {PROVIDER}")

def _call_ollama(system_prompt, user_prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
        },
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["response"]

def _call_openai_compat(system_prompt, user_prompt):
    """OpenAI-compatible API (OpenAI, NVIDIA NIM, Together, Fireworks, etc.)"""
    if PROVIDER == "nvidia":
        api_key = NVIDIA_API_KEY
        base_url = NVIDIA_BASE_URL
        model = NVIDIA_MODEL
    else:
        api_key = OPENAI_API_KEY
        base_url = OPENAI_BASE_URL
        model = OPENAI_MODEL

    if not api_key:
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
            "  - Wrong: Authorization: \"Bearer {{admin_access_token}}\" or \"Bearer ***\"\n"
            "  - Correct: Authorization: \"Bearer test-token-abc123\"\n"
            "  - Wrong: DATABASE_URL: \"postgresql://user:***@localhost:5432/app\"\n"
            "  - Correct: DATABASE_URL: \"postgresql://user:testpass@localhost:5432/app\"\n"
            "  - Wrong: JWT_SECRET: \"{{JWT_SECRET}}\"\n"
            "  - Correct: JWT_SECRET: \"test-secret-1234567890abcdef\"\n"
            "NEVER use *** in any string - not in DATABASE_URL, not in headers, not in env_vars.\n"
            "Every password, secret, token must be a concrete test value like 'testpass', 'test-token-abc123', 'test-secret-...'.\n"
            "Every CREATE goal MUST have 'verification' and non-empty 'acceptance_criteria'.\n"
            "No two goals may verify the same target with the same method (near-duplicate check)."
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

    print("\U0001f680 Generating {0} prompt-spec pairs... [provider={1}]\n".format(count, PROVIDER))
    created = 0
    failed = 0
    consecutive_fails = 0

    pbar = tqdm(total=count, desc="Generating", unit="spec",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]  \u2713{postfix}")
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
    import argparse

    parser = argparse.ArgumentParser(description="Generate COMMAND_RUNWAY specs from natural language")
    parser.add_argument("--prompt", type=str, help="Feature request prompt (single spec mode)")
    parser.add_argument("--batch", type=int, help="Number of specs to generate (batch mode, default 10)")
    parser.add_argument("--provider", type=str, choices=["ollama", "openai", "nvidia", "anthropic", "openai-compat"],
                        help="LLM provider (overrides PROVIDER config)")
    parser.add_argument("--model", type=str, help="Model name (overrides provider's default model)")
    parser.add_argument("--api-key", type=str, help="API key for provider (or set via env var)")
    parser.add_argument("--base-url", type=str, help="Base URL for OpenAI-compatible APIs")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens in response")
    parser.add_argument("--timeout", type=int, default=300, help="LLM request timeout in seconds")
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
    if args.api_key:
        if PROVIDER == "nvidia":
            NVIDIA_API_KEY = args.api_key
        elif PROVIDER in ("openai", "openai-compat"):
            OPENAI_API_KEY = args.api_key
        elif PROVIDER == "anthropic":
            ANTHROPIC_API_KEY = args.api_key
    if args.base_url:
        if PROVIDER == "nvidia":
            NVIDIA_BASE_URL = args.base_url
        elif PROVIDER in ("openai", "openai-compat"):
            OPENAI_BASE_URL = args.base_url

    if args.temperature:
        TEMPERATURE = args.temperature
    if args.max_tokens:
        MAX_TOKENS = args.max_tokens
    if args.timeout:
        OLLAMA_TIMEOUT = args.timeout

    if args.prompt:
        print("\U0001f680 Processing fresh prompt: {0}...\n".format(args.prompt[:80]))
        result = generate_one_pair(prompt=args.prompt)
        if result.get("validated"):
            print("\U0001f3c1 Done. Spec saved to {0}".format(OUTPUT_FILE))
            sys.exit(0)
        else:
            print("\u274c Spec had validation errors, saved to {0}".format(FAILED_FILE))
            sys.exit(1)
    else:
        n = args.batch if args.batch else (int(sys.argv[1]) if len(sys.argv) > 1 else 10)
        generate_batch(n)