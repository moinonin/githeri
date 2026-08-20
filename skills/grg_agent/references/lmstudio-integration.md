# LM Studio Integration with GRG Agent

## Overview
LM Studio can be used as an OpenAI-compatible provider with the GRG Agent by configuring the `OllamaClient` with custom `api_key` support.

## Configuration

### LM Studio Settings
1. Open LM Studio
2. Settings → Developer → "Start Server" (port 1234 by default)
3. Load model: `qwen2.5-coder-14b-instruct-uncensored`

### GRG Agent Configuration
The `OllamaClient` now supports custom `api_key` for LM Studio:

```python
from grg_agent.llm_client import OllamaClient

client = OllamaClient(
    base_url="http://127.0.0.1:1234/v1",
    default_model="qwen2.5-coder-14b-instruct-uncensored",
    api_key="lm-studio"  # Custom key for LM Studio
)
```

### Hermes Skill Config
In `~/.hermes/config.yaml`:
```yaml
skills:
  grg_agent:
    enabled: true
    config:
      llm_provider: "ollama"
      ollama_base_url: "http://127.0.0.1:1234/v1"
      ollama_default_model: "qwen2.5-coder-14b-instruct-uncensored"
```

### Makefile Usage
```bash
# Full pipeline with LM Studio
make grg-full PROMPT="Your feature request" \
    PROVIDER=lmstudio MODEL="qwen2.5-coder-14b-instruct-uncensored" BASE_URL="http://localhost:1234/v1"

# Single spec with LM Studio
make grg-spec PROMPT="Your feature request" \
    PROVIDER=lmstudio MODEL="qwen2.5-coder-14b-instruct-uncensored" BASE_URL="http://localhost:1234/v1"
```

## Verified Working Model

**qwen2.5-coder-14b-instruct-uncensored** - First local model to complete full GRG pipeline end-to-end:
- NL → Spec → Plan → Execute → Runbook
- Works with GRG Agent multi-strategy generation (standard, decompose, test_first, refine)
- Execution-based verification (syntax + runtime)
- GRG quality gates: composite scoring, diversity control, convergence detection

### Why This Model Works
- 14B parameter coder model fine-tuned for code generation
- Uncensored variant removes alignment filters that interfere with code structure
- OpenAI-compatible API in LM Studio works with GRG's `OllamaClient` (custom `api_key` support)
- Sufficient context window for spec + plan generation tasks
- Produces valid imports, proper error handling, and correct HTTP status codes

## Performance Comparison

| Approach | Model | Success Rate | Speed | Best For |
|----------|-------|--------------|-------|----------|
| GRG Full Pipeline | qwen2.5-coder-14b (LM Studio) | ~100% | ~260s/spec | Specific features |
| make generate | specforge-128k:latest (Ollama) | ~70% | ~170s/spec | Bulk corpus |
| make generate | qwen2.5-coder-14b (LM Studio) | ~20-33% | ~300-400s/spec | Testing |

## Known Issues & Fixes

### Issue: Missing import statements in blueprints
**Fix**: Added explicit requirement in SYSTEM_PROMPT and retry feedback:
> "CRITICAL: For CREATE goals, blueprint MUST include all necessary import statements at the top."

### Issue: Near-duplicate http verifications
**Fix**: Added "DISTINCT target" reminder in retry feedback:
> "CRITICAL: Each goal must verify a DISTINCT target. Different (type, url) for http, different (type, path) for file_exists, different (type, command) for cli."

### Issue: Missing acceptance_criteria for CREATE goals
**Fix**: Added "acceptance_criteria required" reminder in SYSTEM_PROMPT and retry feedback.

## Integration Notes

### LM Studio → GRG Agent Flow
1. LM Studio runs OpenAI-compatible server on port 1234
2. GRG Agent's `OllamaClient` connects with custom `api_key="lm-studio"`
3. Skill config reads `ollama_base_url` and `ollama_default_model` from config
4. `create_llm_client("ollama", base_url=..., default_model=..., api_key=...)` creates the client
5. Agent runs multi-strategy generation with GRG quality gates
6. Verification executes code in temp files (syntax + runtime checks)

### Makefile Integration
The Makefile was updated to support `PROVIDER=lmstudio`:
```makefile
grg-spec:
    @if [ "$(PROVIDER)" = "lmstudio" ]; then \
        MODEL="$(MODEL)" BASE_URL="$(BASE_URL)" $(PYTHON) scripts/grg_make_spec.py ollama "$$PROMPT"; \
    else \
        $(PYTHON) scripts/grg_make_spec.py $(PROVIDER) "$$PROMPT"; \
    fi
```

This maps `lmstudio` provider to `ollama` internally with env vars for MODEL and BASE_URL.