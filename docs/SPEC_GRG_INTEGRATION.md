task_id: grg-command-runway-integration
summary: |
  Integrate GRG Agent as a COMMAND_RUNWAY executor with GRG quality gates.
  GRG Agent provides multi-provider LLM factory, AlphaMomentumTracker quality monitoring,
  and diversity-controlled candidate generation. COMMAND_RUNWAY provides the spec-to-verified-implementation
  method with three layers (prompt → plan → runbook), verification discipline, and audit trail.
  This spec defines the integration where GRG Agent executes COMMAND_RUNWAY plans, using
  GRG composite confidence scores as binary verification gates.

context: |
  Target repository: githeri (this repo). GRG Agent skill lives at ~/.hermes/skills/grg_agent/
  COMMAND_RUNWAY skill lives at ~/.hermes/skills/software-development/command-runway-pattern/
  Both skills are installed and available. Python 3.11+, .venv required.
  GRG core package installed via `pip install -e /path/to/grg`.
  Hermes proxy runs on localhost:8465 for remote provider; Ollama on localhost:11434 for local.
  Small model preference: SmolLM2-360M-Instruct for fast iteration, then scale to qwen2.5-coder:7b-instruct.

local_goals:
  - id: L1
    description: Define GRG Agent as COMMAND_RUNWAY executor with unified LLM provider factory
    type: create
    blueprint: |
      import asyncio
      from typing import Dict, Any, List, Optional
      from dataclasses import dataclass
      from pathlib import Path

      from .llm_client import create_llm_client
      from .monitor import GRGMonitor
      from .diversity import DiversityController
      from .state import Candidate, Score

      class GRGExecutor:
          """GRG Agent executor for COMMAND_RUNWAY plans."""
          
          def __init__(self, config):
              self.config = config
              self.llm_client = create_llm_client(config.llm_provider)
              self.monitor = GRGMonitor(config)
              self.diversity = DiversityController(config)
          
          async def execute_plan(self, plan_path: str) -> Dict[str, Any]:
              """Execute a COMMAND_RUNWAY plan and produce RUNBOOK.md."""
              import json
              plan = json.loads(Path(plan_path).read_text())
              # Execute stages sequentially with GRG verification gates
              runbook = {"task_id": plan["task_id"], "stages": [], "status": "In-Flight"}
              for stage in plan["stages"]:
                  stage_result = await self._execute_stage(stage)
                  runbook["stages"].append(stage_result)
                  if not all(cmd.get("passed", False) for cmd in stage_result["commands"] if cmd["type"] == "verify"):
                      runbook["status"] = "Blocked"
                      break
              else:
                  runbook["status"] = "Verified"
              return runbook
          
          async def _execute_stage(self, stage: Dict) -> Dict:
              # Execute preconditions, inspect, mutate, verify commands
              return {"stage_id": stage["id"], "commands": []}
    acceptance_criteria:
      - test: "Executor loads plan from COMMAND_RUNWAY.md or JSON"
        steps: |
          1. Create minimal plan with 2 stages
          2. Run executor --plan plan.json --dry-run
          3. Verify stage order and command parsing
      - test: "Provider factory integrates with executor"
        steps: |
          1. Set llm_provider=auto in config
          2. Execute a simple generation task
          3. Verify Ollama or Hermes proxy client instantiated correctly
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_executor_loads_plan -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L2
    description: Implement AlphaMomentumTracker as COMMAND_RUNWAY verify command
    type: verify
    blueprint: |
      import math
      from grg import AlphaMomentumTracker, compute_structural_alpha
      from typing import Dict, Any, Optional, List
      from dataclasses import dataclass

      @dataclass
      class VerifyResult:
          passed: bool
          composite_confidence: float
          alpha: float
          valpha: float
          details: str

      class GRGVerifyCommand:
          """GRG AlphaMomentumTracker wrapped as a verify command."""
          
          def __init__(self, config):
              self.config = config
              self.threshold_mult = config.grg_threshold_mult
          
          def verify(self, logprobs: List[float], threshold_mult: Optional[float] = None) -> VerifyResult:
              if threshold_mult is None:
                  threshold_mult = self.threshold_mult
              
              tracker = AlphaMomentumTracker(window_size=16, alpha_ema=0.3)
              composites = []
              
              for i, lp in enumerate(logprobs):
                  window = logprobs[:i]
                  if len(window) > 1:
                      alpha = compute_structural_alpha(lp, window, threshold_mult)
                      tracker.push(alpha)
                  else:
                      tracker.push(0.0)
                  
                  stats = tracker.get_stats()
                  alpha_h = stats.get("alpha", 1.0)
                  v_alpha = stats.get("v_alpha", 0.0)
                  
                  if not math.isfinite(alpha_h):
                      alpha_h = 0.0
                  if not math.isfinite(v_alpha):
                      v_alpha = 0.0
                  
                  model_prob = math.exp(lp)
                  composite = float(model_prob) * max(0.5, min(1.5, alpha_h * (1 + max(0.0, v_alpha))))
                  composites.append(composite)
              
              mean_composite = sum(composites) / len(composites) if composites else 0.0
              baseline = 0.5  # baseline alpha
              passed = mean_composite > threshold_mult * baseline
              
              return VerifyResult(
                  passed=passed,
                  composite_confidence=mean_composite,
                  alpha=tracker.ema_alpha,
                  valpha=tracker.ema_velocity,
                  details=f"composite={mean_composite:.3f}, alpha={tracker.ema_alpha:.3f}, valpha={tracker.ema_velocity:.3f}, threshold={threshold_mult * baseline:.3f}"
              )
    acceptance_criteria:
      - test: "Tracker detects alpha collapse on low-entropy generation"
        steps: |
          1. Generate repetitive text with temperature=0.1
          2. Run tracker with threshold=1.5
          3. Verify FAIL with low composite_confidence
      - test: "Tracker passes diverse high-quality generation"
        steps: |
          1. Generate diverse code with temperature=0.8
          2. Run tracker with threshold=1.5
          3. Verify PASS with composite_confidence > threshold
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_alpha_tracker_verify -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L3
    description: Implement DiversityController as candidate generator per stage
    type: create
    blueprint: |
      import random
      import math
      from typing import List, Dict, Any
      from dataclasses import dataclass
      import torch
      from transformers import AutoTokenizer

      from .config import GRGAgentConfig
      from .state import Strategy, Candidate

      @dataclass
      class PromptVariant:
          prompt: str
          temperature: float
          top_p: float
          name: str
          description: str

      class DiversityController:
          """Explicit diversity management for candidate generation."""
          
          def __init__(self, config: GRGAgentConfig):
              self.config = config
              self.temp_min, self.temp_max = config.diversity_temperature_range
              self.min_cosine = config.diversity_min_cosine
              self.max_candidates = config.diversity_max_candidates
              self.candidate_pool: List[Candidate] = []
          
          def generate_variants(self, base_prompt: str, num_variants: int = None, iteration: int = 0, previous_best: str = None) -> List[PromptVariant]:
              if num_variants is None:
                  num_variants = min(4, self.config.max_strategies)
              
              variants = []
              # Always include base prompt
              variants.append(PromptVariant(
                  prompt=base_prompt,
                  temperature=self.config.temperature,
                  top_p=self.config.top_p,
                  name="base",
                  description="Standard generation"
              ))
              
              strategies = ["cot", "decompose", "explain", "test_first", "refine"]
              if previous_best and iteration > 0:
                  strategies.remove("refine")
                  strategies.insert(0, "refine")
              
              selected = random.sample(strategies, min(num_variants - 1, len(strategies)))
              
              for strategy in selected:
                  temp = self.temp_min + (self.temp_max - self.temp_min) * (iteration / 5.0)
                  top_p = self.config.top_p + random.uniform(-0.05, 0.05)
                  variants.append(PromptVariant(
                      prompt=f"{base_prompt}\n\nStrategy: {strategy}",
                      temperature=temp,
                      top_p=top_p,
                      name=strategy,
                      description=strategy
                  ))
              
              return variants[:num_variants]
          
          def filter_candidates(self, candidates: List[Candidate], min_diversity: float = 0.85) -> List[Candidate]:
              """Filter candidates by cosine similarity threshold."""
              if len(candidates) <= 1:
                  return candidates
              
              filtered = [candidates[0]]
              for cand in candidates[1:]:
                  diverse = True
                  for selected in filtered:
                      # Would check embedding distance here
                      pass
                  if diverse:
                      filtered.append(cand)
              return filtered
    acceptance_criteria:
      - test: "Controller produces diverse candidates for same prompt"
        steps: |
          1. Request 4 candidates with temp range [0.3, 1.5]
          2. Compute pairwise cosine similarity
          3. Verify all pairs < 0.85 similarity
      - test: "Controller respects candidates_per_strategy config"
        steps: |
          1. Set candidates_per_strategy=5
          2. Verify exactly 5 candidates returned
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_diversity_controller -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L4
    description: Wire GRG Agent hermes_skill.py to emit COMMAND_RUNWAY plan format
    type: update
    blueprint: |
      import asyncio
      import json
      import os
      from pathlib import Path
      from typing import Dict, Any, Optional

      from .executor import GRGExecutor
      from .config import GRGAgentConfig
      from .llm_client import create_llm_client

      async def solve_with_plan(self, task: str, spec_path: Optional[str] = None, max_iterations: int = 5, model: str = None) -> Dict[str, Any]:
          """Solve task using COMMAND_RUNWAY plan execution."""
          
          if spec_path:
              # Validate spec with COMMAND_RUNWAY validator
              from scripts.validator import validate_spec
              spec_yaml = Path(spec_path).read_text()
              errors = validate_spec(spec_yaml)
              if errors:
                  return {"error": f"Spec validation failed: {errors}"}
              
              # Generate plan via make plan SPEC=<path>
              import subprocess
              result = subprocess.run(["make", "plan", f"SPEC={spec_path}"], capture_output=True, text=True)
              if result.returncode != 0:
                  return {"error": f"Plan generation failed: {result.stderr}"}
              plan_path = "/tmp/grg_plan.json"  # Extract from output
          else:
              # Generate plan from task using .runbookprompt.md + structural anchor
              plan_path = await self._generate_plan_from_task(task)
          
          # Execute plan via GRGExecutor
          executor = GRGExecutor(self.config)
          runbook = await executor.execute_plan(plan_path)
          
          # Produce RUNBOOK.md (Layer 3 execution log)
          runbook_path = "RUNBOOK.md"
          self._write_runbook_markdown(runbook, runbook_path)
          
          return {
              "success": runbook["status"] == "Verified",
              "runbook": runbook,
              "runbook_path": runbook_path,
              "stages_passed": sum(1 for s in runbook["stages"] if all(c.get("passed", False) for c in s["commands"] if c["type"] == "verify")),
              "total_stages": len(runbook["stages"])
          }
      
      def _write_runbook_markdown(self, runbook: Dict, path: str):
          """Write RUNBOOK.md in COMMAND_RUNWAY Layer 3 format."""
          with open(path, "w") as f:
              f.write(f"# Runbook: {runbook['task_id']}\n\n")
              f.write(f"Status: {runbook['status']}\n\n")
              for stage in runbook["stages"]:
                  f.write(f"## Stage {stage['stage_id']}\n")
                  for cmd in stage["commands"]:
                      status = "✓" if cmd.get("passed") else "✗"
                      f.write(f"- {status} {cmd['id']} ({cmd['type']}): {cmd.get('output', '')}\n")
    acceptance_criteria:
      - test: "/grg solve with --spec produces valid COMMAND_RUNWAY plan"
        steps: |
          1. Create test spec YAML
          2. Run /grg solve "test" --spec test_spec.yaml --dry-run
          3. Verify plan output matches COMMAND_RUNWAY stage table format
      - test: "/grg solve without spec uses structural anchor prompt"
        steps: |
          1. Run /grg solve "implement binary search" --iterations 2
          2. Verify plan generated and executed
          3. Verify RUNBOOK.md created with execution log
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_skill_emits_plan -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L5
    description: Add Make targets for GRG-COMMAND_RUNWAY integration workflow
    type: create
    blueprint: |
      # Add to Makefile:
      # GRG-COMMAND_RUNWAY Integration Targets
      
      # Generate validated spec from NL prompt
      grg-spec:
      	@if [ -z "$(PROMPT)" ]; then echo 'Usage: make grg-spec PROMPT="<feature>"'; exit 2; fi
      	@echo "🚀 Generating validated spec from prompt..."
      	@$(PYTHON) scripts/run_pipeline.py --prompt "$(PROMPT)" $(PROVIDER_ARGS)
      
      # Generate COMMAND_RUNWAY plan from validated spec
      grg-plan:
      	@if [ -z "$(SPEC)" ]; then echo 'Usage: make grg-plan SPEC=<spec.yaml>'; exit 2; fi
      	@echo "📐 Generating COMMAND_RUNWAY plan..."
      	@$(PYTHON) scripts/plan_from_spec.py "$(SPEC)" > /tmp/grg_plan.json
      	@cat /tmp/grg_plan.json
      
      # Execute plan via GRGExecutor
      grg-run:
      	@if [ -z "$(PLAN)" ]; then echo 'Usage: make grg-run PLAN=<plan.json>'; exit 2; fi
      	@echo "🤖 Executing plan via GRGExecutor..."
      	@$(PYTHON) -m grg_agent.executor --plan "$(PLAN)"
      
      # End-to-end: spec → plan → run → runbook
      grg-full:
      	@if [ -z "$(PROMPT)" ]; then echo 'Usage: make grg-full PROMPT="<feature>"'; exit 2; fi
      	@echo "🚀 End-to-end GRG-COMMAND_RUNWAY pipeline..."
      	@make grg-spec PROMPT="$(PROMPT)" PROVIDER=$(PROVIDER) MODEL=$(MODEL)
      	@make grg-plan SPEC=data/training_data.jsonl#$$(($$(wc -l < data/training_data.jsonl) - 1))
      	@make grg-run PLAN=/tmp/grg_plan.json
      	@echo "✅ RUNBOOK.md generated"
      
      # Verify runbook completeness
      grg-verify:
      	@if [ -z "$(RUNBOOK)" ]; then echo 'Usage: make grg-verify RUNBOOK=RUNBOOK.md'; exit 2; fi
      	@echo "🔍 Verifying runbook completeness..."
      	@$(PYTHON) -m grg_agent.executor --verify "$(RUNBOOK)"
    acceptance_criteria:
      - test: "make grg-full runs end-to-end on simple task"
        steps: |
          1. Run make grg-full PROMPT="implement fibonacci with memoization"
          2. Verify RUNBOOK.md exists with all stages passed
          3. Verify generated code passes tests
      - test: "make grg-verify catches incomplete runbook"
        steps: |
          1. Create runbook with failed stage
          2. Run make grg-verify RUNBOOK=bad_runbook.md
          3. Verify non-zero exit and clear failure message
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_make_targets -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L6
    description: Implement runbook JSON serialization for automation bridge
    type: create
    blueprint: |
      import json
      from typing import Dict, Any, List
      from dataclasses import dataclass, asdict
      from datetime import datetime

      @dataclass
      class RunbookCommand:
          id: str
          type: str  # inspect|modify|verify
          tool: str
          args: Dict[str, Any]
          depends_on: List[str]
          expected: Dict[str, Any]
          fallback: str
          passed: bool = False
          output: str = ""
          retry_count: int = 0

      @dataclass
      class RunbookStage:
          id: str
          commands: List[RunbookCommand]
          completion_condition: str

      @dataclass
      class Runbook:
          task_id: str
          status: str  # Draft|In-Flight|Verified|Blocked
          preconditions: List[Dict[str, Any]]
          stages: List[RunbookStage]
          goals: Dict[str, List[Dict[str, Any]]]
          created_at: str
          updated_at: str

      class GRGRunbookSerializer:
          """Serialize GRG execution to COMMAND_RUNWAY machine-readable JSON."""
          
          @staticmethod
          def to_json(runbook: Runbook) -> str:
              return json.dumps(asdict(runbook), indent=2)
          
          @staticmethod
          def from_json(json_str: str) -> Runbook:
              data = json.loads(json_str)
              return Runbook(**data)
          
          @staticmethod
          def validate_dag(stages: List[RunbookStage]) -> bool:
              """Verify stage DAG (depends_on) is acyclic."""
              # Build adjacency list
              graph = {}
              for stage in stages:
                  for cmd in stage.commands:
                      graph[cmd.id] = cmd.depends_on
              
              # Detect cycles using DFS
              visited = set()
              rec_stack = set()
              
              def has_cycle(node):
                  visited.add(node)
                  rec_stack.add(node)
                  for dep in graph.get(node, []):
                      if dep not in visited:
                          if has_cycle(dep):
                              return True
                      elif dep in rec_stack:
                          return True
                  rec_stack.remove(node)
                  return False
              
              for node in graph:
                  if node not in visited:
                      if has_cycle(node):
                          return False
              return True
    acceptance_criteria:
      - test: "Executor produces valid JSON runbook"
        steps: |
          1. Execute plan with 2 stages
          2. Verify RUNBOOK.json exists and validates against schema
          3. Verify composite_confidence in verify command results
      - test: "JSON runbook loadable by automation harness"
        steps: |
          1. Parse RUNBOOK.json with Python
          2. Verify all required keys present
          3. Verify stage DAG (depends_on) is acyclic
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_runbook_json -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L7
    description: Integrate IMPROVE_SPEC enrichment fields into GRG spec generation
    type: update
    blueprint: |
      import yaml
      from typing import Dict, Any, List

      class GRGSpecGenerator:
          """Generate specs with IMPROVE_SPEC enrichment fields."""
          
          # Structural anchor for small models (COMMAND_RUNWAY Section 15)
          STRUCTURAL_ANCHOR = (
              "CRITICAL: local_goals MUST be a list of objects with id, description, type, "
              "blueprint, acceptance_criteria, verification, NOT a list of strings.\n"
              "WRONG (will be rejected by validator):\n"
              "  local_goals:\n"
              "    - Implement GRG executor\n"
              "    - Add Alpha tracker verify command\n"
              "CORRECT:\n"
              "  local_goals:\n"
              "    - id: L1\n"
              "      description: \"Define GRG Agent as COMMAND_RUNWAY executor\"\n"
              "      type: create\n"
              "      blueprint: \"Create GRGExecutor class in grg_agent/executor.py...\"\n"
              "      acceptance_criteria:\n"
              "        - test: \"Executor loads plan...\"\n"
              "          steps: \"Create minimal plan..., Run executor...\"\n"
              "      verification:\n"
              "        type: cli\n"
              "        command: \".venv/bin/python -m pytest tests/test_grg_executor.py::test_executor_loads_plan -xvs\"\n"
              "        expect:\n"
              "          exit_code: 0\n"
              "          stdout_contains: \"PASSED\""
          )
          
          def generate_spec(self, prompt: str) -> str:
              """Generate spec with all IMPROVE_SPEC fields."""
              spec = {
                  "task_id": self._slugify(prompt),
                  "summary": prompt,
                  "context": {
                      "language": "Python",
                      "framework": "GRG Agent",
                      "test_framework": "pytest"
                  },
                  "business_rules": [
                      {"name": "verification_gate_binary", "formula": "composite_confidence > threshold → PASS else FAIL"},
                      {"name": "diversity_similarity_cap", "formula": "cosine_similarity < 0.85 for all pairs"},
                  ],
                  "test_fixtures": [
                      {"name": "minimal_plan", "setup_commands": ["echo 'test' > test.json"], "teardown_commands": []},
                  ],
                  "environment": {
                      "packages": ["pytest>=7.0", "pyyaml>=6.0", "grg-core"],
                      "env_vars": {"GRG_PROVIDER": "auto"}
                  },
                  "global_verification": [
                      ".venv/bin/python -m pytest tests/ -x --tb=short",
                      ".venv/bin/python -m mypy grg_agent/",
                  ],
                  "local_goals": []
              }
              return yaml.dump(spec, sort_keys=False)
    acceptance_criteria:
      - test: "Generated spec passes COMMAND_RUNWAY validator"
        steps: |
          1. Run GRG spec generation on test prompt
          2. Validate with COMMAND_RUNWAY validator (make validate-spec SPEC=generated.yaml)
          3. Verify zero errors, all IMPROVE_SPEC fields present
      - test: "Structural anchor improves first-attempt validity on small models"
        steps: |
          1. Run spec generation with SmolLM2-360M (3 attempts)
          2. Compare validity rate with/without anchor
          3. Verify >=2/3 valid with anchor (per skill evidence)
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_improve_spec_fields -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

  - id: L8
    description: Add global verification gates and failure procedure compliance
    type: create
    blueprint: |
      from typing import Dict, Any, List
      from enum import Enum
      from dataclasses import dataclass

      class FailureType(Enum):
          INCORRECT_ASSUMPTION = "incorrect_assumption"
          MISSING_DEPENDENCY = "missing_dependency"
          BAD_IMPLEMENTATION = "bad_implementation"
          ENVIRONMENT = "environment"
          TEST_FAILURE = "test_failure"
          UNEXPECTED_ARCHITECTURE = "unexpected_architecture"

      @dataclass
      class IterationRecord:
          stage_id: str
          command_id: str
          failure_type: FailureType
          diagnosis: str
          corrective_action: str
          retry_count: int

      class GRGFailureHandler:
          """Implement COMMAND_RUNWAY failure procedure."""
          
          def __init__(self):
              self.iterations: List[IterationRecord] = []
          
          def handle_failure(self, stage_id: str, command_id: str, error: str, context: Dict) -> Dict[str, Any]:
              """Stop, diagnose, record, retry - never advance on failure."""
              # Classify failure
              failure_type = self._classify_failure(error, context)
              
              # Record iteration
              retry_count = sum(1 for i in self.iterations if i.command_id == command_id)
              record = IterationRecord(
                  stage_id=stage_id,
                  command_id=command_id,
                  failure_type=failure_type,
                  diagnosis=self._diagnose(failure_type, error, context),
                  corrective_action=self._corrective_action(failure_type, context),
                  retry_count=retry_count
              )
              self.iterations.append(record)
              
              return {
                  "action": "retry",
                  "retry_count": retry_count + 1,
                  "diagnosis": record.diagnosis,
                  "corrective_action": record.corrective_action,
                  "stop_dependents": True
              }
          
          def _classify_failure(self, error: str, context: Dict) -> FailureType:
              error_lower = error.lower()
              if "import" in error_lower or "module" in error_lower:
                  return FailureType.MISSING_DEPENDENCY
              elif "assert" in error_lower or "test" in error_lower:
                  return FailureType.TEST_FAILURE
              elif "connection" in error_lower or "timeout" in error_lower:
                  return FailureType.ENVIRONMENT
              else:
                  return FailureType.BAD_IMPLEMENTATION
          
          def _diagnose(self, failure_type: FailureType, error: str, context: Dict) -> str:
              return f"{failure_type.value}: {error}"
          
          def _corrective_action(self, failure_type: FailureType, context: Dict) -> str:
              actions = {
                  FailureType.MISSING_DEPENDENCY: "Install missing dependency and retry",
                  FailureType.TEST_FAILURE: "Fix implementation to satisfy test, then retry",
                  FailureType.ENVIRONMENT: "Resolve environment issue and retry",
                  FailureType.BAD_IMPLEMENTATION: "Fix implementation bug and retry",
              }
              return actions.get(failure_type, "Analyze error and apply fix")
    acceptance_criteria:
      - test: "Executor stops on verify failure and records iteration"
        steps: |
          1. Create plan with failing verify command
          2. Run executor
          3. Verify RUNBOOK.md has Iteration section with diagnosis
          4. Verify dependent commands not executed
      - test: "Global verification runs after all stages pass"
        steps: |
          1. Execute plan with all stages passing
          2. Verify global_verification commands run
          3. Verify final status = Verified only if global gates pass
    verification:
      type: cli
      command: .venv/bin/python -m pytest tests/test_grg_executor.py::test_failure_procedure -xvs
      expect:
        exit_code: 0
        stdout_contains: "PASSED"

