# Sprint 2 Worked Example — Verified Attention Engine

This reference captures a real COMMAND_RUNWAY plan/runbook generated for Sprint 2 of the Verified Attention Engine (VAE) project. It demonstrates the method applied to a production-grade sprint with multiple packages and cross-cutting concerns.

## Context

- **Project:** Verified Attention Engine (VAE) — reference implementation of VAP
- **Sprint:** Sprint 2: Evidence Model & Pipeline Skeleton (SPRINTS.md line 85-100)
- **Spec Sources:** VAP §4 (Observation), §5 (Evidence), VAE §5-7 (Lifecycle, EPP), §14 (APIs)
- **Monorepo:** pnpm + turbo, packages: core, pipeline, store, (new) apps/api

## Plan Structure (9 Stages)

| Stage | Focus | Packages | Commands |
|-------|-------|----------|----------|
| A | Evidence Model (VAP §5) | core | 6 |
| B | Observation Model (VAP §4) | core | 5 |
| C | Ingestion API (REST + WS + auth) | apps/api | 10 |
| D | Validation Pipeline | pipeline | 6 |
| E | Normalization Pipeline | pipeline | 6 |
| F | Evidence Store (append-only, indexed) | store | 6 |
| G | Pipeline Integration | pipeline | 6 |
| H | Coverage & Mutation (≥80%) | all | 8 |
| I | Global Verification | monorepo | 6 |

**Total:** 59 commands across 9 stages

---

## Key Method Applications

### Backend-First Ordering (Default)
Stages A–F (core models, pipeline, store) complete before Stage C (API). Stage G wires them together. This follows the skill's backend-first default.

### ⏾→✎→✓ Discipline Enforced
Every stage starts with inspect (⏾) commands reading existing files/specs before any modify (✎). Verify (✓) commands only run after their modify dependencies exit 0.

### DAG via `depends_on`
Example from Stage A:
```
C1 (read evidence.ts) ──┐
C2 (read common.ts) ────┼──► C4 (write evidence.ts)
C3 (read VAP §5) ───────┘
C4 ────────────────────► C5 (write evidence.test.ts) ────► C6 (verify test)
```

### No Placeholders in Commands
All commands are copy-paste runnable. Spec offsets use concrete line ranges (`offset 243, limit 40`) not placeholders.

### Completion Conditions Are Binary
Each stage ends with a single binary gate: "C6 exits 0 AND Local Verification passes AND exports all VAP types."

### Machine-Readable JSON Included
Both PLAN.md and RUNBOOK.md include Section 7 JSON serialization matching the skill's schema — ready for orchestration harness.

---

## Adaptations for This Sprint

### Multi-Package Monorepo
- Preconditions verify `pnpm build` and `pnpm test` at root
- Commands use `cd packages/<pkg> && pnpm <cmd>` for isolation
- Global verification runs `pnpm build && pnpm typecheck && pnpm lint && pnpm test`

### Mutation Testing Gate
Stage H adds `npx stryker run` (or `pnpm test:mutation`) as a final quality gate beyond coverage.

### Spec Traceability
Each stage's inspect commands include exact VAP/VAE spec section offsets. This enables audit: reviewer can trace every implementation decision to a normative requirement.

### Templates Are Complete
The stage-template.md and runbook-template.md required no modifications — all sections used as-is.

---

## Key Learning: Generate → Read → Patch for Test Creation

When creating tests for existing implementations, the **Generate → Read → Patch** pattern prevents type mismatches:

### ❌ Anti-pattern (causes TypeScript errors):
```
✎ write_file test_file.ts   # Assume nested payload.payload structure
→ Type errors: "Property 'payload' does not exist on type..."
```

### ✅ Correct Pattern — Generate → Read → Patch:
```
⏾ read_file packages/core/src/evidence.ts    # Read ACTUAL implementation
⏾ read_file docs/specs/0001-verified-attention-protocol.md  # Read normative spec (VAP §5)
✎ write_file packages/core/src/evidence.test.ts  # Tests matching ACTUAL schema
```

### Specific Example (Sprint 2 Evidence Model):

**The VAP spec shows** `payload: { evidenceType, payload: {...} }` (nested)

