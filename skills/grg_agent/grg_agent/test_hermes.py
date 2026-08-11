#!/usr/bin/env python3
"""Test GRG Agent Hermes components (without external API calls)"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from grg_agent.grg_agent import (
    GRGAgentConfig,
    GRGAgentHermes,
    create_agent_hermes,
    HermesLLMClient,
    GenerationResult,
    create_hermes_client,
    GRGMonitor,
    DiversityController,
    CodePlanner,
    CodeVerifier,
    Candidate,
)


class MockHermesClient:
    """Mock Hermes client for testing without API keys."""

    def __init__(self, *args, **kwargs):
        self.call_count = 0

    async def generate(self, prompt: str, **kwargs):
        self.call_count += 1

        # Return simple valid code based on prompt
        if "fibonacci" in prompt.lower():
            code = """def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a"""
        elif "factorial" in prompt.lower():
            code = """def factorial(n):
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result"""
        else:
            code = """def solution():
    return 'implemented'"""

        return GenerationResult(
            text=code,
            logprobs=[-0.1] * 20,
            finish_reason="stop",
            usage={"total_tokens": 100},
            model="mock-model",
        )

    async def generate_batch(self, prompts, num_candidates=1, **kwargs):
        results = []
        for _ in prompts:
            candidates = []
            for _ in range(num_candidates):
                candidates.append(await self.generate(prompts[0], **kwargs))
            results.append(candidates)
        return results

    async def get_embeddings(self, texts, model=None):
        from grg_agent.grg_agent.llm_client import EmbeddingResult
        import numpy as np
        return EmbeddingResult(
            embeddings=[np.random.randn(384).tolist() for _ in texts],
            model="mock-embedding",
        )


def test_hermes_client():
    """Test Hermes client interface."""
    print("Testing Hermes LLM Client interface...")

    # Test mock client
    import asyncio

    async def run_test():
        client = MockHermesClient()
        result = await client.generate("def fibonacci(n):")
        print(f"  Generated: {result.text[:50]}...")
        print(f"  Logprobs: {len(result.logprobs)}")
        print(f"  Model: {result.model}")
        assert result.text
        assert len(result.logprobs) > 0
        print("  ✓ Hermes client interface OK")

    asyncio.run(run_test())


def test_grg_components():
    """Test GRG components work with Hermes agent."""
    print("\nTesting GRG components...")

    config = GRGAgentConfig(
        max_iterations=2,
        candidates_per_strategy=2,  # Need at least 2 for variants
        max_tokens=50,
    )

    # Test monitor
    monitor = GRGMonitor(config)
    candidate = Candidate(
        text="def fibonacci(n): return n",
        logprobs=[-0.1] * 10,
        strategy="test",
        iteration=0,
    )
    monitor.score_candidate(candidate)
    print(f"  Monitor: composite={candidate.score.mean_composite:.3f}")
    assert candidate.score.mean_composite > 0
    print("  ✓ GRG Monitor OK")

    # Test diversity
    diversity = DiversityController(config)
    variants = diversity.generate_variants("def test():", num_variants=3)
    print(f"  Diversity: {len(variants)} variants")
    assert len(variants) >= 2
    print("  ✓ Diversity Controller OK")

    # Test planner
    planner = CodePlanner(config)
    plan = planner.create_plan("def fibonacci(n):")
    print(f"  Planner: {len(plan.strategies)} strategies")
    assert len(plan.strategies) > 0
    print("  ✓ Code Planner OK")

    # Test verifier
    verifier = CodeVerifier(config)
    candidate = Candidate(
        text='def add(a, b):\n    return a + b\n\nprint(add(1, 2))',
        logprobs=[-0.1]*10,
        strategy="test",
        iteration=0,
    )
    result = verifier.verify(candidate, "def add(a, b):")
    print(f"  Verifier: passed={result.passed}, execution={result.execution_success}")
    assert result.execution_success
    print("  ✓ Code Verifier OK")


def test_agent_integration():
    """Test full agent integration with mock client."""
    print("\nTesting agent integration...")

    config = GRGAgentConfig(
        max_iterations=1,
        candidates_per_strategy=1,
        max_tokens=30,
        temperature=0.8,
    )

    # Create agent with mock client
    from grg_agent.grg_agent.agent_hermes import GRGAgentHermes

    # Monkey-patch the client creation
    import grg_agent.grg_agent.llm_client as llm_client_module
    original_create = llm_client_module.create_hermes_client

    def mock_create_hermes_client(proxy_url=None):
        return MockHermesClient()

    llm_client_module.create_hermes_client = mock_create_hermes_client

    try:
        import asyncio

        async def run_agent():
            agent = GRGAgentHermes(config)
            # Replace the client with our mock
            agent.llm_client = MockHermesClient()

            task = "def fibonacci(n):\n    '''Return nth Fibonacci.'''\n"
            candidate = await agent.solve(task, max_iterations=1)

            print(f"  Agent result: verified={candidate.verified}")
            print(f"  Strategy: {candidate.strategy}")
            print(f"  Composite: {candidate.score.mean_composite if candidate.score else 0:.3f}")
            print(f"  Code: {candidate.text[:60]}...")

            stats = agent.get_stats()
            print(f"  Stats: generations={stats['total_generations']}, verifications={stats['total_verifications']}")

            return candidate

        candidate = asyncio.run(run_agent())
        assert candidate is not None
        print("  ✓ Agent integration OK")

    finally:
        llm_client_module.create_hermes_client = original_create


def test_hermes_skill():
    """Test Hermes skill entry point."""
    print("\nTesting Hermes skill...")

    from grg_agent import GRGAgentSkill, create_skill, SKILL_MANIFEST

    skill = create_skill(config={
        'max_iterations': 2,
        'candidates_per_strategy': 1,
    })

    print(f"  Skill manifest: {SKILL_MANIFEST['name']} v{SKILL_MANIFEST['version']}")
    print(f"  Commands: {[c['name'] for c in SKILL_MANIFEST['commands']]}")
    print(f"  Config schema keys: {list(SKILL_MANIFEST['config_schema'].keys())}")
    assert 'grg:solve' in [c['name'] for c in SKILL_MANIFEST['commands']]
    print("  ✓ Hermes skill OK")


def main():
    print("=" * 60)
    print("GRG AGENT HERMES COMPONENT TESTS")
    print("=" * 60)

    test_hermes_client()
    test_grg_components()
    test_agent_integration()
    test_hermes_skill()

    print("\n" + "=" * 60)
    print("ALL HERMES COMPONENT TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()