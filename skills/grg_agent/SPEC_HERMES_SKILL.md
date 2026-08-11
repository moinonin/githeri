# GRG Agent as Hermes Skill - Specification (REVISED)

## Overview
Transform the GRG Agent from a local-model system into a **Hermes Skill** that uses the same LLM provider configuration as the running Hermes instance. The skill should be portable — copy to another server with a fresh Hermes, and it picks up that server's provider config automatically.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      HERMES PLATFORM                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  PROVIDER CONFIG │  │  HERMES PROXY   │  │  PLUGINS/SKILLS│  │
│  │  (config.yaml,   │──│  (OpenAI-compat │──│  - grg_agent   │  │
│  │   env vars,      │  │   local proxy)  │  │  - other skills│  │
│  │   OAuth tokens)  │  │  localhost:PORT │  │                │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬───────┘  │
│           │                    │                    │          │
│           │   SKILL READS      │   SKILL CALLS      │          │
│           │   SAME CONFIG      │   PROXY ENDPOINT   │          │
│           ▼                    ▼                    ▼          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    GRG AGENT SKILL                      │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────────┐   │  │
│  │  │ PLANNER │ │ MONITOR │ │ DIVERSITY CONTROLLER    │   │  │
│  │  └────┬────┘ └────┬────┘ └───────────┬────────────┘   │  │
│  │       │         │                    │                │  │
│  │       ▼         ▼                    ▼                │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │    HERMES LLM CLIENT (OpenAI-compat proxy)      │  │  │
│  │  │  chat.completions.create(model, messages, ...)  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Architecture Decision

**The skill does NOT have direct access to `hermes_app.llm_client`** — the AIAgent doesn't expose its internal OpenAI client in a way that external skills can use. The spec's assumption at line 102 (`self.llm_client = hermes_app.llm_client`) is not achievable with the current Hermes API.

**Instead, the skill uses the Hermes OpenAI-compatible proxy (`hermes proxy`)** which:
- Runs as a local HTTP server (typically `http://localhost:8080/v1` or similar)
- Uses the exact same provider config, credentials, and model routing as the main Hermes session
- Is started by the user when they run `hermes proxy` (or can be auto-started)
- Provides a standard OpenAI API interface — any OpenAI-compatible client works

This achieves the goal: the skill uses the *same* provider config as the current session, is portable to any server running Hermes proxy, and requires zero code changes when moved.

## Hermes LLM Client Interface (Revised)

```python
class HermesLLMClient:
    """Unified interface to Hermes's OpenAI-compatible proxy."""

    def __init__(self, proxy_url: str = None):
        # Auto-discover proxy URL from env or default
        self.proxy_url = proxy_url or os.environ.get("HERMES_PROXY_URL") or "http://localhost:8080/v1"
        self.client = AsyncOpenAI(base_url=self.proxy_url, api_key="hermes-proxy")  # key ignored by proxy

    async def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 256,
        logprobs: bool = True,
        stop: List[str] = None,
    ) -> GenerationResult:
        """Use Hermes proxy (inherits session's provider/model routing)."""
        # If model is None, proxy uses the default coding model from config
        response = await self.client.chat.completions.create(
            model=model or "default",  # "default" is handled by proxy
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            logprobs=logprobs,
            stop=stop,
        )
        # ... extract result

    async def get_embeddings(self, texts: List[str], model: str = None) -> EmbeddingResult:
        """Get embeddings via proxy."""
        response = await self.client.embeddings.create(
            model=model or "text-embedding-3-small",
            input=texts,
        )
        # ... extract result
```

## Skill Integration Points

### 1. Hermes Proxy (Started Separately)
```bash
# User starts proxy (once per session/server)
hermes proxy
# Listens on http://localhost:8080/v1 by default
# Uses config.yaml providers, OAuth, model routing
```

### 2. Skill Config (config.yaml + Skill Config)
```yaml
skills:
  grg_agent:
    enabled: true
    config:
      max_iterations: 5
      candidates_per_strategy: 3
      grg_window: 16
      threshold_mult: 1.5
      # Proxy connection (optional - auto-discovered)
      hermes_proxy_url: "http://localhost:8080/v1"  # or from HERMES_PROXY_URL env
```

### 3. Skill Entry Point (Revised)
```python
# examples/grg_agent/hermes_skill.py
class GRGAgentSkill:
    """Hermes skill entry point - uses Hermes proxy for LLM access."""

    def __init__(self, hermes_app=None, config: Dict[str, Any] = None):
        self.app = hermes_app
        self.config = config or {}

        # Get proxy URL from skill config or env (NOT from hermes_app)
        proxy_url = self.config.get('hermes_proxy_url') or os.environ.get('HERMES_PROXY_URL')
        
        agent_config = GRGAgentConfig(...)
        self.llm_client = HermesLLMClient(proxy_url=proxy_url)
        self.agent = GRGAgentHermes(agent_config, self.llm_client)

    async def on_command(self, command: str, args: dict):
        if command == "grg:solve":
            return await self.agent.solve(args["task"])
        # ...
```

