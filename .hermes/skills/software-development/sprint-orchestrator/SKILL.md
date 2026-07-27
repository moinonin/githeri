---
name: sprint-orchestrator
description: "Sprint orchestrator for parallel feature execution with dependency resolution"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestrator, parallel, sprint, dag, dependency-resolution]
    related_skills: [ci-cd-integration, observability, spec-forge, command-runway-pattern]
---

# Sprint Orchestrator

## What This Is

A sprint execution orchestrator that:
1. **Parses SPRINTS.md** - Reads sprint definitions with dependencies
2. **Builds DAG** - Resolves dependency graph, detects cycles
3. **Parallel Execution** - Runs independent sprints concurrently
4. **Resource Management** - Controls GPU/CPU workers, memory limits
5. **Progress Tracking** - Reports status, handles failures, retries

## When To Use

- Running multiple sprints with dependencies
- CI/CD pipelines with parallel stages
- Resource-constrained environments (GPU limits)
- Complex multi-sprint workflows

## Installation

```bash
cp -r skills/software-development/sprint-orchestrator ~/.hermes/skills/sprint-orchestrator
```

## Usage

### Build Dependency Graph

```bash
python skills/software-development/sprint-orchestrator/scripts/dependency_graph.py \
  --sprits-file SPRINTS.md
```

### Run Orchestrator

```bash
python skills/software-development/sprint-orchestrator/scripts/orchestrator.py \
  --sprits-file SPRINTS.md \
  --workers 3 \
  --dry-run
```

### Check Dependencies

```bash
python skills/software-development/sprint-orchestrator/scripts/dependency_graph.py \
  --sprits-file SPRINTS.md \
  --check-only
```

## SPRINTS.md Format

```yaml
# Each sprint is a YAML document
# task_id: unique identifier
# depends_on: list of task_ids this sprint depends on
# parallel_group: optional group for explicit parallelism hints
```

Example:
```yaml
- task_id: sprint-a
  summary: "Foundation sprint"
  depends_on: []
  parallel_group: "group-1"

- task_id: sprint-b
  summary: "Parallel sprint"
  depends_on: []
  parallel_group: "group-1"

- task_id: sprint-c
  summary: "Depends on A and B"
  depends_on: ["sprint-a", "sprint-b"]
  parallel_group: "group-2"
```

## Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `python orchestrator.py --help` | Exits 0 |
| L2 | `python dependency_graph.py --sprits-file test.md --check-only` | No cycles, valid DAG |
| L3 | `python orchestrator.py --sprits-file test.md --dry-run --workers 3` | Parallel execution plan |
| L4 | `python dependency_graph.py --sprits-file SPRINTS.md` | Correct dependency resolution |

## Scripts

| Script | Purpose |
|--------|---------|
| `orchestrator.py` | Main orchestration engine |
| `dependency_graph.py` | DAG builder, cycle detection, topological sort |
| `worker_pool.py` | Parallel worker management with resource limits |
| `resource_manager.py` | GPU/CPU/memory allocation and tracking |