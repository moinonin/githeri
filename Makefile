.PHONY: generate check clean validate validate-one plan spec test help convert-chat train merge eval-model install-skill uninstall-skill score score-failed upload-hf

N ?= 5
PYTHON = .venv/bin/python
OUTPUT = data/training_data.jsonl

# -------------------- end-to-end --------------------
#    make spec "Add a forgot-password endpoint"  →  validated spec + plan prompt
#
#    This is the full NL → spec → plan flow in one target.
#    Requires Ollama running locally (qwen2.5-coder:7b-instruct).
#    The validated spec is appended to data/training_data.jsonl.
#    The COMMAND_RUNWAY plan prompt is emitted to stdout.

# Generate a single validated spec from a fresh natural-language prompt.
# Usage: make spec PROMPT="Add a POST /register endpoint that accepts email and password"
# Alternative: echo "prompt here" > /tmp/prompt.txt && make spec PROMPT_FILE=/tmp/prompt.txt
spec:
	@if [ -z "$(PROMPT)" ] && [ -z "$(PROMPT_FILE)" ]; then echo 'Usage: make spec PROMPT="<your feature request>" OR make spec PROMPT_FILE=/path/to/prompt.txt'; exit 2; fi
	@if [ -n "$(PROMPT_FILE)" ]; then \
		PROMPT="$$(cat $(PROMPT_FILE))"; \
		echo "🚀 Processing fresh prompt from file → validated spec…"; \
		$(PYTHON) scripts/run_pipeline.py --prompt "$$PROMPT"; \
	else \
		echo "🚀 Processing fresh prompt → validated spec…"; \
		$(PYTHON) scripts/run_pipeline.py --prompt "$(PROMPT)"; \
	fi

# End-to-end: spec the feature THEN emit the plan prompt for it.
# Requires Python 3.10+ for the walrus operator (used inline below).
# Usage: make spec-and-plan PROMPT="Add a PATCH endpoint to update user displayName"
# Alternative: echo "prompt" > /tmp/prompt.txt && make spec-and-plan PROMPT_FILE=/tmp/prompt.txt
spec-and-plan:
	@if [ -z "$(PROMPT)" ] && [ -z "$(PROMPT_FILE)" ]; then echo 'Usage: make spec-and-plan PROMPT="<your feature request>" OR make spec-and-plan PROMPT_FILE=/path/to/prompt.txt'; exit 2; fi
	@if [ -n "$(PROMPT_FILE)" ]; then \
		PROMPT="$$(cat $(PROMPT_FILE))"; \
		echo "🚀 End-to-end: fresh prompt → validated spec → plan prompt"; \
		$(PYTHON) scripts/run_pipeline.py --prompt "$$PROMPT"; \
	else \
		echo "🚀 End-to-end: fresh prompt → validated spec → plan prompt"; \
		$(PYTHON) scripts/run_pipeline.py --prompt "$(PROMPT)"; \
	fi
	@echo ""
	@echo "📐 Emitting plan prompt for the freshly-generated spec…"
	@$(PYTHON) -c "import json,sys; \
lines=open('$(OUTPUT)').read().strip().splitlines(); \
pair=json.loads(lines[-1]); \
open('/tmp/_githeri_last_spec.yaml','w').write(pair['spec_yaml'])"
	@$(PYTHON) scripts/plan_from_spec.py /tmp/_githeri_last_spec.yaml
	@rm -f /tmp/_githeri_last_spec.yaml

# -------------------- full pipeline --------------------
#    make generate N=10   →  produce validated spec pairs
#    make validate        →  validate all pairs (or one with SPEC=)
#    make plan SPEC=<p>   →  emit plan prompt for a validated spec
#    make test            →  run the validator + plan test suite

generate:
	@echo "🚀 Generating $(N) prompt–spec pairs…"
	$(PYTHON) scripts/run_pipeline.py $(N)

i ?= 1
check:
	@echo "📋 Showing first $(i) entry from $(OUTPUT):"
	@head -$(i) $(OUTPUT) | jq .

