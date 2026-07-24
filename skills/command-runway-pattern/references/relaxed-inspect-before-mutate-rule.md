# Relaxed Inspect-Before-Mutate Rule (Clarification)

## The Rule as Patched

> **Invariant:** Each ✎ command must have at least one ⏾ command in its `depends_on` chain that reads the target before modification. All ⏾ commands that are prerequisites must exit 0 before their dependent ✎ commands start. ✓ commands run after their ✎ dependencies — in the same stage or at stage end.

## Why the Original Rule Was Too Strict

The original rule: *"in every stage, all ⏾ commands must exit 0 before any ✎ command starts"*

This forbids legitimate patterns like:
1. **Generate → Read → Patch** — A command creates a file (✎), then a later command reads it (⏾) to understand its structure, then another command patches it (✎)
2. **Migration → Read → Seed** — Run migration (✎), read resulting schema (⏾), seed data (✎)
3. **Compile → Read Artifact → Test** — Build (✎), read compiled output (⏾), run tests (✓)

In the VAE Sprint 2 runbook, Stage B (Prisma Schema & Database):
- C8: `npx prisma init` (✎ create schema.prisma)
- C9: `read_file prisma/schema.prisma` (⏾ re-read generated scaffold)
- C10: `patch prisma/schema.prisma` (✎ replace User model)

This is valid and necessary — you must read the generated scaffold before patching it. The DAG enforces the correct order:
- C9 `depends_on: [C8]`
- C10 `depends_on: [C9]`

## Correct Enforcement

The DAG (`depends_on`) already enforces the correct discipline. The rule should be:

> **Each ✎ command must have a ⏾ in its transitive `depends_on` closure that reads the target file before the ✎ modifies it.**

Not: "all ⏾ in stage before any ✎ in stage."

## Implementation for Agents/Harnesses

When validating a runbook:
1. For each ✎ command, walk its `depends_on` DAG
2. Verify at least one ⏾ command in that DAG reads the same target path (or parent directory for creates)
3. If missing, flag as "missing inspection before mutation"
4. Stage-level ordering is derived from DAG, not a blanket "all ⏾ before all ✎"

## Files Referenced

- `SKILL.md` — Rule patched in "Stage Structure" section
- `references/command-runway-pattern.md` — Reference doc patched in "Command Roles" section
- `/tmp/sprint-runbooks/sprint-02/PLAN.md` Stage B — Worked example of Generate→Read→Patch pattern