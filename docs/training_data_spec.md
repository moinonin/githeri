# Sample Converted JSONL (Chat Format)

Below is a sample of the converted JSONL (chat format) for the first two entries you shared.

Each line is a complete training example containing a `messages` array.

## Example 1

```json
{"messages":[{"role":"system","content":"You are a precise specification generator. Output ONLY a YAML document. No code, no commentary. Convert the given feature request into a valid executable specification with task_id, summary, local_goals (with verification steps), global_goals_refs, and context."},{"role":"user","content":"Create a POST endpoint for advanced query builder (JSON-based query DSL). Support nested conditions, joins. Return 200."},{"role":"assistant","content":"task_id: advanced-query-builder-endpoint\nsummary: \"Implement a POST endpoint for an advanced JSON-based query DSL that supports nested conditions and joins\"\ndepends_on: [\"stage-1-core-models\", \"stage-2-api-routes\"]\nlocal_goals:\n  - id: L1\n    description: \"INSPECT: check existing API routes structure to ensure no conflicting endpoints\"\n    verification:\n      type: cli\n      command: \"cat apps/api/src/routes/queries.ts\"\n      expect:\n        exit_code: 0\n  - id: L2\n    description: \"CREATE: add POST /v1/queries endpoint for advanced query builder\"\n    verification:\n      type: cli\n      command: \"pnpm build --filter=@verified-attention/api\"\n      expect:\n        exit_code: 0\n  - id: L3\n    description: \"VERIFY: POST /v1/queries returns 200 with a valid JSON-based query DSL response\"\n    verification:\n      type: http\n      method: POST\n      url: http://localhost:3000/v1/queries\n      headers:\n        Authorization: \"Bearer {test_token}\"\n      body:\n        contentId: \"test-content\"\n        query: '{\"filter\": {\"and\": [{\"eq\": {\"field\": \"status\", \"value\": \"active\"}}, {\"gt\": {\"field\": \"createdAt\", \"value\": \"2023-01-01\"}}]}}'\n      expect:\n        status: 200\n        json_schema:\n          type: object\n          properties:\n            queryId: { type: string }\n            results: { type: array }\n          required: [queryId, results]\nglobal_goals_refs: [\"G5\", \"G13\"]\ncontext:\n  language: TypeScript\n  framework: Express\n  orm: Prisma\n  test_framework: Vitest"}]}
```

---

## Example 2

```json
{"messages":[{"role":"system","content":"You are a precise specification generator. Output ONLY a YAML document. No code, no commentary. Convert the given feature request into a valid executable specification with task_id, summary, local_goals (with verification steps), global_goals_refs, and context."},{"role":"user","content":"Add a GET endpoint for migration progress dashboard (records migrated, errors, lag). Per table. Return 200."},{"role":"assistant","content":"task_id: migration-progress-dashboard\nsummary: \"Add a GET endpoint to display migration progress dashboard\"\ndepends_on: [\"stage-1-core-models\", \"stage-2-pipeline\"]\nlocal_goals:\n  - id: L1\n    description: \"INSPECT: check existing migration model and routes before adding endpoints\"\n    verification:\n      type: file_exists\n      path: \"src/models/Migration.ts\"\n      expect:\n        exists: true\n  - id: L2\n    description: \"INSPECT: check existing API routes structure\"\n    verification:\n      type: cli\n      command: \"cat apps/api/src/routes/migrations.ts\"\n      expect:\n        exit_code: 0\n  - id: L3\n    description: \"CREATE: add GET /v1/migrations/progress endpoint and migration model extensions\"\n    verification:\n      type: cli\n      command: \"pnpm build --filter=@verified-attention/api\"\n      expect:\n        exit_code: 0\n  - id: L4\n    description: \"VERIFY: GET /v1/migrations/progress returns migration progress dashboard\"\n    verification:\n      type: http\n      method: GET\n      url: http://localhost:3000/v1/migrations/progress\n      headers:\n        Authorization: \"Bearer {test_token}\"\n      expect:\n        status: 200\n        json_schema:\n          type: object\n          properties:\n            table: { type: string }\n            recordsMigrated: { type: integer }\n            errors: { type: array }\n            lag: { type: number }\n          required: [table, recordsMigrated, errors, lag]\nglobal_goals_refs: [\"G5\", \"G13\"]\ncontext:\n  language: TypeScript\n  framework: Express\n  orm: Prisma\n  test_framework: Vitest"}]}
```

---

## Notes

- Each line is a complete training example.
- The **system** message defines the model's behavior.
- The **user** message contains the natural-language feature request.
- The **assistant** message contains the corresponding executable YAML specification (`spec_yaml`) from the original dataset.
- This format is compatible with conversational fine-tuning frameworks such as:
  - **Unsloth**
  - **Axolotl**
  - **LLaMA Factory**
  - Any framework that accepts OpenAI-style chat-format datasets.
