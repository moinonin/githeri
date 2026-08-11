#!/usr/bin/env python3
"""Full GRG Agent integration test"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import torch
from examples.grg_agent import (
    GRGAgentConfig, 
    create_agent,
    GRGAgent,
)

def test_full_agent():
    """Test full GRG agent on a simple task"""
    print("=" * 60)
    print("FULL GRG AGENT TEST")
    print("=" * 60)
    
    config = GRGAgentConfig(
        model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        use_lora=False,
        max_iterations=3,
        max_tokens=50,
        candidates_per_strategy=2,
        temperature=0.8,
        top_p=0.9,
    )
    
    print("Creating agent...")
    agent = GRGAgent(config)
    
    task = "def fibonacci(n):\n    '''Return nth Fibonacci number.'''\n"
    
    print(f"\nTask: {task.strip()}")
    print("Solving...")
    
    best = agent.solve(task, max_iterations=2)
    
    print(f"\nBest candidate:")
    print(f"  Strategy: {best.strategy}")
    print(f"  Iteration: {best.iteration}")
    print(f"  Composite: {best.score.mean_composite if best.score else 'N/A':.3f}")
    print(f"  Verified: {best.verified}")
    print(f"  Code:\n{best.text}")
    
    agent.print_summary()
    
    return best

if __name__ == "__main__":
    best = test_full_agent()
    print("\n✓ Full agent test completed!")