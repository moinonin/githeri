#!/usr/bin/env python3
"""
Worker Pool - Parallel sprint execution with resource management.
"""

import argparse
import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum


class SprintStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Sprint:
    task_id: str
    summary: str
    depends_on: List[str]
    parallel_group: Optional[str] = None
    status: SprintStatus = SprintStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    retries: int = 0


@dataclass
class WorkerConfig:
    max_workers: int = 3
    max_gpu_workers: int = 1
    max_memory_gb: float = 8.0
    max_retries: int = 2
    retry_delay: int = 30


class ResourceTracker:
    """Tracks available GPU/CPU/memory resources."""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.gpu_in_use = 0
        self.memory_used_gb = 0.0
        self.active_workers = 0
    
    def can_acquire(self, needs_gpu: bool = False, memory_gb: float = 0.0) -> bool:
        if self.active_workers >= self.config.max_workers:
            return False
        if needs_gpu and self.gpu_in_use >= self.config.max_gpu_workers:
            return False
        if self.memory_used_gb + memory_gb > self.config.max_memory_gb:
            return False
        return True
    
    def acquire(self, needs_gpu: bool = False, memory_gb: float = 0.0):
        self.active_workers += 1
        if needs_gpu:
            self.gpu_in_use += 1
        self.memory_used_gb += memory_gb
    
    def release(self, needs_gpu: bool = False, memory_gb: float = 0.0):
        self.active_workers = max(0, self.active_workers - 1)
        if needs_gpu:
            self.gpu_in_use = max(0, self.gpu_in_use - 1)
        self.memory_used_gb = max(0.0, self.memory_used_gb - memory_gb)


