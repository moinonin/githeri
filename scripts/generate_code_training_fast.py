#!/usr/bin/env python3
"""
Generate training data using GRG Agent with Ollama specforge model.
Optimized for speed: single strategy, fewer candidates.
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

skill = create_skill(config={
    'llm_provider': PROVIDER,
    'ollama_base_url': OLLAMA_URL,
    'ollama_default_model': MODEL,
    'max_iterations': MAX_ITERATIONS,
    'temperature': TEMPERATURE,
    'top_p': TOP_P,
    'max_tokens': MAX_TOKENS,
    'candidates_per_strategy': 1,
    'max_strategies': 1,
})


def verify_code(code: str) -> dict:
    """Run syntax + execution verification (fast)."""
    result = {"syntax_ok": False, "exec_ok": False, "error": None}
    
    # 1. Syntax check
    try:
        compile(code, '<string>', 'exec')
        result["syntax_ok"] = True
    except SyntaxError as e:
        result["error"] = f"Syntax: {e}"
        return result
    
    # 2. Execution test (basic import)
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


async def generate_one(prompt: str) -> dict:
    """Generate code for a single prompt."""
    task = f"{prompt}\n\nRequirements:\n- Python 3.10+\n- Type hints\n- Docstrings\n- Edge case handling\n- Production ready"
    
    grg_result = await skill.on_command('grg:solve', {
        'task': task,
        'model': MODEL,
        'iterations': MAX_ITERATIONS
    })
    
    code = grg_result.get('code', '')
    verified = grg_result.get('verified', False)
    composite = grg_result.get('composite', 0.0)
    
    verify_result = verify_code(code)
    
    return {
        "prompt": prompt,
        "code": code,
        "grg_verified": verified,
        "grg_composite": composite,
        "grg_success": grg_result.get('success', False),
        "verify_syntax": verify_result["syntax_ok"],
        "verify_exec": verify_result["exec_ok"],
        "verify_error": verify_result["error"],
        "overall_pass": verified and verify_result["syntax_ok"] and verify_result["exec_ok"],
        "timestamp": datetime.utcnow().isoformat(),
        "model": MODEL,
        "provider": PROVIDER,
    }


async def main():
    OUTPUT_FILE = Path("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/data/training_data_code.jsonl")
    CHAT_FILE = Path("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/data/training_data_code_chat.jsonl")
    
    print(f"Generating for {len(SEED_PROMPTS)} prompts...")
    print(f"Model: {MODEL} via {PROVIDER}")
    
    # Load existing
    existing = {}
    if OUTPUT_FILE.exists():
        with OUTPUT_FILE.open() as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing[d['prompt']] = d
                except:
                    pass
    
    passed = 0
    failed = 0
    
    with OUTPUT_FILE.open('a') as fout:
        for i, prompt in enumerate(SEED_PROMPTS, 1):
            if prompt in existing:
                print(f"[{i}/{len(SEED_PROMPTS)}] Skipping (exists)")
                if existing[prompt].get('overall_pass'):
                    passed += 1
                else:
                    failed += 1
                continue
            
            print(f"\n[{i}/{len(SEED_PROMPTS)}] {prompt[:80]}...")
            
            try:
                result = await generate_one(prompt)
                
                fout.write(json.dumps(result) + '\n')
                fout.flush()
                
                if result['overall_pass']:
                    passed += 1
                    print(f"  ✅ PASS (composite={result['grg_composite']:.3f})")
                else:
                    failed += 1
                    print(f"  ❌ FAIL: {result.get('verify_error', 'unknown')}")
            except Exception as e:
                print(f"  ❌ ERROR: {e}")
                failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"Data saved to: {OUTPUT_FILE}")
    
    # Convert to chat format
    await convert_to_chat(OUTPUT_FILE, CHAT_FILE)


async def convert_to_chat(input_file: Path, output_file: Path):
    """Convert to chat format for fine-tuning."""
    print(f"\nConverting to chat format: {output_file}")
    
    SYSTEM_PROMPT = "You are a Python expert. Generate clean, correct, production-ready Python code. Include all necessary imports, type hints, docstrings, and handle edge cases."
    
    count = 0
    with input_file.open() as fin, output_file.open('w') as fout:
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
                continue
            
            chat = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": code}
                ]
            }
            fout.write(json.dumps(chat, ensure_ascii=False) + '\n')
            count += 1
    
    print(f"Converted {count} passing examples to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())