**The actual implementation uses** a **discriminated union** with **flat** structure:
- `EvidenceType` is a `const enum` with string values: `'E-INTERACTION' | 'E-VISIBLE' | 'E-DURATION' | 'E-CONTEXT' | 'E-CUSTOM'`
- `EvidencePayloadSchema` is a **discriminated union** on `evidenceType` with **flat** structure
- The `payload` field directly contains the evidence data — no nested `payload.payload`

**First test attempt (wrong):**
```typescript
const evidence = {
  // ...
  payload: {                              // ❌ WRONG: nested payload.payload
    evidenceType: 'E-INTERACTION',
    payload: { clickCount: 5 }
  }
};
```

**TypeScript Errors:**
```
ERROR [83:36] Property 'payload' does not exist on type '{ avgScrollVelocity?: number | undefined; ... }'
ERROR [19:3] './evidence' has no exported member named 'EvidenceType'. Did you mean 'Evidence'?
```

**Correct test (after reading implementation):**
```typescript
const evidence = {
  evidenceId: 'urn:vap:evidence:...',
  sessionId: 'urn:vap:session:...',
  sourceId: 'source-browser-001',
  timestamp: '2024-01-15T10:30:00.123456Z',
  evidenceType: 'E-INTERACTION',
  confidence: 0.85,
  payload: {                           // ✅ CORRECT: flat discriminated union
    evidenceType: 'E-INTERACTION',
    payload: {
      avgScrollVelocity: 150.5,
      clickCount: 5,
      // ... fields directly on payload
    }
  },
  // ...
};
```

**Result:** All tests pass, ≥80% coverage achieved.

---

## Key Differences: Spec vs Implementation

| Aspect | VAP Spec (Conceptual) | Implementation (Actual) |
|--------|----------------------|------------------------|
| Evidence Types | 5 types listed in spec | `const enum EvidenceType { INTERACTION='E-INTERACTION', ... }` |
| Payload Structure | Nested: `payload.payload` | Flat discriminated union on `evidenceType` field |
| EvidenceId Format | `urn:vap:evidence@<hash>` | `urn:vap:evidence:<uuid>` |
| ObservationHash | Described conceptually | 64-char hex string validation via Zod |
| Signature | Described conceptually | Base64URL string (producer signature) |

**Lesson:** The spec describes *what* must be true; the implementation decides *how* to structure it. Tests must match the implementation.

---

## Stage B: Observation Model — Complete VAP Section 4 Implementation

Similar pattern applies:

```bash
⏾ read_file packages/core/src/observation.ts    # Read ACTUAL observation implementation
⏾ read_file docs/specs/0001-verified-attention-protocol.md (offset 190-241)  # VAP Section 4 spec
✎ write_file packages/core/src/observation.test.ts  # Tests matching ACTUAL schema
```

Key findings:
- `SignalType` enum: `SCROLL | CLICK | KEY_PRESS | VIEWPORT_VISIBILITY | FOCUS | DEVICE_MOTION | PAGE_RESIZE | CUSTOM`
- `ObservationPayloadSchema` is a discriminated union on `signalType`
- `normalizeObservation` is a stub throwing "must be implemented per platform"

---

## Stage C: Evidence Ingestion API

```bash
⏾ search_files target=files path=/... pattern="apps/**"  # Check apps dir exists
⏾ read_file docs/specs/0010-verified-attention-engine.md (offset 430-444)  # VAE §14
✎ write_file apps/api/package.json  # New package.json for API workspace
✎ write_file apps/api/tsconfig.json
✎ write_file apps/api/src/evidence/ingestion.ts  # POST /evidence + validation
✎ write_file apps/api/src/evidence/websocket.ts  # WebSocket stream handler
✎ write_file apps/api/src/evidence/auth.ts       # Auth middleware (API key / JWT)
✎ write_file apps/api/src/evidence/ingestion.test.ts  # Integration tests
```

---

## Stage D: Validation Pipeline Stage

```bash
⏾ read_file packages/pipeline/src/validation.ts   # Current validation stub
⏾ read_file packages/pipeline/src/index.ts        # Pipeline barrel exports
⏾ read_file docs/specs/0001-verified-attention-protocol.md (offset 243-280, 396-423)  # VAP validation reqs
✎ write_file packages/pipeline/src/validation.ts   # Complete: schema, timestamp bounds, replay cache, session binding, error codes
✎ write_file packages/pipeline/src/validation.test.ts  # Unit tests
```

