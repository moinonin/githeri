#!/usr/bin/env python3
"""
Dependency Graph Builder - Parses SPRINTS.md, builds DAG, detects cycles, topological sort.
"""

import argparse
import sys
import yaml
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Set, Optional, Tuple


class Sprint:
    def __init__(self, task_id: str, summary: str, depends_on: List[str], parallel_group: Optional[str] = None):
        self.task_id = task_id
        self.summary = summary
        self.depends_on = depends_on
        self.parallel_group = parallel_group


class DependencyGraph:
    def __init__(self):
        self.nodes: Dict[str, Sprint] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)  # node -> set of dependencies
        self.reverse_edges: Dict[str, Set[str]] = defaultdict(set)  # node -> set of dependents
    
    def add_sprint(self, sprint: Sprint):
        self.nodes[sprint.task_id] = sprint
        for dep in sprint.depends_on:
            self.edges[sprint.task_id].add(dep)
            self.reverse_edges[dep].add(sprint.task_id)
    
    def has_cycle(self) -> Tuple[bool, List[str]]:
        """Detect cycles using DFS. Returns (has_cycle, cycle_path)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.nodes}
        parent = {}
        
        def dfs(node: str) -> Optional[List[str]]:
            color[node] = GRAY
            for dep in self.edges[node]:
                if dep not in self.nodes:
                    continue  # Skip missing dependencies
                if color[dep] == WHITE:
                    parent[dep] = node
                    cycle = dfs(dep)
                    if cycle:
                        return cycle
                elif color[dep] == GRAY:
                    # Found cycle
                    cycle = [node, dep]
                    while cycle[-1] != dep:
                        cycle.append(parent[cycle[-1]])
                    return list(reversed(cycle))
            color[node] = BLACK
            return None
        
        for node in self.nodes:
            if color[node] == WHITE:
                cycle = dfs(node)
                if cycle:
                    return True, cycle
        return False, []
    
    def topological_sort(self) -> List[str]:
        """Kahn's algorithm for topological sorting."""
        in_degree = defaultdict(int)
        for node in self.nodes:
            for dep in self.edges[node]:
                if dep in self.nodes:
                    in_degree[dep] += 1
        
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self.reverse_edges[node]:
                if dependent in self.nodes:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        if len(result) != len(self.nodes):
            # Cycle detected
            raise ValueError("Graph has cycles, cannot topologically sort")
        
        return result
    
    def get_parallel_groups(self, topo_order: List[str]) -> List[List[str]]:
        """Group nodes by parallel execution level (all nodes at same level can run in parallel)."""
        # Compute level for each node (longest path from any root)
        levels = {}
        for node in topo_order:
            if not self.edges[node]:
                levels[node] = 0
            else:
                max_dep_level = max(levels.get(dep, 0) for dep in self.edges[node] if dep in levels)
                levels[node] = max_dep_level + 1
        
        # Group by level
        max_level = max(levels.values()) if levels else 0
        groups = [[] for _ in range(max_level + 1)]
        for node, level in levels.items():
            groups[level].append(node)
        
        return groups
    
    def validate_dependencies(self) -> List[str]:
        """Check that all dependencies exist."""
        errors = []
        for node, sprint in self.nodes.items():
            for dep in sprint.depends_on:
                if dep not in self.nodes:
                    errors.append(f"{node}: depends on missing sprint '{dep}'")
        return errors


def load_sprints(file_path: Path) -> List[Sprint]:
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
    parser = argparse.ArgumentParser(description="Build dependency graph from SPRINTS.md")
    parser.add_argument('--sprints-file', type=Path, required=True, help="Path to SPRINTS.md")
    parser.add_argument('--check-only', action='store_true', help="Only validate, don't output graph")
    parser.add_argument('--output', type=Path, help="Output file for graph visualization")
    args = parser.parse_args()
    
    # Load sprints
    sprints = load_sprints(args.sprints_file)
    if not sprints:
        print("❌ No sprints found in file")
        sys.exit(1)
    
    # Build graph
    graph = DependencyGraph()
    for sprint in sprints:
        graph.add_sprint(sprint)
    
    # Validate dependencies
    errors = graph.validate_dependencies()
    if errors:
        print("❌ Dependency errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    
    # Check for cycles
    has_cycle, cycle = graph.has_cycle()
    if has_cycle:
        print(f"❌ Cycle detected: {' -> '.join(cycle)}")
        sys.exit(1)
    
    if args.check_only:
        print("✅ Dependency graph is valid (DAG)")
        return
    
    # Topological sort
    topo_order = graph.topological_sort()
    print(f"✅ Valid DAG with {len(topo_order)} sprints")
    print(f"Topological order: {' -> '.join(topo_order)}")
    
    # Parallel groups
    groups = graph.get_parallel_groups(topo_order)
    print(f"\nParallel execution groups ({len(groups)} levels):")
    for i, group in enumerate(groups):
        print(f"  Level {i}: {', '.join(group)}")
    
    if args.output:
        # Output graphviz DOT format
        dot = "digraph G {\n"
        for node in graph.nodes:
            for dep in graph.edges[node]:
                if dep in graph.nodes:
                    dot += f'  "{dep}" -> "{node}";\n'
        dot += "}"
        args.output.write_text(dot)
        print(f"\nGraph written to {args.output}")


if __name__ == '__main__':
    main()