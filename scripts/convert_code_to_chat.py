#!/usr/bin/env python3
"""Convert GRG code training data to chat format for fine-tuning."""
import json
from pathlib import Path

INPUT_FILE = Path('data/training_data_code.jsonl')
OUTPUT_FILE = Path('data/training_data_code_chat.jsonl')

SYSTEM_PROMPT = 'You are a Python expert. Generate clean, correct, production-ready Python code. Include all necessary imports, type hints, docstrings, and handle edge cases.'

def main():
    print(f"Converting {INPUT_FILE} -> {OUTPUT_FILE}")
    
    count = 0
    with INPUT_FILE.open() as fin, OUTPUT_FILE.open('w') as fout:
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
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                    {'role': 'assistant', 'content': code}
                ]
            }
            fout.write(json.dumps(chat, ensure_ascii=False) + '\n')
            count += 1
    
    print(f"Converted {count} passing examples to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()