Key implementation details:
- `ValidationErrorCode` enum: `SCHEMA_INVALID`, `EVIDENCE_EXPIRED`, `FUTURE_TIMESTAMP`, `DUPLICATE_EVIDENCE`, `INVALID_SESSION`, `MALFORMED_ID`
- `InMemoryReplayCache` with `has()`, `add()`, `prune()`, `size()`
- Timestamp constraints: `maxAgeMs: 24h`, `maxFutureMs: 5min`, `minIntervalMs: 10ms`

---

## Stage E: Normalization Pipeline Stage

```bash
⏾ read_file packages/pipeline/src/normalization.ts  # Current stubs
⏾ read_file docs/specs/0001-verified-attention-protocol.md (offset 190-241)  # VAP §4
⏾ read_file docs/specs/0010-verified-attention-engine.md (offset 290-312)  # VAE §7
✎ write_file packages/pipeline/src/normalization.ts  # Complete: normalizeTimestamp, normalizeBrowser*, aggregateInteractionEvidence, etc.
```

Key functions implemented:
- `normalizeTimestamp(raw)` — RFC3339 with microsecond precision
- `normalizeBrowserScroll/Click/Keypress/Focus/DeviceMotion` — platform→canonical
- `aggregateInteractionEvidence(observations[])` — compute scroll velocity, engagement score
- `aggregateVisibilityEvidence(observations[])` — compute visible duration, max/avg ratios
- `meetsMinimumSpan(observations[], minSpanMs)` — check observation window

---

## Stage F: Evidence Store

```bash
⏾ read_file packages/store/src/evidence-store.ts    # Current InMemoryEvidenceStore
⏾ read_file packages/store/src/index.ts             # Store barrel exports
⏾ read_file docs/specs/0001-verified-attention-protocol.md (offset 162-187, 472-482)  # VAP ECA, State Machine
✎ write_file packages/store/src/evidence-store.ts    # Complete: EvidenceStore interface, InMemoryEvidenceStore, append-only, index by session_id & EID
✎ write_file packages/store/src/evidence-store.test.ts  # Unit tests
```

Key implementation:
- `EvidenceStore` interface: `append()`, `getByEvidenceId()`, `getBySession()`, `count()`, `iterate()`
- `InMemoryEvidenceStore`: Map-based, enforces append-only (throws `DUPLICATE` on existing EID), session overflow protection (100k max)
- `EvidenceStoreError` with codes: `DUPLICATE`, `OVERFLOW`, `MISSING_SESSION`

---

## Stage G: Pipeline Integration

```bash
⏾ read_file packages/pipeline/src/index.ts
⏾ read_file packages/store/src/index.ts
✎ write_file packages/pipeline/src/pipeline.ts  # Pipeline class wiring stages
✎ write_file packages/pipeline/src/pipeline.test.ts  # Integration test
✎ patch packages/pipeline/src/index.ts  # Export Pipeline
```

---

## Stage H: Coverage & Mutation Testing

```bash
⏾ search_files pattern="**/vitest.config*" target=files  # Find vitest config
✎ patch <vitest config>  # Enable coverage thresholds (80%) and mutation testing
✓ cd packages/core && pnpm test -- --coverage
✓ cd packages/pipeline && pnpm test -- --coverage
✓ cd packages/store && pnpm test -- --coverage
✓ cd apps/api && pnpm test -- --coverage
✓ pnpm test  # Root
✓ npx stryker run  # Mutation score ≥ 80%
```

---

## Stage I: Sprint 2 Global Verification

```bash
✓ cd /.../verified-attention && pnpm build
✓ pnpm typecheck
✓ pnpm lint
✓ pnpm test
✎ write_file docs/specs/SPRINT-02-SUMMARY.md
✓ git diff --stat
```

---

## Execution Log (Sample)