### 4. CLI Commands
```bash
# In Hermes TUI or CLI (after skill installed and proxy running)
> /grg solve "implement binary search"
> /grg analyze --file src/utils.py
> grg-agent --task "refactor auth module" --iterations 5
```

## File Structure (Hermes Skill)

```
~/.hermes/skills/grg_agent/           # User-installed skill
├── skill.yaml                        # Skill manifest
├── grg_agent/
│   ├── __init__.py
│   ├── config.py                     # Skill config (not model config)
│   ├── state.py                      # Same data structures
│   ├── llm_client.py                 # Hermes LLM client wrapper (OpenAI proxy)
│   ├── monitor.py                    # GRG Monitor (reuse AlphaMomentumTracker)
│   ├── diversity.py                  # Diversity Controller
│   ├── planner.py                    # Code Planner
│   ├── verifier.py                   # Code Verifier (execution, types)
│   ├── agent_hermes.py               # GRG Agent orchestration (Hermes version)
│   └── hermes_skill.py               # Hermes integration entry point
├── skill.yaml                        # Skill manifest
└── README.md
```

## Skill Manifest (skill.yaml)

```yaml
name: grg_agent
version: "1.0.0"
description: "GRG-guided autonomous coding agent using Hermes LLM proxy"
author: "GRG Team"
license: "MIT"

entry_point: "grg_agent.hermes_skill:GRGAgentSkill"
commands:
  - name: "grg:solve"
    description: "Solve a coding task with GRG agent"
    args:
      - name: "task"
        type: "string"
        required: true
      - name: "iterations"
        type: "integer"
        default: 5
      - name: "model"
        type: "string"
        description: "Override default coding model (passed to proxy)"

  - name: "grg:analyze"
    description: "Analyze code quality with GRG"
    args:
      - name: "file"
        type: "string"
        required: true

config_schema:
  max_iterations: {type: integer, default: 5}
  candidates_per_strategy: {type: integer, default: 3}
  max_candidates: {type: integer, default: 15}
  grg_window: {type: integer, default: 16}
  threshold_mult: {type: number, default: 1.5}
  diversity_temperature_range: {type: array, default: [0.3, 1.5]}
  temperature: {type: number, default: 0.8}
  top_p: {type: number, default: 0.9}
  max_tokens: {type: integer, default: 256}
  verify_execution: {type: boolean, default: true}
  verify_timeout: {type: integer, default: 10}
  hermes_proxy_url: {type: string, required: false, description: "Hermes proxy URL (default: http://localhost:8080/v1 or HERMES_PROXY_URL env)"}
```

## Benefits of This Approach

| Benefit | Explanation |
|---------|-------------|
| **Uses session's provider config** | Proxy reads same config.yaml, OAuth, env vars as main Hermes |
| **Portable** | Copy skill to another server, run `hermes proxy` there, works automatically |
| **No local models needed** | Uses whatever providers the host Hermes is configured with |
| **Cluster-aware** | Routes to 64GB Ryzen for heavy models, M1 for light — handled by proxy |
| **Unified config** | Single `config.yaml` for all LLM settings |
| **Skill ecosystem** | Works alongside other Hermes skills |
| **TUI/CLI integration** | `/grg solve` command in Hermes |
| **Provider fallback** | Automatic fallback if primary provider fails (handled by proxy) |
| **Cost tracking** | Hermes's observability for token usage |
| **Standard API** | OpenAI-compatible — works with any OpenAI client library |

## Implementation Priority

1. **Hermes LLM Client** - Wrapper around OpenAI-compatible proxy (auto-discovers proxy URL)
2. **Proxy URL Discovery** - Env var `HERMES_PROXY_URL` → skill config → default `http://localhost:8080/v1`
3. **Agent Core** - Reuse existing components (monitor, diversity, planner, verifier)
4. **Skill Entry Point** - `GRGAgentSkill` class for Hermes (accepts proxy URL from config/env)
5. **Commands** - `/grg solve`, `/grg analyze`
6. **Skill Manifest** - `skill.yaml` for installation
7. **Tests** - Integration tests with running proxy

## Migration Path

The existing `examples/grg_agent/` becomes the **skill source**. When installing as a Hermes skill:

```bash
# Install skill (one-time)
mkdir -p ~/.hermes/skills/grg_agent
cp -r examples/grg_agent/* ~/.hermes/skills/grg_agent/
# Create skill.yaml from SPEC_HERMES_SKILL.md manifest section

# Start proxy (per session/server)
hermes proxy &

# Use in Hermes
> /grg solve "implement fibonacci"
```

```python
# In Hermes skill, the llm_client is now the proxy wrapper
from .llm_client import HermesLLMClient
from .agent_hermes import GRGAgentHermes
from .hermes_skill import GRGAentSkill
```

---

*This revised spec defines the GRG Agent as a first-class Hermes skill using the Hermes OpenAI-compatible proxy for LLM access — portable, config-driven, and aligned with actual Hermes architecture.*