# Example SPRINTS.md - Sprint definitions with dependencies

# Backend sprints
- task_id: "sprint-1-core-models"
  summary: "Core data models and database schema"
  depends_on: []
  parallel_group: "backend"

- task_id: "sprint-2-auth"
  summary: "Authentication and authorization system"
  depends_on: ["sprint-1-core-models"]
  parallel_group: "backend"

- task_id: "sprint-3-api"
  summary: "REST API layer with validation"
  depends_on: ["sprint-1-core-models", "sprint-2-auth"]
  parallel_group: "backend"

- task_id: "sprint-4-ml"
  summary: "ML pipeline integration"
  depends_on: ["sprint-1-core-models"]
  parallel_group: "ml"

# Frontend sprints
- task_id: "sprint-5-ui-components"
  summary: "React component library"
  depends_on: []
  parallel_group: "frontend"

- task_id: "sprint-6-dashboard"
  summary: "Admin dashboard with charts"
  depends_on: ["sprint-5-ui-components", "sprint-3-api"]
  parallel_group: "frontend"

- task_id: "sprint-7-ml-ui"
  summary: "ML model monitoring UI"
  depends_on: ["sprint-5-ui-components", "sprint-4-ml"]
  parallel_group: "frontend"

# Integration
- task_id: "sprint-8-e2e-tests"
  summary: "End-to-end test suite"
  depends_on: ["sprint-6-dashboard", "sprint-7-ml-ui"]
  parallel_group: "integration"

- task_id: "sprint-9-deploy"
  summary: "Production deployment pipeline"
  depends_on: ["sprint-8-e2e-tests"]
  parallel_group: "integration"

# ============================================================================
# AUTONOMOUS PIPELINE COMPLETION SPRINTS (Sprint 10-13)
# ============================================================================
# Status as of 2026-07-28:
# The 4-stage pipeline is 80% built:
#   1. NL Prompt -> Validated YAML Spec   (run_pipeline.py + validator.py)     [WORKING]
#   2. Spec -> PLAN.md + RUNBOOK.md        (assemble_plan.py)                  [WORKING]
#   3. RUNBOOK -> Executed Code            (autonomous_execute.py)             [WORKING]
#   4. Safety / Docker Isolation           (Dockerfile + .dockerignore)         [PARTIAL]
#
# 4 GAPS preventing full autonomy without cloud models:
#
# GAP 1: No YAML sanitizer — raw Ollama output contains ANSI escape sequences
#         and terminal control chars (e.g. \x1b[1D, \x1b[K) that break yaml.safe_load()
#         Fix: Add clean_yaml_output() to validator.py — strip control chars before parsing
#
# GAP 2: .dockerignore missing critical exclusions — .venv (1.6GB) and models/ (33GB)
#         are included in Docker build context, causing 60+ second timeouts
#         Fix: Add .venv, models/, *.gguf, __pycache__ to .dockerignore
#
# GAP 3: autonomous_execute.py has no --docker flag — the script runs commands
#         directly on the host; the Dockerfile exists but is not called by the pipeline
#         Fix: Add --docker flag that builds image, runs inside container, destroys after
#
# GAP 4: Dockerfile is hardcoded to Node — for a generic pipeline it must adapt
#         to the detected project type (Python/Node/Go/Rust)
#         Fix: Create Dockerfile.template per project type, or multi-runtime base image
#
# GAP 5: No single entry point — no one command that chains NL -> spec -> plan
#         -> runbook -> execute -> report (optionally inside Docker)
#         Fix: Create run_autonomous.py that chains all stages with --docker and --model flags
# ============================================================================

- task_id: "sprint-10-yaml-sanitizer"
  summary: "Add ANSI/terminal control character sanitization to validator.py before yaml.safe_load"
  depends_on: []
  parallel_group: "autonomous"
  gaps_closed: ["GAP 1"]

- task_id: "sprint-11-dockerignore-fix"
  summary: "Fix .dockerignore to exclude .venv, models/, *.gguf, __pycache__ — reduce build context from 35GB to <100MB"
  depends_on: []
  parallel_group: "autonomous"
  gaps_closed: ["GAP 2"]

- task_id: "sprint-12-docker-execution-flag"
  summary: "Add --docker flag to autonomous_execute.py — build image, run inside container, destroy after"
  depends_on: ["sprint-10-yaml-sanitizer", "sprint-11-dockerignore-fix"]
  parallel_group: "autonomous"
  gaps_closed: ["GAP 3"]

- task_id: "sprint-13-generic-dockerfile"
  summary: "Create generic Dockerfile.template that adapts to Python/Node/Go/Rust based on detected project type"
  depends_on: ["sprint-11-dockerignore-fix"]
  parallel_group: "autonomous"
  gaps_closed: ["GAP 4"]

- task_id: "sprint-14-single-entry-point"
  summary: "Create run_autonomous.py — single entry point chaining NL -> spec -> plan -> runbook -> execute -> report with --docker and --model flags"
  depends_on: ["sprint-12-docker-execution-flag", "sprint-13-generic-dockerfile"]
  parallel_group: "autonomous"
  gaps_closed: ["GAP 5"]

- task_id: "sprint-15-e2e-test"
  summary: "End-to-end test of full pipeline with POST /notifications example: NL prompt -> spec -> plan -> execute (in Docker) -> verify 202 response"
  depends_on: ["sprint-14-single-entry-point"]
  parallel_group: "integration"