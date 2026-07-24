# Sprint 18: Mobile & Desktop SDKs — COMMAND_RUNWAY Worked Example

**Sprint**: 18 of 21 (Phase 3: Browser Extension / Mobile & Desktop SDKs)
**Generated**: 2026-07-23
**Status**: Draft Plan (PLAN.md + RUNBOOK.md created)

---

## Summary

This reference documents the COMMAND_RUNWAY plan and runbook for Sprint 18, which delivers native Android (Kotlin), iOS (Swift), and Desktop (Electron/Tauri + Rust/Swift/C) SDKs for the Verified Attention Engine, plus cross-platform evidence parity tests, mobile app store compliance artifacts, and integration documentation.

---

## Plan Structure (PLAN.md)

**10 Stages** following backend-first ordering with parallel Android/iOS tracks:

| Stage | Name | Commands | Verification Gate |
|-------|------|----------|-------------------|
| A | Android SDK Core | A1–A8 | `./gradlew :core:build` → exit 0 |
| B | Android Observers (VAP §4) | B1–B9 | `./gradlew :observers:test` → exit 0 |
| C | Android Consent/Queue/Network/Session | C1–C8 | `./gradlew build test` → exit 0 |
| D | iOS SDK Core (SPM) | D1–D7 | `swift build` → exit 0 |
| E | iOS Observers (VAP §4) | E1–E8 | `swift test --filter VAEObserversTests` → exit 0 |
| F | iOS Consent/Queue/Network/Session | F1–F7 | `swift test` → exit 0 |
| G | Desktop SDK (Electron/Tauri + native) | G1–G11 | `npm run build` → exit 0 |
| H | Cross-Platform Evidence Parity | H1–H8 | `npm test` → exit 0 |
| I | Mobile App Store Compliance | I1–I7 | Manual review of PrivacyInfo.xcprivacy + data-safety.xml |
| J | Documentation (Mobile + Desktop) | J1–J8 | Directory existence check |

**Dependency Graph**:
```
A → B → C
D → E → F
              ↘
               G → H,I,J (parallel)
```

---

## Key Patterns Demonstrated

### 1. Multi-Platform Parallel Tracks
Android (Stages A–C) and iOS (Stages D–F) run in parallel with identical stage structure — same VAP observers, same evidence schema, same verification gates. This is the **backend-first, platform-parallel** pattern.

### 2. Shared Schema as Single Source of Truth
Stage H creates `vap-evidence-schema.json` consumed by all platform test runners. Prevents schema drift — the #1 risk for cross-platform SDKs.

### 3. Compliance as Verifiable Stage
Stage I treats App Store / Play Store compliance as a verification gate with concrete artifacts (PrivacyInfo.xcprivacy, data-safety.xml), not a documentation afterthought.

### 4. Desktop Native Modules via Tauri/Rust
Stage G uses Tauri with Rust for Windows/Linux and Swift for macOS native modules — unified build via `cargo` and `npm run build`. Demonstrates **polyglot native layer** pattern.

### 5. Machine-Readable JSON Extension
Both PLAN.md and RUNBOOK.md include full JSON serialization with:
- Structured goals (local L1–L6, global G1–G6)
- Preconditions as executable shell checks
- Stage completion conditions as command exit codes
- DAG via `depends_on` for orchestration harnesses

---

## Files Produced

| File | Purpose |
|------|---------|
| `/tmp/sprint-runbooks/sprint-18/PLAN.md` | Layer 2: Static stage-by-stage plan with command tables |
| `/tmp/sprint-runbooks/sprint-18/RUNBOOK.md` | Layer 3: Execution log template + JSON for automation |

---

## Lessons for Future Sprints

1. **Platform-parallel stages reduce calendar time** — Android and iOS tracks are independent until Stage G (Desktop) and Stage H (Parity). Assign different engineers.

2. **Evidence parity tests must exist before platform code** — In practice, write Stage H's `vap-evidence-schema.json` and test fixtures *first* (could be Stage 0), then implement platforms against it. This runbook puts it after for logical grouping, but TDD order would reverse it.

3. **Compliance artifacts are code, not docs** — PrivacyInfo.xcprivacy is XML that Apple validates; data-safety.xml maps to Play Console form fields. Generate them from a shared compliance model, don't hand-edit.

4. **Desktop native modules need CI matrix** — Stage G's verification (`npm run build`) only tests the current OS. Real verification needs GitHub Actions matrix: `ubuntu-latest`, `macos-latest`, `windows-latest` with `cargo build --target` for each.

5. **Bundle size gates belong in each platform stage** — Add ✓ commands after each platform's build: `du -sh <artifact>` with size assertion. This runbook has it only in global goals (G6).

---

## Related References

- `references/sprint-02-worked-example.md` — Evidence model & pipeline skeleton (Phase 0)
- `references/sprint-11-proof-generation.md` — Proof generation at scale (Phase 2)
- `references/sprint-14-security-hardening.md` — Security hardening & pentest (Phase 2)