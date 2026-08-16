---
name: grg_agent
description: "GRG-guided autonomous coding agent with multi-provider LLM support (Ollama + Hermes Proxy)"
version: 1.1.0
author: GRG Team
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coding-agent, grg, autonomous, quality, reasoning, ollama, hermes-proxy]
    related_skills: [grg-inference-pipeline, grg-training-pipeline, command-runway-pattern]
---

# GRG Agent Skill

The **GRG Agent** is a Hermes skill that provides an autonomous coding agent guided by Geometric Reasoning Governor (GRG) — a lightweight trajectory monitoring system that detects quality collapse in LLM generations without requiring a separate judge model.

Supports **two LLM providers**: local Ollama models (free, offline, logprobs) and Hermes Proxy (remote API providers — NVIDIA, OpenAI, xAI, etc.).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      HERMES PLATFORM                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  PROVIDER CONFIG │  │  HERMES PROXY   │  │  PLUGINS/SKILLS│  │
│  │  (config.yaml,   │  │  (OpenAI-compat │  │  - grg_agent   │  │
│  │   env vars,      │  │   local proxy)  │  │  - other skills│  │
│  │   OAuth tokens)  │  │  localhost:8465 │  │                │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬───────┘  │
│           │                    │                    │          │
│           ▼                    ▼                    ▼          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    GRG AGENT SKILL                      │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────────┐   │  │
│  │  │ PLANNER │ │ MONITOR │ │ DIVERSITY CONTROLLER    │   │  │
│  │  └────┬────┘ └────┬────┘ └───────────┬────────────┘   │  │
│  │       │         │                    │                │  │
│  │       ▼         ▼                    ▼                │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │       MULTI-PROVIDER LLM CLIENT                 │  │  │
│  │  │  ┌──────────────┐    ┌──────────────────────┐   │  │  │
│  │  │  │ OllamaClient │    │ HermesProxyClient   │   │  │  │
│  │  │  │ (local:11434)│    │ (proxy:8465)        │   │  │  │
│  │  │  └──────────────┘    └──────────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Providers

| Provider | Key | Backend | Requires | Logprobs | Cost |
|----------|-----|---------|----------|----------|------|
| `ollama` | `--provider ollama` | Local Ollama server | `ollama pull MODEL` | Yes | Free |
| `hermes` | `--provider hermes` | Hermes proxy (remote APIs) | `hermes proxy start` | Varies | Per-token |
| `auto` | `--provider auto` | Auto-detect (default) | Either above | — | — |

**Auto-detection order:**
1. `HERMES_PROXY_URL` env var set → Hermes Proxy
2. Ollama reachable at `127.0.0.1:11434` → Ollama
3. Fallback → Hermes Proxy default

## Commands

### `/grg solve <task>`
Solve a coding task with the GRG agent.

**Arguments:**
- `task` (string, required): The coding task to solve
- `iterations` (integer, optional, default: 5): Max iterations
- `model` (string, optional): Override model (passed to provider)

**Example:**
```
/grg solve "implement binary search in Python"
/grg solve "refactor auth module" --iterations 10
```

### `/grg analyze <file>`
Analyze code quality with GRG.

**Arguments:**
- `file` (string, required): Path to file to analyze

**Example:**
```
/grg analyze --file src/utils.py
```

### `/grg config`
Get/set GRG agent configuration.

**Arguments:**
- `action` (string, required): "get" or "set"
- `key` (string, for set): Config key
- `value` (any, for set): Config value

**Example:**
```
/grg config --action get
/grg config --action set --key temperature --value 0.7
```

### `/grg help`
Show help for GRG agent commands.

## Configuration

Configure the skill in `~/.hermes/config.yaml`:

```yaml
skills:
  grg_agent:
    enabled: true
    config:
      # LLM Provider
      llm_provider: "auto"                              # "auto" | "hermes" | "ollama"
      hermes_proxy_url: "http://localhost:8465/v1"       # or from HERMES_PROXY_URL env
      ollama_base_url: "http://127.0.0.1:11434/v1"       # local Ollama server
      ollama_default_model: "qwen2.5-coder:7b-instruct"  # default Ollama model

      # Agent Loop
      max_iterations: 5
      candidates_per_strategy: 3
      grg_window: 16
      grg_threshold_mult: 1.5
      temperature: 0.8
      top_p: 0.9
      max_tokens: 256
      verify_execution: true
      verify_timeout: 10
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `llm_provider` | string | `"auto"` | Provider: `"auto"`, `"hermes"`, or `"ollama"` |
| `hermes_proxy_url` | string | auto | Hermes proxy URL (or `HERMES_PROXY_URL` env) |
| `ollama_base_url` | string | `http://127.0.0.1:11434/v1` | Ollama API base URL |
| `ollama_default_model` | string | `qwen2.5-coder:7b-instruct` | Default Ollama model |
| `max_iterations` | integer | 5 | Max agent iterations |
| `candidates_per_strategy` | integer | 3 | Candidates per strategy |
| `max_candidates` | integer | 15 | Max candidate pool size |
| `grg_window` | integer | 16 | GRG tracking window |
| `grg_threshold_mult` | number | 1.5 | GRG threshold multiplier |
| `diversity_temperature_range` | array | [0.3, 1.5] | Temperature range for diversity |
| `temperature` | number | 0.8 | Default generation temperature |
| `top_p` | number | 0.9 | Default top-p |
| `max_tokens` | integer | 256 | Max tokens per generation |
| `verify_execution` | boolean | true | Verify code execution |
| `verify_timeout` | integer | 10 | Verification timeout (seconds) |

