#!/usr/bin/env python3
"""GRG Agent - Main orchestrator for GRG-guided code generation"""

import random
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import torch

from .config import GRGAgentConfig
from .state import (
    Candidate, Strategy, TrajectoryState, Score,
    TrajectoryState, Candidate, Strategy, Score,
    GRGHistoryEntry
)
from .planner import Plan
from .llm_skill import LLMSkill, create_llm_skill
from .monitor import GRGMonitor, create_monitor
from .diversity import DiversityController, create_diversity_controller
from .planner import CodePlanner, create_planner
from .verifier import CodeVerifier, create_verifier, VerificationResult
from .config import GRGAgentConfig


class GRGAgent:
    """
    GRG Agent - Main orchestrator for GRG-guided code generation.
    
    Uses GRG as strategic brain:
    - Planner decomposes task
    - Diversity controller generates variants
    - LLM Skill generates candidates
    - Monitor scores with GRG
    - Verifier validates
    - Iterates until convergence
    """
    
    def __init__(self, config: GRGAgentConfig):
        self.config = config
        
        # Core components
        self.llm_skill = create_llm_skill(config)
        self.monitor = create_monitor(config)
        self.diversity = DiversityController(config, self.llm_skill.tokenizer)
        self.planner = create_planner(config)
        self.verifier = create_verifier(config)
        
        # Trajectory state
        self.trajectory = TrajectoryState()
        
        # Stats
        self.total_generations = 0
        self.total_verifications = 0
        self.iteration_times = []
    
    def solve(self, task: str, max_iterations: int = None) -> Candidate:
        """
        Main entry point: solve a code generation task.
        
        Returns the best verified candidate.
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        print(f"\n{'='*60}")
        print(f"GRG AGENT: Solving task")
        print(f"{'='*60}")
        print(f"Task: {task[:100]}...")
        print(f"Max iterations: {max_iterations}")
        
        # 1. PLAN: Create execution plan
        print("\n[1/5] PLANNING...")
        plan = self.planner.create_plan(task)
        print(f"  Task type: {plan.task_type if hasattr(plan, 'task_type') else 'unknown'}")
        print(f"  Strategies: {len(plan.strategies)}")
        print(f"  Estimated iterations: {plan.estimated_iterations}")
        
        # Update trajectory
        self.trajectory = TrajectoryState()
        
        best_candidate = None
        
        # 2. MAIN LOOP
        for iteration in range(max_iterations):
            self.trajectory.iteration = iteration
            iter_start = time.time()
            
            print(f"\n{'='*50}")
            print(f"ITERATION {iteration + 1}/{max_iterations}")
            print(f"{'='*50}")
            
            # Generate candidates for each strategy
            all_candidates = []
            
            for strategy in self.trajectory.strategies_used[:]:  # Copy for safety
                pass  # Will be populated by strategies
            
            # Generate candidates for each strategy in plan
            for strategy in plan.strategies:
                print(f"\n  Strategy: {strategy.name} ({strategy.description})")
                
                # Generate prompt variants
                variants = self.diversity.generate_variants(
                    base_prompt=strategy.prompt,
                    num_variants=self.config.candidates_per_strategy,
                    iteration=iteration,
                    previous_best=self.trajectory.best_candidate.text if self.trajectory.best_candidate else None
                )
                
                print(f"    Generated {len(variants)} variants")
                
                # Generate candidates for each variant
                for variant in variants:
                    print(f"    Generating: {variant.name} (temp={variant.temperature:.2f})")
                    
                    candidate = self.llm_skill.generate(
                        prompt=variant.prompt,
                        temperature=variant.temperature,
                        top_p=variant.top_p,
                        max_tokens=self.config.max_tokens,
                        return_logprobs=True,
                    )
                    candidate.strategy = strategy.name
                    candidate.iteration = iteration
                    candidate.metadata.update({
                        "variant": variant.name,
                        "temperature": variant.temperature,
                        "top_p": variant.top_p,
                    })
                    
                    # Score with GRG
                    self.monitor.score_candidate(candidate)
                    
                    # Add to diversity pool
                    self.diversity.add_candidate(candidate, self.llm_skill)
                    
                    all_candidates.append(candidate)
                    self.total_generations += 1
                    
                    # Check candidate pool size
                    if len(self.diversity.candidate_pool) > self.config.diversity_max_candidates:
                        # Already handled by add_candidate
                        pass
            
            # Score all candidates with GRG
            print(f"\n  Scoring {len(all_candidates)} candidates with GRG...")
            for cand in all_candidates:
                if cand.score is None:
                    self.monitor.score_candidate(cand)
            
            # Sort by GRG composite
            all_candidates.sort(key=lambda c: c.score.mean_composite if c.score else 0.0, reverse=True)
            
            # Verify top candidates
            print(f"\n  Verifying top candidates...")
            verified_candidates = []
            for i, cand in enumerate(all_candidates[:min(5, len(all_candidates))]):
                print(f"  Verifying candidate {i+1} (composite={cand.score.mean_composite:.3f})...")
                result = self.verifier.verify(cand, plan.task)
                self.total_verifications += 1
                
                if result.passed:
                    cand.verified = True
                    verified_candidates.append(cand)
                    print(f"    ✓ VERIFIED (time={result.execution_time:.2f}s)")
                else:
                    print(f"    ✗ FAILED: {result.errors[:2]}")
            
            # Update trajectory
            self.trajectory.candidates.extend(all_candidates)
            self.trajectory.strategies_used.extend([strategy.name for strategy in plan.strategies for _ in range(self.config.candidates_per_strategy)])
            
            # Update best candidate
            if verified_candidates:
                best_verified = max(verified_candidates, key=lambda c: c.score.mean_composite if c.score else 0.0)
                if self.trajectory.best_candidate is None or \
                   best_verified.score.mean_composite > self.trajectory.best_candidate.score.mean_composite:
                    self.trajectory.best_candidate = best_verified
                    print(f"\n  ✓ NEW BEST: {best_verified.score.mean_composite:.3f} composite (strategy: {best_verified.strategy})")
            
            # Update diversity history
            diversity_score = self.diversity.get_pool_diversity(self.llm_skill)
            self.trajectory.diversity_history.append(diversity_score)
            
            # Update monitor history
            for cand in all_candidates:
                if cand.score:
                    self.monitor.history.append(GRGHistoryEntry(
                        iteration=iteration,
                        alpha=cand.score.grg_stats.get("final_alpha", 0),
                        v_alpha=cand.score.grg_stats.get("final_v_alpha", 0),
                        m_alpha=cand.score.grg_stats.get("final_m_alpha", 0),
                        horizon=cand.score.grg_stats.get("final_horizon", 999),
                        is_collapsing=cand.score.grg_stats.get("is_collapsing", False),
                        is_stable=cand.score.grg_stats.get("is_stable", False),
                        composite=cand.score.mean_composite,
                    ))
            
            # Record iteration time
            iter_time = time.time() - iter_start
            self.iteration_times.append(iter_time)
            print(f"\n  Iteration time: {iter_time:.1f}s")
            
            # Check convergence
            if self.trajectory.best_candidate and self.trajectory.best_candidate.verified:
                # Check if we've converged (stable for 2 iterations)
                if iteration >= 1:
                    # Check if best candidate is stable
                    print(f"\n  Convergence check...")
                    # For now, just return on first verified
                    if self.trajectory.best_candidate.verified:
                        print(f"  ✓ Converged on verified solution!")
                        return self.trajectory.best_candidate
        
        # Return best candidate found
        if self.trajectory.best_candidate:
            return self.trajectory.best_candidate
        
        # Fallback: return highest scored
        if self.trajectory.candidates:
            best = max(self.trajectory.candidates, key=lambda c: c.score.mean_composite if c.score else 0.0)
            return best
        
        # Ultimate fallback
        return Candidate(text="", logprobs=[], strategy="none", iteration=0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "total_generations": self.total_generations,
            "total_verifications": self.total_verifications,
            "total_iterations": len(self.iteration_times),
            "total_time": sum(self.iteration_times),
            "avg_iteration_time": sum(self.iteration_times) / len(self.iteration_times) if self.iteration_times else 0,
            "trajectory": {
                "total_candidates": len(self.trajectory.candidates),
                "verified": len(self.trajectory.get_verified()),
                "best_composite": self.trajectory.best_candidate.score.mean_composite if self.trajectory.best_candidate and self.trajectory.best_candidate.score else 0,
                "diversity": self.trajectory.get_diversity_score(),
            },
            "monitor": self.monitor.get_trajectory_stats(),
            "diversity": self.diversity.get_pool_diversity(self.llm_skill),
        }
    
    def print_summary(self):
        """Print final summary"""
        stats = self.get_stats()
        print(f"\n{'='*60}")
        print("GRG AGENT SUMMARY")
        print(f"{'='*60}")
        print(f"Total generations: {stats['total_generations']}")
        print(f"Total verifications: {stats['total_verifications']}")
        print(f"Iterations: {stats['total_iterations']}")
        print(f"Total time: {stats['total_time']:.1f}s")
        print(f"Avg iteration time: {stats['avg_iteration_time']:.1f}s")
        print(f"\nTrajectory:")
        print(f"  Total candidates: {stats['trajectory']['total_candidates']}")
        print(f"  Verified: {stats['trajectory']['verified']}")
        print(f"  Best composite: {stats['trajectory']['best_composite']:.3f}")
        print(f"  Diversity: {stats['trajectory']['diversity']:.3f}")
        print(f"\nMonitor:")
        for k, v in stats['monitor'].items():
            print(f"  {k}: {v}")


def create_agent(config: GRGAgentConfig) -> GRGAgent:
    """Factory function to create GRG agent"""
    return GRGAgent(config)