# Validate every spec in the training corpus (the batch gate)
validate:
	@echo "🔬 Validating all specs in $(OUTPUT) against the hardened validator…"
	@$(PYTHON) -c "import json,sys; \
from scripts.validator import validate_spec; \
pairs=[json.loads(l) for l in open('$(OUTPUT)').read().strip().splitlines()]; \
fail=0; \
[fail:=fail+1 for p in pairs if validate_spec(p['spec_yaml'])]; \
print(f'  {len(pairs)-fail}/{len(pairs)} pairs pass, {fail} fail'); \
sys.exit(1 if fail else 0)"

# Validate a single spec file (accepts .yaml or data/<file>.jsonl#<index>)
validate-one:
	@if [ -z "$(SPEC)" ]; then echo "Usage: make validate-one SPEC=<path-to-yaml-or-jsonl#index>"; exit 2; fi
	@$(PYTHON) -c "import sys; sys.path.insert(0, 'scripts'); \
from validator import validate_spec; \
spec = open('$(SPEC)').read() if not '#' in '$(SPEC)' else None; \
print('Use make plan SPEC=... for jsonl#index extraction') if spec is None else None; \
errors = validate_spec(spec) if spec else []; \
print(f'  FAIL ({len(errors)} errors)') if errors else print('  PASS'); \
[print(f'    - {e}') for e in errors[:8]]; \
sys.exit(1 if errors else 0)"

# Emit the COMMAND_RUNWAY plan prompt for a validated spec.
# SPEC can be a .yaml path or data/training_data.jsonl#<index>.
# Output (stdout) is: runbookprompt.md + the validated spec, ready for an agent.
plan:
	@if [ -z "$(SPEC)" ]; then echo "Usage: make plan SPEC=<path-to-yaml-or-jsonl#index>"; exit 2; fi
	@echo "📐 Emitting COMMAND_RUNWAY plan prompt for: $(SPEC)"
	@$(PYTHON) scripts/plan_from_spec.py "$(SPEC)"

# Score all specs in the training corpus
score:
	@echo "📊 Scoring all specs in $(OUTPUT) against runbook criteria..."
	@$(PYTHON) scripts/score_corpus.py --file $(OUTPUT)

# Score failed specs (invalid specs saved separately)
score-failed:
	@echo "📊 Scoring failed specs in data/failed_specs.jsonl..."
	@$(PYTHON) scripts/score_corpus.py --file data/failed_specs.jsonl --threshold 0.0

# Convert training data to chat format for fine-tuning
# Usage: make convert-chat [MIN_SCORE=0.75]
convert-chat:
	@echo "💬 Converting training data to chat format (min_score=$(MIN_SCORE))..."
	@$(PYTHON) scripts/convert_to_chat.py --min-score $(MIN_SCORE)

# Fine-tuning pipeline targets
train:
	@echo "🏋️  Starting LoRA fine-tuning..."
	@$(PYTHON) scripts/train.py

merge:
	@echo "🔗 Merging adapter and exporting GGUF..."
	@$(PYTHON) scripts/merge_and_export.py

eval-model:
	@echo "📊 Evaluating fine-tuned model..."
	@$(PYTHON) scripts/eval_model.py

# Upload model to HuggingFace Hub
# Requires HF_TOKEN in .env file: echo "HF_TOKEN=hf_your_token" > .env
# Usage: make upload-hf REPO=githeri/qwen2.5-coder-7b-specforge
#         make upload-hf REPO=githeri/qwen2.5-coder-7b-specforge PRIVATE=1
HF_REPO ?= githeri/qwen2.5-coder-7b-specforge
upload-hf:
	@if [ ! -f .env ] || ! grep -q "HF_TOKEN" .env; then echo '❌ HF_TOKEN not found. Create .env: echo "HF_TOKEN=hf_your_token" > .env'; exit 1; fi
	@echo "☁️  Uploading model to HuggingFace Hub: $(HF_REPO)"
	@$(PYTHON) scripts/upload_to_hf.py --model-dir models/qwen2.5-coder-7b-specforge --repo $(HF_REPO) $(if $(PRIVATE),--private)

# Observability
dashboard:
	@echo "📊 Generating observability dashboard..."
	@$(PYTHON) skills/software-development/observability/scripts/generate_dashboard.py \
		--db metrics/autonomous.db --output dashboard/autonomous.html

