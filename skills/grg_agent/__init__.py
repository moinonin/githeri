# GRG Agent Skill for Hermes
# This makes the skill a proper Python package and exposes the grg_agent subpackage

from .grg_agent.hermes_skill import GRGAgentSkill, create_skill, SKILL_MANIFEST

__all__ = ["GRGAgentSkill", "create_skill", "SKILL_MANIFEST"]