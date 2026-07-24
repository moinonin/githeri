# Zod Discriminated Union Test Pattern

## Context
When testing Zod discriminated unions (e.g., VAP EvidencePayloadSchema with `evidenceType` as discriminator), the discriminator field must match exactly for each union member. Mismatched payload fields are correctly rejected by Zod.

## Pattern

```typescript
// Schema definition (from evidence.ts)
export const EvidencePayloadSchema = z.discriminatedUnion('evidenceType', [
  z.object({ evidenceType: z.literal('E-INTERACTION'), payload: InteractionEvidencePayloadSchema }),
  z.object({ evidenceType: z.literal('E-VISIBLE'), payload: VisibilityEvidencePayloadSchema }),
  z.object({ evidenceType: z.literal('E-DURATION'), payload: DurationEvidencePayloadSchema }),
  z.object({ evidenceType: z.literal('E-CONTEXT'), payload: ContextEvidencePayloadSchema }),
  z.object({ evidenceType: z.literal('E-CUSTOM'), payload: CustomEvidencePayloadSchema })
]);
```

## Test Cases Required

### 1. Valid Combinations (should pass)
Test each discriminator value with its correct payload schema:
```typescript
// E-INTERACTION with interaction payload
{ evidenceType: 'E-INTERACTION', payload: { clickCount: 5, avgScrollVelocity: 1.2 } }

// E-VISIBLE with visibility payload
{ evidenceType: 'E-VISIBLE', payload: { visibleDurationMs: 5000, maxVisibilityRatio: 0.9, avgVisibilityRatio: 0.5 } }

// E-DURATION with duration payload
{ evidenceType: 'E-DURATION', payload: { sessionStartTime: 1000, activeDurationMs: 45000 } }

// E-CONTEXT with context payload
{ evidenceType: 'E-CONTEXT', payload: { platform: 'browser', userAgent: 'Mozilla/5.0' } }

// E-CUSTOM with arbitrary payload
{ evidenceType: 'E-CUSTOM', payload: { anyField: 'anyValue', nested: { foo: 1 } } }
```

### 2. Mismatched Combinations (should fail)
Test each discriminator value with INCORRECT payload schema:
```typescript
// E-INTERACTION with visibility payload (wrong)
{ evidenceType: 'E-INTERACTION', payload: { visibleDurationMs: 5000, maxVisibilityRatio: 0.9, avgVisibilityRatio: 0.5 } }

// E-VISIBLE with interaction payload (wrong)
{ evidenceType: 'E-VISIBLE', payload: { clickCount: 5, avgScrollVelocity: 1.2 } }

// E-DURATION with context payload (wrong)
{ evidenceType: 'E-DURATION', payload: { platform: 'browser' } }
```

### 3. Invalid Discriminator Values (should fail)
```typescript
{ evidenceType: 'E-BOGUS', payload: { clickCount: 5 } }
{ evidenceType: 'INTERACTION', payload: { clickCount: 5 } } // wrong case
{ evidenceType: '', payload: { clickCount: 5 } }
```

## Key Insight
Zod's `discriminatedUnion` correctly rejects mismatched payloads — it doesn't just strip unknown fields. The test MUST verify both:
1. Valid combinations pass
2. Mismatched combinations fail

This is a common pitfall where developers assume Zod strips extra fields (like `z.object().passthrough()`), but discriminated unions are strict about the payload matching the discriminator.

## VAP-Specific Notes
- Evidence types: E-INTERACTION, E-VISIBLE, E-DURATION, E-CONTEXT, E-CUSTOM
- Each has a dedicated payload schema in evidence.ts
- The discriminated union is used in EvidencePayloadSchema (lines 84-90)
- EvidenceSchema uses a simpler `z.union()` for the payload (not discriminated) - this is a deliberate design choice for the top-level EvidenceSchema

## Common Test Mistake
```typescript
// WRONG - assumes Zod strips extra fields
const payload = { evidenceType: 'E-INTERACTION', payload: { visibleDurationMs: 5000 } };
const result = EvidencePayloadSchema.safeParse(payload);
expect(result.success).toBe(false); // This SHOULD fail - it does!

// WRONG - assumes it should pass because all fields are optional
// Some InteractionEvidencePayloadSchema fields are optional, so Zod doesn't reject
```

Always test both valid and invalid combinations explicitly.