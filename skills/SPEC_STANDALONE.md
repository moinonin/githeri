# GRG Agent Standalone Package — Extraction Specification

## Overview

Transform the GRG Agent from a Hermes-coupled skill into a **standalone Python package** (`grg-agent`) that runs independently with local models (PyTorch/MLX) or any OpenAI-compatible endpoint. The package exposes the same GRG-guided autonomous coding loop without requiring Hermes.

**Goal:** `pip install grg-agent` → `from grg_agent import create_agent` → works immediately.

---

## Current State Analysis

The GRG Agent already has **two parallel orchestrators** sharing identical core components:

| File | LLM Backend | Hermes Dependency |
|------|-------------|-------------------|
| `agent.py` | Local model (`LLMSkill` — PyTorch + LoRA) | **None** — fully standalone |
| `agent_hermes.py` | Hermes proxy (`HermesLLMClient` — OpenAI-compat) | Requires running Hermes proxy |

**Core components (shared, zero Hermes deps):**
- `monitor.py` — GRG scoring (reuses `AlphaMomentumTracker`)
- `diversity.py` — Prompt/temperature variants + embedding pool
- `planner.py` — Task decomposition into strategies
- `verifier.py` — Code execution, type checking, tests
- `state.py` — `Candidate`, `Score`, `Strategy`, `TrajectoryState`
- `config.py` — `GRGAgentConfig` (has one Hermes-specific field)

---

## Target Architecture (Post-Extraction)

```
┌─────────────────────────────────────────────────────────────────┐
│                        grg-agent PACKAGE                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      PUBLIC API                             │  │
│  │  from grg_agent import GRGAgentConfig, create_agent         │  │
│  │  from grg_agent.llm import LLMSkill, OpenAISkill, MockSkill │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │   GRGAgent  │ │   Config    │ │   State     │ │  Extras   │  │
│  │ (orchestrator)             │ (dataclasses)  │ (cli, etc) │  │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └─────┬─────┘  │
│         │               │               │              │         │
│         ▼               ▼               ▼              ▼         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    CORE COMPONENTS                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌────────────┐   │  │
│  │  │ PLANNER  │ │ MONITOR  │ │ DIVERSITY  │ │ VERIFIER   │   │  │
│  │  └────┬────┘ └────┬────┘ └─────┬──────┘ └──────┬─────┘   │  │
│  │       │           │            │               │          │  │
│  │       ▼           ▼            ▼               ▼          │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │              LLMSkillProtocol (ABC)                  │  │  │
│  │  │  generate()  generate_batch()  get_embeddings()      │  │  │
│  │  │  get_logprobs()                                       │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │        ▲                 ▲                  ▲              │  │
│  │   ┌────┴────┐       ┌────┴────┐        ┌────┴────┐       │  │
│  │   │LLMSkill │       │OpenAISkill│      │MockSkill │       │  │
│  │   │(local)  │       │(proxy)    │      │(test)    │       │  │
│  │   └─────────┘       └───────────┘        └──────────┘       │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Extraction Plan

### Phase 1: Interface Definition (New File)

**File:** `grg_agent/interfaces.py`

```python
"""LLM Skill Protocol — unified interface for all backends."""

from typing import Protocol, List, Optional, Dict, Any
from dataclasses import dataclass
import torch


