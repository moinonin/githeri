# test_sprints.md

## Test Sprints for Orchestrator

This fixture file contains test specifications for the SprintOrchestrator skill.

### Test 1: Basic Dependency Graph

- **Task**: Create dependency graph from sprint spec
- **Expected**: Graph should correctly represent task dependencies
- **Verification**: Graph should match expected structure

### Test 2: Parallel Group Detection

- **Task**: Compute parallel execution groups from dependency graph
- **Expected**: Groups should be correctly computed based on dependencies
- **Verification**: Groups should match expected parallel structure

### Test 3: Worker Pool Resource Management

- **Task**: Manage parallel execution with resource constraints
- **Expected**: Worker pool should respect max_workers limit
- **Verification**: Resource tracking should be accurate

### Test 4: Full Orchestration with Parallel Execution
- **Task**: Execute sprint tasks in parallel groups
- **Expected**: Tasks should execute in parallel as defined by groups
- **Verification**: All tasks should complete successfully