#!/usr/bin/env python3
"""GRG Agent Hermes Skill - Entry point for Hermes integration."""

import asyncio
import os
from typing import Dict, Any, Optional
from pathlib import Path

from .config import GRGAgentConfig
from .agent_hermes import GRGAgentHermes, create_agent_hermes
from .llm_client import create_llm_client
from .executor import GRGExecutor, Runbook


class GRGAgentSkill:
    """
    Hermes Skill for GRG Agent.

    Integrates with Hermes's plugin system and provides commands:
    - /grg solve <task>
    - /grg analyze <file>
    - /grg config
    """

    def __init__(self, hermes_app=None, config: Dict[str, Any] = None):
        self.app = hermes_app
        self.config = config or {}
        self.agent = None
        self._init_agent()

    def _init_agent(self):
        """Initialize GRG agent with skill config and LLM provider."""
        agent_config = GRGAgentConfig(
            max_iterations=self.config.get('max_iterations', 5),
            candidates_per_strategy=self.config.get('candidates_per_strategy', 3),
            max_candidates=self.config.get('max_candidates', 15),
            grg_window=self.config.get('grg_window', 16),
            grg_threshold_mult=self.config.get('grg_threshold_mult', 1.5),
            alpha_critical=self.config.get('alpha_critical', 0.1),
            horizon_critical=self.config.get('horizon_critical', 5.0),
            composite_floor=self.config.get('composite_floor', 0.5),
            composite_ceiling=self.config.get('composite_ceiling', 1.5),
            diversity_temperature_range=tuple(self.config.get('diversity_temperature_range', [0.3, 1.5])),
            diversity_min_cosine=self.config.get('diversity_min_cosine', 0.3),
            diversity_max_candidates=self.config.get('diversity_max_candidates', 20),
            temperature=self.config.get('temperature', 0.8),
            top_p=self.config.get('top_p', 0.9),
            max_tokens=self.config.get('max_tokens', 256),
            max_strategies=self.config.get('max_strategies', 4),
            planner_temperature=self.config.get('planner_temperature', 0.7),
            verify_execution=self.config.get('verify_execution', True),
            verify_timeout=self.config.get('verify_timeout', 10),
        )

        # Provider selection: "auto" | "hermes" | "ollama"
        provider = self.config.get('llm_provider', 'auto')

        # Provider-specific kwargs
        provider_kwargs = {}
        if provider == "hermes":
            proxy_url = self.config.get('hermes_proxy_url') or os.environ.get('HERMES_PROXY_URL')
            if proxy_url:
                provider_kwargs['proxy_url'] = proxy_url
        elif provider == "ollama":
            provider_kwargs['base_url'] = self.config.get('ollama_base_url') or os.environ.get('BASE_URL', 'http://127.0.0.1:11434/v1')
            provider_kwargs['default_model'] = self.config.get('ollama_default_model') or os.environ.get('MODEL', 'qwen2.5-coder:7b-instruct')
            # Allow custom api_key for LM Studio
            if 'api_key' in self.config:
                provider_kwargs['api_key'] = self.config['api_key']
            elif 'LMSTUDIO_API_KEY' in os.environ:
                provider_kwargs['api_key'] = os.environ['LMSTUDIO_API_KEY']

        # Create LLM client
        llm_client = create_llm_client(provider, **provider_kwargs)

        self.agent = create_agent_hermes(agent_config, llm_client)

    async def on_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle skill commands from Hermes."""
        if command == "grg:solve":
            return await self._cmd_solve(args)
        elif command == "grg:execute":
            return await self._cmd_execute(args)
        elif command == "grg:analyze":
            return await self._cmd_analyze(args)
        elif command == "grg:config":
            return await self._cmd_config(args)
        elif command == "grg:help":
            return await self._cmd_help(args)
        else:
            return {"error": f"Unknown command: {command}"}

    async def _cmd_solve(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Solve a coding task."""
        task = args.get('task')
        if not task:
            return {"error": "Missing required argument: task"}

        max_iterations = args.get('iterations', self.config.get('max_iterations', 5))
        model = args.get('model')

        print(f"GRG Agent solving: {task[:100]}...")

        candidate = await self.agent.solve(task, max_iterations=max_iterations, model=model)

        return {
            "success": candidate.verified,
            "code": candidate.text,
            "strategy": candidate.strategy,
            "iteration": candidate.iteration,
            "composite": candidate.score.mean_composite if candidate.score else 0,
            "verified": candidate.verified,
            "metadata": candidate.metadata,
            "stats": self.agent.get_stats(),
        }

    async def _cmd_analyze(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code quality with GRG."""
        file_path = args.get('file')
        if not file_path:
            return {"error": "Missing required argument: file"}

        # Read file
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        code = path.read_text()

        # Create a candidate from existing code
        from .state import Candidate
        candidate = Candidate(
            text=code,
            logprobs=[],  # No logprobs for existing code
            strategy="analyze",
            iteration=0,
        )

        # Score with GRG monitor (using dummy logprobs since we don't have them)
        # This would need actual logprobs from the model that generated it
        # For now, return basic analysis

        return {
            "file": str(path),
            "lines": len(code.split('\n')),
            "chars": len(code),
            "has_def": 'def ' in code,
            "has_class": 'class ' in code,
            "has_imports": 'import ' in code or 'from ' in code,
        }

    async def _cmd_config(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get/set GRG agent configuration."""
        action = args.get('action', 'get')

        if action == 'get':
            return {"config": self.config}
        elif action == 'set':
            key = args.get('key')
            value = args.get('value')
            if key in self.config:
                self.config[key] = value
                self._init_agent()  # Reinitialize with new config
                return {"success": True, "config": self.config}
            return {"error": f"Unknown config key: {key}"}
        return {"error": f"Unknown action: {action}"}

    async def _cmd_help(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Show help for GRG agent commands."""
        return {
            "commands": [
                {
                    "name": "grg:solve",
                    "description": "Solve a coding task with GRG agent",
                    "args": {
                        "task": "string (required) - The coding task to solve",
                        "iterations": "integer (optional) - Max iterations (default: 5)",
                        "model": "string (optional) - Override model (passed to LLM provider)",
                    }
                },
                {
                    "name": "grg:execute",
                    "description": "Execute a COMMAND_RUNWAY plan from spec",
                    "args": {
                        "spec": "string (optional) - Path to spec YAML file",
                        "task": "string (optional) - NL task to generate spec from",
                        "provider": "string (optional) - LLM provider: auto, hermes, ollama",
                    }
                },
                {
                    "name": "grg:analyze",
                    "description": "Analyze code quality with GRG",
                    "args": {
                        "file": "string (required) - Path to file to analyze",
                    }
                },
                {
                    "name": "grg:config",
                    "description": "Get/set GRG agent configuration",
                    "args": {
                        "action": "string - 'get' or 'set'",
                        "key": "string (for set) - Config key",
                        "value": "any (for set) - Config value",
                    }
                },
            ],
            "description": "GRG Agent - Autonomous coding agent with multi-provider LLM support (Hermes Proxy, Ollama, etc.)",
        }

    async def _cmd_execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a COMMAND_RUNWAY plan with GRG executor."""
        spec_path = args.get('spec')
        task = args.get('task')
        provider = args.get('provider', 'auto')
        
        if not spec_path and not task:
            return {"error": "Either 'spec' (path) or 'task' (NL) required"}
        
        config = GRGAgentConfig()
        executor = GRGExecutor(config, provider=provider)
        
        if spec_path:
            # Load spec, generate plan, execute
            # First validate the spec
            import sys
            sys.path.insert(0, '/home/defi/Desktop/portfolio/projects/python/githeri/scripts')
            from validator import validate_spec
            import yaml
            
            with open(spec_path) as f:
                spec_yaml = f.read()
            
            errors = validate_spec(spec_yaml)
            if errors:
                return {"error": f"Spec validation failed: {errors}"}
            
            # Generate plan from spec
            from plan_from_spec import main as plan_main
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(spec_yaml)
                spec_file = f.name
            
            # Run plan_from_spec to get plan prompt
            result = subprocess.run(
                ['python', '-m', 'plan_from_spec', spec_file],
                capture_output=True,
                text=True,
                cwd='/home/defi/Desktop/portfolio/projects/python/githeri',
                env={**os.environ, 'PYTHONPATH': '/home/defi/.hermes/skills/autonomous-ai-agents/grg_agent'}
            )
            
            if result.returncode != 0:
                return {"error": f"Plan generation failed: {result.stderr}"}
            
            # The plan prompt is in result.stdout - we'd need to parse it to JSON
            # For now, return the prompt for manual execution
            return {
                "spec": spec_path,
                "plan_prompt": result.stdout,
                "note": "Plan generated. Execute with grg:execute --plan <plan_json>"
            }
        else:
            # Generate from NL task - use GRG agent directly
            candidate = await self.agent.solve(task, max_iterations=config.max_iterations)
            
            return {
                "task": task,
                "success": candidate.verified,
                "code": candidate.text,
                "strategy": candidate.strategy,
                "iteration": candidate.iteration,
                "composite": candidate.score.mean_composite if candidate.score else 0,
                "verified": candidate.verified,
                "metadata": candidate.metadata,
                "stats": self.agent.get_stats(),
            }


# Skill manifest for Hermes
SKILL_MANIFEST = {
    "name": "grg_agent",
    "version": "1.0.0",
    "description": "GRG-guided autonomous coding agent with multi-provider LLM support",
    "author": "GRG Team",
    "license": "MIT",
    "entry_point": "grg_agent.hermes_skill:GRGAgentSkill",
    "commands": [
        {
            "name": "grg:solve",
            "description": "Solve a coding task with GRG agent",
            "args": {
                "task": {"type": "string", "required": True, "description": "The coding task to solve"},
                "iterations": {"type": "integer", "required": False, "default": 5, "description": "Max iterations"},
                "model": {"type": "string", "required": False, "description": "Override model (passed to LLM provider)"},
            }
        },
        {
            "name": "grg:execute",
            "description": "Execute a COMMAND_RUNWAY plan from spec",
            "args": {
                "spec": {"type": "string", "required": False, "description": "Path to spec YAML file"},
                "task": {"type": "string", "required": False, "description": "NL task to generate spec from"},
                "provider": {"type": "string", "required": False, "description": "LLM provider: auto, hermes, ollama"},
            }
        },
        {
            "name": "grg:analyze",
            "description": "Analyze code quality with GRG",
            "args": {
                "file": {"type": "string", "required": True, "description": "Path to file to analyze"},
            }
        },
        {
            "name": "grg:config",
            "description": "Get/set GRG agent configuration",
            "args": {
                "action": {"type": "string", "required": True, "enum": ["get", "set"]},
                "key": {"type": "string", "required": False},
                "value": {"type": "string", "required": False},
            }
        },
        {
            "name": "grg:help",
            "description": "Show help for GRG agent commands",
            "args": {}
        },
    ],
    "config_schema": {
        "max_iterations": {"type": "integer", "default": 5, "description": "Max agent iterations"},
        "candidates_per_strategy": {"type": "integer", "default": 3, "description": "Candidates per strategy"},
        "max_candidates": {"type": "integer", "default": 15, "description": "Max candidate pool size"},
        "grg_window": {"type": "integer", "default": 16, "description": "GRG tracking window"},
        "grg_threshold_mult": {"type": "number", "default": 1.5, "description": "GRG threshold multiplier"},
        "diversity_temperature_range": {"type": "array", "default": [0.3, 1.5], "description": "Temperature range for diversity"},
        "temperature": {"type": "number", "default": 0.8, "description": "Default generation temperature"},
        "top_p": {"type": "number", "default": 0.9, "description": "Default top-p"},
        "max_tokens": {"type": "integer", "default": 256, "description": "Max tokens per generation"},
        "verify_execution": {"type": "boolean", "default": True, "description": "Verify code execution"},
        "verify_timeout": {"type": "integer", "default": 10, "description": "Verification timeout (seconds)"},
        "llm_provider": {"type": "string", "default": "auto", "enum": ["auto", "hermes", "ollama"], "description": "LLM provider: auto, hermes (proxy), or ollama (local)"},
        "hermes_proxy_url": {"type": "string", "required": False, "description": "Hermes proxy URL (default: http://localhost:8645/v1 or HERMES_PROXY_URL env)"},
        "ollama_base_url": {"type": "string", "default": "http://127.0.0.1:11434/v1", "description": "Ollama API base URL"},
        "ollama_default_model": {"type": "string", "default": "qwen2.5-coder:7b-instruct", "description": "Default Ollama model"},
    },
}


def create_skill(hermes_app=None, config: Dict[str, Any] = None) -> GRGAgentSkill:
    """Factory function for Hermes skill system."""
    return GRGAgentSkill(hermes_app, config)


# CLI entry point for direct usage
async def main():
    """Direct CLI usage for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m grg_agent.hermes_skill <task> [--provider hermes|ollama] [--model MODEL]")
        return

    # Parse args properly
    args = sys.argv[1:]
    task_parts = []
    provider = "auto"
    model = None
    i = 0
    while i < len(args):
        if args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        else:
            task_parts.append(args[i])
            i += 1

    task = " ".join(task_parts)

    # Create skill with provider config
    skill = create_skill(config={"llm_provider": provider})
    result = await skill.on_command("grg:solve", {"task": task, "model": model})

    print("\n" + "="*60)
    print("RESULT")
    print("="*60)
    print(f"Success: {result.get('success')}")
    print(f"Verified: {result.get('verified')}")
    print(f"Strategy: {result.get('strategy')}")
    print(f"Composite: {result.get('composite', 0):.3f}")
    print(f"\nCode:\n{result.get('code', '')}")


if __name__ == "__main__":
    asyncio.run(main())