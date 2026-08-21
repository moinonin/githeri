# GRG Agent Skill - Deployment Guide

Install the GRG Agent skill on a new server with Hermes.

---

## Prerequisites

- Python 3.10+
- Hermes installed and configured
- Network access to LLM provider (Hermes proxy or Ollama)

---

## Step 1: Install GRG Core Package

The skill depends on the `grg` package (Geometric Reasoning Governor).

```bash
# Clone and install in editable mode
git clone https://github.com/your-org/grg.git ~/grg
cd ~/grg && pip install -e .

# Verify
python3 -c "import grg; print(grg.__version__)"
```

---

## Step 2: Deploy Skill Directory

Copy the skill to Hermes' skill directory:

```bash
# From your local machine
scp -r ~/.hermes/skills/grg_agent/ user@target-server:~/.hermes/skills/

# OR on target server directly
git clone <your-skills-repo> ~/.hermes/skills/grg_agent
```

**Required structure:**
```
~/.hermes/skills/grg_agent/
├── grg_agent/              # Python package (MUST be here)
│   ├── __init__.py
│   ├── hermes_skill.py     # Entry point
│   ├── config.py
│   ├── llm_client.py
│   ├── agent_hermes.py
│   └── diversity.py
├── README.md
├── pyproject.toml
├── skill.yaml              # Skill manifest
└── references/
```

---

## Step 3: Configure Hermes

Edit `~/.hermes/config.yaml`:

```yaml
skills:
  grg_agent:
    enabled: true
    config:
      # LLM Provider: "auto" | "hermes" | "ollama"
      llm_provider: "hermes"
      
      # Hermes Proxy (remote APIs via OpenAI-compatible proxy)
      hermes_proxy_url: "http://localhost:8465/v1"
      
      # Ollama (local, free, provides logprobs for GRG scoring)
      ollama_base_url: "http://127.0.0.1:11434/v1"
      ollama_default_model: "qwen2.5-coder:7b-instruct"
      
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

---

## Step 4: Start LLM Provider

### Option A: Hermes Proxy (Recommended for remote APIs)

```bash
# Start proxy on port 8465
hermes proxy start --port 8465 &

# Verify
curl http://localhost:8465/health
# {"status": "ok", "upstream": "Nous Portal", "authenticated": true}

# List available models
curl http://localhost:8465/v1/models | jq '.data[].id'
```

**Free models available:**
- `poolside/laguna-s-2.1:free`
- `poolside/laguna-xs-2.1:free`
- `tencent/hy3:free`
- `stepfun/step-3.7-flash:free`
- `upstage/solar-pro4:free`
- `meituan/longcat-2.0:free`

### Option B: Ollama (Local, provides logprobs)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model with logprobs support
ollama pull qwen2.5-coder:7b-instruct

# Start server
ollama serve &
```

---

## Step 5: Verify Installation

```bash
# Test GRG agent directly
cd ~/.hermes/skills/grg_agent
python3 -m grg_agent.hermes_skill "def hello(): return 'world'" --model poolside/laguna-s-2.1:free

# Expected: Verified code output
```

```bash
# Or via Hermes slash command (in Hermes TUI/CLI)
/grg solve "implement binary search"
```

---

## Step 6: Optional - Add to Project for Version Control

```bash
# In your project repo
mkdir -p skills/
cp -r ~/.hermes/skills/grg_agent skills/

# Symlink so Hermes uses your version-controlled copy
ln -sf $(pwd)/skills/grg_agent ~/.hermes/skills/grg_agent
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: grg` | Run Step 1: `pip install -e ~/grg` |
| `ModuleNotFoundError: grg_agent` | Skill dir must be at `~/.hermes/skills/grg_agent/grg_agent/` |
| Proxy connection refused | Start `hermes proxy start --port 8465` |
| Ollama 404 on `/api/generate` | Use `/v1` endpoints: `ollama_base_url: "http://127.0.0.1:11434/v1"` |
| GRG composite always 0.5 | Free models don't provide logprobs; use Ollama or paid model for real GRG scoring |

---

## Quick Test Prompts

```bash
# Simple function
python3 -m grg_agent.hermes_skill "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"

# Class with edge cases
python3 -m grg_agent.hermes_skill "Implement a Calculator class with add, sub, mul, div. Handle div by zero."

# Algorithm
python3 -m grg_agent.hermes_skill "def binary_search(arr, target): return index or -1"
```

---

## File Checklist for Deployment

- [ ] `grg` core package installed (`pip install -e ~/grg`)
- [ ] Skill at `~/.hermes/skills/grg_agent/grg_agent/`
- [ ] `~/.hermes/config.yaml` has `grg_agent.enabled: true`
- [ ] LLM provider running (Hermes proxy on 8465 or Ollama on 11434)
- [ ] Test command produces verified code output