global_goals_refs: []
depends_on: []

business_rules:
  - name: verification_gate_binary
    formula: "composite_confidence > grg_threshold_mult * baseline_alpha → PASS else FAIL"
  - name: diversity_similarity_cap
    formula: "cosine_similarity(candidate_i, candidate_j) < 0.85 for all i ≠ j"
  - name: stage_gate_all_verify_pass
    formula: "∀ stage: ∀ verify_command ∈ stage: verify_command.exit_code = 0"
  - name: no_advance_on_failure
    formula: "failed_verify → ¬execute(dependents) ∧ retry(failed_verify)"

test_fixtures:
  - name: minimal_plan
    setup_commands:
      - "echo 'test' > test_plan.json"
    teardown_commands: []
  - name: failing_verify_plan
    setup_commands:
      - "echo 'test' > failing_plan.json"
    teardown_commands: []

environment:
  packages:
    - pytest>=7.0
    - pyyaml>=6.0
    - grg-core (local editable)
  env_vars:
    HERMES_PROXY_URL: "http://localhost:8465/v1"
    OLLAMA_BASE_URL: "http://127.0.0.1:11434/v1"
    GRG_PROVIDER: "auto"

global_verification:
  - .venv/bin/python -m pytest tests/ -x --tb=short
  - .venv/bin/python -m mypy grg_agent/ --ignore-missing-imports
  - .venv/bin/python -m ruff check grg_agent/

# Structural anchor for small model spec generation (COMMAND_RUNWAY Section 15)
# CRITICAL: local_goals MUST be a list of objects with id, description, type, blueprint, acceptance_criteria, verification, NOT a list of strings.
# WRONG (will be rejected by validator):
#   local_goals:
#     - Implement GRG executor
#     - Add Alpha tracker verify command
# CORRECT:
#   local_goals:
#     - id: L1
#       description: "Define GRG Agent as COMMAND_RUNWAY executor"
#       type: create
#       blueprint: "Create GRGExecutor class in grg_agent/executor.py..."
#       acceptance_criteria:
#         - test: "Executor loads plan..."
#           steps: "Create minimal plan..., Run executor..."
#       verification:
#         type: cli
#         command: ".venv/bin/python -m pytest tests/test_grg_executor.py::test_executor_loads_plan -xvs"
#         expect:
#           exit_code: 0
#           stdout_contains: "PASSED"