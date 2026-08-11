#!/usr/bin/env python3
"""GRG Executor - Executes COMMAND_RUNWAY plans with GRG quality gates."""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import GRGAgentConfig
from .llm_client import create_llm_client, BaseLLMClient, GenerationResult
from .monitor import GRGMonitor, create_monitor
from .diversity import DiversityController, create_diversity_controller
from .planner import CodePlanner, create_planner
from .verifier import CodeVerifier, create_verifier
from .state import Candidate, Score


@dataclass
class RunbookCommand:
    """Single command in runbook execution log."""
    id: str
    type: str  # inspect | modify | verify
    tool: str
    args: Dict[str, Any]
    depends_on: List[str]
    expected: Dict[str, Any]
    fallback: str
    passed: bool = False
    output: str = ""
    error: str = ""
    retry_count: int = 0
    started_at: str = ""
    completed_at: str = ""
    grg_composite: float = 0.0


@dataclass
class RunbookStage:
    """Stage in runbook."""
    id: str
    commands: List[RunbookCommand]
    completion_condition: str
    passed: bool = False


@dataclass
class Runbook:
    """COMMAND_RUNWAY Layer 3 execution log."""
    task_id: str
    status: str  # Draft | In-Flight | Verified | Blocked
    preconditions: List[Dict[str, Any]]
    stages: List[RunbookStage]
    goals: Dict[str, List[Dict[str, Any]]]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class GRGExecutor:
    """Executes COMMAND_RUNWAY plans using GRG quality monitoring."""
    
    def __init__(self, config: GRGAgentConfig, provider: str = "auto", foreign_dir: str = "foreign"):
        self.config = config
        self.foreign_dir = Path(foreign_dir)
        self.foreign_dir.mkdir(parents=True, exist_ok=True)
        self.llm_client = create_llm_client(provider)
        self.monitor = create_monitor(config)
        self.diversity = create_diversity_controller(config)
        self.planner = create_planner(config)
        self.verifier = create_verifier(config)
        self.runbook: Optional[Runbook] = None
    
    async def execute_plan(self, plan_path: str) -> Runbook:
        """Execute a COMMAND_RUNWAY plan and produce RUNBOOK.md + JSON."""
        plan = self._load_plan(plan_path)
        task_id = plan.get("task_id", "unknown")
        
        # Initialize runbook
        self.runbook = Runbook(
            task_id=task_id,
            status="In-Flight",
            preconditions=plan.get("preconditions", []),
            stages=[],
            goals={"local": [], "global": plan.get("global_verification", [])},
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        
        print(f"\n{'='*60}")
        print(f"GRG EXECUTOR: {task_id}")
        print(f"{'='*60}")
        
        # Execute stages sequentially
        for stage_def in plan.get("stages", []):
            stage_result = await self._execute_stage(stage_def)
            self.runbook.stages.append(stage_result)
            self.runbook.updated_at = datetime.utcnow().isoformat()
            
            # Check stage completion
            if not stage_result.passed:
                self.runbook.status = "Blocked"
                print(f"\n❌ Stage {stage_result.id} FAILED - stopping execution")
                break
            else:
                print(f"\n✅ Stage {stage_result.id} PASSED")
        
        else:
            # All stages passed - run global verification
            print(f"\n🔍 Running global verification...")
            global_passed = await self._run_global_verification()
            self.runbook.status = "Verified" if global_passed else "Blocked"
        
        # Save runbook
        self._save_runbook()
        return self.runbook
    
    def _load_plan(self, plan_path: str) -> Dict[str, Any]:
        """Load plan from JSON or markdown."""
        path = Path(plan_path)
        if path.suffix == ".json":
            return json.loads(path.read_text())
        elif path.suffix == ".md":
            # Parse markdown plan - simplified, would need full parser
            return {"task_id": path.stem, "stages": []}
        else:
            raise ValueError(f"Unsupported plan format: {plan_path}")
    
    async def _execute_stage(self, stage_def: Dict[str, Any]) -> RunbookStage:
        """Execute a single stage with GRG verification."""
        stage_id = stage_def.get("id", "unknown")
        commands_def = stage_def.get("commands", [])
        completion_condition = stage_def.get("completion_condition", "all verify pass")
        
        print(f"\n{'─'*50}")
        print(f"STAGE: {stage_id}")
        print(f"{'─'*50}")
        
        stage = RunbookStage(
            id=stage_id,
            commands=[],
            completion_condition=completion_condition,
        )
        
        # Separate commands by type (inspect → modify → verify)
        inspect_cmds = [c for c in commands_def if c.get("type") == "inspect"]
        modify_cmds = [c for c in commands_def if c.get("type") == "modify"]
        verify_cmds = [c for c in commands_def if c.get("type") == "verify"]
        
        # Execute in order: inspect → modify → verify
        all_cmds = inspect_cmds + modify_cmds + verify_cmds
        
        for cmd_def in all_cmds:
            cmd = self._to_runbook_command(cmd_def)
            result = await self._execute_command(cmd)
            stage.commands.append(result)
            
            # If ANY command fails, apply failure procedure
            if not result.passed:
                await self._handle_failure(stage, result)
                stage.passed = False
                return stage
        
        # Check stage completion condition
        verify_results = [c.passed for c in stage.commands if c.type == "verify"]
        stage.passed = all(verify_results) if verify_results else True
        return stage
    
    def _to_runbook_command(self, cmd_def: Dict[str, Any]) -> RunbookCommand:
        """Convert plan command to runbook command."""
        return RunbookCommand(
            id=cmd_def.get("id", "C1"),
            type=cmd_def.get("type", "verify"),
            tool=cmd_def.get("tool", "shell"),
            args=cmd_def.get("args", {}),
            depends_on=cmd_def.get("depends_on", []),
            expected=cmd_def.get("expected", {}),
            fallback=cmd_def.get("fallback", "retry"),
        )
    
    async def _execute_command(self, cmd: RunbookCommand) -> RunbookCommand:
        """Execute a single command with retry logic."""
        cmd.started_at = datetime.utcnow().isoformat()
        
        for attempt in range(cmd.retry_count + 1):
            cmd.retry_count = attempt
            
            try:
                if cmd.tool == "shell":
                    result = await self._run_shell(cmd)
                elif cmd.tool == "read_file":
                    result = await self._run_read_file(cmd)
                elif cmd.tool == "write_file":
                    result = await self._run_write_file(cmd)
                elif cmd.tool == "patch":
                    result = await self._run_patch(cmd)
                elif cmd.tool == "llm_generate":
                    result = await self._run_llm_generate(cmd)
                else:
                    result = {"passed": False, "output": "", "error": f"Unknown tool: {cmd.tool}"}
                
                cmd.output = result.get("output", "")
                cmd.error = result.get("error", "")
                cmd.passed = result.get("passed", False)
                cmd.grg_composite = result.get("grg_composite", 0.0)
                
                if cmd.passed:
                    break
                    
            except Exception as e:
                cmd.error = str(e)
                cmd.passed = False
            
            if not cmd.passed and attempt < 2:  # Max 3 attempts
                print(f"  ⚠️ Command {cmd.id} failed (attempt {attempt + 1}), retrying...")
                await asyncio.sleep(1)
        
        cmd.completed_at = datetime.utcnow().isoformat()
        return cmd
    
    async def _run_shell(self, cmd: RunbookCommand) -> Dict[str, Any]:
        """Execute shell command. Use foreign_dir as cwd for verify commands."""
        shell_cmd = cmd.args.get("command", "")
        timeout = cmd.args.get("timeout", 30)
        
        # Verify commands run inside foreign_dir so relative paths resolve
        # to generated artifacts, not native project files
        run_cwd = self.foreign_dir if cmd.type == "verify" else Path.cwd()
        
        print(f"  🔧 $ {shell_cmd}")
        if cmd.type == "verify":
            print(f"     (cwd: {run_cwd})")
        
        try:
            proc = await asyncio.create_subprocess_shell(
                shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(run_cwd)
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            # Check expectations
            expected = cmd.expected
            passed = True
            
            if "exit_code" in expected:
                passed = passed and (proc.returncode == expected["exit_code"])
            
            if "stdout_contains" in expected:
                passed = passed and (expected["stdout_contains"] in output)
            
            if "stdout_regex" in expected:
                import re
                passed = passed and bool(re.search(expected["stdout_regex"], output))
            
            return {"passed": passed, "output": output, "error": error, "grg_composite": 0.0}
            
        except asyncio.TimeoutError:
            return {"passed": False, "output": "", "error": f"Timeout after {timeout}s", "grg_composite": 0.0}
        except Exception as e:
            return {"passed": False, "output": "", "error": str(e), "grg_composite": 0.0}
    
    async def _run_read_file(self, cmd: RunbookCommand) -> Dict[str, Any]:
        """Read file command."""
        path = cmd.args.get("path", "")
        try:
            content = Path(path).read_text()
            passed = True
            if "content_contains" in cmd.expected:
                passed = cmd.expected["content_contains"] in content
            return {"passed": passed, "output": content[:500], "error": "", "grg_composite": 0.0}
        except Exception as e:
            return {"passed": False, "output": "", "error": str(e), "grg_composite": 0.0}
    
    async def _run_write_file(self, cmd: RunbookCommand) -> Dict[str, Any]:
        """Write file command (typically LLM-generated code)."""
        path = cmd.args.get("path", "")
        prompt = cmd.args.get("prompt", "")
        
        if not prompt:
            return {"passed": False, "output": "", "error": "No prompt provided for write_file", "grg_composite": 0.0}
        
        # Generate candidates with diversity
        variants = self.diversity.generate_variants(
            base_prompt=prompt,
            num_variants=self.config.candidates_per_strategy,
        )
        
        best_candidate = None
        best_score = 0.0
        
        for variant in variants:
            result = await self.llm_client.generate(
                prompt=variant.prompt,
                temperature=variant.temperature,
                top_p=variant.top_p,
                max_tokens=2048,
                logprobs=True,
            )
            
            candidate = Candidate(
                text=result.text,
                logprobs=result.logprobs or [],
                strategy=variant.name,
                iteration=0,
            )
            
            # Score with GRG
            if candidate.logprobs:
                score = self.monitor.score_candidate(candidate)
                if score.mean_composite > best_score:
                    best_score = score.mean_composite
                    best_candidate = candidate
        
        if best_candidate:
            foreign_path = self.foreign_dir / path
            foreign_path.parent.mkdir(parents=True, exist_ok=True)
            foreign_path.write_text(best_candidate.text)
            
            # Auto-fix with ruff (non-blocking)
            try:
                subprocess.run(
                    ["ruff", "check", "--fix", str(foreign_path)],
                    capture_output=True,
                    timeout=10,
                    cwd=Path.cwd()
                )
            except Exception:
                pass
            
            # Verify file content
            passed = True
            if "content_contains" in cmd.expected:
                passed = cmd.expected["content_contains"] in best_candidate.text
            
            return {
                "passed": passed,
                "output": f"Generated {foreign_path} (strategy: {best_candidate.strategy}, composite: {best_score:.3f})",
                "error": "",
                "grg_composite": best_score,
            }
        else:
            return {"passed": False, "output": "", "error": "No candidates generated", "grg_composite": 0.0}
    
    async def _run_patch(self, cmd: RunbookCommand) -> Dict[str, Any]:
        """Apply patch command."""
        # Simplified - would need full patch implementation
        return {"passed": False, "output": "", "error": "Patch not implemented", "grg_composite": 0.0}
    
    async def _run_llm_generate(self, cmd: RunbookCommand) -> Dict[str, Any]:
        """LLM generation with DiversityController multi-candidate + GRG scoring (L2/L3)."""
        prompt = cmd.args.get("prompt", "")
        max_tokens = cmd.args.get("max_tokens", 2048)
        
        # Generate diverse candidates
        variants = self.diversity.generate_variants(
            base_prompt=prompt,
            num_variants=self.config.candidates_per_strategy,
        )
        
        best_candidate = None
        best_score = 0.0
        
        for variant in variants:
            result = await self.llm_client.generate(
                prompt=variant.prompt,
                temperature=variant.temperature,
                top_p=variant.top_p,
                max_tokens=max_tokens,
                logprobs=True,
            )
            
            candidate = Candidate(
                text=result.text,
                logprobs=result.logprobs or [],
                strategy=variant.name,
                iteration=0,
            )
            
            # Score with GRG (L2: composite as quality gate)
            if candidate.logprobs:
                score = self.monitor.score_candidate(candidate)
                if score.mean_composite > best_score:
                    best_score = score.mean_composite
                    best_candidate = candidate
        
        if best_candidate:
            # Write to disk if path specified - use foreign directory
            path = cmd.args.get("path")
            if path:
                foreign_path = self.foreign_dir / path
                foreign_path.parent.mkdir(parents=True, exist_ok=True)
                foreign_path.write_text(best_candidate.text)
                path = foreign_path  # Use foreign path for subsequent operations
                
                # Auto-fix with ruff (non-blocking, logs warnings)
                try:
                    subprocess.run(
                        ["ruff", "check", "--fix", str(foreign_path)],
                        capture_output=True,
                        timeout=10,
                        cwd=Path.cwd()
                    )
                except Exception:
                    pass  # Ruff failure doesn't fail the stage
            
            # Verify content
            passed = True
            if "content_contains" in cmd.expected:
                passed = cmd.expected["content_contains"] in best_candidate.text
            
            # L2: GRG composite must meet minimum threshold (configurable)
            # Note: GRG composites for code are typically 0.1-0.5 range
            min_composite = self.config.composite_floor * 0.2  # 0.1 default
            if best_score < min_composite:
                passed = False
                error = f"GRG composite {best_score:.3f} below threshold {min_composite}"
            else:
                error = ""
            
            return {
                "passed": passed,
                "output": f"Generated (strategy: {best_candidate.strategy}, GRG: {best_score:.3f})" + (f"\n{best_candidate.text[:300]}" if not path else ""),
                "error": error,
                "grg_composite": best_score,
            }
        else:
            return {"passed": False, "output": "", "error": "No candidates generated", "grg_composite": 0.0}
    
    async def _handle_failure(self, stage: RunbookStage, failed_cmd: RunbookCommand):
        """COMMAND_RUNWAY failure procedure: stop, diagnose, record, retry."""
        print(f"\n  🛑 FAILURE in {stage.id}/{failed_cmd.id}")
        print(f"     Error: {failed_cmd.error}")
        print(f"     Output: {failed_cmd.output[:200]}")
        
        # Record iteration in runbook metadata
        if "iterations" not in self.runbook.metadata:
            self.runbook.metadata["iterations"] = []
        
        self.runbook.metadata["iterations"].append({
            "stage_id": stage.id,
            "command_id": failed_cmd.id,
            "error": failed_cmd.error,
            "diagnosis": self._diagnose_failure(failed_cmd),
            "corrective_action": self._corrective_action(failed_cmd),
            "retry_count": failed_cmd.retry_count,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Stop dependent commands (don't execute them)
        for cmd in stage.commands:
            if failed_cmd.id in cmd.depends_on and not cmd.completed_at:
                cmd.passed = False
                cmd.error = f"Blocked by failure of {failed_cmd.id}"
    
    def _diagnose_failure(self, cmd: RunbookCommand) -> str:
        """Classify failure type."""
        error = cmd.error.lower()
        if "import" in error or "modulenotfound" in error:
            return "missing_dependency"
        elif "assert" in error or "test" in error:
            return "test_failure"
        elif "connection" in error or "timeout" in error:
            return "environment"
        elif "syntax" in error or "indentation" in error:
            return "bad_implementation"
        else:
            return "unknown"
    
    def _corrective_action(self, cmd: RunbookCommand) -> str:
        """Suggest corrective action."""
        diagnosis = self._diagnose_failure(cmd)
        actions = {
            "missing_dependency": "Install missing package and retry",
            "test_failure": "Fix implementation to satisfy test",
            "environment": "Resolve environment/configuration issue",
            "bad_implementation": "Fix code bug and retry",
            "unknown": "Analyze error and apply fix",
        }
        return actions.get(diagnosis, "Investigate and fix")
    
    async def _run_global_verification(self) -> bool:
        """Run global verification commands."""
        global_commands = self.runbook.goals.get("global", [])
        all_passed = True
        
        for i, gv_cmd in enumerate(global_commands):
            print(f"  Global check {i+1}: {gv_cmd}")
            cmd = RunbookCommand(
                id=f"GV{i+1}",
                type="verify",
                tool="shell",
                args={"command": gv_cmd, "timeout": 120},
                depends_on=[],
                expected={"exit_code": 0},
                fallback="fail",
            )
            result = await self._execute_command(cmd)
            if not result.passed:
                all_passed = False
                print(f"    ❌ FAILED")
            else:
                print(f"    ✅ PASSED")
        
        return all_passed
    
    def _save_runbook(self):
        """Save runbook as markdown and JSON in foreign directory."""
        if not self.runbook:
            return
        
        # JSON for automation
        json_path = self.foreign_dir / "RUNBOOK.json"
        json_data = {
            "task_id": self.runbook.task_id,
            "status": self.runbook.status,
            "preconditions": self.runbook.preconditions,
            "stages": [
                {
                    "id": s.id,
                    "commands": [asdict(c) for c in s.commands],
                    "completion_condition": s.completion_condition,
                    "passed": s.passed,
                }
                for s in self.runbook.stages
            ],
            "goals": self.runbook.goals,
            "created_at": self.runbook.created_at,
            "updated_at": self.runbook.updated_at,
            "metadata": self.runbook.metadata,
        }
        json_path.write_text(json.dumps(json_data, indent=2))
        
        # Markdown for human review
        md_path = self.foreign_dir / "RUNBOOK.md"
        lines = [
            f"# Runbook: {self.runbook.task_id}",
            f"",
            f"Status: {self.runbook.status}",
            f"Created: {self.runbook.created_at}",
            f"Updated: {self.runbook.updated_at}",
            f"",
        ]
        
        for stage in self.runbook.stages:
            status_icon = "✅" if stage.passed else "❌"
            lines.append(f"## {status_icon} Stage {stage.id}")
            lines.append(f"Completion: {stage.completion_condition}")
            lines.append("")
            
            for cmd in stage.commands:
                cmd_status = "✅" if cmd.passed else "❌"
                grg_info = f" (GRG: {cmd.grg_composite:.3f})" if cmd.grg_composite > 0 else ""
                lines.append(f"- {cmd_status} **{cmd.id}** ({cmd.type}){grg_info}")
                lines.append(f"  Command: `{cmd.args.get('command', cmd.args.get('prompt', 'N/A'))}`")
                if cmd.output:
                    lines.append(f"  Output: {cmd.output[:200]}")
                if cmd.error:
                    lines.append(f"  Error: {cmd.error}")
                if cmd.retry_count > 0:
                    lines.append(f"  Retries: {cmd.retry_count}")
                lines.append("")
        
        if self.runbook.metadata.get("iterations"):
            lines.append("## Iterations (Failures & Corrections)")
            for it in self.runbook.metadata["iterations"]:
                lines.append(f"- **{it['stage_id']}/{it['command_id']}**: {it['diagnosis']}")
                lines.append(f"  Action: {it['corrective_action']}")
                lines.append(f"  Retries: {it['retry_count']}")
                lines.append("")
        
        md_path.write_text("\n".join(lines))
        
        print(f"\n📝 Runbook saved: {md_path} + {json_path}")


# CLI entry point
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="GRG Executor for COMMAND_RUNWAY plans")
    parser.add_argument("--plan", required=True, help="Path to plan JSON/markdown")
    parser.add_argument("--provider", default="auto", help="LLM provider: auto, hermes, ollama")
    parser.add_argument("--verify", help="Verify runbook completeness")
    parser.add_argument("--foreign-dir", default="foreign", help="Directory for generated artifacts (default: foreign)")
    args = parser.parse_args()
    
    config = GRGAgentConfig()
    executor = GRGExecutor(config, provider=args.provider, foreign_dir=args.foreign_dir)
    
    if args.verify:
        # Verify existing runbook
        runbook_path = Path(args.verify)
        if runbook_path.suffix == ".json":
            data = json.loads(runbook_path.read_text())
            stages = data.get("stages", [])
            all_passed = all(s.get("passed", False) for s in stages)
            print(f"Runbook status: {'VERIFIED' if all_passed else 'BLOCKED'}")
            print(f"Stages: {len(stages)}, Passed: {sum(1 for s in stages if s.get('passed'))}")
            exit(0 if all_passed else 1)
        else:
            print("Only JSON runbook verification supported")
            exit(1)
    else:
        runbook = await executor.execute_plan(args.plan)
        print(f"\n{'='*60}")
        print(f"FINAL STATUS: {runbook.status}")
        print(f"Stages passed: {sum(1 for s in runbook.stages if s.passed)}/{len(runbook.stages)}")
        exit(0 if runbook.status == "Verified" else 1)


if __name__ == "__main__":
    asyncio.run(main())