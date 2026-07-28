# sprint-orchestrator

**Trigger condition**: When you need to execute a sprint that requires parallel task execution with proper grouping and resource management.

**One-line behavior**: Use the `SprintOrchestrator` class to execute sprint tasks in parallel groups based on dependency graph analysis.

**Detailed description**:
The SprintOrchestrator skill enables parallel execution of sprint tasks by:
1. Building a dependency graph from the sprint spec
2. Detecting circular dependencies
3. Computing parallel execution groups via topological sorting
4. Managing a worker pool with resource tracking
5. Executing tasks in parallel groups while respecting resource constraints

**Steps to use**:
1. Create a sprint spec YAML file with proper `depends_on` syntax
2. Run `python -m sprint_orchestrator <spec_path>` to execute
3. Monitor execution through the worker pool stats

**Example**:
```bash
python -m sprint_orchestrator /Users/nickrotich/.../sprint11.spec.yaml --workers 2
```

**Pitfalls**:
- Circular dependencies will cause execution to fail
- Insufficient worker resources may cause timeouts
- Tasks must be properly defined in the spec with `name` and `depends_on` fields

**Related skills**: dependency_graph, worker_pool, command-runway-autonomous