## Quick Start

### Option A: Ollama (local, free)
```bash
# 1. Pull a model
ollama pull qwen2.5-coder:7b-instruct

# 2. Run
make grg-test
# or
make grg-ollama TASK="implement fibonacci with memoization" MODEL="qwen2.5-coder:7b-instruct"
```

### Option B: Hermes Proxy (remote API providers)
```bash
# 1. Start Hermes proxy
hermes proxy start --port 8465 &

# 2. Run
make grg-hermes TASK="implement fibonacci with memoization" MODEL="nvidia/nemotron-3-ultra-550b-a55b"
```

### Option C: Auto-detect
```bash
make grg-auto TASK="implement fibonacci with memoization"
```

### Direct CLI (no Make)
```bash
cd examples/grg_agent

# Ollama
python -m grg_agent.hermes_skill "def binary_search(arr, target): ..." \
    --provider ollama --model qwen2.5-coder:7b-instruct

# Hermes proxy
python -m grg_agent.hermes_skill "def binary_search(arr, target): ..." \
    --provider hermes --model nvidia/nemotron-3-ultra-550b-a55b
```

## Makefile Targets

Run from repo root (`/Users/nickrotich/Desktop/portfolio/projects/python/grg`):

| Target | Description | Usage |
|--------|-------------|-------|
| `make grg-test` | Quick test with Ollama qwen2.5-coder:7b | `make grg-test` |
| `make grg-ollama` | Run with Ollama (local) | `make grg-ollama TASK="..." MODEL="..."` |
| `make grg-hermes` | Run with Hermes proxy (remote) | `make grg-hermes TASK="..." MODEL="..."` |
| `make grg-auto` | Auto-detect provider | `make grg-auto TASK="..."` |
| `make grg-install` | Install GRG agent in dev mode | `make grg-install` |
| `make grg-ollama-models` | List available Ollama models | `make grg-ollama-models` |
| `make grg-test-unit` | Run GRG agent unit tests | `make grg-test-unit` |

## How It Works

### GRG Monitor (AlphaMomentumTracker)
Tracks token log-prob trajectories during generation to detect:
- **Alpha collapse**: Over-confident low-entropy generations
- **Momentum loss**: Stalling or repetitive patterns
- **Quality signals**: Composite scores combining model probability, alpha (entropy), and variance-adjusted alpha

**Composite confidence** = `model_prob × α × (1 + max(0, Vα))`

### Diversity Controller
Maintains candidate diversity through:
- Temperature scheduling across strategies
- Cosine similarity filtering
- Strategy rotation (beam, diverse, stochastic, constrained)

### Planner
Generates structured plans for coding tasks, decomposing into verifiable stages.

### Verifier
Executes and type-checks generated code for correctness.

## Skill Integration

The skill entry point is in `grg_agent/hermes_skill.py`:

```python
from grg_agent.hermes_skill import GRGAgentSkill, create_skill

# Hermes loads the skill automatically when enabled
skill = create_skill(hermes_app, config)
result = await skill.on_command("grg:solve", {"task": "implement quicksort"})
```

The skill supports multiple LLM providers via a unified factory:

```python
from grg_agent.llm_client import create_llm_client

# Ollama (local)
client = create_llm_client("ollama",
    base_url="http://127.0.0.1:11434/v1",
    default_model="qwen2.5-coder:7b-instruct")

# Hermes proxy (remote)
client = create_llm_client("hermes",
    proxy_url="http://localhost:8465/v1")

# Auto-detect
client = create_llm_client("auto")

result = await client.generate(prompt="...", temperature=0.8, logprobs=True)
```

## Development

```bash
# Install in development mode
cd /Users/nickrotich/Desktop/portfolio/projects/python/grg/examples/grg_agent
pip install -e .

# Or via Makefile
make grg-install

# Run main test suite
pytest tests/ -v

# Run GRG agent tests
make grg-test-unit

# Type check
mypy grg_agent/
```

## Benefits

| Benefit | Explanation |
|---------|-------------|
| **Multi-provider** | Switch between local Ollama (free, logprobs) and remote API providers (Hermes proxy) |
| **Uses session's provider config** | Proxy reads same config.yaml, OAuth, env vars as main Hermes |
| **Portable** | Copy skill to another server, run `hermes proxy` or Ollama there, works automatically |
| **Ollama = logprobs** | Local models provide logprobs → GRG scoring works without API costs |
| **Cluster-aware** | Routes to 64GB Ryzen for heavy models, M1 for light — handled by proxy |
| **Unified config** | Single `config.yaml` for all LLM settings |
| **Skill ecosystem** | Works alongside other Hermes skills |
| **TUI/CLI integration** | `/grg solve` command in Hermes, `make grg-*` from terminal |
| **Provider fallback** | Auto-detect falls back from Hermes → Ollama → default |
| **Cost tracking** | Hermes's observability for token usage (proxy mode) |
| **Standard API** | OpenAI-compatible — works with any OpenAI client library |

## Requirements

- Python 3.10+
- **Ollama** running locally with at least one model pulled (`ollama pull qwen2.5-coder:7b-instruct`)
- **OR** Hermes with proxy running (`hermes proxy start --port 8465`)
- GRG core package (`pip install -e /path/to/grg`)

## License

MIT
