# Sprint 11 Worked Example — Verified Attention Engine

This reference captures a COMMAND_RUNWAY plan/runbook generated for Sprint 11 of the Verified Attention Engine (VAE) project. It demonstrates the method applied to a production-grade sprint focused on proof generation hardening.

## Context

- **Project:** Verified Attention Engine (VAE) — reference implementation of VAP
- **Sprint:** Sprint 11: Proof Generation - Production Ready (SPRINTS.md lines 255–269)
- **Spec Sources:** VAP §10 (Proof of Attention), Appendix A (Cryptographic Requirements), VAE §10 (Proof Generation)
- **Monorepo:** pnpm + turbo, packages: core, pipeline, store, crypto, apps/api, apps/verifier
- **Dependencies:** Sprint 10 (verification engine produces PASS decisions)

## Plan Structure (7 Stages)

| Stage | Focus | Packages | Commands |
|-------|-------|----------|----------|
| A | Proof Generation Pipeline — Core Infrastructure | apps/verifier/src/proof-gen | 10 |
| B | Proof Signing with HSM / Cloud KMS Integration | packages/crypto/hsm | 13 |
| C | Proof Revocation & Supplementary Proofs (VAP §10) | packages/core/proof | 9 |
| D | Proof Retrieval API | apps/api/src/proofs | 11 |
| E | Proof Webhook Delivery | apps/verifier/src/webhooks | 11 |
| F | Conformance Tests — Proof Full (VAP §10 + Appendix A) | tests/conformance/proof-full | 12 |
| G | Load Test — 10K Proofs/Min Generation + Signing | tests/load/proof-gen-10k | 9 |

**Total:** 75 commands across 7 stages

## Key Method Applications

### Backend-First Ordering (Default)
Stages A–C (core proof generation, signing, revocation) complete before Stage D (API) and Stage E (webhooks). Stage F (conformance) validates all prior stages. Stage G (load test) runs last. This follows the skill's backend-first default.

### ⏾→✎→✓ Discipline Enforced
Every stage starts with inspect (⏾) commands reading existing files/specs before any modify (✎). Verify (✓) commands only run after their modify dependencies exit 0.

### DAG via `depends_on`
Example from Stage A:
```
A1 (read proof.ts) ──┐
A2 (read SPRINTS.md) ┼──► A3 (mkdir) ──► A4 (types.ts) ──► A5 (pipeline.ts) ──► A6 (idempotency.ts) ──► A7 (index.ts) ──► A8 (tests) ──► A9 (build) ──► A10 (test)
```

### Spec Traceability
Each stage's inspect commands include exact VAP/VAE spec section offsets and SPRINTS.md line ranges. This enables audit: reviewer can trace every implementation decision to a normative requirement.

### Multi-Package Monorepo Patterns
- Preconditions verify `pnpm build` and `pnpm test` at root
- Commands use `cd <repo> && pnpm build --filter=@vae/<pkg>` for isolation
- Global verification runs `pnpm build && pnpm typecheck && pnpm lint && pnpm test && pnpm test:conformance`

### Load Test as Final Verification Gate
Stage G adds a production-scale load test (10K proofs/min, p99 < 1s) as the final quality gate — beyond unit/conformance tests.

### Machine-Readable JSON Included
Both PLAN.md and RUNBOOK.md include Section 7 JSON serialization matching the skill's schema — ready for orchestration harness.

## Adaptations for This Sprint

### HSM/Cloud KMS Abstraction (Stage B)
Created a provider-agnostic `HSMSigner` interface with three implementations:
- `aws-kms.ts` — AWS KMS
- `azure-keyvault.ts` — Azure Key Vault
- `pkcs11.ts` — PKCS#11 (hardware HSM)

All share common `types.ts` (SignRequest, SignResult, AuditEntry) and `audit.ts` for immutable audit trail. Keys never in process memory.

### Revocation Chain Integrity (Stage C)
Implemented `ProofVersion` type and `verifyRevocationChain()` to ensure supplementary proofs form an unbroken chain back to the original proof — critical for VAP §10 audit requirements.

### Webhook At-Least-Once Delivery (Stage E)
Implemented exponential backoff (max 5 retries), dead letter queue with HMAC-signed payloads for consumer verification, and idempotency keys to handle redelivery safely.

### Conformance Test Structure (Stage F)
Organized by VAP §10 clause:
- `structure.test.ts` — 7 mandatory fields, serialization, hash computation
- `signature.test.ts` — Ed25519/ECDSA verification, key rotation
- `immutability.test.ts` — append-only, no field modification post-sign
- `revocation.test.ts` — REVOKED flag, version chain, supplementary proofs
- `appendix-a.test.ts` — cryptographic requirements, algorithm agility

Each test traces to a spec clause via inline comments.

## Files Generated

- `/tmp/sprint-runbooks/sprint-11/PLAN.md` — Layer 2 static plan (531 lines)
- `/tmp/sprint-runbooks/sprint-11/RUNBOOK.md` — Layer 3 runbook with execution log template (416 lines)

Both follow the skill's templates exactly. The RUNBOOK.md adds an empty Execution Log table (Section 3) to be filled during execution.

## Lessons Learned

1. **Spec offsets beat search**: Using `read_file` with `offset`/`limit` on the spec is faster and more precise than `search_files` for normative references.

2. **Stage count = verification gates**: 7 stages for a 2-week sprint is appropriate — each stage is an independently verifiable increment. Merging stages would lose retry granularity.

3. **Global verification is cheap**: Running `pnpm build && pnpm typecheck && pnpm lint && pnpm test && pnpm test:conformance` at Stage G catches cross-package regressions that per-package tests miss.

4. **JSON serialization enables automation**: The Section 7 JSON can be consumed by a harness to drive execution without LLM in the loop.

5. **Templates are complete**: The stage-template.md and runbook-template.md required no modifications — all sections used as-is.

6. **Provider abstraction pays off**: The HSM interface (Stage B) was designed before any provider implementation, allowing parallel work and clean substitution — a pattern worth repeating for other pluggable components.