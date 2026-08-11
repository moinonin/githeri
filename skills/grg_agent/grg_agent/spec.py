# GRG Agent Specification

## Overview
A GRG (Geometric Reasoning Governor) Agent that treats LLM as a skill/tool rather than a wrapper. The agent uses GRG as a strategic layer for planning, monitoring, and diversity control.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GRG AGENT                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  PLANNER    │  │  MONITOR    │  │  DIVERSITY CONTROLLER   │  │
│  │  - Decompose│  │  - GRG Track│  │  - Prompt variation     │  │
│  │  - Strategy │  │  - Evaluate │  │  - Temperature sched    │  │
│  │  - Tools    │  │  - Oracle   │  │  - Candidate pool       │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬────────────┘  │
│         │                │                      │             │
│         ▼                ▼                      ▼             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    LLM SKILL                            │  │
│  │  generate(prompt, strategy) → candidates                │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. LLM Skill (`llm_skill.py`)
- Wraps a model (PyTorch/MLX) with unified `generate()` interface
- Supports: temperature, top-p, max_tokens, custom stopping
- Returns: text, logprobs, hidden_states (optional)

### 2. GRG Monitor (`monitor.py`)
- Reuses existing `AlphaMomentumTracker` and `compute_structural_alpha`
- Scores candidate trajectories with composite confidence
- Provides `score_candidate(logprobs)` and `score_batch(candidates)`

### 3. Diversity Controller (`diversity.py`)
- **Prompt variations**: rephrasing, few-shot, chain-of-thought, temperature
- **Strategy variations**: different algorithms, decompositions, approaches
- **Temperature scheduling**: adaptive per-iteration
- **Candidate pool**: maintains diversity via embedding distance

### 4. Planner (`planner.py`)
- Decomposes task into strategies
- Selects tools/approaches per subtask
- Manages iteration budget

### 5. GRG Agent (`agent.py`)
- Orchestrates all components
- Main loop: Plan → Generate → Monitor → Iterate
- Maintains trajectory state across iterations

### 6. Verifier (`verifier.py`) - Optional
- Code execution verification
- Type checking
- Test running

## Data Structures

```python
@dataclass
class Candidate:
    text: str
    logprobs: List[float]
    strategy: str
    iteration: int
    score: Optional[Score] = None
    verified: bool = False

@dataclass
class Score:
    composites: List[float]
    mean_composite: float
    grg_stats: Dict  # alpha, v_alpha, horizon, etc.

@dataclass
class Strategy:
    name: str
    prompt: str
    temperature: float
    top_p: float
    description: str

@dataclass
class TrajectoryState:
    candidates: List[Candidate]
    iteration: int
    grg_history: List[Dict]
    best_candidate: Optional[Candidate]
```

## Agent Loop

```
1. PLAN: decompose task → strategies[]
2. For each strategy:
   a. Generate diverse candidates (diversity.variants())
   b. Score with GRG monitor
   c. Add to candidate pool
3. MONITOR: score all candidates, update GRG state
4. SELECT: best candidate by GRG composite
5. VERIFY: external tools (execution, types, tests)
5. ITERATE: if not verified and iterations < max:
   - Analyze failure
   - Update strategy/diversity
   - GOTO 2
6. RETURN: best verified candidate
```

## Configuration

```python
@dataclass
class GRGAgentConfig:
    model_id: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    
    max_iterations: int = 5
    candidates_per_strategy: int = 3
    max_candidates: int = 15
    
    grg_window: int = 16
    grg_threshold_mult: float = 1.5
    alpha_critical: float = 0.1
    horizon_critical: float = 5.0
    
    diversity_temperature_range: Tuple[float, float] = (0.3, 1.5)
    diversity_min_cosine: float = 0.3
    
    temperature: float = 0.8
    top_p: float = 0.9
    max_tokens: int = 256
```

## File Structure

```
examples/grg_agent/
├── __init__.py
├── config.py              # GRGAgentConfig
├── llm_skill.py           # LLMSkill wrapper
├── monitor.py             # GRGMonitor (reuse AlphaMomentumTracker)
├── diversity.py           # DiversityController
├── planner.py             # CodePlanner
├── verifier.py            # CodeVerifier (execution, types)
├── agent.py               # GRGAgent (main orchestrator)
├── state.py               # TrajectoryState, Candidate, Score
├── spec.py                # This spec
├── test_agent.py          # Integration tests
└── README.md
```

## Integration Points

### Reuses from grg_inference:
- `AlphaMomentumTracker` → `monitor.py`
- `compute_structural_alpha` → `monitor.py`
- `composite_confidence` → `monitor.py`

### Reuses from grg_trainers:
- `LMWithValueHead` concept → `llm_skill.py`
- LoRA setup → `llm_skill.py`

### New:
- `DiversityController` - explicit diversity management
- `CodePlanner` - task decomposition
- `GRGAgent` - orchestration
- `TrajectoryState` - persistent memory

## Success Metrics

1. **Oracle improvement**: >60% on eval_prompts (vs 33% base, 73% oracle)
2. **GRG selector**: >50% pass@1 (vs 33% trained)
3. **Diversity**: Candidate cosine similarity < 0.5
4. **Iterations**: Typically converge in 2-3 iterations
6. **Training**: GRG loss decreases over iterations

## Implementation Priority

1. **State & Config** (foundation)
2. **LLM Skill** (model interface)
3. **Monitor** (reuse GRG)
4. **Diversity Controller** (core innovation)
5. **Planner** (task decomposition)
6. **Agent** (orchestration)
7. **Verifier** (optional, execution)
8. **Tests & Integration**

---

*This spec defines a GRG Agent where GRG is the strategic brain and LLM is a skill tool.*