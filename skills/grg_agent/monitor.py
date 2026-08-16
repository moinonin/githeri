#!/usr/bin/env python3
"""GRG Monitor - Scores candidates using GRG trajectory analysis"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from grg import AlphaMomentumTracker, compute_structural_alpha
from .config import GRGAgentConfig
from .state import Candidate, Score, GRGHistoryEntry


class GRGMonitor:
    """
    GRG Monitor - scores candidates using GRG trajectory analysis.
    Reuses AlphaMomentumTracker and compute_structural_alpha from grg package.
    """
    
    def __init__(self, config: 'GRGAgentConfig'):
        self.config = config
        self.tracker = AlphaMomentumTracker(
            window_size=config.grg_window,
            alpha_ema=0.3,
        )
        self.threshold_mult = config.grg_threshold_mult
        self.history: List[GRGHistoryEntry] = []
    
    def reset(self):
        """Reset tracker for new trajectory"""
        self.tracker = AlphaMomentumTracker(
            window_size=self.config.grg_window,
            alpha_ema=0.3,
        )
        self.history.clear()
    
    def push_alpha(self, alpha: float) -> Dict[str, Any]:
        """Push alpha to tracker and return stats"""
        self.tracker.push(alpha)
        return self.tracker.get_stats()
    
    def score_logprobs(self, logprobs: List[float], threshold_mult: Optional[float] = None) -> Score:
        """
        Score a sequence of logprobs using GRG trajectory analysis.
        
        Args:
            logprobs: List of log probabilities for each token
            threshold_mult: Override threshold multiplier
            
        Returns:
            Score with composites and GRG stats
        """
        if threshold_mult is None:
            threshold_mult = self.threshold_mult
        
        composites = []
        tracker = AlphaMomentumTracker(
            window_size=self.config.grg_window,
            alpha_ema=0.3,
        )
        
        for i, lp in enumerate(logprobs):
            window = logprobs[:i]
            if len(window) > 1:
                alpha = compute_structural_alpha(
                    lp,
                    window,
                    threshold_mult
                )
                tracker.push(alpha)
            else:
                tracker.push(0.0)
            
            stats = tracker.get_stats()
            alpha_h = stats.get("alpha", 1.0)
            v_alpha = stats.get("v_alpha", 0.0)
            m_alpha = stats.get("m_alpha", 0.0)
            horizon = stats.get("horizon", 999.0)
            is_collapsing = stats.get("is_collapsing", False)
            is_stable = stats.get("is_stable", False)
            
            # Clamp alpha for safety
            if not math.isfinite(alpha_h):
                alpha_h = 0.0
            if not math.isfinite(v_alpha):
                v_alpha = 0.0
            
            model_prob = math.exp(lp)
            composite = float(model_prob) * max(
                self.config.composite_floor, 
                min(self.config.composite_ceiling, alpha_h * (1 + max(0.0, v_alpha)))
            )
            composites.append(composite)
            
            # Record history
            self.history.append(GRGHistoryEntry(
                iteration=0,  # Will be set by agent
                alpha=alpha_h,
                v_alpha=v_alpha,
                m_alpha=m_alpha,
                horizon=horizon,
                is_collapsing=is_collapsing,
                is_stable=is_stable,
                composite=composite,
            ))
        
        return Score(
            composites=composites,
            mean_composite=sum(composites) / len(composites) if composites else 0.0,
            grg_stats={
                "final_alpha": tracker.ema_alpha,
                "final_v_alpha": tracker.ema_velocity,
                "final_m_alpha": tracker.ema_momentum,
                "final_horizon": tracker.get_structural_horizon(),
                "is_collapsing": tracker.get_stats().get("is_collapsing", False),
                "is_stable": tracker.get_stats().get("is_stable", False),
                "composites": composites,
            }
        )
    
    def score_candidate(self, candidate: 'Candidate', threshold_mult: Optional[float] = None) -> Score:
        """Score a candidate using its logprobs"""
        score = self.score_logprobs(candidate.logprobs, threshold_mult)
        candidate.score = score
        return score
    
    def score_batch(self, candidates: List['Candidate'], threshold_mult: Optional[float] = None) -> List[Score]:
        """Score multiple candidates"""
        return [self.score_candidate(c, threshold_mult) for c in candidates]
    
    def get_best_candidate(self, candidates: List['Candidate']) -> Optional['Candidate']:
        """Select best candidate by mean composite"""
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.score.mean_composite if c.score else 0.0)
    
    def get_trajectory_stats(self) -> Dict[str, Any]:
        """Get aggregate stats for the trajectory"""
        if not self.history:
            return {}
        
        alphas = [h.alpha for h in self.history]
        v_alphas = [h.v_alpha for h in self.history]
        composites = [h.composite for h in self.history]
        
        return {
            "mean_alpha": sum(alphas) / len(alphas),
            "min_alpha": min(alphas),
            "max_alpha": max(alphas),
            "mean_v_alpha": sum(v_alphas) / len(v_alphas),
            "mean_composite": sum(composites) / len(composites),
            "min_composite": min(composites),
            "collapsing_count": sum(1 for h in self.history if h.is_collapsing),
            "stable_count": sum(1 for h in self.history if h.is_stable),
        }
    
    def get_trajectory_health(self) -> Dict[str, float]:
        """Get overall trajectory health metrics"""
        if not self.history:
            return {"health": 0.0, "stability": 0.0, "progress": 0.0}
        
        stats = self.tracker.get_stats()
        trajectory_stats = self.get_trajectory_stats()
        
        # Health: weighted by alpha and composite
        health = (stats.get("alpha", 0) + trajectory_stats.get("mean_composite", 0)) / 2
        
        # Stability: inverse of collapsing frequency
        collapsing_freq = trajectory_stats.get("collapsing_count", 0) / len(self.history)
        stability = 1.0 - collapsing_freq
        
        # Progress: composite trend
        composites = [h.composite for h in self.history]
        if len(composites) > 1:
            progress = (composites[-1] - composites[0]) / len(composites)
        else:
            progress = 0.0
        
        return {
            "health": max(0.0, min(1.0, health)),
            "stability": max(0.0, min(1.0, stability)),
            "progress": progress,
        }


def create_monitor(config: 'GRGAgentConfig') -> 'GRGMonitor':
    """Factory function to create GRG monitor"""
    return GRGMonitor(config)