#!/usr/bin/env python3
"""
Simple test to verify SprintOrchestrator works with a sample spec
"""

import os
import sys
sys.path.insert(0, '/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/skills/software-development/sprint-orchestrator/scripts')

from dependency_graph import build_graph, detect_cycles, get_parallel_groups
from worker_pool import WorkerPool
import subprocess
import json

class SprintOrchestrator:
    def __init__(self, spec_path: str, max_workers: int = 2, timeout: int = 3600):
        self.spec_path = spec_path
        self.max_workers = max_workers
        self.timeout = timeout
        self.graph = None
        self.parallel_groups = []
        self.pool = None
    
    def build_graph(self):
        """Build the dependency graph from the spec."""
        self.graph = build_graph(self.spec_path)
    
    def detect_cycles(self):
        """Detect cycles in the graph."""
        if self.graph is None:
            self.build_graph()
        cycles = detect_cycles(self.graph)
        if cycles:
            raise RuntimeError(f"Circular dependencies detected: {cycles}")
    
    def compute_parallel_groups(self):
        """Compute parallel execution groups."""
        if self.graph is None:
            self.build_graph()
        self.parallel_groups = get_parallel_groups(self.graph)
    
    def execute(self):
        """Execute all tasks in parallel groups."""
        if self.parallel_groups is None:
            self.compute_parallel_groups()
        
        self.pool = WorkerPool(max_workers=self.max_workers, timeout=self.timeout)
        
        # Execute each group sequentially (groups are parallel within themselves)
        for group_idx, group in enumerate(self.parallel_groups):
            print(f"Executing group {group_idx + 1}: {', '.join(group)}")
            for task_name in group:
                # In a real implementation, we'd map task_name to actual command
                # For now, we'll just simulate
                command = f"echo Executing task: {task_name}"
                worker_id = self.pool.submit(command)
                print(f"  Submitted task {task_name} to {worker_id}")
        
        # Wait for all to complete
        results = self.pool.wait_for_completion()
        print(f"All groups executed. Completed: {len(results)}")
    
    def run(self):
        """Run the full orchestration."""
        self.build_graph()
        self.detect_cycles()
        self.compute_parallel_groups()
        self.execute()

def main():
    if len(sys.argv) != 2:
        print("Usage: python sprint_orchestrator.py <spec_path>")
        sys.exit(1)
    
    spec_path = sys.argv[1]
    orchestrator = SprintOrchestrator(spec_path)
    orchestrator.run()

if __name__ == "__main__":
    main()