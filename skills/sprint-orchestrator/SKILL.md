---
name: sprint-orchestrator
description: "Parallel sprint execution engine with dependency resolution, resource tracking, and failure handling."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sprint, orchestration, parallel, dependency-resolution, resource-management]
    related_skills: [command-runway-pattern, command-runway-autonomous, spec-forge, ci-cd-integration]
---

# Sprint Orchestrator

## What This Is

A production-grade sprint orchestration engine that:
1. **Resolves dependencies** - Topological sort with cycle detection
2. **Executes in parallel** - Worker pool with configurable concurrency
3. **Manages resources** - GPU, memory, and worker slot tracking
4. **Handles failures** - Automatic retries with exponential backoff
5. **Reports progress** - Real-time status updates and execution plans

## When To Use This Skill

Use Sprint Orchestrator when:
- You have multiple features/sprints that can run in parallel
- Sprints have explicit dependencies on each other
- You want to maximize CI/CD throughput
- You need failure isolation and retry logic

Do NOT use when:
- All sprints are strictly sequential (no parallelism possible)
- You have circular dependencies (must fix architecture first)
- You only have 1-2 sprints (overhead not worth it)

## Installation

```bash
cp -r skills/software-development/sprint-orchestrator ~/.hermes/skills/sprint-orchestrator
```

## Usage

### From CLI

```bash
# Dry run - show execution plan only
python .hermes/skills/software-development/sprint-orchestrator/scripts/orchestrator.py \
  --sprints-file SPRINTS.md --dry-run

# Execute with 4 workers
python .hermes/skills/software-development/sprint-orchestrator/scripts/orchestrator.py \
  --sprints-file SPRINTS.md --workers 4

# Execute with GPU workers
python .hermes/skills/software-development/sprint-orchestrator/scripts/orchestrator.py \
  --sprints-file SPRINTS.md --workers 4 --gpu-workers 2 --memory 16
```

### From Makefile

```bash
# Dry run
make orchestrate SPRINTS=SPRINTS.md --dry-run

# Execute with 4 workers
make orchestrate SPRINTS=SPRINTS.md WORKERS=4

# Execute with verbose output
make orchestrate SPRINTS=SPRINTS.md WORKERS=4 VERBOSE=1
```

## SPRINTS.md Format

```yaml
- task_id: "feature-auth"
  summary: "Add authentication endpoints"
  depends_on: []
  parallel_group: "backend"

- task_id: "feature-api"
  summary: "Build REST API layer"
  depends_on: ["feature-auth"]
  parallel_group: "backend"

- task_id: "feature-ui"
  summary: "Build React UI components"
  depends_on: []
  parallel_group: "frontend"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `task_id` | Yes | Unique identifier (kebab-case) |
| `summary` | Yes | Human-readable description |
| `depends_on` | No | List of task_ids this sprint depends on |
| `parallel_group` | No | Group name for resource allocation hints |

## Architecture

### Dependency Resolution

1. **Graph Construction** - Build DAG from `depends_on` relationships
2. **Cycle Detection** - Fail fast if cycles detected
3. **Topological Sort** - Determine execution order
4. **Parallel Grouping** - Group by level for max parallelism

### Resource Management

| Resource | Config | Tracking |
|----------|--------|----------|
| Workers | `--workers` | Active thread count |
| GPU | `--gpu-workers` | GPU slot allocation |
| Memory | `--memory` GB | Memory budget per worker |

### Failure Handling

1. **Retry Logic** - Up to `--retries` attempts with `--retry-delay` backoff
2. **Failure Isolation** - Failed sprints don't block unrelated sprints
3. **Dependency Blocking** - Dependent sprints skip if dependency fails

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_workers` | 3 | Max concurrent sprints |
| `max_gpu_workers` | 1 | Max concurrent GPU-using sprints |
| `max_memory_gb` | 8.0 | Memory budget |
| `max_retries` | 2 | Retry attempts per sprint |
| `retry_delay` | 30s | Delay between retries |

## Integration Points

### Command-Runway Integration

Sprints can reference Command-Runway specs:

```yaml
- task_id: "sprint-5-auth"
  summary: "Implement authentication"
  depends_on: ["sprint-4-core-models"]
```

### CI/CD Integration

```yaml
# .github/workflows/sprints.yml
jobs:
  sprints:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run sprints
        run: make orchestrate SPRINTS=SPRINTS.md WORKERS=4
```

## Output

### Execution Plan (Dry Run)

```
📋 Execution Plan (5 sprints, 3 levels):
  Level 0: sprint-1, sprint-2
  Level 1: sprint-3
  Level 2: sprint-4, sprint-5
```

### Execution Output

```
🎭 Starting orchestration with 5 sprints
   Max workers: 3
   Max GPU workers: 1
   Max memory: 8.0GB
   Dry run: False

📦 Phase 0: sprint-1, sprint-2
🚀 Starting sprint: sprint-1 (Add authentication)
✅ Sprint sprint-1 completed successfully
🚀 Starting sprint: sprint-2 (Build database schema)
✅ Sprint sprint-2 completed successfully

📦 Phase 1: sprint-3
...

🎯 ORCHESTRATION COMPLETE
Total time: 45.2s
Completed: 5
Failed: 0
Skipped: 0

✅ All sprints completed successfully!
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Cycle detected | Exit with error, show cycle |
| Missing dependency | Exit with error |
| Sprint failure | Retry up to `--retries` times |
| Max retries exceeded | Mark failed, continue others |
| Dependency failed | Skip dependent sprints |

## Files

```
sprint-orchestrator/
├── SKILL.md
├── scripts/
│   ├── orchestrator.py      # Main CLI entry point
│   ├── dependency_graph.py  # DAG operations
│   └── worker_pool.py       # Parallel execution
└── templates/
    └── SPRINTS.md.example   # Example sprint file
```