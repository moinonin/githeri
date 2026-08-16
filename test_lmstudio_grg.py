#!/usr/bin/env python3
"""Test GRG Agent with LM Studio (qwen2.5-coder-14b-instruct-uncensored)"""

import asyncio
import sys
from pathlib import Path

# Add the grg_agent to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "skills" / "grg_agent"))

import grg_agent
from grg_agent.llm_client import OllamaClient, create_llm_client
from grg_agent.agent_hermes import GRGAgentHermes
from grg_agent.grg_agent import GRGAgentConfig


async def test_lmstudio_connection():
    """Test connection to LM Studio with qwen2.5-coder-14b-instruct-uncensored"""
    print("=" * 60)
    print("Testing LM Studio connection...")
    print("=" * 60)
    
    # LM Studio OpenAI-compatible endpoint typically runs on port 1234
    client = OllamaClient(
        base_url="http://127.0.0.1:1234/v1",
        default_model="qwen2.5-coder-14b-instruct-uncensored",
        api_key="lm-studio"
    )
    
    try:
        result = await client.generate(
            prompt="Write a Python function to compute fibonacci sequence",
            temperature=0.7,
            max_tokens=200,
            logprobs=True
        )
        print(f"✓ Connected to LM Studio")
        print(f"  Model: {result.model}")
        print(f"  Finish reason: {result.finish_reason}")
        print(f"  Tokens: {result.usage}")
        print(f"  Logprobs count: {len(result.logprobs) if result.logprobs else 0}")
        print(f"  Generated code:\n{result.text[:500]}")
        return True
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False


async def test_grg_agent_with_lmstudio():
    """Test GRG Agent with LM Studio backend"""
    print("\n" + "=" * 60)
    print("Testing GRG Agent with LM Studio backend...")
    print("=" * 60)
    
    config = GRGAgentConfig(
        max_iterations=2,
        candidates_per_strategy=2,
        max_tokens=256,
        temperature=0.8,
        top_p=0.9,
    )
    
    # Create agent
    agent = GRGAgentHermes(config)
    
    # Replace the LLM client with our LM Studio client
    agent.llm_client = OllamaClient(
        base_url="http://127.0.0.1:1234/v1",
        default_model="qwen2.5-coder-14b-instruct-uncensored",
        api_key="lm-studio"
    )
    
    # Test prompt
    task = """def find_max_subarray(arr):
    '''Find the maximum sum subarray using Kadane's algorithm.
    Returns tuple of (max_sum, start_idx, end_idx).'''"""
    
    print(f"Task: {task}")
    print("\nRunning GRG Agent...")
    
    try:
        candidate = await agent.solve(task, max_iterations=2)
        
        print(f"\n✓ GRG Agent completed!")
        print(f"  Verified: {candidate.verified}")
        print(f"  Strategy: {candidate.strategy}")
        print(f"  Iteration: {candidate.iteration}")
        if candidate.score:
            print(f"  Composite Score: {candidate.score.mean_composite:.3f}")
            print(f"  Score attrs: {vars(candidate.score)}")
        print(f"  Code:\n{candidate.text}")
        
        stats = agent.get_stats()
        print(f"\n  Stats: {stats}")
        
        return candidate
        
    except Exception as e:
        print(f"✗ GRG Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    # First test connection
    connected = await test_lmstudio_connection()
    
    if connected:
        # Then test full GRG agent
        await test_grg_agent_with_lmstudio()
    else:
        print("\nSkipping GRG Agent test due to connection failure")
        print("Make sure LM Studio is running with qwen2.5-coder-14b-instruct-uncensored loaded")


if __name__ == "__main__":
    asyncio.run(main())