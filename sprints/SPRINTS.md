# Example SPRINTS.md - Sprint definitions with dependencies

# Backend sprints
- task_id: "sprint-1-core-models"
  summary: "Core data models and database schema"
  depends_on: []
  parallel_group: "backend"

- task_id: "sprint-2-auth"
  summary: "Authentication and authorization system"
  depends_on: ["sprint-1-core-models"]
  parallel_group: "backend"

- task_id: "sprint-3-api"
  summary: "REST API layer with validation"
  depends_on: ["sprint-1-core-models", "sprint-2-auth"]
  parallel_group: "backend"

- task_id: "sprint-4-ml"
  summary: "ML pipeline integration"
  depends_on: ["sprint-1-core-models"]
  parallel_group: "ml"

# Frontend sprints
- task_id: "sprint-5-ui-components"
  summary: "React component library"
  depends_on: []
  parallel_group: "frontend"

- task_id: "sprint-6-dashboard"
  summary: "Admin dashboard with charts"
  depends_on: ["sprint-5-ui-components", "sprint-3-api"]
  parallel_group: "frontend"

- task_id: "sprint-7-ml-ui"
  summary: "ML model monitoring UI"
  depends_on: ["sprint-5-ui-components", "sprint-4-ml"]
  parallel_group: "frontend"

# Integration
- task_id: "sprint-8-e2e-tests"
  summary: "End-to-end test suite"
  depends_on: ["sprint-6-dashboard", "sprint-7-ml-ui"]
  parallel_group: "integration"

- task_id: "sprint-9-deploy"
  summary: "Production deployment pipeline"
  depends_on: ["sprint-8-e2e-tests"]
  parallel_group: "integration"