#!/usr/bin/env python3
"""GRG spec generation from NL prompt - uses GRG Agent Hermes Skill."""

import sys
import asyncio
import json
import os

# Use the local grg_agent skill
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills', 'grg_agent'))

from grg_agent.hermes_skill import create_skill

async def main():
    if len(sys.argv) < 3:
        print("Usage: python grg_make_spec.py <provider> <prompt>")
        print("Providers: ollama | hermes | auto")
        print("For LM Studio, use 'ollama' with BASE_URL and MODEL env vars")
        sys.exit(2)
    
    provider = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    
    # Map provider names
    if provider == "lmstudio":
        # LM Studio uses OllamaClient internally with OpenAI-compatible API
        provider = "ollama"
    
    # Create skill with provider config
    skill = create_skill(config={'llm_provider': provider})
    
    # Use the grg:execute command which does NL -> Spec -> Plan
    result = await skill.on_command('grg:execute', {'task': prompt, 'provider': provider})
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())