#!/usr/bin/env python3
"""GRG Agent State - Core data structures"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Score:
    """GRG score for a candidate"""
    composites: List[float] = field(default_factory=list)
    mean_composite: float = 0.0
    grg_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.composites:
            self.mean_composite = sum(self.composites) / len(self.composites)


@dataclass
class Candidate:
    """A generated candidate with GRG scoring"""
    text: str
    logprobs: List[float]
    strategy: str
    iteration: int
    score: Optional['Score'] = None
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if isinstance(self.metadata, str):
            import json
            self.metadata = json.loads(self.metadata)


@dataclass
class Strategy:
    """Generation strategy"""
    name: str
    prompt: str
    temperature: float
    top_p: float
    description: str = ""
    iteration: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryState:
    """Full trajectory state across agent iterations"""
    candidates: List[Candidate] = field(default_factory=list)
    iteration: int = 0
    grg_history: List[Dict[str, Any]] = field(default_factory=list)
    best_candidate: Optional[Candidate] = None
    strategies_used: List[str] = field(default_factory=list)
    diversity_history: List[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_candidate(self, candidate: Candidate):
        self.candidates.append(candidate)
        self.updated_at = datetime.now()
    
    def get_best_by_composite(self) -> Optional[Candidate]:
        """Get candidate with highest mean composite"""
        scored = [c for c in self.candidates if c.score is not None]
        if not scored:
            return None
        return max(scored, key=lambda c: c.score.mean_composite if c.score else 0.0)
    
    def get_verified(self) -> List[Candidate]:
        return [c for c in self.candidates if c.verified]
    
    def get_diversity_score(self) -> float:
        """Average pairwise cosine distance between candidate embeddings"""
        if len(self.candidates) < 2:
            return 1.0
        # Placeholder - would need embeddings
        return 0.5


@dataclass
class GRGHistoryEntry:
    """Single entry in GRG history"""
    iteration: int
    alpha: float
    v_alpha: float
    m_alpha: float
    horizon: float
    is_collapsing: bool
    is_stable: bool
    composite: float
    timestamp: datetime = field(default_factory=datetime.now)