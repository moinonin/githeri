#!/usr/bin/env python3
"""
Sprint Orchestrator - Main orchestration engine for parallel sprint execution.
"""

import argparse
import subprocess
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from dependency_graph import DependencyGraph, Sprint


@dataclass
class OrchestrationConfig:
    sprints_file: Path
    workers: int
    dry_run: bool
    verbose: bool
    timeout: int


class SprintOrchestrator:
    def __init__(self, config: OrchestrationConfig):
        self.config = config
        self.graph = DependencyGraph()
        self.results = {}
        self.lock = threading.Lock()
        self.overall_success = True
    
    def load_sprints(self) -> bool:
        """Load sprints from YAML file."""
        try:
            with open(self.config.sprints_file) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ Error loading sprints file: {e}")
            return False
        
        if not isinstance(data, list):
            print("❌ SPRINTS.md must be a YAML list")
            return False
        
        for item in data:
            sprint = Sprint(
                task_id=item.get('task_id', ''),
                summary=item.get('summary', ''),
                depends_on=item.get('depends_on', []),
                parallel_group=item.get('parallel_group')
            )
            self.graph.add_sprint(sprint)
        
        # Validate
        errors = self.graph.validate_dependencies()
        if errors:
            print("❌ Dependency validation failed:")
            for err in errors:
                print(f"  - {err}")
            return False
        
        has_cycle, cycle = self.graph.has_cycle()
        if has_cycle:
            print(f"❌ Circular dependency detected: {' -> '.join(cycle)}")
            return False
        
        print(f"✅ Loaded {len(self.graph.nodes)} sprints")
        return True
    
    def get_execution_plan(self) -> List[List[str]]:
        """Get parallel execution groups."""
        topo_order = self.graph.topological_sort()
        return self.graph.get_parallel_groups(topo_order)
    
    def execute_sprint(self, sprint_id: str) -> Dict:
        """Execute a single sprint using the sprint execution pipeline."""
        sprint = self.graph.nodes[sprint_id]
        print(f"🚀 Starting sprint: {sprint_id} ({sprint.summary})")
        
        if self.config.dry_run:
            print(f"  [DRY RUN] Would execute sprint {sprint_id}")
            time.sleep(0.5)
            return {"sprint_id": sprint_id, "success": True, "output": "dry-run"}
        
        # Execute via make -f Makefile.sprints sprint-all SPRINT=sprint_id
        cmd = [
            "make", "-f", "Makefile.sprints",
            f"SPRINT={sprint_id}",
            "sprint-all"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )
            
            success = result.returncode == 0
            output = result.stdout
            if not success:
                output += "\n" + result.stderr
            
            return {
                "sprint_id": sprint_id,
                "success": success,
                "output": output
            }
        except subprocess.TimeoutExpired:
            return {
                "sprint_id": sprint_id,
                "success": False,
                "output": f"Timeout after {self.config.timeout}s"
            }
        except Exception as e:
            return {
                "sprint_id": sprint_id,
                "success": False,
                "output": str(e)
            }
    
    def execute_parallel(self, sprint_ids: List[str]) -> Dict[str, Dict]:
        """Execute multiple sprints in parallel."""
        phase_results = {}
        
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {executor.submit(self.execute_sprint, sid): sid for sid in sprint_ids}
            
            for future in as_completed(futures):
                sprint_id = futures[future]
                try:
                    result = future.result()
                    phase_results[sprint_id] = result
                    
                    with self.lock:
                        self.results[sprint_id] = result
                    
                    if result["success"]:
                        print(f"✅ Sprint {sprint_id} completed")
                    else:
                        print(f"❌ Sprint {sprint_id} failed")
                except Exception as e:
                    with self.lock:
                        self.results[sprint_id] = {"success": False, "output": str(e)}
                    print(f"❌ Sprint {sprint_id} error: {e}")
        
        return phase_results
    
    def run(self) -> bool:
        """Run the full orchestration."""
        print(f"🎯 Sprint Orchestrator")
        print(f"   Sprints file: {self.config.sprints_file}")
        print(f"   Workers: {self.config.workers}")
        print(f"   Dry run: {self.config.dry_run}")
        print(f"   Timeout: {self.config.timeout}s")
        
        if not self.load_sprints():
            return False
        
        # Get execution plan
        groups = self.get_execution_plan()
        print(f"\n📋 Execution Plan ({len(groups)} phases):")
        for i, group in enumerate(groups):
            print(f"  Phase {i+1}: {', '.join(group)} (parallel)")
        
        if self.config.dry_run:
            print("\n🏃 Dry run complete - no sprints executed")
            return True
        
        # Execute phase by phase
        phase_num = 0
        for group in groups:
            phase_num += 1
            print(f"\n{'='*60}")
            print(f"📦 PHASE {phase_num}: {', '.join(group)}")
            print(f"{'='*60}")
            
            phase_results = self.execute_parallel(group)
            
            # Check if all succeeded
            phase_success = all(r["success"] for r in phase_results.values())
            if not phase_success:
                print(f"⚠️  Phase {phase_num} had failures")
                self.overall_success = False
                
                # Ask whether to continue
                if self.config.verbose:
                    continue_choice = input("Continue anyway? (y/N): ").lower()
                    if continue_choice != 'y':
                        break
            else:
                print(f"✅ Phase {phase_num} completed successfully")
        
        return self.overall_success


def main():
    parser = argparse.ArgumentParser(description="Sprint Orchestrator - Parallel sprint execution with dependency resolution")
    parser.add_argument('--sprints-file', type=Path, default=Path("SPRINTS.md"), help="Path to SPRINTS.md")
    parser.add_argument('--workers', type=int, default=3, help="Number of parallel workers")
    parser.add_argument('--dry-run', action='store_true', help="Show execution plan without running")
    parser.add_argument('--verbose', action='store_true', help="Verbose output")
    parser.add_argument('--timeout', type=int, default=3600, help="Timeout per sprint (seconds)")
    args = parser.parse_args()
    
    config = OrchestrationConfig(
        sprints_file=args.sprints_file,
        workers=args.workers,
        dry_run=args.dry_run,
        verbose=args.verbose,
        timeout=args.timeout
    )
    
    orchestrator = SprintOrchestrator(config)
    success = orchestrator.run()
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 EXECUTION SUMMARY")
    print(f"{'='*60}")
    
    if hasattr(orchestrator, 'results'):
        for sprint_id, result in orchestrator.results.items():
            status = "✅" if result.get("success") else "❌"
            print(f"  {status} {sprint_id}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()