.PHONY: generate check clean validate validate-one plan spec test help

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
spec:
	@if [ -z "$(PROMPT)" ]; then echo 'Usage: make spec PROMPT="<your feature request>"'; exit 2; fi
	@echo "🚀 Processing fresh prompt → validated spec…"
	@$(PYTHON) scripts/run_pipeline.py --prompt "$(PROMPT)"

# End-to-end: spec the feature THEN emit the plan prompt for it.
# Requires Python 3.10+ for the walrus operator (used inline below).
spec-and-plan:
	@if [ -z "$(PROMPT)" ]; then echo 'Usage: make spec-and-plan PROMPT="<your feature request>"'; exit 2; fi
	@echo "🚀 End-to-end: fresh prompt → validated spec → plan prompt"
	@$(PYTHON) scripts/run_pipeline.py --prompt "$(PROMPT)"
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

check:
	@echo "📋 Showing first entry from $(OUTPUT):"
	@head -1 $(OUTPUT) | jq .

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
	@echo "  make plan SPEC=<p>                  Emit the COMMAND_RUNWAY plan prompt for a spec"
	@echo "                                      <p> = path/to/spec.yaml OR data/<f>.jsonl#<index>"
	@echo "  make test                           Run the validator + plan test suite"
	@echo "  make clean                          Delete output file"