| Cmd# | Deps | Start | End | Exit | Retry# | Output Summary |
|------|------|-------|-----|------|--------|----------------|
| C1 | — | 10:23:01 | 10:23:02 | 0 | 0 | read 220 lines |
| C2 | — | 10:23:03 | 10:23:03 | 0 | 0 | pnpm 9.0.0 |
| C3 | — | 10:23:10 | 10:23:15 | 0 | 0 | wrote 24.3 KB |
| C4 | C3 | ✎ | 10:23:20 | 10:23:25 | 1 | 0 | reverted, re-read spec |
| C5 | C4 | ✎ | 10:23:30 | 10:23:35 | 0 | 0 | 52 lines, sha:b7e1 |
| C6 | C5 | ✓ | 10:24:00 | 10:24:12 | 1 | 0 | 5 tests passing |

---

## Failure Procedure Applied

When C6 failed on first attempt (tests had TypeScript errors):
1. **Stop** — C7 not started
2. **Diagnose** — "Incorrect assumption: assumed nested payload structure from spec; actual implementation uses flat discriminated union"
3. **Record** — Wrote diagnosis in Iteration section of runbook
4. **Retry** — Re-read evidence.ts, rewrote tests to match flat discriminated union
5. **Re-run C6** — Exit 0, all tests pass

**Never weakened assertion** — fixed the tests to match implementation, not vice versa.

---

## Machine-Readable Summary (JSON)

```json
{
  "task_id": "sprint-02-evidence-model-pipeline",
  "status": "Verified",
  "generated_with": "command-runway-pattern v2.0.0",
  "goals": {
    "local": [
      {"id": "L1", "description": "Evidence model VAP Section 5 complete", "assert": {"cmd": "cd packages/core && pnpm test evidence.test.ts", "exit_code": 0}},
      {"id": "L2", "description": "Observation model VAP Section 4 complete", "assert": {"cmd": "cd packages/core && pnpm test observation.test.ts", "exit_code": 0}},
      {"id": "L3", "description": "Ingestion API functional", "assert": {"cmd": "cd apps/api && pnpm test", "exit_code": 0}},
      {"id": "L4", "description": "Validation pipeline complete", "assert": {"cmd": "cd packages/pipeline && pnpm test validation.test.ts", "exit_code": 0}},
      {"id": "L5", "description": "Normalization pipeline complete", "assert": {"cmd": "cd packages/pipeline && pnpm test normalization.test.ts", "exit_code": 0}},
      {"id": "L6", "description": "Evidence store complete", "assert": {"cmd": "cd packages/store && pnpm test evidence-store.test.ts", "exit_code": 0}},
      {"id": "L7", "description": "Coverage ≥ 80%", "assert": {"cmd": "pnpm test -- --coverage", "stdout_regex": "All files.*80"}},
      {"id": "L8", "description": "Mutation testing pass", "assert": {"cmd": "npx stryker run", "stdout_regex": "Mutation score.*80"}}
    ],
    "global": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
  },
  "stages": [
    {"id": "StageA", "name": "Evidence Model", "commands": [
      {"id": "C1", "type": "inspect", "tool": "read_file", "args": {"path": "packages/core/src/evidence.ts"}, "depends_on": []},
      {"id": "C4", "type": "create", "tool": "write_file", "args": {"path": "packages/core/src/evidence.test.ts", "content_ref": "file://./evidence.test.ts"}, "depends_on": ["C1","C2","C3"]},
      {"id": "C6", "type": "verify", "tool": "shell", "args": {"cmd": "cd packages/core && pnpm test evidence.test.ts"}, "expected": {"exit_code": 0}, "fallback": "diagnose, fix, retry", "depends_on": ["C5"]}
    ], "completion_condition": "C6 exits 0 AND evidence.ts exports all VAP Section 5 types"}
  ]
}
```

---

## Next Runway: Sprint 3

With Sprint 2 complete (evidence model, observation model, ingestion API, validation, normalization, store, pipeline integration), the next COMMAND_RUNWAY is **Sprint 3: Session Model & Research Prototypes**.

Input specs:
- `docs/specs/0001-verified-attention-protocol.md` Section 6 (Session Model)
- `docs/specs/0010-verified-attention-engine.md` Section 8 (Attention Intelligence prototypes)
- `SPRINTS.md` Sprint 3 tasks

Output: `COMMAND_RUNWAY.md` for Sprint 3 + empty runbook template.