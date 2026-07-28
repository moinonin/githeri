#!/usr/bin/env python3
"""
Simple test to verify SprintOrchestrator works
"""

import sys
import os

# Add the skill directory to path
sys.path.insert(0, '/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/skills/software-development/sprint-orchestrator/scripts')

# Import the classes
from orchestrator import SprintOrchestrator
from dependency_graph import build_graph, detect_cycles, get_parallel_groups
from worker_pool import WorkerPool

# Create a simple test
if __name__ == "__main__":
    print("Creating test orchestrator...")
    orchestrator = SprintOrchestrator("/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/sprints/test_sprint11.spec.yaml")
    
    print("Building graph...")
    orchestrator.build_graph()
    print("Graph built successfully")
    
    print("Detecting cycles...")
    try:
        orchestrator.detect_cycles()
        print("No cycles detected - good!")
    except RuntimeError as e:
        print(f"Cycle detected: {e}")
    
    print("Computing parallel groups...")
    orchestrator.compute_parallel_groups()
    print(f"Parallel groups: {orchestrator.parallel_groups}")
    
    print("Executing...")
    orchestrator.execute()
    print("Execution complete!")