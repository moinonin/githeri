# Test SPRINTS.md for orchestrator validation

## test-sprint-a
- task_id: test-sprint-a
- summary: "Test sprint A - no dependencies"
- depends_on: []
- local_goals:
  - id: L1
    description: "CREATE: Test file A"
    verification:
      type: file_exists
      path: test_output_a.txt
- parallel_group: "group-1"

## test-sprint-b
- task_id: test-sprint-b
- summary: "Test sprint B - no dependencies"
- depends_on: []
- local_goals:
  - id: L1
    description: "CREATE: Test file B"
    verification:
      type: file_exists
      path: test_output_b.txt
- parallel_group: "group-1"

## test-sprint-c
- task_id: test-sprint-c
- summary: "Test sprint C - depends on A and B"
- depends_on: ["test-sprint-a", "test-sprint-b"]
- local_goals:
  - id: L1
    description: "CREATE: Test file C"
    verification:
      type: file_exists
      path: test_output_c.txt
- parallel_group: "group-2"

## test-sprint-d
- task_id: test-sprint-d
- summary: "Test sprint D - depends on C"
- depends_on: ["test-sprint-c"]
- local_goals:
  - id: L1
    description: "CREATE: Test file D"
    verification:
      type: file_exists
      path: test_output_d.txt
- parallel_group: "group-3"