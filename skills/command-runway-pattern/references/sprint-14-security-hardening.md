# Sprint 14 Worked Example — Verified Attention Engine

This reference captures a COMMAND_RUNWAY plan/runbook generated for Sprint 14 of the Verified Attention Engine (VAE) project. It demonstrates the method applied to a security-focused sprint with heavy infrastructure and compliance requirements.

## Context

- **Project:** Verified Attention Engine (VAE) — reference implementation of VAP
- **Sprint:** Sprint 14: Security Hardening & Penetration Testing (SPRINTS.md lines 309–327)
- **Spec Sources:** VAP §13 (Security), §17 (Privacy), VAE §10–11 (Security/Privacy), OWASP ASVS Level 2, NIST SSDF
- **Monorepo:** pnpm + turbo, packages: `auth`, `security`, `auth/rbac`, `security/secrets`, `security/encryption-at-rest`, `security/tls`, `apps/api/src/security`
- **Dependencies:** Sprint 13 complete (all APIs and stores exist)

## Plan Structure (10 Stages)

| Stage | Focus | Packages | Commands |
|-------|-------|----------|----------|
| A | Auth Core — Interfaces, Types, Config | `packages/auth/` | 8 |
| B | Auth Implementations — OAuth2/OIDC, API Keys, mTLS | `packages/auth/` | 12 |
| C | RBAC Engine — Roles, Policies, Enforcement, Audit | `packages/auth/rbac.ts` | 10 |
| D | Secrets Management — Vault Client, Rotation, Injection | `packages/security/secrets/` | 10 |
| E | Encryption at Rest — Key Manager, Store Wrappers | `packages/security/encryption-at-rest/` | 10 |
| F | TLS Everywhere — mTLS Mesh, External TLS, Cert Automation | `packages/security/tls/` | 10 |
| G | API Security Hardening — Headers, CSP, Rate Limit, WAF | `apps/api/src/security/` | 10 |
| H | Dependency Security — SBOM, CVE Scan, License Check | `docs/security/` | 8 |
| I | Penetration Testing — Internal + External, Remediation | `docs/security/pentest-report.md` | 8 |
| J | Global Verification — Build, Typecheck, Lint, Test, Conformance, Security Scan | monorepo | 8 |

**Total:** ~94 commands across 10 stages

## Key Method Applications

### Backend-First Ordering (Default) — Infrastructure Before Compliance
Stages A–G build the security infrastructure (auth, RBAC, secrets, encryption, TLS, API hardening) before Stages H–I which verify it (SBOM, CVE scan, pentest). Stage J validates everything. This follows the skill's backend-first default — the security controls must exist before they can be audited.

### ⏾→✎→✓ Discipline Enforced
Every stage starts with inspect (⏾) commands reading existing files/specs before any modify (✎). Verify (✓) commands only run after their modify dependencies exit 0.

### DAG via `depends_on`
Example from Stage A:
```
A1 (read SPRINTS.md) ──┐
A2 (read VAP §13) ─────┼──► A3 (read package.json) ──► A4 (mkdir) ──► A5/A6/A7 (write types/interfaces/config) ──► A8 (build)
```

### Spec Traceability
Each stage's inspect commands include exact VAP/VAE spec section offsets and SPRINTS.md line ranges. This enables audit: reviewer can trace every implementation decision to a normative requirement.

### Multi-Package Monorepo Patterns
- Preconditions verify `pnpm build` and `pnpm test` at root
- Commands use `cd <repo> && pnpm build --filter=@vae/<pkg>` for isolation
- Global verification runs `pnpm build && pnpm typecheck && pnpm lint && pnpm test && pnpm test:conformance && pnpm test:security && pnpm audit --audit-level=critical`

### Compliance as Final Verification Gates
Stages H (SBOM/CVE/license) and I (pentest) add compliance verification as explicit gates — beyond unit/conformance tests. Stage J runs the full security test suite.

### Machine-Readable JSON Included
Both PLAN.md and RUNBOOK.md include Section 7 JSON serialization matching the skill's schema — ready for orchestration harness.

## Adaptations for This Sprint

