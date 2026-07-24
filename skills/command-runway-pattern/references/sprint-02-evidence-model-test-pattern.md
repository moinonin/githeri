# Sprint 02: Evidence Model Test Pattern — Worked Example

## Context

Sprint 2 of the Verified Attention Engine (VAE) project: "Evidence Model & Pipeline Skeleton"
- Goal: Implement core VAP Evidence data model and processing pipeline skeleton
- Stage A: Evidence Model — Complete VAP Section 5 Implementation
- Task: Write comprehensive unit tests for the Evidence model (already implemented in `packages/core/src/evidence.ts`)

## The Pattern: Generate → Read → Patch

### What Happened (The Anti-Pattern)

**First attempt (wrong):**
1. ✎ `write_file packages/core/src/evidence.test.ts` — wrote tests assuming a nested payload structure: `payload: { evidenceType: 'E-INTERACTION', payload: {...} }`
2. ⏾ `read_file packages/core/src/evidence.ts` — read implementation AFTER writing tests
3. → TypeScript errors: schema mismatches, EvidenceType not found, property errors

**Second attempt (correct):**
1. ⏾ `read_file packages/core/src/evidence.ts` — read actual implementation FIRST
2. ⏾ `read_file docs/specs/0001-verified-attention-protocol.md` (Section 5) — read normative spec
3. → Understood actual structure: discriminated union on `evidenceType` with FLAT payload
4. ✎ `write_file packages/core/src/evidence.test.ts` — write tests matching ACTUAL implementation
5. ✓ `pnpm test` — tests pass

### Key Technical Learnings

#### 1. EvidenceType Enum Not Re-exported from evidence.ts

The `EvidenceType` enum is defined in `common.ts` but **not re-exported** from `evidence.ts`:
```typescript
// common.ts - defines it
export enum EvidenceType {
  INTERACTION = 'E-INTERACTION',
  VISIBLE = 'E-VISIBLE',
  DURATION = 'E-DURATION',
  CONTEXT = 'E-CONTEXT',
  CUSTOM = 'E-CUSTOM'
}

// evidence.ts - imports EvidenceTypeSchema but NOT the enum
import { EvidenceTypeSchema } from './common';
// EvidenceType enum NOT exported from evidence.ts
```

**Fix for tests:** Use string literals `'E-INTERACTION'` etc. directly, or cast with `as any`:
```typescript
const evidence = {
  evidenceType: 'E-INTERACTION' as any,  // or just use string literal
  // ...
};
```

#### 2. Payload Structure is FLAT (Discriminated Union)

The EvidenceSchema uses a **discriminated union on `evidenceType`** with FLAT payload:

```typescript
// EvidenceSchema.payload uses a union of the 5 payload schemas directly:
payload: z.union([
  InteractionEvidencePayloadSchema,    // { avgScrollVelocity?, scrollDirectionChanges?, clickCount?, keyPressCount?, interactionDurationMs?, readingPauses?, engagementScore? }
  VisibilityEvidencePayloadSchema,     // { visibleDurationMs, maxVisibilityRatio, avgVisibilityRatio, viewportIntersections? }
  DurationEvidencePayloadSchema,       // { sessionStartTime, sessionEndTime?, activeDurationMs, idleDurationMs?, heartbeatCount? }
  ContextEvidencePayloadSchema,        // { platform, userAgent?, viewportSize?, devicePixelRatio?, timezone?, language?, connectionType?, effectiveType? }
  CustomEvidencePayloadSchema          // Record<string, unknown>
])
```

**NOT nested:** The payload is NOT `{ evidenceType: 'E-INTERACTION', payload: {...} }` — that's the `EvidencePayloadSchema` (discriminated union) which is used internally.

**Test payloads must be FLAT:**
```typescript
// Correct - flat structure
payload: {
  avgScrollVelocity: 150.5,
  scrollDirectionChanges: 3,
  clickCount: 5,
  // ...
}

// Incorrect - nested (this is the EvidencePayloadSchema structure)
payload: {
  evidenceType: 'E-INTERACTION',
  payload: { ... }
}
```

#### 3. EvidenceType Enum Values Are String Constants

The `EvidenceType` enum values are the literal strings:
```typescript
export enum EvidenceType {
  INTERACTION = 'E-INTERACTION',
  VISIBLE = 'E-VISIBLE',
  DURATION = 'E-DURATION',
  CONTEXT = 'E-CONTEXT',
  CUSTOM = 'E-CUSTOM'
}
```

In tests, use the literal strings: `'E-INTERACTION'`, `'E-VISIBLE'`, etc.

#### 4. EvidenceSchema Payload is a Union, Not Discriminated Union at Top Level

The `EvidenceSchema` uses `z.union([...])` for payload, not `z.discriminatedUnion`. The discriminated union is internal (`EvidencePayloadSchema`).

So in tests, the payload is just the raw payload object without an `evidenceType` discriminant at the payload level — the discriminant is at the top level (`evidence.evidenceType`).

#### 5. EvidenceType Enum Not Exported from evidence.ts

The `EvidenceType` enum is defined in `common.ts` and used via `EvidenceTypeSchema` in `evidence.ts`, but the enum itself is **not re-exported** from `evidence.ts`.

