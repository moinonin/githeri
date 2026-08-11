#!/usr/bin/env python3
"""GRG Agent Configuration"""

from dataclasses import dataclass
from typing import Tuple, Optional, List

# Use the main grg package which is properly installed
from grg import AlphaMomentumTracker, compute_structural_alpha


@dataclass
class GRGAgentConfig:
    """Configuration for GRG Agent"""
    
    # Model
    model_id: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: Optional[List[str]] = None  # defaults to ["q_proj", "v_proj"]
    
    # Model loading
    load_in_4bit: bool = False
    
    # Agent Loop
    max_iterations: int = 5
    candidates_per_strategy: int = 3
    max_candidates: int = 15
    
    # GRG Monitor
    grg_window: int = 16
    grg_threshold_mult: float = 1.5
    alpha_critical: float = 0.1
    horizon_critical: float = 5.0
    composite_floor: float = 0.5
    composite_ceiling: float = 1.5
    
    # Diversity Controller
    diversity_temperature_range: Tuple[float, float] = (0.3, 1.5)
    diversity_min_cosine: float = 0.3
    diversity_max_candidates: int = 20
    
    # LLM Generation
    temperature: float = 0.8
    top_p: float = 0.9
    max_tokens: int = 256
    
    # Planner
    max_strategies: int = 4
    planner_temperature: float = 0.7
    
    # Verifier
    verify_execution: bool = True
    verify_timeout: int = 10
    
    # Device
    device: str = "auto"  # "auto", "mps", "cuda", "cpu"
    
    def __post_init__(self):
        if self.lora_target_modules is None:
            self.lora_target_modules = ["q_proj", "v_proj"]
        
        if self.device == "auto":
            import torch
            self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")


# GRG Monitor Config (for AlphaMomentumTracker)
GRG_TRACKER_CONFIG = {
    "window_size": 20,
    "alpha_ema": 0.3,
    "v_alpha_ema": 0.3,
    "v_panic": 0.1,
}


def get_grg_tracker(config: GRGAgentConfig) -> AlphaMomentumTracker:
    """Create GRG tracker with agent config"""
    return AlphaMomentumTracker(
        window_size=config.grg_window,
        alpha_ema=0.3,
    )