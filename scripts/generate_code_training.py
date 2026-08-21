#!/usr/bin/env python3
"""
Generate training data using GRG Agent with Ollama specforge model.
Cycles through all SEED_PROMPTS, generates verified code, saves to data/training_data_code.jsonl
Then converts to chat format for fine-tuning.
"""
import asyncio
import json
import sys
import subprocess
import tempfile
import os
from pathlib import Path
from datetime import datetime

# Add skill path
sys.path.insert(0, '/Users/nickrotich/.hermes/skills/grg_agent')
from grg_agent.hermes_skill import create_skill

# Import prompts
sys.path.insert(0, '/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/scripts')
from prompt_generator import SEED_PROMPTS

# Configuration
MODEL = "specforge-128k-tools2:latest"
PROVIDER = "ollama"
OLLAMA_URL = "http://127.0.0.1:11434/v1"
MAX_ITERATIONS = 2
TEMPERATURE = 0.3
TOP_P = 0.9
MAX_TOKENS = 1024

# Output files
OUTPUT_FILE = Path("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/data/training_data_code.jsonl")
CHAT_FILE = Path("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/data/training_data_code_chat.jsonl")

# System prompt for GRG agent
SYSTEM_PROMPT = """You are a Python expert. Generate clean, correct, production-ready Python code.
Follow these rules:
- Include all necessary imports
- Add type hints
- Include docstrings
- Handle edge cases
- No markdown, no commentary, ONLY the code
"""

skill = create_skill(config={
    'llm_provider': PROVIDER,
    'ollama_base_url': OLLAMA_URL,
    'ollama_default_model': MODEL,
    'max_iterations': MAX_ITERATIONS,
    'temperature': TEMPERATURE,
    'top_p': TOP_P,
    'max_tokens': MAX_TOKENS,
})


def verify_code(code: str) -> dict:
    """Run syntax + ruff + execution verification."""
    result = {"syntax_ok": False, "ruff_ok": False, "exec_ok": False, "error": None}
    
    # 1. Syntax check
    try:
        compile(code, '<string>', 'exec')
        result["syntax_ok"] = True
    except SyntaxError as e:
        result["error"] = f"Syntax: {e}"
        return result
    
    # 2. Ruff check (if available)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name
    
    try:
        proc = subprocess.run(
            ['ruff', 'check', '--quiet', temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        result["ruff_ok"] = proc.returncode == 0
        if proc.returncode != 0:
            result["error"] = f"Ruff: {proc.stdout}"
    except FileNotFoundError:
        result["ruff_ok"] = True  # ruff not installed, skip
    except subprocess.TimeoutExpired:
        result["error"] = "Ruff timeout"
    finally:
        os.unlink(temp_path)
    
    # 3. Execution test (basic import check)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code + "\n\nprint('IMPORT_OK')\n")
        temp_path = f.name
    
    try:
        proc = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        result["exec_ok"] = proc.returncode == 0 and "IMPORT_OK" in proc.stdout
        if not result["exec_ok"]:
            result["error"] = proc.stderr or proc.stdout
    except subprocess.TimeoutExpired:
        result["error"] = "Execution timeout"
    finally:
        os.unlink(temp_path)
    
    return result


def generate_for_prompt(prompt: str, index: int, total: int) -> dict:
    """Generate code for a single prompt using GRG agent."""
    print(f"\n[{index}/{total}] {prompt[:80]}...")
    
    task = f"{prompt}\n\nRequirements:\n- Python 3.10+\n- Type hints\n- Docstrings\n- Edge case handling\n- Production ready"
    
    try:
        grg_result = asyncio.run(skill.on_command('grg:solve', {
            'task': task,
            'model': MODEL,
            'iterations': MAX_ITERATIONS
        }))
        
        code = grg_result.get('code', '')
        verified = grg_result.get('verified', False)
        composite = grg_result.get('composite', 0.0)
        
        # Additional validation
        verify_result = verify_code(code)
        
        return {
            "prompt": prompt,
            "code": code,
            "grg_verified": verified,
            "grg_composite": composite,
            "grg_success": grg_result.get('success', False),
            "verify_syntax": verify_result["syntax_ok"],
            "verify_ruff": verify_result["ruff_ok"],
            "verify_exec": verify_result["exec_ok"],
            "verify_error": verify_result["error"],
            "overall_pass": verified and verify_result["syntax_ok"] and verify_result["ruff_ok"] and verify_result["exec_ok"],
            "timestamp": datetime.utcnow().isoformat(),
            "model": MODEL,
            "provider": PROVIDER,
        }
    except Exception as e:
        return {
            "prompt": prompt,
            "code": "",
            "grg_verified": False,
            "grg_composite": 0.0,
            "grg_success": False,
            "verify_syntax": False,
            "verify_ruff": False,
            "verify_exec": False,
            "verify_error": str(e),
            "overall_pass": False,
            "timestamp": datetime.utcnow().isoformat(),
            "model": MODEL,
            "provider": PROVIDER,
        }


def main():
    print(f"Generating training data for {len(SEED_PROMPTS)} prompts")
    print(f"Model: {MODEL} via {PROVIDER}")
    print(f"Output: {OUTPUT_FILE}")
    
    # Load existing data if resuming
    existing = {}
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open() as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing[d['prompt']] = d
                except:
                    pass
        print(f"Loaded {len(existing)} existing entries")
    
    # Generate
    passed = 0
    failed = 0
    
    with OUTPUT_FILE.open('a') as fout:
        for i, prompt in enumerate(SEED_PROMPTS, 1):
            if prompt in existing:
                print(f"[{i}/{len(SEED_PROMPTS)}] Skipping (already generated)")
                if existing[prompt].get('overall_pass'):
                    passed += 1
                else:
                    failed += 1
                continue
            
            result = generate_for_prompt(prompt, i, len(SEED_PROMPTS))
            
            fout.write(json.dumps(result) + '\n')
            fout.flush()
            
            if result['overall_pass']:
                passed += 1
                print(f"  ✅ PASS (composite={result['grg_composite']:.3f})")
            else:
                failed += 1
                print(f"  ❌ FAIL: {result.get('verify_error', 'unknown')}")
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(SEED_PROMPTS)}")
    print(f"Data saved to: {OUTPUT_FILE}")
    
    # Convert to chat format
    convert_to_chat()


def convert_to_chat():
    """Convert training_data_code.jsonl to chat format for fine-tuning."""
    print(f"\nConverting to chat format: {CHAT_FILE}")
    
    count = 0
    with OUTPUT_FILE.open() as fin, CHAT_FILE.open('w') as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            prompt = entry.get('prompt', '').strip()
            code = entry.get('code', '').strip()
            
            if not prompt or not code:
                continue
            
            if not entry.get('overall_pass', False):
                continue  # Only include passing examples
            
            chat = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT.strip()},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": code}
                ]
            }
            fout.write(json.dumps(chat, ensure_ascii=False) + '\n')
            count += 1
    
    print(f"Converted {count} passing examples to {CHAT_FILE}")


if __name__ == "__main__":
    main()