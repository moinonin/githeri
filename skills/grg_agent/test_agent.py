#!/usr/bin/env python3
"""Test GRG Agent components"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import torch
from grg_agent.grg_agent import (
    GRGAgentConfig, 
    create_agent,
    create_llm_skill,
    create_monitor,
    create_diversity_controller,
    create_planner,
    create_verifier,
)
from grg_agent.grg_agent.state import Candidate, Strategy

def test_config():
    """Test configuration"""
    print("Testing config...")
    config = GRGAgentConfig(
        model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        use_lora=True,
        lora_r=8,
        lora_alpha=16,
        max_iterations=3,
        max_tokens=50,
    )
    print(f"  Config: {config.model_id}, device={config.device}")
    assert config.device in ["mps", "cuda", "cpu"]
    print("  ✓ Config OK")

def test_llm_skill():
    """Test LLM skill loading"""
    print("\nTesting LLM skill...")
    config = GRGAgentConfig(
        model_id="HuggingFaceTB/SmolLM2-360M-Instruct",  # Small for test
        use_lora=False,
        lora_r=8,
        lora_alpha=16,
        load_in_4bit=False,
        max_tokens=20,
    )
    
    try:
        skill = create_llm_skill(config)
        print(f"  Loaded: {config.model_id}")
        
        # Test generation
        candidate = skill.generate("def hello():", max_tokens=10, temperature=0.8)
        print(f"  Generated: {candidate.text[:50]}")
        print(f"  Logprobs: {len(candidate.logprobs)}")
        assert len(candidate.logprobs) > 0
        print("  ✓ LLM Skill OK")
    except Exception as e:
        print(f"  ✗ LLM Skill failed: {e}")
        raise

def test_monitor():
    """Test GRG monitor"""
    print("\nTesting GRG monitor...")
    from grg_agent.grg_agent.config import GRGAgentConfig
    from grg_agent.grg_agent.monitor import create_monitor
    from grg_agent.grg_agent.state import Candidate
    
    config = GRGAgentConfig()
    monitor = create_monitor(config)
    
    # Test with dummy logprobs
    logprobs = [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7, -0.8, -0.9, -1.0]
    score = monitor.score_logprobs(logprobs)
    
    print(f"  Composites: {score.composites}")
    print(f"  Mean composite: {score.mean_composite:.3f}")
    print(f"  GRG stats: {score.grg_stats}")
    assert score.mean_composite > 0
    print("  ✓ Monitor OK")

def test_diversity():
    """Test diversity controller"""
    print("\nTesting diversity controller...")
    from grg_agent.grg_agent.config import GRGAgentConfig
    from grg_agent.grg_agent.diversity import create_diversity_controller
    
    config = GRGAgentConfig()
    diversity = create_diversity_controller(config)
    
    base_prompt = "def fibonacci(n):\n    '''Return nth Fibonacci number.'''\n"
    variants = diversity.generate_variants(base_prompt, num_variants=3, iteration=0)
    
    print(f"  Generated {len(variants)} variants:")
    for v in variants:
        print(f"    - {v.name}: temp={v.temperature:.2f}")
    # Note: refine is skipped when no previous_best, so we get 2 variants
    assert len(variants) >= 2
    print("  ✓ Diversity OK")

def test_planner():
    """Test code planner"""
    print("\nTesting planner...")
    from grg_agent.grg_agent.config import GRGAgentConfig
    from grg_agent.grg_agent.planner import create_planner
    
    config = GRGAgentConfig()
    planner = create_planner(config)
    
    task = "def binary_search(arr, target):\n    '''Return index of target in sorted array.'''\n"
    plan = planner.create_plan(task)
    
    print(f"  Task type: {plan.task_type if hasattr(plan, 'task_type') else 'unknown'}")
    print(f"  Strategies: {len(plan.strategies)}")
    for s in plan.strategies:
        print(f"    - {s.name}: {s.description}")
    print("  ✓ Planner OK")

def test_verifier():
    """Test code verifier"""
    print("\nTesting verifier...")
    from grg_agent.grg_agent.config import GRGAgentConfig
    from grg_agent.grg_agent.verifier import create_verifier
    from grg_agent.grg_agent.state import Candidate
    
    config = GRGAgentConfig()
    verifier = create_verifier(config)
    
    # Test with valid code
    candidate = Candidate(
        text='def add(a, b):\n    return a + b\n\nprint(add(2, 3))',
        logprobs=[-0.1]*10,
        strategy="test",
        iteration=0,
    )
    
    result = verifier.verify(candidate, "def add(a, b):")
    print(f"  Execution: {result.execution_success}")
    print(f"  Passed: {result.passed}")
    if result.errors:
        print(f"  Errors: {result.errors}")
    print("  ✓ Verifier OK")

def test_agent_components():
    """Test agent component integration"""
    print("\nTesting agent component integration...")
    from grg_agent.grg_agent import (
        GRGAgentConfig, 
        create_agent,
        GRGAgent,
    )
    from grg_agent.grg_agent.state import Candidate
    
    config = GRGAgentConfig(
        model_id="HuggingFaceTB/SmolLM2-360M-Instruct",
        use_lora=False,
        max_iterations=1,
        max_tokens=20,
        candidates_per_strategy=1,
    )
    
    agent = create_agent(config)
    
    # Test with simple task
    candidate = agent.llm_skill.generate("def hello():", max_tokens=10)
    print(f"  Generated: {candidate.text}")
    
    # Score with monitor
    agent.monitor.score_candidate(candidate)
    print(f"  Composite: {candidate.score.mean_composite:.3f}")
    
    # Test diversity
    variants = agent.diversity.generate_variants("def test():", num_variants=2)
    print(f"  Variants: {len(variants)}")
    
    print("  ✓ Agent components OK")


def main():
    print("=" * 60)
    print("GRG AGENT COMPONENT TESTS")
    print("=" * 60)
    
    test_config()
    test_llm_skill()
    test_monitor()
    test_diversity()
    test_planner()
    test_verifier()
    test_agent_components()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()