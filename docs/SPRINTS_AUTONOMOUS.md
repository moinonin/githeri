# Sprint 11 - Sprint Orchestrator

## Overview
This sprint implements the SprintOrchestrator skill that enables parallel execution of sprint tasks with proper dependency resolution and resource management.

## Key Components
- **DependencyGraph**: Builds and validates dependency graphs from sprint specs
- **WorkerPool**: Manages parallel execution with resource tracking
- **SprintOrchestrator**: Coordinates graph analysis and parallel execution
- **SKILL.md**: Documentation for the skill
- **SKILL.md**: Documentation for the skill

## How It Works
1. **Graph Construction**: Parses sprint spec YAML to build a dependency graph
2. **Cycle Detection**: Identifies circular dependencies before execution
3. **Parallel Grouping**: Uses topological sorting to group tasks by parallel execution capability
4. **Worker Pool**: Manages parallel execution with resource constraints
5. **Execution**: Runs tasks in parallel groups while respecting resource limits

## Usage
### Command Line
```bash
# Execute sprint 11
make -f Makefile.sprints sprint-execute SPRINT=sprint11
```

### Test Prompt Example
```bash
# Test prompt from prompt_generator.py
python3 run_autonomous.py --prompt "Implement a background job that recalculates confidence scores for pending verification sessions every five minutes. Skip completed sessions and log processing statistics. Include unit tests covering successful recalculation and failure scenarios."
```

### Verification Gates
- **L1**: SprintOrchestrator implementation exists
- **L2**: Dependency graph with cycle detection and parallel groups
- **L3**: Worker pool with resource management
- **L4**: SPRINTS.md contains depends_on and parallel_group syntax
- **L5**: Orchestrator runs sprints in parallel with correct dependencies
- **L6**: Full orchestration with failure handling and retry logic

### Verification Command
```bash
make -f Makefile.sprints orchestrate SPRINTS=test_sprints.md --dry-run
```

### Expected Output
```
Parallel groups: 3
  Group 1: task1
  Group 2: task2, task3
  Group 4: task4
```

### Error Handling
- Circular dependencies cause immediate failure with clear error message
- Worker pool respects max_workers limit
- All tasks must complete successfully for success status