**Test workaround:** Use string literals directly or import from `common`:
```typescript
// Option 1: Import from common
import { EvidenceType } from './common';

// Option 2: Use string literals with casting
evidenceType: 'E-INTERACTION' as any
```

#### 6. EvidenceState Enum IS Exported

`EvidenceState` enum IS exported from `evidence.ts` (defined locally in evidence.ts):
```typescript
export enum EvidenceState {
  PROPOSED = 'PROPOSED',
  VALIDATED = 'VALIDATED',
  INDEXED = 'INDEXED',
  ARCHIVED = 'ARCHIVED',
  DISCARDED = 'DISCARDED'
}
```

#### 7. Payload Schemas Not Exported Individually

The individual payload schemas (`InteractionEvidencePayloadSchema`, `VisibilityEvidencePayloadSchema`, etc.) are used internally by `EvidenceSchema` but **not exported** from `evidence.ts`.

Only `EvidenceSchema`, `EvidenceProvenanceSchema`, `EvidenceMetadataSchema`, `EvidenceStateSchema`, `EvidenceWithStateSchema`, `EvidenceValidationResultSchema` are exported.

**Test approach:** Test via `EvidenceSchema.safeParse()` with complete evidence objects, not by testing individual payload schemas directly.

#### 8. createEvidence Helper Returns Partial (Missing signature)

`createEvidence()` returns `Omit<Evidence, 'signature'>` — the signature must be added by the producer.

```typescript
export function createEvidence(
  params: Omit<Evidence, 'evidenceId' | 'timestamp' | 'signature'> & { timestamp?: string }
): Omit<Evidence, 'signature'>
```

#### 8. computeEvidenceHash is a Stub

```typescript
export function computeEvidenceHash(evidence: Evidence): Hash {
  return '' as Hash;  // Stub - implementation in crypto package
}
```

#### 9. Common Schema Imports

All base schemas come from `./common`:
```typescript
import {
  TimestampSchema, UUIDSchema, SessionIdSchema, SourceIdSchema,
  EvidenceIdSchema, EvidenceTypeSchema, ConfidenceSchema,
  HashSchema, SignatureSchema, BaseMetadataSchema, zodIssuesToPlain,
  type Hash, type ZodIssue
} from './common';
```

### Test File Structure That Works

```typescript
import { describe, it, expect } from 'vitest';
import {
  EvidenceSchema,
  EvidenceProvenanceSchema,
  EvidenceMetadataSchema,
  EvidenceStateSchema,
  EvidenceWithStateSchema,
  EvidenceValidationResultSchema,
  EvidenceState,
  createEvidence,
  validateEvidence,
  computeEvidenceHash,
  type Evidence,
  type EvidenceValidationResult,
  type EvidenceProvenance,
  type EvidenceMetadata,
  type EvidenceWithState,
} from './evidence';
import {
  TimestampSchema,
  UUIDSchema,
  SessionIdSchema,
  SourceIdSchema,
  EvidenceIdSchema,
  HashSchema,
  SignatureSchema,
  BaseMetadataSchema,
  zodIssuesToPlain,
} from './common';

describe('Evidence Model - VAP Section 5', () => {
  // Test complete evidence objects via EvidenceSchema.safeParse()
  // Test individual schemas (Provenance, Metadata, State, etc.)
  // Test helper functions (createEvidence, validateEvidence, computeEvidenceHash)
  // Test enums via string constants
  // Test schema exports
  // Test completeness of EvidenceSchema shape
});
```

### Syntax Error Fixed

**Error:** `Expected "}" but found ")"` at line ~467

**Cause:** Extra closing `});` in the `EvidenceValidationResultSchema` test block:
```typescript
// Wrong - extra closing
    });
  });
  });

// Correct
    });
  });
```

### Complete Test Coverage Achieved

| Test Category | Tests | Status |
|---------------|-------|--------|
| Valid evidence objects (5 types) | 5 | ✅ |
| Invalid evidence (id, confidence, sessionId, hash, empty observations, missing fields) | 6 | ✅ |
| EvidenceProvenanceSchema | 4 | ✅ |
| EvidenceMetadataSchema | 3 | ✅ |
| EvidenceStateSchema | 2 | ✅ |
| EvidenceWithStateSchema | 1 | ✅ |
| EvidenceValidationResultSchema | 2 | ✅ |
| createEvidence helper | 2 | ✅ |
| validateEvidence function | 3 | ✅ |
| computeEvidenceHash | 1 | ✅ |
| Enum values | 2 | ✅ |
| Schema exports | 1 | ✅ |
| Common schemas | 4 | ✅ |
| Model completeness | 2 | ✅ |
| Type inference | 2 | ✅ |
| Cross-package | 1 | ✅ |

**Total: ~50 tests covering all VAP Section 5 requirements**

### Run Commands

```bash
# Run evidence tests only
cd packages/core && pnpm test evidence.test.ts

# Run with coverage
cd packages/core && pnpm test -- --coverage

# Run all tests
pnpm test
```

### Checklist for Future Stages

- [ ] Always ⏾ read_file target implementation BEFORE ✎ write_file tests
- [ ] Verify actual schema structure matches test assumptions
- [ ] Check what's exported from the module under test
- [ ] Use actual string literals for enum values if enum not exported
- [ ] Match payload structure exactly (flat vs nested)
- [ ] Run `pnpm test` after each test file creation
- [ ] Ensure coverage ≥ 80% before advancing