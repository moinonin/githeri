#!/usr/bin/env python3
"""
DependencyGraph — builds a DAG from sprint specs, detects cycles,
and computes parallel execution groups via topological sort.
"""

from collections import defaultdict, deque
import sys
import json

def build_graph(spec_path: str) -> dict:
    """
    Parse sprint spec YAML and build a directed graph.
    Returns dict mapping node -> list of dependencies.
    """
    import yaml
    try:
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR parsing spec: {e}", file=sys.stderr)
        return {}

    graph = defaultdict(list)
    for node in spec.get('tasks', []):
        node_name = node['name']
        for dep in node.get('depends_on', []):
            graph[node_name].append(dep)
    return graph

def detect_cycles(graph: dict) -> list:
    """
    Detect cycles in the dependency graph.
    Returns list of cycles (each cycle is a list of nodes).
    """
    visited = set()
    rec_stack = set()
    cycles = []
    
    # Get all nodes (including dependencies that aren't keys in the graph)
    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)

    def dfs(node, path):
        if node in rec_stack:
            # Found cycle
            idx = path.index(node)
            cycle = path[idx:] + [node]
            cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            dfs(neighbor, path + [node])
        rec_stack.remove(node)

    for node in all_nodes:
        if node not in visited:
            dfs(node, [])
    return cycles

def get_parallel_groups(graph: dict) -> list:
    """
    Compute parallel execution groups using topological sort.
    Returns list of groups (each group is a list of nodes).
    """
    # Get all nodes (including dependencies that aren't keys in the graph)
    all_nodes = set(graph.keys())
    for deps in graph.values():
        all_nodes.update(deps)
    
    in_degree = {node: 0 for node in all_nodes}
    for node in graph:
        for dep in graph[node]:
            in_degree[dep] += 1

    queue = deque([node for node in all_nodes if in_degree[node] == 0])
    topo_order = []
    
    # Also track the depth of each node
    depth = {node: 0 for node in all_nodes}
    
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            depth[neighbor] = max(depth[neighbor], depth[node] + 1)
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Group by depth in topological order
    groups = {}
    for node in topo_order:
        d = depth[node]
        if d not in groups:
            groups[d] = []
        groups[d].append(node)
    
    return [groups[d] for d in sorted(groups.keys())]

def main():
    if len(sys.argv) != 2:
        print("Usage: python dependency_graph.py <spec_path>", file=sys.stderr)
        sys.exit(1)

    spec_path = sys.argv[1]
    graph = build_graph(spec_path)
    
    # Detect cycles
    cycles = detect_cycles(graph)
    if cycles:
        print(f"ERROR: {len(cycles)} circular dependency(s) detected:")
        for i, cycle in enumerate(cycles):
            print(f"  Cycle {i+1}: {' -> '.join(cycle)}")
        sys.exit(1)
    
    # Get parallel groups
    groups = get_parallel_groups(graph)
    print(f"Parallel groups: {len(groups)}")
    for i, group in enumerate(groups):
        print(f"  Group {i+1}: {', '.join(group)}")

if __name__ == "__main__":
    main()