metrics-collect:
	@echo "📊 Collecting metrics from autonomous run..."
	@if [ -z "$(SPRINT)" ]; then echo "Usage: make metrics-collect SPRINT=sprint8"; exit 1; fi
	@$(PYTHON) skills/software-development/observability/scripts/collect_metrics.py \
		--sprint-id $(SPRINT) --runbook docs/sprints/$(SPRINT)/RUNBOOK.md --spec sprints/$(SPRINT).spec.yaml

alerts:
	@echo "🚨 Checking for anomalies..."
	@$(PYTHON) skills/software-development/observability/scripts/alerting.py \
		--db metrics/autonomous.db --email $(EMAIL)

# Sprint Orchestrator
orchestrate:
	@echo "🎯 Running sprint orchestrator..."
	@$(PYTHON) .hermes/skills/software-development/sprint-orchestrator/scripts/orchestrator.py \
		--sprints-file $(SPRINTS) --workers $(WORKERS) $(if $(DRY_RUN),--dry-run) $(if $(VERBOSE),--verbose)

# Autonomous cycle: spec → plan → runbook → execute → report
autonomous-cycle:
	@echo "🤖 Running autonomous cycle for spec $(SPEC)..."
	@make spec PROMPT_FILE=$(SPEC)
	@make -f Makefile.sprints sprint-all SPRINT=$(basename $(SPEC) .spec.yaml)

uninstall-skill:
	@echo "🗑️  Uninstalling spec-forge skill..."
	@rm -rf ~/.hermes/skills/spec-forge
	@echo "✅ Skill removed."

test:
	@echo "🧪 Running the validator + plan test suite…"
	$(PYTHON) -m pytest tests/ -v

clean:
	@echo "🧹 Removing $(OUTPUT)"
	rm -f $(OUTPUT)

help:
	@echo "Usage:"
	@echo "  make spec PROMPT=\"<text>\"          Generate a validated spec from a fresh NL feature request"
	@echo "  make spec-and-plan PROMPT=\"<text>\"  End-to-end: fresh prompt → validated spec → plan prompt"
	@echo "  make generate N=10                  Generate N pairs from seed prompts (default 5)"
	@echo "  make check                          Pretty-print first pair"
	@echo "  make validate                       Validate all pairs against the hardened spec gate"
	@echo "  make validate-one SPEC=x            Validate a single .yaml spec file"
	@echo "  make score                          Score all specs against runbook criteria"
	@echo "  make score-failed                   Score failed specs (data/failed_specs.jsonl)"
	@echo "  make plan SPEC=<p>                  Emit the COMMAND_RUNWAY plan prompt for a spec"
	@echo "                                      <p> = path/to/spec.yaml OR data/<f>.jsonl#<index>"
	@echo "  make convert-chat                   Convert training_data.jsonl → chat format for fine-tuning"
	@echo "  make train                          Run LoRA fine-tuning (qwen2.5-coder-7b)"
	@echo "  make merge                          Merge adapter + export GGUF for Ollama"
	@echo "  make eval-model                     Evaluate fine-tuned model on held-out prompts"
	@echo "  make upload-hf REPO=<hf-repo>       Upload model to HuggingFace Hub (requires HF_TOKEN in .env)"
	@echo "  make install-skill                  Install spec-forge skill to ~/.hermes/skills/"
	@echo "  make uninstall-skill                Remove spec-forge skill"
	@echo "  make test                           Run the validator + plan test suite"
	@echo "  make clean                          Delete output file"
	@echo "  make orchestrate SPRINTS=file.md    Run sprint orchestrator (parallel execution)"
	@echo "  make orchestrate SPRINTS=file.md --dry-run  Show execution plan only"
	@echo "  make orchestrate SPRINTS=file.md --workers 2  Run with 2 workers"
	@echo "  make dashboard                      Generate observability dashboard"
	@echo "  make metrics-collect SPRINT=sprint8  Collect metrics from sprint"
	@echo "  make alerts                         Check for anomalies"
	@echo "  make guardrails-pipeline FEATURE=x   Run production guardrails pipeline"
	@echo "  make autonomous-cycle SPEC=prompt.txt  Full NL → spec → plan → execute → report"
