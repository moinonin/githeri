.PHONY: generate check clean help

N ?= 5
OUTPUT = data/training_data.jsonl

generate:
	@echo "🚀 Generating $(N) prompt–spec pairs…"
	python scripts/run_pipeline.py $(N)

check:
	@echo "📋 Showing first entry from $(OUTPUT):"
	@head -1 $(OUTPUT) | jq .

clean:
	@echo "🧹 Removing $(OUTPUT)"
	rm -f $(OUTPUT)

help:
	@echo "Usage:"
	@echo "  make generate N=10    Generate N pairs (default 5)"
	@echo "  make check            Pretty-print first pair"
	@echo "  make clean            Delete output file"