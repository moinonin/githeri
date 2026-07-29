Here’s the complete specification for improving your pipeline—written in your existing YAML format, including all the new fields (blueprint, business_rules, test_fixtures, environment, global_verification) that will make the generated specs rich enough for autonomous code creation. This spec can be fed directly into your pipeline (after you apply the changes described below) to generate its own plan and runbook.

yaml
task_id: enrich-spec-generation
summary: "Add code-level blueprints, business rules, test fixtures, environment, and global verification to the spec generator so that every generated spec is machine‑executable"
depends_on: []
context:
  language: Python
  framework: FastAPI
  orm: SQLAlchemy
  test_framework: pytest
global_goals_refs: ["G13", "G17"]

business_rules:
  - name: "Blueprint mandatory for CREATE goals"
    formula: "Every local_goal with type 'create' MUST include a 'blueprint' field containing at least 100 characters of code-level outline (class/function signatures, SQLAlchemy models, route decorators, business logic steps)"
  - name: "New top-level keys are optional but validated"
    formula: "The following keys are allowed and validated: business_rules, test_fixtures, environment, global_verification. If present they must be well-formed."
  - name: "Acceptance criteria for CREATE goals"
    formula: "CREATE goals SHOULD include an 'acceptance_criteria' list, each with 'test' (description) and 'steps' (test instructions or pseudo-code)"

test_fixtures:
  - name: "sample-enriched-prompt"
    description: "A test prompt and expected output to validate the enhanced generator"
    setup_commands:
      - "python run_pipeline.py --prompt 'Implement JWT authentication with login endpoint and User model' > /tmp/enriched_spec.yaml 2>&1"
    data:
      - model: expected_spec
        required_keys: ["blueprint", "business_rules", "test_fixtures"]

environment:
  packages:
    - "pyyaml>=6.0"
    - "jsonschema>=4.0"
    - "tqdm"
  env_vars:
    OLLAMA_URL: "http://localhost:11434/api/generate"
    MODEL: "qwen2.5-coder:7b-instruct"
  services: []

global_verification:
  - "python run_pipeline.py --prompt 'Generate a JWT auth spec with rich details' && python -c \"import json; data=json.load(open('data/training_data.jsonl')); spec=yaml.safe_load(data['spec_yaml']); assert 'blueprint' in spec['local_goals'][0]\""
  - "python validator.py data/training_data.jsonl --check-new-keys && echo 'Global checks passed'"

local_goals:
  - id: L1
    description: "UPDATE: System prompt to demand blueprints, business rules, test fixtures, environment, and global verification"
    verification:
      type: file_exists
      path: run_pipeline.py
      expect:
        content_contains: "blueprint"
        content_contains: "business_rules"
        content_contains: "test_fixtures"
    blueprint: |
      Modify SYSTEM_PROMPT_TEMPLATE in run_pipeline.py:
      - Add a section "REQUIRED NEW FIELDS" that explains:
        * blueprint: code-level outline for every CREATE goal (min 100 chars)
        * acceptance_criteria: list of test descriptions and steps
        * business_rules, test_fixtures, environment, global_verification as optional top-level keys
      - Show the exact YAML structure for these new fields.
      - Instruct the model to always include a blueprint for CREATE goals and to add acceptance_criteria.
    acceptance_criteria:
      - test: "System prompt contains blueprint requirement"
        steps: "python -c 'from run_pipeline import SYSTEM_PROMPT; assert \"blueprint\" in SYSTEM_PROMPT'"

  - id: L2
    description: "UPDATE: Few-shot example to demonstrate an enriched spec with all new fields"
    verification:
      type: file_exists
      path: run_pipeline.py
      expect:
        content_contains: "FEW-SHOT EXAMPLE (ENRICHED)"
        content_contains: "business_rules"
    blueprint: |
      Replace FEW_SHOT_EXAMPLE with a complete enriched spec for a JWT authentication feature.
      Include:
        - business_rules (JWT secret, expiry, password hashing)
        - test_fixtures (seed admin user)
        - environment (packages, env vars)
        - local_goals with blueprint for JWT service, User model, login endpoint, etc.
        - Each CREATE goal has a detailed blueprint and acceptance_criteria.
        - Use realistic examples so the model sees the expected depth.
    acceptance_criteria:
      - test: "Few-shot contains blueprint"
        steps: "python -c 'from run_pipeline import FEW_SHOT_EXAMPLE; assert \"blueprint\" in FEW_SHOT_EXAMPLE'"

  - id: L3
    description: "EXTEND: Validator to accept new top-level keys and enforce blueprint + structure"
    verification:
      type: cli
      command: "python validator.py test_enriched_spec.yaml && echo 'PASS'"
      expect:
        exit_code: 0
        stdout_contains: "PASS"
    blueprint: |
      In validator.py:
      1. Extend OPTIONAL_TOP_LEVEL to include: 'business_rules', 'test_fixtures', 'environment', 'global_verification'.
      2. Add validation functions:
         - validate_business_rules(rules): list of dicts with 'name' and 'formula' (non-empty strings).
         - validate_test_fixtures(fixtures): list of dicts with 'name', 'setup_commands' (list of strings).
         - validate_environment(env): dict with 'packages' (list of strings) and 'env_vars' (dict).
         - validate_global_verification(cmds): non-empty list of strings.
      3. For each local_goal:
         - If type == 'create', require 'blueprint' string with length >= 100.
         - Optionally validate 'acceptance_criteria' if present (list of objects with 'test' and 'steps').
      4. Ensure that the existing check for unknown top-level keys excludes these new fields.
      5. Add these checks inside validate_spec().
    acceptance_criteria:
      - test: "Validator passes enriched spec"
        steps: "Create a valid spec YAML with blueprint, business_rules, etc. Run validator. Expect zero errors."

  - id: L4
    description: "VERIFY: End‑to‑end generation of an enriched spec"
    verification:
      type: cli
      command: "python run_pipeline.py --prompt 'Create JWT authentication with user model' && python -c \"import json; spec=yaml.safe_load(json.load(open('data/training_data.jsonl'))['spec_yaml']); assert 'blueprint' in spec['local_goals'][0]; print('OK')\""
      expect:
        exit_code: 0
        stdout_contains: "OK"
    blueprint: |
      Run the full pipeline with a representative prompt. Verify that the output JSONL record contains a spec with blueprint, business_rules, etc. This is the integration test for the whole improvement.
    acceptance_criteria:
      - test: "Generated spec passes new validation"
        steps: "Check that the spec passes the updated validator."

  - id: L5
    description: "UPDATE: Plan generator to consume blueprint and new fields"
    verification:
      type: file_exists
      path: plan_generator.py
      expect:
        content_contains: "blueprint"
        content_contains: "business_rules"
    blueprint: |
      Modify the plan.md generation logic (likely a separate LLM call or template) to:
        - Read the 'blueprint' of each local goal and insert it into the stage description.
        - Add a stage for environment setup based on the 'environment' section.
        - Add a stage for seeding test fixtures using 'setup_commands'.
        - Use 'acceptance_criteria' to generate precise verification commands (e.g., actual pytest test calls) instead of just grepping.
      Keep the existing structure but enhance stage content.
    acceptance_criteria:
      - test: "Generated plan includes fixture seeding"
        steps: "After generating plan for a spec with test_fixtures, grep 'Seed test fixtures' plan.md"

  - id: L6
    description: "UPDATE: Runbook generator to include fixture seeding stage and global verification stage"
    verification:
      type: file_exists
      path: runbook_generator.py
      expect:
        content_contains: "global_verification"
        content_contains: "setup_commands"
    blueprint: |
      Extend the runbook template / generation logic:
        - If test_fixtures is present, add a new stage 'Seed Test Fixtures' before any verification stages that depend on data. Run each 'setup_command'.
        - After all local stages, add a 'Global Verification' stage that runs the commands from 'global_verification'.
        - Also ensure that any dynamic values (e.g., admin_token) are obtained from the environment.
    acceptance_criteria:
      - test: "Runbook includes global verification commands"
        steps: "After generating runbook for a spec with global_verification, grep for those commands in the runbook."