class SprintOrchestrator:
    def __init__(self, sprints: List[Sprint], config: WorkerConfig):
        self.sprints = {s.task_id: s for s in sprints}
        self.config = config
        self.resources = ResourceTracker(config)
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.results: Dict[str, Dict] = {}
    
    def can_run(self, sprint: Sprint) -> bool:
        """Check if sprint's dependencies are satisfied."""
        for dep in sprint.depends_on:
            if dep not in self.completed:
                return False
        return True
    
    def get_runnable(self) -> List[Sprint]:
        """Get all sprints that can run now."""
        return [
            s for s in self.sprints.values()
            if s.status == SprintStatus.PENDING and self.can_run(s)
        ]
    
    def run_sprint(self, sprint: Sprint, dry_run: bool = False) -> bool:
        """Execute a single sprint."""
        sprint.status = SprintStatus.RUNNING
        sprint.start_time = datetime.now()
        
        print(f"🚀 Starting sprint: {sprint.task_id} ({sprint.summary})")
        
        if dry_run:
            print(f"   [DRY RUN] Would execute sprint {sprint.task_id}")
            time.sleep(0.1)  # Simulate quick work
            sprint.status = SprintStatus.SUCCESS
            sprint.end_time = datetime.now()
            self.completed.add(sprint.task_id)
            return True
        
        # Actual execution would go here
        # For now, just simulate success
        try:
            # Execute the sprint's plan
            # This would call the autonomous executor or similar
            time.sleep(0.5)  # Simulate work
            sprint.status = SprintStatus.SUCCESS
            sprint.end_time = datetime.now()
            self.completed.add(sprint.task_id)
            print(f"✅ Sprint {sprint.task_id} completed successfully")
            return True
        except Exception as e:
            sprint.status = SprintStatus.FAILED
            sprint.end_time = datetime.now()
            sprint.error = str(e)
            self.failed.add(sprint.task_id)
            print(f"❌ Sprint {sprint.task_id} failed: {e}")
            return False
    
    def execute(self, dry_run: bool = False) -> bool:
        """Execute all sprints in dependency order."""
        print(f"🎭 Starting orchestration with {len(self.sprints)} sprints")
        print(f"   Max workers: {self.config.max_workers}")
        print(f"   Max GPU workers: {self.config.max_gpu_workers}")
        print(f"   Max memory: {self.config.max_memory_gb}GB")
        print(f"   Dry run: {dry_run}")
        print()
        
        total_start = time.time()
        
        while True:
            runnable = self.get_runnable()
            
            if not runnable:
                # Check if all done
                pending = [s for s in self.sprints.values() if s.status == SprintStatus.PENDING]
                if not pending:
                    break
                # Wait for running sprints to complete
                print("   ⏳ Waiting for running sprints...")
                time.sleep(1)
                continue
            
            # Execute runnable sprints in parallel (up to max_workers)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {executor.submit(self.run_sprint, s, dry_run): s for s in runnable[:self.config.max_workers]}
                
                for future in concurrent.futures.as_completed(futures):
                    sprint = futures[future]
                    try:
                        success = future.result()
                        if not success and sprint.retries < self.config.max_retries:
                            sprint.retries += 1
                            sprint.status = SprintStatus.PENDING
                            print(f"   🔄 Retrying {sprint.task_id} (attempt {sprint.retries + 1})")
                    except Exception as e:
                        print(f"❌ Sprint {sprint.task_id} error: {e}")
                        sprint.status = SprintStatus.FAILED
                        sprint.error = str(e)
                        self.failed.add(sprint.task_id)
        
        total_time = time.time() - total_start
        
        # Summary
        print("\n" + "="*50)
        print("🎯 ORCHESTRATION COMPLETE")
        print("="*50)
        print(f"Total time: {total_time:.1f}s")
        print(f"Completed: {len(self.completed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"Skipped: {len([s for s in self.sprints.values() if s.status == SprintStatus.SKIPPED])}")
        
        if self.failed:
            print("\n❌ Failed sprints:")
            for fid in self.failed:
                sprint = self.sprints[fid]
                print(f"  - {fid}: {sprint.error}")
            return False
        
        print("\n✅ All sprints completed successfully!")
        return True


def load_sprints_from_yaml(file_path: Path) -> List[Sprint]:
    """Load sprints from YAML file."""
    with open(file_path) as f:
        data = yaml.safe_load(f)
    
    sprints = []
    if isinstance(data, list):
        for item in data:
            sprint = Sprint(
                task_id=item.get('task_id', ''),
                summary=item.get('summary', ''),
                depends_on=item.get('depends_on', []),
                parallel_group=item.get('parallel_group')
            )
            sprints.append(sprint)
    return sprints


def main():
    parser = argparse.ArgumentParser(description="Sprint Orchestrator - Parallel sprint execution")
    parser.add_argument('--sprints-file', type=Path, required=True, help="Path to SPRINTS.md")
    parser.add_argument('--workers', type=int, default=3, help="Max parallel workers")
    parser.add_argument('--gpu-workers', type=int, default=1, help="Max GPU workers")
    parser.add_argument('--memory', type=float, default=8.0, help="Max memory GB")
    parser.add_argument('--dry-run', action='store_true', help="Simulate execution without running")
    parser.add_argument('--retries', type=int, default=2, help="Max retries per sprint")
    parser.add_argument('--retry-delay', type=int, default=30, help="Retry delay in seconds")
    args = parser.parse_args()
    
    # Load sprints
    sprints = load_sprints_from_yaml(args.sprints_file)
    if not sprints:
        print("❌ No sprints found in file")
        sys.exit(1)
    
    # Build dependency graph to validate
    graph = DependencyGraph()
    for sprint in sprints:
        graph.add_sprint(sprint)
    
    errors = graph.validate_dependencies()
    if errors:
        print("❌ Dependency errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    
    has_cycle, cycle = graph.has_cycle()
    if has_cycle:
        print(f"❌ Cycle detected: {' -> '.join(cycle)}")
        sys.exit(1)
    
    print("✅ Dependency graph validated")
    
    # Create config
    config = WorkerConfig(
        max_workers=args.workers,
        max_gpu_workers=args.gpu_workers,
        max_memory_gb=args.memory,
        max_retries=args.retries,
        retry_delay=args.retry_delay
    )
    
    # Execute
    orchestrator = SprintOrchestrator(sprints, config)
    success = orchestrator.execute(dry_run=args.dry_run)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    import yaml
    from dependency_graph import DependencyGraph
    main()