@dataclass
class GenerationResult:
    """Unified generation output across all backends."""
    text: str
    logprobs: Optional[List[float]] = None
    tokens: Optional[List[int]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None


@dataclass
class EmbeddingResult:
    """Unified embedding output."""
    embeddings: List[List[float]]
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMSkillProtocol(Protocol):
    """Protocol that all LLM backends must implement."""

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.8,
        top_p: float = 0.9,
        max_tokens: int = 256,
        logprobs: bool = True,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate single completion."""
        ...

    async def generate_batch(
        self,
        prompts: List[str],
        num_candidates: int = 1,
        **kwargs
    ) -> List[List[GenerationResult]]:
        """Generate multiple candidates per prompt."""
        ...

    def get_embeddings(self, texts: List[str], model: str = None) -> EmbeddingResult:
        """Get embeddings for diversity calculation."""
        ...

    def get_logprobs(self, prompt: str, completion: str) -> List[float]:
        """Get logprobs for given prompt+completion (for scoring existing code)."""
        ...
```

---

### Phase 2: Config Decoupling (`config.py`)

**Changes to `GRGAgentConfig`:**

```python
# REMOVE:
hermes_proxy_url: Optional[str] = None

# ADD (local model config):
model_id: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
device: str = "auto"  # "cuda", "mps", "cpu", "auto"
use_lora: bool = True
lora_r: int = 16
lora_alpha: int = 32
lora_dropout: float = 0.05
lora_target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"])
load_in_4bit: bool = False
load_in_8bit: bool = False
torch_dtype: str = "bfloat16"  # "float16", "bfloat16", "float32"

# GENERATION DEFAULTS (keep):
temperature: float = 0.8
top_p: float = 0.9
max_tokens: int = 256
```

**New field for backend selection:**
```python
llm_backend: str = "local"  # "local" | "openai" | "mock"
openai_base_url: Optional[str] = None  # for OpenAI-compatible endpoints
openai_api_key: str = "dummy"  # for OpenAI-compatible endpoints
```

---

### Phase 3: Backend Implementations

#### 3.1 Local Model Backend (Existing `llm_skill.py` → `llm/local.py`)

Minimal changes — already implements the protocol. Just:
- Add `GenerationResult`/`EmbeddingResult` return types
- Make `generate()` async (wrap sync in `asyncio.to_thread` or keep sync with protocol accepting both)
- Extract tokenizer access for diversity controller

#### 3.2 OpenAI-Compatible Backend (New `llm/openai.py`)

```python
"""OpenAI-compatible backend (vLLM, Ollama, TGI, Hermes proxy, OpenAI API)."""

from openai import AsyncOpenAI
from .interfaces import LLMSkillProtocol, GenerationResult, EmbeddingResult
from ..config import GRGAgentConfig


class OpenAISkill:
    """LLM backend for any OpenAI-compatible API."""

    def __init__(self, config: GRGAgentConfig):
        self.config = config
        self.client = AsyncOpenAI(
            base_url=config.openai_base_url or "http://localhost:8080/v1",
            api_key=config.openai_api_key,
        )
        self._model = config.model_id  # used as default model

    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self._model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.config.temperature),
            top_p=kwargs.get("top_p", self.config.top_p),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            logprobs=kwargs.get("logprobs", True),
            stop=kwargs.get("stop"),
        )
        choice = response.choices[0]
        logprobs_list = None
        if choice.logprobs and choice.logprobs.content:
            logprobs_list = [lp.logprob for lp in choice.logprobs.content]
        return GenerationResult(
            text=choice.message.content or "",
            logprobs=logprobs_list,
            finish_reason=choice.finish_reason,
            usage=dict(response.usage) if response.usage else None,
            model=response.model,
        )

    async def generate_batch(self, prompts: List[str], num_candidates: int = 1, **kwargs) -> List[List[GenerationResult]]:
        results = []
        for prompt in prompts:
            candidates = []
            for _ in range(num_candidates):
                candidates.append(await self.generate(prompt, **kwargs))
            results.append(candidates)
        return results

    def get_embeddings(self, texts: List[str], model: str = None) -> EmbeddingResult:
        # Sync call for embeddings (typically fast)
        import asyncio
        return asyncio.run(self._get_embeddings_async(texts, model))

    async def _get_embeddings_async(self, texts: List[str], model: str = None) -> EmbeddingResult:
        model = model or "text-embedding-3-small"
        response = await self.client.embeddings.create(model=model, input=texts)
        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            model=model,
            usage={"total_tokens": response.usage.total_tokens} if response.usage else None,
        )

    def get_logprobs(self, prompt: str, completion: str) -> List[float]:
        # Not directly supported by OpenAI API — would need logprobs on full text
        # Fallback: return empty list, monitor will use dummy score
        return []
```

#### 3.3 Mock Backend (Existing `test_hermes.py` → `llm/mock.py`)

For testing without any model.

---

### Phase 4: Unified Agent (`agent.py` Refactor)

**File:** `grg_agent/agent.py`

```python
"""GRG Agent — unified orchestrator accepting any LLMSkillProtocol."""

from typing import Optional
from .config import GRGAgentConfig
from .state import Candidate, TrajectoryState
from .interfaces import LLMSkillProtocol
from .monitor import GRGMonitor
from .diversity import DiversityController
from .planner import CodePlanner
from .verifier import CodeVerifier


class GRGAgent:
    """GRG-guided autonomous coding agent."""

    def __init__(
        self,
        config: GRGAgentConfig,
        llm: Optional[LLMSkillProtocol] = None,
    ):
        self.config = config

        # Create or use provided LLM backend
        if llm is None:
            llm = self._create_default_llm(config)
        self.llm = llm

        # Core components (unchanged)
        self.monitor = GRGMonitor(config)
        self.diversity = DiversityController(config, self._get_tokenizer())
        self.planner = CodePlanner(config)
        self.verifier = CodeVerifier(config)

        # Trajectory state
        self.trajectory = TrajectoryState()
        self.total_generations = 0
        self.total_verifications = 0
        self.iteration_times = []

    def _create_default_llm(self, config: GRGAgentConfig) -> LLMSkillProtocol:
        """Factory for default backend based on config."""
        if config.llm_backend == "local":
            from .llm.local import LLMSkill
            return LLMSkill(config)
        elif config.llm_backend == "openai":
            from .llm.openai import OpenAISkill
            return OpenAISkill(config)
        elif config.llm_backend == "mock":
            from .llm.mock import MockSkill
            return MockSkill()
        else:
            raise ValueError(f"Unknown llm_backend: {config.llm_backend}")

    def _get_tokenizer(self):
        """Get tokenizer for diversity embeddings (local backend only)."""
        if hasattr(self.llm, 'tokenizer'):
            return self.llm.tokenizer
        # Fallback: use a simple tokenizer for OpenAI/mock
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("gpt2")

    def solve(self, task: str, max_iterations: int = None) -> Candidate:
        """Main entry point — identical logic for all backends."""
        # ... existing solve() logic unchanged ...
        pass

    def get_stats(self) -> dict:
        """Get agent statistics."""
        # ... existing get_stats() ...
        pass


def create_agent(
    config: GRGAgentConfig,
    llm: Optional[LLMSkillProtocol] = None,
) -> GRGAgent:
    """Factory function — main public API."""
    return GRGAgent(config, llm)
```

---

### Phase 5: Package Structure

```
grg-agent/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── grg_agent/
│       ├── __init__.py           # Public exports
│       ├── config.py             # GRGAgentConfig
│       ├── state.py              # Candidate, Score, Strategy, TrajectoryState
│       ├── interfaces.py         # LLMSkillProtocol (NEW)
│       ├── monitor.py            # GRGMonitor (unchanged)
│       ├── diversity.py          # DiversityController (unchanged)
│       ├── planner.py            # CodePlanner (unchanged)
│       ├── verifier.py           # CodeVerifier (unchanged)
│       ├── agent.py              # GRGAgent (refactored)
│       └── llm/
│           ├── __init__.py       # Exports: LLMSkill, OpenAISkill, MockSkill
│           ├── local.py          # Local PyTorch model (from llm_skill.py)
│           ├── openai.py         # OpenAI-compatible (NEW)
│           └── mock.py           # Mock for testing (NEW)
├── tests/
│   ├── test_agent.py             # Integration tests
│   ├── test_components.py        # Unit tests
│   └── test_mock.py              # Mock backend tests
└── examples/
    ├── basic_usage.py
    ├── with_vllm.py
    ├── with_ollama.py
    └── with_hermes_proxy.py
```

---

### Phase 6: Packaging (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "grg-agent"
version = "0.1.0"
description = "GRG-guided autonomous coding agent — standalone package"
readme = "README.md"
license = {text = "MIT"}
authors = [{name = "GRG Team"}]
requires-python = ">=3.10"
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Software Development :: Code Generators",
]
dependencies = [
    "torch>=2.3",
    "transformers>=4.40",
    "accelerate>=0.30",
    "numpy>=1.24",
    "peft>=0.10",          # for local LoRA backend
    "openai>=1.30",        # for OpenAI-compatible backend
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.9",
]
local = [
    "bitsandbytes>=0.43",  # for 4-bit quantization (CUDA only)
]
vllm = [
    "vllm>=0.5",           # for vLLM backend example
]

[project.urls]
Homepage = "https://github.com/yourorg/grg"
Repository = "https://github.com/yourorg/grg"
Issues = "https://github.com/yourorg/grg/issues"

[tool.setuptools.packages.find]
where = ["src"]
include = ["grg_agent*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
```

---

### Phase 7: Public API (`__init__.py`)

```python
"""GRG Agent — Autonomous coding with GRG quality guidance.

Usage:
    from grg_agent import GRGAgentConfig, create_agent

    config = GRGAgentConfig(model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    agent = create_agent(config)
    result = agent.solve("def two_sum(nums, target): ...")
    print(result.text)

With OpenAI-compatible endpoint (vLLM, Ollama, Hermes proxy):
    config = GRGAgentConfig(
        llm_backend="openai",
        openai_base_url="http://localhost:8000/v1",  # vLLM
        model_id="qwen2.5-coder:7b",
    )
    agent = create_agent(config)
"""

from .config import GRGAgentConfig
from .state import Candidate, Score, Strategy, TrajectoryState
from .agent import GRGAgent, create_agent
from .interfaces import LLMSkillProtocol, GenerationResult, EmbeddingResult

# Backends (optional imports)
try:
    from .llm.local import LLMSkill
except ImportError:
    LLMSkill = None

try:
    from .llm.openai import OpenAISkill
except ImportError:
    OpenAISkill = None

try:
    from .llm.mock import MockSkill
except ImportError:
    MockSkill = None

__all__ = [
    "GRGAgentConfig",
    "Candidate",
    "Score",
    "Strategy",
    "TrajectoryState",
    "GRGAgent",
    "create_agent",
    "LLMSkillProtocol",
    "GenerationResult",
    "EmbeddingResult",
    "LLMSkill",
    "OpenAISkill",
    "MockSkill",
]

__version__ = "0.1.0"
```

---

## Usage Examples

### 1. Local Model (Default)
```python
from grg_agent import GRGAgentConfig, create_agent

config = GRGAgentConfig(
    model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct",
    device="cuda",  # or "mps", "cpu", "auto"
    use_lora=True,
    max_iterations=5,
)

agent = create_agent(config)
candidate = agent.solve("""
def two_sum(nums, target):
    \"\"\"Return indices of two numbers adding to target.\"\"\"
""")

print(f"Verified: {candidate.verified}")
print(f"Composite: {candidate.score.mean_composite:.3f}")
print(candidate.text)
```

### 2. vLLM / OpenAI-Compatible Endpoint
```python
from grg_agent import GRGAgentConfig, create_agent

config = GRGAgentConfig(
    llm_backend="openai",
    openai_base_url="http://localhost:8000/v1",  # vLLM server
    openai_api_key="dummy",  # vLLM ignores
    model_id="qwen2.5-coder:7b",
    max_iterations=5,
)

agent = create_agent(config)
candidate = agent.solve("def fibonacci(n): ...")
```

### 3. Ollama
```python
config = GRGAgentConfig(
    llm_backend="openai",
    openai_base_url="http://localhost:11434/v1",
    model_id="qwen2.5-coder:7b",
)
```

### 4. Hermes Proxy (Current Skill Backend)
```python
config = GRGAgentConfig(
    llm_backend="openai",
    openai_base_url="http://localhost:8080/v1",  # hermes proxy
    model_id="default",  # uses Hermes config.yaml routing
)
```

### 5. Testing (No Model)
```python
from grg_agent import GRGAgentConfig, create_agent, MockSkill

config = GRGAgentConfig(max_iterations=2)
agent = create_agent(config, llm=MockSkill())
candidate = agent.solve("def hello(): ...")
```

---

## Migration from Current Code

### For Hermes Skill Users (No Change Needed)
The Hermes skill (`hermes_skill.py`) continues working exactly as before — it uses `HermesLLMClient` which is the OpenAI-compatible backend. Just update imports:

```python
# Old (in hermes_skill.py)
from .agent_hermes import GRGAgentHermes
from .llm_client import HermesLLMClient

# New (after extraction)
from grg_agent import GRGAgentConfig, create_agent
from grg_agent.llm.openai import OpenAISkill  # or use create_agent with llm_backend="openai"
```

### For Local Agent Users (`agent.py`)
```python
# Old
from examples.grg_agent import GRGAgentConfig, create_agent

# New (after pip install grg-agent)
from grg_agent import GRGAgentConfig, create_agent
```

### For Test Users (`test_hermes.py`)
```python
# Old
from examples.grg_agent.test_hermes import MockHermesClient

# New
from grg_agent.llm.mock import MockSkill
```

---

## Testing Strategy

### Unit Tests (No Model)
```bash
# Fast, runs in CI
pytest tests/test_components.py tests/test_mock.py -v
```

### Integration Tests (Local Model)
```bash
# Requires GPU, runs nightly
pytest tests/test_agent.py -v -k "local"
```

### Integration Tests (OpenAI Compatible)
```bash
# Requires running vLLM/Ollama/Hermes proxy
OPENAI_BASE_URL=http://localhost:8000/v1 pytest tests/test_agent.py -v -k "openai"
```

---

## Timeline Estimate

| Phase | Task | Effort |
|-------|------|--------|
| 1 | `interfaces.py` protocol definition | 30 min |
| 2 | Config decoupling (`config.py`) | 20 min |
| 3 | Backend implementations (`llm/local.py`, `llm/openai.py`, `llm/mock.py`) | 2 hrs |
| 4 | Agent refactor (`agent.py`) | 1 hr |
| 5 | Package structure + `pyproject.toml` | 45 min |
| 6 | Public API (`__init__.py`) | 15 min |
| 7 | Tests migration | 1 hr |
| 8 | Examples + README | 45 min |
| **Total** | | **~7 hrs** |

---

## Backwards Compatibility

| Current Import | New Import | Status |
|----------------|------------|--------|
| `from examples.grg_agent import GRGAgentConfig` | `from grg_agent import GRGAgentConfig` | ✅ Alias in `examples/grg_agent/__init__.py` |
| `from examples.grg_agent.agent import GRGAgent` | `from grg_agent import GRGAgent` | ✅ Alias |
| `from examples.grg_agent.agent_hermes import GRGAgentHermes` | `from grg_agent.llm.openai import OpenAISkill` | ⚠️ Different API, thin wrapper provided |
| `from examples.grg_agent.llm_skill import LLMSkill` | `from grg_agent.llm.local import LLMSkill` | ✅ Alias |
| `from examples.grg_agent.llm_client import HermesLLMClient` | `from grg_agent.llm.openai import OpenAISkill` | ⚠️ Different API |

**Strategy:** Keep `examples/grg_agent/` as a **compat layer** that re-exports from `grg_agent` with deprecation warnings.

---

## Future Extensions (Post-Extraction)

- [ ] **vLLM backend** — native async engine, no HTTP overhead
- [ ] **MLX backend** — Apple Silicon native (`mlx-lm`)
- [ ] **TGI backend** — HuggingFace Text Generation Inference
- [ ] **Multi-model routing** — different models per strategy
- [ ] **GRG-guided training** — composite as reward signal
- [ ] **Persistent trajectory store** — SQLite/Redis for resume
- [ ] **Web API** — FastAPI wrapper for agent-as-service
- [ ] **Spec-Forge integration** — validated spec → agent execution

---

## License

MIT — Part of the GRG (Geometric Reasoning Governor) project.