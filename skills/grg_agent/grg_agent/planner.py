#!/usr/bin/env python3
"""Code Planner - Task decomposition and strategy selection"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import random

from .config import GRGAgentConfig
from .state import Strategy


@dataclass
class Plan:
    """Execution plan for a task"""
    task: str
    strategies: List[Strategy]
    estimated_iterations: int
    tools_needed: List[str]
    risk_assessment: Dict[str, float]


class CodePlanner:
    """
    Plans code generation tasks by decomposing into strategies.
    """
    
    def __init__(self, config: 'GRGAgentConfig'):
        self.config = config
        self.max_strategies = config.max_strategies
        self.planner_temperature = config.planner_temperature
    
    def analyze_task(self, task: str) -> Dict[str, Any]:
        """Analyze task to determine type and difficulty"""
        task_lower = task.lower()
        
        # Detect task type
        task_type = "general"
        if any(kw in task_lower for kw in ["sort", "search", "binary", "merge", "quick"]):
            task_type = "algorithm"
        elif any(kw in task_lower for kw in ["tree", "bst", "linked list", "graph", "heap"]):
            task_type = "data_structure"
        elif any(kw in task_lower for kw in ["dp", "dynamic programming", "knapsack", "coin change", "lcs"]):
            task_type = "dynamic_programming"
        elif any(kw in task_lower for kw in ["string", "regex", "palindrome", "kmp", "substring"]):
            task_type = "string"
        elif any(kw in task_lower for kw in ["dijkstra", "bfs", "dfs", "topological", "cycle", "mst"]):
            task_type = "graph"
        elif any(kw in task_lower for kw in ["class", "design", "implement", "system", "api"]):
            task_type = "system_design"
        
        # Estimate difficulty
        difficulty = "easy"
        if task_type in ["dynamic_programming", "graph", "system_design"]:
            difficulty = "hard"
        elif task_type in ["data_structure", "string"]:
            difficulty = "medium"
        
        # Estimate iterations needed
        base_iterations = 3
        if difficulty == "hard":
            base_iterations = 5
        elif difficulty == "medium":
            base_iterations = 4
        
        return {
            "task_type": task_type,
            "difficulty": difficulty,
            "estimated_iterations": min(base_iterations, 5),
        }
    
    def generate_strategies(self, task: str, analysis: Optional[Dict[str, Any]] = None) -> List[Strategy]:
        """Generate strategies for a task"""
        if analysis is None:
            analysis = self.analyze_task(task)
        
        task_type = analysis.get("task_type", "general")
        difficulty = analysis.get("difficulty", "easy")
        
        # Base strategies for all tasks
        strategies = [
            Strategy(
                name="standard",
                prompt="",  # Will be filled by agent
                temperature=0.8,
                top_p=0.9,
                description="Standard generation"
            ),
        ]
        
        # Add task-specific strategies
        if task_type == "algorithm":
            strategies.extend([
                Strategy(name="decompose", prompt="", temperature=0.7, top_p=0.9, 
                         description="Step-by-step decomposition"),
                Strategy(name="test_first", prompt="", temperature=0.8, top_p=0.9,
                         description="Write tests first"),
            ])
        elif task_type == "data_structure":
            strategies.extend([
                Strategy(name="decompose", prompt="", temperature=0.7, top_p=0.9,
                         description="Break into operations"),
                Strategy(name="explain", prompt="", temperature=0.7, top_p=0.9,
                         description="Explain invariants first"),
            ])
        elif task_type == "dynamic_programming":
            strategies.extend([
                Strategy(name="decompose", prompt="", temperature=0.6, top_p=0.9,
                         description="Identify states and transitions"),
                Strategy(name="test_first", prompt="", temperature=0.8, top_p=0.9,
                         description="Test base cases first"),
            ])
        elif task_type == "graph":
            strategies.extend([
                Strategy(name="decompose", prompt="", temperature=0.7, top_p=0.9,
                         description="Identify nodes/edges/traversal"),
                Strategy(name="explain", prompt="", temperature=0.7, top_p=0.9,
                         description="Explain traversal strategy"),
            ])
        elif task_type == "string":
            strategies.extend([
                Strategy(name="decompose", prompt="", temperature=0.7, top_p=0.9,
                         description="Character/pattern analysis"),
                Strategy(name="test_first", prompt="", temperature=0.8, top_p=0.9,
                         description="Test edge cases"),
            ])
        
        # For harder tasks, add refinement strategy
        if difficulty == "hard":
            strategies.append(
                Strategy(name="refine", prompt="", temperature=0.8, top_p=0.9,
                         description="Iterative refinement")
            )
        
        # Limit number of strategies
        return strategies[:self.config.max_strategies]
    
    def create_plan(self, task: str) -> Plan:
        """Create full execution plan for a task"""
        analysis = self.analyze_task(task)
        strategies = self.generate_strategies(task, analysis)
        
        # Fill in prompts (will be populated by agent)
        for strategy in strategies:
            if not strategy.prompt:
                strategy.prompt = task
        
        return Plan(
            task=task,
            strategies=strategies,
            estimated_iterations=analysis.get("estimated_iterations", 3),
            tools_needed=self._get_tools_needed(analysis),
            risk_assessment=self._assess_risk(analysis),
        )
    
    def _get_tools_needed(self, analysis: Dict[str, Any]) -> List[str]:
        """Determine what verification tools are needed"""
        tools = ["execution"]
        task_type = analysis.get("task_type", "general")
        
        if task_type in ["data_structure", "system_design"]:
            tools.append("type_check")
        if task_type in ["algorithm", "dynamic_programming", "graph"]:
            tools.append("test_generation")
        
        return tools
    
    def _assess_risk(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Assess risk factors for the task"""
        difficulty = analysis.get("difficulty", "easy")
        
        risk = {
            "complexity": 0.3 if difficulty == "easy" else (0.5 if difficulty == "medium" else 0.8),
            "ambiguity": 0.2,
            "verification_difficulty": 0.3 if difficulty == "easy" else (0.5 if difficulty == "medium" else 0.7),
        }
        return risk


def create_planner(config: 'GRGAgentConfig') -> 'CodePlanner':
    """Factory function to create planner"""
    return CodePlanner(config)