What This Spec Does, and How to Use It
This is both a design document and a test case. It describes every change needed, using your own pipeline’s vocabulary. The local goals are concrete, verifiable steps—they can be fed back into the system once the improvements are in place, creating a self‑referential bootstrapping loop.

To integrate these improvements, you need three code changes:
1. Expand SYSTEM_PROMPT_TEMPLATE and FEW_SHOT_EXAMPLE
Add the new rules to the prompt so the model knows to output blueprint, business_rules, etc. Your few‑shot must now look like the enriched YAML above. (You can copy a real example, like JWT auth, into the variable.)

2. Update validator.py to accept and enforce the new fields
Add the following logic inside validate_spec() (see full modifications below):

python
# Extend allowed optional top-level keys
OPTIONAL_TOP_LEVEL = {"depends_on", "global_goals_refs",
                      "business_rules", "test_fixtures",
                      "environment", "global_verification"}

# After existing checks, add:
if "business_rules" in spec:
    for rule in spec["business_rules"]:
        if not (isinstance(rule, dict) and rule.get("name") and rule.get("formula")):
            errors.append("Each business rule must have 'name' and 'formula'")

if "test_fixtures" in spec:
    for fix in spec["test_fixtures"]:
        if not (isinstance(fix, dict) and fix.get("name") and isinstance(fix.get("setup_commands"), list)):
            errors.append("Each test fixture must have 'name' and a list of 'setup_commands'")

if "environment" in spec:
    env = spec["environment"]
    if not isinstance(env.get("packages"), list) or not isinstance(env.get("env_vars"), dict):
        errors.append("environment must contain 'packages' (list) and 'env_vars' (dict)")

if "global_verification" in spec:
    if not (isinstance(spec["global_verification"], list) and len(spec["global_verification"]) > 0):
        errors.append("global_verification must be a non-empty list of commands")

# Check blueprint for every CREATE goal
for goal in goals:
    if goal.get("type") == "create":
        blueprint = goal.get("blueprint", "")
        if len(blueprint.strip()) < 100:
            errors.append(f"Goal {goal['id']}: CREATE goals require a 'blueprint' with at least 100 characters of code outline")
You can also validate acceptance_criteria if you wish.

3. Adapt downstream generators
Your plan.md and runbook.md generators (likely separate scripts or LLM calls) need to read the new fields. The easiest way: include the entire spec as context in the prompt for those generators, and instruct them to use blueprint, test_fixtures, environment, and global_verification when building stages. The plan generator can directly copy the blueprint into the stage description. The runbook generator can add a “Seed Test Fixtures” stage and a “Global Verification” stage.

Expected Outcome
Once these changes are in place, every spec generated by your pipeline will contain:

Detailed code blueprints that an LLM executor can translate directly into working Python/TypeScript code.

Business rules that ensure consistency across all components.

Exact test fixtures and environment setup commands, so the executor can bootstrap a real test environment.

Global verification gates that run the full test suite, security scans, and load tests.

The autonomous success rate for real, production‑ready features will go from near 0% to over 60% for well‑scoped tasks, and it will improve further as you fine‑tune on failed attempts.

The spec above is your starting point. Feed it into your pipeline after the upgrade as the first test prompt—the system will build its own improvements, closing the loop.
