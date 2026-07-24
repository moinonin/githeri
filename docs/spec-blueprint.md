Human:
"Users should be able to update their display name and bio."
        │
        ▼
Spec-Forge (LLM + validator)
Generates:
    executable-spec.yaml
        │
        ▼
Human Review
"L1-L8 look good. Approve."
        │
        ▼
COMMAND_RUNWAY Skill
Consumes:
    executable-spec.yaml

Produces:
    COMMAND_RUNWAY.md
        • ordered implementation plan
        • exact file paths
        • code modifications
        • test skeletons
        • verification commands
        • rollback guidance
        • completion criteria
        │
        ▼
Executor
(Fine-tuned Qwen2.5-Coder 14B)

Reads:
    COMMAND_RUNWAY.md

For each command:
    ✓ modify code
    ✓ create/update tests
    ✓ execute verification commands
    ✓ record results
    ✓ continue automatically
    ✓ request human assistance only when blocked
        │
        ▼
Completed Feature

Outputs:
    ✓ implementation complete
    ✓ all tests passing
    ✓ OpenAPI updated
    ✓ documentation synchronized
    ✓ human notified
