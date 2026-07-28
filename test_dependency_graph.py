#!/usr/bin/env python3

import sys
import os

# Add the skill path to Python path
sys.path.insert(0, '/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/skills/software-development/sprint-orchestrator/scripts')

# Import the modules
from dependency_graph import build_graph, detect_cycles, get_parallel_groups

# Create a simple test graph manually
test_graph = {
    'task1': ['task2', 'task3'],
    'task2': ['task4'],
    'task3': ['task4'],
    'task4': []
}

print("Testing dependency_graph functions...")

# Test build_graph (we'll simulate by using our manual graph)
graph = build_graph('/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/sprints/test_sprint11.spec.yaml')
print("Graph built from spec")

# Test cycle detection
cycles = detect_cycles(graph)
print(f"Cycles detected: {cycles}")

# Test parallel groups
groups = get_parallel_groups(graph)
print(f"Parallel groups: {len(groups)} groups")
for i, group in enumerate(groups):
    print(f"  Group {i+1}: {group}")

print("All tests completed successfully!")