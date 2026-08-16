#!/usr/bin/env python3
"""Diversity Controller - Explicit diversity management for candidate generation"""

import random
import math
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

import torch
from transformers import AutoTokenizer

from .config import GRGAgentConfig
from .state import Strategy, Candidate


@dataclass
class PromptVariant:
    """A prompt variant with metadata"""
    prompt: str
    temperature: float
    top_p: float
    name: str
    description: str


class DiversityController:
    """
    Explicit diversity management for candidate generation.
    Generates diverse prompt variants and controls candidate pool diversity.
    """
    
    def __init__(self, config: 'GRGAgentConfig', tokenizer=None):
        self.config = config
        self.tokenizer = tokenizer
        self.candidate_pool: List[Candidate] = []
        self.generated_embeddings: List[torch.Tensor] = []
        
        # Temperature range
        self.temp_min, self.temp_max = config.diversity_temperature_range
        self.min_cosine = config.diversity_min_cosine
        self.max_candidates = config.diversity_max_candidates
        
        # Prompt templates for variation
        self.prompt_templates = {
            "base": "{prompt}\n\nReturn ONLY the Python code, no explanations, no markdown, no extra text.",
            "cot": "{prompt}\n\nLet's think step by step, then return ONLY the Python code.",
            "few_shot": "{prompt}\n\nHere are some examples:\n{few_shot_examples}\n\nNow solve - return ONLY the Python code.",
            "decompose": "{prompt}\n\nFirst, break down the problem into steps:\n1.\n2.\n3.\n\nThen implement - return ONLY the Python code.",
            "refine": "{prompt}\n\nPrevious attempt had issues. Fix the following:\n{previous_attempt}\n\nCorrected version - return ONLY the Python code:",
            "explain": "{prompt}\n\nExplain your approach briefly, then return ONLY the Python code.",
            "test_first": "{prompt}\n\nFirst write tests, then implementation:\n```python\n# Tests\n```\n\n```python\n# Implementation\n```\n\nReturn ONLY the Python code.",
        }
        
        # Strategy descriptions
        self.strategy_types = {
            "standard": "Standard generation with base prompt",
            "cot": "Chain-of-thought reasoning",
            "decompose": "Problem decomposition into steps",
            "refine": "Iterative refinement from previous attempt",
            "explain": "Explain approach before coding",
            "test_first": "Write tests first, then implementation",
        }
    
    def set_tokenizer(self, tokenizer):
        self.tokenizer = tokenizer
    
    def generate_variants(
        self, 
        base_prompt: str, 
        num_variants: int = None,
        iteration: int = 0,
        previous_best: str = None
    ) -> List[PromptVariant]:
        """Generate diverse prompt variants"""
        if num_variants is None:
            num_variants = min(4, self.config.max_strategies)
        
        variants = []
        
        # Always include base prompt
        variants.append(PromptVariant(
            prompt=base_prompt,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            name="base",
            description="Standard generation"
        ))
        
        # Select remaining variants
        available_strategies = ["cot", "decompose", "explain", "test_first", "refine"]
        
        # If we have a previous best, add refinement
        if previous_best and iteration > 0:
            available_strategies.remove("refine")
            available_strategies.insert(0, "refine")
        
        # Randomly select strategies
        selected = random.sample(available_strategies, min(num_variants - 1, len(available_strategies)))
        
        for strategy in selected:
            template = self.prompt_templates[strategy]
            
            if strategy == "refine" and previous_best:
                prompt = template.format(
                    prompt=base_prompt,
                    previous_attempt=previous_best[:500]
                )
            elif strategy == "refine" and not previous_best:
                # Skip refine if no previous attempt
                continue
            else:
                prompt = template.format(prompt=base_prompt)
            
            # Vary temperature
            if iteration == 0:
                temp = self.config.temperature
            else:
                # Increase temperature for exploration in later iterations
                progress = min(iteration / 5.0, 1.0)
                temp = self.temp_min + (self.temp_max - self.temp_min) * progress
            
            # Slight top-p variation
            top_p = self.config.top_p + random.uniform(-0.05, 0.05)
            top_p = max(0.85, min(0.95, top_p))
            
            variants.append(PromptVariant(
                prompt=prompt,
                temperature=temp,
                top_p=top_p,
                name=strategy,
                description=self.strategy_types.get(strategy, strategy)
            ))
        
        return variants[:num_variants]
    
    def generate_temperature_schedule(
        self, 
        num_steps: int, 
        strategy: str = "adaptive"
    ) -> List[float]:
        """Generate temperature schedule for iterations"""
        if strategy == "adaptive":
            # Start low, increase for exploration, then decrease
            temps = []
            for i in range(num_steps):
                progress = i / max(1, num_steps - 1)
                if progress < 0.3:
                    # Exploitation phase
                    temp = self.config.temperature * (1 - progress * 0.5)
                elif progress < 0.7:
                    # Exploration phase
                    temp = self.config.temperature + (self.temp_max - self.config.temperature) * ((progress - 0.3) / 0.4)
                else:
                    # Convergence phase
                    temp = self.temp_max - (self.temp_max - self.config.temperature) * ((progress - 0.7) / 0.3)
                temps.append(max(0.1, min(2.0, temp)))
            return temps
        elif strategy == "constant":
            return [self.config.temperature] * num_steps
        elif strategy == "linear_decay":
            return [self.temp_max - (self.temp_max - self.temp_min) * i / max(1, num_steps - 1) for i in range(num_steps)]
        else:
            return [self.config.temperature] * num_steps
    
    def add_candidate(self, candidate: Candidate, llm_skill=None):
        """Add candidate to pool and track embeddings"""
        if len(self.candidate_pool) >= self.max_candidates:
            # Remove least diverse candidate
            if self.generated_embeddings and llm_skill:
                self._remove_least_diverse(llm_skill)
        
        self.candidate_pool.append(candidate)
        
        # Track embedding for diversity
        if self.tokenizer:
            # Simple text-based diversity (placeholder)
            pass
    
    def _remove_least_diverse(self, llm_skill):
        """Remove least diverse candidate from pool"""
        if len(self.candidate_pool) <= 2:
            return
        
        # Compute embeddings if needed
        texts = [c.text for c in self.candidate_pool]
        embeddings = llm_skill.get_embeddings(texts)
        
        # Compute pairwise cosine similarities
        min_avg_sim = float('inf')
        remove_idx = 0
        
        for i in range(len(embeddings)):
            sims = []
            for j in range(len(embeddings)):
                if i != j:
                    sim = torch.nn.functional.cosine_similarity(
                        embeddings[i].unsqueeze(0), 
                        embeddings[j].unsqueeze(0)
                    ).item()
                    sims.append(sim)
            avg_sim = sum(sims) / len(sims)
            if avg_sim < min_avg_sim:
                min_avg_sim = avg_sim
                remove_idx = i
        
        # Remove least diverse
        self.candidate_pool.pop(remove_idx)
        if len(self.generated_embeddings) > remove_idx:
            self.generated_embeddings.pop(remove_idx)
    
    def get_pool_diversity(self, llm_skill=None) -> float:
        """Compute average pairwise cosine distance in pool"""
        if len(self.candidate_pool) < 2:
            return 1.0
        
        if llm_skill and self.tokenizer:
            texts = [c.text for c in self.candidate_pool]
            embeddings = llm_skill.get_embeddings(texts)
            
            total_sim = 0.0
            count = 0
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = torch.nn.functional.cosine_similarity(
                        embeddings[i].unsqueeze(0),
                        embeddings[j].unsqueeze(0)
                    ).item()
                    total_sim += sim
                    count += 1
            
            avg_sim = total_sim / count if count > 0 else 0.0
            return 1.0 - avg_sim  # Distance = 1 - similarity
        
        return 0.5  # Placeholder
    
    def filter_candidates(self, candidates: List[Candidate], min_diversity: float = 0.3) -> List[Candidate]:
        """Filter candidates by diversity threshold"""
        if len(candidates) <= 1:
            return candidates
        
        filtered = [candidates[0]]
        for cand in candidates[1:]:
            # Check diversity against already selected
            diverse = True
            for selected in filtered:
                # Placeholder: would check embedding distance
                pass
            if diverse:
                filtered.append(cand)
        
        return filtered


def create_diversity_controller(config: 'GRGAgentConfig', tokenizer=None) -> 'DiversityController':
    """Factory function to create diversity controller"""
    return DiversityController(config, tokenizer)