#!/usr/bin/env python3
"""
Sprint Orchestrator - Main entry point for running multiple sprints in parallel.

This is the main CLI entry point that ties together:
- Dependency graph validation
- Parallel worker pool execution
- Resource tracking
- Progress reporting
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import List, Optional

# Import our modules
sys.path.insert(0, str(Path(__file__).parent))

from dependency_graph import DependencyGraph, Sprint
from worker_pool import SprintOrchestrator, Sprint, WorkerConfig


def load_sprints(file_path: Path) -> List[Sprint]:
    """Load sprints from YAML file."""
    if not file_path.exists():
        print(f"❌ Sprints file not found: {file_path}")
        sys.exit(1)
    
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


def validate_sprints(sprints: List[Sprint]) -> bool:
    """Validate sprint dependencies and check for cycles."""
    graph = DependencyGraph()
    for sprint in sprints:
        graph.add_sprint(sprint)
    
    # Check dependencies
    errors = graph.validate_dependencies()
    if errors:
        print("❌ Dependency errors:")
        for err in errors:
            print(f"  - {err}")
        return False
    
    # Check cycles
    has_cycle, cycle = graph.has_cycle()
    if has_cycle:
        print(f"❌ Cycle detected: {' -> '.join(cycle)}")
        return False
    
    return True


def print_execution_plan(sprints: List[Sprint]):
    """Print the execution plan with parallel levels."""
    graph = DependencyGraph()
    for sprint in sprints:
        graph.add_sprint(sprint)
    
    topo_order = graph.topological_sort()
    groups = graph.get_parallel_groups(topo_order)
    
    print(f"\n📋 Execution Plan ({len(sprints)} sprints, {len(groups)} levels):")
    for i, group in enumerate(groups):
        print(f"  Level {i}: {', '.join(group)}")


def main():
    parser = argparse.ArgumentParser(description="Sprint Orchestrator - Parallel sprint execution")
    parser.add_argument('--sprints-file', type=Path, required=True, help="Path to sprints YAML file")
    parser.add_argument('--workers', type=int, default=3, help="Max parallel workers")
    parser.add_argument('--gpu-workers', type=int, default=1, help="Max GPU workers")
    parser.add_argument('--memory', type=float, default=8.0, help="Max memory GB")
    parser.add_argument('--dry-run', action='store_true', help="Show execution plan only")
    parser.add_argument('--verbose', action='store_true', help="Verbose output")
    parser.add_argument('--retries', type=int, default=2, help="Max retries per sprint")
    parser.add_argument('--retry-delay', type=int, default=30, help="Retry delay in seconds")
    args = parser.parse_args()
    
    # Load sprints
    sprints = load_sprints(args.sprints_file)
    if not sprints:
        print("❌ No sprints found in file")
        sys.exit(1)
    
    print(f"📦 Loaded {len(sprints)} sprints from {args.sprints_file}")
    
    # Validate
    if not validate_sprints(sprints):
        sys.exit(1)
    
    print("✅ Dependency graph validated")
    
    # Print execution plan
    print_execution_plan(sprints)
    
    if args.dry_run:
        print("\n🏁 Dry run complete - no sprints executed")
        return
    
    # Configure worker
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
    main()