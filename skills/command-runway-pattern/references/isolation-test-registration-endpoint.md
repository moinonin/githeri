# Isolation Test: Registration Endpoint (Worked Example)

This document captures the isolation test run during skill development — applying the COMMAND_RUNWAY method to a generic spec (not VAE) to verify the skill produces non-VAE-contaminated output.

## Spec Used

```markdown
# Feature: User Registration Endpoint

## Requirement
Build a POST /register endpoint that accepts email + password, hashes the password, persists the user, and returns 201 with the user ID. Duplicate email returns 409.

## Constraints
- Node.js 20+, Express, Prisma ORM
- Password hashing with bcrypt (10 rounds)
- Email normalized to lowercase before persistence
- Error shape: {error: string, details?: any}
```

## Generated Artifacts

### PLAN.md (Layer 2) — 5 stages, 27 commands

| Stage | Focus | Key Commands |
|-------|-------|--------------|
| A | Project Scaffold & Preconditions | node/npm version checks, `npm init -y`, install express/prisma/bcrypt, devDeps |
| B | Prisma Schema & Database | `prisma init`, User model with `email @unique`, `passwordHash`, migration |
| C | Registration Service | `registerUser(email, password)`: lowercase email, bcrypt 10 rounds, prisma.user.create, catch P2002 → EMAIL_EXISTS |
| D | Express Route & Error Shape | POST /register, validate body, map errors to `{error, details?}`, return 201 `{id}` / 409 `{error: "EMAIL_EXISTS"}` |
| E | Security Verification & Global Checks | grep for plaintext password logs, full test suite, typecheck |

### RUNBOOK.md (Layer 3) — Same 5 stages, empty execution log, goal verification, JSON extension

### Key Discipline Verified

1. **⏾→✎→✓ ordering** — Every stage has inspect commands before mutate, verify after
2. **DAG via `depends_on`** — Stage B commands depend on Stage A; Stage C depends on B; etc.
3. **Relaxed inspect-before-mutate rule** — Stage B: C8 creates schema, C9 re-reads it, C10 patches it. Valid re-inspection after mutation, enforced by DAG (`C9 depends_on C8`, `C10 depends_on C9`).
4. **No VAE leakage** — Zero references to VAE, VAP, Evidence, Proof, conformance, pnpm, turbo, @verified-attention/*
5. **Agent-agnostic commands** — Generic `shell`, `read_file`, `write_file`, `patch`, `search_files`
6. **Machine-readable JSON** — `depends_on` DAG, `expected` assertions (exit_code, stdout_regex, http_status, body_regex, file_exists), `content_ref` resolution (file://, hash://, inline:)

## Lessons for Future Use

- The three-layer method (prompt → plan → runbook) works for any spec-driven feature
- The relaxed rule ("Each ✎ must have a ⏾ in its depends_on chain reading the target before modification") correctly handles valid re-inspection patterns
- The JSON extension enables orchestration harnesses; `content_ref` with `hash://` enables reproducible builds
- Sprint-to-stage mapping: 1 sprint ≈ 1–3 stages; keep stages < 1 hour / < 15 commands
- Backend-first ordering is a default, not a rule — UI-only features can skip it

## Files Referenced

- `/tmp/runway-test/PLAN.md` — Full Layer 2 plan
- `/tmp/runway-test/RUNBOOK.md` — Full Layer 3 runbook
- `/tmp/runway-test/SPEC.md` — Input spec