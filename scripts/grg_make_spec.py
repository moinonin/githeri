#!/usr/bin/env python3
"""GRG spec generation from NL prompt - used by Make target."""

import sys
import asyncio

sys.path.insert(0, '/Users/nickrotich/.hermes/skills/grg_agent')

from grg_agent.hermes_skill import GRGAgentSkill

async def main():
    if len(sys.argv) < 3:
        print("Usage: python grg_make_spec.py <provider> <prompt>")
        sys.exit(2)
    
    provider = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    
    skill = GRGAgentSkill(config={'llm_provider': provider})
    result = await skill.on_command('grg:execute', {'task': prompt, 'provider': provider})
    
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())