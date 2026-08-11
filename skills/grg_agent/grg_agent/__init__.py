#!/usr/bin/env python3
"""GRG Agent Package - Unified exports for both local and Hermes versions"""

# Core components (shared)
from .config import GRGAgentConfig, get_grg_tracker
from .state import (
    Candidate, Strategy, TrajectoryState, Score, 
    GRGHistoryEntry
)
from .monitor import GRGMonitor, create_monitor
from .diversity import DiversityController, create_diversity_controller
from .planner import CodePlanner, create_planner, Plan
from .verifier import CodeVerifier, create_verifier, VerificationResult
from .executor import GRGExecutor, Runbook, RunbookStage, RunbookCommand

# Local model version
from .llm_skill import LLMSkill, create_llm_skill
from .agent import GRGAgent, create_agent

# Hermes version
from .llm_client import HermesLLMClient, GenerationResult, EmbeddingResult, create_hermes_client
from .agent_hermes import GRGAgentHermes, create_agent_hermes
from .hermes_skill import GRGAgentSkill, create_skill, SKILL_MANIFEST

__all__ = [
    # Config
    "GRGAgentConfig",
    "get_grg_tracker",
    
    # State
    "Candidate",
    "Strategy", 
    "TrajectoryState",
    "Score",
    "Plan",
    "GRGHistoryEntry",
    
    # Core components
    "GRGMonitor",
    "create_monitor",
    "DiversityController",
    "create_diversity_controller",
    "CodePlanner",
    "create_planner",
    "Plan",
    "CodeVerifier",
    "create_verifier",
    "VerificationResult",
    "GRGExecutor",
    "Runbook",
    "RunbookStage",
    "RunbookCommand",
    
    # Local model version
    "LLMSkill",
    "create_llm_skill",
    "GRGAgent",
    "create_agent",
    
    # Hermes version
    "HermesLLMClient",
    "GenerationResult",
    "EmbeddingResult",
    "create_hermes_client",
    "GRGAgentHermes",
    "create_agent_hermes",
    "GRGAgentSkill",
    "create_skill",
    "SKILL_MANIFEST",
]