### Provider Abstraction Pattern (Stages B, D, F)
- **Stage B:** `AuthProvider` interface with three implementations (OAuth2/OIDC, API Key, mTLS) — all share common types and factory
- **Stage D:** `VaultClient` + `CloudSecretsClient` (AWS/GCP/Azure) behind common interface, `RotationManager` for automated rotation, `SecretInjector` for zero-secrets-in-config
- **Stage F:** `MtlsMesh` (SPIFFE/SPIRE), `ExternalTLS` (cert-manager/ACME), `CertManager` (issue/renew/revoke) behind `TLSManager` facade

This pattern — interface first, provider implementations second, factory/manager third — is worth repeating for other pluggable components.

### Store Wrapper Pattern (Stage E)
Created `EncryptedStore` base wrapper (encrypt on write, decrypt on read, transparent to store interface) with three concrete wrappers:
- `EvidenceStoreWrapper` (indexes on encrypted fields)
- `ProofStoreWrapper`
- `AnalyticsWarehouseWrapper` (column-level encryption)

All use per-tenant/environment AES-256-GCM keys from `KeyManager`. This wrapper pattern preserves existing store interfaces while adding encryption transparently.

### Security Middleware Composition (Stage G)
Composed middleware in explicit order: **WAF → Rate Limit → Headers → Auth**. Each is independently testable; the composer enforces order. Tests verify header presence, CSP nonce, rate limit enforcement, WAF rule matching, and middleware order.

### Pentest Integration as Stage (Stage I)
Pentest is a first-class stage with:
1. Internal scanning (nmap, nuclei, sqlmap against staging)
2. External scanning (nmap, nuclei, zap against production domain)
3. Raw findings capture
4. Structured report with remediation tracking
5. Remediation loop (fix → test → build → merge)
6. Post-remediation regression test

This treats pentest as a verification gate, not an afterthought.

### SBOM/CVE/License as Stage (Stage H)
Generates CycloneDX SBOM, runs `pnpm audit` + `audit-ci` with thresholds, runs `license-checker`. Produces three artifacts: `sbom.json`, `license-report.json`, `dependency-scan-report.md`. Gate: zero critical/unpatched CVEs in production dependencies.

## Files Generated

- `/tmp/sprint-runbooks/sprint-14/PLAN.md` — Layer 2 static plan (341 lines)
- `/tmp/sprint-runbooks/sprint-14/RUNBOOK.md` — Layer 3 runbook with execution log template (439 lines)

Both follow the skill's templates exactly. The RUNBOOK.md adds an empty Execution Log table (Section 4) to be filled during execution.

## Lessons Learned

1. **Compliance stages belong in the runway**: Treating SBOM, CVE scan, license check, and pentest as explicit stages (not afterthoughts) ensures they get the same ⏾→✎→✓ discipline and retry granularity as implementation work.

2. **Provider abstraction pays off at infrastructure scale**: The auth/secrets/TLS provider interfaces (Stages B, D, F) were designed before implementations, allowing parallel work and clean substitution — same pattern as Sprint 11 HSM abstraction.

3. **Store wrappers > store modifications**: Wrapping existing stores with encryption (Stage E) is cleaner than modifying store implementations — preserves interfaces, isolates crypto logic, enables tenant isolation.

4. **Middleware order is a testable contract**: Stage G's composer (WAF → rate limit → headers → auth) has a test that verifies order. Security middleware order matters; make it explicit and tested.

5. **Pentest stage needs a remediation loop**: Stage I's I7 (fix → test → build → merge per finding) and I8 (full regression) ensure findings don't just get documented — they get fixed and verified.

6. **Spec offsets beat search**: Using `read_file` with `offset`/`limit` on the spec is faster and more precise than `search_files` for normative references.

7. **Stage count = verification gates**: 10 stages for a 2-week security sprint is appropriate — each stage is an independently verifiable increment. Merging stages would lose retry granularity.

8. **Global verification is cheap**: Running the full monorepo build + typecheck + lint + test + conformance + security + audit at Stage J catches cross-package regressions that per-package tests miss.

9. **JSON serialization enables automation**: The Section 7 JSON can be consumed by a harness to drive execution without LLM in the loop.

10. **Templates are complete**: The stage-template.md and runbook-template.md required no modifications — all sections used as-is.